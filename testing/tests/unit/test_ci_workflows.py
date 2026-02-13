"""CI workflow structural validation tests.

Tests that validate GitHub Actions workflow files have the correct structure
and configuration. These are unit tests that parse YAML — no external services.

Requirements:
    WU2-AC1: nightly.yml builds multi-arch Cube Store for linux/amd64 and linux/arm64
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
NIGHTLY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "nightly.yml"
CUBE_STORE_DOCKERFILE = REPO_ROOT / "docker" / "cube-store" / "Dockerfile"


class TestNightlyWorkflow:
    """Structural validation of nightly.yml workflow."""

    @pytest.mark.requirement("WU2-AC1")
    def test_nightly_workflow_exists(self) -> None:
        """Verify nightly.yml workflow file exists."""
        assert NIGHTLY_WORKFLOW.exists(), f"nightly.yml not found at {NIGHTLY_WORKFLOW}"

    @pytest.mark.requirement("WU2-AC1")
    def test_nightly_has_cube_store_build_job(self) -> None:
        """Verify nightly.yml contains a build-cube-store job.

        The job must exist at the top level of the 'jobs' section.
        """
        workflow = yaml.safe_load(NIGHTLY_WORKFLOW.read_text())
        jobs = workflow.get("jobs", {})
        assert "build-cube-store" in jobs, (
            f"Missing 'build-cube-store' job in nightly.yml. Found jobs: {list(jobs.keys())}"
        )

    @pytest.mark.requirement("WU2-AC1")
    def test_cube_store_job_has_multiarch_platforms(self) -> None:
        """Verify build-cube-store job targets linux/amd64 and linux/arm64.

        The docker/build-push-action step must specify both platforms
        to produce a multi-arch manifest.
        """
        workflow = yaml.safe_load(NIGHTLY_WORKFLOW.read_text())
        job = workflow["jobs"]["build-cube-store"]
        steps = job.get("steps", [])

        # Find the build-push step
        build_step = next(
            (s for s in steps if "docker/build-push-action" in s.get("uses", "")),
            None,
        )
        assert build_step is not None, "No docker/build-push-action step in build-cube-store job"

        platforms = build_step.get("with", {}).get("platforms", "")
        assert "linux/amd64" in platforms, "Missing linux/amd64 platform"
        assert "linux/arm64" in platforms, "Missing linux/arm64 platform"

    @pytest.mark.requirement("WU2-AC1")
    def test_cube_store_job_pushes_to_ghcr(self) -> None:
        """Verify build-cube-store pushes to ghcr.io/obsidian-owl/cube-store.

        The image must be pushed to the project's OCI registry, not Docker Hub.
        """
        workflow = yaml.safe_load(NIGHTLY_WORKFLOW.read_text())
        job = workflow["jobs"]["build-cube-store"]
        steps = job.get("steps", [])

        # Find the build-push step
        build_step = next(
            (s for s in steps if "docker/build-push-action" in s.get("uses", "")),
            None,
        )
        assert build_step is not None

        tags = build_step.get("with", {}).get("tags", "")
        assert "ghcr.io/obsidian-owl/cube-store" in tags, (
            f"Image not pushed to ghcr.io/obsidian-owl/cube-store. Tags: {tags}"
        )

    @pytest.mark.requirement("WU2-AC1")
    def test_cube_store_job_has_packages_write_permission(self) -> None:
        """Verify build-cube-store has packages:write permission for GHCR push."""
        workflow = yaml.safe_load(NIGHTLY_WORKFLOW.read_text())
        job = workflow["jobs"]["build-cube-store"]
        permissions = job.get("permissions", {})
        assert permissions.get("packages") == "write", (
            f"Missing 'packages: write' permission. Got: {permissions}"
        )

    @pytest.mark.requirement("WU2-AC1")
    def test_cube_store_dockerfile_exists(self) -> None:
        """Verify Cube Store Dockerfile exists for multi-arch build."""
        assert CUBE_STORE_DOCKERFILE.exists(), (
            f"Dockerfile not found at {CUBE_STORE_DOCKERFILE}. "
            "Required for multi-arch Cube Store build."
        )

    @pytest.mark.requirement("WU2-AC1")
    def test_cube_store_dockerfile_has_from_instruction(self) -> None:
        """Verify Dockerfile has a FROM instruction (valid Dockerfile)."""
        content = CUBE_STORE_DOCKERFILE.read_text()
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        has_from = any(line.upper().startswith("FROM") for line in lines)
        assert has_from, "Dockerfile missing FROM instruction"
