#!/usr/bin/env bash
# Targeted Specwright integration dispatcher.
#
# This wrapper keeps Specwright's integration phase deterministic: structural
# units can skip cleanly, while change surfaces with a known focused proof can
# dispatch to that proof without hardwiring a stale one-size-fits-all command.
#
# Environment overrides:
#   SPECWRIGHT_INTEGRATION_PROFILE    Explicit profile name (overrides auto-detect)
#   SPECWRIGHT_CHANGED_FILES          Newline-delimited file list for tests/debugging
#   SPECWRIGHT_INTEGRATION_DRY_RUN=1  Print the selected profile/command only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=./common.sh
source "${SCRIPT_DIR}/common.sh"

UNIT_C_DEVPOD_BOUNDARY_TRIGGER_PATTERN='^(testing/ci/(common\.sh|test-e2e-cluster\.sh|test-unit-c-boundary\.sh)|testing/k8s/setup-cluster\.sh|testing/k8s/flux/[^/]+\.yaml|tests/integration/test_unit_c_devpod_flux_boundary\.py|tests/unit/test_unit_c_boundary_wrapper\.py|scripts/devpod-ensure-ready\.sh|\.devcontainer/hetzner/postStartCommand\.sh)$'

resolve_changed_files() {
    if [[ -n "${SPECWRIGHT_CHANGED_FILES:-}" ]]; then
        printf '%s\n' "${SPECWRIGHT_CHANGED_FILES}"
        return 0
    fi

    local merge_base=""
    if git -C "${PROJECT_ROOT}" rev-parse --verify origin/main >/dev/null 2>&1; then
        merge_base="$(git -C "${PROJECT_ROOT}" merge-base HEAD origin/main 2>/dev/null || true)"
    elif git -C "${PROJECT_ROOT}" rev-parse --verify main >/dev/null 2>&1; then
        merge_base="$(git -C "${PROJECT_ROOT}" merge-base HEAD main 2>/dev/null || true)"
    fi

    if [[ -n "${merge_base}" ]]; then
        git -C "${PROJECT_ROOT}" diff --name-only "${merge_base}" HEAD
        return 0
    fi

    git -C "${PROJECT_ROOT}" diff --name-only HEAD~1 HEAD 2>/dev/null || true
}

detect_profile() {
    local changed_files="$1"

    if printf '%s\n' "${changed_files}" | grep -Eq \
        "${UNIT_C_DEVPOD_BOUNDARY_TRIGGER_PATTERN}"; then
        printf '%s\n' "unit-c-devpod-boundary"
        return 0
    fi

    printf '%s\n' "none"
}

run_profile() {
    local profile="$1"
    shift

    case "${profile}" in
        none)
            echo "[INFO] No targeted Specwright integration suite matched the current change surface; skipping integration gate."
            return 0
            ;;
        unit-c-devpod-boundary)
            local cmd=(
                uv run pytest -q
                tests/integration/test_unit_c_devpod_flux_boundary.py
                "$@"
            )

            if [[ "${SPECWRIGHT_INTEGRATION_DRY_RUN:-0}" == "1" ]]; then
                printf '[INFO] Selected profile: %s\n' "${profile}"
                printf '[INFO] Command:'
                printf ' %q' "${cmd[@]}"
                printf '\n'
                return 0
            fi

            printf '[INFO] Selected profile: %s\n' "${profile}"
            "${cmd[@]}"
            return $?
            ;;
        *)
            echo "[ERROR] Unknown Specwright integration profile '${profile}'." >&2
            echo "[ERROR] Supported profiles: none, unit-c-devpod-boundary" >&2
            return 2
            ;;
    esac
}

cd "${PROJECT_ROOT}"

profile="${SPECWRIGHT_INTEGRATION_PROFILE:-}"
if [[ -z "${profile}" ]]; then
    changed_files="$(resolve_changed_files)"
    profile="$(detect_profile "${changed_files}")"
fi

run_profile "${profile}" "$@"
