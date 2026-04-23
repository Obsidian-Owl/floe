"""Regression tests for architecture drift guard scripts."""

from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def test_architecture_drift_rejects_single_quoted_platform_service_map(
    tmp_path: Path,
) -> None:
    """Single-quoted duplicated platform service maps must be rejected."""
    service_key = "pola" + "ris"
    duplicated_map = tmp_path / "duplicated_service_map.py"
    duplicated_map.write_text(f"SERVICE_DEFAULT_PORTS = {{{service_key!r}: 8181}}\n")

    result = run_architecture_drift(duplicated_map)

    assert result.returncode == 2
    assert "duplicated platform service map detected" in result.stderr


def test_architecture_drift_allows_nested_platform_service_config_map(
    tmp_path: Path,
) -> None:
    """Nested service configuration maps are examples, not duplicate port tables."""
    service_key = "pola" + "ris"
    nested_config = tmp_path / "nested_service_config.py"
    nested_config.write_text(
        f"generator.add_plugin_values({{{service_key!r}: {{'enabled': True}}}})\n"
    )

    result = run_architecture_drift(nested_config)

    assert result.returncode == 0, result.stderr
