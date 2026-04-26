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
#   DEVPOD_REMOTE_E2E_TIMEOUT Remote E2E timeout in seconds (default: 7200).
#   DEVPOD_REMOTE_POLL_INTERVAL Remote E2E polling interval in seconds
#                        (default: 20).
#   DEVPOD_REMOTE_POLL_FAILURE_LIMIT Consecutive DevPod poll failures tolerated
#                        before aborting (default: 30).
#   DEVPOD_UP_RECOVERY_TIMEOUT Seconds to poll workspace status after a
#                        transport-level `devpod up` failure (default: 600).
#   DEVPOD_ENABLE_REMOTE_TUNNELS Set to 1 to establish host service tunnels
#                        before remote E2E. Default 0 because remote tests run
#                        inside the DevPod workspace network.

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
DEVPOD_REMOTE_RUN_ROOT="${DEVPOD_REMOTE_RUN_ROOT:-/tmp/floe-devpod-e2e}"
DEVPOD_REMOTE_E2E_TIMEOUT="${DEVPOD_REMOTE_E2E_TIMEOUT:-7200}"
DEVPOD_REMOTE_POLL_INTERVAL="${DEVPOD_REMOTE_POLL_INTERVAL:-20}"
DEVPOD_REMOTE_POLL_FAILURE_LIMIT="${DEVPOD_REMOTE_POLL_FAILURE_LIMIT:-30}"
DEVPOD_UP_RECOVERY_TIMEOUT="${DEVPOD_UP_RECOVERY_TIMEOUT:-600}"
DEVPOD_UP_RECOVERY_INTERVAL="${DEVPOD_UP_RECOVERY_INTERVAL:-15}"
DEVPOD_ENABLE_REMOTE_TUNNELS="${DEVPOD_ENABLE_REMOTE_TUNNELS:-0}"
REMOTE_RUN_ID="run-$(date -u '+%Y%m%dT%H%M%SZ')-$$"
REMOTE_RUN_DIR="${DEVPOD_REMOTE_RUN_ROOT}/${REMOTE_RUN_ID}"
LOCAL_REMOTE_ARTIFACTS_DIR="${PROJECT_ROOT}/test-artifacts/devpod-${REMOTE_RUN_ID}"

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

shell_quote() {
    printf '%q' "$1"
}

devpod_remote_bash() {
    local script="$1"
    local escaped_script
    escaped_script="$(shell_quote "${script}")"
    devpod ssh "${WORKSPACE}" \
        --start-services=false \
        --workdir "${DEVPOD_REMOTE_WORKDIR}" \
        --command "bash -lc ${escaped_script}"
}

workspace_running() {
    local status
    status="$(devpod status "${WORKSPACE}" 2>&1 || true)"
    [[ "${status}" =~ [Rr]unning ]]
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

if [[ ! "${DEVPOD_REMOTE_E2E_TIMEOUT}" =~ ^[0-9]+$ ]] || [[ "${DEVPOD_REMOTE_E2E_TIMEOUT}" -lt 1 ]]; then
    error "Invalid DEVPOD_REMOTE_E2E_TIMEOUT='${DEVPOD_REMOTE_E2E_TIMEOUT}'"
    exit 1
fi

if [[ ! "${DEVPOD_REMOTE_POLL_INTERVAL}" =~ ^[0-9]+$ ]] || [[ "${DEVPOD_REMOTE_POLL_INTERVAL}" -lt 1 ]]; then
    error "Invalid DEVPOD_REMOTE_POLL_INTERVAL='${DEVPOD_REMOTE_POLL_INTERVAL}'"
    exit 1
fi

if [[ ! "${DEVPOD_REMOTE_POLL_FAILURE_LIMIT}" =~ ^[0-9]+$ ]] || [[ "${DEVPOD_REMOTE_POLL_FAILURE_LIMIT}" -lt 1 ]]; then
    error "Invalid DEVPOD_REMOTE_POLL_FAILURE_LIMIT='${DEVPOD_REMOTE_POLL_FAILURE_LIMIT}'"
    exit 1
fi

if [[ ! "${DEVPOD_UP_RECOVERY_TIMEOUT}" =~ ^[0-9]+$ ]] || [[ "${DEVPOD_UP_RECOVERY_TIMEOUT}" -lt 1 ]]; then
    error "Invalid DEVPOD_UP_RECOVERY_TIMEOUT='${DEVPOD_UP_RECOVERY_TIMEOUT}'"
    exit 1
fi

if [[ ! "${DEVPOD_UP_RECOVERY_INTERVAL}" =~ ^[0-9]+$ ]] || [[ "${DEVPOD_UP_RECOVERY_INTERVAL}" -lt 1 ]]; then
    error "Invalid DEVPOD_UP_RECOVERY_INTERVAL='${DEVPOD_UP_RECOVERY_INTERVAL}'"
    exit 1
fi

if [[ "${DEVPOD_ENABLE_REMOTE_TUNNELS}" != "0" && "${DEVPOD_ENABLE_REMOTE_TUNNELS}" != "1" ]]; then
    error "Invalid DEVPOD_ENABLE_REMOTE_TUNNELS='${DEVPOD_ENABLE_REMOTE_TUNNELS}'. Use: 0|1"
    exit 1
fi

recover_workspace_after_up_failure() {
    local deadline=$((SECONDS + DEVPOD_UP_RECOVERY_TIMEOUT))
    log "devpod up returned failure; checking whether workspace '${WORKSPACE}' is running before cleanup..."

    while (( SECONDS < deadline )); do
        workspace_running && return 0
        log "  Workspace not running yet; retrying status in ${DEVPOD_UP_RECOVERY_INTERVAL}s"
        sleep "${DEVPOD_UP_RECOVERY_INTERVAL}"
    done

    return 1
}

provision_workspace() {
    if devpod up "${WORKSPACE}" \
        --source "${DEVPOD_SOURCE_RESOLVED}" \
        --id "${WORKSPACE}" \
        --provider "${PROVIDER}" \
        --devcontainer-path "${DEVCONTAINER}" \
        --ide none; then
        return 0
    fi

    recover_workspace_after_up_failure
}

start_remote_e2e_run() {
    local run_dir_q
    local workdir_q
    local remote_script
    run_dir_q="$(shell_quote "${REMOTE_RUN_DIR}")"
    workdir_q="$(shell_quote "${DEVPOD_REMOTE_WORKDIR}")"

    remote_script=$(cat <<REMOTE_SCRIPT
set -euo pipefail
run_dir=${run_dir_q}
workdir=${workdir_q}
mkdir -p "\${run_dir}/artifacts"
rm -f "\${run_dir}/exit-code" "\${run_dir}/output.log" "\${run_dir}/nohup.log"
cat > "\${run_dir}/run.sh" <<'REMOTE_RUN'
#!/usr/bin/env bash
set +e
mkdir -p "\${FLOE_REMOTE_RUN_DIR}/artifacts"
{
    echo "[remote-e2e] started at \$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "[remote-e2e] workdir=\${FLOE_REMOTE_WORKDIR}"
    cd "\${FLOE_REMOTE_WORKDIR}"
    IMAGE_LOAD_METHOD=kind make test-e2e
} > "\${FLOE_REMOTE_RUN_DIR}/output.log" 2>&1
rc=\$?
cp -a "\${FLOE_REMOTE_WORKDIR}/test-artifacts/." "\${FLOE_REMOTE_RUN_DIR}/artifacts/" 2>/dev/null || true
echo "[remote-e2e] finished at \$(date -u '+%Y-%m-%dT%H:%M:%SZ') exit=\${rc}" >> "\${FLOE_REMOTE_RUN_DIR}/output.log"
echo "\${rc}" > "\${FLOE_REMOTE_RUN_DIR}/exit-code"
exit 0
REMOTE_RUN
chmod +x "\${run_dir}/run.sh"
FLOE_REMOTE_WORKDIR="\${workdir}" FLOE_REMOTE_RUN_DIR="\${run_dir}" \
    nohup bash "\${run_dir}/run.sh" > "\${run_dir}/nohup.log" 2>&1 < /dev/null &
echo \$! > "\${run_dir}/pid"
printf '%s\n' "\${run_dir}"
REMOTE_SCRIPT
)

    devpod_remote_bash "${remote_script}"
}

poll_remote_e2e_run() {
    local deadline=$((SECONDS + DEVPOD_REMOTE_E2E_TIMEOUT))
    local poll_failures=0
    local poll_output=""
    local poll_status=0
    local poll_script=""
    local poll_state=""
    local run_dir_q
    run_dir_q="$(shell_quote "${REMOTE_RUN_DIR}")"

    poll_script=$(cat <<REMOTE_SCRIPT
set -euo pipefail
run_dir=${run_dir_q}
if [[ -f "\${run_dir}/exit-code" ]]; then
    printf 'complete:%s\n' "\$(cat "\${run_dir}/exit-code")"
    exit 0
fi
if [[ -f "\${run_dir}/pid" ]] && kill -0 "\$(cat "\${run_dir}/pid")" 2>/dev/null; then
    printf 'running\n'
    exit 0
fi
printf 'lost\n'
exit 0
REMOTE_SCRIPT
)

    while (( SECONDS < deadline )); do
        set +e
        poll_output="$(devpod_remote_bash "${poll_script}" 2>&1)"
        poll_status=$?
        set -e
        poll_state="$(printf '%s\n' "${poll_output}" | grep -E '^(complete:[0-9]+|running|lost)$' | tail -1 || true)"

        if [[ -n "${poll_state}" ]]; then
            poll_failures=0
            case "${poll_state}" in
                complete:*)
                    printf '%s\n' "${poll_state#complete:}"
                    return 0
                    ;;
                running)
                    log "  Remote E2E still running (${SECONDS}s elapsed, artifacts: ${REMOTE_RUN_DIR})"
                    ;;
                lost)
                    error "Remote E2E process is no longer running and no exit-code was written"
                    return 3
                    ;;
                *)
                    error "Unexpected remote E2E poll response: ${poll_output}"
                    ;;
            esac
        elif [[ "${poll_status}" -eq 0 ]]; then
            error "Unexpected remote E2E poll response: ${poll_output}"
        else
            poll_failures=$((poll_failures + 1))
            error "Remote E2E poll failed (${poll_failures}/${DEVPOD_REMOTE_POLL_FAILURE_LIMIT}): ${poll_output}"
            if (( poll_failures >= DEVPOD_REMOTE_POLL_FAILURE_LIMIT )); then
                return 4
            fi
        fi
        sleep "${DEVPOD_REMOTE_POLL_INTERVAL}"
    done

    error "Remote E2E timed out after ${DEVPOD_REMOTE_E2E_TIMEOUT}s"
    return 2
}

fetch_remote_e2e_artifacts() {
    local run_parent
    local run_name
    local parent_q
    local name_q
    mkdir -p "${LOCAL_REMOTE_ARTIFACTS_DIR}"

    run_parent="$(dirname "${REMOTE_RUN_DIR}")"
    run_name="$(basename "${REMOTE_RUN_DIR}")"
    parent_q="$(shell_quote "${run_parent}")"
    name_q="$(shell_quote "${run_name}")"

    if devpod_remote_bash "cd ${parent_q} && tar -czf - ${name_q}" \
        | tar -xzf - -C "${LOCAL_REMOTE_ARTIFACTS_DIR}" --strip-components=1; then
        log "Remote E2E artifacts saved to ${LOCAL_REMOTE_ARTIFACTS_DIR}"
    else
        error "Failed to fetch remote E2E artifact bundle from ${REMOTE_RUN_DIR}"
    fi
}

run_remote_e2e_detached() {
    local remote_dir=""
    local exit_code=""

    log "Starting detached remote E2E run in ${REMOTE_RUN_DIR}..."
    remote_dir="$(start_remote_e2e_run)" || return 1
    log "Remote E2E started: ${remote_dir}"

    if exit_code="$(poll_remote_e2e_run)"; then
        fetch_remote_e2e_artifacts || true
        if [[ -f "${LOCAL_REMOTE_ARTIFACTS_DIR}/output.log" ]]; then
            log "--- Remote E2E output (last 30 lines) ---"
            tail -30 "${LOCAL_REMOTE_ARTIFACTS_DIR}/output.log" >&2 || true
            log "--- End remote E2E output ---"
        fi
        return "${exit_code}"
    fi

    exit_code=$?
    fetch_remote_e2e_artifacts || true
    return "${exit_code}"
}

establish_service_tunnels() {
    case "${DEVPOD_E2E_EXECUTION}" in
        remote)
            if [[ "${DEVPOD_ENABLE_REMOTE_TUNNELS}" == "1" ]]; then
                log "Establishing optional service port tunnels for remote E2E..."
                bash "${SCRIPT_DIR}/devpod-tunnels.sh" \
                    || { error "Failed to establish optional remote SSH tunnels"; exit 1; }
                log "Tunnels established"
            else
                log "Skipping service port tunnels for remote E2E (DEVPOD_ENABLE_REMOTE_TUNNELS=0)"
            fi
            ;;
        local)
            log "Establishing service port tunnels for local E2E..."
            bash "${SCRIPT_DIR}/devpod-tunnels.sh" \
                || { error "Failed to establish SSH tunnels"; exit 1; }
            log "Tunnels established"
            ;;
        *)
            error "Invalid DEVPOD_E2E_EXECUTION='${DEVPOD_E2E_EXECUTION}'. Use: remote|local"
            exit 1
            ;;
    esac
}

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
provision_workspace \
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

# ─── Step 3: Establish tunnels when required ─────────────────────────────────

log "Step 3/5: Preparing service access..."
establish_service_tunnels

# ─── Step 4: Run E2E tests ───────────────────────────────────────────────────

log "Step 4/5: Running E2E tests..."

# Run tests and capture exit code (don't let set -e kill us)
set +e
case "${DEVPOD_E2E_EXECUTION}" in
    remote)
        log "Running E2E inside DevPod workspace '${WORKSPACE}' (workdir: ${DEVPOD_REMOTE_WORKDIR})..."
        run_remote_e2e_detached
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
