#!/bin/bash
# In-cluster E2E test runner — runs tests as a K8s Job inside the Kind cluster
#
# This eliminates host-to-cluster connectivity issues (port-forwards, SSH tunnels)
# by running tests where the services are.
#
# Usage: ./testing/ci/test-e2e-cluster.sh [-- pytest-args...]
#
# Environment:
#   KUBECONFIG          Path to kubeconfig (default: ~/.kube/config)
#   TEST_NAMESPACE      K8s namespace for tests (default: floe-test)
#   JOB_TIMEOUT         Job completion timeout in seconds (default: 3600)
#   KIND_CLUSTER        Kind cluster name (default: floe)
#   SKIP_BUILD          Skip image build if set to "true" (default: false)

set -euo pipefail

# Configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
JOB_TIMEOUT="${JOB_TIMEOUT:-3600}"
KIND_CLUSTER="${KIND_CLUSTER:-floe}"
SKIP_BUILD="${SKIP_BUILD:-false}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
JOB_NAME="floe-test-e2e"
JOB_MANIFEST="testing/k8s/jobs/test-e2e.yaml"
IMAGE_NAME="floe-test-runner:latest"
ARTIFACTS_DIR="${PROJECT_ROOT}/test-artifacts"

cd "${PROJECT_ROOT}"

# --- Utility functions ---

info() { echo "[INFO] $*"; }
error() { echo "[ERROR] $*" >&2; }
cleanup_job() {
    info "Cleaning up Job ${JOB_NAME}..."
    kubectl delete job "${JOB_NAME}" -n "${TEST_NAMESPACE}" --ignore-not-found 2>/dev/null || true
}

# --- Pre-flight checks ---

if ! command -v kind &>/dev/null; then
    error "kind CLI not found. Install: https://kind.sigs.k8s.io/docs/user/quick-start/"
    exit 1
fi

if ! command -v kubectl &>/dev/null; then
    error "kubectl not found."
    exit 1
fi

if ! kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER}$"; then
    error "Kind cluster '${KIND_CLUSTER}' not found. Create it first."
    exit 1
fi

if ! kubectl get namespace "${TEST_NAMESPACE}" &>/dev/null; then
    error "Namespace '${TEST_NAMESPACE}' not found. Deploy the platform first."
    exit 1
fi

# --- Step 1: Build test runner image ---

if [[ "${SKIP_BUILD}" != "true" ]]; then
    info "Building test runner image..."
    docker build -t "${IMAGE_NAME}" -f testing/Dockerfile . 2>&1 | tail -5
    info "Loading image into Kind cluster '${KIND_CLUSTER}'..."
    kind load docker-image "${IMAGE_NAME}" --name "${KIND_CLUSTER}"
else
    info "Skipping image build (SKIP_BUILD=true)"
fi

# --- Step 2: Delete previous Job (idempotent) ---

cleanup_job

# --- Step 3: Ensure PVC exists ---

if ! kubectl get pvc test-artifacts -n "${TEST_NAMESPACE}" &>/dev/null; then
    info "Creating test-artifacts PVC..."
    kubectl apply -n "${TEST_NAMESPACE}" -f - <<'EOFPVC'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-artifacts
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
EOFPVC
fi

# --- Step 4: Submit Job ---

info "Submitting E2E test Job..."
kubectl apply -f "${JOB_MANIFEST}" -n "${TEST_NAMESPACE}"
info "Job '${JOB_NAME}' submitted. Waiting up to ${JOB_TIMEOUT}s for completion..."

# --- Step 5: Wait for completion ---

# kubectl wait returns non-zero on timeout
if kubectl wait --for=condition=complete "job/${JOB_NAME}" \
    -n "${TEST_NAMESPACE}" \
    --timeout="${JOB_TIMEOUT}s" 2>/dev/null; then
    JOB_STATUS="complete"
elif kubectl wait --for=condition=failed "job/${JOB_NAME}" \
    -n "${TEST_NAMESPACE}" \
    --timeout=10s 2>/dev/null; then
    JOB_STATUS="failed"
else
    JOB_STATUS="timeout"
fi

# --- Step 6: Extract results ---

info "Extracting test results..."
mkdir -p "${ARTIFACTS_DIR}"

# Get pod name for the Job
POD_NAME=$(kubectl get pods -n "${TEST_NAMESPACE}" \
    -l "job-name=${JOB_NAME}" \
    --sort-by=.metadata.creationTimestamp \
    -o jsonpath='{.items[-1].metadata.name}' 2>/dev/null || true)

if [[ -n "${POD_NAME}" ]]; then
    # Extract logs
    kubectl logs "${POD_NAME}" -n "${TEST_NAMESPACE}" \
        > "${ARTIFACTS_DIR}/e2e-output.log" 2>/dev/null || true

    # Extract JUnit XML if available
    kubectl cp "${TEST_NAMESPACE}/${POD_NAME}:/artifacts/e2e-results.xml" \
        "${ARTIFACTS_DIR}/e2e-results.xml" 2>/dev/null || true

    # Show last 30 lines of output
    info "--- Test output (last 30 lines) ---"
    tail -30 "${ARTIFACTS_DIR}/e2e-output.log" 2>/dev/null || true
    info "--- End test output ---"
else
    error "No pod found for Job '${JOB_NAME}'"
fi

# --- Step 7: Report and exit ---

case "${JOB_STATUS}" in
    complete)
        info "E2E tests PASSED"
        cleanup_job
        exit 0
        ;;
    failed)
        error "E2E tests FAILED"
        error "Full output: ${ARTIFACTS_DIR}/e2e-output.log"
        cleanup_job
        exit 1
        ;;
    timeout)
        error "E2E tests TIMED OUT after ${JOB_TIMEOUT}s"
        error "Job may still be running. Cleaning up..."
        cleanup_job
        exit 2
        ;;
esac
