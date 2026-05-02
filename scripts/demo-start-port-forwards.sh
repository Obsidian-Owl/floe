#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${FLOE_DEMO_NAMESPACE:-floe-dev}"
RELEASE="${FLOE_DEMO_RELEASE:-floe-platform}"
PIDS_FILE="${FLOE_DEMO_PIDS_FILE:-.demo-pids}"
LOG_FILE="${FLOE_DEMO_PORT_FORWARD_LOG:-.demo-port-forwards.log}"

DAGSTER_HOST_PORT="${FLOE_DEMO_DAGSTER_PORT:-3100}"
POLARIS_API_PORT="${FLOE_DEMO_POLARIS_API_PORT:-8181}"
POLARIS_MGMT_PORT="${FLOE_DEMO_POLARIS_MGMT_PORT:-8182}"
MINIO_API_PORT="${FLOE_DEMO_MINIO_API_PORT:-9000}"
MINIO_CONSOLE_PORT="${FLOE_DEMO_MINIO_CONSOLE_PORT:-9001}"
JAEGER_PORT="${FLOE_DEMO_JAEGER_PORT:-16686}"
MARQUEZ_PORT="${FLOE_DEMO_MARQUEZ_PORT:-5100}"
OTEL_GRPC_PORT="${FLOE_DEMO_OTEL_GRPC_PORT:-4317}"
OTEL_HTTP_PORT="${FLOE_DEMO_OTEL_HTTP_PORT:-4318}"

KUBECTL=(kubectl)
if [[ -n "${KUBECONFIG:-}" ]]; then
    KUBECTL+=(--kubeconfig "${KUBECONFIG}")
fi

stop_existing() {
    if [[ -f "${PIDS_FILE}" ]]; then
        kill $(cat "${PIDS_FILE}") 2>/dev/null || true
        rm -f "${PIDS_FILE}"
    fi
}

cleanup_on_error() {
    local rc=$?
    if [[ ${rc} -ne 0 ]]; then
        stop_existing
        echo "Port-forward startup failed. See ${LOG_FILE} for kubectl output." >&2
    fi
    exit "${rc}"
}
trap cleanup_on_error EXIT

start_port_forward() {
    local service=$1
    shift
    "${KUBECTL[@]}" port-forward "svc/${service}" "$@" -n "${NAMESPACE}" >>"${LOG_FILE}" 2>&1 &
    echo $! >>"${PIDS_FILE}"
}

wait_for_tcp() {
    local host=$1 port=$2 label=$3 timeout=${4:-30}
    for _ in $(seq 1 "${timeout}"); do
        if (echo >/dev/tcp/"${host}"/"${port}") 2>/dev/null; then
            return 0
        fi
        sleep 1
    done
    echo "ERROR: ${label} did not accept TCP connections on ${host}:${port} after ${timeout}s" >&2
    return 1
}

wait_for_http() {
    local url=$1 label=$2 timeout=${3:-60}
    for _ in $(seq 1 "${timeout}"); do
        if curl -fsS --connect-timeout 2 --max-time 5 "${url}" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    echo "ERROR: ${label} did not become healthy at ${url} after ${timeout}s" >&2
    return 1
}

stop_existing
: >"${LOG_FILE}"

"${KUBECTL[@]}" wait --for=condition=ready pod \
    -l "app.kubernetes.io/instance=${RELEASE}" \
    -n "${NAMESPACE}" \
    --timeout=180s >/dev/null

start_port_forward "${RELEASE}-dagster-webserver" "${DAGSTER_HOST_PORT}:3000"
start_port_forward "${RELEASE}-polaris" "${POLARIS_API_PORT}:8181" "${POLARIS_MGMT_PORT}:8182"
start_port_forward "${RELEASE}-minio" "${MINIO_API_PORT}:9000" "${MINIO_CONSOLE_PORT}:9001"
start_port_forward "${RELEASE}-jaeger-query" "${JAEGER_PORT}:16686"
start_port_forward "${RELEASE}-marquez" "${MARQUEZ_PORT}:5000"
start_port_forward "${RELEASE}-otel" "${OTEL_GRPC_PORT}:4317" "${OTEL_HTTP_PORT}:4318"

wait_for_http "http://localhost:${DAGSTER_HOST_PORT}/server_info" "Dagster"
wait_for_tcp localhost "${POLARIS_API_PORT}" "Polaris"
wait_for_tcp localhost "${POLARIS_MGMT_PORT}" "Polaris management"
wait_for_tcp localhost "${MINIO_API_PORT}" "MinIO API"
wait_for_tcp localhost "${MINIO_CONSOLE_PORT}" "MinIO console"
wait_for_http "http://localhost:${JAEGER_PORT}/api/services" "Jaeger" 30
wait_for_tcp localhost "${MARQUEZ_PORT}" "Marquez"
wait_for_tcp localhost "${OTEL_GRPC_PORT}" "OTel gRPC"
wait_for_tcp localhost "${OTEL_HTTP_PORT}" "OTel HTTP"
