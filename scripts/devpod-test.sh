#!/usr/bin/env bash
# =============================================================================
# DevPod E2E test lifecycle: up → health → sync → tunnel → test → delete
# =============================================================================
#
# Runs the full E2E test cycle on a remote Hetzner DevPod workspace.
# Cost-safe: trap handler guarantees VM deletion on ANY exit path.
#
# Usage:
#   ./scripts/devpod-test.sh                    # Full lifecycle
#   DEVPOD_HEALTH_TIMEOUT=180 ./scripts/devpod-test.sh  # Custom timeout
#
# Prerequisites:
#   - devpod CLI installed
#   - Hetzner provider configured (run: make devpod-setup)
#   - .env file with DEVPOD_HETZNER_TOKEN
#   - current branch pushed to origin, or DEVPOD_SOURCE set explicitly
#
# Environment:
#   DEVPOD_E2E_EXECUTION remote|local (default: remote). The local fallback is
#                        retained only for debugging DevPod image transport.
#   DEVPOD_REMOTE_WORKDIR Remote repository root inside the workspace
#                        (default: /workspace).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=./devpod-source.sh
source "${SCRIPT_DIR}/devpod-source.sh"

# ─── Configuration ────────────────────────────────────────────────────────────

WORKSPACE="${DEVPOD_WORKSPACE:-floe}"
DEVCONTAINER="${DEVPOD_DEVCONTAINER:-.devcontainer/hetzner/devcontainer.json}"
if [[ "${DEVCONTAINER}" != .devcontainer/* ]]; then
    echo "[devpod-test] ERROR: DEVPOD_DEVCONTAINER must be a relative path under .devcontainer/. Got: '${DEVCONTAINER}'" >&2
    exit 1
fi
KUBECONFIG_PATH="${HOME}/.kube/devpod-${WORKSPACE}.config"
HEALTH_TIMEOUT="${DEVPOD_HEALTH_TIMEOUT:-120}"
NAMESPACE="${TEST_NAMESPACE:-floe-test}"
PROVIDER="${DEVPOD_PROVIDER:-hetzner}"
DEVPOD_E2E_EXECUTION="${DEVPOD_E2E_EXECUTION:-remote}"
DEVPOD_REMOTE_WORKDIR="${DEVPOD_REMOTE_WORKDIR:-/workspace}"

# Track whether we created the workspace (for cleanup decisions)
WORKSPACE_CREATED=false
TEST_EXIT_CODE=0

# ─── Logging ──────────────────────────────────────────────────────────────────

log() {
    echo "[devpod-test] $(date '+%H:%M:%S') $*" >&2
}

error() {
    echo "[devpod-test] $(date '+%H:%M:%S') ERROR: $*" >&2
}

# ─── Cleanup (cost-safety guarantee) ─────────────────────────────────────────

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    log "Cleanup triggered (exit code: ${exit_code})"

    # Kill SSH tunnels (best-effort)
    if [[ -x "${SCRIPT_DIR}/devpod-tunnels.sh" ]]; then
        "${SCRIPT_DIR}/devpod-tunnels.sh" --kill 2>/dev/null || true
        log "SSH tunnels killed"
    fi

    # Delete workspace to stop billing (best-effort)
    if [[ "${WORKSPACE_CREATED}" == "true" ]]; then
        log "Deleting workspace '${WORKSPACE}' to stop billing..."
        if devpod delete "${WORKSPACE}" --force 2>/dev/null; then
            log "Workspace deleted"
        else
            error "Failed to delete workspace '${WORKSPACE}'!"
            error "MANUAL ACTION REQUIRED: Run 'devpod delete ${WORKSPACE} --force' or delete the VM in Hetzner Cloud Console."
        fi
    fi

    # Propagate the test exit code, not the cleanup exit code
    if [[ ${TEST_EXIT_CODE} -ne 0 ]]; then
        exit "${TEST_EXIT_CODE}"
    fi
    exit "${exit_code}"
}

# Set trap BEFORE any devpod operations
trap cleanup EXIT INT TERM

# ─── Input validation ─────────────────────────────────────────────────────────

if [[ ! "${WORKSPACE}" =~ ^[a-zA-Z][a-zA-Z0-9_-]*$ ]]; then
    error "Invalid workspace name: '${WORKSPACE}'"
    exit 1
fi

# ─── Pre-flight checks ───────────────────────────────────────────────────────

if ! command -v devpod >/dev/null 2>&1; then
    error "devpod CLI not found. Install from https://devpod.sh/docs/getting-started/install"
    exit 1
fi

provider_list="$(devpod provider list 2>/dev/null || true)"
if [[ "${provider_list}" != *hetzner* ]]; then
    error "Hetzner provider not configured. Run: make devpod-setup"
    exit 1
fi

# ─── Step 1: Provision workspace ─────────────────────────────────────────────

log "Step 1/5: Provisioning workspace '${WORKSPACE}' on ${PROVIDER}..."
log "  This provisions a Hetzner VM, builds the container, and deploys the Kind cluster."
log "  First run takes ~10-15 minutes. Subsequent runs reuse the image."

# Mark before provisioning so cleanup can delete a partially-provisioned VM
WORKSPACE_CREATED=true
DEVPOD_SOURCE_RESOLVED="$(devpod_resolve_source "${PROJECT_ROOT}")" \
    || { error "Failed to resolve DevPod source"; exit 1; }
log "  Source: ${DEVPOD_SOURCE_RESOLVED}"
devpod up "${WORKSPACE}" \
    --source "${DEVPOD_SOURCE_RESOLVED}" \
    --id "${WORKSPACE}" \
    --provider "${PROVIDER}" \
    --devcontainer-path "${DEVCONTAINER}" \
    --ide none \
    || { error "Failed to provision workspace"; exit 1; }
log "Workspace provisioned"

# ─── Step 2: Health gate ─────────────────────────────────────────────────────

log "Step 2/5: Verifying cluster health (timeout: ${HEALTH_TIMEOUT}s)..."

# Sync kubeconfig first so we can check cluster health
bash "${SCRIPT_DIR}/devpod-sync-kubeconfig.sh" "${WORKSPACE}" \
    || { error "Failed to sync kubeconfig"; exit 1; }

ELAPSED=0
INTERVAL=10
while [[ ${ELAPSED} -lt ${HEALTH_TIMEOUT} ]]; do
    # Count non-healthy pods (not Running and not Completed)
    POD_ROWS="$(kubectl --kubeconfig="${KUBECONFIG_PATH}" get pods -n "${NAMESPACE}" --no-headers 2>/dev/null || true)"
    TOTAL="$(printf '%s\n' "${POD_ROWS}" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')"
    if [[ "${TOTAL}" -eq 0 ]]; then
        UNHEALTHY=0
    else
        UNHEALTHY="$(printf '%s\n' "${POD_ROWS}" | grep -Ecv " Running | Completed " || true)"
    fi

    if [[ "${TOTAL}" -gt 0 ]] && [[ "${UNHEALTHY}" -eq 0 ]]; then
        log "All ${TOTAL} pods healthy"
        break
    fi

    log "  Waiting for pods... (${UNHEALTHY} unhealthy of ${TOTAL}, ${ELAPSED}s elapsed)"
    sleep "${INTERVAL}"
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [[ ${ELAPSED} -ge ${HEALTH_TIMEOUT} ]]; then
    error "Cluster health check timed out after ${HEALTH_TIMEOUT}s"
    error "Unhealthy pods:"
    kubectl --kubeconfig="${KUBECONFIG_PATH}" get pods -n "${NAMESPACE}" --no-headers 2>/dev/null \
        | grep -v " Running \| Completed " >&2 || true
    exit 1
fi

# ─── Step 3: Establish tunnels ───────────────────────────────────────────────

log "Step 3/5: Establishing service port tunnels..."

bash "${SCRIPT_DIR}/devpod-tunnels.sh" \
    || { error "Failed to establish SSH tunnels"; exit 1; }

log "Tunnels established"

# ─── Step 4: Run E2E tests ───────────────────────────────────────────────────

log "Step 4/5: Running E2E tests..."

# Run tests and capture exit code (don't let set -e kill us)
set +e
case "${DEVPOD_E2E_EXECUTION}" in
    remote)
        log "Running E2E inside DevPod workspace '${WORKSPACE}' (workdir: ${DEVPOD_REMOTE_WORKDIR})..."
        devpod ssh "${WORKSPACE}" \
            --start-services=false \
            --workdir "${DEVPOD_REMOTE_WORKDIR}" \
            --command "IMAGE_LOAD_METHOD=kind make test-e2e"
        TEST_EXIT_CODE=$?
        ;;
    local)
        log "Running E2E from local host (DEVPOD_E2E_EXECUTION=local). This may stream large images over DevPod transport."
        make -C "${PROJECT_ROOT}" test-e2e KUBECONFIG="${KUBECONFIG_PATH}"
        TEST_EXIT_CODE=$?
        ;;
    *)
        error "Invalid DEVPOD_E2E_EXECUTION='${DEVPOD_E2E_EXECUTION}'. Use: remote|local"
        TEST_EXIT_CODE=2
        ;;
esac
set -e

if [[ ${TEST_EXIT_CODE} -eq 0 ]]; then
    log "E2E tests PASSED"
else
    error "E2E tests FAILED (exit code: ${TEST_EXIT_CODE})"
fi

# ─── Step 5: Cleanup (via trap handler) ──────────────────────────────────────

log "Step 5/5: Cleaning up..."
# Cleanup happens automatically via the EXIT trap
