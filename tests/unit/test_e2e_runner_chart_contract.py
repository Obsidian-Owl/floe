"""Unit-level chart contract tests for Unit C's test runner."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATE_PATH = _REPO_ROOT / "charts" / "floe-platform" / "templates" / "tests" / "_test-job.tpl"
_VALUES_TEST_PATH = _REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"


def _render_test_job(template: str) -> str:
    """Render a test Job template using the chart contract helper."""
    result = subprocess.run(
        [
            "bash",
            "-lc",
            f"source testing/ci/common.sh && floe_render_test_job {template}",
        ],
        cwd=_REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Failed to render {template} via floe_render_test_job.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result.stdout


def _render_e2e_job() -> str:
    """Render the standard E2E Job template using the chart contract helper."""
    return _render_test_job("tests/job-e2e.yaml")


def _render_bootstrap_job() -> str:
    """Render the bootstrap Job template using the chart contract helper."""
    return _render_test_job("tests/job-bootstrap.yaml")


def _rendered_job_args(rendered: str) -> list[str]:
    """Return the pytest args from a rendered test Job."""
    docs = yaml.safe_load_all(rendered)
    jobs = [doc for doc in docs if isinstance(doc, dict) and doc.get("kind") == "Job"]
    assert len(jobs) == 1
    containers: list[dict[str, Any]] = jobs[0]["spec"]["template"]["spec"]["containers"]
    args: list[str] = containers[0].get("args", [])
    return args


def _rendered_e2e_env_names() -> list[str]:
    """Return env var names from the rendered standard E2E Job."""
    docs = yaml.safe_load_all(_render_e2e_job())
    jobs = [doc for doc in docs if isinstance(doc, dict) and doc.get("kind") == "Job"]
    assert len(jobs) == 1
    containers: list[dict[str, Any]] = jobs[0]["spec"]["template"]["spec"]["containers"]
    env: list[dict[str, Any]] = containers[0].get("env", [])
    return [entry["name"] for entry in env]


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
    rendered = _render_e2e_job()
    assert 'image: "floe-test-runner:latest"' in rendered
    assert "imagePullPolicy: IfNotPresent" in rendered


def test_test_runner_template_uses_configurable_test_path() -> None:
    """The shared test Job template must not hardcode product E2E test paths."""
    template = _TEMPLATE_PATH.read_text()

    assert '{{- $testPath := default "tests/e2e/" .testPath }}' in template
    assert "- {{ $testPath | quote }}" in template


def test_rendered_bootstrap_job_targets_bootstrap_boundary() -> None:
    """Bootstrap Job runs only the bootstrap validation boundary."""
    args = _rendered_job_args(_render_bootstrap_job())

    assert "tests/bootstrap/" in args
    assert "tests/e2e/" not in args
    marker_index = args.index("-m")
    assert args[marker_index + 1] == "bootstrap"


def test_rendered_e2e_job_targets_product_e2e_boundary() -> None:
    """Product E2E Job keeps the default product E2E path."""
    args = _rendered_job_args(_render_e2e_job())

    assert "tests/e2e/" in args
    assert "tests/bootstrap/" not in args


def test_test_runner_uses_generated_contract_env_helper() -> None:
    """The test Job env table must come from the generated contract helper."""
    template = _TEMPLATE_PATH.read_text()

    assert 'include "floe-platform.testRunner.contractEnv" $context' in template
    assert "name: INTEGRATION_TEST_HOST" not in template
    assert "name: POLARIS_HOST" not in template


def test_rendered_e2e_job_uses_canonical_generated_env_names() -> None:
    """Rendered E2E Job env must use canonical generated contract bindings."""
    env_names = _rendered_e2e_env_names()

    assert "FLOE_EXECUTION_CONTEXT" in env_names
    assert "POLARIS_HOST" in env_names
    assert "POLARIS_PORT" in env_names
    assert "OTEL_COLLECTOR_GRPC_HOST" in env_names
    assert "OTEL_COLLECTOR_GRPC_PORT" in env_names
    assert "INTEGRATION_TEST_HOST" not in env_names
    assert len(env_names) == len(set(env_names))


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
