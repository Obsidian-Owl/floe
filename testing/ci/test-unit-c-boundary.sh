#!/usr/bin/env bash
# Focused integration proof for Unit C's DevPod + Flux startup boundary.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=./common.sh
source "${SCRIPT_DIR}/common.sh"

COMMAND="${1:-}"
PLATFORM_READY_TIMEOUT="${PLATFORM_READY_TIMEOUT:-900}"
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
    if devpod_remote_command "docker image inspect '${image_name}' >/dev/null 2>&1"; then
        return 0
    fi
    return 1
}

sync_devpod_checkout() {
    local workspace
    workspace=$(devpod_workspace)

    info "Syncing the current checkout into DevPod workspace '${workspace}'..."
    COPYFILE_DISABLE=1 tar \
        --exclude='.git' \
        --exclude='.venv' \
        --exclude='.mypy_cache' \
        --exclude='.pytest_cache' \
        --exclude='.ruff_cache' \
        --exclude='test-artifacts' \
        --exclude='.specify' \
        -cf - -C "${PROJECT_ROOT}" . \
        | devpod ssh "${workspace}" \
            --start-services=false \
            --workdir "${DEVPOD_REMOTE_WORKDIR}" \
            --command "tar -xf -"
}

ensure_remote_demo_image_loaded() {
    local demo_image="${FLOE_DEMO_IMAGE}"

    if remote_image_present "${demo_image}"; then
        info "Remote demo image '${demo_image}' is present. Reloading it into Kind..."
        devpod_remote_command \
            "source '${DEVPOD_REMOTE_WORKDIR}/testing/ci/common.sh' && floe_kind_evict_image '${demo_image}' '${FLOE_KIND_CLUSTER}'"
        devpod_remote_command \
            "kind load docker-image '${demo_image}' --name '${FLOE_KIND_CLUSTER}'"
        return 0
    fi

    sync_devpod_checkout
    info "Remote demo image '${demo_image}' is missing. Rebuilding it in the DevPod workspace..."
    devpod_remote_command \
        "FLOE_DEMO_IMAGE_REPOSITORY='${FLOE_DEMO_IMAGE_REPOSITORY}' FLOE_DEMO_IMAGE_TAG='${FLOE_DEMO_IMAGE_TAG}' KIND_CLUSTER_NAME='${FLOE_KIND_CLUSTER}' make build-demo-image"
}

ensure_remote_test_runner_image_loaded() {
    local test_runner_image="floe-test-runner:latest"

    if remote_image_present "${test_runner_image}"; then
        info "Remote test-runner image '${test_runner_image}' is present."
        return 0
    fi

    sync_devpod_checkout
    info "Remote test-runner image '${test_runner_image}' is missing. Rebuilding it in the DevPod workspace..."
    devpod_remote_command "make test-integration-image"
}

ensure_devpod_ready() {
    local workspace
    workspace=$(devpod_workspace)
    DEVPOD_WORKSPACE="${workspace}" bash "${PROJECT_ROOT}/scripts/devpod-ensure-ready.sh"
    export KUBECONFIG
    KUBECONFIG="$(devpod_kubeconfig_path)"
}

rebootstrap_remote_platform() {
    info "Namespace '${FLOE_NAMESPACE}' is missing. Re-running the remote DevPod post-start bootstrap..."
    devpod_remote_command "bash .devcontainer/hetzner/postStartCommand.sh"
    ensure_devpod_ready
}

check_platform_ready() {
    ensure_devpod_ready
    if ! kubectl get namespace "${FLOE_NAMESPACE}" >/dev/null 2>&1; then
        rebootstrap_remote_platform
    fi
    floe_require_cluster

    if ! kubectl get helmrelease/floe-platform -n "${FLOE_NAMESPACE}" \
        -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null \
        | grep -qx "True"; then
        ensure_remote_demo_image_loaded
    fi

    info "Checking Flux-managed floe-platform readiness..."
    kubectl wait helmrelease/floe-platform -n "${FLOE_NAMESPACE}" \
        --for=condition=Ready --timeout="${PLATFORM_READY_TIMEOUT}s" >/dev/null

    info "Checking required platform secrets..."
    kubectl get secret -n "${FLOE_NAMESPACE}" \
        "$(floe_service_name postgresql)" \
        "$(floe_service_name minio)" \
        "$(floe_service_name polaris-credentials)" >/dev/null
}

run_remote_kind_startup() {
    check_platform_ready
    ensure_remote_test_runner_image_loaded

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
