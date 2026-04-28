"""Regression tests for Helm CI demo image wiring."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/helm-ci.yaml")


def _workflow() -> dict[str, object]:
    loaded = yaml.safe_load(WORKFLOW.read_text())
    assert isinstance(loaded, dict)
    return loaded


def _integration_step_command(name: str) -> str:
    workflow = _workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    integration = jobs["integration"]
    assert isinstance(integration, dict)
    steps = integration["steps"]
    assert isinstance(steps, list)

    for step in steps:
        assert isinstance(step, dict)
        if step.get("name") == name:
            run = step.get("run")
            assert isinstance(run, str)
            return run
    raise AssertionError(f"missing integration step: {name}")


def _integration_step_names() -> list[str]:
    workflow = _workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    integration = jobs["integration"]
    assert isinstance(integration, dict)
    steps = integration["steps"]
    assert isinstance(steps, list)
    return [str(step.get("name")) for step in steps if isinstance(step, dict)]


def _stripped_lines(command: str) -> list[str]:
    return [line.strip() for line in command.splitlines() if line.strip()]


def _assert_values_override_after_test_values(command: str) -> None:
    lines = _stripped_lines(command)
    test_values_index = lines.index("--values charts/floe-platform/values-test.yaml \\")
    override_values_index = lines.index("--values /tmp/floe-demo-image-values.yaml \\")
    assert test_values_index < override_values_index


def test_helm_ci_builds_demo_image_before_installing_test_values() -> None:
    workflow = WORKFLOW.read_text()
    build_index = workflow.find("make build-demo-image")
    install_index = workflow.find("helm upgrade --install floe-test charts/floe-platform")

    assert build_index != -1, "Helm CI must build/load the Dagster demo image"
    assert install_index != -1, "Helm CI must install the floe-platform chart"
    assert build_index < install_index, "demo image must be loaded before Helm install"


def test_helm_ci_installs_python_dependencies_before_building_demo_image() -> None:
    step_names = _integration_step_names()

    setup_python_index = step_names.index("Set up Python")
    setup_uv_index = step_names.index("Install uv")
    sync_index = step_names.index("Install dependencies")
    build_index = step_names.index("Build and load Dagster demo image")

    assert setup_python_index < build_index
    assert setup_uv_index < build_index
    assert sync_index < build_index
    assert _integration_step_command("Install dependencies") == "uv sync --all-extras --dev"


def test_helm_ci_builds_demo_image_with_make_env_names() -> None:
    command = _integration_step_command("Build and load Dagster demo image")

    assert 'DEMO_IMAGE_REPOSITORY="${FLOE_DEMO_IMAGE_REPOSITORY}"' in command
    assert 'DEMO_IMAGE_TAG="${FLOE_DEMO_IMAGE_TAG}"' in command
    assert "make build-demo-image" in command
    assert 'FLOE_DEMO_IMAGE_REPOSITORY="${FLOE_DEMO_IMAGE_REPOSITORY}"' not in command
    assert 'FLOE_DEMO_IMAGE_TAG="${FLOE_DEMO_IMAGE_TAG}"' not in command


def test_helm_ci_path_filters_include_demo_image_helper_tests() -> None:
    workflow = WORKFLOW.read_text()

    assert "testing/ci/render-demo-image-values.py" in workflow
    assert "testing/ci/tests/**" in workflow


def test_helm_ci_passes_generated_demo_image_values_to_install_and_diff() -> None:
    build_command = _integration_step_command("Build and load Dagster demo image")
    diff_command = _integration_step_command(
        "Diff upgrade (informational — exits 2 on fresh cluster, non-zero is expected)"
    )
    install_command = _integration_step_command("Install floe-platform chart with test values")

    assert "uv run python testing/ci/render-demo-image-values.py" in build_command
    assert "/tmp/floe-demo-image-values.yaml" in build_command
    _assert_values_override_after_test_values(diff_command)
    _assert_values_override_after_test_values(install_command)
