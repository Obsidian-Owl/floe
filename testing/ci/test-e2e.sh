#!/bin/bash
# End-to-end test runner script for CI
# Runs full E2E tests against complete platform stack
#
# Usage: ./testing/ci/test-e2e.sh [pytest-args...]
#
# Environment:
#   KUBECONFIG          Path to kubeconfig (default: ~/.kube/config)
#   TEST_NAMESPACE      K8s namespace for tests (default: floe-test)
#   E2E_TIMEOUT         E2E test timeout in seconds (default: 600)
#   COLLECT_LOGS        Collect logs on failure: true/false (default: true)

set -euo pipefail

# Configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
E2E_TIMEOUT="${E2E_TIMEOUT:-600}"
COLLECT_LOGS="${COLLECT_LOGS:-true}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

echo "Running E2E tests..."
echo "Namespace: ${TEST_NAMESPACE}"
echo "Timeout: ${E2E_TIMEOUT}s"
echo ""

# Check kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "ERROR: kubectl is not installed or not in PATH" >&2
    exit 1
fi

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster" >&2
    exit 1
fi

# Function to collect logs on failure
collect_logs() {
    if [[ "${COLLECT_LOGS}" == "true" ]]; then
        echo ""
        echo "=== Collecting logs from ${TEST_NAMESPACE} ==="

        LOG_DIR="${PROJECT_ROOT}/test-logs"
        mkdir -p "${LOG_DIR}"

        # Get pod statuses
        kubectl get pods -n "${TEST_NAMESPACE}" -o wide > "${LOG_DIR}/pods.txt" 2>&1 || true

        # Get events
        kubectl get events -n "${TEST_NAMESPACE}" --sort-by='.lastTimestamp' > "${LOG_DIR}/events.txt" 2>&1 || true

        # Collect logs from each pod
        for pod in $(kubectl get pods -n "${TEST_NAMESPACE}" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
            echo "Collecting logs from ${pod}..."
            kubectl logs -n "${TEST_NAMESPACE}" "${pod}" --all-containers --tail=100 > "${LOG_DIR}/${pod}.log" 2>&1 || true
        done

        echo "Logs collected in ${LOG_DIR}/"
    fi
}

# Set up trap to collect logs on failure
trap 'collect_logs' ERR

# Verify all required services are running
echo "Verifying service readiness..."
REQUIRED_SERVICES=("postgres" "minio" "polaris" "dagster" "marquez")
for service in "${REQUIRED_SERVICES[@]}"; do
    if ! kubectl get pods -n "${TEST_NAMESPACE}" -l "app=${service}" --no-headers 2>/dev/null | grep -q "Running"; then
        echo "WARNING: Service ${service} may not be running" >&2
    fi
done

echo ""
echo "Running E2E tests..."

# Run E2E tests
uv run pytest \
    tests/e2e/ \
    -v \
    --tb=short \
    --timeout="${E2E_TIMEOUT}" \
    "$@"

echo ""
echo "E2E tests completed successfully!"
