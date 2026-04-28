"""Tests for rendering Dagster demo image Helm overrides."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

MODULE_PATH = Path(__file__).resolve().parents[1] / "render-demo-image-values.py"
spec = importlib.util.spec_from_file_location("render_demo_image_values", MODULE_PATH)
assert spec is not None and spec.loader is not None
render_demo_image_values = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_demo_image_values)


def test_render_demo_image_values_sets_all_dagster_image_consumers() -> None:
    rendered = render_demo_image_values.render_values(
        repository="floe-dagster-demo",
        tag="72c3dcf7e273",
        pull_policy="Never",
    )

    values = yaml.safe_load(rendered)
    expected_image = {
        "repository": "floe-dagster-demo",
        "tag": "72c3dcf7e273",
        "pullPolicy": "Never",
    }

    assert values["dagsterDemoImage"] == expected_image
    assert values["dagster"]["dagsterWebserver"]["image"] == expected_image
    assert values["dagster"]["dagsterDaemon"]["image"] == expected_image
    assert values["dagster"]["runLauncher"]["config"]["k8sRunLauncher"]["image"] == expected_image
    assert (
        values["dagster"]["runLauncher"]["config"]["k8sRunLauncher"]["imagePullPolicy"] == "Never"
    )


def test_render_demo_image_values_rejects_empty_repository() -> None:
    try:
        render_demo_image_values.render_values(repository="", tag="abc", pull_policy="Never")
    except SystemExit as exc:
        assert "repository cannot be empty" in str(exc)
    else:
        raise AssertionError("empty repository must fail")


def test_render_demo_image_values_rejects_empty_tag() -> None:
    try:
        render_demo_image_values.render_values(
            repository="floe-dagster-demo", tag="", pull_policy="Never"
        )
    except SystemExit as exc:
        assert "tag cannot be empty" in str(exc)
    else:
        raise AssertionError("empty tag must fail")
