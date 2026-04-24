#!/usr/bin/env bash
# Validate dbt plugin version requirements for CI and local pre-push hooks.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

echo "Validating dbt plugin version requirements..."

# Check floe-dbt-core requires dbt-core>=1.6,<2.0 (NFR-003)
core_dep="$(grep -E '"dbt-core.*"' plugins/floe-dbt-core/pyproject.toml || true)"
if [[ -z "${core_dep}" ]]; then
    echo "ERROR: floe-dbt-core must depend on dbt-core" >&2
    exit 1
fi

if ! echo "${core_dep}" | grep -qE '>=1\.6.*<2\.0'; then
    echo "ERROR: floe-dbt-core must require dbt-core>=1.6,<2.0" >&2
    echo "Current: ${core_dep}" >&2
    echo "Required: dbt-core>=1.6,<2.0 (NFR-003)" >&2
    exit 1
fi

echo "✓ floe-dbt-core: ${core_dep}"

# Check floe-dbt-fusion requires dbt Fusion CLI >=1.0 (NFR-004)
# Note: Fusion is a CLI binary, not a Python dependency
fusion_check="$(grep -E 'MIN_FUSION_VERSION|>=.*1\.0' plugins/floe-dbt-fusion/src/floe_dbt_fusion/detection.py || true)"
if [[ -z "${fusion_check}" ]]; then
    echo "WARNING: Could not verify Fusion version check in detection.py" >&2
else
    echo "✓ floe-dbt-fusion: Fusion version check found"
fi

echo "dbt version requirements validated"
