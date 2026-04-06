#!/bin/bash
# Full E2E test orchestrator — runs standard then destructive E2E suites sequentially.
#
# Standard E2E tests run first. If they fail, destructive tests are skipped
# (unless FORCE_DESTRUCTIVE=true). Artifacts from both suites are preserved.
#
# Usage: ./testing/ci/test-e2e-full.sh
#
# Environment:
#   FORCE_DESTRUCTIVE   Run destructive tests even if standard tests fail (default: false)
#   SKIP_BUILD          Skip image build (passed through to test-e2e-cluster.sh)
#   IMAGE_LOAD_METHOD   Image loading method (passed through to test-e2e-cluster.sh)
#   TEST_NAMESPACE      K8s namespace (passed through, default: floe-test)
#   JOB_TIMEOUT         Per-suite timeout in seconds (passed through, default: 3600)

set -euo pipefail

FORCE_DESTRUCTIVE="${FORCE_DESTRUCTIVE:-false}"
TEST_NAMESPACE="${TEST_NAMESPACE:-floe-test}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info() { echo "[INFO] $*"; }
error() { echo "[ERROR] $*" >&2; }

# Track exit codes
STANDARD_EXIT=0
DESTRUCTIVE_EXIT=0

# =============================================================================
# Phase 1: Standard E2E tests (non-destructive)
# =============================================================================

info "=== Phase 1: Standard E2E Tests ==="

if "${SCRIPT_DIR}/test-e2e-cluster.sh"; then
    info "Standard E2E tests PASSED"
    STANDARD_EXIT=0
else
    STANDARD_EXIT=$?
    error "Standard E2E tests FAILED (exit code: ${STANDARD_EXIT})"
fi

# =============================================================================
# Pod cleanup between suites
# =============================================================================

info "Cleaning up standard test pods before destructive suite..."
kubectl delete pods -l test-type=e2e -n "${TEST_NAMESPACE}" --ignore-not-found 2>/dev/null || true

# Wait for pods to terminate
for i in $(seq 1 30); do
    pod_count=$(kubectl get pods -l test-type=e2e -n "${TEST_NAMESPACE}" --no-headers 2>/dev/null | wc -l | tr -d ' ')
    if [[ "${pod_count}" == "0" ]]; then
        break
    fi
    if [[ $i -eq 30 ]]; then
        error "Standard test pods did not terminate within 30s"
        exit 1
    fi
    sleep 1
done

# =============================================================================
# Phase 2: Destructive E2E tests
# =============================================================================

if [[ "${STANDARD_EXIT}" -ne 0 ]] && [[ "${FORCE_DESTRUCTIVE}" != "true" ]]; then
    info "Skipping destructive tests (standard tests failed). Set FORCE_DESTRUCTIVE=true to override."
    DESTRUCTIVE_EXIT=0
else
    info "=== Phase 2: Destructive E2E Tests ==="

    # Use SKIP_BUILD=true since the image was already built in Phase 1
    if SKIP_BUILD=true IMAGE_LOAD_METHOD=skip TEST_SUITE=e2e-destructive "${SCRIPT_DIR}/test-e2e-cluster.sh"; then
        info "Destructive E2E tests PASSED"
        DESTRUCTIVE_EXIT=0
    else
        DESTRUCTIVE_EXIT=$?
        error "Destructive E2E tests FAILED (exit code: ${DESTRUCTIVE_EXIT})"
    fi
fi

# =============================================================================
# Summary
# =============================================================================

info ""
info "=== E2E Test Summary ==="
if [[ "${STANDARD_EXIT}" -eq 0 ]]; then
    info "  Standard:    PASSED"
else
    error "  Standard:    FAILED (exit ${STANDARD_EXIT})"
fi

if [[ "${STANDARD_EXIT}" -ne 0 ]] && [[ "${FORCE_DESTRUCTIVE}" != "true" ]]; then
    info "  Destructive: SKIPPED"
elif [[ "${DESTRUCTIVE_EXIT}" -eq 0 ]]; then
    info "  Destructive: PASSED"
else
    error "  Destructive: FAILED (exit ${DESTRUCTIVE_EXIT})"
fi

# Exit with first non-zero exit code
if [[ "${STANDARD_EXIT}" -ne 0 ]]; then
    exit "${STANDARD_EXIT}"
elif [[ "${DESTRUCTIVE_EXIT}" -ne 0 ]]; then
    exit "${DESTRUCTIVE_EXIT}"
fi

info "E2E tests PASSED"
exit 0
