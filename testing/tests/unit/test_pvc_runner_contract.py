"""Unit contracts for Unit D runner-side PVC ownership behavior.

The `test-artifacts` PVC is chart-owned. Runner scripts must not recreate it
through `kubectl apply`, or Helm ownership metadata is bypassed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_RUNNER = REPO_ROOT / "testing" / "ci" / "test-e2e-cluster.sh"
INTEGRATION_RUNNER = REPO_ROOT / "testing" / "ci" / "test-integration.sh"


class TestRunnerPvcOwnershipContract:
    """AC-3 plus the same late-discovery CI surface in test-integration.sh."""

    @pytest.mark.parametrize(
        ("runner_path", "runner_label"),
        [
            pytest.param(E2E_RUNNER, "test-e2e-cluster.sh", id="e2e-runner"),
            pytest.param(INTEGRATION_RUNNER, "test-integration.sh", id="integration-runner"),
        ],
    )
    @pytest.mark.requirement("AC-3")
    def test_runner_no_longer_applies_pvc_template(
        self,
        runner_path: Path,
        runner_label: str,
    ) -> None:
        """Runner scripts must not pipe pvc-artifacts.yaml into kubectl apply."""

        assert runner_path.exists(), f"Expected runner script at {runner_path}"
        runner_text = runner_path.read_text(encoding="utf-8")
        apply_match = re.search(
            r'floe_render_test_job\s+"tests/pvc-artifacts\.yaml"\s*\|\s*kubectl apply -f -',
            runner_text,
        )
        assert apply_match is None, (
            f"{runner_label} still applies the test-artifacts PVC via kubectl apply. "
            "The PVC must remain Helm-owned from creation."
        )

    @pytest.mark.parametrize(
        ("runner_path", "runner_label"),
        [
            pytest.param(E2E_RUNNER, "test-e2e-cluster.sh", id="e2e-runner"),
            pytest.param(INTEGRATION_RUNNER, "test-integration.sh", id="integration-runner"),
        ],
    )
    @pytest.mark.requirement("AC-3")
    def test_runner_does_not_log_pvc_apply_step(
        self,
        runner_path: Path,
        runner_label: str,
    ) -> None:
        """Runner output contracts must not advertise a dedicated PVC apply step."""

        assert runner_path.exists(), f"Expected runner script at {runner_path}"
        runner_text = runner_path.read_text(encoding="utf-8")
        assert 'Applying test-artifacts PVC from chart...' not in runner_text, (
            f"{runner_label} still advertises a dedicated PVC apply step even though "
            "the chart now owns that resource."
        )
