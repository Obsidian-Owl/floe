"""Unit contracts for Unit D test-artifacts PVC template ownership.

These tests keep the PVC template behavior in the fast host-side Specwright
unit slice:

- the chart-rendered PVC must carry Helm ownership labels when tests are enabled
- the PVC must not render when tests are disabled
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
VALUES_DEFAULTS = REPO_ROOT / "charts" / "floe-platform" / "values.yaml"
VALUES_TEST = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"
HELPERS_TEMPLATE = REPO_ROOT / "charts" / "floe-platform" / "templates" / "_helpers.tpl"
PVC_TEMPLATE = REPO_ROOT / "charts" / "floe-platform" / "templates" / "tests" / "pvc-artifacts.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    assert path.exists(), f"Expected YAML file at {path}"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} did not parse to a dict"
    return data


def _render_pvc_template(values_file: Path, *extra_args: str) -> list[dict[str, Any]]:
    """Render the PVC template through a temporary dependency-free chart."""

    if shutil.which("helm") is None:
        pytest.fail("helm CLI not available on PATH — required for PVC ownership assertions.")

    assert HELPERS_TEMPLATE.exists(), f"Missing chart helpers at {HELPERS_TEMPLATE}"
    assert PVC_TEMPLATE.exists(), f"Missing PVC template at {PVC_TEMPLATE}"

    with tempfile.TemporaryDirectory(prefix="floe-pvc-chart-") as temp_dir:
        temp_chart_dir = Path(temp_dir)
        (temp_chart_dir / "Chart.yaml").write_text(
            'apiVersion: v2\nname: floe-platform\nversion: 0.1.0\nappVersion: "1.0.0"\n',
            encoding="utf-8",
        )
        shutil.copy2(VALUES_DEFAULTS, temp_chart_dir / "values.yaml")

        temp_template_path = temp_chart_dir / "templates" / "tests" / "pvc-artifacts.yaml"
        temp_template_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HELPERS_TEMPLATE, temp_chart_dir / "templates" / "_helpers.tpl")
        shutil.copy2(PVC_TEMPLATE, temp_template_path)

        result = subprocess.run(
            [
                "helm",
                "template",
                "floe-platform",
                str(temp_chart_dir),
                "-f",
                str(values_file),
                *extra_args,
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30,
            check=False,
        )

    assert result.returncode == 0, f"helm template failed: {result.stderr}"

    docs: list[dict[str, Any]] = []
    for raw in yaml.safe_load_all(result.stdout):
        if isinstance(raw, dict) and raw:
            docs.append(raw)
    return docs


@pytest.fixture(scope="module")
def values_test_config() -> dict[str, Any]:
    """Parse values-test.yaml once for expectations."""

    return _load_yaml(VALUES_TEST)


class TestPvcTemplateOwnership:
    """AC-1 / AC-2: Helm template ownership and gating behavior."""

    @pytest.mark.requirement("AC-1")
    def test_pvc_template_renders_helm_managed_labels(
        self,
        values_test_config: dict[str, Any],
    ) -> None:
        """The rendered PVC must carry Helm ownership labels and no hook annotation."""

        docs = _render_pvc_template(VALUES_TEST, "--set", "tests.enabled=true")
        assert len(docs) == 1, (
            "Expected exactly one rendered PVC when tests.enabled=true for "
            "templates/tests/pvc-artifacts.yaml."
        )

        pvc = docs[0]
        assert pvc.get("kind") == "PersistentVolumeClaim", (
            "pvc-artifacts template must render a PersistentVolumeClaim."
        )

        metadata = pvc.get("metadata", {})
        assert isinstance(metadata, dict), "Rendered PVC metadata is missing."

        labels = metadata.get("labels", {})
        assert isinstance(labels, dict), "Rendered PVC labels are missing."
        assert labels.get("app.kubernetes.io/managed-by") == "Helm", (
            "PVC must render the Helm ownership label via floe-platform.labels."
        )
        assert labels.get("app.kubernetes.io/component") == "test-artifacts", (
            "PVC must preserve the test-artifacts component label."
        )

        expected_pvc_name = values_test_config.get("tests", {}).get("artifacts", {}).get("pvcName")
        assert isinstance(expected_pvc_name, str) and expected_pvc_name, (
            "values-test.yaml must expose tests.artifacts.pvcName."
        )
        assert metadata.get("name") == expected_pvc_name, (
            "Rendered PVC name must come from values-test.yaml tests.artifacts.pvcName."
        )

        annotations = metadata.get("annotations") or {}
        assert isinstance(annotations, dict), "Rendered PVC annotations must be a mapping."
        assert "helm.sh/hook" not in annotations, (
            "PVC must be a regular chart resource, not a Helm hook."
        )

    @pytest.mark.requirement("AC-2")
    def test_pvc_template_does_not_render_when_tests_disabled(self) -> None:
        """The PVC must stay absent when tests.enabled=false."""

        docs = _render_pvc_template(VALUES_TEST, "--set", "tests.enabled=false")
        assert docs == [], (
            "templates/tests/pvc-artifacts.yaml must render no documents when tests.enabled=false."
        )
