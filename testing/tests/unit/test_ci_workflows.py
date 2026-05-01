"""CI workflow and test values structural validation tests.

Tests that validate GitHub Actions workflow files and Helm test values
have the correct structure. These are unit tests that parse YAML — no
external services or Helm CLI required.

Requirements:
    WU2-AC1: weekly.yml builds Cube Store for linux/amd64
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
WEEKLY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "weekly.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
UV_SECURITY_ACTION = REPO_ROOT / ".github" / "actions" / "uv-security-audit" / "action.yml"
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
SETUP_HOOKS = REPO_ROOT / "scripts" / "setup-hooks.sh"
CUBE_STORE_DOCKERFILE = REPO_ROOT / "docker" / "cube-store" / "Dockerfile"
VALUES_TEST = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"


def _local_pre_commit_hooks() -> dict[str, dict[str, object]]:
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text())
    hooks: dict[str, dict[str, object]] = {}
    for repo in config["repos"]:
        if repo["repo"] == "local":
            hooks.update({hook["id"]: hook for hook in repo["hooks"]})
    return hooks


class TestWeeklyWorkflow:
    """Structural validation of weekly.yml workflow."""

    @pytest.mark.requirement("WU2-AC1")
    def test_weekly_workflow_exists(self) -> None:
        """Verify weekly.yml workflow file exists."""
        assert WEEKLY_WORKFLOW.exists(), f"weekly.yml not found at {WEEKLY_WORKFLOW}"

    @pytest.mark.requirement("WU2-AC1")
    def test_weekly_has_cube_store_build_job(self) -> None:
        """Verify weekly.yml contains a build-cube-store job.

        The job must exist at the top level of the 'jobs' section.
        """
        workflow = yaml.safe_load(WEEKLY_WORKFLOW.read_text())
        jobs = workflow.get("jobs", {})
        assert "build-cube-store" in jobs, (
            f"Missing 'build-cube-store' job in nightly.yml. Found jobs: {list(jobs.keys())}"
        )

    @pytest.mark.requirement("WU2-AC1")
    def test_cube_store_job_has_amd64_platform(self) -> None:
        """Verify build-cube-store job targets linux/amd64.

        Upstream cubejs/cubestore is AMD64-only (no ARM64 manifest),
        so we only build for linux/amd64.
        """
        workflow = yaml.safe_load(WEEKLY_WORKFLOW.read_text())
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

    @pytest.mark.requirement("WU2-AC1")
    def test_cube_store_job_pushes_to_ghcr(self) -> None:
        """Verify build-cube-store pushes to ghcr.io/obsidian-owl/cube-store.

        The image must be pushed to the project's OCI registry, not Docker Hub.
        """
        workflow = yaml.safe_load(WEEKLY_WORKFLOW.read_text())
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
        workflow = yaml.safe_load(WEEKLY_WORKFLOW.read_text())
        job = workflow["jobs"]["build-cube-store"]
        permissions = job.get("permissions", {})
        assert permissions.get("packages") == "write", (
            f"Missing 'packages: write' permission. Got: {permissions}"
        )

    @pytest.mark.requirement("WU2-AC1")
    def test_cube_store_job_push_enabled(self) -> None:
        """Verify build-push-action has push: true to publish images.

        Without push: true, images are built locally but never pushed
        to GHCR, making the build pipeline a no-op.
        """
        workflow = yaml.safe_load(WEEKLY_WORKFLOW.read_text())
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
        """Verify Cube Store Dockerfile exists for build."""
        assert CUBE_STORE_DOCKERFILE.exists(), (
            f"Dockerfile not found at {CUBE_STORE_DOCKERFILE}. Required for Cube Store build."
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
    def test_cube_store_rollback_path_enabled(self) -> None:
        """Verify the local test values use the documented Cube rollback path.

        The local Kind/DevPod test environment keeps the Cube API enabled but
        disables Cube Store because the upstream Cube Store image is not
        reliable in this environment. The API must fall back to in-memory
        cache/queue mode instead of blocking namespace readiness.
        """
        values = yaml.safe_load(VALUES_TEST.read_text())
        cube = values.get("cube", {})
        assert "cubeStore" in cube, (
            "Key must be 'cubeStore' (camelCase) to match Helm subchart."
            f" Found keys: {list(cube.keys())}"
        )
        cubestore = cube["cubeStore"]
        assert cubestore.get("enabled") is False, (
            "cube.cubeStore.enabled must be false for the rollback path. "
            f"Got: {cubestore.get('enabled')}"
        )

        config = cube.get("config", {})
        assert config.get("cacheDriver") == "memory", (
            "cube.config.cacheDriver must be 'memory' when cubeStore is disabled. "
            f"Got: {config.get('cacheDriver')}"
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


class TestValuesTestJobs:
    """Structural validation of test-job toggles in values-test.yaml."""

    @pytest.mark.requirement("9b-AC-6")
    def test_chart_test_jobs_are_opt_in_only(self) -> None:
        """Verify values-test does not auto-render in-cluster test Jobs.

        The E2E runner scripts render these templates explicitly with
        ``--set tests.enabled=true``. Leaving the toggle enabled in
        ``values-test.yaml`` deploys the standard and destructive test Jobs
        into every normal platform install, which poisons namespace readiness
        and interferes with Task 6 bootstrap verification.
        """
        values = yaml.safe_load(VALUES_TEST.read_text())
        tests_config = values.get("tests", {})
        assert tests_config.get("enabled") is False, (
            "values-test.yaml must keep tests.enabled=false so chart test Jobs "
            "remain opt-in via testing/ci/common.sh rendering."
        )


class TestLocalHookAlignment:
    """Structural validation for local pre-push and CI alignment."""

    @pytest.mark.requirement("VAL-HOOKS")
    def test_pre_push_runs_ruff_format_check(self) -> None:
        """Local pre-push must catch the same Ruff formatting failure as CI."""
        hooks = _local_pre_commit_hooks()

        assert hooks["ruff-format-check"]["entry"] == "uv run --no-sync ruff format --check ."
        assert hooks["ruff-format-check"]["stages"] == ["pre-push"]

    @pytest.mark.requirement("VAL-HOOKS")
    def test_mutating_file_hygiene_hooks_are_pre_commit_only(self) -> None:
        """Auto-fix hygiene hooks should not mutate files during pre-push."""
        config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text())
        hygiene_repo = next(
            repo
            for repo in config["repos"]
            if repo["repo"] == "https://github.com/pre-commit/pre-commit-hooks"
        )

        for hook in hygiene_repo["hooks"]:
            assert hook["stages"] == ["pre-commit"], f"{hook['id']} should not run during pre-push"

    @pytest.mark.requirement("VAL-HOOKS")
    def test_pre_push_reuses_ci_scripts_for_shared_gates(self) -> None:
        """Local pre-push should call the same reusable scripts as CI."""
        hooks = _local_pre_commit_hooks()

        assert hooks["dbt-version-contracts"]["entry"] == (
            "./testing/ci/validate-dbt-version-requirements.sh"
        )
        assert hooks["uv-secure"]["entry"] == "./testing/ci/uv-security-audit.sh"
        assert hooks["pytest-unit"]["entry"] == "./testing/ci/test-unit.sh"
        assert hooks["pytest-contract"]["entry"] == "./testing/ci/test-contract.sh"

    @pytest.mark.requirement("VAL-HOOKS")
    def test_ci_reuses_local_hook_scripts_for_shared_gates(self) -> None:
        """CI should invoke the same scripts used by local pre-push."""
        ci_text = CI_WORKFLOW.read_text()
        action_text = UV_SECURITY_ACTION.read_text()

        assert "./testing/ci/validate-dbt-version-requirements.sh" in ci_text
        assert "./testing/ci/uv-security-audit.sh" in action_text

    @pytest.mark.requirement("VAL-HOOKS")
    def test_setup_hooks_overrides_global_hooks_path_locally(self) -> None:
        """Hook setup should make repo-local hooks win over global hook managers."""
        setup_text = SETUP_HOOKS.read_text()

        assert "git config --local core.hooksPath" in setup_text
        assert "git config --global --get core.hooksPath" in setup_text

    @pytest.mark.requirement("VAL-HOOKS")
    def test_pre_push_unsets_git_hook_environment_before_running_pytest(self) -> None:
        """Local pre-push must not leak hook-local Git env into test subprocesses."""
        setup_text = SETUP_HOOKS.read_text()
        pre_push_template = setup_text.split("cat > \"$HOOKS_DIR/pre-push\" << 'HOOK'", maxsplit=1)[
            1
        ].split("HOOK", maxsplit=1)[0]

        assert "git rev-parse --local-env-vars" in pre_push_template
        assert 'unset "$git_env_var"' in pre_push_template
        assert pre_push_template.index('unset "$git_env_var"') < pre_push_template.index(
            "pre-commit run --hook-stage pre-push",
        )


class TestCubeStoreRollbackPath:
    """Verify Cube Store E2E tests exist and rollback path is documented."""

    E2E_DEPLOY_TEST = REPO_ROOT / "tests" / "e2e" / "test_platform_deployment_e2e.py"

    @pytest.mark.requirement("WU2-AC5")
    def test_cube_store_e2e_test_exists(self) -> None:
        """Verify Cube Store E2E test exists in deployment suite.

        The rollback path (cubeStore.enabled: false) is available via
        values-test.yaml. The deployment E2E suite must gate its Cube Store
        assertions on that toggle instead of hard-failing when the rollback
        path is active.
        """
        content = self.E2E_DEPLOY_TEST.read_text()
        assert "test_cube_store_pod_running" in content, (
            "Missing test_cube_store_pod_running in E2E deployment tests"
        )
        values = yaml.safe_load(VALUES_TEST.read_text())
        cube = values.get("cube", {})
        assert "cubeStore" in cube and "enabled" in cube["cubeStore"], (
            "values-test.yaml must keep the cube.cubeStore.enabled rollback toggle"
        )
