#!/usr/bin/env bash
# Run uv-secure with the same ignores and exit handling used in CI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Centralized vulnerability ignores:
# - GHSA-w8v5-vhqr-4h9v: diskcache 5.6.3 has no patched version as of 2026-04-28.
#   Agent-memory is a devtool-only optional component, not installed in runtime
#   platform images. Revisit before beta or when a patched release exists.
IGNORE_VULNS="${UV_SECURE_IGNORE_VULNS:-GHSA-w8v5-vhqr-4h9v}"

cd "${PROJECT_ROOT}"

echo "Running uv-secure with ignores: ${IGNORE_VULNS}"

uv_secure_reported_vulnerabilities() {
    grep -Eq "Vulnerable:[[:space:]]*[1-9][0-9]*" <<< "$1"
}

uv_secure_invocation_failed() {
    grep -Eiq "(Failed to spawn|No such file or directory|not found|ModuleNotFoundError|ImportError)" <<< "$1"
}

output="$(uv run --no-sync uv-secure --no-check-uv-tool --ignore-vulns "${IGNORE_VULNS}" . 2>&1)" || {
    exit_code=$?
    echo "${output}"

    if uv_secure_invocation_failed "${output}"; then
        echo "uv-secure invocation or configuration failed" >&2
        exit 1
    fi

    if uv_secure_reported_vulnerabilities "${output}"; then
        echo "Vulnerabilities detected" >&2
        exit 1
    fi

    # Exit code 2 = warnings (not blocking)
    if [[ "${exit_code}" -eq 2 ]]; then
        echo "uv-secure returned warnings (exit code 2)" >&2
        exit 0
    fi

    # Exit code 3 = tool crash, check if actual vulnerabilities were reported
    if [[ "${exit_code}" -eq 3 ]]; then
        echo "uv-secure crashed but no vulnerabilities were reported" >&2
        exit 0
    fi

    exit "${exit_code}"
}

echo "${output}"
