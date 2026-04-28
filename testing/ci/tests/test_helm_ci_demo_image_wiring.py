"""Regression tests for Helm CI demo image wiring."""

from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/helm-ci.yaml")


def test_helm_ci_builds_demo_image_before_installing_test_values() -> None:
    workflow = WORKFLOW.read_text()
    build_index = workflow.find("make build-demo-image")
    install_index = workflow.find("helm upgrade --install floe-test charts/floe-platform")

    assert build_index != -1, "Helm CI must build/load the Dagster demo image"
    assert install_index != -1, "Helm CI must install the floe-platform chart"
    assert build_index < install_index, "demo image must be loaded before Helm install"


def test_helm_ci_builds_demo_image_with_make_env_names() -> None:
    workflow = WORKFLOW.read_text()

    assert (
        'DEMO_IMAGE_REPOSITORY="${FLOE_DEMO_IMAGE_REPOSITORY}" \\\n'
        '            DEMO_IMAGE_TAG="${FLOE_DEMO_IMAGE_TAG}" \\\n'
        "            make build-demo-image"
    ) in workflow


def test_helm_ci_passes_generated_demo_image_values_to_install_and_diff() -> None:
    workflow = WORKFLOW.read_text()
    values_sequence = (
        "--values charts/floe-platform/values-test.yaml \\\n"
        "            --values /tmp/floe-demo-image-values.yaml"
    )

    assert "render-demo-image-values.py" in workflow
    assert "/tmp/floe-demo-image-values.yaml" in workflow
    assert workflow.count("--values /tmp/floe-demo-image-values.yaml") >= 2
    assert (
        f"helm diff upgrade floe-test charts/floe-platform \\\n"
        f"            --namespace floe-test \\\n"
        f"            {values_sequence}"
    ) in workflow
    assert (
        f"helm upgrade --install floe-test charts/floe-platform \\\n"
        f"            --namespace floe-test --create-namespace \\\n"
        f"            {values_sequence}"
    ) in workflow
