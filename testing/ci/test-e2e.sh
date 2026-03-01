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
#   DAGSTER_HOST_PORT   Dagster localhost port (default: 3100)
#   MINIO_USER          MinIO admin username (default: minioadmin)
#   MINIO_PASS          MinIO admin password (default: minioadmin123)

set -euo pipefail

# Configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
E2E_TIMEOUT="${E2E_TIMEOUT:-600}"
COLLECT_LOGS="${COLLECT_LOGS:-true}"
MINIO_USER="${MINIO_USER:-minioadmin}"
MINIO_PASS="${MINIO_PASS:-minioadmin123}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

# Validate namespace format (K8s DNS label: lowercase alphanumeric + hyphens)
if [[ ! "${TEST_NAMESPACE}" =~ ^[a-z0-9][a-z0-9-]*[a-z0-9]$ ]]; then
    echo "ERROR: Invalid namespace format: '${TEST_NAMESPACE}'" >&2
    exit 1
fi

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
        if (echo >/dev/tcp/"$host"/"$port") 2>/dev/null; then return 0; fi
        sleep 1
    done
    echo "ERROR: Port $host:$port not available after ${timeout}s" >&2
    return 1
}

# Check if a port is already listening (e.g. via Kind NodePort mapping)
port_already_available() {
    (echo >/dev/tcp/localhost/"$1") 2>/dev/null
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
echo "(Ports already exposed via Kind NodePorts will be skipped)"

# Port-forward all Helm chart services to localhost for E2E tests
# When Kind NodePorts already expose a port, skip the port-forward

# Dagster webserver (port 3000 -> localhost:3100)
# Remapped from 3000 to avoid conflict with local dev servers
DAGSTER_HOST_PORT="${DAGSTER_HOST_PORT:-3100}"
if port_already_available "${DAGSTER_HOST_PORT}"; then
    echo "  Dagster (${DAGSTER_HOST_PORT}): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-dagster-webserver "${DAGSTER_HOST_PORT}":3000 -n "${TEST_NAMESPACE}" &
    DAGSTER_PF_PID=$!
fi

# Polaris catalog API (8181) + management health (8182)
if port_already_available 8181; then
    echo "  Polaris (8181): already available (NodePort)"
    # 8182 (management) may still need a port-forward even when 8181 has a NodePort
    if ! port_already_available 8182; then
        kubectl port-forward svc/floe-platform-polaris 8182:8182 -n "${TEST_NAMESPACE}" &
        POLARIS_PF_PID=$!
    else
        echo "  Polaris mgmt (8182): already available (NodePort)"
    fi
else
    kubectl port-forward svc/floe-platform-polaris 8181:8181 8182:8182 -n "${TEST_NAMESPACE}" &
    POLARIS_PF_PID=$!
fi

# MinIO API (port 9000 -> localhost:9000)
if port_already_available 9000; then
    echo "  MinIO API (9000): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-minio 9000:9000 -n "${TEST_NAMESPACE}" &
    MINIO_API_PF_PID=$!
fi

# MinIO Console (port 9001 -> localhost:9001)
if port_already_available 9001; then
    echo "  MinIO Console (9001): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-minio 9001:9001 -n "${TEST_NAMESPACE}" &
    MINIO_UI_PF_PID=$!
fi

# OTel collector (port 4317 -> localhost:4317)
if port_already_available 4317; then
    echo "  OTel (4317): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-otel 4317:4317 -n "${TEST_NAMESPACE}" &
    OTEL_PF_PID=$!
fi

# Marquez lineage service (if deployed)
# Note: Marquez API is on port 5000, admin is on port 5001
if kubectl get svc floe-platform-marquez -n "${TEST_NAMESPACE}" &>/dev/null; then
    if port_already_available 5000; then
        echo "  Marquez (5000): already available (NodePort)"
    else
        kubectl port-forward svc/floe-platform-marquez 5000:5000 -n "${TEST_NAMESPACE}" &
        MARQUEZ_PF_PID=$!
    fi
fi

# Jaeger query service (if deployed)
if kubectl get svc floe-platform-jaeger-query -n "${TEST_NAMESPACE}" &>/dev/null; then
    if port_already_available 16686; then
        echo "  Jaeger (16686): already available (NodePort)"
    else
        kubectl port-forward svc/floe-platform-jaeger-query 16686:16686 -n "${TEST_NAMESPACE}" &
        JAEGER_PF_PID=$!
    fi
fi

# PostgreSQL (for direct DB access tests if needed)
if port_already_available 5432; then
    echo "  PostgreSQL (5432): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-postgresql 5432:5432 -n "${TEST_NAMESPACE}" &
    POSTGRES_PF_PID=$!
fi

# Wait for ports to be available (either NodePort or port-forward)
wait_for_port localhost "${DAGSTER_HOST_PORT}" 15
wait_for_port localhost 8181 15
wait_for_port localhost 8182 15
wait_for_port localhost 9000 15
wait_for_port localhost 4317 15
wait_for_port localhost 5432 15
wait_for_port localhost 5000 15 || true  # Marquez API port (optional)
wait_for_port localhost 16686 15 || true  # Jaeger optional

echo "Port-forwards established."

# Verify MinIO bucket exists before running tests (defense-in-depth)
MINIO_BUCKET="${MINIO_BUCKET:-floe-iceberg}"
echo "Verifying MinIO bucket '${MINIO_BUCKET}'..."
BUCKET_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:9000/${MINIO_BUCKET}/" 2>/dev/null) || true
if [[ "$BUCKET_CODE" == "404" ]]; then
    echo "MinIO bucket '${MINIO_BUCKET}' not found — creating..." >&2
    MINIO_POD=$(kubectl get pods -n "${TEST_NAMESPACE}" -l app.kubernetes.io/name=minio \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [[ -z "${MINIO_POD}" ]]; then
        echo "ERROR: No MinIO pod found in namespace ${TEST_NAMESPACE}" >&2
        exit 1
    fi
    kubectl exec -n "${TEST_NAMESPACE}" "${MINIO_POD}" -- \
        mc alias set local http://localhost:9000 "${MINIO_USER}" "${MINIO_PASS}" 2>&1 || true
    kubectl exec -n "${TEST_NAMESPACE}" "${MINIO_POD}" -- \
        mc mb "local/${MINIO_BUCKET}" --ignore-existing 2>&1
    # Re-verify
    BUCKET_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:9000/${MINIO_BUCKET}/" 2>/dev/null) || true
    if [[ "$BUCKET_CODE" == "404" ]]; then
        echo "ERROR: Failed to create MinIO bucket '${MINIO_BUCKET}'" >&2
        exit 1
    fi
    echo "MinIO bucket '${MINIO_BUCKET}' created successfully"
fi
echo "MinIO bucket '${MINIO_BUCKET}' accessible (HTTP ${BUCKET_CODE})"

# Install PyIceberg from git for Polaris 1.2.0 compatibility
# TODO(pyiceberg-0.11.1): Remove git install once PyPI release available
echo "Installing PyIceberg from git (Polaris 1.2.0 PUT fix)..."
uv pip install "pyiceberg @ git+https://github.com/apache/iceberg-python.git@9687d080f28951464cf02fb2645e2a1185838b21" 2>&1 || {
    echo "WARNING: PyIceberg git install failed -- E2E tests may fail with HttpMethod errors" >&2
}

echo ""
echo "Running E2E tests..."

# Run E2E tests
# TODO(pyiceberg-0.11.1): Remove UV_NO_SYNC once PyPI release available
# UV_NO_SYNC=1: Prevent uv from reverting manually-installed packages (e.g.,
# pyiceberg from git with Polaris 1.2.0 PUT fix).
# Tracking: https://github.com/apache/iceberg-python/pull/3010
DAGSTER_URL="http://localhost:${DAGSTER_HOST_PORT}" \
UV_NO_SYNC=1 uv run pytest \
    tests/e2e/ \
    -v \
    --tb=short \
    --timeout="${E2E_TIMEOUT}" \
    "$@"

echo ""
echo "E2E tests completed successfully!"
