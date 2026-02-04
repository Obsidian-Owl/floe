#!/usr/bin/env bash
# PreToolUse hook: block direct pytest tests/e2e/ if port-forwards are missing.
# Reads TOOL_INPUT JSON from stdin, checks required ports.
set -euo pipefail

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only care about pytest commands targeting tests/e2e
if ! echo "$CMD" | grep -qE 'pytest.*tests/e2e'; then
  exit 0
fi

# Whitelist: make test-e2e manages its own port-forwards
if echo "$CMD" | grep -qE 'make\s+test-e2e'; then
  exit 0
fi

# Required ports: Polaris, Dagster, MinIO, Jaeger, Marquez
declare -A PORTS=(
  [Polaris]=8181
  [Dagster]=3000
  [MinIO]=9000
  [Jaeger]=16686
  [Marquez]=5000
)

MISSING=()
for SVC in "${!PORTS[@]}"; do
  if ! nc -z localhost "${PORTS[$SVC]}" 2>/dev/null; then
    MISSING+=("$SVC:${PORTS[$SVC]}")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "BLOCKED: E2E port-forwards missing for: ${MISSING[*]}" >&2
  echo "Use 'make test-e2e' which manages port-forwards automatically." >&2
  exit 2
fi

exit 0
