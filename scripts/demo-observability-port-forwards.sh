#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${FLOE_DEMO_NAMESPACE:-floe-dev}"
RELEASE="${FLOE_DEMO_RELEASE:-floe-platform}"
PIDS_FILE="${FLOE_DEMO_PIDS_FILE:-.demo-pids}"
LOG_FILE="${FLOE_DEMO_PORT_FORWARD_LOG:-.demo-port-forwards.log}"
LOKI_PORT="${FLOE_DEMO_LOKI_PORT:-3101}"
PROMETHEUS_PORT="${FLOE_DEMO_PROMETHEUS_PORT:-9090}"

KUBECTL=(kubectl)
if [[ -n "${KUBECONFIG:-}" ]]; then
  KUBECTL+=(--kubeconfig "${KUBECONFIG}")
fi

STARTED_PIDS=()

cleanup_started_forwards() {
  local status=$?
  if [[ "${status}" -eq 0 ]]; then
    return
  fi
  for pid in "${STARTED_PIDS[@]}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  if [[ -f "${PIDS_FILE}" && "${#STARTED_PIDS[@]}" -gt 0 ]]; then
    local tmp_file
    tmp_file="$(mktemp)"
    grep -vxF -f <(printf "%s\n" "${STARTED_PIDS[@]}") "${PIDS_FILE}" >"${tmp_file}" || true
    mv "${tmp_file}" "${PIDS_FILE}"
  fi
}
trap cleanup_started_forwards EXIT

local_port_open() {
  local port="$1"
  (echo >"/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1
}

start_forward() {
  local label="$1"
  local service="$2"
  local local_port="$3"
  local remote_port="$4"

  if local_port_open "${local_port}"; then
    echo "ERROR: ${label} local port ${local_port} is already in use; refusing to validate against a pre-existing listener" >&2
    exit 1
  fi

  "${KUBECTL[@]}" port-forward "svc/${service}" "${local_port}:${remote_port}" \
    -n "${NAMESPACE}" >>"${LOG_FILE}" 2>&1 &
  local pid=$!
  STARTED_PIDS+=("${pid}")
  echo "${pid}" >>"${PIDS_FILE}"

  for _ in $(seq 1 30); do
    if ! kill -0 "${pid}" 2>/dev/null; then
      echo "ERROR: ${label} port-forward process exited before binding localhost:${local_port}; see ${LOG_FILE}" >&2
      exit 1
    fi
    if local_port_open "${local_port}"; then
      return
    fi
    sleep 1
  done

  echo "ERROR: ${label} did not accept TCP connections on localhost:${local_port} after 30s; see ${LOG_FILE}" >&2
  exit 1
}

"${KUBECTL[@]}" rollout status "deployment/${RELEASE}-loki" \
  -n "${NAMESPACE}" --timeout=180s >/dev/null
"${KUBECTL[@]}" rollout status "deployment/${RELEASE}-prometheus" \
  -n "${NAMESPACE}" --timeout=180s >/dev/null

start_forward "Loki" "${RELEASE}-loki" "${LOKI_PORT}" "3100"
start_forward "Prometheus" "${RELEASE}-prometheus" "${PROMETHEUS_PORT}" "9090"
