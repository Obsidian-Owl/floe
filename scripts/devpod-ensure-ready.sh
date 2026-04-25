#!/usr/bin/env bash
# =============================================================================
# Ensure DevPod workspace is running and K8s cluster is accessible
# =============================================================================
#
# Validates that the DevPod workspace is running, syncs kubeconfig via
# devpod-sync-kubeconfig.sh, and confirms the K8s cluster is reachable.
#
# Does NOT provision or delete — just validates + connects.
# Idempotent: safe to call multiple times.
#
# Usage:
#   ./scripts/devpod-ensure-ready.sh
#
# Environment:
#   DEVPOD_WORKSPACE    Workspace name (default: floe)
#   DEVPOD_AUTO_START   Restart a stopped saved workspace when set to 1 (default: 1)
#   DEVPOD_PROVIDER     Provider used for restart/create via devpod up (default: hetzner)
#   DEVPOD_DEVCONTAINER Devcontainer path used for restart/create
#                       (default: .devcontainer/hetzner/devcontainer.json)
#   DEVPOD_SOURCE       Optional explicit DevPod source, otherwise origin@branch
#   DEVPOD_GIT_REF      Optional branch/ref when deriving the Git source

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=./devpod-source.sh
source "${SCRIPT_DIR}/devpod-source.sh"
WORKSPACE="${DEVPOD_WORKSPACE:-floe}"
AUTO_START="${DEVPOD_AUTO_START:-1}"
PROVIDER="${DEVPOD_PROVIDER:-hetzner}"
DEVCONTAINER="${DEVPOD_DEVCONTAINER:-.devcontainer/hetzner/devcontainer.json}"
KUBECONFIG_PATH="${HOME}/.kube/devpod-${WORKSPACE}.config"

log() {
    echo "[devpod-ready] $*"
}

error() {
    echo "[devpod-ready] ERROR: $*" >&2
    exit 1
}

workspace_running() {
    devpod status "${WORKSPACE}" 2>&1 | grep -qi "running"
}

# ─── 1. Check devpod CLI exists ──────────────────────────────────────────────

if ! command -v devpod >/dev/null 2>&1; then
    error "devpod CLI not found in PATH.
  Install: https://devpod.sh/docs/getting-started/install
  Then run: make devpod-up"
fi

# ─── 2. Check workspace is running (or start it if allowed) ─────────────────

if ! workspace_running; then
    case "${AUTO_START}" in
        1|true|TRUE|yes|YES)
            if [[ "${DEVCONTAINER}" != .devcontainer/* ]]; then
                error "DEVPOD_DEVCONTAINER must stay under .devcontainer/. Got: '${DEVCONTAINER}'"
            fi

            log "Workspace '${WORKSPACE}' is not running. Starting it via devpod up..."
            DEVPOD_SOURCE_RESOLVED="$(devpod_resolve_source "${PROJECT_ROOT}")" \
                || error "Failed to resolve DevPod source"
            log "Using source: ${DEVPOD_SOURCE_RESOLVED}"
            devpod up "${WORKSPACE}" \
                --source "${DEVPOD_SOURCE_RESOLVED}" \
                --id "${WORKSPACE}" \
                --provider "${PROVIDER}" \
                --devcontainer-path "${DEVCONTAINER}" \
                --ide none
            ;;
        *)
            error "DevPod workspace '${WORKSPACE}' is not running.
  Start it with: make devpod-up
  Or run the full lifecycle: make devpod-test"
            ;;
    esac
fi

log "Workspace '${WORKSPACE}' is running."

# ─── 3. Sync kubeconfig (delegates to devpod-sync-kubeconfig.sh) ─────────────

log "Syncing kubeconfig..."
if ! bash "${SCRIPT_DIR}/devpod-sync-kubeconfig.sh" "${WORKSPACE}"; then
    error "Failed to sync kubeconfig. Check DevPod workspace health."
fi

# ─── 4. Validate cluster reachable (retry for SSH tunnel startup) ────────────

log "Validating cluster connectivity..."
RETRIES=0
MAX_RETRIES=10
while ! kubectl --kubeconfig "${KUBECONFIG_PATH}" cluster-info >/dev/null 2>&1; do
    RETRIES=$((RETRIES + 1))
    if [[ ${RETRIES} -ge ${MAX_RETRIES} ]]; then
        error "K8s cluster not reachable via ${KUBECONFIG_PATH} after ${MAX_RETRIES} attempts.
  Check: kubectl --kubeconfig ${KUBECONFIG_PATH} cluster-info"
    fi
    log "Waiting for SSH tunnel... (${RETRIES}/${MAX_RETRIES})"
    sleep 2
done

log "SUCCESS: DevPod workspace ready, K8s cluster accessible."
