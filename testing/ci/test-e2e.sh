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
#   MINIO_USER          MinIO admin username (from env or AWS_ACCESS_KEY_ID)
#   MINIO_PASS          MinIO admin password (from env or AWS_SECRET_ACCESS_KEY)

set -euo pipefail

# Configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
E2E_TIMEOUT="${E2E_TIMEOUT:-600}"
COLLECT_LOGS="${COLLECT_LOGS:-true}"
# Export credentials as env vars so child processes (ensure-bucket.py)
# can read them without exposing via process arguments.
export MINIO_USER="${MINIO_USER:-${AWS_ACCESS_KEY_ID:-}}"
export MINIO_PASS="${MINIO_PASS:-${AWS_SECRET_ACCESS_KEY:-}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Validate MinIO credentials are available
if [[ -z "${MINIO_USER}" ]]; then
    echo "ERROR: MINIO_USER not set and AWS_ACCESS_KEY_ID not available" >&2
    echo "Set AWS_ACCESS_KEY_ID or MINIO_USER before running E2E tests" >&2
    exit 1
fi
if [[ -z "${MINIO_PASS}" ]]; then
    echo "ERROR: MINIO_PASS not set and AWS_SECRET_ACCESS_KEY not available" >&2
    echo "Set AWS_SECRET_ACCESS_KEY or MINIO_PASS before running E2E tests" >&2
    exit 1
fi

cd "${PROJECT_ROOT}"

# Extract config from manifest.yaml — sets MANIFEST_BUCKET, MANIFEST_REGION, etc.
eval "$(python3 "${SCRIPT_DIR}/extract-manifest-config.py" "${PROJECT_ROOT}/demo/manifest.yaml")"

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

# Check if a port is already listening AND responsive (e.g. via Kind NodePort mapping).
# A TCP-only check is insufficient: OrbStack can bind ports that forward to a stale
# container, causing connection resets. We verify by sending a minimal HTTP request
# and checking for any valid response (even 4xx/5xx counts as "working").
port_already_available() {
    local port=$1
    if [[ ! "${port}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: port_already_available called with non-numeric port: '${port}'" >&2
        return 1
    fi
    # First check TCP
    if ! (echo >/dev/tcp/localhost/"${port}") 2>/dev/null; then
        return 1
    fi
    # Verify the connection actually works (not a stale OrbStack mapping)
    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 --max-time 3 \
        "http://localhost:${port}/" 2>/dev/null) || true
    # http_code "000" means connection reset/refused — port is stale
    [[ "${http_code}" != "000" ]]
}

# Wait for a pod to be Ready with kubectl wait. Exits non-zero on timeout.
wait_for_pod() {
    local labels=$1 description=$2 timeout=${3:-120}
    echo "  Waiting for ${description}..."
    if kubectl wait pods -n "${TEST_NAMESPACE}" -l "${labels}" \
        --for=condition=Ready --timeout="${timeout}s" 2>/dev/null; then
        echo "  ${description}: Ready"
        return 0
    fi
    echo "ERROR: ${description} not ready after ${timeout}s" >&2
    return 1
}

# Cleanup function for port-forwards
cleanup_port_forwards() {
    # Kill watchdog and its entire process group (includes restarted port-forwards)
    if [[ -n "${WATCHDOG_PID:-}" ]]; then
        kill -- -"${WATCHDOG_PID}" 2>/dev/null || kill "${WATCHDOG_PID}" 2>/dev/null || true
    fi
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

# Port-forward watchdog: monitors TCP health every 30s and restarts dead forwards.
# Only monitors ports that were set up via kubectl port-forward (not NodePort).
# Each entry: "CHECK_PORT|PORT_MAPPINGS|SERVICE|PID_VAR"
# PORT_MAPPINGS can be multi-port: "8181:8181 8182:8182" for combined forwards.
WATCHDOG_ENTRIES=()

register_port_forward() {
    local check_port=$1 port_mappings=$2 service=$3 pid_var=$4
    WATCHDOG_ENTRIES+=("${check_port}|${port_mappings}|${service}|${pid_var}")
}

start_port_forward_watchdog() {
    if [[ ${#WATCHDOG_ENTRIES[@]} -eq 0 ]]; then
        return
    fi
    # NOTE: The watchdog runs in a subshell, so `eval "${pid_var}=$!"` updates
    # the PID variable within the subshell only — the parent shell's PID vars
    # become stale after a restart. This is acceptable because:
    #   1. cleanup_port_forwards kills by stored PID (parent's original PID)
    #   2. The watchdog's restarted process is a child of the subshell and will
    #      be cleaned up when the subshell (WATCHDOG_PID) is killed
    #   3. We kill the watchdog subshell's entire process group on cleanup
    (
        while true; do
            sleep 30
            for entry in "${WATCHDOG_ENTRIES[@]}"; do
                IFS='|' read -r check_port port_mappings service pid_var <<< "${entry}"

                # Check TCP connectivity on the monitored port
                if ! (echo >/dev/tcp/localhost/"${check_port}") 2>/dev/null; then
                    echo "WATCHDOG: Port ${check_port} (${service}) is dead, restarting..." >&2
                    # Kill old process if still running
                    old_pid="${!pid_var:-}"
                    if [[ -n "${old_pid}" ]]; then
                        kill "${old_pid}" 2>/dev/null || true
                        wait "${old_pid}" 2>/dev/null || true
                    fi
                    # Restart port-forward (port_mappings may contain multiple mappings)
                    # shellcheck disable=SC2086
                    kubectl port-forward "svc/${service}" ${port_mappings} -n "${TEST_NAMESPACE}" &
                    # Safety: pid_var is always one of our known PID variable names
                    # (e.g. DAGSTER_PF_PID, POLARIS_PF_PID) — never from external input.
                    eval "${pid_var}=$!"
                    echo "WATCHDOG: Restarted ${service} port-forward (PID ${!pid_var}) on ${port_mappings}" >&2
                fi
            done
        done
    ) &
    WATCHDOG_PID=$!
}

# Set up traps: cleanup port-forwards on EXIT, full cleanup on ERR
trap 'cleanup_port_forwards' EXIT
trap 'cleanup_all' ERR

# Verify all required Helm chart pods are running
echo "Verifying service readiness..."

# Critical services — MUST be running or tests will fail
wait_for_pod "app.kubernetes.io/name=floe-platform,app.kubernetes.io/component=postgresql" "PostgreSQL" 120
wait_for_pod "app.kubernetes.io/component=polaris" "Polaris" 120
wait_for_pod "app.kubernetes.io/name=dagster,component=dagster-webserver" "Dagster Webserver" 180

# Non-critical services — warn but continue
NON_CRITICAL_SERVICES=(
    "app.kubernetes.io/name=minio:MinIO"
    "app.kubernetes.io/name=otel:OTel Collector"
)
for entry in "${NON_CRITICAL_SERVICES[@]}"; do
    labels="${entry%%:*}"
    desc="${entry#*:}"
    if ! kubectl get pods -n "${TEST_NAMESPACE}" -l "${labels}" --no-headers 2>/dev/null | grep -q "Running"; then
        echo "WARNING: ${desc} may not be running (labels: ${labels})" >&2
    fi
done

# Clean up stale jobs from previous runs (crashed sessions leave pods
# in ContainerCreating that poison pod-health assertions)
echo "Cleaning up stale jobs from previous runs..."
kubectl delete jobs --all -n "${TEST_NAMESPACE}" --ignore-not-found --wait=true

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
    register_port_forward "${DAGSTER_HOST_PORT}" "${DAGSTER_HOST_PORT}:3000" "floe-platform-dagster-webserver" "DAGSTER_PF_PID"
fi

# Polaris catalog API (8181) + management health (8182)
if port_already_available 8181; then
    echo "  Polaris (8181): already available (NodePort)"
    # 8182 (management) may still need a port-forward even when 8181 has a NodePort
    if ! port_already_available 8182; then
        kubectl port-forward svc/floe-platform-polaris 8182:8182 -n "${TEST_NAMESPACE}" &
        POLARIS_PF_PID=$!
        register_port_forward 8182 "8182:8182" "floe-platform-polaris" "POLARIS_PF_PID"
    else
        echo "  Polaris mgmt (8182): already available (NodePort)"
    fi
else
    kubectl port-forward svc/floe-platform-polaris 8181:8181 8182:8182 -n "${TEST_NAMESPACE}" &
    POLARIS_PF_PID=$!
    register_port_forward 8181 "8181:8181 8182:8182" "floe-platform-polaris" "POLARIS_PF_PID"
fi

# MinIO API (port 9000 -> localhost:9000)
if port_already_available 9000; then
    echo "  MinIO API (9000): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-minio 9000:9000 -n "${TEST_NAMESPACE}" &
    MINIO_API_PF_PID=$!
    register_port_forward 9000 "9000:9000" "floe-platform-minio" "MINIO_API_PF_PID"
fi

# MinIO Console (port 9001 -> localhost:9001)
if port_already_available 9001; then
    echo "  MinIO Console (9001): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-minio 9001:9001 -n "${TEST_NAMESPACE}" &
    MINIO_UI_PF_PID=$!
    register_port_forward 9001 "9001:9001" "floe-platform-minio" "MINIO_UI_PF_PID"
fi

# OTel collector (port 4317 -> localhost:4317)
if port_already_available 4317; then
    echo "  OTel (4317): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-otel 4317:4317 -n "${TEST_NAMESPACE}" &
    OTEL_PF_PID=$!
    register_port_forward 4317 "4317:4317" "floe-platform-otel" "OTEL_PF_PID"
fi

# Marquez lineage service (if deployed)
# Note: Marquez API is on port 5000, admin is on port 5001
if kubectl get svc floe-platform-marquez -n "${TEST_NAMESPACE}" &>/dev/null; then
    MARQUEZ_HOST_PORT="${MARQUEZ_HOST_PORT:-5100}"
    if port_already_available "${MARQUEZ_HOST_PORT}"; then
        echo "  Marquez (${MARQUEZ_HOST_PORT}): already available (NodePort)"
    else
        kubectl port-forward svc/floe-platform-marquez "${MARQUEZ_HOST_PORT}":5000 -n "${TEST_NAMESPACE}" &
        MARQUEZ_PF_PID=$!
        register_port_forward "${MARQUEZ_HOST_PORT}" "${MARQUEZ_HOST_PORT}:5000" "floe-platform-marquez" "MARQUEZ_PF_PID"
    fi
fi

# Jaeger query service (if deployed)
# OrbStack can bind port 16686 to a stale container, causing silent failures.
# We kill any existing listener, establish a fresh port-forward, and health-check.
JAEGER_QUERY_PORT="${JAEGER_QUERY_PORT:-16686}"
if kubectl get svc floe-platform-jaeger-query -n "${TEST_NAMESPACE}" &>/dev/null; then
    # Kill any stale listener on the preferred port
    lsof -ti :"${JAEGER_QUERY_PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1  # allow port to be released

    if port_already_available "${JAEGER_QUERY_PORT}"; then
        echo "  Jaeger (${JAEGER_QUERY_PORT}): already available (NodePort)"
    else
        kubectl port-forward svc/floe-platform-jaeger-query "${JAEGER_QUERY_PORT}":16686 -n "${TEST_NAMESPACE}" &
        JAEGER_PF_PID=$!
        sleep 2  # allow port-forward to establish

        # Health check: verify Jaeger API is responsive
        if ! curl -sf "http://localhost:${JAEGER_QUERY_PORT}/api/services" >/dev/null 2>&1; then
            echo "WARNING: Jaeger health check failed on port ${JAEGER_QUERY_PORT}, retrying..." >&2
            kill "${JAEGER_PF_PID}" 2>/dev/null || true
            wait "${JAEGER_PF_PID}" 2>/dev/null || true
            sleep 1

            # Fallback: try alternative port if primary can't be freed
            if [[ "${JAEGER_QUERY_PORT}" == "16686" ]]; then
                JAEGER_QUERY_PORT=16687
                lsof -ti :"${JAEGER_QUERY_PORT}" | xargs kill -9 2>/dev/null || true
                sleep 1
            fi

            kubectl port-forward svc/floe-platform-jaeger-query "${JAEGER_QUERY_PORT}":16686 -n "${TEST_NAMESPACE}" &
            JAEGER_PF_PID=$!
            sleep 2

            if ! curl -sf "http://localhost:${JAEGER_QUERY_PORT}/api/services" >/dev/null 2>&1; then
                echo "ERROR: Jaeger health check failed on port ${JAEGER_QUERY_PORT} after retry" >&2
                # Non-fatal: Jaeger is optional for most tests
            fi
        fi
        # Only register watchdog if Jaeger health check ultimately succeeded
        if curl -sf "http://localhost:${JAEGER_QUERY_PORT}/api/services" >/dev/null 2>&1; then
            register_port_forward "${JAEGER_QUERY_PORT}" "${JAEGER_QUERY_PORT}:16686" "floe-platform-jaeger-query" "JAEGER_PF_PID"
        else
            echo "WARNING: Jaeger watchdog not registered — health check never passed" >&2
        fi
    fi
fi

# PostgreSQL (for direct DB access tests if needed)
if port_already_available 5432; then
    echo "  PostgreSQL (5432): already available (NodePort)"
else
    kubectl port-forward svc/floe-platform-postgresql 5432:5432 -n "${TEST_NAMESPACE}" &
    POSTGRES_PF_PID=$!
    register_port_forward 5432 "5432:5432" "floe-platform-postgresql" "POSTGRES_PF_PID"
fi

# Wait for ports to be available (either NodePort or port-forward)
wait_for_port localhost "${DAGSTER_HOST_PORT}" 15
wait_for_port localhost 8181 15
wait_for_port localhost 8182 15
wait_for_port localhost 9000 15
wait_for_port localhost 4317 15
# OTel Collector HTTP (non-critical — warn but continue)
if port_already_available 4318; then
    echo "  OTel HTTP (4318): Already available"
else
    echo "  WARNING: OTel HTTP (4318) not yet available — port-forward may be needed" >&2
fi
wait_for_port localhost 5432 15
wait_for_port localhost "${MARQUEZ_HOST_PORT:-5100}" 15 || true  # Marquez API port (optional)
wait_for_port localhost "${JAEGER_QUERY_PORT}" 15 || true  # Jaeger optional

echo "Port-forwards established."

# Start watchdog to monitor and restart dead port-forwards during test execution
start_port_forward_watchdog
echo "Port-forward watchdog started (${#WATCHDOG_ENTRIES[@]} ports monitored)"

# Verify MinIO bucket exists before running tests (defense-in-depth)
# Uses boto3 HeadBucket with credentials — anonymous curl returns 403 for both
# existing and non-existing buckets, making it useless for detection.
# The bucket should exist from defaultBuckets server startup, but we retry
# to handle the window between MinIO TCP-ready and API-ready.
MINIO_BUCKET="${MINIO_BUCKET:-${MANIFEST_BUCKET}}"
MINIO_URL="${MINIO_URL:-http://localhost:9000}"

# Fail fast on missing credentials — don't waste retry time on config errors
if [[ -z "${MINIO_USER}" ]] || [[ -z "${MINIO_PASS}" ]]; then
    echo "ERROR: MINIO_USER and MINIO_PASS must be set" >&2
    exit 1
fi

BUCKET_ATTEMPT=0
BUCKET_MAX_ATTEMPTS=10
echo "Verifying MinIO bucket '${MINIO_BUCKET}' via S3 API..."
while true; do
    BUCKET_ATTEMPT=$((BUCKET_ATTEMPT + 1))
    if uv run python3 "${SCRIPT_DIR}/ensure-bucket.py" "${MINIO_URL}" "${MINIO_BUCKET}"; then
        echo "MinIO bucket '${MINIO_BUCKET}' ready"
        break
    fi
    if [[ $BUCKET_ATTEMPT -ge $BUCKET_MAX_ATTEMPTS ]]; then
        echo "ERROR: MinIO bucket '${MINIO_BUCKET}' not available after ${BUCKET_MAX_ATTEMPTS} attempts" >&2
        echo "Check MinIO pod status: kubectl get pods -n floe-test -l app.kubernetes.io/name=minio" >&2
        exit 1
    fi
    echo "  Attempt ${BUCKET_ATTEMPT}/${BUCKET_MAX_ATTEMPTS} - bucket not ready, waiting 3s..."
    sleep 3
done

# Verify Polaris catalog exists (defense-in-depth for bootstrap job failures)
POLARIS_CATALOG="${POLARIS_CATALOG:-${MANIFEST_WAREHOUSE}}"
POLARIS_CLIENT_ID="${POLARIS_CLIENT_ID:-${MANIFEST_OAUTH_CLIENT_ID}}"
POLARIS_CLIENT_SECRET="${POLARIS_CLIENT_SECRET:-}"

# Validate catalog name to prevent URL injection
if [[ ! "${POLARIS_CATALOG}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "ERROR: Invalid catalog name format: '${POLARIS_CATALOG}'" >&2
    exit 1
fi

echo "Verifying Polaris catalog '${POLARIS_CATALOG}'..."

# Acquire OAuth token — pipe credentials via stdin (-d @-) to avoid
# exposing them in process arguments (visible in ps aux).
POLARIS_TOKEN=$(printf 'grant_type=client_credentials&client_id=%s&client_secret=%s&scope=PRINCIPAL_ROLE:ALL' \
    "${POLARIS_CLIENT_ID}" "${POLARIS_CLIENT_SECRET}" | \
    curl -s -X POST \
    "http://localhost:8181/api/catalog/v1/oauth/tokens" \
    -d @- \
    2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))") || true

if [[ -z "${POLARIS_TOKEN}" ]]; then
    echo "ERROR: Failed to acquire Polaris OAuth token" >&2
    exit 1
fi

# Check if catalog exists
CATALOG_CODE=$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer ${POLARIS_TOKEN}" \
    "http://localhost:8181/api/management/v1/catalogs/${POLARIS_CATALOG}" 2>/dev/null) || true

if [[ "${CATALOG_CODE}" == "404" ]]; then
    echo "WARNING: Polaris catalog fallback triggered — catalog '${POLARIS_CATALOG}' not found" >&2
    echo "WARNING: Bootstrap hook may have failed. Check bootstrap job logs:" >&2
    echo "WARNING:   kubectl logs -n ${TEST_NAMESPACE} -l job-name=floe-platform-bootstrap --tail=50" >&2
    echo "Polaris catalog '${POLARIS_CATALOG}' not found — creating..." >&2
    # Build JSON payload with python3 to safely escape special characters.
    # Credentials read from environment (MINIO_USER, MINIO_PASS) to avoid
    # exposing them in process arguments (visible in ps aux).
    CATALOG_JSON=$(python3 -c "
import json, os, sys
MINIO_ENDPOINT = 'http://floe-platform-minio:9000'
minio_user = os.environ.get('MINIO_USER', '')
minio_pass = os.environ.get('MINIO_PASS', '')
manifest_region = os.environ.get('MANIFEST_REGION', 'us-east-1')
manifest_path_style = os.environ.get('MANIFEST_PATH_STYLE_ACCESS', 'true')
payload = {
    'catalog': {
        'name': sys.argv[1],
        'type': 'INTERNAL',
        'properties': {
            'default-base-location': f's3://{sys.argv[2]}',
            's3.endpoint': MINIO_ENDPOINT,
            's3.path-style-access': manifest_path_style,
            's3.access-key-id': minio_user,
            's3.secret-access-key': minio_pass,
            's3.region': manifest_region,
            'table-default.s3.endpoint': MINIO_ENDPOINT,
            'table-default.s3.path-style-access': manifest_path_style,
            'table-default.s3.access-key-id': minio_user,
            'table-default.s3.secret-access-key': minio_pass,
            'table-default.s3.region': manifest_region,
        },
        'storageConfigInfo': {
            'storageType': 'S3',
            'allowedLocations': [f's3://{sys.argv[2]}'],
            'endpoint': MINIO_ENDPOINT,
            'endpointInternal': MINIO_ENDPOINT,
            'pathStyleAccess': manifest_path_style == 'true',
            'region': manifest_region,
            'stsUnavailable': True,
        },
    }
}
print(json.dumps(payload))
" "${POLARIS_CATALOG}" "${MINIO_BUCKET}")

    POLARIS_TMP=$(mktemp)
    CREATE_CODE=$(printf '%s' "${CATALOG_JSON}" | curl -s -o "${POLARIS_TMP}" -w '%{http_code}' -X POST \
        -H "Authorization: Bearer ${POLARIS_TOKEN}" \
        -H "Content-Type: application/json" \
        "http://localhost:8181/api/management/v1/catalogs" \
        -d @- 2>/dev/null) || true

    if [[ "${CREATE_CODE}" == "200" ]] || [[ "${CREATE_CODE}" == "201" ]]; then
        echo "Polaris catalog '${POLARIS_CATALOG}' created successfully"
    elif [[ "${CREATE_CODE}" == "409" ]]; then
        echo "Polaris catalog '${POLARIS_CATALOG}' already exists (race condition) — OK"
    else
        echo "ERROR: Failed to create Polaris catalog (HTTP ${CREATE_CODE})" >&2
        cat "${POLARIS_TMP}" >&2 2>/dev/null || true
        rm -f "${POLARIS_TMP}"
        exit 1
    fi
    rm -f "${POLARIS_TMP}"
elif [[ "${CATALOG_CODE}" == "200" ]]; then
    echo "Polaris catalog '${POLARIS_CATALOG}' exists (HTTP 200)"
else
    echo "ERROR: Unexpected response checking Polaris catalog (HTTP ${CATALOG_CODE})" >&2
    exit 1
fi

echo "Installing pyiceberg[s3fs]==0.11.1..."
uv pip install "pyiceberg[s3fs]==0.11.1" 2>&1 || {
    echo "ERROR: PyIceberg install failed -- E2E tests WILL fail" >&2
    exit 1
}

# Export canonical {SERVICE}_PORT env vars for Python port resolution
# (testing.fixtures.services.get_effective_port reads these).
# Both dagster aliases get the same host-mapped port so tests using either
# name resolve correctly.
export DAGSTER_WEBSERVER_PORT="${DAGSTER_HOST_PORT}"
export DAGSTER_PORT="${DAGSTER_HOST_PORT}"
export MARQUEZ_PORT="${MARQUEZ_HOST_PORT:-5100}"
export JAEGER_QUERY_PORT="${JAEGER_QUERY_PORT}"

echo ""
echo "Running E2E tests..."

# Run E2E tests
DAGSTER_URL="http://localhost:${DAGSTER_HOST_PORT}" \
uv run pytest \
    tests/e2e/ \
    -v \
    --tb=short \
    --timeout="${E2E_TIMEOUT}" \
    "$@"

echo ""
echo "E2E tests completed successfully!"
