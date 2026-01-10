#!/bin/bash
# Unit test runner script for CI
# Runs all unit tests with coverage reporting
#
# Usage: ./testing/ci/test-unit.sh [pytest-args...]
#
# Environment:
#   COVERAGE_THRESHOLD  Minimum coverage percentage (default: 80)
#   COVERAGE_REPORT     Coverage report format: xml, html, term (default: xml)
#   PYTHON_VERSION      Python version suffix for coverage file (e.g., "3.10" -> coverage-3.10.xml)
#
# Note: This script dynamically discovers all packages with tests.
#       New packages are automatically included when they have a tests/unit/ directory.

set -euo pipefail

# Configuration
COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-80}"
COVERAGE_REPORT="${COVERAGE_REPORT:-xml}"
PYTHON_VERSION="${PYTHON_VERSION:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Coverage file name (optionally include Python version)
if [[ -n "${PYTHON_VERSION}" ]]; then
    COVERAGE_FILE="coverage-${PYTHON_VERSION}.xml"
else
    COVERAGE_FILE="coverage.xml"
fi

cd "${PROJECT_ROOT}"

echo "Running unit tests..."
echo "Coverage threshold: ${COVERAGE_THRESHOLD}%"
echo "Coverage report: ${COVERAGE_REPORT}"
echo ""

# Dynamically discover all packages with unit tests
UNIT_TEST_PATHS=""
COVERAGE_SOURCES=""

# Discover packages
for pkg_dir in packages/*/; do
    pkg_name=$(basename "${pkg_dir}")
    unit_test_dir="${pkg_dir}tests/unit"
    if [[ -d "${unit_test_dir}" ]]; then
        echo "  Found: ${unit_test_dir}"
        UNIT_TEST_PATHS="${UNIT_TEST_PATHS} ${unit_test_dir}"
        COVERAGE_SOURCES="${COVERAGE_SOURCES} --cov=${pkg_dir}src"
    fi
done

# Discover plugins
for plugin_dir in plugins/*/; do
    if [[ -d "${plugin_dir}" ]]; then
        plugin_name=$(basename "${plugin_dir}")
        unit_test_dir="${plugin_dir}tests/unit"
        if [[ -d "${unit_test_dir}" ]]; then
            echo "  Found: ${unit_test_dir}"
            UNIT_TEST_PATHS="${UNIT_TEST_PATHS} ${unit_test_dir}"
            COVERAGE_SOURCES="${COVERAGE_SOURCES} --cov=${plugin_dir}src"
        fi
    fi
done

# Always include testing module tests
# Note: Contract tests are NOT included here - they run separately via test-contract.sh
# because they test cross-package contracts and have different fixture requirements
if [[ -d "testing/tests/unit" ]]; then
    echo "  Found: testing/tests/unit"
    UNIT_TEST_PATHS="${UNIT_TEST_PATHS} testing/tests/unit"
fi

echo ""

if [[ -z "${UNIT_TEST_PATHS}" ]]; then
    echo "ERROR: No test directories found" >&2
    exit 1
fi

# Build coverage report flags
COVERAGE_FLAGS="${COVERAGE_SOURCES}"
case "${COVERAGE_REPORT}" in
    xml)
        COVERAGE_FLAGS="${COVERAGE_FLAGS} --cov-report=xml:${COVERAGE_FILE}"
        ;;
    html)
        COVERAGE_FLAGS="${COVERAGE_FLAGS} --cov-report=html:coverage_html"
        ;;
    term)
        COVERAGE_FLAGS="${COVERAGE_FLAGS} --cov-report=term-missing"
        ;;
    *)
        COVERAGE_FLAGS="${COVERAGE_FLAGS} --cov-report=xml:${COVERAGE_FILE} --cov-report=term-missing"
        ;;
esac

# Run unit tests
# shellcheck disable=SC2086
uv run pytest \
    ${UNIT_TEST_PATHS} \
    -v \
    ${COVERAGE_FLAGS} \
    --cov-fail-under="${COVERAGE_THRESHOLD}" \
    "$@"

echo ""
echo "Unit tests completed successfully!"
