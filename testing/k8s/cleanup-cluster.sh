#!/usr/bin/env bash
# Cleanup Kind cluster for floe integration testing
# Usage: ./testing/k8s/cleanup-cluster.sh
#
# Environment variables:
#   CLUSTER_NAME: Name of Kind cluster (default: floe-test)
#   KEEP_CLUSTER: Set to "true" to only delete namespace, not cluster
#   VERBOSE: Set to "true" for verbose output

set -euo pipefail

# Configuration
CLUSTER_NAME="${CLUSTER_NAME:-floe-test}"
NAMESPACE="floe-test"

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

# Clean up kubeconfig entries for the cluster
cleanup_kubeconfig() {
    local context_name="kind-${CLUSTER_NAME}"

    log_info "Cleaning up kubeconfig entries for ${context_name}..."

    # Remove context, cluster, and user entries from kubeconfig
    # These commands are safe to run even if entries don't exist
    kubectl config delete-context "${context_name}" 2>/dev/null || true
    kubectl config delete-cluster "${context_name}" 2>/dev/null || true
    kubectl config delete-user "${context_name}" 2>/dev/null || true

    log_info "Kubeconfig cleaned up"
}

# Delete namespace only (keep cluster)
delete_namespace() {
    log_info "Deleting namespace: ${NAMESPACE}"

    if kubectl get namespace "${NAMESPACE}" &> /dev/null; then
        kubectl delete namespace "${NAMESPACE}" --wait=true --timeout=120s || {
            log_warn "Namespace deletion timed out, forcing..."
            kubectl delete namespace "${NAMESPACE}" --force --grace-period=0 2>/dev/null || true
        }
        log_info "Namespace deleted"
    else
        log_info "Namespace ${NAMESPACE} does not exist"
    fi
}

# Delete Kind cluster
delete_cluster() {
    log_info "Deleting Kind cluster: ${CLUSTER_NAME}"

    if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
        kind delete cluster --name "${CLUSTER_NAME}"
        log_info "Cluster deleted"
    else
        log_info "Cluster ${CLUSTER_NAME} does not exist"
    fi

    # Clean up kubeconfig entries (so Lens doesn't show stale cluster)
    cleanup_kubeconfig

    # Clean up artifact directory
    if [[ -d /tmp/floe-test-artifacts ]]; then
        rm -rf /tmp/floe-test-artifacts
        log_info "Cleaned up artifact directory"
    fi
}

# Main
main() {
    if [[ "${KEEP_CLUSTER:-false}" == "true" ]]; then
        log_info "Keeping cluster, only deleting namespace (KEEP_CLUSTER=true)"
        delete_namespace
    else
        delete_cluster
    fi

    log_info "Cleanup complete"
}

main "$@"
