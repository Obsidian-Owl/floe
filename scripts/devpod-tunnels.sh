#!/usr/bin/env bash
# =============================================================================
# SSH tunnel script for DevPod workspace service access
# =============================================================================
#
# Forwards all E2E test service ports from the remote DevPod workspace
# to localhost. Services are accessible at the same ports as local Kind.
#
# Usage:
#   ./scripts/devpod-tunnels.sh          # Start tunnels
#   ./scripts/devpod-tunnels.sh --kill   # Stop all tunnels
#   ./scripts/devpod-tunnels.sh --status # Show active tunnels

set -euo pipefail

WORKSPACE="${DEVPOD_WORKSPACE:-floe}"
if [[ ! "${WORKSPACE}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "ERROR: Invalid workspace name: ${WORKSPACE}" >&2
    exit 1
fi
SSH_TARGET="${WORKSPACE}.devpod"

# Port mappings: local_port:remote_port:service_name
# Subset of kind-config.yaml extraPortMappings required for E2E tests and demo.
# Not forwarded (not needed for E2E): Grafana (3001), Prometheus (9090),
# Marquez Admin (5001), OCI Registry (30500/30501), Keycloak (8082),
# Infisical (8083), PostgreSQL (5432). Add entries here if tests need them.
PORTS=(
    "3100:3100:dagster-webserver"
    "8181:8181:polaris-api"
    "8182:8182:polaris-management"
    "9000:9000:minio-api"
    "9001:9001:minio-console"
    "16686:16686:jaeger-query"
    "5100:5100:marquez-api"
    "4317:4317:otel-grpc"
    "4318:4318:otel-http"
)

log() {
    echo "[devpod-tunnels] $*"
}

tunnel_pids() {
    pgrep -f "ssh.*${SSH_TARGET}" 2>/dev/null || true
}

# ─── Kill mode ───────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--kill" ]]; then
    PIDS=$(tunnel_pids)
    if [[ -n "${PIDS}" ]]; then
        log "Killing SSH tunnels to ${SSH_TARGET}..."
        echo "${PIDS}" | xargs kill 2>/dev/null || true
        log "Tunnels stopped"
    else
        log "No active tunnels found"
    fi
    exit 0
fi

# ─── Status mode ─────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--status" ]]; then
    PIDS=$(tunnel_pids)
    if [[ -n "${PIDS}" ]]; then
        log "Active SSH tunnels to ${SSH_TARGET}:"
        # shellcheck disable=SC2086
        ps -p ${PIDS} -o pid,args 2>/dev/null | tail -n +2
    else
        log "No active tunnels"
    fi
    exit 0
fi

# ─── Pre-flight checks ──────────────────────────────────────────────────────

if ! command -v ssh >/dev/null 2>&1; then
    echo "ERROR: ssh not found" >&2
    exit 1
fi

# Check if tunnels already exist
EXISTING=$(tunnel_pids)
if [[ -n "${EXISTING}" ]]; then
    log "Tunnels already active (PIDs: $(echo "${EXISTING}" | tr '\n' ' '))"
    log "Use --kill to stop, or --status to inspect"
    exit 0
fi

# ─── Build SSH command ───────────────────────────────────────────────────────

# SSH keepalive: probe every 30s, disconnect after 3 missed probes (90s dead).
SSH_ARGS=(-fN -o ServerAliveInterval=30 -o ServerAliveCountMax=3)
FORWARDED=()
for MAPPING in "${PORTS[@]}"; do
    LOCAL_PORT="${MAPPING%%:*}"
    REST="${MAPPING#*:}"
    REMOTE_PORT="${REST%%:*}"
    SERVICE="${REST#*:}"

    # Check if local port is already in use
    if lsof -ti ":${LOCAL_PORT}" >/dev/null 2>&1; then
        log "SKIP: Port ${LOCAL_PORT} (${SERVICE}) already in use"
        continue
    fi

    SSH_ARGS+=(-L "${LOCAL_PORT}:localhost:${REMOTE_PORT}")
    FORWARDED+=("${MAPPING}")
    log "Forward: localhost:${LOCAL_PORT} → ${SERVICE} (:${REMOTE_PORT})"
done

# Guard: no tunnels to establish if all ports were skipped
if [[ ${#FORWARDED[@]} -eq 0 ]]; then
    log "WARNING: All ports were already in use — no tunnels to establish"
    log "Run '--kill' then retry, or check existing processes with '--status'"
    exit 0
fi

# ─── Establish tunnels ───────────────────────────────────────────────────────

log "Connecting to ${SSH_TARGET}..."
ssh "${SSH_ARGS[@]}" "${SSH_TARGET}" 2>>"${HOME}/.kube/devpod-ssh.log" || {
    echo "ERROR: Failed to establish SSH tunnels to ${SSH_TARGET}" >&2
    echo "  Check: ssh ${SSH_TARGET} (DevPod SSH config)" >&2
    echo "  Check: devpod status ${WORKSPACE}" >&2
    exit 1
}

log ""
log "${#FORWARDED[@]} of ${#PORTS[@]} tunnels established. Services available at:"
for MAPPING in "${FORWARDED[@]}"; do
    LOCAL_PORT="${MAPPING%%:*}"
    REST="${MAPPING#*:}"
    SERVICE="${REST#*:}"
    log "  http://localhost:${LOCAL_PORT}  →  ${SERVICE}"
done
log ""
log "Stop tunnels: $0 --kill"
