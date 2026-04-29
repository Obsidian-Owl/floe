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
MAX_ATTEMPTS="${UV_SECURE_MAX_ATTEMPTS:-3}"
PIP_AUDIT_IGNORE_VULNS="${PIP_AUDIT_IGNORE_VULNS:-${IGNORE_VULNS},GHSA-5j53-63w8-8625,GHSA-7gcm-g887-7qv7,GHSA-gc5v-m9x4-r6x2}"

cd "${PROJECT_ROOT}"

echo "Running uv-secure with ignores: ${IGNORE_VULNS}"

if [[ ! "${MAX_ATTEMPTS}" =~ ^[0-9]+$ ]] || [[ "${MAX_ATTEMPTS}" -lt 1 ]]; then
    echo "Invalid UV_SECURE_MAX_ATTEMPTS='${MAX_ATTEMPTS}'" >&2
    exit 1
fi

uv_secure_reported_vulnerabilities() {
    grep -Eq "Vulnerable:[[:space:]]*[1-9][0-9]*" <<< "$1"
}

uv_secure_invocation_failed() {
    grep -Eiq "(Failed to spawn|No such file or directory|not found|ModuleNotFoundError|ImportError)" <<< "$1"
}

run_pip_audit_fallback() {
    local export_file audit_file
    export_file="$(mktemp)"
    audit_file="$(mktemp)"
    trap 'rm -f "${export_file}" "${audit_file}"' RETURN

    echo "uv-secure did not complete; running pip-audit fallback over exported uv.lock" >&2
    uv export \
        --frozen \
        --all-packages \
        --all-groups \
        --no-hashes \
        --no-emit-project \
        --no-emit-workspace \
        --output-file "${export_file}" >/dev/null

    # pip-audit cannot derive versions for local editable workspace members.
    # uv-secure remains the primary lockfile scanner; this fallback audits the
    # pinned third-party package set when uv-secure crashes before analysis.
    grep -Ev '^-e[[:space:]]+' "${export_file}" > "${audit_file}"

    local pip_audit_args=(
        uv run --no-sync pip-audit
        --requirement "${audit_file}"
        --no-deps
        --disable-pip
        --progress-spinner off
    )
    local old_ifs="${IFS}"
    IFS=","
    read -r -a ignore_ids <<< "${PIP_AUDIT_IGNORE_VULNS}"
    IFS="${old_ifs}"
    for ignore_id in "${ignore_ids[@]}"; do
        if [[ -n "${ignore_id}" ]]; then
            pip_audit_args+=(--ignore-vuln "${ignore_id}")
        fi
    done

    "${pip_audit_args[@]}"
}

attempt=1
while [[ "${attempt}" -le "${MAX_ATTEMPTS}" ]]; do
    output="$(uv run --no-sync uv-secure --no-check-uv-tool --ignore-vulns "${IGNORE_VULNS}" . 2>&1)" && {
        echo "${output}"
        exit 0
    }
    exit_code=$?

    if uv_secure_invocation_failed "${output}"; then
        echo "${output}"
        echo "uv-secure invocation or configuration failed" >&2
        exit 1
    fi

    if uv_secure_reported_vulnerabilities "${output}"; then
        echo "${output}"
        echo "Vulnerabilities detected" >&2
        exit 1
    fi

    # Exit code 2 = warnings (not blocking)
    if [[ "${exit_code}" -eq 2 ]]; then
        echo "${output}"
        echo "uv-secure returned warnings (exit code 2)" >&2
        exit 0
    fi

    # Exit code 3 = scanner runtime error. Retry transient package metadata
    # download failures, but fail closed if the scanner never completes.
    if [[ "${exit_code}" -eq 3 ]]; then
        echo "${output}"
        if [[ "${attempt}" -lt "${MAX_ATTEMPTS}" ]]; then
            echo "uv-secure scanner crashed on attempt ${attempt}/${MAX_ATTEMPTS}; retrying" >&2
            attempt=$((attempt + 1))
            continue
        fi
        echo "uv-secure scanner crashed after ${MAX_ATTEMPTS} attempts" >&2
        run_pip_audit_fallback
        exit $?
    fi

    exit "${exit_code}"
done
