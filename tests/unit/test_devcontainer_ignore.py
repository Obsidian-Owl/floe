"""Structural tests for DevPod upload context exclusions."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEVCONTAINER_IGNORE = REPO_ROOT / ".devcontainerignore"


def _ignore_patterns() -> set[str]:
    return {
        line.strip()
        for line in DEVCONTAINER_IGNORE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


@pytest.mark.requirement("AC-2")
def test_devcontainerignore_excludes_nested_python_caches_and_virtualenvs() -> None:
    """DevPod must not upload package-local caches or virtualenvs to Hetzner."""
    patterns = _ignore_patterns()

    assert "**/.venv/" in patterns
    assert "**/.mypy_cache/" in patterns
    assert "**/.pytest_cache/" in patterns
    assert "**/.ruff_cache/" in patterns
    assert "devtools/agent-memory/.venv/" in patterns
    assert "packages/floe-core/.venv/" in patterns
    assert "plugins/floe-alert-webhook/.mypy_cache/" in patterns


@pytest.mark.requirement("AC-2")
def test_devcontainerignore_excludes_generated_runtime_artifacts() -> None:
    """Remote context should exclude generated logs, coverage, and test artifacts."""
    patterns = _ignore_patterns()

    assert "demo/**/logs/" in patterns
    assert "test-logs/" in patterns
    assert "test-artifacts/" in patterns
    assert "coverage*.xml" in patterns
    assert "coverage.json" in patterns
    assert "demo/customer-360/logs/" in patterns
    assert "demo/customer-360/target/" in patterns


@pytest.mark.requirement("AC-2")
def test_devcontainerignore_excludes_local_tool_state() -> None:
    """Local agent/search/index state should not be uploaded to DevPod."""
    patterns = _ignore_patterns()

    assert ".gitnexus/" in patterns
    assert ".import_linter_cache/" in patterns
    assert ".cognee/" in patterns
    assert ".omc/" in patterns
    assert "target/" in patterns
