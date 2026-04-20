#!/usr/bin/env bash
# Focused integration proof for Unit C's DevPod + Flux startup boundary.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=./common.sh
source "${SCRIPT_DIR}/common.sh"

COMMAND="${1:-}"
PLATFORM_READY_TIMEOUT="${PLATFORM_READY_TIMEOUT:-120}"
REMOTE_STARTUP_TIMEOUT="${REMOTE_STARTUP_TIMEOUT:-180}"
REMOTE_JOB_TIMEOUT="${REMOTE_JOB_TIMEOUT:-600}"

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

devpod_remote_command() {
    local command="$1"
    local workspace
    workspace=$(devpod_workspace)
    devpod ssh "${workspace}" \
        --start-services=false \
        --workdir "${DEVPOD_REMOTE_WORKDIR}" \
        --command "${command}"
}

remote_image_present() {
    local image_name="${1:-floe-test-runner:latest}"
    if devpod_remote_command "docker image inspect ${image_name} >/dev/null 2>&1"; then
        return 0
    fi
    return 1
}

ensure_devpod_ready() {
    local workspace
    workspace=$(devpod_workspace)
    DEVPOD_WORKSPACE="${workspace}" bash "${PROJECT_ROOT}/scripts/devpod-ensure-ready.sh"
    export KUBECONFIG
    KUBECONFIG="$(devpod_kubeconfig_path)"
}

check_platform_ready() {
    ensure_devpod_ready
    floe_require_cluster

    info "Checking Flux-managed floe-platform readiness..."
    kubectl wait helmrelease/floe-platform -n "${FLOE_NAMESPACE}" \
        --for=condition=Ready --timeout="${PLATFORM_READY_TIMEOUT}s" >/dev/null

    info "Checking required platform secrets..."
    kubectl get secret -n "${FLOE_NAMESPACE}" \
        floe-platform-postgresql \
        floe-platform-minio \
        floe-platform-polaris-credentials >/dev/null
}

run_remote_kind_startup() {
    check_platform_ready
    if ! remote_image_present "floe-test-runner:latest"; then
        error "Remote image floe-test-runner:latest is not present in the DevPod workspace."
        error "Rebuild it on the remote workspace before rerunning this proof."
        return 1
    fi

    info "Loading the cached remote test-runner image into Kind..."
    devpod_remote_command \
        "kind load docker-image 'floe-test-runner:latest' --name '${FLOE_KIND_CLUSTER}'"

    info "Running startup-only probe from the current checkout against the remote cluster..."
    STARTUP_ONLY=true \
        JOB_STARTUP_TIMEOUT="${REMOTE_STARTUP_TIMEOUT}" \
        JOB_TIMEOUT="${REMOTE_JOB_TIMEOUT}" \
        SKIP_BUILD=true \
        IMAGE_LOAD_METHOD=skip \
        "${SCRIPT_DIR}/test-e2e-cluster.sh"
}

case "${COMMAND}" in
    platform-ready)
        check_platform_ready
        ;;
    remote-kind-startup)
        run_remote_kind_startup
        ;;
    *)
        error "Unknown command '${COMMAND}'. Use: platform-ready | remote-kind-startup"
        exit 2
        ;;
esac
