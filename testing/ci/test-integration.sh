#!/bin/bash
# Integration test runner script for CI
# Runs integration tests against K8s services (requires Kind cluster)
#
# Usage: ./testing/ci/test-integration.sh [pytest-args...]
#
# Environment:
#   KUBECONFIG          Path to kubeconfig (default: ~/.kube/config)
#   TEST_NAMESPACE      K8s namespace for tests (default: floe-test)
#   WAIT_TIMEOUT        Service readiness timeout in seconds (default: 300)

set -euo pipefail

# Configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-300}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

echo "Running integration tests..."
echo "Namespace: ${TEST_NAMESPACE}"
echo "Kubeconfig: ${KUBECONFIG}"
echo ""

# Check kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed or not in PATH" >&2
    exit 1
fi

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster" >&2
    echo "Ensure Kind cluster is running: kind get clusters" >&2
    exit 1
fi

# Check namespace exists
if ! kubectl get namespace "${TEST_NAMESPACE}" &> /dev/null; then
    echo "WARNING: Namespace ${TEST_NAMESPACE} does not exist" >&2
    echo "Creating namespace..." >&2
    kubectl create namespace "${TEST_NAMESPACE}"
fi

# Wait for pods to be ready
echo "Waiting for pods in ${TEST_NAMESPACE} to be ready (timeout: ${WAIT_TIMEOUT}s)..."
if ! kubectl wait --for=condition=ready pods --all -n "${TEST_NAMESPACE}" --timeout="${WAIT_TIMEOUT}s" 2>/dev/null; then
    echo "WARNING: Some pods may not be ready" >&2
    kubectl get pods -n "${TEST_NAMESPACE}"
fi

echo ""
echo "Running integration tests..."

# Run integration tests
uv run pytest \
    packages/floe-core/tests/integration/ \
    -v \
    --tb=short \
    -x \
    "$@"

echo ""
echo "Integration tests completed successfully!"
