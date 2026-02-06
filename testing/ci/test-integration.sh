#!/bin/bash
# Integration test runner — executes tests INSIDE K8s Kind cluster
#
# This script builds a Docker image with all packages and test code,
# loads it into the Kind cluster, and runs a K8s Job that executes
# integration tests. Tests run in-cluster where K8s DNS resolves
# service hostnames natively, eliminating S3 endpoint monkey-patching.
#
# Usage: ./testing/ci/test-integration.sh [pytest-args...]
#
# Environment:
#   KUBECONFIG          Path to kubeconfig (default: ~/.kube/config)
#   TEST_NAMESPACE      K8s namespace for tests (default: floe-test)
#   WAIT_TIMEOUT        Job completion timeout in seconds (default: 600)
#   KIND_CLUSTER_NAME   Kind cluster name (default: floe)
#   SKIP_BUILD          Set to "true" to skip Docker build (use existing image)

set -euo pipefail

# Configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-600}"
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-floe}"
SKIP_BUILD="${SKIP_BUILD:-false}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

IMAGE_NAME="floe-test-runner:latest"
JOB_NAME="floe-test-integration"

cd "${PROJECT_ROOT}"

echo "=== Integration Test Runner (K8s) ==="
echo "Namespace: ${TEST_NAMESPACE}"
echo "Kind cluster: ${KIND_CLUSTER_NAME}"
echo "Timeout: ${WAIT_TIMEOUT}s"
echo ""

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed or not in PATH" >&2
    exit 1
fi

if ! command -v kind &> /dev/null; then
    echo "ERROR: kind is not installed or not in PATH" >&2
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster" >&2
    echo "Ensure Kind cluster is running: make kind-up" >&2
    exit 1
fi

# Check namespace exists
if ! kubectl get namespace "${TEST_NAMESPACE}" &> /dev/null; then
    echo "WARNING: Namespace ${TEST_NAMESPACE} does not exist" >&2
    echo "Creating namespace..." >&2
    kubectl create namespace "${TEST_NAMESPACE}"
fi

# 1. Build Docker image
if [[ "${SKIP_BUILD}" != "true" ]]; then
    echo "Building test runner image..."
    docker build -t "${IMAGE_NAME}" -f testing/Dockerfile .
    echo "Image built successfully."
    echo ""

    # 2. Load into Kind cluster
    echo "Loading image into Kind cluster '${KIND_CLUSTER_NAME}'..."
    kind load docker-image "${IMAGE_NAME}" --name "${KIND_CLUSTER_NAME}"
    echo "Image loaded."
    echo ""
else
    echo "Skipping Docker build (SKIP_BUILD=true)"
    echo ""
fi

# 3. Wait for service pods to be ready
echo "Waiting for pods in ${TEST_NAMESPACE} to be ready..."
if ! kubectl wait --for=condition=ready pods --all -n "${TEST_NAMESPACE}" --timeout=120s 2>/dev/null; then
    echo "WARNING: Some pods may not be ready" >&2
    kubectl get pods -n "${TEST_NAMESPACE}" --no-headers 2>/dev/null | head -20
fi
echo ""

# 4. Delete any previous test Job (idempotent)
echo "Cleaning up previous test jobs..."
kubectl delete job "${JOB_NAME}" -n "${TEST_NAMESPACE}" --ignore-not-found 2>/dev/null
# Wait for pod cleanup
sleep 2

# 5. Apply the integration test Job from the manifest
echo "Creating integration test Job..."
kubectl apply -f testing/k8s/jobs/test-runner.yaml 2>/dev/null | grep "floe-test-integration" || true
echo ""

# 6. Wait for test pod to start
echo "Waiting for test pod to start..."
for i in $(seq 1 60); do
    pod_status=$(kubectl get pods -l test-type=integration -n "${TEST_NAMESPACE}" -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
    if [[ "${pod_status}" == "Running" || "${pod_status}" == "Succeeded" || "${pod_status}" == "Failed" ]]; then
        break
    fi
    if [[ $i -eq 60 ]]; then
        echo "ERROR: Test pod did not start within 60s" >&2
        kubectl get pods -n "${TEST_NAMESPACE}" -l test-type=integration 2>/dev/null
        exit 1
    fi
    sleep 1
done
echo "Test pod is running."
echo ""

# 7. Stream logs (follows until Job completes)
echo "=== Test Output ==="
kubectl logs -f "job/${JOB_NAME}" -n "${TEST_NAMESPACE}" --tail=-1 2>/dev/null || true
echo "=== End Test Output ==="
echo ""

# 8. Check Job status
echo "Checking Job status..."
JOB_SUCCEEDED=$(kubectl get job "${JOB_NAME}" -n "${TEST_NAMESPACE}" -o jsonpath='{.status.succeeded}' 2>/dev/null || echo "")
JOB_FAILED=$(kubectl get job "${JOB_NAME}" -n "${TEST_NAMESPACE}" -o jsonpath='{.status.failed}' 2>/dev/null || echo "")

if [[ "${JOB_SUCCEEDED}" == "1" ]]; then
    echo "Integration tests PASSED"
    exit 0
elif [[ "${JOB_FAILED}" == "1" ]]; then
    echo "Integration tests FAILED" >&2
    exit 1
else
    # Wait for job completion with timeout
    if kubectl wait --for=condition=complete "job/${JOB_NAME}" -n "${TEST_NAMESPACE}" --timeout="${WAIT_TIMEOUT}s" 2>/dev/null; then
        echo "Integration tests PASSED"
        exit 0
    else
        echo "Integration tests FAILED or timed out" >&2
        kubectl get job "${JOB_NAME}" -n "${TEST_NAMESPACE}" -o yaml 2>/dev/null | grep -A5 "status:" || true
        exit 1
    fi
fi
