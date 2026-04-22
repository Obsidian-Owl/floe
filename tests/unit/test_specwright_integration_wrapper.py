"""Regression tests for the Specwright integration dispatcher."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _REPO_ROOT / ".specwright" / "config.json"
_SCRIPT_PATH = _REPO_ROOT / "testing" / "ci" / "test-specwright-integration.sh"


def _run_wrapper(*, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the wrapper with a controlled environment."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", str(_SCRIPT_PATH)],
        cwd=_REPO_ROOT,
        env=merged_env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


@pytest.mark.requirement("AC-5")
def test_specwright_config_uses_integration_dispatcher() -> None:
    """Specwright config points build/verify at the generic integration wrapper."""
    config = json.loads(_CONFIG_PATH.read_text())
    assert config["commands"]["test:integration"] == "./testing/ci/test-specwright-integration.sh"


@pytest.mark.requirement("AC-5")
def test_dispatcher_noop_profile_exits_zero() -> None:
    """The explicit no-op profile should skip cleanly for structural units."""
    result = _run_wrapper(env={"SPECWRIGHT_INTEGRATION_PROFILE": "none"})
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "No targeted Specwright integration suite matched" in result.stdout


@pytest.mark.requirement("AC-5")
def test_dispatcher_unit_c_profile_dry_run_reports_remote_boundary_command() -> None:
    """The Unit C profile should expose the existing remote boundary proof command."""
    result = _run_wrapper(
        env={
            "SPECWRIGHT_INTEGRATION_PROFILE": "unit-c-devpod-boundary",
            "SPECWRIGHT_INTEGRATION_DRY_RUN": "1",
        }
    )
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "Selected profile: unit-c-devpod-boundary" in result.stdout
    assert "tests/integration/test_unit_c_devpod_flux_boundary.py" in result.stdout


@pytest.mark.requirement("AC-5")
def test_dispatcher_auto_detects_unit_c_profile_from_changed_files() -> None:
    """The wrapper should detect the Unit C profile from matching changed files."""
    result = _run_wrapper(
        env={
            "SPECWRIGHT_CHANGED_FILES": "testing/ci/test-unit-c-boundary.sh",
            "SPECWRIGHT_INTEGRATION_DRY_RUN": "1",
        }
    )
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "Selected profile: unit-c-devpod-boundary" in result.stdout
