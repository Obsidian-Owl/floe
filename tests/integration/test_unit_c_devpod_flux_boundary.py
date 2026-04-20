"""Integration proof for Unit C's remote DevPod + Flux startup boundary."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BOUNDARY_SCRIPT = _REPO_ROOT / "testing" / "ci" / "test-unit-c-boundary.sh"
_PLATFORM_READY_TIMEOUT = int(os.environ.get("UNIT_C_PLATFORM_READY_TIMEOUT", "1200"))
_REMOTE_KIND_STARTUP_TIMEOUT = int(os.environ.get("UNIT_C_REMOTE_KIND_STARTUP_TIMEOUT", "2400"))


def _run_boundary_check(command: str, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run the Unit C boundary wrapper with the requested subcommand."""
    env = os.environ.copy()
    env.setdefault("DEVPOD_WORKSPACE", "floe")
    return subprocess.run(
        [str(_BOUNDARY_SCRIPT), command],
        cwd=_REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


@pytest.mark.requirement("RAC-7")
def test_platform_release_is_ready_on_devpod_cluster() -> None:
    """The Flux-managed floe-platform release must be ready with its secrets present."""
    result = _run_boundary_check("platform-ready", timeout=_PLATFORM_READY_TIMEOUT)
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, (
        "The Unit C platform-ready probe failed. The DevPod cluster must show a "
        "Ready floe-platform release and the required runtime secrets.\n"
        f"{combined}"
    )


@pytest.mark.requirement("RAC-8")
def test_remote_kind_startup_boundary_passes() -> None:
    """The remote Kind path must start the test pod without image/secret startup failures."""
    result = _run_boundary_check("remote-kind-startup", timeout=_REMOTE_KIND_STARTUP_TIMEOUT)
    combined = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, (
        "The Unit C remote-kind-startup probe failed. The test pod must reach "
        "startup without ImagePullBackOff, ErrImagePull, or "
        "CreateContainerConfigError.\n"
        f"{combined}"
    )
