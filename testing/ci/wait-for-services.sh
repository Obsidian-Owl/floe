#!/bin/bash
# Wait for K8s test services to be ready
# Used by both local testing and CI
#
# Usage: ./testing/ci/wait-for-services.sh [namespace]
#
# Environment:
#   TEST_NAMESPACE        K8s namespace (default: floe-test)
#   POD_TIMEOUT           Pod readiness timeout in seconds (default: 300)
#   JOB_TIMEOUT           Job completion timeout in seconds (default: 180)
#   POLARIS_URL           Polaris API URL (default: http://localhost:8181)
#   POLARIS_CATALOG_NAME  Catalog name to verify (default: floe-e2e)
#   POLARIS_CLIENT_ID     OAuth client ID (default: demo-admin)
#   POLARIS_CLIENT_SECRET OAuth client secret (default: demo-secret)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${1:-${TEST_NAMESPACE:-floe-test}}"
POD_TIMEOUT="${POD_TIMEOUT:-300}"
JOB_TIMEOUT="${JOB_TIMEOUT:-180}"
POLARIS_URL="${POLARIS_URL:-http://localhost:8181}"
POLARIS_CATALOG_NAME="${POLARIS_CATALOG_NAME:-floe-e2e}"

# Source Polaris auth helper
# shellcheck source=testing/ci/polaris-auth.sh
source "$SCRIPT_DIR/polaris-auth.sh"

echo "Waiting for services in namespace: ${NAMESPACE}"

# Check kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed or not in PATH" >&2
    exit 1
fi

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster" >&2
    echo "Ensure Kind cluster is running: kind get clusters" >&2
    exit 1
fi

# Wait for all pods to be ready
echo "Waiting for pods to be ready (timeout: ${POD_TIMEOUT}s)..."
if ! kubectl wait --for=condition=ready pods --all -n "${NAMESPACE}" --timeout="${POD_TIMEOUT}s"; then
    echo "ERROR: Pods failed to become ready" >&2
    kubectl get pods -n "${NAMESPACE}"
    exit 1
fi

# Wait for setup Jobs to complete (if they exist)
# NOTE: polaris-setup (bootstrap) has hook-delete-policy: hook-succeeded,
# so kubectl wait will fail after it succeeds. We verify via API instead.
echo "Waiting for setup Jobs to complete (timeout: ${JOB_TIMEOUT}s)..."

for job in minio-setup minio-iam-setup; do
    if kubectl get job "${job}" -n "${NAMESPACE}" &> /dev/null; then
        echo "  Waiting for ${job}..."
        if ! kubectl wait --for=condition=complete "job/${job}" -n "${NAMESPACE}" --timeout="${JOB_TIMEOUT}s"; then
            echo "ERROR: Job ${job} failed to complete" >&2
            kubectl logs "job/${job}" -n "${NAMESPACE}" --tail=50 >&2
            exit 1
        fi
    fi
done

# Verify Polaris catalog exists via management API (AD-1)
# The bootstrap job has hook-delete-policy: hook-succeeded, so the job is
# deleted after success. We verify the OUTCOME (catalog exists) not the
# MECHANISM (job completed). This is race-free.
echo "Verifying Polaris catalog '${POLARIS_CATALOG_NAME}' via API..."
POLARIS_ATTEMPT=0
POLARIS_MAX_ATTEMPTS=60
while true; do
    POLARIS_ATTEMPT=$((POLARIS_ATTEMPT + 1))

    TOKEN=$(get_polaris_token "$POLARIS_URL" 2>/dev/null) || true
    if [[ -n "$TOKEN" ]]; then
        if verify_polaris_catalog "$POLARIS_URL" "$POLARIS_CATALOG_NAME" "$TOKEN" 2>/dev/null; then
            echo "Polaris catalog '${POLARIS_CATALOG_NAME}' verified successfully"
            break
        fi
    fi

    if [[ $POLARIS_ATTEMPT -ge $POLARIS_MAX_ATTEMPTS ]]; then
        echo "ERROR: Polaris catalog '${POLARIS_CATALOG_NAME}' not available after ${POLARIS_MAX_ATTEMPTS} attempts" >&2
        echo "Bootstrap job may have failed. Check: kubectl logs -n ${NAMESPACE} -l app.kubernetes.io/component=polaris-bootstrap --tail=50" >&2
        exit 1
    fi

    echo "  Attempt ${POLARIS_ATTEMPT}/${POLARIS_MAX_ATTEMPTS} - catalog not ready, waiting 5s..."
    sleep 5
done

# Verify service health
echo ""
echo "=== Service Status ==="
kubectl get pods -n "${NAMESPACE}"
echo ""
kubectl get jobs -n "${NAMESPACE}" 2>/dev/null || true

echo ""
echo "All services ready!"
