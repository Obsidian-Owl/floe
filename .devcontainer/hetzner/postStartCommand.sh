#!/usr/bin/env bash
# =============================================================================
# DevPod Hetzner Post-Start Command
# =============================================================================
#
# Creates a Kind cluster and deploys the floe-platform Helm chart if not
# already running. Idempotent — safe to re-run on workspace restart.
#
# This script runs automatically when the DevPod workspace starts.
# It delegates to the existing setup-cluster.sh for the heavy lifting.

set -euo pipefail

# ─── Strip HOST session env vars injected by devpod agent ────────────────────
#
# The devpod inner agent runs postStartCommand with the Hetzner VM's environment
# injected (DBUS_SESSION_BUS_ADDRESS, XDG_RUNTIME_DIR, etc.). These variables
# reference host paths that do not exist inside the container. When set,
# DBUS_SESSION_BUS_ADDRESS can redirect Docker to a non-existent rootless socket,
# causing `docker info` to fail with "permission denied" despite the socket being
# present at /var/run/docker.sock. Unset them unconditionally so Docker always
# uses the default /var/run/docker.sock path.
unset DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR

# ─── Git safe.directory (DevPod mounts /workspace with different ownership) ──
git config --global --add safe.directory /workspace 2>/dev/null || true

CLUSTER_NAME="${KIND_CLUSTER_NAME:-floe-test}"
NAMESPACE="${TEST_NAMESPACE:-floe-test}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
DOCKER_TIMEOUT="${DOCKER_TIMEOUT:-120}"

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

# ─── Wait for Docker daemon (docker-outside-of-docker feature) ───────────────
#
# The docker-outside-of-docker devcontainer feature mounts the host Docker
# socket at /var/run/docker-host.sock and runs docker-init.sh to expose it
# at /var/run/docker.sock (symlink or socat proxy). It also calls groupmod to
# align the container's docker group GID with the host socket's GID so the
# non-root remoteUser (node) can access the socket.
#
# docker-init.sh requires sudo for groupmod/socat/tee. The Dockerfile grants
# these via /etc/sudoers.d/node-docker. If the socket is not yet accessible,
# wait up to DOCKER_TIMEOUT seconds.

log "Waiting for Docker daemon..."
ELAPSED=0
while ! docker info >/dev/null 2>&1; do
    if [[ ${ELAPSED} -ge ${DOCKER_TIMEOUT} ]]; then
        log "ERROR: Docker daemon not available after ${DOCKER_TIMEOUT}s" >&2
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
log "Docker daemon ready (${ELAPSED}s)"

# ─── Connect devcontainer to Kind network ─────────────────────────────────────
#
# Docker-outside-of-Docker: this container is on the default bridge network.
# Kind creates its own "kind" network. Without connecting them, kubectl from
# this container cannot reach the Kind control plane at its Docker IP.
# We connect BEFORE cluster creation so setup-cluster.sh's kubectl calls work.

connect_to_kind_network() {
    # Find our own container ID. In Docker, hostname defaults to the short
    # container ID (12 hex chars), which docker network connect accepts.
    # This assumption holds as long as devcontainer.json does not set a
    # custom hostname via runArgs (ours does not). The cgroup-based
    # alternative (parsing /proc/self/cgroup) is fragile across cgroup v1/v2
    # and container runtimes, so we prefer hostname with this documented constraint.
    local container_id
    container_id=$(hostname)

    # Check if "kind" network exists
    if ! docker network inspect kind >/dev/null 2>&1; then
        log "Kind network does not exist yet — will connect after cluster creation"
        return 1
    fi

    # Check if already connected
    if docker inspect "${container_id}" --format '{{json .NetworkSettings.Networks}}' 2>/dev/null | grep -q '"kind"'; then
        log "Already connected to kind network"
        return 0
    fi

    docker network connect kind "${container_id}" 2>/dev/null || {
        log "WARNING: Failed to connect to kind network" >&2
        return 1
    }
    log "Connected devcontainer to kind network"
}

# ─── Fix kubeconfig for Docker-outside-of-Docker ─────────────────────────────
#
# Kind maps the API server to a random port on the host's loopback
# (e.g. 127.0.0.1:40017). Inside this devcontainer, 127.0.0.1 refers to the
# container's own loopback — not the host. We rewrite the kubeconfig to use
# the Kind control plane container's Docker network IP (e.g. 172.18.0.2:6443),
# which IS reachable from this container via the shared Docker bridge network.

fix_kubeconfig_for_dood() {
    local control_plane="${CLUSTER_NAME}-control-plane"
    if ! docker inspect "${control_plane}" >/dev/null 2>&1; then
        return 1
    fi

    local cp_ip
    cp_ip=$(docker inspect "${control_plane}" \
        --format '{{(index .NetworkSettings.Networks "kind").IPAddress}}')
    if [[ -z "${cp_ip}" ]]; then
        log "WARNING: Could not determine IP for ${control_plane}" >&2
        return 1
    fi

    local current_server
    current_server=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null || true)
    if [[ "${current_server}" == https://127.0.0.1:* ]]; then
        local internal_server="https://${cp_ip}:6443"
        kubectl config set-cluster "kind-${CLUSTER_NAME}" --server="${internal_server}"
        log "Rewrote kubeconfig: ${current_server} → ${internal_server}"
    fi
}

# ─── Check if Kind cluster already exists ────────────────────────────────────

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    log "Kind cluster '${CLUSTER_NAME}' already exists"

    # Connect to kind network and fix kubeconfig before health check
    connect_to_kind_network || true
    fix_kubeconfig_for_dood || true

    # Verify cluster is healthy
    if kubectl cluster-info --context "kind-${CLUSTER_NAME}" >/dev/null 2>&1; then
        log "Cluster is healthy"

        # Check if pods are healthy (Running or Completed only)
        READY_COUNT=$(kubectl get pods -n "${NAMESPACE}" --no-headers 2>/dev/null \
            | grep -c " Running \| Completed " || true)
        if [[ "${READY_COUNT}" -gt 0 ]]; then
            log "Found ${READY_COUNT} running pods in namespace '${NAMESPACE}'"
            log "Skipping cluster setup — already running"
            exit 0
        else
            log "No healthy pods found in '${NAMESPACE}' — will re-deploy"
        fi
    else
        log "Cluster exists but is unhealthy — deleting and recreating"
        kind delete cluster --name "${CLUSTER_NAME}" 2>/dev/null || true
    fi
fi

# ─── Create cluster via existing setup script ────────────────────────────────

log "Setting up Kind cluster and deploying floe-platform..."

if [[ -f "${WORKSPACE_DIR}/testing/k8s/setup-cluster.sh" ]]; then
    cd "${WORKSPACE_DIR}"
    bash testing/k8s/setup-cluster.sh
    log "Kind cluster setup complete"
else
    log "ERROR: setup-cluster.sh not found at ${WORKSPACE_DIR}/testing/k8s/setup-cluster.sh" >&2
    exit 1
fi

# ─── Post-setup: connect to Kind network and fix kubeconfig ──────────────────

connect_to_kind_network || true
fix_kubeconfig_for_dood || true

# Verify final connectivity
if kubectl cluster-info --context "kind-${CLUSTER_NAME}" >/dev/null 2>&1; then
    log "Cluster reachable"
else
    log "WARNING: Cluster not reachable after setup — check Docker networking" >&2
fi
