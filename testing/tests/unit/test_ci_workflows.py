"""CI workflow and test values structural validation tests.

Tests that validate GitHub Actions workflow files and Helm test values
have the correct structure. These are unit tests that parse YAML — no
external services or Helm CLI required.

Requirements:
    WU2-AC1: nightly.yml builds multi-arch Cube Store for linux/amd64 and linux/arm64
    WU2-AC2: values-test.yaml enables Cube Store with overridden image repository
    WU2-AC3: Resource requests fit Kind: API 50m/128Mi, Store 100m/256Mi
    WU2-AC4: StatefulSet supports image override via values
    WU2-AC5: Rollback path: cubeStore.enabled: false + xfail markers
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
NIGHTLY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "nightly.yml"
CUBE_STORE_DOCKERFILE = REPO_ROOT / "docker" / "cube-store" / "Dockerfile"
VALUES_TEST = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"


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
        assert build_step is not None, "No docker/build-push-action step in build-cube-store job"

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
    def test_cube_store_job_push_enabled(self) -> None:
        """Verify build-push-action has push: true to publish images.

        Without push: true, images are built locally but never pushed
        to GHCR, making the entire multi-arch build pipeline a no-op.
        """
        workflow = yaml.safe_load(NIGHTLY_WORKFLOW.read_text())
        job = workflow["jobs"]["build-cube-store"]
        steps = job.get("steps", [])

        build_step = next(
            (s for s in steps if "docker/build-push-action" in s.get("uses", "")),
            None,
        )
        assert build_step is not None, "No docker/build-push-action step in build-cube-store job"

        push = build_step.get("with", {}).get("push")
        assert push is True or push == "true", (
            f"build-push-action must have push: true. Got: {push}"
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


class TestValuesTestCubeStore:
    """Structural validation of Cube Store config in values-test.yaml."""

    @pytest.mark.requirement("WU2-AC2")
    def test_cube_store_enabled(self) -> None:
        """Verify cubeStore.enabled is true in test values.

        Cube Store must be enabled for E2E tests to validate the full
        Cube stack (API + Store).
        """
        values = yaml.safe_load(VALUES_TEST.read_text())
        cube = values.get("cube", {})
        assert "cubeStore" in cube, (
            "Key must be 'cubeStore' (camelCase) to match Helm subchart."
            f" Found keys: {list(cube.keys())}"
        )
        cubestore = cube["cubeStore"]
        assert cubestore.get("enabled") is True, (
            f"cube.cubeStore.enabled must be true. Got: {cubestore.get('enabled')}"
        )

    @pytest.mark.requirement("WU2-AC2")
    def test_cube_store_image_is_public(self) -> None:
        """Verify Cube Store image uses a publicly accessible registry.

        The image repository must be cubejs/cubestore (official public image)
        to avoid private registry authentication failures in CI/Kind.
        """
        values = yaml.safe_load(VALUES_TEST.read_text())
        cube = values.get("cube", {})
        cubestore = cube.get("cubeStore", {})
        image = cubestore.get("image", {})
        repo = image.get("repository", "")
        assert repo == "cubejs/cubestore", (
            f"Cube Store image must use public cubejs/cubestore. Got: {repo}"
        )

    @pytest.mark.requirement("WU2-AC3")
    def test_cube_api_resources_fit_kind(self) -> None:
        """Verify Cube API resource requests fit Kind single-node capacity.

        API pods must request at most 50m CPU and 128Mi memory.
        """
        values = yaml.safe_load(VALUES_TEST.read_text())
        cube = values.get("cube", {})
        api_resources = cube.get("api", {}).get("resources", {})
        requests = api_resources.get("requests", {})

        cpu = requests.get("cpu", "")
        memory = requests.get("memory", "")

        assert cpu == "50m", f"Cube API CPU request must be 50m. Got: {cpu}"
        assert memory == "128Mi", f"Cube API memory request must be 128Mi. Got: {memory}"

    @pytest.mark.requirement("WU2-AC3")
    def test_cube_store_resources_fit_kind(self) -> None:
        """Verify Cube Store resource requests fit Kind single-node capacity.

        Store pods must request at most 100m CPU and 256Mi memory.
        """
        values = yaml.safe_load(VALUES_TEST.read_text())
        cube = values.get("cube", {})
        cubestore = cube.get("cubeStore", {})
        resources = cubestore.get("resources", {})
        requests = resources.get("requests", {})

        cpu = requests.get("cpu", "")
        memory = requests.get("memory", "")

        assert cpu == "100m", f"Cube Store CPU request must be 100m. Got: {cpu}"
        assert memory == "256Mi", f"Cube Store memory request must be 256Mi. Got: {memory}"

    @pytest.mark.requirement("WU2-AC4")
    def test_cube_store_image_has_explicit_tag(self) -> None:
        """Verify Cube Store image tag is explicitly set, not 'latest'.

        Per WU2-BC3, the StatefulSet must use an explicit tag to prevent
        accidental version drift.
        """
        values = yaml.safe_load(VALUES_TEST.read_text())
        cube = values.get("cube", {})
        cubestore = cube.get("cubeStore", {})
        image = cubestore.get("image", {})
        tag = image.get("tag", "")

        assert tag, "Cube Store image tag must be set"
        assert tag != "latest", "Cube Store image tag must not be 'latest'"


class TestCubeStoreRollbackPath:
    """Verify Cube Store E2E tests exist and rollback path is documented."""

    E2E_DEPLOY_TEST = REPO_ROOT / "tests" / "e2e" / "test_platform_deployment_e2e.py"

    @pytest.mark.requirement("WU2-AC5")
    def test_cube_store_e2e_test_exists(self) -> None:
        """Verify Cube Store E2E test exists in deployment suite.

        The rollback path (cubeStore.enabled: false) is available via
        values-test.yaml. Cube Store tests now pass reliably with the
        multi-arch GHCR image, so xfail markers have been removed.
        """
        content = self.E2E_DEPLOY_TEST.read_text()
        assert "test_cube_store_pod_running" in content, (
            "Missing test_cube_store_pod_running in E2E deployment tests"
        )
