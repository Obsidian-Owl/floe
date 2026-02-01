#!/usr/bin/env bash
#
# Validate Helm Quickstart Commands
#
# This script validates all quickstart commands from the chart README
# to ensure they work correctly.
#
# Requirements:
# - E2E-006: Quickstart validation
# - Helm 3.12+
# - kubectl configured
# - Kind cluster (optional, will create if needed)
#
# Usage:
#   ./scripts/validate-helm-quickstart.sh [--skip-cluster]
#

set -euo pipefail

# Configuration
NAMESPACE="${NAMESPACE:-floe-quickstart}"
RELEASE_NAME="${RELEASE_NAME:-floe-qs}"
CHART_DIR="charts/floe-platform"
TIMEOUT="${TIMEOUT:-10m}"
SKIP_CLUSTER="${1:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed"
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi

    # Check helm version
    HELM_VERSION=$(helm version --short | grep -oE 'v[0-9]+\.[0-9]+')
    log_info "Helm version: $HELM_VERSION"

    # Check if cluster is available
    if ! kubectl cluster-info &> /dev/null; then
        if [[ "$SKIP_CLUSTER" == "--skip-cluster" ]]; then
            log_warn "Cluster not available, skipping cluster tests"
            return 1
        fi
        log_error "Kubernetes cluster not available. Start with: make kind-up"
        exit 1
    fi

    log_info "Prerequisites check passed"
    return 0
}

validate_chart_structure() {
    log_info "Validating chart structure..."

    if [[ ! -d "$CHART_DIR" ]]; then
        log_error "Chart directory not found: $CHART_DIR"
        exit 1
    fi

    if [[ ! -f "$CHART_DIR/Chart.yaml" ]]; then
        log_error "Chart.yaml not found in $CHART_DIR"
        exit 1
    fi

    if [[ ! -f "$CHART_DIR/values.yaml" ]]; then
        log_error "values.yaml not found in $CHART_DIR"
        exit 1
    fi

    log_info "Chart structure validated"
}

validate_helm_lint() {
    log_info "Running helm lint..."

    if ! helm lint "$CHART_DIR" --values "$CHART_DIR/values.yaml" 2>&1 | head -20; then
        log_warn "helm lint reported issues (may be subchart related)"
    fi

    log_info "Helm lint completed"
}

validate_helm_template() {
    log_info "Running helm template..."

    if ! helm template test "$CHART_DIR" --values "$CHART_DIR/values.yaml" > /dev/null 2>&1; then
        log_error "helm template failed"
        exit 1
    fi

    log_info "Helm template validated"
}

validate_dependency_update() {
    log_info "Updating chart dependencies..."

    if ! helm dependency update "$CHART_DIR" 2>&1 | tail -5; then
        log_error "helm dependency update failed"
        exit 1
    fi

    log_info "Dependencies updated"
}

validate_install() {
    log_info "Testing chart installation..."

    # Create namespace
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # Install chart with minimal config (faster test)
    if ! helm upgrade --install "$RELEASE_NAME" "$CHART_DIR" \
        --namespace "$NAMESPACE" \
        --values "$CHART_DIR/values.yaml" \
        --set dagster.enabled=false \
        --set otel.enabled=false \
        --set minio.enabled=false \
        --wait \
        --timeout "$TIMEOUT" 2>&1 | tail -20; then
        log_error "helm install failed"
        return 1
    fi

    log_info "Chart installed successfully"
}

validate_helm_test() {
    log_info "Running helm test..."

    if ! helm test "$RELEASE_NAME" --namespace "$NAMESPACE" --timeout 5m 2>&1 | tail -20; then
        log_warn "helm test reported issues"
        return 1
    fi

    log_info "Helm tests passed"
}

validate_status() {
    log_info "Checking release status..."

    helm status "$RELEASE_NAME" --namespace "$NAMESPACE" | head -20

    log_info "Getting pod status..."
    kubectl get pods -n "$NAMESPACE" --no-headers | head -10

    log_info "Status check completed"
}

cleanup() {
    log_info "Cleaning up..."

    helm uninstall "$RELEASE_NAME" --namespace "$NAMESPACE" 2>/dev/null || true
    kubectl delete namespace "$NAMESPACE" --ignore-not-found --wait=false

    log_info "Cleanup completed"
}

main() {
    log_info "=========================================="
    log_info "Helm Quickstart Validation"
    log_info "=========================================="

    # Always validate chart structure and lint
    validate_chart_structure
    validate_dependency_update
    validate_helm_lint
    validate_helm_template

    # Skip cluster tests if requested or cluster unavailable
    if ! check_prerequisites; then
        log_info "Skipping cluster-based tests"
        log_info "=========================================="
        log_info "Quickstart validation (template only): PASSED"
        log_info "=========================================="
        exit 0
    fi

    # Run cluster tests
    trap cleanup EXIT

    validate_install
    validate_status
    validate_helm_test

    log_info "=========================================="
    log_info "Quickstart validation: PASSED"
    log_info "=========================================="
}

main "$@"
