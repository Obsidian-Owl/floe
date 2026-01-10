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
#   SKIP_MONITORING: Set to "true" to skip Prometheus/Grafana stack
#   VERBOSE: Set to "true" for verbose output
#
# After setup, services are accessible via localhost:
#   Polaris:     http://localhost:8181
#   Dagster:     http://localhost:3000
#   MinIO API:   http://localhost:9000
#   MinIO UI:    http://localhost:9001
#   Grafana:     http://localhost:3001 (admin/admin)
#   Prometheus:  http://localhost:9090

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

    # Export kubeconfig to ensure ~/.kube/config is up to date
    # This is idempotent and ensures Lens/other tools can see the cluster
    log_info "Exporting kubeconfig for kind-${CLUSTER_NAME}..."
    kind export kubeconfig --name "${CLUSTER_NAME}"

    # Verify context is set
    kubectl config use-context "kind-${CLUSTER_NAME}"
}

# Deploy metrics-server (required for kubectl top and Lens metrics)
deploy_metrics_server() {
    log_info "Deploying metrics-server..."
    kubectl apply -f "${SCRIPT_DIR}/services/metrics-server.yaml"

    log_info "Waiting for metrics-server to be ready..."
    kubectl wait --for=condition=available deployment/metrics-server -n kube-system --timeout=120s || {
        log_warn "metrics-server not ready within timeout, continuing..."
    }
}

# Deploy kube-prometheus-stack via Helm
deploy_monitoring_stack() {
    if [[ "${SKIP_MONITORING:-false}" == "true" ]]; then
        log_info "Skipping monitoring stack (SKIP_MONITORING=true)"
        return
    fi

    # Check if Helm is available
    if ! command -v helm &> /dev/null; then
        log_warn "Helm not installed, skipping monitoring stack"
        log_warn "Install Helm from: https://helm.sh/docs/intro/install/"
        return
    fi

    log_info "Adding Prometheus Helm repo..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
    helm repo update

    log_info "Deploying kube-prometheus-stack..."
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --create-namespace \
        --set prometheus.service.type=NodePort \
        --set prometheus.service.nodePort=30090 \
        --set grafana.service.type=NodePort \
        --set grafana.service.nodePort=30080 \
        --set grafana.adminPassword=admin \
        --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
        --wait \
        --timeout 5m

    log_info "Monitoring stack deployed"
    log_info "  Grafana:    http://localhost:3001 (admin/admin)"
    log_info "  Prometheus: http://localhost:9090"
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

    # Apply Jaeger (for OpenTelemetry integration tests)
    log_info "Deploying Jaeger..."
    kubectl apply -f "${SCRIPT_DIR}/services/jaeger.yaml"
}

# Wait for all services to be ready
wait_for_services() {
    log_info "Waiting for all services to be ready..."

    local services=("postgres" "minio" "polaris" "dagster-webserver" "dagster-daemon" "jaeger")

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
    echo "Monitoring (kube-system):"
    kubectl get pods -n kube-system -l k8s-app=metrics-server 2>/dev/null || true
    echo ""
    if kubectl get namespace monitoring &>/dev/null; then
        echo "Monitoring Stack (monitoring namespace):"
        kubectl get pods -n monitoring --no-headers 2>/dev/null | head -5 || true
        echo "  ..."
    fi
    echo ""
    echo "Services accessible via localhost (NodePort):"
    echo "  Polaris:     http://localhost:8181"
    echo "  Dagster:     http://localhost:3000"
    echo "  MinIO API:   http://localhost:9000"
    echo "  MinIO UI:    http://localhost:9001 (minioadmin/minioadmin123)"
    echo "  Jaeger:      http://localhost:16686"
    echo "  Grafana:     http://localhost:3001 (admin/admin)"
    echo "  Prometheus:  http://localhost:9090"
    echo ""
    echo "Verify metrics: kubectl top nodes"
    echo ""
}

# Main
main() {
    check_prerequisites
    create_cluster
    deploy_metrics_server
    deploy_services
    wait_for_services
    deploy_monitoring_stack
    print_info
}

main "$@"
