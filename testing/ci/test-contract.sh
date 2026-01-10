#!/bin/bash
# Contract test runner script for CI
# Runs cross-package contract tests that validate API stability
#
# Usage: ./testing/ci/test-contract.sh [pytest-args...]
#
# Contract tests validate:
# - Cross-package interfaces (e.g., floe-core to floe-catalog-polaris)
# - Plugin ABC compliance
# - CompiledArtifacts schema stability
#
# Note: Contract tests run separately from unit tests because they:
# - Import from multiple packages
# - Have different fixture requirements (OTel reset)
# - Test API contracts, not implementation details

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

echo "Running contract tests..."
echo ""

if [[ ! -d "tests/contract" ]]; then
    echo "No contract tests found at tests/contract/"
    exit 0
fi

# Run contract tests
uv run pytest \
    tests/contract \
    -v \
    "$@"

echo ""
echo "Contract tests completed successfully!"
