#!/usr/bin/env bash
# =============================================================================
# One-time DevPod Hetzner provider setup
# =============================================================================
#
# Configures the Hetzner cloud provider for DevPod from .env file settings.
# Idempotent — safe to re-run. Converges to desired state on every run.
#
# Usage:
#   ./scripts/devpod-setup.sh
#
# Required .env variables:
#   DEVPOD_HETZNER_TOKEN  - Hetzner Cloud API token (read + write)
#
# Optional .env variables:
#   DEVPOD_WORKSPACE            - Workspace name (default: floe)
#   DEVPOD_MACHINE_TYPE         - Hetzner machine type (default: ccx33)
#   DEVPOD_REGION               - Hetzner region (default: sin)
#   DEVPOD_INACTIVITY_TIMEOUT   - VM auto-delete timeout (default: 120m)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROVIDER_REPO="mrsimonemms/devpod-provider-hetzner"

log() {
    echo "[devpod-setup] $*" >&2
}

error() {
    echo "[devpod-setup] ERROR: $*" >&2
    exit 1
}

# ─── Source .env ──────────────────────────────────────────────────────────────

ENV_FILE="${PROJECT_ROOT}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
else
    error ".env file not found at ${ENV_FILE}. Copy .env.example to .env and set DEVPOD_HETZNER_TOKEN."
fi

# Defaults (overridable via .env — evaluated AFTER sourcing)
MACHINE_TYPE="${DEVPOD_MACHINE_TYPE:-ccx33}"
REGION="${DEVPOD_REGION:-sin}"
DISK_SIZE="${DEVPOD_DISK_SIZE:-64}"
DISK_IMAGE="${DEVPOD_DISK_IMAGE:-docker-ce}"
INACTIVITY_TIMEOUT="${DEVPOD_INACTIVITY_TIMEOUT:-120m}"

# ─── Validate inputs ─────────────────────────────────────────────────────────

WORKSPACE="${DEVPOD_WORKSPACE:-floe}"

if [[ -z "${DEVPOD_HETZNER_TOKEN:-}" ]]; then
    error "DEVPOD_HETZNER_TOKEN is not set in .env. Get a token from Hetzner Cloud Console → Security → API Tokens (read + write)."
fi

if [[ ! "${WORKSPACE}" =~ ^[a-zA-Z][a-zA-Z0-9_-]*$ ]]; then
    error "Invalid workspace name: '${WORKSPACE}'. Must start with a letter and contain only alphanumerics, hyphens, and underscores."
fi

# ─── Pre-flight ───────────────────────────────────────────────────────────────

if ! command -v devpod >/dev/null 2>&1; then
    error "devpod CLI not found. Install from https://devpod.sh/docs/getting-started/install"
fi

# ─── Install provider if not present ─────────────────────────────────────────

if devpod provider list 2>/dev/null | grep -q "hetzner"; then
    log "Hetzner provider already installed"
else
    log "Installing Hetzner provider from ${PROVIDER_REPO}..."
    # Provider v1.0.1 schema requires TOKEN (not HCLOUD_TOKEN). The deprecation
    # warning comes from the hcloud SDK, not the provider option schema.
    # Suppress trace mode to prevent token leakage in CI logs
    { set +x; } 2>/dev/null
    devpod provider add "${PROVIDER_REPO}" \
        -o TOKEN="${DEVPOD_HETZNER_TOKEN}" \
        -o MACHINE_TYPE="${MACHINE_TYPE}" \
        -o REGION="${REGION}" \
        -o DISK_SIZE="${DISK_SIZE}" \
        -o DISK_IMAGE="${DISK_IMAGE}" \
        -o INACTIVITY_TIMEOUT="${INACTIVITY_TIMEOUT}" \
        || error "Failed to add Hetzner provider"
    log "Provider installed and configured"
    exit 0
fi

# ─── Converge provider options ────────────────────────────────────────────────

log "Setting provider options (convergent)..."
# Suppress trace mode to prevent token leakage in CI logs
{ set +x; } 2>/dev/null
devpod provider set-options hetzner \
    -o TOKEN="${DEVPOD_HETZNER_TOKEN}" \
    -o MACHINE_TYPE="${MACHINE_TYPE}" \
    -o REGION="${REGION}" \
    -o DISK_SIZE="${DISK_SIZE}" \
    -o DISK_IMAGE="${DISK_IMAGE}" \
    -o INACTIVITY_TIMEOUT="${INACTIVITY_TIMEOUT}" \
    || error "Failed to set provider options"

log "Provider configured: MACHINE_TYPE=${MACHINE_TYPE}, REGION=${REGION}, DISK_SIZE=${DISK_SIZE}, INACTIVITY_TIMEOUT=${INACTIVITY_TIMEOUT}"
log "Setup complete"
