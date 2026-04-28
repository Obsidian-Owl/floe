"""Structural tests for the DevPod readiness helper."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "devpod-ensure-ready.sh"
_ENV_EXAMPLE_PATH = _REPO_ROOT / ".env.example"


def _read_script() -> str:
    """Return the current DevPod readiness helper source."""
    return _SCRIPT_PATH.read_text()


@pytest.mark.requirement("AC-2")
def test_ensure_ready_uses_documented_auto_start_controls() -> None:
    """The helper must keep auto-start config explicit and discoverable."""
    script = _read_script()
    env_example = _ENV_EXAMPLE_PATH.read_text()

    for variable in ("DEVPOD_AUTO_START", "DEVPOD_PROVIDER", "DEVPOD_DEVCONTAINER"):
        assert variable in script, (
            f"scripts/devpod-ensure-ready.sh must read {variable} instead of "
            "hardcoding DevPod startup behavior."
        )
        assert variable in env_example, (
            f".env.example must document {variable} so users can find the "
            "DevPod startup controls without reading shell internals."
        )


@pytest.mark.requirement("AC-2")
def test_ensure_ready_can_restart_a_stopped_workspace() -> None:
    """A saved stopped workspace should be revived by the helper when auto-start is enabled."""
    script = _read_script()

    assert re.search(r'devpod\s+status.*grep\s+-qi\s+"running"', script), (
        "scripts/devpod-ensure-ready.sh must still detect the running state "
        "before deciding whether startup is needed."
    )
    assert 'devpod_resolve_source "${PROJECT_ROOT}"' in script, (
        "The readiness helper must resolve a Git-backed DevPod source before "
        "starting a saved workspace."
    )
    assert re.search(r'devpod\s+up\s+"\$\{WORKSPACE\}"', script), (
        "The readiness helper must call 'devpod up' with the workspace name "
        "and pass the repository as --source."
    )
    assert '--source "${DEVPOD_SOURCE_RESOLVED}"' in script, (
        "The readiness helper must pass the resolved source through --source "
        "instead of uploading the local worktree."
    )
    for fragment in (
        '--id "${WORKSPACE}"',
        '--provider "${PROVIDER}"',
        '--devcontainer-path "${DEVCONTAINER}"',
        "--ide none",
    ):
        assert fragment in script, (
            "The helper must start the workspace through the same explicit "
            f"DevPod startup inputs used elsewhere ({fragment})."
        )
