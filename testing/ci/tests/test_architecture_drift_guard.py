"""Regression tests for architecture drift guard scripts."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run_architecture_drift(target: Path) -> subprocess.CompletedProcess[str]:
    """Run the architecture drift script against a target file."""
    return subprocess.run(
        [
            str(PROJECT_ROOT / "scripts/check-architecture-drift"),
            str(target),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_architecture_drift_reaches_summary_under_set_e(tmp_path: Path) -> None:
    """Counter increments must not exit before the summary under set -e."""
    parser_module = ("s" + "ql") + ("pa" + "rse")
    validation_suffix = "s" + "ql"
    drift_file = tmp_path / "sql_drift.py"
    drift_file.write_text(
        f"import {parser_module}\n"
        "\n"
        f"def validate_{validation_suffix}(text: str) -> bool:\n"
        "    return True\n"
    )

    result = run_architecture_drift(drift_file)

    assert result.returncode == 2
    assert "ARCHITECTURE DRIFT DETECTED" in result.stderr
    assert "Violations: 1, Warnings: 1" in result.stderr


def test_architecture_drift_import_count_reaches_warning_summary() -> None:
    """Root test import counting must not exit before the warning summary."""
    drift_file = PROJECT_ROOT / "tests" / "unit" / f"test_arch_drift_{uuid.uuid4().hex}.py"
    drift_file.write_text("def test_placeholder() -> None:\n    pass\n")
    try:
        result = run_architecture_drift(drift_file)
    finally:
        drift_file.unlink(missing_ok=True)

    assert result.returncode == 1
    assert "Root-level test imports from <2 packages" in result.stderr
    assert "ARCHITECTURE DRIFT WARNINGS" in result.stderr
    assert "Warnings: 1" in result.stderr


def test_architecture_drift_rejects_single_quoted_platform_service_map(
    tmp_path: Path,
) -> None:
    """Duplicated platform service maps in Python must be rejected."""
    component_name = "pola" + "ris"
    duplicated_map = tmp_path / "duplicated_service_map.py"
    duplicated_map.write_text(f"SERVICE_DEFAULT_PORTS = {{{component_name!r}: 8181}}\n")

    result = run_architecture_drift(duplicated_map)

    assert result.returncode == 2
    assert "duplicated platform service map detected" in result.stderr


def test_architecture_drift_rejects_non_python_platform_service_map(
    tmp_path: Path,
) -> None:
    """Duplicated platform service maps in YAML must be rejected."""
    component_name = "pola" + "ris"
    duplicated_map = tmp_path / "duplicated_service_map.yaml"
    duplicated_map.write_text(f'ports:\n  "{component_name}": 8181\n')

    result = run_architecture_drift(duplicated_map)

    assert result.returncode == 2
    assert "duplicated platform service map detected" in result.stderr


def test_architecture_drift_allows_nested_platform_service_config_map(
    tmp_path: Path,
) -> None:
    """Nested service configuration maps are examples, not duplicate port tables."""
    component_name = "pola" + "ris"
    nested_config = tmp_path / "nested_service_config.py"
    nested_config.write_text(
        f"generator.add_plugin_values({{{component_name!r}: {{'enabled': True}}}})\n"
    )

    result = run_architecture_drift(nested_config)

    assert result.returncode == 0, result.stderr
