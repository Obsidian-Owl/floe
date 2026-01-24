#!/bin/bash
# Wait for K8s test services to be ready
# Used by both local testing and CI
#
# Usage: ./testing/ci/wait-for-services.sh [namespace]
#
# Environment:
#   TEST_NAMESPACE    K8s namespace (default: floe-test)
#   POD_TIMEOUT       Pod readiness timeout in seconds (default: 300)
#   JOB_TIMEOUT       Job completion timeout in seconds (default: 180)

set -euo pipefail

NAMESPACE="${1:-${TEST_NAMESPACE:-floe-test}}"
POD_TIMEOUT="${POD_TIMEOUT:-300}"
JOB_TIMEOUT="${JOB_TIMEOUT:-180}"

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
echo "Waiting for setup Jobs to complete (timeout: ${JOB_TIMEOUT}s)..."

for job in minio-setup minio-iam-setup polaris-setup; do
    if kubectl get job "${job}" -n "${NAMESPACE}" &> /dev/null; then
        echo "  Waiting for ${job}..."
        if ! kubectl wait --for=condition=complete "job/${job}" -n "${NAMESPACE}" --timeout="${JOB_TIMEOUT}s"; then
            echo "ERROR: Job ${job} failed to complete" >&2
            kubectl logs "job/${job}" -n "${NAMESPACE}" --tail=50 >&2
            exit 1
        fi
    fi
done

# Verify service health
echo ""
echo "=== Service Status ==="
kubectl get pods -n "${NAMESPACE}"
echo ""
kubectl get jobs -n "${NAMESPACE}" 2>/dev/null || true

echo ""
echo "All services ready!"
