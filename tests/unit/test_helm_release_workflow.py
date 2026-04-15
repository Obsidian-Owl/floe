"""Structural tests: Cosign signing in helm-release workflow.

Validates that the GitHub Actions workflow for chart releases includes
Cosign keyless signing after OCI push.  These are structural YAML tests
(parse + assert), not execution tests.

Requirements Covered:
    FLUX-AC-8: Cosign keyless signing step in helm-release.yaml
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "helm-release.yaml"


def _load_workflow() -> dict[str, Any]:
    """Load and parse the helm-release workflow YAML.

    Returns:
        Parsed workflow as a dictionary.

    Raises:
        AssertionError: If the file does not exist.
    """
    assert _WORKFLOW_PATH.exists(), f"Workflow file not found: {_WORKFLOW_PATH}"
    return yaml.safe_load(_WORKFLOW_PATH.read_text())


def _find_job(workflow: dict[str, Any], job_id: str) -> dict[str, Any]:
    """Find a job by ID in the workflow.

    Args:
        workflow: Parsed workflow dict.
        job_id: Job ID to find.

    Returns:
        Job configuration dict.

    Raises:
        AssertionError: If job not found.
    """
    jobs = workflow.get("jobs", {})
    assert job_id in jobs, (
        f"Job {job_id!r} not found. Available jobs: {list(jobs.keys())}"
    )
    return jobs[job_id]


class TestCosignInstallerStep:
    """Verify cosign-installer action is present in the OCI publish job."""

    @pytest.mark.requirement("FLUX-AC-8")
    def test_cosign_installer_action_present(self) -> None:
        """publish-oci job must include sigstore/cosign-installer action.

        The cosign binary must be installed before the signing step.
        """
        workflow = _load_workflow()
        job = _find_job(workflow, "publish-oci")
        steps = job.get("steps", [])
        cosign_steps = [
            s for s in steps
            if "cosign-installer" in str(s.get("uses", ""))
        ]
        assert len(cosign_steps) > 0, (
            "publish-oci job must include a step using sigstore/cosign-installer"
        )


class TestCosignSigningStep:
    """Verify cosign signing step exists with correct configuration."""

    @pytest.mark.requirement("FLUX-AC-8")
    def test_signing_step_exists(self) -> None:
        """A step with 'cosign sign' must exist in publish-oci job."""
        workflow = _load_workflow()
        job = _find_job(workflow, "publish-oci")
        steps = job.get("steps", [])
        sign_steps = [
            s for s in steps
            if "cosign sign" in str(s.get("run", ""))
        ]
        assert len(sign_steps) > 0, (
            "publish-oci job must include a step running 'cosign sign'"
        )

    @pytest.mark.requirement("FLUX-AC-8")
    def test_signing_uses_yes_flag(self) -> None:
        """cosign sign must use --yes flag for non-interactive execution."""
        workflow = _load_workflow()
        job = _find_job(workflow, "publish-oci")
        steps = job.get("steps", [])
        sign_steps = [
            s for s in steps
            if "cosign sign" in str(s.get("run", ""))
        ]
        assert len(sign_steps) > 0
        run_content = sign_steps[0].get("run", "")
        assert "--yes" in run_content, (
            "cosign sign must use --yes flag for non-interactive mode"
        )

    @pytest.mark.requirement("FLUX-AC-8")
    def test_signing_step_has_continue_on_error(self) -> None:
        """Signing step must have continue-on-error: true.

        Signing is best-effort — it should not fail the release workflow.
        """
        workflow = _load_workflow()
        job = _find_job(workflow, "publish-oci")
        steps = job.get("steps", [])
        sign_steps = [
            s for s in steps
            if "cosign sign" in str(s.get("run", ""))
        ]
        assert len(sign_steps) > 0
        assert sign_steps[0].get("continue-on-error") is True, (
            "cosign signing step must have continue-on-error: true"
        )

    @pytest.mark.requirement("FLUX-AC-8")
    def test_signing_applies_to_all_charts(self) -> None:
        """Signing must apply to all charts pushed, not just one.

        The signing step should iterate over charts (for loop or
        reference the push step's output for each chart).
        """
        workflow = _load_workflow()
        job = _find_job(workflow, "publish-oci")
        steps = job.get("steps", [])
        sign_steps = [
            s for s in steps
            if "cosign sign" in str(s.get("run", ""))
        ]
        assert len(sign_steps) > 0
        run_content = sign_steps[0].get("run", "")
        # Must iterate over charts (for loop) or reference both charts
        has_iteration = (
            "for " in run_content
            or ("floe-platform" in run_content and "floe-jobs" in run_content)
        )
        assert has_iteration, (
            "cosign signing must apply to all charts (use a for loop or "
            "reference both floe-platform and floe-jobs)"
        )


class TestOciJobPermissions:
    """Verify publish-oci job has required permissions for signing."""

    @pytest.mark.requirement("FLUX-AC-8")
    def test_id_token_write_permission(self) -> None:
        """publish-oci job must have id-token: write for keyless signing.

        Keyless signing requires GitHub OIDC token.
        """
        workflow = _load_workflow()
        job = _find_job(workflow, "publish-oci")
        permissions = job.get("permissions", {})
        assert permissions.get("id-token") == "write", (
            f"publish-oci must have 'id-token: write' permission, "
            f"got {permissions}"
        )

    @pytest.mark.requirement("FLUX-AC-8")
    def test_packages_write_permission(self) -> None:
        """publish-oci job must retain packages: write permission."""
        workflow = _load_workflow()
        job = _find_job(workflow, "publish-oci")
        permissions = job.get("permissions", {})
        assert permissions.get("packages") == "write", (
            f"publish-oci must have 'packages: write' permission, "
            f"got {permissions}"
        )
