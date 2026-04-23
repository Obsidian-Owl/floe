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
#   JOB_STARTUP_TIMEOUT Startup-only timeout in seconds (default: 180)
#   SKIP_BUILD          Skip image build if set to "true" (default: false)
#   IMAGE_LOAD_METHOD   How to load image: auto|kind|devpod|skip (default: auto)
#   STARTUP_ONLY        Exit after proving pod startup boundary (default: false)
#   TEST_SUITE          Test suite to run: bootstrap|e2e|e2e-destructive
#                       (default: bootstrap first, then e2e)
#   LOG_TAIL_LINES      Lines to capture per pod on failure (default: 100)
#   DEVPOD_REMOTE_WORKDIR Remote repo root inside the DevPod workspace
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
JOB_STARTUP_TIMEOUT="${JOB_STARTUP_TIMEOUT:-180}"
SKIP_BUILD="${SKIP_BUILD:-false}"
IMAGE_LOAD_METHOD="${IMAGE_LOAD_METHOD:-auto}"
STARTUP_ONLY="${STARTUP_ONLY:-false}"
if [[ -z "${TEST_SUITE+x}" ]]; then
    FLOE_DIRECT_BOOTSTRAP_GATE="true"
    TEST_SUITE="bootstrap"
else
    FLOE_DIRECT_BOOTSTRAP_GATE="false"
fi
IMAGE_NAME="floe-test-runner:latest"
ARTIFACTS_DIR="${PROJECT_ROOT}/test-artifacts"
LOG_TAIL_LINES="${LOG_TAIL_LINES:-100}"

# --- Utility functions (must be defined before first use) ---

info() { echo "[INFO] $*"; }
error() { echo "[ERROR] $*" >&2; }

devpod_workspace() {
    printf '%s\n' "${DEVPOD_WORKSPACE:-floe}"
}

devpod_kubeconfig_path() {
    local workspace
    workspace=$(devpod_workspace)
    printf '%s\n' "${HOME}/.kube/devpod-${workspace}.config"
}

devpod_remote_workdir() {
    printf '%s\n' "${DEVPOD_REMOTE_WORKDIR}"
}

ensure_devpod_ready() {
    local workspace
    workspace=$(devpod_workspace)

    if ! command -v devpod >/dev/null 2>&1; then
        error "devpod CLI not found. Install it or use IMAGE_LOAD_METHOD=kind."
        exit 1
    fi

    DEVPOD_WORKSPACE="${workspace}" \
        bash "${PROJECT_ROOT}/scripts/devpod-ensure-ready.sh"
    export KUBECONFIG
    KUBECONFIG="$(devpod_kubeconfig_path)"
}

devpod_remote_command() {
    local command="$1"
    local workspace
    local remote_workdir
    workspace=$(devpod_workspace)
    remote_workdir=$(devpod_remote_workdir)
    devpod ssh "${workspace}" \
        --start-services=false \
        --workdir "${remote_workdir}" \
        --command "${command}"
}

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

job_pod_name() {
    kubectl get pods -n "${TEST_NAMESPACE}" \
        -l "job-name=${JOB_NAME}" \
        --sort-by=.metadata.creationTimestamp \
        -o jsonpath='{.items[-1].metadata.name}' 2>/dev/null || true
}

job_waiting_reason() {
    local pod_name="$1"
    kubectl get pod "${pod_name}" -n "${TEST_NAMESPACE}" \
        -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true
}

job_started_at() {
    local pod_name="$1"
    kubectl get pod "${pod_name}" -n "${TEST_NAMESPACE}" \
        -o jsonpath='{.status.containerStatuses[0].state.running.startedAt}{.status.containerStatuses[0].state.terminated.startedAt}' 2>/dev/null || true
}

assert_startup_boundary() {
    local pod_name=""
    local waiting_reason=""
    local started_at=""

    info "STARTUP_ONLY=true — waiting up to ${JOB_STARTUP_TIMEOUT}s for the pod startup boundary..."

    for _ in $(seq 1 "${JOB_STARTUP_TIMEOUT}"); do
        pod_name=$(job_pod_name)
        if [[ -n "${pod_name}" ]]; then
            waiting_reason=$(job_waiting_reason "${pod_name}")
            started_at=$(job_started_at "${pod_name}")

            case "${waiting_reason}" in
                ImagePullBackOff|ErrImagePull|CreateContainerConfigError)
                    extract_pod_logs
                    error "Test pod hit startup failure reason '${waiting_reason}'."
                    error "Pod: ${pod_name}"
                    return 1
                    ;;
            esac

            if [[ -n "${started_at}" ]]; then
                info "Startup boundary passed for pod '${pod_name}'."
                return 0
            fi
        fi

        sleep 1
    done

    extract_pod_logs
    error "Test pod did not reach a started state within ${JOB_STARTUP_TIMEOUT}s."
    return 1
}

# Select Job name and chart-rendered template based on TEST_SUITE
case "${TEST_SUITE}" in
    bootstrap)
        JOB_NAME="floe-test-bootstrap"
        JOB_TEMPLATE="tests/job-bootstrap.yaml"
        RBAC_TEMPLATE="tests/rbac-standard.yaml"
        ;;
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
        error "Unknown TEST_SUITE '${TEST_SUITE}'. Use: bootstrap|e2e|e2e-destructive"
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
            local workspace
            workspace=$(devpod_workspace)
            info "Loading image into DevPod workspace '${workspace}' and Kind cluster '${kind_cluster}'..."
            docker save "${image}" | devpod_remote_command "docker load"
            devpod_remote_command "kind load docker-image '${image}' --name '${kind_cluster}'"
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
                local workspace
                workspace=$(devpod_workspace)
                info "Loading image into DevPod workspace '${workspace}' and Kind cluster '${kind_cluster}'..."
                docker save "${image}" | devpod_remote_command "docker load"
                devpod_remote_command "kind load docker-image '${image}' --name '${kind_cluster}'"
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

if [[ "${IMAGE_LOAD_METHOD}" == "devpod" ]]; then
    ensure_devpod_ready
elif [[ "${IMAGE_LOAD_METHOD}" == "auto" && -n "${DEVPOD_WORKSPACE:-}" ]]; then
    if ! kubectl cluster-info >/dev/null 2>&1; then
        ensure_devpod_ready
    fi
fi

floe_require_cluster

# --- Step 1: Build test runner image ---

if [[ "${IMAGE_LOAD_METHOD}" == "skip" ]]; then
    info "Skipping image build and load (IMAGE_LOAD_METHOD=skip)"
elif [[ "${SKIP_BUILD}" != "true" ]]; then
    info "Building test runner image..."
    scripts/with-public-docker-config.sh docker build -t "${IMAGE_NAME}" -f testing/Dockerfile . 2>&1 | tail -5
    load_image "${IMAGE_NAME}"
else
    info "Skipping image build (SKIP_BUILD=true)"
    load_image "${IMAGE_NAME}"
fi

# --- Step 2: Delete previous Job (idempotent) ---

cleanup_job

# --- Step 3: Render and apply RBAC + Job from the chart ---
# All identifiers flow from _helpers.tpl via floe_render_test_job — no
# manifest paths, no raw YAML heredocs, no hardcoded resource names.

info "Applying ${TEST_SUITE} RBAC from chart..."
floe_render_test_job "${RBAC_TEMPLATE}" | kubectl apply -f -

# Ensure the chart-gated artifacts PVC exists before the Job mounts it.

info "Ensuring chart-owned test artifacts PVC exists..."
floe_ensure_test_artifacts_pvc

# --- Step 4: Submit Job ---

info "Submitting ${TEST_SUITE} test Job from chart..."
floe_render_test_job "${JOB_TEMPLATE}" | kubectl apply -f -
info "Job '${JOB_NAME}' submitted. Waiting up to ${JOB_TIMEOUT}s for completion..."

if [[ "${STARTUP_ONLY}" == "true" ]]; then
    if assert_startup_boundary; then
        info "E2E startup boundary PASSED"
        exit 0
    fi
    exit 1
fi

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
POD_NAME=$(job_pod_name)

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
        info "${TEST_SUITE} tests PASSED"
        if [[ "${FLOE_DIRECT_BOOTSTRAP_GATE}" == "true" ]]; then
            info "Bootstrap passed; running product E2E suite without rebuilding/loading image."
            cleanup_job
            SKIP_BUILD=true IMAGE_LOAD_METHOD=skip TEST_SUITE=e2e "${SCRIPT_DIR}/test-e2e-cluster.sh"
            exit $?
        fi
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
