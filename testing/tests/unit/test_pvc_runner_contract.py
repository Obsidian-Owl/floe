"""Unit contracts for Unit D runner-side PVC ownership behavior.

The test-artifacts PVC is chart-owned. Runner scripts must provision it
through the shared helper in `testing/ci/common.sh` so fresh clusters get
the claim before the Job starts and Helm ownership metadata stays aligned.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMON_HELPERS = REPO_ROOT / "testing" / "ci" / "common.sh"
E2E_RUNNER = REPO_ROOT / "testing" / "ci" / "test-e2e-cluster.sh"
INTEGRATION_RUNNER = REPO_ROOT / "testing" / "ci" / "test-integration.sh"


class TestRunnerPvcOwnershipContract:
    """AC-3 plus the runner-side fresh-cluster provisioning contract."""

    @pytest.mark.requirement("AC-3")
    def test_common_helpers_provision_pvc_with_helm_ownership_metadata(self) -> None:
        """common.sh must provide the shared Helm-adoptable PVC bootstrap helper."""

        assert COMMON_HELPERS.exists(), f"Expected common helper script at {COMMON_HELPERS}"
        helper_text = COMMON_HELPERS.read_text(encoding="utf-8")
        assert "floe_ensure_test_artifacts_pvc()" in helper_text, (
            "testing/ci/common.sh must define floe_ensure_test_artifacts_pvc()."
        )
        assert 'floe_render_test_job "tests/pvc-artifacts.yaml"' in helper_text, (
            "PVC bootstrap helper must render the real chart PVC template."
        )
        assert 'meta.helm.sh/release-name="${FLOE_RELEASE_NAME}"' in helper_text, (
            "PVC bootstrap helper must stamp the Helm release-name annotation."
        )
        assert 'meta.helm.sh/release-namespace="${FLOE_NAMESPACE}"' in helper_text, (
            "PVC bootstrap helper must stamp the Helm release-namespace annotation."
        )
        assert "app.kubernetes.io/managed-by=Helm" in helper_text, (
            "PVC bootstrap helper must preserve the Helm managed-by label."
        )

    @pytest.mark.parametrize(
        ("runner_path", "runner_label"),
        [
            pytest.param(E2E_RUNNER, "test-e2e-cluster.sh", id="e2e-runner"),
            pytest.param(INTEGRATION_RUNNER, "test-integration.sh", id="integration-runner"),
        ],
    )
    @pytest.mark.requirement("AC-3")
    def test_runner_bootstraps_pvc_via_shared_helper(
        self,
        runner_path: Path,
        runner_label: str,
    ) -> None:
        """Runner scripts must provision the artifacts PVC before applying the Job."""

        assert runner_path.exists(), f"Expected runner script at {runner_path}"
        runner_text = runner_path.read_text(encoding="utf-8")
        helper_index = runner_text.find("floe_ensure_test_artifacts_pvc")
        job_index = runner_text.find('floe_render_test_job "${JOB_TEMPLATE}"')

        assert helper_index != -1, (
            f"{runner_label} must call floe_ensure_test_artifacts_pvc() before "
            "submitting the chart-rendered test Job."
        )
        assert job_index != -1, (
            f"{runner_label} no longer renders the chart Job via JOB_TEMPLATE; "
            "update this contract if the runner structure changed intentionally."
        )
        assert helper_index < job_index, (
            f"{runner_label} provisions the Job before the artifacts PVC helper. "
            "Fresh clusters would leave the pod Pending on a missing claim."
        )

    @pytest.mark.parametrize(
        ("runner_path", "runner_label"),
        [
            pytest.param(E2E_RUNNER, "test-e2e-cluster.sh", id="e2e-runner"),
            pytest.param(INTEGRATION_RUNNER, "test-integration.sh", id="integration-runner"),
        ],
    )
    @pytest.mark.requirement("AC-3")
    def test_runner_does_not_inline_pvc_template_apply(
        self,
        runner_path: Path,
        runner_label: str,
    ) -> None:
        """Runner scripts must keep PVC bootstrap logic centralized in common.sh."""

        assert runner_path.exists(), f"Expected runner script at {runner_path}"
        runner_text = runner_path.read_text(encoding="utf-8")
        apply_match = re.search(
            r'floe_render_test_job\s+"tests/pvc-artifacts\.yaml"\s*\|\s*kubectl apply -f -',
            runner_text,
        )
        assert apply_match is None, (
            f"{runner_label} still inlines the PVC template apply. "
            "Provisioning must stay centralized in testing/ci/common.sh."
        )
        assert '"claimName": "test-artifacts"' not in runner_text, (
            f"{runner_label} still hardcodes the test-artifacts PVC name. "
            "PVC naming must flow from chart values via shared helpers."
        )
