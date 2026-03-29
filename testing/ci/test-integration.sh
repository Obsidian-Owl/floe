#!/bin/bash
# Test runner — executes tests INSIDE K8s Kind cluster
#
# This script builds a Docker image with all packages and test code,
# loads it into the Kind cluster, and runs a K8s Job that executes
# tests. Tests run in-cluster where K8s DNS resolves service hostnames
# natively, eliminating tunnel/port-forward fragility.
#
# Usage: ./testing/ci/test-integration.sh [pytest-args...]
#
# Environment:
#   TEST_SUITE          Test suite to run: integration|e2e|e2e-destructive (default: integration)
#   KUBECONFIG          Path to kubeconfig (default: ~/.kube/config)
#   TEST_NAMESPACE      K8s namespace for tests (default: floe-test)
#   WAIT_TIMEOUT        Job completion timeout in seconds (default: 600)
#   KIND_CLUSTER_NAME   Kind cluster name (default: floe)
#   SKIP_BUILD          Set to "true" to skip Docker build (use existing image)

set -euo pipefail

# Configuration
TEST_SUITE="${TEST_SUITE:-integration}"
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-600}"
KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-floe}"
SKIP_BUILD="${SKIP_BUILD:-false}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

IMAGE_NAME="floe-test-runner:latest"

# Select Job name and manifest based on TEST_SUITE
case "${TEST_SUITE}" in
    integration)
        JOB_NAME="floe-test-integration"
        JOB_MANIFEST="testing/k8s/jobs/test-runner.yaml"
        TEST_TYPE_LABEL="integration"
        ;;
    e2e)
        JOB_NAME="floe-test-e2e"
        JOB_MANIFEST="testing/k8s/jobs/test-e2e.yaml"
        TEST_TYPE_LABEL="e2e"
        ;;
    e2e-destructive)
        JOB_NAME="floe-test-e2e-destructive"
        JOB_MANIFEST="testing/k8s/jobs/test-e2e.yaml"
        TEST_TYPE_LABEL="e2e-destructive"
        ;;
    *)
        echo "ERROR: Unknown TEST_SUITE '${TEST_SUITE}'. Use: integration|e2e|e2e-destructive" >&2
        exit 1
        ;;
esac

cd "${PROJECT_ROOT}"

echo "=== Test Runner (K8s In-Cluster) ==="
echo "Suite: ${TEST_SUITE}"
echo "Job: ${JOB_NAME}"
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

# 3. Apply RBAC and PVC for E2E suites
if [[ "${TEST_SUITE}" == "e2e" ]]; then
    echo "Applying E2E RBAC and PVC..."
    kubectl apply -f testing/k8s/rbac/e2e-test-runner.yaml 2>/dev/null || true
    kubectl apply -f testing/k8s/pvc/test-artifacts.yaml 2>/dev/null || true
    echo ""
elif [[ "${TEST_SUITE}" == "e2e-destructive" ]]; then
    echo "Applying destructive E2E RBAC and PVC..."
    kubectl apply -f testing/k8s/rbac/e2e-destructive-runner.yaml 2>/dev/null || true
    kubectl apply -f testing/k8s/pvc/test-artifacts.yaml 2>/dev/null || true
    echo ""
fi

# 4. Wait for service pods to be ready
echo "Waiting for pods in ${TEST_NAMESPACE} to be ready..."
if ! kubectl wait --for=condition=ready pods --all -n "${TEST_NAMESPACE}" --timeout=120s 2>/dev/null; then
    echo "WARNING: Some pods may not be ready" >&2
    kubectl get pods -n "${TEST_NAMESPACE}" --no-headers 2>/dev/null | head -20
fi
echo ""

# 5. Delete any previous test Job (idempotent)
echo "Cleaning up previous test jobs..."
kubectl delete job "${JOB_NAME}" -n "${TEST_NAMESPACE}" --ignore-not-found 2>/dev/null
# Wait for pod cleanup
sleep 2

# 6. Apply the test Job from the manifest
echo "Creating ${TEST_SUITE} test Job..."
kubectl apply -f "${JOB_MANIFEST}" 2>/dev/null | grep "${JOB_NAME}" || true
echo ""

# 7. Wait for test pod to start
echo "Waiting for test pod to start..."
for i in $(seq 1 60); do
    pod_status=$(kubectl get pods -l "test-type=${TEST_TYPE_LABEL}" -n "${TEST_NAMESPACE}" -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "")
    if [[ "${pod_status}" == "Running" || "${pod_status}" == "Succeeded" || "${pod_status}" == "Failed" ]]; then
        break
    fi
    if [[ $i -eq 60 ]]; then
        echo "ERROR: Test pod did not start within 60s" >&2
        kubectl get pods -n "${TEST_NAMESPACE}" -l "test-type=${TEST_TYPE_LABEL}" 2>/dev/null
        exit 1
    fi
    sleep 1
done
echo "Test pod is running."
echo ""

# 8. Stream logs (follows until Job completes)
echo "=== Test Output ==="
kubectl logs -f "job/${JOB_NAME}" -n "${TEST_NAMESPACE}" --tail=-1 2>/dev/null || true
echo "=== End Test Output ==="
echo ""

# 9. Extract JUnit XML from PVC (E2E suites only)
if [[ "${TEST_SUITE}" == "e2e" || "${TEST_SUITE}" == "e2e-destructive" ]]; then
    echo "Extracting test artifacts from PVC..."
    # Create helper pod to access PVC
    kubectl run artifact-extractor \
        --image=busybox \
        --restart=Never \
        -n "${TEST_NAMESPACE}" \
        --overrides='{
            "spec": {
                "volumes": [{"name": "artifacts", "persistentVolumeClaim": {"claimName": "test-artifacts"}}],
                "containers": [{"name": "extractor", "image": "busybox", "command": ["sleep", "30"],
                    "volumeMounts": [{"name": "artifacts", "mountPath": "/artifacts"}]}]
            }
        }' 2>/dev/null || true

    # Wait for helper pod
    kubectl wait --for=condition=ready pod/artifact-extractor -n "${TEST_NAMESPACE}" --timeout=30s 2>/dev/null || true

    # Copy artifacts
    if [[ "${TEST_SUITE}" == "e2e" ]]; then
        kubectl cp "${TEST_NAMESPACE}/artifact-extractor:/artifacts/e2e-results.xml" ./e2e-results.xml 2>/dev/null || \
            echo "WARNING: Could not extract e2e-results.xml" >&2
    else
        kubectl cp "${TEST_NAMESPACE}/artifact-extractor:/artifacts/e2e-destructive-results.xml" ./e2e-destructive-results.xml 2>/dev/null || \
            echo "WARNING: Could not extract e2e-destructive-results.xml" >&2
    fi

    # Clean up helper pod
    kubectl delete pod artifact-extractor -n "${TEST_NAMESPACE}" --ignore-not-found 2>/dev/null || true
    echo ""
fi

# 10. Check Job status
echo "Checking Job status..."
JOB_SUCCEEDED=$(kubectl get job "${JOB_NAME}" -n "${TEST_NAMESPACE}" -o jsonpath='{.status.succeeded}' 2>/dev/null || echo "")
JOB_FAILED=$(kubectl get job "${JOB_NAME}" -n "${TEST_NAMESPACE}" -o jsonpath='{.status.failed}' 2>/dev/null || echo "")

if [[ "${JOB_SUCCEEDED}" == "1" ]]; then
    echo "${TEST_SUITE} tests PASSED"
    exit 0
elif [[ "${JOB_FAILED}" == "1" ]]; then
    echo "${TEST_SUITE} tests FAILED" >&2
    exit 1
else
    # Wait for job completion with timeout
    if kubectl wait --for=condition=complete "job/${JOB_NAME}" -n "${TEST_NAMESPACE}" --timeout="${WAIT_TIMEOUT}s" 2>/dev/null; then
        echo "${TEST_SUITE} tests PASSED"
        exit 0
    else
        echo "${TEST_SUITE} tests FAILED or timed out" >&2
        kubectl get job "${JOB_NAME}" -n "${TEST_NAMESPACE}" -o yaml 2>/dev/null | grep -A5 "status:" || true
        exit 1
    fi
fi
