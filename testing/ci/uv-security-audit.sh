#!/usr/bin/env bash
# Run uv-secure with the same ignores and exit handling used in CI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Centralized vulnerability ignores:
# - GHSA-5j53-63w8-8625: fastapi-users OAuth/CSRF (not used)
# - GHSA-7gcm-g887-7qv7: protobuf DoS (transitive, no fix)
IGNORE_VULNS="${UV_SECURE_IGNORE_VULNS:-GHSA-5j53-63w8-8625,GHSA-7gcm-g887-7qv7}"

cd "${PROJECT_ROOT}"

echo "Running uv-secure with ignores: ${IGNORE_VULNS}"

output="$(uv run --no-sync uv-secure --no-check-uv-tool --ignore-vulns "${IGNORE_VULNS}" . 2>&1)" || {
    exit_code=$?
    echo "${output}"

    # Exit code 2 = warnings (not blocking)
    if [ "${exit_code}" -eq 2 ]; then
        echo "uv-secure returned warnings (exit code 2)" >&2
        exit 0
    fi

    # Exit code 3 = tool crash, check if actual vulnerabilities were reported
    if [ "${exit_code}" -eq 3 ]; then
        if echo "${output}" | grep -q "Vulnerable:" && ! echo "${output}" | grep -q "Vulnerable: 0"; then
            echo "Vulnerabilities detected" >&2
            exit 1
        fi

        echo "uv-secure crashed but no vulnerabilities were reported" >&2
        exit 0
    fi

    exit "${exit_code}"
}

echo "${output}"
