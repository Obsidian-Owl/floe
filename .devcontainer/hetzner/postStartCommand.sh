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

CLUSTER_NAME="${KIND_CLUSTER_NAME:-floe-test}"
NAMESPACE="${TEST_NAMESPACE:-floe-test}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

# ─── Check if Kind cluster already exists ────────────────────────────────────

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    log "Kind cluster '${CLUSTER_NAME}' already exists"

    # Verify cluster is healthy
    if kubectl cluster-info --context "kind-${CLUSTER_NAME}" >/dev/null 2>&1; then
        log "Cluster is healthy"

        # Check if pods are running
        POD_COUNT=$(kubectl get pods -n "${NAMESPACE}" --no-headers 2>/dev/null | wc -l | tr -d ' ')
        if [[ "${POD_COUNT}" -gt 0 ]]; then
            log "Found ${POD_COUNT} pods in namespace '${NAMESPACE}'"
            log "Skipping cluster setup — already running"
            exit 0
        else
            log "No pods found in '${NAMESPACE}' — Helm chart may need deploying"
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
