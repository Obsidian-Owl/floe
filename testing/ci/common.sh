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

# Canonical identifiers. Scripts may override via environment before sourcing,
# but must not redefine after sourcing.
: "${FLOE_RELEASE_NAME:=floe-platform}"
: "${FLOE_NAMESPACE:=floe-test}"
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
_FLOE_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_FLOE_REPO_ROOT="$(cd "${_FLOE_COMMON_DIR}/../.." && pwd)"
: "${FLOE_MANIFEST_PATH:=${_FLOE_REPO_ROOT}/demo/manifest.yaml}"

# Flux CD version — pinned for reproducible CI installs.
: "${FLUX_VERSION:=2.5.1}"

if [[ -z "${FLOE_DEMO_IMAGE_REPOSITORY:-}" || -z "${FLOE_DEMO_IMAGE_TAG:-}" || -z "${FLOE_DEMO_IMAGE:-}" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        if [[ -z "${FLOE_DEMO_IMAGE_REPOSITORY:-}" ]]; then
            FLOE_DEMO_IMAGE_REPOSITORY="$(
                python3 "${_FLOE_COMMON_DIR}/resolve-demo-image-ref.py" --field repository
            )"
        fi
        if [[ -z "${FLOE_DEMO_IMAGE_TAG:-}" ]]; then
            FLOE_DEMO_IMAGE_TAG="$(
                python3 "${_FLOE_COMMON_DIR}/resolve-demo-image-ref.py" --field tag
            )"
        fi
        if [[ -z "${FLOE_DEMO_IMAGE:-}" ]]; then
            FLOE_DEMO_IMAGE="$(
                python3 "${_FLOE_COMMON_DIR}/resolve-demo-image-ref.py" --field ref
            )"
        fi
    fi
fi
: "${FLOE_DEMO_IMAGE_REPOSITORY:=floe-dagster-demo}"
: "${FLOE_DEMO_IMAGE_TAG:=local}"
: "${FLOE_DEMO_IMAGE:=${FLOE_DEMO_IMAGE_REPOSITORY}:${FLOE_DEMO_IMAGE_TAG}}"

export FLOE_RELEASE_NAME FLOE_NAMESPACE FLOE_KIND_CLUSTER FLOE_CHART_DIR FLOE_VALUES_FILE
export FLOE_FLUX_FIXTURE_DIR FLOE_FLUX_GIT_URL FLOE_FLUX_GIT_BRANCH DEVPOD_REMOTE_WORKDIR
export FLOE_MANIFEST_PATH FLOE_DEMO_IMAGE_REPOSITORY FLOE_DEMO_IMAGE_TAG FLOE_DEMO_IMAGE
export FLUX_VERSION

# floe_normalize_image_ref <image>
# Normalizes a Docker image reference to the form containerd stores in Kind.
floe_normalize_image_ref() {
    local image="$1"
    if [[ -z "${image}" ]]; then
        echo "floe_normalize_image_ref: image argument required" >&2
        return 2
    fi
    if [[ "${image}" == */* ]]; then
        printf '%s\n' "${image}"
        return 0
    fi
    printf 'docker.io/library/%s\n' "${image}"
}

# floe_kind_control_plane_name [cluster]
# Returns the Docker container name for a Kind control-plane node.
floe_kind_control_plane_name() {
    local cluster="${1:-${FLOE_KIND_CLUSTER}}"
    printf '%s-control-plane\n' "${cluster}"
}

# floe_kind_evict_image <image> [cluster]
# Removes an image ref from the Kind node's containerd store so a subsequent
# `kind load docker-image` cannot silently reuse a stale mutable tag.
floe_kind_evict_image() {
    local image="$1"
    local cluster="${2:-${FLOE_KIND_CLUSTER}}"
    local control_plane=""
    local image_ref=""

    if [[ -z "${image}" ]]; then
        echo "floe_kind_evict_image: image argument required" >&2
        return 2
    fi
    if ! command -v docker >/dev/null 2>&1; then
        return 0
    fi

    control_plane="$(floe_kind_control_plane_name "${cluster}")"
    if ! docker inspect "${control_plane}" >/dev/null 2>&1; then
        return 0
    fi

    image_ref="$(floe_normalize_image_ref "${image}")"
    docker exec "${control_plane}" ctr -n k8s.io images rm "${image_ref}" >/dev/null 2>&1 || true
}

# floe_service_name <component>
# Returns the K8s service/resource name for a platform component, derived
# from the release name. Example: floe_service_name polaris -> floe-platform-polaris
floe_service_name() {
    local component="$1"
    if [[ -z "${component}" ]]; then
        echo "floe_service_name: component argument required" >&2
        return 2
    fi
    printf '%s-%s\n' "${FLOE_RELEASE_NAME}" "${component}"
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

# floe_export_minio_credentials_from_cluster [namespace] [secret-name]
# Exports MINIO_USER and MINIO_PASS from the live cluster secret when the
# caller already knows how to reach the cluster but has not pre-exported the
# credentials.
floe_export_minio_credentials_from_cluster() {
    local namespace="${1:-${FLOE_NAMESPACE}}"
    local secret_name="${2:-$(floe_service_name minio)}"
    local user=""
    local password=""

    if [[ -n "${MINIO_USER:-}" && -n "${MINIO_PASS:-}" ]]; then
        return 0
    fi
    if ! command -v kubectl >/dev/null 2>&1; then
        return 1
    fi

    user=$(kubectl get secret -n "${namespace}" "${secret_name}" \
        -o go-template='{{index .data "root-user" | base64decode}}' 2>/dev/null || true)
    password=$(kubectl get secret -n "${namespace}" "${secret_name}" \
        -o go-template='{{index .data "root-password" | base64decode}}' 2>/dev/null || true)

    if [[ -n "${user}" && -z "${MINIO_USER:-}" ]]; then
        export MINIO_USER="${user}"
    fi
    if [[ -n "${password}" && -z "${MINIO_PASS:-}" ]]; then
        export MINIO_PASS="${password}"
    fi

    [[ -n "${MINIO_USER:-}" && -n "${MINIO_PASS:-}" ]]
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
