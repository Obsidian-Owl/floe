#!/bin/bash
# Legacy integration runner — bootstrap-gated wrapper around in-cluster E2E Jobs.
#
# This entry point is kept for release/weekly workflows and `make test`.
# It delegates to test-e2e-cluster.sh so every product E2E/integration run
# validates the bootstrap boundary first.
#
# Usage: ./testing/ci/test-integration.sh
#
# Environment:
#   TEST_SUITE          Suite to run: bootstrap|e2e|e2e-destructive (default: e2e)
#   WAIT_TIMEOUT        Legacy job timeout in seconds; maps to JOB_TIMEOUT
#   JOB_TIMEOUT         Job completion timeout for test-e2e-cluster.sh
#   SKIP_BUILD          Set to "true" to skip Docker build (use existing image)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_SUITE="${TEST_SUITE:-e2e}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-600}"
export JOB_TIMEOUT="${JOB_TIMEOUT:-${WAIT_TIMEOUT}}"

run_cluster_suite() {
    local suite="$1"
    TEST_SUITE="${suite}" "${SCRIPT_DIR}/test-e2e-cluster.sh"
}

run_cluster_suite_skip_build() {
    local suite="$1"
    SKIP_BUILD=true TEST_SUITE="${suite}" "${SCRIPT_DIR}/test-e2e-cluster.sh"
}

case "${TEST_SUITE}" in
    bootstrap)
        echo "Running bootstrap validation via test-e2e-cluster.sh..."
        run_cluster_suite "bootstrap"
        ;;
    e2e)
        echo "Running bootstrap-gated standard E2E via test-e2e-cluster.sh..."
        run_cluster_suite "bootstrap"
        run_cluster_suite_skip_build "e2e"
        ;;
    e2e-destructive)
        echo "Running bootstrap-gated destructive E2E via test-e2e-cluster.sh..."
        run_cluster_suite "bootstrap"
        run_cluster_suite_skip_build "e2e-destructive"
        ;;
    integration)
        echo "ERROR: TEST_SUITE=integration has been retired. Use TEST_SUITE=e2e." >&2
        exit 1
        ;;
    *)
        echo "ERROR: Unknown TEST_SUITE '${TEST_SUITE}'. Use: bootstrap|e2e|e2e-destructive" >&2
        exit 1
        ;;
esac
