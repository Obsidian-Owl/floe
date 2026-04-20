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
: "${FLOE_FLUX_GIT_URL:=https://github.com/Obsidian-Owl/floe}"
# Leave the branch unset by default so setup-cluster.sh can auto-detect the
# current checkout while still allowing explicit overrides from the environment.
: "${FLOE_FLUX_GIT_BRANCH:=}"

# Flux CD version — pinned for reproducible CI installs.
: "${FLUX_VERSION:=2.5.1}"

export FLOE_RELEASE_NAME FLOE_NAMESPACE FLOE_KIND_CLUSTER FLOE_CHART_DIR FLOE_VALUES_FILE
export FLOE_FLUX_GIT_URL FLOE_FLUX_GIT_BRANCH
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
    printf '%s-%s\n' "${FLOE_RELEASE_NAME}" "${component}"
}

# floe_render_test_job <template-path>
# Renders a single test template from the chart, with tests.enabled=true.
# template-path is relative to the chart's templates/ directory
# (e.g. "tests/job-e2e.yaml").
#
# Emits rendered YAML on stdout — caller pipes to `kubectl apply -f -`.
floe_render_test_job() {
    local template="$1"
    if [[ -z "${template}" ]]; then
        echo "floe_render_test_job: template path required" >&2
        return 2
    fi
    helm template "${FLOE_RELEASE_NAME}" "${FLOE_CHART_DIR}" \
        -f "${FLOE_VALUES_FILE}" \
        --set tests.enabled=true \
        --namespace "${FLOE_NAMESPACE}" \
        -s "templates/${template}"
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
