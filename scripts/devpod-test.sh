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
#   DEVPOD_REMOTE_E2E_MAKE_TARGET Make target to run after Kind bootstrap
#                        (default: test-e2e). Use test-e2e-full for release
#                        validation with destructive tests.
#   DEVPOD_REMOTE_E2E_TIMEOUT Remote E2E timeout in seconds (default: 7200).
#   DEVPOD_REMOTE_POLL_INTERVAL Remote E2E polling interval in seconds
#                        (default: 20).
#   DEVPOD_REMOTE_POLL_FAILURE_LIMIT Consecutive DevPod poll failures tolerated
#                        before aborting (default: 30).
#   DEVPOD_REMOTE_FLUX_SETTLEMENT_TIMEOUT Seconds to wait for Flux source,
#                        HelmRelease, and rollout settlement before E2E starts
#                        (default: 900).
#   DEVPOD_REMOTE_FLUX_SETTLEMENT_INTERVAL Seconds between Flux settlement polls
#                        (default: 10).
#   DEVPOD_REMOTE_FLUX_GITREPOSITORY Flux GitRepository name to inspect
#                        (default: floe).
#   DEVPOD_REMOTE_FLUX_SOURCE_NAMESPACE Namespace containing the GitRepository
#                        (default: flux-system).
#   DEVPOD_REMOTE_FLUX_HELMRELEASES Space-separated HelmReleases to wait for
#                        (default: "floe-platform floe-jobs-test").
#   DEVPOD_REMOTE_FLUX_DEPLOYMENTS Space-separated Deployments to wait for
#                        after HelmReleases settle.
#   DEVPOD_REMOTE_FLUX_STATEFULSETS Space-separated StatefulSets to wait for
#                        after HelmReleases settle.
#   DEVPOD_UP_RECOVERY_TIMEOUT Seconds to poll workspace status after a
#                        transport-level `devpod up` failure (default: 600).
#   DEVPOD_ENABLE_REMOTE_TUNNELS Set to 1 to establish host service tunnels
#                        before remote E2E. Default 0 because remote tests run
#                        inside the DevPod workspace network.
#   DEVPOD_KUBECONFIG   Local kubeconfig path for local E2E fallback
#                        (default: ~/.kube/devpod-${DEVPOD_WORKSPACE}.config)

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
KUBECONFIG_PATH="${DEVPOD_KUBECONFIG:-${HOME}/.kube/devpod-${WORKSPACE}.config}"
HEALTH_TIMEOUT="${DEVPOD_HEALTH_TIMEOUT:-120}"
NAMESPACE="${TEST_NAMESPACE:-floe-test}"
PROVIDER="${DEVPOD_PROVIDER:-hetzner}"
DEVPOD_E2E_EXECUTION="${DEVPOD_E2E_EXECUTION:-remote}"
DEVPOD_REMOTE_WORKDIR="${DEVPOD_REMOTE_WORKDIR:-/workspace}"
DEVPOD_REMOTE_E2E_MAKE_TARGET="${DEVPOD_REMOTE_E2E_MAKE_TARGET:-test-e2e}"
DEVPOD_REMOTE_RUN_ROOT="${DEVPOD_REMOTE_RUN_ROOT:-/tmp/floe-devpod-e2e}"
DEVPOD_REMOTE_E2E_TIMEOUT="${DEVPOD_REMOTE_E2E_TIMEOUT:-7200}"
DEVPOD_REMOTE_POLL_INTERVAL="${DEVPOD_REMOTE_POLL_INTERVAL:-20}"
DEVPOD_REMOTE_POLL_FAILURE_LIMIT="${DEVPOD_REMOTE_POLL_FAILURE_LIMIT:-30}"
DEVPOD_REMOTE_FLUX_SETTLEMENT_TIMEOUT="${DEVPOD_REMOTE_FLUX_SETTLEMENT_TIMEOUT:-900}"
DEVPOD_REMOTE_FLUX_SETTLEMENT_INTERVAL="${DEVPOD_REMOTE_FLUX_SETTLEMENT_INTERVAL:-10}"
DEVPOD_REMOTE_FLUX_GITREPOSITORY="${DEVPOD_REMOTE_FLUX_GITREPOSITORY:-floe}"
DEVPOD_REMOTE_FLUX_SOURCE_NAMESPACE="${DEVPOD_REMOTE_FLUX_SOURCE_NAMESPACE:-flux-system}"
DEVPOD_REMOTE_FLUX_HELMRELEASES="${DEVPOD_REMOTE_FLUX_HELMRELEASES:-floe-platform floe-jobs-test}"
DEVPOD_REMOTE_FLUX_DEPLOYMENTS="${DEVPOD_REMOTE_FLUX_DEPLOYMENTS:-floe-platform-dagster-webserver floe-platform-polaris floe-platform-minio floe-platform-jaeger floe-platform-marquez floe-platform-otel}"
DEVPOD_REMOTE_FLUX_STATEFULSETS="${DEVPOD_REMOTE_FLUX_STATEFULSETS:-floe-platform-postgresql}"
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
    if printf '%s\n' "${status}" | grep -Eiq 'not[[:space:]-]+running|stopped|failed|error'; then
        return 1
    fi
    printf '%s\n' "${status}" | grep -Eiq '(^|[^[:alpha:]])running([^[:alpha:]]|$)'
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

if [[ ! "${DEVPOD_REMOTE_FLUX_SETTLEMENT_TIMEOUT}" =~ ^[0-9]+$ ]] || [[ "${DEVPOD_REMOTE_FLUX_SETTLEMENT_TIMEOUT}" -lt 1 ]]; then
    error "Invalid DEVPOD_REMOTE_FLUX_SETTLEMENT_TIMEOUT='${DEVPOD_REMOTE_FLUX_SETTLEMENT_TIMEOUT}'"
    exit 1
fi

if [[ ! "${DEVPOD_REMOTE_FLUX_SETTLEMENT_INTERVAL}" =~ ^[0-9]+$ ]] || [[ "${DEVPOD_REMOTE_FLUX_SETTLEMENT_INTERVAL}" -lt 1 ]]; then
    error "Invalid DEVPOD_REMOTE_FLUX_SETTLEMENT_INTERVAL='${DEVPOD_REMOTE_FLUX_SETTLEMENT_INTERVAL}'"
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

if [[ "${DEVPOD_REMOTE_RUN_ROOT}" != /* ]]; then
    error "Invalid DEVPOD_REMOTE_RUN_ROOT='${DEVPOD_REMOTE_RUN_ROOT}': value must be an absolute path"
    exit 1
fi

if [[ "${DEVPOD_REMOTE_RUN_ROOT}" == *"/../"* || "${DEVPOD_REMOTE_RUN_ROOT}" == */.. ]]; then
    error "Invalid DEVPOD_REMOTE_RUN_ROOT='${DEVPOD_REMOTE_RUN_ROOT}': parent traversal is not allowed"
    exit 1
fi

if [[ "${DEVPOD_ENABLE_REMOTE_TUNNELS}" != "0" && "${DEVPOD_ENABLE_REMOTE_TUNNELS}" != "1" ]]; then
    error "Invalid DEVPOD_ENABLE_REMOTE_TUNNELS='${DEVPOD_ENABLE_REMOTE_TUNNELS}'. Use: 0|1"
    exit 1
fi

if [[ -z "${DEVPOD_REMOTE_E2E_MAKE_TARGET}" ]]; then
    error "Invalid DEVPOD_REMOTE_E2E_MAKE_TARGET: value cannot be empty"
    exit 1
fi

for kube_name in "${DEVPOD_REMOTE_FLUX_GITREPOSITORY}" "${DEVPOD_REMOTE_FLUX_SOURCE_NAMESPACE}"; do
    if [[ ! "${kube_name}" =~ ^[a-zA-Z0-9._-]+$ ]]; then
        error "Invalid Flux resource name '${kube_name}'"
        exit 1
    fi
done

for kube_name_list in \
    "${DEVPOD_REMOTE_FLUX_HELMRELEASES}" \
    "${DEVPOD_REMOTE_FLUX_DEPLOYMENTS}" \
    "${DEVPOD_REMOTE_FLUX_STATEFULSETS}"; do
    if [[ ! "${kube_name_list}" =~ ^[a-zA-Z0-9._\ -]+$ ]]; then
        error "Invalid Flux resource list '${kube_name_list}'"
        exit 1
    fi
done

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
    local workspace_env_args=()
    if [[ "${DEVPOD_E2E_EXECUTION}" == "remote" ]]; then
        workspace_env_args=(--workspace-env FLOE_DEVPOD_SKIP_POSTSTART_SETUP=1)
    fi

    if devpod up "${WORKSPACE}" \
        --source "${DEVPOD_SOURCE_RESOLVED}" \
        --id "${WORKSPACE}" \
        --provider "${PROVIDER}" \
        --devcontainer-path "${DEVCONTAINER}" \
        "${workspace_env_args[@]}" \
        --ide none; then
        return 0
    fi

    recover_workspace_after_up_failure
}

start_remote_e2e_run() {
    local run_dir_q
    local workdir_q
    local make_target_q
    local flux_settlement_timeout_q
    local flux_settlement_interval_q
    local flux_gitrepository_q
    local flux_source_namespace_q
    local flux_helmreleases_q
    local flux_deployments_q
    local flux_statefulsets_q
    local remote_script
    local start_output=""
    local start_status=0
    local remote_dir=""
    run_dir_q="$(shell_quote "${REMOTE_RUN_DIR}")"
    workdir_q="$(shell_quote "${DEVPOD_REMOTE_WORKDIR}")"
    make_target_q="$(shell_quote "${DEVPOD_REMOTE_E2E_MAKE_TARGET}")"
    flux_settlement_timeout_q="$(shell_quote "${DEVPOD_REMOTE_FLUX_SETTLEMENT_TIMEOUT}")"
    flux_settlement_interval_q="$(shell_quote "${DEVPOD_REMOTE_FLUX_SETTLEMENT_INTERVAL}")"
    flux_gitrepository_q="$(shell_quote "${DEVPOD_REMOTE_FLUX_GITREPOSITORY}")"
    flux_source_namespace_q="$(shell_quote "${DEVPOD_REMOTE_FLUX_SOURCE_NAMESPACE}")"
    flux_helmreleases_q="$(shell_quote "${DEVPOD_REMOTE_FLUX_HELMRELEASES}")"
    flux_deployments_q="$(shell_quote "${DEVPOD_REMOTE_FLUX_DEPLOYMENTS}")"
    flux_statefulsets_q="$(shell_quote "${DEVPOD_REMOTE_FLUX_STATEFULSETS}")"

    remote_script=$(cat <<REMOTE_SCRIPT
set -euo pipefail
run_dir=${run_dir_q}
workdir=${workdir_q}
make_target=${make_target_q}
mkdir -p "\${run_dir}/artifacts"
rm -f "\${run_dir}/exit-code" "\${run_dir}/output.log" "\${run_dir}/nohup.log"
cat > "\${run_dir}/run.sh" <<'REMOTE_RUN'
#!/usr/bin/env bash
set +e
mkdir -p "\${FLOE_REMOTE_RUN_DIR}/artifacts"
resolve_flux_ref_commit() {
    local ref_type="\${1:?ref type required}"
    local ref_name="\${2:?ref name required}"
    local local_ref=""
    local remote_ref=""

    case "\${ref_type}" in
        branch)
            local_ref="refs/remotes/origin/\${ref_name}^{commit}"
            remote_ref="refs/heads/\${ref_name}"
            ;;
        tag)
            local_ref="refs/tags/\${ref_name}^{commit}"
            remote_ref="refs/tags/\${ref_name}"
            ;;
        *)
            return 0
            ;;
    esac

    git rev-parse --verify --quiet "\${local_ref}" 2>/dev/null && return 0
    git ls-remote --exit-code origin "\${remote_ref}" 2>/dev/null | awk 'NR == 1 { print \$1; exit }'
}

resolve_flux_expected_revision() {
    local source_namespace="\${FLOE_REMOTE_FLUX_SOURCE_NAMESPACE}"
    local gitrepository="\${FLOE_REMOTE_FLUX_GITREPOSITORY}"
    local state=""
    local source_branch=""
    local source_tag=""
    local source_commit=""
    local source_semver=""

    state="\$(kubectl get gitrepository "\${gitrepository}" -n "\${source_namespace}" -o 'jsonpath={.spec.ref.branch}{"\t"}{.spec.ref.tag}{"\t"}{.spec.ref.commit}{"\t"}{.spec.ref.semver}' 2>/dev/null || true)"
    IFS=\$'\t' read -r source_branch source_tag source_commit source_semver <<< "\${state}"

    if [[ -n "\${source_commit}" ]]; then
        printf '%s\n' "\${source_commit}"
        return 0
    fi
    if [[ -n "\${source_branch}" ]]; then
        resolve_flux_ref_commit branch "\${source_branch}"
        return 0
    fi
    if [[ -n "\${source_tag}" ]]; then
        resolve_flux_ref_commit tag "\${source_tag}"
        return 0
    fi
    if [[ -n "\${source_semver}" ]]; then
        echo "[remote-e2e] GitRepository uses semver \${source_semver}; relying on Flux readiness for source settlement" >&2
        return 0
    fi

    git rev-parse --verify --quiet "HEAD^{commit}" 2>/dev/null || true
}

wait_for_rollout_with_remaining_budget() {
    local resource="\${1:?resource required}"
    local namespace="\${2:?namespace required}"
    local deadline="\${3:?deadline required}"
    local remaining
    remaining=\$((deadline - SECONDS))

    if (( remaining < 1 )); then
        echo "[remote-e2e] ERROR: settlement budget exhausted before \${resource} rollout" >&2
        return 1
    fi

    kubectl rollout status "\${resource}" -n "\${namespace}" --timeout="\${remaining}s"
}

wait_for_flux_settlement() {
    local namespace="\${TEST_NAMESPACE:-floe-test}"
    local source_namespace="\${FLOE_REMOTE_FLUX_SOURCE_NAMESPACE}"
    local gitrepository="\${FLOE_REMOTE_FLUX_GITREPOSITORY}"
    local helmreleases="\${FLOE_REMOTE_FLUX_HELMRELEASES}"
    local deployments="\${FLOE_REMOTE_FLUX_DEPLOYMENTS}"
    local statefulsets="\${FLOE_REMOTE_FLUX_STATEFULSETS}"
    local timeout="\${FLOE_REMOTE_FLUX_SETTLEMENT_TIMEOUT}"
    local interval="\${FLOE_REMOTE_FLUX_SETTLEMENT_INTERVAL}"
    local expected_revision=""
    local source_revision=""
    local deadline

    if ! kubectl get namespace "\${source_namespace}" >/dev/null 2>&1; then
        echo "[remote-e2e] Flux namespace \${source_namespace} not found; skipping settlement gate"
        return 0
    fi

    expected_revision="\$(resolve_flux_expected_revision)"
    deadline=\$((SECONDS + timeout))
    echo "[remote-e2e] waiting for Flux settlement in namespace \${namespace} (expected revision: \${expected_revision:-unknown})"

    while (( SECONDS < deadline )); do
        local source_ready=0
        local helm_ready=1
        source_revision="\$(kubectl get gitrepository "\${gitrepository}" -n "\${source_namespace}" -o "jsonpath={.status.artifact.revision}" 2>/dev/null || true)"
        if [[ -z "\${expected_revision}" || "\${source_revision}" == *"\${expected_revision}"* ]]; then
            source_ready=1
        fi

        for helmrelease in \${helmreleases}; do
            local state=""
            local observed=""
            local generation=""
            local ready=""
            state="\$(kubectl get helmrelease "\${helmrelease}" -n "\${namespace}" -o 'jsonpath={.status.observedGeneration}{"\t"}{.metadata.generation}{"\t"}{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
            IFS=\$'\t' read -r observed generation ready <<< "\${state}"
            if [[ -z "\${observed}" || "\${observed}" != "\${generation}" || "\${ready}" != "True" ]]; then
                helm_ready=0
            fi
        done

        if [[ "\${source_ready}" -eq 1 && "\${helm_ready}" -eq 1 ]]; then
            echo "[remote-e2e] Flux source and HelmReleases settled"
            for deployment in \${deployments}; do
                wait_for_rollout_with_remaining_budget "deployment/\${deployment}" "\${namespace}" "\${deadline}" || return 1
            done
            for statefulset in \${statefulsets}; do
                wait_for_rollout_with_remaining_budget "statefulset/\${statefulset}" "\${namespace}" "\${deadline}" || return 1
            done
            return 0
        fi

        echo "[remote-e2e] Flux not settled yet: source=\${source_revision:-missing}; retrying in \${interval}s"
        sleep "\${interval}"
    done

    echo "[remote-e2e] ERROR: Flux did not settle within \${timeout}s" >&2
    kubectl get gitrepository "\${gitrepository}" -n "\${source_namespace}" -o wide 2>/dev/null >&2 || true
    kubectl get helmrelease -n "\${namespace}" 2>/dev/null >&2 || true
    return 1
}

{
    echo "[remote-e2e] started at \$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "[remote-e2e] workdir=\${FLOE_REMOTE_WORKDIR}"
    cd "\${FLOE_REMOTE_WORKDIR}"
    SKIP_MONITORING=\${SKIP_MONITORING:-true} make kind-up
    wait_for_flux_settlement
    flux_rc=\$?
    if [[ "\${flux_rc}" -ne 0 ]]; then
        echo "[remote-e2e] Flux settlement failed exit=\${flux_rc}"
        (exit "\${flux_rc}")
    else
        IMAGE_LOAD_METHOD=kind make "\${FLOE_REMOTE_E2E_MAKE_TARGET}"
    fi
} > "\${FLOE_REMOTE_RUN_DIR}/output.log" 2>&1
rc=\$?
cp -a "\${FLOE_REMOTE_WORKDIR}/test-artifacts/." "\${FLOE_REMOTE_RUN_DIR}/artifacts/" 2>/dev/null || true
echo "[remote-e2e] finished at \$(date -u '+%Y-%m-%dT%H:%M:%SZ') exit=\${rc}" >> "\${FLOE_REMOTE_RUN_DIR}/output.log"
echo "\${rc}" > "\${FLOE_REMOTE_RUN_DIR}/exit-code"
exit 0
REMOTE_RUN
chmod +x "\${run_dir}/run.sh"
FLOE_REMOTE_WORKDIR="\${workdir}" FLOE_REMOTE_RUN_DIR="\${run_dir}" FLOE_REMOTE_E2E_MAKE_TARGET="\${make_target}" \
    FLOE_REMOTE_FLUX_SETTLEMENT_TIMEOUT=${flux_settlement_timeout_q} \
    FLOE_REMOTE_FLUX_SETTLEMENT_INTERVAL=${flux_settlement_interval_q} \
    FLOE_REMOTE_FLUX_GITREPOSITORY=${flux_gitrepository_q} \
    FLOE_REMOTE_FLUX_SOURCE_NAMESPACE=${flux_source_namespace_q} \
    FLOE_REMOTE_FLUX_HELMRELEASES=${flux_helmreleases_q} \
    FLOE_REMOTE_FLUX_DEPLOYMENTS=${flux_deployments_q} \
    FLOE_REMOTE_FLUX_STATEFULSETS=${flux_statefulsets_q} \
    nohup bash "\${run_dir}/run.sh" > "\${run_dir}/nohup.log" 2>&1 < /dev/null &
echo \$! > "\${run_dir}/pid"
printf '%s\n' "\${run_dir}"
REMOTE_SCRIPT
)

    set +e
    start_output="$(devpod_remote_bash "${remote_script}" 2>&1)"
    start_status=$?
    set -e

    remote_dir="$(printf '%s\n' "${start_output}" | grep -Fx "${REMOTE_RUN_DIR}" | tail -1 || true)"
    if [[ -n "${remote_dir}" ]]; then
        if [[ "${start_status}" -ne 0 ]]; then
            error "DevPod SSH reported failure after remote E2E start; continuing with detached run: ${start_output}"
        fi
        printf '%s\n' "${remote_dir}"
        return 0
    fi

    if [[ "${start_status}" -eq 0 ]]; then
        printf '%s\n' "${start_output}"
        return 0
    fi

    printf '%s\n' "${start_output}" >&2
    return "${start_status}"
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
pid=""
if [[ -f "\${run_dir}/exit-code" ]]; then
    printf 'complete:%s\n' "\$(cat "\${run_dir}/exit-code")"
    exit 0
fi
if [[ -f "\${run_dir}/pid" ]]; then
    pid=\$(cat "\${run_dir}/pid")
fi
if [[ "\${pid}" =~ ^[0-9]+$ ]] && kill -0 "\${pid}" 2>/dev/null; then
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
        return 1
    fi
}

run_remote_e2e_detached() {
    local remote_dir=""
    local exit_code=""
    local poll_status=0

    log "Starting detached remote E2E run in ${REMOTE_RUN_DIR}..."
    remote_dir="$(start_remote_e2e_run)" || return 1
    log "Remote E2E started: ${remote_dir}"

    exit_code="$(poll_remote_e2e_run)"
    poll_status=$?
    if [[ "${poll_status}" -eq 0 ]]; then
        if ! fetch_remote_e2e_artifacts; then
            return 2  # poll OK but evidence artifacts missing
        fi
        if [[ -f "${LOCAL_REMOTE_ARTIFACTS_DIR}/output.log" ]]; then
            log "--- Remote E2E output (last 30 lines) ---"
            tail -30 "${LOCAL_REMOTE_ARTIFACTS_DIR}/output.log" >&2 || true
            log "--- End remote E2E output ---"
        fi
        return "${exit_code}"
    fi

    fetch_remote_e2e_artifacts || true
    return "${poll_status}"
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

if [[ "${DEVPOD_E2E_EXECUTION}" == "remote" ]]; then
    log "Remote E2E owns Kind bootstrap; skipping host kubeconfig health gate"
else
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
exit "${TEST_EXIT_CODE}"
