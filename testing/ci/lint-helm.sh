#!/bin/bash
# Helm chart linting script
# Strips Dagster subchart schema (external $ref 404 workaround) before linting
#
# Usage: ./testing/ci/lint-helm.sh
#
# This script mirrors the CI helm-lint job so local and CI checks stay aligned.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

echo "=== Helm Chart Lint ==="
echo ""

# Check helm is installed
if ! command -v helm &> /dev/null; then
    echo "ERROR: helm is not installed" >&2
    exit 1
fi

# Update dependencies
echo "Updating chart dependencies..."
helm dependency update charts/floe-platform 2>&1 | tail -3
helm dependency update charts/floe-jobs 2>&1 | tail -3
echo ""

# Strip Dagster subchart schema (404 external $ref workaround)
echo "Stripping Dagster subchart schema (external \$ref 404 workaround)..."
cd charts/floe-platform/charts
if ls dagster-*.tgz 1>/dev/null 2>&1; then
    mkdir -p dagster-tmp
    tar xzf dagster-*.tgz -C dagster-tmp
    rm -f dagster-tmp/dagster/values.schema.json
    DAGSTER_TGZ=$(ls dagster-*.tgz)
    rm "$DAGSTER_TGZ"
    cd dagster-tmp && COPYFILE_DISABLE=1 tar czf "../${DAGSTER_TGZ}" dagster/ && cd ..
    rm -rf dagster-tmp
    echo "  Done"
else
    echo "  No Dagster subchart found, skipping"
fi
cd "${PROJECT_ROOT}"
echo ""

# Lint charts
FAILED=0

echo "Linting floe-platform..."
if ! helm lint charts/floe-platform --values charts/floe-platform/values.yaml; then
    FAILED=1
fi

echo ""
echo "Linting floe-platform (test values)..."
if ! helm lint charts/floe-platform --values charts/floe-platform/values-test.yaml; then
    FAILED=1
fi

echo ""
echo "Linting floe-jobs..."
if ! helm lint charts/floe-jobs --values charts/floe-jobs/values.yaml; then
    FAILED=1
fi

echo ""
echo "Linting floe-jobs (test values)..."
if ! helm lint charts/floe-jobs --values charts/floe-jobs/values-test.yaml; then
    FAILED=1
fi

echo ""
if [[ "${FAILED}" -eq 1 ]]; then
    echo "FAILED: One or more charts failed linting" >&2
    exit 1
fi

echo "All charts passed linting"
