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
#   export KUBECONFIG=~/.kube/devpod-${WORKSPACE}.config
#   kubectl get pods -n floe-test

set -euo pipefail

WORKSPACE="${1:-floe}"
LOCAL_KUBECONFIG="${HOME}/.kube/devpod-${WORKSPACE}.config"
LOCAL_API_PORT="${DEVPOD_K8S_API_PORT:-26443}"

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

# Check workspace is running (devpod status outputs to stderr)
if ! devpod status "${WORKSPACE}" 2>&1 | grep -qi "running"; then
    error "DevPod workspace '${WORKSPACE}' is not running. Start it with: devpod up ${WORKSPACE}"
fi

# ─── Extract kubeconfig ─────────────────────────────────────────────────────

log "Extracting kubeconfig from workspace '${WORKSPACE}'..."

# Read kubeconfig — try KUBECONFIG env var path first, then common locations
REMOTE_CONFIG=$(devpod ssh "${WORKSPACE}" --command 'bash -c "cat \${KUBECONFIG:-/home/node/.kube/config} 2>/dev/null || cat ~/.kube/config 2>/dev/null"' 2>/dev/null) || \
    error "Failed to read kubeconfig from workspace. Is the Kind cluster running?"

# Parse the remote API server address and port.
# In Docker-outside-of-Docker (DooD) environments, the kubeconfig may have been
# rewritten to use the Kind control plane's Docker network IP (e.g. 172.18.0.2:6443)
# instead of the default 127.0.0.1:<random-port>.
REMOTE_API_HOST=""
REMOTE_API_PORT=""

# Try DooD format first: non-loopback IP (e.g. 172.18.0.2:6443)
REMOTE_API_HOST=$(echo "${REMOTE_CONFIG}" | sed -nE 's|.*server: https://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):[0-9]+.*|\1|p' | head -1)
REMOTE_API_PORT=$(echo "${REMOTE_CONFIG}" | sed -nE 's|.*server: https://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:([0-9]+).*|\1|p' | head -1)

if [[ -z "${REMOTE_API_PORT}" ]]; then
    error "Could not parse K8s API server from remote kubeconfig"
fi
if [[ ! "${REMOTE_API_PORT}" =~ ^[0-9]+$ ]]; then
    error "Invalid remote API port: ${REMOTE_API_PORT}"
fi

# Default tunnel target is localhost (standard Kind setup).
# For DooD, use the Docker network IP directly since 127.0.0.1 won't reach Kind.
TUNNEL_TARGET="${REMOTE_API_HOST:-localhost}"
if [[ "${TUNNEL_TARGET}" == "127.0.0.1" ]]; then
    TUNNEL_TARGET="localhost"
fi

log "Remote K8s API: ${TUNNEL_TARGET}:${REMOTE_API_PORT}"

# ─── Rewrite and save kubeconfig ─────────────────────────────────────────────

mkdir -p "$(dirname "${LOCAL_KUBECONFIG}")"

echo "${REMOTE_CONFIG}" | \
    sed -E "s|server: https://[^:]+:[0-9]+|server: https://127.0.0.1:${LOCAL_API_PORT}|g" \
    > "${LOCAL_KUBECONFIG}"

chmod 600 "${LOCAL_KUBECONFIG}"
log "Kubeconfig written to ${LOCAL_KUBECONFIG}"

# ─── Establish SSH tunnel ────────────────────────────────────────────────────

# Kill existing tunnel if any (match on local port regardless of remote target)
if pgrep -f "devpod ssh.*-L ${LOCAL_API_PORT}:" >/dev/null 2>&1; then
    log "Killing existing SSH tunnel on port ${LOCAL_API_PORT}..."
    pkill -f "devpod ssh.*-L ${LOCAL_API_PORT}:" 2>/dev/null || true
    sleep 1
fi

log "Establishing SSH tunnel: localhost:${LOCAL_API_PORT} → ${TUNNEL_TARGET}:${REMOTE_API_PORT}..."

# Use devpod ssh for tunneling — it handles SSH config/credentials internally.
# Run in background with nohup to keep the tunnel alive after script exits.
# SSH keepalive: devpod ssh uses its own --ssh-keepalive-interval flag
# (not OpenSSH -o options). Default is 55s; we set 30s for faster detection.
# stdin redirect: prevent nohup from hanging on stdin.
nohup devpod ssh "${WORKSPACE}" \
    --ssh-keepalive-interval 30s \
    -L "${LOCAL_API_PORT}:${TUNNEL_TARGET}:${REMOTE_API_PORT}" \
    --command "sleep infinity" \
    >>"${HOME}/.kube/devpod-ssh.log" 2>&1 < /dev/null &

TUNNEL_PID=$!

# Wait briefly for tunnel to establish
sleep 3

if ! kill -0 "${TUNNEL_PID}" 2>/dev/null; then
    error "SSH tunnel process exited immediately. Check ${HOME}/.kube/devpod-ssh.log"
fi

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
