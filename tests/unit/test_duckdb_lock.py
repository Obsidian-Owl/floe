"""Structural tests for DuckDB lock stability.

The demo Docker image exports third-party dependencies from ``uv.lock`` into
hash-verified ``requirements.txt`` and installs them with pip. DuckDB
prerelease artifacts are not stable enough for that path: a yanked or removed
dev wheel breaks remote DevPod E2E before product tests can run.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_UV_LOCK = _REPO_ROOT / "uv.lock"


def _duckdb_lock_block() -> str:
    """Return the ``uv.lock`` package block for DuckDB."""
    content = _UV_LOCK.read_text()
    match = re.search(
        r'(?ms)^\[\[package\]\]\nname = "duckdb"\n.*?(?=^\[\[package\]\]|\Z)',
        content,
    )
    assert match is not None, "uv.lock must contain a package block for duckdb"
    return match.group(0)


@pytest.mark.requirement("DEVPOD-REMOTE-E2E")
def test_duckdb_lock_uses_published_stable_release() -> None:
    """DuckDB must be locked to a stable release for remote Docker builds."""
    block = _duckdb_lock_block()

    version_match = re.search(r'^version = "([^"]+)"$', block, re.MULTILINE)
    assert version_match is not None, "duckdb lock block must contain a version"
    version = version_match.group(1)

    assert "dev" not in version and re.search(r"[a-zA-Z]", version) is None, (
        f"duckdb is locked to prerelease {version!r}; remote Docker builds export uv.lock "
        "to requirements.txt and require a stable PyPI release."
    )


@pytest.mark.requirement("DEVPOD-REMOTE-E2E")
def test_workspace_constraints_pin_duckdb_stable_release() -> None:
    """The lock policy must keep global prerelease mode from selecting DuckDB dev builds."""
    content = _PYPROJECT.read_text()

    assert re.search(r'"duckdb==\d+\.\d+\.\d+"', content) is not None, (
        "pyproject.toml must pin duckdb to a stable release in tool.uv "
        "constraint-dependencies so global prerelease resolution cannot select "
        "ephemeral DuckDB dev builds."
    )
