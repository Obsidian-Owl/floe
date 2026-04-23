#!/bin/bash
# Full validation orchestrator — runs bootstrap, platform blackbox,
# developer workflow, then destructive validation lanes.
#
# Bootstrap runs first and gates in-cluster platform validation. Developer
# workflow validation always runs. Destructive validation requires bootstrap and
# platform success unless FORCE_DESTRUCTIVE=true. Artifacts from all lanes are
# preserved.
#
# Usage: ./testing/ci/test-e2e-full.sh
#
# Environment:
#   FORCE_DESTRUCTIVE   Run destructive tests even if bootstrap/platform fail (default: false)
#   SKIP_BUILD          Skip image build (passed through to test-e2e-cluster.sh)
#   IMAGE_LOAD_METHOD   Image loading method (passed through to test-e2e-cluster.sh)
#   TEST_NAMESPACE      K8s namespace (passed through, default: floe-test)
#   JOB_TIMEOUT         Per-suite timeout in seconds (passed through, default: 3600)

set -euo pipefail

FORCE_DESTRUCTIVE="${FORCE_DESTRUCTIVE:-false}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
source "${SCRIPT_DIR}/common.sh"
TEST_NAMESPACE="${TEST_NAMESPACE:-${FLOE_NAMESPACE}}"

info() { echo "[INFO] $*"; }
error() { echo "[ERROR] $*" >&2; }

# Track exit codes
BOOTSTRAP_EXIT=0
PLATFORM_EXIT=0
DEVELOPER_EXIT=0
DESTRUCTIVE_EXIT=0
CAN_REUSE_PLATFORM_IMAGE=false
CLEANUP_FAILED=false

# =============================================================================
# Phase 1: Bootstrap validation
# =============================================================================

info "=== Phase 1: Bootstrap Validation ==="

if "${SCRIPT_DIR}/test-bootstrap-validation.sh"; then
    info "Bootstrap validation PASSED"
else
    BOOTSTRAP_EXIT=$?
    error "Bootstrap validation FAILED (exit code: ${BOOTSTRAP_EXIT})"
fi

# =============================================================================
# Phase 2: Platform blackbox validation
# =============================================================================

if [[ "${BOOTSTRAP_EXIT}" -eq 0 ]]; then
    info "=== Phase 2: Platform Blackbox Validation ==="

    if "${SCRIPT_DIR}/test-e2e-cluster.sh"; then
        info "Platform blackbox validation PASSED"
        CAN_REUSE_PLATFORM_IMAGE=true
    else
        PLATFORM_EXIT=$?
        error "Platform blackbox validation FAILED (exit code: ${PLATFORM_EXIT})"
    fi
else
    info "Skipping platform blackbox validation because bootstrap failed."
fi

# =============================================================================
# Phase 3: Developer workflow validation
# =============================================================================

info "=== Phase 3: Developer Workflow Validation ==="

if "${SCRIPT_DIR}/test-developer-workflow.sh"; then
    info "Developer workflow validation PASSED"
else
    DEVELOPER_EXIT=$?
    error "Developer workflow validation FAILED (exit code: ${DEVELOPER_EXIT})"
fi

# =============================================================================
# Pod cleanup before destructive suite
# =============================================================================

info "Cleaning up platform validation pods before destructive suite..."
kubectl delete pods -l test-type=e2e -n "${TEST_NAMESPACE}" --ignore-not-found 2>/dev/null || true

for i in $(seq 1 30); do
    pod_count=$(kubectl get pods -l test-type=e2e -n "${TEST_NAMESPACE}" --no-headers 2>/dev/null | wc -l | tr -d ' ')
    if [[ "${pod_count}" == "0" ]]; then
        break
    fi
    if [[ $i -eq 30 ]]; then
        error "Platform validation pods did not terminate within 30s"
        CLEANUP_FAILED=true
        DESTRUCTIVE_EXIT=1
        break
    fi
    sleep 1
done

# =============================================================================
# Phase 4: Destructive E2E tests
# =============================================================================

if [[ ("${BOOTSTRAP_EXIT}" -ne 0 || "${PLATFORM_EXIT}" -ne 0) && "${FORCE_DESTRUCTIVE}" != "true" ]]; then
    info "Skipping destructive tests (bootstrap and platform must pass). Set FORCE_DESTRUCTIVE=true to override."
elif [[ "${CLEANUP_FAILED}" == "true" ]]; then
    info "Skipping destructive tests because platform cleanup failed."
else
    info "=== Phase 4: Destructive E2E Tests ==="

    if [[ "${CAN_REUSE_PLATFORM_IMAGE}" == "true" ]]; then
        # Platform validation already built and loaded the runner image.
        if SKIP_BUILD=true IMAGE_LOAD_METHOD=skip TEST_SUITE=e2e-destructive "${SCRIPT_DIR}/test-e2e-cluster.sh"; then
            info "Destructive E2E tests PASSED"
        else
            DESTRUCTIVE_EXIT=$?
            error "Destructive E2E tests FAILED (exit code: ${DESTRUCTIVE_EXIT})"
        fi
    elif TEST_SUITE=e2e-destructive "${SCRIPT_DIR}/test-e2e-cluster.sh"; then
        info "Destructive E2E tests PASSED"
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
if [[ "${BOOTSTRAP_EXIT}" -eq 0 ]]; then
    info "  Bootstrap:   PASSED"
else
    error "  Bootstrap:   FAILED (exit ${BOOTSTRAP_EXIT})"
fi

if [[ "${BOOTSTRAP_EXIT}" -ne 0 ]]; then
    info "  Platform:    SKIPPED"
elif [[ "${PLATFORM_EXIT}" -eq 0 ]]; then
    info "  Platform:    PASSED"
else
    error "  Platform:    FAILED (exit ${PLATFORM_EXIT})"
fi

if [[ "${DEVELOPER_EXIT}" -eq 0 ]]; then
    info "  Developer:   PASSED"
else
    error "  Developer:   FAILED (exit ${DEVELOPER_EXIT})"
fi

if [[ ("${BOOTSTRAP_EXIT}" -ne 0 || "${PLATFORM_EXIT}" -ne 0) && "${FORCE_DESTRUCTIVE}" != "true" ]]; then
    info "  Destructive: SKIPPED"
elif [[ "${CLEANUP_FAILED}" == "true" ]]; then
    error "  Destructive: SKIPPED (cleanup failed)"
elif [[ "${DESTRUCTIVE_EXIT}" -eq 0 ]]; then
    info "  Destructive: PASSED"
else
    error "  Destructive: FAILED (exit ${DESTRUCTIVE_EXIT})"
fi

# Exit with first non-zero exit code
if [[ "${BOOTSTRAP_EXIT}" -ne 0 ]]; then
    exit "${BOOTSTRAP_EXIT}"
elif [[ "${PLATFORM_EXIT}" -ne 0 ]]; then
    exit "${PLATFORM_EXIT}"
elif [[ "${DEVELOPER_EXIT}" -ne 0 ]]; then
    exit "${DEVELOPER_EXIT}"
elif [[ "${DESTRUCTIVE_EXIT}" -ne 0 ]]; then
    exit "${DESTRUCTIVE_EXIT}"
fi

info "E2E tests PASSED"
exit 0
