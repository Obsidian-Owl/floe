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
#   ALLOW_NO_TESTS      Set to "true" to allow running with no integration tests (default: false)
#
# Note: This script dynamically discovers all packages with integration tests.
#       New packages are automatically included when they have a tests/integration/ directory.

set -euo pipefail

# Configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-300}"
ALLOW_NO_TESTS="${ALLOW_NO_TESTS:-false}"
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

# Dynamically discover all packages with integration tests
INTEGRATION_TEST_PATHS=""

for pkg_dir in packages/*/; do
    integration_test_dir="${pkg_dir}tests/integration"
    if [[ -d "${integration_test_dir}" ]]; then
        echo "  Found: ${integration_test_dir}"
        INTEGRATION_TEST_PATHS="${INTEGRATION_TEST_PATHS} ${integration_test_dir}"
    fi
done

# Also check for root-level integration tests
if [[ -d "tests/integration" ]]; then
    echo "  Found: tests/integration"
    INTEGRATION_TEST_PATHS="${INTEGRATION_TEST_PATHS} tests/integration"
fi

echo ""

if [[ -z "${INTEGRATION_TEST_PATHS}" ]]; then
    echo "WARNING: No integration test directories found" >&2
    if [[ "${ALLOW_NO_TESTS}" == "true" ]]; then
        echo "ALLOW_NO_TESTS=true, exiting successfully." >&2
        exit 0
    else
        echo "ERROR: No integration tests found. This may indicate missing tests." >&2
        echo "Set ALLOW_NO_TESTS=true to skip this check during early development." >&2
        exit 1
    fi
fi

echo "Running integration tests..."

# Run integration tests
# shellcheck disable=SC2086
uv run pytest \
    ${INTEGRATION_TEST_PATHS} \
    -v \
    --tb=short \
    -x \
    "$@"

echo ""
echo "Integration tests completed successfully!"
