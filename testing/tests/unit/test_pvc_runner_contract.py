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
FAIL_FAST_CLEANUP_RETURN = (
    r'\s*\\?\s*\|\|\s*\{ rm -f "\$\{rendered_pvc\}"; return 1; \}'
)


class TestRunnerPvcOwnershipContract:
    """AC-3 plus the runner-side fresh-cluster provisioning contract."""

    @staticmethod
    def _common_helper_body(helper_text: str, helper_name: str) -> str:
        """Extract a shared helper body from common.sh."""

        match = re.search(
            rf"{helper_name}\(\)\s*\{{(?P<body>.*?)^\}}",
            helper_text,
            re.DOTALL | re.MULTILINE,
        )
        assert match is not None, f"Could not locate {helper_name}() in common.sh."
        return match.group("body")

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
        ("pattern", "description"),
        [
            pytest.param(
                (
                    r'floe_render_test_job "tests/pvc-artifacts\.yaml" > '
                    r'"\$\{rendered_pvc\}"'
                    + FAIL_FAST_CLEANUP_RETURN
                ),
                "rendering the chart PVC template",
                id="render-fail-fast",
            ),
            pytest.param(
                r'kubectl apply -f "\$\{rendered_pvc\}" >/dev/null' + FAIL_FAST_CLEANUP_RETURN,
                "applying the rendered PVC",
                id="apply-fail-fast",
            ),
            pytest.param(
                (
                    r'kubectl annotate -f "\$\{rendered_pvc\}".*?--overwrite >/dev/null'
                    + FAIL_FAST_CLEANUP_RETURN
                ),
                "adding Helm release annotations",
                id="annotate-fail-fast",
            ),
            pytest.param(
                (
                    r'kubectl label -f "\$\{rendered_pvc\}".*?--overwrite >/dev/null'
                    + FAIL_FAST_CLEANUP_RETURN
                ),
                "restoring the Helm managed-by label",
                id="label-fail-fast",
            ),
        ],
    )
    @pytest.mark.requirement("AC-3")
    def test_common_helper_fails_fast_on_bootstrap_errors(
        self,
        pattern: str,
        description: str,
    ) -> None:
        """common.sh must stop immediately when PVC bootstrap commands fail."""

        helper_text = COMMON_HELPERS.read_text(encoding="utf-8")
        helper_body = self._common_helper_body(helper_text, "floe_ensure_test_artifacts_pvc")

        assert re.search(pattern, helper_body, re.DOTALL), (
            "floe_ensure_test_artifacts_pvc() must remove the rendered manifest "
            f"and return 1 immediately when {description} fails."
        )

    @pytest.mark.parametrize(
        ("pattern", "description"),
        [
            pytest.param(
                (
                    r'floe_render_test_job "tests/pvc-artifacts\.yaml" > '
                    r'"\$\{rendered_pvc\}"'
                    + FAIL_FAST_CLEANUP_RETURN
                ),
                "rendering the chart PVC template",
                id="name-helper-render-fail-fast",
            ),
            pytest.param(
                (
                    r'kubectl create --dry-run=client -f "\$\{rendered_pvc\}" '
                    r"-o jsonpath='\{\.metadata\.name\}'"
                    + FAIL_FAST_CLEANUP_RETURN
                ),
                "parsing the rendered PVC name",
                id="name-helper-parse-fail-fast",
            ),
        ],
    )
    @pytest.mark.requirement("AC-3")
    def test_pvc_name_helper_fails_fast_on_lookup_errors(
        self,
        pattern: str,
        description: str,
    ) -> None:
        """PVC name helper must return non-zero when render/parse steps fail."""

        helper_text = COMMON_HELPERS.read_text(encoding="utf-8")
        helper_body = self._common_helper_body(helper_text, "floe_test_artifacts_pvc_name")

        assert re.search(pattern, helper_body, re.DOTALL), (
            "floe_test_artifacts_pvc_name() must remove the rendered manifest "
            f"and return 1 immediately when {description} fails."
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

    @pytest.mark.requirement("AC-3")
    def test_integration_runner_skips_artifact_extraction_when_pvc_name_lookup_fails(self) -> None:
        """test-integration.sh must not mount an empty PVC name after lookup failure."""

        runner_text = INTEGRATION_RUNNER.read_text(encoding="utf-8")

        assert (
            'if artifacts_pvc_name="$(floe_test_artifacts_pvc_name)" '
            '&& [[ -n "${artifacts_pvc_name}" ]]; then'
        ) in runner_text, (
            "test-integration.sh must gate artifact extraction on a successful, non-empty "
            "PVC name lookup."
        )
        assert (
            'echo "WARNING: Could not resolve test artifacts PVC name '
            '— JUnit XML will be missing" >&2'
        ) in runner_text, (
            "test-integration.sh must emit a direct warning when PVC name lookup fails "
            "instead of creating an extractor pod with an empty claim name."
        )
