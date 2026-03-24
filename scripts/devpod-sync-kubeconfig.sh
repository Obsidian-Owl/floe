#!/usr/bin/env bash
# =============================================================================
# Sync kubeconfig from DevPod workspace to local machine
# =============================================================================
#
# Extracts kubeconfig from the remote DevPod workspace, rewrites the K8s
# API server address to localhost, and establishes an SSH tunnel.
#
# Usage:
#   ./scripts/devpod-sync-kubeconfig.sh [workspace-name]
#
# After running, use:
#   export KUBECONFIG=~/.kube/devpod-floe.config
#   kubectl get pods -n floe-test

set -euo pipefail

WORKSPACE="${1:-floe}"
LOCAL_KUBECONFIG="${HOME}/.kube/devpod-floe.config"
LOCAL_API_PORT="${DEVPOD_K8S_API_PORT:-26443}"
SSH_TARGET="${WORKSPACE}.devpod"

# Validate inputs contain only safe characters
if [[ ! "${WORKSPACE}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "[devpod-sync] ERROR: Invalid workspace name: ${WORKSPACE}" >&2
    exit 1
fi
if [[ ! "${LOCAL_API_PORT}" =~ ^[0-9]+$ ]]; then
    echo "[devpod-sync] ERROR: Invalid port: ${LOCAL_API_PORT}" >&2
    exit 1
fi

log() {
    echo "[devpod-sync] $*"
}

error() {
    echo "[devpod-sync] ERROR: $*" >&2
    exit 1
}

# ─── Pre-flight checks ──────────────────────────────────────────────────────

if ! command -v devpod >/dev/null 2>&1; then
    error "devpod CLI not found. Install from https://devpod.sh"
fi

# Check workspace is running
if ! devpod status "${WORKSPACE}" 2>/dev/null | grep -qi "running"; then
    error "DevPod workspace '${WORKSPACE}' is not running. Start it with: devpod up ${WORKSPACE}"
fi

# ─── Extract kubeconfig ─────────────────────────────────────────────────────

log "Extracting kubeconfig from workspace '${WORKSPACE}'..."

REMOTE_CONFIG=$(devpod ssh "${WORKSPACE}" -- cat /home/node/.kube/config 2>/dev/null) || \
    error "Failed to read kubeconfig from workspace. Is the Kind cluster running?"

# Parse the remote API server port (POSIX-compatible — no grep -P)
REMOTE_API_PORT=$(echo "${REMOTE_CONFIG}" | sed -nE 's|.*server: https://127\.0\.0\.1:([0-9]+).*|\1|p' | head -1)
if [[ -z "${REMOTE_API_PORT}" ]]; then
    REMOTE_API_PORT=$(echo "${REMOTE_CONFIG}" | sed -nE 's|.*server: https://0\.0\.0\.0:([0-9]+).*|\1|p' | head -1)
fi
if [[ -z "${REMOTE_API_PORT}" ]]; then
    error "Could not parse K8s API server port from remote kubeconfig"
fi
if [[ ! "${REMOTE_API_PORT}" =~ ^[0-9]+$ ]]; then
    error "Invalid remote API port: ${REMOTE_API_PORT}"
fi

log "Remote K8s API port: ${REMOTE_API_PORT}"

# ─── Rewrite and save kubeconfig ─────────────────────────────────────────────

mkdir -p "$(dirname "${LOCAL_KUBECONFIG}")"

echo "${REMOTE_CONFIG}" | \
    sed -E "s|server: https://[^:]+:[0-9]+|server: https://localhost:${LOCAL_API_PORT}|g" \
    > "${LOCAL_KUBECONFIG}"

chmod 600 "${LOCAL_KUBECONFIG}"
log "Kubeconfig written to ${LOCAL_KUBECONFIG}"

# ─── Establish SSH tunnel ────────────────────────────────────────────────────

# Kill existing tunnel if any
if pgrep -f "ssh.*-L ${LOCAL_API_PORT}:localhost:${REMOTE_API_PORT}.*${SSH_TARGET}" >/dev/null 2>&1; then
    log "Killing existing SSH tunnel on port ${LOCAL_API_PORT}..."
    pkill -f "ssh.*-L ${LOCAL_API_PORT}:localhost:${REMOTE_API_PORT}.*${SSH_TARGET}" 2>/dev/null || true
    sleep 1
fi

log "Establishing SSH tunnel: localhost:${LOCAL_API_PORT} → remote:${REMOTE_API_PORT}..."
ssh -fNL "${LOCAL_API_PORT}:localhost:${REMOTE_API_PORT}" "${SSH_TARGET}" 2>>"${HOME}/.kube/devpod-ssh.log" || \
    error "Failed to establish SSH tunnel. Check SSH config for '${SSH_TARGET}' (see ~/.kube/devpod-ssh.log)"

# ─── Validate ────────────────────────────────────────────────────────────────

log "Validating connection..."
if kubectl --kubeconfig "${LOCAL_KUBECONFIG}" cluster-info >/dev/null 2>&1; then
    log "SUCCESS: K8s cluster accessible at localhost:${LOCAL_API_PORT}"
    log ""
    log "Usage:"
    log "  export KUBECONFIG=${LOCAL_KUBECONFIG}"
    log "  kubectl get pods -n floe-test"
else
    log "WARNING: cluster-info check failed. The tunnel may need a moment to establish."
    log "Retry: kubectl --kubeconfig ${LOCAL_KUBECONFIG} cluster-info"
fi
