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
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
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

        # Kind's taint-removal step can race the API server in DooD (Docker-
        # outside-of-Docker) environments where kubelet startup is slower.
        # Use --retain so the control plane container survives failure, allowing
        # manual taint removal and cluster recovery without full re-creation.
        if ! kind create cluster --name "${CLUSTER_NAME}" --config "${SCRIPT_DIR}/kind-config.yaml" --retain --wait "${TIMEOUT}s" 2>&1; then
            local cp_container="${CLUSTER_NAME}-control-plane"
            if docker inspect "${cp_container}" >/dev/null 2>&1; then
                log_warn "Kind taint-removal raced API server startup — retrying manually"
                local retries=0
                while [[ ${retries} -lt 30 ]]; do
                    if docker exec --privileged "${cp_container}" \
                        kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes >/dev/null 2>&1; then
                        docker exec --privileged "${cp_container}" \
                            kubectl --kubeconfig=/etc/kubernetes/admin.conf \
                            taint nodes --all node-role.kubernetes.io/control-plane- 2>/dev/null || true
                        log_info "Taint removed manually — cluster recovered"
                        break
                    fi
                    sleep 2
                    retries=$((retries + 1))
                done
                if [[ ${retries} -ge 30 ]]; then
                    log_error "API server did not become ready after 60s"
                    exit 1
                fi
            else
                log_error "Cluster creation failed and no control plane container found"
                exit 1
            fi
        fi
        log_info "Cluster created successfully"
    fi

    # Export kubeconfig to ensure ~/.kube/config is up to date
    # This is idempotent and ensures Lens/other tools can see the cluster
    log_info "Exporting kubeconfig for kind-${CLUSTER_NAME}..."
    kind export kubeconfig --name "${CLUSTER_NAME}"

    # Verify context is set
    kubectl config use-context "kind-${CLUSTER_NAME}"

    # Docker-outside-of-Docker fix: Kind writes 127.0.0.1:<random-port> to
    # kubeconfig, but in a DooD devcontainer, 127.0.0.1 is the container's
    # own loopback — not the Docker host. Rewrite to the control plane
    # container's Docker network IP which IS reachable via the shared network.
    if docker inspect "${CLUSTER_NAME}-control-plane" >/dev/null 2>&1; then
        local cp_ip
        cp_ip=$(docker inspect "${CLUSTER_NAME}-control-plane" \
            --format '{{(index .NetworkSettings.Networks "kind").IPAddress}}' 2>/dev/null || true)
        if [[ -n "${cp_ip}" ]]; then
            local current_server
            current_server=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null || true)
            if [[ "${current_server}" == https://127.0.0.1:* ]]; then
                # Check if 127.0.0.1 is actually reachable (it is on native Docker, not in DooD)
                local api_port
                api_port=$(echo "${current_server}" | sed -nE 's|https://127.0.0.1:([0-9]+)|\1|p')
                if ! kubectl --server="https://127.0.0.1:${api_port}" --insecure-skip-tls-verify cluster-info >/dev/null 2>&1; then
                    kubectl config set-cluster "kind-${CLUSTER_NAME}" --server="https://${cp_ip}:6443" >/dev/null
                    log_info "DooD: Rewrote kubeconfig to https://${cp_ip}:6443"
                fi
            fi
        fi
    fi
}

# Pre-load container images that Helm hooks need (avoids ImagePullBackOff in Kind)
preload_images() {
    log_info "Pre-loading images into Kind cluster..."
    # Bootstrap job uses curlimages/curl for init containers and main container
    docker pull curlimages/curl:8.5.0 2>&1 || log_warn "Failed to pull curlimages/curl:8.5.0"
    kind load docker-image curlimages/curl:8.5.0 --name "${CLUSTER_NAME}" 2>&1 || {
        log_warn "Failed to load curlimages/curl:8.5.0 into Kind — bootstrap may be slow"
    }
    log_info "Images pre-loaded"
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

# Deploy services via Helm charts
deploy_services_helm() {
    if [[ "${SKIP_SERVICES:-false}" == "true" ]]; then
        log_info "Skipping service deployment (SKIP_SERVICES=true)"
        return
    fi

    if ! command -v helm &> /dev/null; then
        log_error "Helm is required for service deployment"
        log_error "Install Helm from: https://helm.sh/docs/intro/install/"
        exit 1
    fi

    log_info "Deploying services via Helm to namespace: ${NAMESPACE}"

    # Build and load the Dagster demo image into Kind (required by values-test.yaml)
    # The dagster webserver and daemon use floe-dagster-demo:latest with pullPolicy: Never
    if [[ -f "${PROJECT_ROOT}/docker/dagster-demo/Dockerfile" ]]; then
        log_info "Building Dagster demo image..."
        make -C "${PROJECT_ROOT}" build-demo-image 2>&1 || {
            log_warn "Dagster demo image build failed — Dagster pods will be in ErrImageNeverPull"
        }
    fi

    # Update Helm dependencies
    log_info "Updating Helm chart dependencies..."
    helm dependency update "${PROJECT_ROOT}/charts/floe-platform" 2>/dev/null || true

    # Install floe-platform with test values
    log_info "Installing floe-platform chart..."
    helm upgrade --install floe-platform "${PROJECT_ROOT}/charts/floe-platform" \
        --namespace "${NAMESPACE}" --create-namespace \
        --values "${PROJECT_ROOT}/charts/floe-platform/values-test.yaml" \
        --wait \
        --timeout 10m

    # Install floe-jobs with test values (if needed for job execution tests)
    log_info "Installing floe-jobs chart..."
    helm dependency update "${PROJECT_ROOT}/charts/floe-jobs" 2>/dev/null || true
    helm upgrade --install floe-jobs-test "${PROJECT_ROOT}/charts/floe-jobs" \
        --namespace "${NAMESPACE}" \
        --values "${PROJECT_ROOT}/charts/floe-jobs/values-test.yaml" \
        --wait \
        --timeout 5m

    log_info "Helm-based services deployed successfully"
}

# Wait for Helm-deployed services
wait_for_services_helm() {
    log_info "Waiting for Helm-deployed services to be ready..."

    # Check Polaris (parent-chart component label)
    log_info "Waiting for Polaris..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=polaris -n "${NAMESPACE}" --timeout="${TIMEOUT}s" 2>/dev/null || {
        log_warn "Polaris pods not ready within timeout"
    }

    # Check PostgreSQL (parent-chart component label)
    log_info "Waiting for PostgreSQL..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=postgresql -n "${NAMESPACE}" --timeout="${TIMEOUT}s" 2>/dev/null || {
        log_warn "PostgreSQL pods not ready within timeout"
    }

    # Check MinIO (subchart name label)
    log_info "Waiting for MinIO..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=minio -n "${NAMESPACE}" --timeout="${TIMEOUT}s" 2>/dev/null || {
        log_warn "MinIO pods not ready within timeout"
    }

    # Check Dagster if enabled (subchart name label)
    log_info "Waiting for Dagster..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=dagster -n "${NAMESPACE}" --timeout="${TIMEOUT}s" 2>/dev/null || {
        log_warn "Dagster pods not ready within timeout (may be disabled)"
    }

    log_info "All Helm-deployed services are ready"
}

# Install released PyIceberg version
install_pyiceberg_fix() {
    log_info "Installing pyiceberg[s3fs]==0.11.1..."
    uv pip install "pyiceberg[s3fs]==0.11.1" 2>&1 || {
        log_warn "PyIceberg install failed — E2E tests may fail"
    }
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
    echo "  Dagster:     http://localhost:3100 (requires: kubectl port-forward svc/floe-platform-dagster-webserver 3100:3000 -n floe-test)"
    echo "  MinIO API:   http://localhost:9000"
    echo "  MinIO UI:    http://localhost:9001 (minioadmin/minioadmin123)"
    echo "  Jaeger:      http://localhost:16686"
    echo "  Keycloak:    http://localhost:8082 (admin/admin-secret-123)"
    echo "  Infisical:   http://localhost:8083"
    echo "  OCI Registry (anon):  http://localhost:30500/v2/"
    echo "  OCI Registry (auth):  http://localhost:30501/v2/ (testuser/testpass123)"
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
    preload_images
    deploy_metrics_server
    deploy_services_helm
    wait_for_services_helm
    deploy_monitoring_stack
    install_pyiceberg_fix
    print_info
}

main "$@"
