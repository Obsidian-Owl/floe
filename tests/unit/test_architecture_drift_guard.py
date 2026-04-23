"""Regression tests for architecture drift guard scripts."""

from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_architecture_drift_rejects_single_quoted_platform_service_map(
    tmp_path: Path,
) -> None:
    """Single-quoted duplicated platform service maps must be rejected."""
    duplicated_map = tmp_path / "duplicated_service_map.py"
    duplicated_map.write_text("SERVICE_DEFAULT_PORTS = {'polaris': 8181}\n")

    result = subprocess.run(
        [
            str(PROJECT_ROOT / "scripts/check-architecture-drift"),
            str(duplicated_map),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "duplicated platform service map detected" in result.stderr
