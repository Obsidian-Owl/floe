#!/bin/bash
# testing/ci/common.sh — shared FLOE_* env vars and helper functions.
#
# Source this from any CI test script. All identifiers flow from the Helm
# chart via helpers — no script may hardcode `floe-platform-*` strings.
#
# Usage:
#     # shellcheck source=./common.sh
#     source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
#     floe_require_cluster
#     helm_out=$(floe_render_test_job tests/job-e2e.yaml)
#     svc=$(floe_service_name polaris)
#
# Contract: this file is the single source of truth for release name,
# namespace, Kind cluster name, chart dir, and values file. Consumers
# MUST NOT redefine these.

FLOE_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLOE_PROJECT_ROOT="$(cd "${FLOE_COMMON_DIR}/../.." && pwd)"

floe_common_fail() {
    echo "ERROR: $*" >&2
    exit 1
}

FLOE_PYTHON_WAS_SET=0
if [[ -n "${FLOE_PYTHON+x}" ]]; then
    FLOE_PYTHON_WAS_SET=1
else
    FLOE_PYTHON="${FLOE_PROJECT_ROOT}/.venv/bin/python"
fi
if [[ "${FLOE_PYTHON_WAS_SET}" -eq 0 && ! -x "${FLOE_PYTHON}" ]] && command -v python >/dev/null 2>&1; then
    FLOE_PYTHON="$(command -v python)"
fi
if [[ ! -x "${FLOE_PYTHON}" ]]; then
    floe_common_fail "FLOE_PYTHON is not executable: ${FLOE_PYTHON}. Run 'uv sync' or set FLOE_PYTHON."
fi
export FLOE_PYTHON
unset FLOE_PYTHON_WAS_SET

floe_contract_emit() {
    PYTHONPATH="${FLOE_PROJECT_ROOT}/packages/floe-core/src:${PYTHONPATH:-}" \
        "${FLOE_PYTHON}" -m floe_core.contracts.emit "$@"
}

if ! FLOE_CONTRACT_DEFAULTS="$(floe_contract_emit shell-defaults)"; then
    floe_common_fail "failed to emit floe shell defaults with FLOE_PYTHON=${FLOE_PYTHON}"
fi
eval "${FLOE_CONTRACT_DEFAULTS}"
unset FLOE_CONTRACT_DEFAULTS

# Canonical identifiers. Scripts may override via environment before sourcing,
# but must not redefine after sourcing.
: "${FLOE_RELEASE_NAME:=${FLOE_DEFAULT_RELEASE_NAME}}"
: "${FLOE_NAMESPACE:=${FLOE_DEFAULT_NAMESPACE}}"
# FLOE_KIND_CLUSTER absorbs both legacy env var names (KIND_CLUSTER,
# KIND_CLUSTER_NAME). New code should use FLOE_KIND_CLUSTER only.
: "${FLOE_KIND_CLUSTER:=${KIND_CLUSTER:-${KIND_CLUSTER_NAME:-floe-test}}}"
: "${FLOE_CHART_DIR:=charts/floe-platform}"
: "${FLOE_VALUES_FILE:=charts/floe-platform/values-test.yaml}"
: "${FLOE_FLUX_FIXTURE_DIR:=testing/k8s/flux}"
: "${FLOE_FLUX_GIT_URL:=https://github.com/Obsidian-Owl/floe}"
# Leave the branch unset by default so setup-cluster.sh can auto-detect the
# current checkout while still allowing explicit overrides from the environment.
: "${FLOE_FLUX_GIT_BRANCH:=}"
# Remote repo root inside the DevPod workspace. Defaults to the devcontainer
# workspaceFolder, but stays overrideable for non-standard layouts.
: "${DEVPOD_REMOTE_WORKDIR:=/workspace}"

# Flux CD version — pinned for reproducible CI installs.
: "${FLUX_VERSION:=2.5.1}"

export FLOE_RELEASE_NAME FLOE_NAMESPACE FLOE_KIND_CLUSTER FLOE_CHART_DIR FLOE_VALUES_FILE
export FLOE_FLUX_FIXTURE_DIR FLOE_FLUX_GIT_URL FLOE_FLUX_GIT_BRANCH DEVPOD_REMOTE_WORKDIR
export FLUX_VERSION

# floe_service_name <component>
# Returns the K8s service/resource name for a platform component, derived
# from the release name. Example: floe_service_name polaris -> floe-platform-polaris
floe_service_name() {
    local component="$1"
    if [[ -z "${component}" ]]; then
        echo "floe_service_name: component argument required" >&2
        return 2
    fi
    floe_contract_emit service-name --release-name "${FLOE_RELEASE_NAME}" "${component}"
}

# floe_render_test_job <template-path>
# Renders a single test template from the chart, with tests.enabled=true.
# template-path is relative to the chart's templates/ directory
# (e.g. "tests/job-e2e.yaml").
#
# Emits rendered YAML on stdout — caller pipes to `kubectl apply -f -`.
floe_ensure_chart_dependencies() {
    local dependency_list=""
    local dep_name=""
    local dep_version=""
    local dep_repo=""
    local dep_status=""

    dependency_list=$(helm dependency list "${FLOE_CHART_DIR}") || return 1
    if ! printf '%s\n' "${dependency_list}" | tail -n +2 | grep -Eq $'\tmissing[[:space:]]*$'; then
        return 0
    fi

    echo "Resolving Helm chart dependencies for ${FLOE_CHART_DIR}..." >&2
    while IFS=$'\t' read -r dep_name dep_version dep_repo dep_status; do
        dep_name="${dep_name%%[[:space:]]*}"
        dep_repo="${dep_repo%%[[:space:]]*}"
        dep_status="${dep_status%%[[:space:]]*}"

        if [[ -z "${dep_name}" || "${dep_status}" != "missing" || -z "${dep_repo}" ]]; then
            continue
        fi
        helm repo add --force-update "floe-${dep_name}" "${dep_repo}" >/dev/null
    done < <(printf '%s\n' "${dependency_list}" | tail -n +2)

    helm dependency build "${FLOE_CHART_DIR}" >/dev/null
}

floe_render_test_job() {
    local template="$1"
    if [[ -z "${template}" ]]; then
        echo "floe_render_test_job: template path required" >&2
        return 2
    fi
    floe_ensure_chart_dependencies || return 1
    helm template "${FLOE_RELEASE_NAME}" "${FLOE_CHART_DIR}" \
        -f "${FLOE_VALUES_FILE}" \
        --set tests.enabled=true \
        --namespace "${FLOE_NAMESPACE}" \
        -s "templates/${template}"
}

# floe_test_artifacts_pvc_name
# Returns the PVC name for chart-managed test artifacts. Reads the real chart
# template instead of hardcoding `test-artifacts` in runner scripts.
floe_test_artifacts_pvc_name() {
    local rendered_pvc
    rendered_pvc="$(mktemp "${TMPDIR:-/tmp}/floe-test-pvc-name.XXXXXX.yaml")"

    floe_render_test_job "tests/pvc-artifacts.yaml" > "${rendered_pvc}" \
        || { rm -f "${rendered_pvc}"; return 1; }
    if [[ ! -s "${rendered_pvc}" ]]; then
        rm -f "${rendered_pvc}"
        return 1
    fi

    kubectl create --dry-run=client -f "${rendered_pvc}" -o jsonpath='{.metadata.name}' \
        || { rm -f "${rendered_pvc}"; return 1; }
    rm -f "${rendered_pvc}"
}

# floe_ensure_test_artifacts_pvc
# values-test.yaml keeps tests.enabled=false during normal platform installs,
# so the chart-owned artifacts PVC is absent on a fresh cluster. Create the
# real PVC from the chart template and backfill the Helm ownership metadata
# Helm later validates during upgrade/import checks.
floe_ensure_test_artifacts_pvc() {
    local rendered_pvc
    rendered_pvc="$(mktemp "${TMPDIR:-/tmp}/floe-test-pvc.XXXXXX.yaml")"

    floe_render_test_job "tests/pvc-artifacts.yaml" > "${rendered_pvc}" \
        || { rm -f "${rendered_pvc}"; return 1; }
    if [[ ! -s "${rendered_pvc}" ]]; then
        rm -f "${rendered_pvc}"
        return 0
    fi

    kubectl apply -f "${rendered_pvc}" >/dev/null \
        || { rm -f "${rendered_pvc}"; return 1; }
    kubectl annotate -f "${rendered_pvc}" \
        meta.helm.sh/release-name="${FLOE_RELEASE_NAME}" \
        meta.helm.sh/release-namespace="${FLOE_NAMESPACE}" \
        --overwrite >/dev/null \
        || { rm -f "${rendered_pvc}"; return 1; }
    kubectl label -f "${rendered_pvc}" \
        app.kubernetes.io/managed-by=Helm \
        --overwrite >/dev/null \
        || { rm -f "${rendered_pvc}"; return 1; }

    rm -f "${rendered_pvc}"
}

# floe_require_cluster
# Fails fast if the Kind cluster is not reachable. Writes a single
# actionable message to stderr and exits 1 on failure.
floe_require_cluster() {
    if ! command -v kubectl >/dev/null 2>&1; then
        echo "ERROR: kubectl not found on PATH" >&2
        return 1
    fi
    if ! kubectl cluster-info >/dev/null 2>&1; then
        echo "ERROR: cannot reach Kubernetes cluster '${FLOE_KIND_CLUSTER}'." >&2
        echo "Run 'make kind-up' or set KUBECONFIG to a running cluster." >&2
        return 1
    fi
    if ! kubectl get namespace "${FLOE_NAMESPACE}" >/dev/null 2>&1; then
        echo "ERROR: namespace '${FLOE_NAMESPACE}' does not exist." >&2
        echo "Deploy the platform first: make helm-install" >&2
        return 1
    fi
}
