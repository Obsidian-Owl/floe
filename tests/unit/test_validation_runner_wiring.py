"""Structural tests for validation lane runner wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.requirement("VAL-LANE-RUNNERS")


def test_chart_standard_runner_selects_platform_blackbox() -> None:
    """The standard chart job should target the platform blackbox lane."""
    job_e2e = (
        REPO_ROOT / "charts" / "floe-platform" / "templates" / "tests" / "job-e2e.yaml"
    ).read_text()

    assert '"pytestMarker" "platform_blackbox and not destructive"' in job_e2e


def test_bootstrap_runner_uses_bootstrap_marker() -> None:
    """Bootstrap validation should explicitly select the bootstrap marker."""
    script = (REPO_ROOT / "testing" / "ci" / "test-bootstrap-validation.sh").read_text()

    assert "uv run pytest tests/e2e" in script
    assert '-m "bootstrap"' in script


def test_developer_workflow_runner_uses_developer_marker() -> None:
    """Developer-workflow validation should explicitly select its lane marker."""
    script = (REPO_ROOT / "testing" / "ci" / "test-developer-workflow.sh").read_text()

    assert "uv run pytest tests/e2e" in script
    assert '-m "developer_workflow"' in script


def test_full_runner_orchestrates_bootstrap_platform_developer_then_destructive() -> None:
    """The full runner should execute lanes in the documented order."""
    script = (REPO_ROOT / "testing" / "ci" / "test-e2e-full.sh").read_text()

    assert 'BOOTSTRAP_EXIT=0' in script
    assert 'PLATFORM_EXIT=0' in script
    assert 'DEVELOPER_EXIT=0' in script
    assert 'DESTRUCTIVE_EXIT=0' in script

    assert "test-bootstrap-validation.sh" in script
    assert "test-e2e-cluster.sh" in script
    assert "test-developer-workflow.sh" in script
    assert "TEST_SUITE=e2e-destructive" in script

    bootstrap_index = script.index('test-bootstrap-validation.sh')
    platform_index = script.index('Platform blackbox validation')
    developer_index = script.index('test-developer-workflow.sh')
    destructive_index = script.index('=== Phase 4: Destructive E2E Tests ===')

    assert bootstrap_index < platform_index < developer_index < destructive_index


def test_full_runner_only_reuses_platform_image_after_successful_platform_lane() -> None:
    """Destructive reuse should only happen after a successful platform lane."""
    script = (REPO_ROOT / "testing" / "ci" / "test-e2e-full.sh").read_text()

    assert 'CAN_REUSE_PLATFORM_IMAGE=false' in script
    assert 'CAN_REUSE_PLATFORM_IMAGE=true' in script
    assert 'if [[ "${CAN_REUSE_PLATFORM_IMAGE}" == "true" ]]; then' in script
    assert 'SKIP_BUILD=true IMAGE_LOAD_METHOD=skip TEST_SUITE=e2e-destructive' in script
    assert 'if TEST_SUITE=e2e-destructive "${SCRIPT_DIR}/test-e2e-cluster.sh"; then' in script


def test_full_runner_records_cleanup_failure_without_skipping_summary() -> None:
    """Cleanup failures should still be surfaced in the final summary path."""
    script = (REPO_ROOT / "testing" / "ci" / "test-e2e-full.sh").read_text()

    assert 'CLEANUP_FAILED=false' in script
    assert 'CLEANUP_FAILED=true' in script
    assert 'DESTRUCTIVE_EXIT=1' in script
    assert (
        'if ! pod_count=$(kubectl get pods -l test-type=e2e -n "${TEST_NAMESPACE}" '
        "--no-headers 2>/dev/null | wc -l | tr -d ' '); then"
    ) in script
    assert 'Skipping destructive tests because platform cleanup failed.' in script
    assert 'Destructive: SKIPPED (cleanup failed)' in script
    assert 'if [[ "${CAN_REUSE_PLATFORM_IMAGE}" == "true" ]]; then' in script


def test_testing_guide_describes_validation_lanes() -> None:
    """The testing guide should document every validation lane."""
    guide = (REPO_ROOT / "TESTING.md").read_text()

    assert "bootstrap" in guide
    assert "platform_blackbox" in guide
    assert "developer_workflow" in guide
    assert "destructive" in guide
