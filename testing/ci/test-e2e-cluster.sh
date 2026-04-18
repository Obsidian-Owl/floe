#!/bin/bash
# In-cluster E2E test runner — runs tests as a K8s Job inside the Kind cluster
#
# This eliminates host-to-cluster connectivity issues (port-forwards, SSH tunnels)
# by running tests where the services are.
#
# Usage: ./testing/ci/test-e2e-cluster.sh
#
# Environment:
#   KUBECONFIG          Path to kubeconfig (default: ~/.kube/config)
#   JOB_TIMEOUT         Job completion timeout in seconds (default: 3600)
#   SKIP_BUILD          Skip image build if set to "true" (default: false)
#   IMAGE_LOAD_METHOD   How to load image: auto|kind|devpod|skip (default: auto)
#   TEST_SUITE          Test suite to run: e2e|e2e-destructive (default: e2e)
#   LOG_TAIL_LINES      Lines to capture per pod on failure (default: 100)
#
# Identifiers (release name, namespace, Kind cluster, chart dir, values file)
# come from testing/ci/common.sh — override via FLOE_* env vars there.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=./common.sh
source "${SCRIPT_DIR}/common.sh"

# Configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${FLOE_NAMESPACE}"
JOB_TIMEOUT="${JOB_TIMEOUT:-3600}"
SKIP_BUILD="${SKIP_BUILD:-false}"
IMAGE_LOAD_METHOD="${IMAGE_LOAD_METHOD:-auto}"
TEST_SUITE="${TEST_SUITE:-e2e}"
IMAGE_NAME="floe-test-runner:latest"
ARTIFACTS_DIR="${PROJECT_ROOT}/test-artifacts"
LOG_TAIL_LINES="${LOG_TAIL_LINES:-100}"

# --- Utility functions (must be defined before first use) ---

info() { echo "[INFO] $*"; }
error() { echo "[ERROR] $*" >&2; }

# extract_pod_logs — collect pod logs and K8s events on failure for debugging
extract_pod_logs() {
    mkdir -p "${ARTIFACTS_DIR}/pod-logs"

    info "Collecting pod logs from namespace ${TEST_NAMESPACE}..."

    # Resolve timeout binary: prefer GNU timeout, fall back to gtimeout (macOS
    # coreutils), or run unguarded if neither is present. macOS ships without
    # GNU timeout by default; without this fallback the `if` branch would be
    # False for every pod and logs would silently be skipped.
    local timeout_bin=""
    if command -v timeout >/dev/null 2>&1; then
        timeout_bin="timeout 10"
    elif command -v gtimeout >/dev/null 2>&1; then
        timeout_bin="gtimeout 10"
    else
        error "Warning: neither 'timeout' nor 'gtimeout' found; pod log extraction will run without per-pod timeout"
    fi

    # Collect logs from all pods in the test namespace
    local pod_names
    pod_names=$(kubectl get pods -n "${TEST_NAMESPACE}" \
        --no-headers -o custom-columns=":metadata.name" 2>/dev/null || true)

    local collected=0
    for pod in ${pod_names}; do
        if ${timeout_bin} kubectl logs "${pod}" -n "${TEST_NAMESPACE}" \
            --tail="${LOG_TAIL_LINES}" \
            > "${ARTIFACTS_DIR}/pod-logs/${pod}.log" 2>/dev/null; then
            collected=$((collected + 1))
        else
            error "Warning: failed to extract logs for pod ${pod} (may have terminated)"
            continue
        fi
    done

    # Capture K8s events sorted by timestamp
    kubectl get events --sort-by='.lastTimestamp' -n "${TEST_NAMESPACE}" \
        > "${ARTIFACTS_DIR}/pod-logs/events.txt" 2>/dev/null || true

    info "Pod log extraction complete: ${collected} pod(s) collected"
    info "Pod logs saved to: ${ARTIFACTS_DIR}/pod-logs/"
}

# Select Job name and chart-rendered template based on TEST_SUITE
case "${TEST_SUITE}" in
    e2e)
        JOB_NAME="floe-test-e2e"
        JOB_TEMPLATE="tests/job-e2e.yaml"
        RBAC_TEMPLATE="tests/rbac-standard.yaml"
        ;;
    e2e-destructive)
        JOB_NAME="floe-test-e2e-destructive"
        JOB_TEMPLATE="tests/job-e2e-destructive.yaml"
        RBAC_TEMPLATE="tests/rbac-destructive.yaml"
        ;;
    *)
        error "Unknown TEST_SUITE '${TEST_SUITE}'. Use: e2e|e2e-destructive"
        exit 1
        ;;
esac

cd "${PROJECT_ROOT}"
cleanup_job() {
    info "Cleaning up Job ${JOB_NAME}..."
    kubectl delete job "${JOB_NAME}" -n "${TEST_NAMESPACE}" --ignore-not-found 2>/dev/null || true
}

# load_image <image-name>
# Loads a Docker image into the target environment according to IMAGE_LOAD_METHOD.
load_image() {
    local image="$1"
    local method="${IMAGE_LOAD_METHOD}"
    local kind_cluster="${FLOE_KIND_CLUSTER}"

    case "${method}" in
        skip)
            info "Skipping image load (IMAGE_LOAD_METHOD=skip)"
            return 0
            ;;
        kind)
            info "Loading image into Kind cluster '${kind_cluster}' (IMAGE_LOAD_METHOD=kind)..."
            kind load docker-image "${image}" --name "${kind_cluster}"
            return 0
            ;;
        devpod)
            local ssh_host="${DEVPOD_WORKSPACE:-floe}.devpod"
            info "Loading image into DevPod workspace '${ssh_host}' and Kind cluster '${kind_cluster}'..."
            docker save "${image}" | ssh "${ssh_host}" docker load
            ssh "${ssh_host}" kind load docker-image "${image}" --name "${kind_cluster}"
            return 0
            ;;
        *)
            # auto: detect environment
            if command -v kind &>/dev/null && kind get clusters 2>/dev/null | grep -q "^${kind_cluster}$"; then
                info "Loading image into Kind cluster '${kind_cluster}'..."
                kind load docker-image "${image}" --name "${kind_cluster}"
                return 0
            fi

            if [[ -n "${DEVPOD_WORKSPACE:-}" ]]; then
                local ssh_host="${DEVPOD_WORKSPACE}.devpod"
                info "Loading image into DevPod workspace '${ssh_host}' and Kind cluster '${kind_cluster}'..."
                docker save "${image}" | ssh "${ssh_host}" docker load
                ssh "${ssh_host}" kind load docker-image "${image}" --name "${kind_cluster}"
                return 0
            fi

            error "No Kind cluster '${kind_cluster}' or DevPod workspace detected. Run 'make kind-up' or start DevPod."
            exit 1
            ;;
    esac
}

# Ensure Job is cleaned up on interrupt or exit (idempotent via --ignore-not-found)
trap cleanup_job EXIT

# --- Pre-flight checks ---

if ! command -v helm &>/dev/null; then
    error "helm not found."
    exit 1
fi

floe_require_cluster

# --- Step 1: Build test runner image ---

if [[ "${IMAGE_LOAD_METHOD}" == "skip" ]]; then
    info "Skipping image build and load (IMAGE_LOAD_METHOD=skip)"
elif [[ "${SKIP_BUILD}" != "true" ]]; then
    info "Building test runner image..."
    docker build -t "${IMAGE_NAME}" -f testing/Dockerfile . 2>&1 | tail -5
    load_image "${IMAGE_NAME}"
else
    info "Skipping image build (SKIP_BUILD=true)"
    load_image "${IMAGE_NAME}"
fi

# --- Step 2: Delete previous Job (idempotent) ---

cleanup_job

# --- Step 3: Render and apply RBAC + PVC + Job from the chart ---
# All identifiers flow from _helpers.tpl via floe_render_test_job — no
# manifest paths, no raw YAML heredocs, no hardcoded resource names.

info "Applying ${TEST_SUITE} RBAC from chart..."
floe_render_test_job "${RBAC_TEMPLATE}" | kubectl apply -f -

info "Applying test-artifacts PVC from chart..."
floe_render_test_job "tests/pvc-artifacts.yaml" | kubectl apply -f -

# --- Step 4: Submit Job ---

info "Submitting ${TEST_SUITE} test Job from chart..."
floe_render_test_job "${JOB_TEMPLATE}" | kubectl apply -f -
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
    # Extract logs (use TEST_SUITE in filename to avoid overwriting between suites)
    kubectl logs "${POD_NAME}" -n "${TEST_NAMESPACE}" \
        > "${ARTIFACTS_DIR}/${TEST_SUITE}-output.log" 2>/dev/null || true

    # Extract JUnit XML if available (source uses TEST_SUITE prefix to match Job manifest)
    kubectl cp "${TEST_NAMESPACE}/${POD_NAME}:/artifacts/${TEST_SUITE}-results.xml" \
        "${ARTIFACTS_DIR}/${TEST_SUITE}-results.xml" 2>/dev/null || true

    # Extract HTML report if available
    kubectl cp "${TEST_NAMESPACE}/${POD_NAME}:/artifacts/${TEST_SUITE}-report.html" \
        "${ARTIFACTS_DIR}/${TEST_SUITE}-report.html" 2>/dev/null || true

    # Extract JSON report if available
    kubectl cp "${TEST_NAMESPACE}/${POD_NAME}:/artifacts/${TEST_SUITE}-report.json" \
        "${ARTIFACTS_DIR}/${TEST_SUITE}-report.json" 2>/dev/null || true

    # Show last 30 lines of output
    info "--- Test output (last 30 lines) ---"
    tail -30 "${ARTIFACTS_DIR}/${TEST_SUITE}-output.log" 2>/dev/null || true
    info "--- End test output ---"
else
    error "No pod found for Job '${JOB_NAME}'"
fi

# --- Step 7: Report and exit ---

case "${JOB_STATUS}" in
    complete)
        info "E2E tests PASSED"
        exit 0
        ;;
    failed)
        extract_pod_logs
        error "E2E tests FAILED"
        error "Full output: ${ARTIFACTS_DIR}/${TEST_SUITE}-output.log"
        exit 1
        ;;
    timeout)
        extract_pod_logs
        error "E2E tests TIMED OUT after ${JOB_TIMEOUT}s"
        error "Job may still be running."
        exit 2
        ;;
esac
