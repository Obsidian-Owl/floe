"""Unit-level chart contract tests for Unit C's test runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATE_PATH = _REPO_ROOT / "charts" / "floe-platform" / "templates" / "tests" / "_test-job.tpl"
_VALUES_TEST_PATH = _REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"


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
            "source testing/ci/common.sh && floe_render_test_job tests/job-e2e.yaml",
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


def test_test_runner_uses_generated_contract_env_helper() -> None:
    """The test Job env table must come from the generated contract helper."""
    template = _TEMPLATE_PATH.read_text()

    assert 'include "floe-platform.testRunner.contractEnv" $context' in template
    assert "name: INTEGRATION_TEST_HOST" not in template
    assert "name: POLARIS_HOST" not in template


def test_generated_contract_env_helper_matches_emitter() -> None:
    """Committed Helm helper must match the contract emitter output."""
    from floe_core.contracts.emit import render_helm_test_env_template

    generated = (
        _REPO_ROOT
        / "charts"
        / "floe-platform"
        / "templates"
        / "tests"
        / "_contract-env.generated.tpl"
    )

    assert generated.read_text() == render_helm_test_env_template()
