"""Ralph Wiggum workflow test configuration.

This conftest.py provides shared fixtures and configuration for all
Ralph workflow tests.

Note:
    Ralph tests validate the agentic workflow system including:
    - Quality gates (deterministic checkpoints)
    - Git worktree lifecycle
    - State machine transitions
    - Memory buffer operations
"""

from __future__ import annotations

import pytest

# Use pytest_plugins to load fixtures from the testing module
# This avoids import resolution issues with pyright
pytest_plugins = ["testing.fixtures.ralph"]


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with Ralph-specific markers."""
    config.addinivalue_line(
        "markers",
        "ralph: Marks tests as Ralph Wiggum workflow tests",
    )
    config.addinivalue_line(
        "markers",
        "dry_run: Marks tests that run in dry-run mode (no side effects)",
    )
    config.addinivalue_line(
        "markers",
        "requires_git: Marks tests that require git operations",
    )
