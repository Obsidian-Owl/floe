"""Unit-level chart contract tests for Unit C's test runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATE_PATH = _REPO_ROOT / "charts" / "floe-platform" / "templates" / "tests" / "_test-job.tpl"
_VALUES_TEST_PATH = _REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"
_PACKAGED_CHART_PATH = (
    _REPO_ROOT / "charts" / "floe-platform" / "flux-artifacts" / "floe-platform.tgz"
)
_TEST_RUNNER_DOCKERFILE = _REPO_ROOT / "testing" / "Dockerfile"


def _render_test_job_command(template: str) -> str:
    return (
        "source testing/ci/common.sh && "
        f"FLOE_CHART_DIR={_PACKAGED_CHART_PATH} floe_render_test_job {template}"
    )


@pytest.mark.requirement("AC-5")
def test_test_runner_template_reads_pull_policy_from_chart_values() -> None:
    """The test job template must defer pull policy to the chart-owned values key."""
    template = _TEMPLATE_PATH.read_text()
    assert "imagePullPolicy: {{ $context.Values.tests.image.pullPolicy }}" in template, (
        "The Unit C test-runner template must derive imagePullPolicy from the "
        "chart values contract, not a duplicated literal."
    )


@pytest.mark.requirement("AC-5")
def test_test_values_default_the_test_runner_to_if_not_present() -> None:
    """The test values path must keep the test-runner pull policy at IfNotPresent."""
    values = yaml.safe_load(_VALUES_TEST_PATH.read_text())
    assert values["tests"]["image"]["pullPolicy"] == "IfNotPresent", (
        "charts/floe-platform/values-test.yaml must keep the Unit C test-runner "
        "pull policy at IfNotPresent."
    )


@pytest.mark.requirement("AC-5")
def test_rendered_e2e_job_uses_if_not_present_for_test_runner() -> None:
    """Rendering the E2E test Job must preserve the IfNotPresent pull policy."""
    result = subprocess.run(
        [
            "bash",
            "-lc",
            _render_test_job_command("tests/job-e2e.yaml"),
        ],
        cwd=_REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Failed to render the Unit C E2E Job via floe_render_test_job.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert 'image: "floe-test-runner:latest"' in result.stdout
    assert "imagePullPolicy: IfNotPresent" in result.stdout


@pytest.mark.requirement("LIVE-VALIDATION")
def test_rendered_e2e_job_accepts_targeted_pytest_args_override() -> None:
    """Targeted live reruns must be able to replace the default pytest selection."""
    result = subprocess.run(
        [
            "bash",
            "-lc",
            "source testing/ci/common.sh && "
            "FLOE_TEST_PYTEST_ARGS_JSON='["
            '"tests/e2e/test_observability.py::TestObservability::'
            'test_openlineage_events_in_marquez",'
            '"-q"]\' '
            f"FLOE_CHART_DIR={_PACKAGED_CHART_PATH} "
            "floe_render_test_job tests/job-e2e.yaml",
        ],
        cwd=_REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Failed to render the E2E Job with targeted pytest args.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    assert (
        '"tests/e2e/test_observability.py::TestObservability::test_openlineage_events_in_marquez"'
    ) in result.stdout
    assert '"-q"' in result.stdout
    assert '"platform_blackbox and not destructive"' not in result.stdout


@pytest.mark.requirement("LIVE-VALIDATION")
def test_integration_runner_exports_pytest_args_override() -> None:
    """The documented runner arguments must flow into the rendered test Job."""
    script = (_REPO_ROOT / "testing" / "ci" / "test-integration.sh").read_text()

    assert "FLOE_TEST_PYTEST_ARGS_JSON=" in script
    assert "json.dumps(sys.argv[1:])" in script
    assert "export FLOE_TEST_PYTEST_ARGS_JSON" in script


@pytest.mark.requirement("AC-DevPod-Remote-E2E")
def test_test_runner_image_installs_dbt_installer_prerequisites() -> None:
    """The test-runner image must not rely on installer fallback downloads."""
    dockerfile = _TEST_RUNNER_DOCKERFILE.read_text()

    assert "apt-get install -y --no-install-recommends" in dockerfile
    assert "\n    bash \\" in dockerfile
    assert "\n    jq \\" in dockerfile
    assert "public.cdn.getdbt.com/fs/install/install.sh" in dockerfile
