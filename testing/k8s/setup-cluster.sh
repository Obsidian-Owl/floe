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
#   FLOE_FLUX_GIT_URL: Git URL for the Flux GitRepository test fixture
#   FLOE_FLUX_GIT_BRANCH: Git branch for the Flux GitRepository fixture
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

# Source shared constants (FLUX_VERSION, FLOE_RELEASE_NAME, etc.)
# shellcheck source=../ci/common.sh
source "${SCRIPT_DIR}/../ci/common.sh"

# Parse command line arguments
for arg in "$@"; do
    case "${arg}" in
        --no-flux)
            FLOE_NO_FLUX=1
            ;;
    esac
done
: "${FLOE_NO_FLUX:=0}"

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

    # jq is required for pre-Flux cleanup (helm status JSON parsing).
    # Skipped when services are disabled — jq is only needed for service deployment.
    if [[ "${SKIP_SERVICES:-false}" != "true" ]]; then
        if ! command -v jq &> /dev/null; then
            log_error "jq is not installed. Install: brew install jq (macOS) or apt install jq (Linux)"
            exit 1
        fi
    fi

    # Flux CLI check — skipped when --no-flux is set or services are skipped
    if [[ "${FLOE_NO_FLUX}" != "1" && "${SKIP_SERVICES:-false}" != "true" ]]; then
        if ! command -v flux &> /dev/null; then
            log_error "flux CLI not found. Install: curl -s https://fluxcd.io/install.sh | sudo bash"
            exit 1
        fi

        # Verify flux version matches FLUX_VERSION (warning only)
        local flux_ver
        flux_ver=$(flux --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
        if [[ -n "${flux_ver}" && "${flux_ver}" != "${FLUX_VERSION}" ]]; then
            log_warn "flux CLI version ${flux_ver} does not match FLUX_VERSION=${FLUX_VERSION}"
        fi
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
                    if docker exec "${cp_container}" \
                        kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes >/dev/null 2>&1; then
                        docker exec "${cp_container}" \
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

    # Docker-outside-of-Docker fix: connect this container to the Kind network
    # so it can reach the control plane container's Docker IP. Only needed when
    # running inside a devcontainer (not on bare Docker host).
    if docker network inspect kind >/dev/null 2>&1; then
        local my_id
        my_id=$(hostname)
        if ! docker inspect "${my_id}" --format '{{json .NetworkSettings.Networks}}' 2>/dev/null | grep -q '"kind"'; then
            if docker network connect kind "${my_id}" 2>/dev/null; then
                log_info "DooD: Connected container to kind network"
            fi
        fi
    fi

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

# Build and load the Dagster demo image into Kind (required by values-test.yaml).
# Both Helm and Flux paths need this — Dagster pods use pullPolicy: Never.
build_demo_image() {
    if [[ -f "${PROJECT_ROOT}/docker/dagster-demo/Dockerfile" ]]; then
        log_info "Building Dagster demo image..."
        KIND_CLUSTER_NAME="${CLUSTER_NAME}" make -C "${PROJECT_ROOT}" build-demo-image 2>&1 || {
            log_warn "Dagster demo image build failed — Dagster pods will be in ErrImageNeverPull"
        }
    fi
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

# ---------------------------------------------------------------------------
# Flux GitOps deployment path
# ---------------------------------------------------------------------------

# Pre-Flux cleanup: remove stuck Helm releases before Flux takes over.
# Skipped when Flux is already managing the cluster (flux-system namespace exists).
pre_flux_cleanup() {
    # If Flux is already installed, its own remediation handles stuck releases.
    if kubectl get namespace flux-system &>/dev/null; then
        log_info "Flux already installed — skipping pre-Flux cleanup (Flux remediation handles stuck releases)"
        return
    fi

    log_info "Checking for stuck Helm releases..."

    local releases=("${FLOE_RELEASE_NAME}" "floe-jobs-test")
    for release in "${releases[@]}"; do
        local release_status
        local helm_output
        if helm_output=$(helm status "${release}" -n "${NAMESPACE}" --output json 2>&1); then
            # helm succeeded — parse status with jq
            release_status=$(echo "${helm_output}" | jq -r '.info.status // "unknown"') || {
                log_error "Failed to parse helm status JSON for release ${release}"
                exit 1
            }
        else
            # helm failed — distinguish "not found" from unexpected errors
            if echo "${helm_output}" | grep -qi "not found"; then
                release_status="not-found"
            else
                log_error "helm status failed for release ${release}: ${helm_output}"
                exit 1
            fi
        fi

        case "${release_status}" in
            failed|pending-upgrade|pending-install|pending-rollback)
                log_warn "Release ${release} is in '${release_status}' state — uninstalling"
                helm uninstall "${release}" -n "${NAMESPACE}" --wait --timeout=300s || {
                    log_error "Failed to uninstall stuck release ${release}"
                    exit 1
                }
                ;;
            deployed|superseded)
                log_info "Release ${release} is in '${release_status}' state — no cleanup needed"
                ;;
            not-found)
                log_info "No existing release '${release}' found — clean install"
                ;;
        esac
    done
}

# Install Flux controllers (source-controller + helm-controller only)
install_flux() {
    log_info "Installing Flux controllers..."

    if ! flux install --version="v${FLUX_VERSION}" --components="source-controller,helm-controller" 2>&1; then
        log_error "Flux installation failed"
        kubectl get pods -n flux-system 2>/dev/null || true
        log_error "Flux installation failed. Check cluster resources and network connectivity." >&2
        exit 1
    fi

    # Wait on the named controller Deployments. Flux already verifies install,
    # but a second wait here protects the rest of bootstrap from racing the
    # controllers and avoids brittle pod-label assumptions across Flux versions.
    log_info "Waiting for Flux controllers to be ready..."
    if ! kubectl wait --for=condition=Available deployment/source-controller \
        -n flux-system --timeout=120s 2>&1; then
        log_error "source-controller deployment did not reach Available within 120s" >&2
        kubectl get deployment,pods -n flux-system 2>/dev/null >&2 || true
        kubectl describe deployment/source-controller -n flux-system 2>/dev/null >&2 || true
        exit 1
    fi
    if ! kubectl wait --for=condition=Available deployment/helm-controller \
        -n flux-system --timeout=120s 2>&1; then
        log_error "helm-controller deployment did not reach Available within 120s" >&2
        kubectl get deployment,pods -n flux-system 2>/dev/null >&2 || true
        kubectl describe deployment/helm-controller -n flux-system 2>/dev/null >&2 || true
        exit 1
    fi
    log_info "Flux controllers are ready"
}

resolve_flux_git_branch() {
    if [[ -n "${FLOE_FLUX_GIT_BRANCH:-}" ]]; then
        printf '%s\n' "${FLOE_FLUX_GIT_BRANCH}"
        return 0
    fi

    local current_branch=""
    if git -C "${PROJECT_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        current_branch=$(git -C "${PROJECT_ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
    fi

    if [[ -n "${current_branch}" && "${current_branch}" != "HEAD" ]]; then
        printf '%s\n' "${current_branch}"
        return 0
    fi

    printf '%s\n' "main"
}

render_flux_manifests() {
    local flux_git_branch="$1"
    local flux_fixture_dir="${FLOE_FLUX_FIXTURE_DIR}"
    local manifest_glob
    local rendered_dir
    rendered_dir=$(mktemp -d "${TMPDIR:-/tmp}/floe-flux-manifests.XXXXXX")

    if [[ "${flux_fixture_dir}" != /* ]]; then
        flux_fixture_dir="${PROJECT_ROOT}/${flux_fixture_dir}"
    fi

    if [[ ! -d "${flux_fixture_dir}" ]]; then
        log_error "Flux fixture directory not found: ${flux_fixture_dir}"
        rm -rf "${rendered_dir}"
        return 1
    fi

    manifest_glob="${flux_fixture_dir}/*.yaml"
    if ! compgen -G "${manifest_glob}" >/dev/null; then
        log_error "Flux fixture directory contains no YAML manifests: ${flux_fixture_dir}"
        rm -rf "${rendered_dir}"
        return 1
    fi

    cp "${flux_fixture_dir}/"*.yaml "${rendered_dir}/"

    if [[ "${FLOE_FLUX_GIT_URL}" == *"|"* ]]; then
        log_error "FLOE_FLUX_GIT_URL contains pipe character — cannot safely render Flux manifests"
        rm -rf "${rendered_dir}"
        return 1
    fi

    sed -i.bak \
        -e "s|url: https://github.com/Obsidian-Owl/floe|url: ${FLOE_FLUX_GIT_URL}|" \
        -e "s|branch: main|branch: ${flux_git_branch}|" \
        "${rendered_dir}/gitrepository.yaml"
    rm -f "${rendered_dir}/gitrepository.yaml.bak"

    printf '%s\n' "${rendered_dir}"
}

# Deploy via Flux: apply CRDs and wait for HelmRelease readiness
deploy_via_flux() {
    # Ensure target namespace exists (direct Helm path uses --create-namespace,
    # but kubectl apply of namespaced CRDs requires the namespace to pre-exist)
    kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

    local flux_git_branch
    flux_git_branch=$(resolve_flux_git_branch)
    local flux_manifest_dir
    flux_manifest_dir=$(render_flux_manifests "${flux_git_branch}")
    local apply_status=0

    log_info "Applying Flux HelmRelease CRDs from ${FLOE_FLUX_GIT_URL}@${flux_git_branch}..."
    if kubectl apply -f "${flux_manifest_dir}/"; then
        apply_status=0
    else
        apply_status=$?
    fi
    rm -rf "${flux_manifest_dir}"
    if [[ "${apply_status}" -ne 0 ]]; then
        return "${apply_status}"
    fi

    log_info "Waiting for floe-platform HelmRelease to be ready (up to 15m)..."
    if ! kubectl wait helmrelease/floe-platform -n "${NAMESPACE}" \
        --for=condition=Ready --timeout=900s 2>&1; then
        log_error "floe-platform HelmRelease did not reach Ready state"
        flux get helmrelease -n "${NAMESPACE}" 2>/dev/null >&2 || true
        kubectl get events --sort-by='.lastTimestamp' -n "${NAMESPACE}" 2>/dev/null | tail -10 >&2 || true
        exit 1
    fi

    log_info "Waiting for floe-jobs-test HelmRelease to be ready (up to 10m)..."
    if ! kubectl wait helmrelease/floe-jobs-test -n "${NAMESPACE}" \
        --for=condition=Ready --timeout=600s 2>&1; then
        log_error "floe-jobs-test HelmRelease did not reach Ready state"
        flux get helmrelease -n "${NAMESPACE}" 2>/dev/null >&2 || true
        kubectl get events --sort-by='.lastTimestamp' -n "${NAMESPACE}" 2>/dev/null | tail -10 >&2 || true
        exit 1
    fi

    log_info "Flux-managed releases are ready"
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

    if [[ "${SKIP_SERVICES:-false}" == "true" ]]; then
        log_info "Skipping service deployment (SKIP_SERVICES=true)"
    else
        # Pre-Flux cleanup: remove stuck Helm releases (skips when Flux already installed)
        pre_flux_cleanup

        # Demo image is needed by both paths (Dagster uses pullPolicy: Never)
        build_demo_image

        if [[ "${FLOE_NO_FLUX}" == "1" ]]; then
            log_info "FLOE_NO_FLUX=1 — using direct Helm deployment path"
            deploy_services_helm
            wait_for_services_helm
        else
            log_info "Using Flux GitOps deployment path"
            install_flux
            deploy_via_flux
            # No wait_for_services_helm here — HelmRelease Ready condition is the
            # authoritative readiness signal for Flux-managed releases.
        fi
    fi

    deploy_monitoring_stack
    install_pyiceberg_fix
    print_info
}

main "$@"
