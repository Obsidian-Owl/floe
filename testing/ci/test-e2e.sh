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

# Function to wait for localhost port availability
wait_for_port() {
    local host=$1 port=$2 timeout=${3:-10}
    for i in $(seq 1 "$timeout"); do
        if nc -z "$host" "$port" 2>/dev/null; then return 0; fi
        sleep 1
    done
    echo "ERROR: Port $host:$port not available after ${timeout}s" >&2
    return 1
}

# Cleanup function for port-forwards
cleanup_port_forwards() {
    [[ -n "${DAGSTER_PF_PID:-}" ]] && kill "${DAGSTER_PF_PID}" 2>/dev/null || true
    [[ -n "${POLARIS_PF_PID:-}" ]] && kill "${POLARIS_PF_PID}" 2>/dev/null || true
    [[ -n "${MINIO_API_PF_PID:-}" ]] && kill "${MINIO_API_PF_PID}" 2>/dev/null || true
    [[ -n "${MINIO_UI_PF_PID:-}" ]] && kill "${MINIO_UI_PF_PID}" 2>/dev/null || true
    [[ -n "${OTEL_PF_PID:-}" ]] && kill "${OTEL_PF_PID}" 2>/dev/null || true
    [[ -n "${MARQUEZ_PF_PID:-}" ]] && kill "${MARQUEZ_PF_PID}" 2>/dev/null || true
    [[ -n "${JAEGER_PF_PID:-}" ]] && kill "${JAEGER_PF_PID}" 2>/dev/null || true
    [[ -n "${POSTGRES_PF_PID:-}" ]] && kill "${POSTGRES_PF_PID}" 2>/dev/null || true
}

# Combined cleanup on exit/error
cleanup_all() {
    cleanup_port_forwards
    collect_logs
}

# Set up traps: cleanup port-forwards on EXIT, full cleanup on ERR
trap 'cleanup_port_forwards' EXIT
trap 'cleanup_all' ERR

# Verify all required Helm chart pods are running
echo "Verifying service readiness..."

# Use Helm chart labels for pod verification
HELM_SERVICES=(
    "app.kubernetes.io/name=floe-platform,app.kubernetes.io/component=postgresql"
    "app.kubernetes.io/name=minio"
    "app.kubernetes.io/component=polaris"
    "app.kubernetes.io/name=dagster,component=dagster-webserver"
    "app.kubernetes.io/name=otel"
)
for labels in "${HELM_SERVICES[@]}"; do
    if ! kubectl get pods -n "${TEST_NAMESPACE}" -l "${labels}" --no-headers 2>/dev/null | grep -q "Running"; then
        echo "WARNING: Pods with labels '${labels}' may not be running" >&2
    fi
done

echo ""
echo "Setting up port-forwards for Helm chart services..."

# Port-forward all Helm chart services to localhost for E2E tests
# These services use ClusterIP by default

# Dagster webserver (port 80 -> localhost:3000)
kubectl port-forward svc/floe-platform-dagster-webserver 3000:80 -n "${TEST_NAMESPACE}" &
DAGSTER_PF_PID=$!

# Polaris (port 8181 -> localhost:8181)
kubectl port-forward svc/floe-platform-polaris 8181:8181 -n "${TEST_NAMESPACE}" &
POLARIS_PF_PID=$!

# MinIO API (port 9000 -> localhost:9000)
kubectl port-forward svc/floe-platform-minio 9000:9000 -n "${TEST_NAMESPACE}" &
MINIO_API_PF_PID=$!

# MinIO Console (port 9001 -> localhost:9001)
kubectl port-forward svc/floe-platform-minio 9001:9001 -n "${TEST_NAMESPACE}" &
MINIO_UI_PF_PID=$!

# OTel collector (port 4317 -> localhost:4317)
kubectl port-forward svc/floe-platform-otel 4317:4317 -n "${TEST_NAMESPACE}" &
OTEL_PF_PID=$!

# Marquez lineage service (if deployed)
if kubectl get svc floe-platform-marquez -n "${TEST_NAMESPACE}" &>/dev/null; then
    kubectl port-forward svc/floe-platform-marquez 5001:5001 -n "${TEST_NAMESPACE}" &
    MARQUEZ_PF_PID=$!
fi

# Jaeger query service (if deployed)
if kubectl get svc floe-platform-jaeger-query -n "${TEST_NAMESPACE}" &>/dev/null; then
    kubectl port-forward svc/floe-platform-jaeger-query 16686:16686 -n "${TEST_NAMESPACE}" &
    JAEGER_PF_PID=$!
fi

# PostgreSQL (for direct DB access tests if needed)
kubectl port-forward svc/floe-platform-postgresql 5432:5432 -n "${TEST_NAMESPACE}" &
POSTGRES_PF_PID=$!

# Wait for port-forwards to establish
wait_for_port localhost 3000 15
wait_for_port localhost 8181 15
wait_for_port localhost 9000 15
wait_for_port localhost 4317 15
wait_for_port localhost 5432 15
wait_for_port localhost 5001 15 || true  # Marquez optional
wait_for_port localhost 16686 15 || true  # Jaeger optional

echo "Port-forwards established."
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
