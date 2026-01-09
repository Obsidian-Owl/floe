#!/bin/bash
# Unit test runner script for CI
# Runs all unit tests with coverage reporting
#
# Usage: ./testing/ci/test-unit.sh [pytest-args...]
#
# Environment:
#   COVERAGE_THRESHOLD  Minimum coverage percentage (default: 80)
#   COVERAGE_REPORT     Coverage report format: xml, html, term (default: xml)

set -euo pipefail

# Configuration
COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-80}"
COVERAGE_REPORT="${COVERAGE_REPORT:-xml}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${PROJECT_ROOT}"

echo "Running unit tests..."
echo "Coverage threshold: ${COVERAGE_THRESHOLD}%"
echo "Coverage report: ${COVERAGE_REPORT}"
echo ""

# Build coverage report flags
COVERAGE_FLAGS="--cov=packages/floe-core/src"
case "${COVERAGE_REPORT}" in
    xml)
        COVERAGE_FLAGS="${COVERAGE_FLAGS} --cov-report=xml:coverage.xml"
        ;;
    html)
        COVERAGE_FLAGS="${COVERAGE_FLAGS} --cov-report=html:coverage_html"
        ;;
    term)
        COVERAGE_FLAGS="${COVERAGE_FLAGS} --cov-report=term-missing"
        ;;
    *)
        COVERAGE_FLAGS="${COVERAGE_FLAGS} --cov-report=xml:coverage.xml --cov-report=term-missing"
        ;;
esac

# Run unit tests
# shellcheck disable=SC2086
uv run pytest \
    packages/floe-core/tests/unit/ \
    testing/tests/unit/ \
    tests/contract/ \
    -v \
    ${COVERAGE_FLAGS} \
    --cov-fail-under="${COVERAGE_THRESHOLD}" \
    "$@"

echo ""
echo "Unit tests completed successfully!"
