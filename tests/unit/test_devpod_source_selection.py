"""Structural tests for Git-backed DevPod source selection."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SOURCE_HELPER = _REPO_ROOT / "scripts" / "devpod-source.sh"
_DEVPOD_TEST = _REPO_ROOT / "scripts" / "devpod-test.sh"
_DEVPOD_READY = _REPO_ROOT / "scripts" / "devpod-ensure-ready.sh"
_MAKEFILE = _REPO_ROOT / "Makefile"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"


def _read(path: Path) -> str:
    return path.read_text()


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_source_helper_defaults_to_remote_git_branch() -> None:
    """DevPod source resolution must avoid local worktree upload by default."""
    helper = _read(_SOURCE_HELPER)

    assert "DEVPOD_SOURCE" in helper
    assert "DEVPOD_ALLOW_LOCAL_SOURCE" in helper
    assert "git ls-remote --exit-code --heads" in helper
    assert "git:%s@%s" in helper
    assert "printf '%s\\n' \"${project_root}\"" in helper
    assert "Remote branch" in helper


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_full_lifecycle_uses_devpod_source_flag() -> None:
    """Full lifecycle validation must clone on Hetzner, not upload the repo."""
    script = _read(_DEVPOD_TEST)

    assert 'source "${SCRIPT_DIR}/devpod-source.sh"' in script
    assert 'devpod_resolve_source "${PROJECT_ROOT}"' in script
    assert 'devpod up "${WORKSPACE}"' in script
    assert '--source "${DEVPOD_SOURCE_RESOLVED}"' in script
    assert 'devpod up "${PROJECT_ROOT}"' not in script


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_full_lifecycle_provider_check_is_pipefail_safe() -> None:
    """DevPod provider preflight must not use grep -q under pipefail.

    Some CLI producers receive SIGPIPE when `grep -q` exits after its first
    match. With `set -o pipefail`, that turns a successful match into a failed
    preflight before the Hetzner workspace is even created.
    """
    script = _read(_DEVPOD_TEST)

    assert "provider_list=" in script
    assert "devpod provider list 2>/dev/null || true" in script
    assert 'grep -q "hetzner"' not in script


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_readiness_restart_uses_same_source_selection() -> None:
    """Auto-started workspaces must use the same remote-source path."""
    script = _read(_DEVPOD_READY)

    assert 'source "${SCRIPT_DIR}/devpod-source.sh"' in script
    assert 'devpod_resolve_source "${PROJECT_ROOT}"' in script
    assert '--source "${DEVPOD_SOURCE_RESOLVED}"' in script
    assert 'devpod up "${PROJECT_ROOT}"' not in script


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_make_devpod_up_uses_source_helper() -> None:
    """Manual DevPod startup must not retain the local-folder upload path."""
    makefile = _read(_MAKEFILE)

    assert "source scripts/devpod-source.sh" in makefile
    assert '--source "$${source_resolved}"' in makefile
    assert "devpod up ." not in makefile


@pytest.mark.requirement("AC-DevPod-Git-Source")
def test_env_documents_remote_source_controls() -> None:
    """Source controls must be discoverable without reading shell internals."""
    env_example = _read(_ENV_EXAMPLE)

    for variable in (
        "DEVPOD_SOURCE",
        "DEVPOD_GIT_REF",
        "DEVPOD_ALLOW_LOCAL_SOURCE",
    ):
        assert variable in env_example
