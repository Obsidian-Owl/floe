"""Integration proof for Unit D test-artifacts PVC ownership.

`values-test.yaml` intentionally keeps `tests.enabled=false` for normal
platform installs, so a plain `helm upgrade --install charts/floe-platform
-f values-test.yaml` will not render the test PVC at all. This test therefore
builds a focused temporary chart from the real `_helpers.tpl` and
`templates/tests/pvc-artifacts.yaml`, then installs that chart with
`tests.enabled=true` into a real cluster. The proof stays on the exact PVC
template logic this unit owns while avoiding unrelated test Job resources.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


def _run_command(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    """Run a command and capture stdout/stderr as text."""

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _build_focused_pvc_chart(temp_root: Path, platform_chart_path: Path) -> tuple[Path, Path]:
    """Create a temporary chart containing only the real PVC template."""

    helpers_template = platform_chart_path / "templates" / "_helpers.tpl"
    pvc_template = platform_chart_path / "templates" / "tests" / "pvc-artifacts.yaml"
    values_defaults = platform_chart_path / "values.yaml"
    values_test = platform_chart_path / "values-test.yaml"

    assert helpers_template.exists(), f"Missing chart helpers at {helpers_template}"
    assert pvc_template.exists(), f"Missing PVC template at {pvc_template}"
    assert values_defaults.exists(), f"Missing default values at {values_defaults}"
    assert values_test.exists(), f"Missing test values at {values_test}"

    chart_dir = temp_root / "floe-platform-pvc-only"
    (chart_dir / "templates" / "tests").mkdir(parents=True, exist_ok=True)
    (chart_dir / "Chart.yaml").write_text(
        'apiVersion: v2\nname: floe-platform\nversion: 0.1.0\nappVersion: "1.0.0"\n',
        encoding="utf-8",
    )
    shutil.copy2(values_defaults, chart_dir / "values.yaml")
    shutil.copy2(helpers_template, chart_dir / "templates" / "_helpers.tpl")
    shutil.copy2(pvc_template, chart_dir / "templates" / "tests" / "pvc-artifacts.yaml")
    return chart_dir, values_test


def _load_test_artifacts_pvc_name(values_test: Path) -> str:
    """Return the configured test-artifacts PVC name from values-test.yaml."""

    values = yaml.safe_load(values_test.read_text(encoding="utf-8"))
    assert isinstance(values, dict), f"{values_test} did not parse to a mapping"

    pvc_name = values.get("tests", {}).get("artifacts", {}).get("pvcName")
    assert isinstance(pvc_name, str) and pvc_name, (
        "values-test.yaml must expose tests.artifacts.pvcName for the focused PVC proof."
    )
    return pvc_name


@pytest.mark.requirement("AC-4")
@pytest.mark.requirement("AC-5")
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.usefixtures("kind_cluster", "helm_available")
def test_pvc_template_is_helm_owned_and_repeat_upgrade_safe(
    platform_chart_path: Path,
    test_namespace: str,
    helm_release_name: str,
    tmp_path: Path,
) -> None:
    """Install the real PVC template through Helm and verify repeat upgrade safety."""

    chart_dir, values_test = _build_focused_pvc_chart(tmp_path, platform_chart_path)
    release_name = f"{helm_release_name}-pvc"
    pvc_name = _load_test_artifacts_pvc_name(values_test)

    install_result = _run_command(
        [
            "helm",
            "upgrade",
            "--install",
            release_name,
            str(chart_dir),
            "--namespace",
            test_namespace,
            "-f",
            str(values_test),
            "--set",
            "tests.enabled=true",
        ],
        timeout=180,
    )
    assert install_result.returncode == 0, (
        "Initial focused PVC install failed.\n"
        f"STDOUT:\n{install_result.stdout}\nSTDERR:\n{install_result.stderr}"
    )

    pvc_label_result = _run_command(
        [
            "kubectl",
            "get",
            "pvc",
            pvc_name,
            "-n",
            test_namespace,
            "-o",
            r"jsonpath={.metadata.labels.app\.kubernetes\.io/managed-by}",
        ]
    )
    assert pvc_label_result.returncode == 0, (
        "Could not read the managed-by label from the installed PVC.\n"
        f"STDOUT:\n{pvc_label_result.stdout}\nSTDERR:\n{pvc_label_result.stderr}"
    )
    assert pvc_label_result.stdout.strip() == "Helm", (
        "PVC should be Helm-owned from creation. "
        f"Observed managed-by label: {pvc_label_result.stdout!r}"
    )

    second_upgrade_result = _run_command(
        [
            "helm",
            "upgrade",
            release_name,
            str(chart_dir),
            "--namespace",
            test_namespace,
            "-f",
            str(values_test),
            "--set",
            "tests.enabled=true",
        ],
        timeout=180,
    )
    second_output = "\n".join(
        part for part in (second_upgrade_result.stdout, second_upgrade_result.stderr) if part
    )
    assert second_upgrade_result.returncode == 0, (
        "Repeat Helm upgrade failed for the focused PVC chart.\n"
        f"STDOUT:\n{second_upgrade_result.stdout}\nSTDERR:\n{second_upgrade_result.stderr}"
    )
    assert "cannot be imported into the current release" not in second_output, (
        "Repeat Helm upgrade hit the Helm ownership import error that Unit D is "
        f"meant to eliminate.\nCombined output:\n{second_output}"
    )
