#!/usr/bin/env bash
# Setup Kind cluster for floe integration testing
# Usage: ./testing/k8s/setup-cluster.sh
#
# Prerequisites:
#   - kind (https://kind.sigs.k8s.io/)
#   - kubectl
#   - docker
#
# Environment variables:
#   CLUSTER_NAME: Name of Kind cluster (default: floe-test)
#   SKIP_SERVICES: Set to "true" to skip deploying services
#   VERBOSE: Set to "true" for verbose output

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-floe-test}"
NAMESPACE="floe-test"
TIMEOUT="${TIMEOUT:-300}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v kind &> /dev/null; then
        log_error "kind is not installed. Install from: https://kind.sigs.k8s.io/"
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_error "docker is not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

# Create Kind cluster
create_cluster() {
    log_info "Creating Kind cluster: ${CLUSTER_NAME}"

    # Check if cluster already exists
    if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
        log_warn "Cluster ${CLUSTER_NAME} already exists"
        kubectl cluster-info --context "kind-${CLUSTER_NAME}" &> /dev/null || {
            log_warn "Cluster exists but is not accessible, recreating..."
            kind delete cluster --name "${CLUSTER_NAME}"
        }
    fi

    # Create cluster if it doesn't exist
    if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
        # Create artifact directory if it doesn't exist
        mkdir -p /tmp/floe-test-artifacts

        kind create cluster --config "${SCRIPT_DIR}/kind-config.yaml" --wait "${TIMEOUT}s"
        log_info "Cluster created successfully"
    fi

    # Set kubectl context
    kubectl config use-context "kind-${CLUSTER_NAME}"
}

# Deploy services
deploy_services() {
    if [[ "${SKIP_SERVICES:-false}" == "true" ]]; then
        log_info "Skipping service deployment (SKIP_SERVICES=true)"
        return
    fi

    log_info "Deploying services to namespace: ${NAMESPACE}"

    # Apply namespace first
    kubectl apply -f "${SCRIPT_DIR}/services/namespace.yaml"

    # Wait for namespace to be ready
    kubectl wait --for=jsonpath='{.status.phase}'=Active "namespace/${NAMESPACE}" --timeout=30s

    # Apply PostgreSQL (dependency for Dagster/Polaris)
    log_info "Deploying PostgreSQL..."
    kubectl apply -f "${SCRIPT_DIR}/services/postgres.yaml"

    # Apply MinIO (dependency for Polaris)
    log_info "Deploying MinIO..."
    kubectl apply -f "${SCRIPT_DIR}/services/minio.yaml"

    # Wait for PostgreSQL and MinIO to be ready before Polaris/Dagster
    log_info "Waiting for PostgreSQL to be ready..."
    kubectl wait --for=condition=available deployment/postgres -n "${NAMESPACE}" --timeout=120s

    log_info "Waiting for MinIO to be ready..."
    kubectl wait --for=condition=available deployment/minio -n "${NAMESPACE}" --timeout=120s

    # Apply Polaris
    log_info "Deploying Polaris..."
    kubectl apply -f "${SCRIPT_DIR}/services/polaris.yaml"

    # Apply Dagster
    log_info "Deploying Dagster..."
    kubectl apply -f "${SCRIPT_DIR}/services/dagster.yaml"
}

# Wait for all services to be ready
wait_for_services() {
    log_info "Waiting for all services to be ready..."

    local services=("postgres" "minio" "polaris" "dagster-webserver" "dagster-daemon")

    for service in "${services[@]}"; do
        log_info "Waiting for ${service}..."
        if ! kubectl wait --for=condition=available "deployment/${service}" -n "${NAMESPACE}" --timeout="${TIMEOUT}s" 2>/dev/null; then
            log_warn "Deployment ${service} not found or not ready within timeout"
        fi
    done

    log_info "All services deployed"
}

# Print cluster info
print_info() {
    log_info "Cluster is ready!"
    echo ""
    echo "Cluster: ${CLUSTER_NAME}"
    echo "Namespace: ${NAMESPACE}"
    echo ""
    echo "Services:"
    kubectl get pods -n "${NAMESPACE}" -o wide 2>/dev/null || true
    echo ""
    echo "To access services from your host:"
    echo "  kubectl port-forward -n ${NAMESPACE} svc/postgres 5432:5432"
    echo "  kubectl port-forward -n ${NAMESPACE} svc/minio 9000:9000"
    echo "  kubectl port-forward -n ${NAMESPACE} svc/polaris 8181:8181"
    echo "  kubectl port-forward -n ${NAMESPACE} svc/dagster-webserver 3000:3000"
    echo ""
}

# Main
main() {
    check_prerequisites
    create_cluster
    deploy_services
    wait_for_services
    print_info
}

main "$@"
