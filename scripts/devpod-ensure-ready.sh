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
#   DEVPOD_WORKSPACE  Workspace name (default: floe)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${DEVPOD_WORKSPACE:-floe}"
KUBECONFIG_PATH="${HOME}/.kube/devpod-floe.config"

log() {
    echo "[devpod-ready] $*"
}

error() {
    echo "[devpod-ready] ERROR: $*" >&2
    exit 1
}

# ─── 1. Check devpod CLI exists ──────────────────────────────────────────────

if ! command -v devpod >/dev/null 2>&1; then
    error "devpod CLI not found in PATH.
  Install: https://devpod.sh/docs/getting-started/install
  Then run: make devpod-up"
fi

# ─── 2. Check workspace is running ───────────────────────────────────────────

if ! devpod status "${WORKSPACE}" 2>&1 | grep -qi "running"; then
    error "DevPod workspace '${WORKSPACE}' is not running.
  Start it with: make devpod-up
  Or run the full lifecycle: make devpod-test"
fi

log "Workspace '${WORKSPACE}' is running."

# ─── 3. Sync kubeconfig (delegates to devpod-sync-kubeconfig.sh) ─────────────

log "Syncing kubeconfig..."
if ! bash "${SCRIPT_DIR}/devpod-sync-kubeconfig.sh" "${WORKSPACE}"; then
    error "Failed to sync kubeconfig. Check DevPod workspace health."
fi

# ─── 4. Validate cluster reachable ───────────────────────────────────────────

log "Validating cluster connectivity..."
if ! kubectl --kubeconfig "${KUBECONFIG_PATH}" cluster-info >/dev/null 2>&1; then
    error "K8s cluster not reachable via ${KUBECONFIG_PATH}.
  The SSH tunnel may need a moment. Retry in a few seconds, or check:
    kubectl --kubeconfig ${KUBECONFIG_PATH} cluster-info"
fi

log "SUCCESS: DevPod workspace ready, K8s cluster accessible."
