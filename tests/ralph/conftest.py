"""Ralph Wiggum workflow test configuration.

This conftest.py provides shared fixtures and configuration for all
Ralph workflow tests.

Note:
    Ralph tests validate the agentic workflow system including:
    - Quality gates (deterministic checkpoints)
    - Git worktree lifecycle
    - State machine transitions
    - Memory buffer operations

Session Cleanup:
    The pytest_sessionfinish hook ensures ALL test artifacts are cleaned up
    after the test session, including:
    - Orphaned test/* branches
    - Stale test-ralph-* worktree directories
    - Git worktree metadata
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

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
    config.addinivalue_line(
        "markers",
        "e2e: Marks end-to-end workflow tests (longer running)",
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # noqa: ARG001
    """Clean up ALL orphaned test artifacts after test session.

    This runs after ALL tests complete, ensuring no test artifacts remain
    even if individual test teardowns failed.

    Args:
        session: The pytest session object (unused).
        exitstatus: The exit status code (unused).

    Cleans up:
    1. Git worktree metadata (prune)
    2. Orphaned test/* branches
    3. Stale test-ralph-* directories
    """
    # Silence unused parameter warnings
    del session, exitstatus
    # 1. Prune worktree metadata first
    subprocess.run(
        ["git", "worktree", "prune"],
        check=False,
        capture_output=True,
        text=True,
    )

    # 2. Remove ALL orphaned test/* branches
    result = subprocess.run(
        ["git", "branch", "--list", "test/*"],
        capture_output=True,
        text=True,
        check=False,
    )
    for branch in result.stdout.strip().split("\n"):
        branch = branch.strip().lstrip("* ")
        if branch and branch.startswith("test/"):
            subprocess.run(
                ["git", "branch", "-D", branch],
                check=False,
                capture_output=True,
                text=True,
            )

    # 3. Remove stale test-ralph-* directories in parent directory
    projects_dir = Path.cwd().parent
    for path in projects_dir.glob("test-ralph-*"):
        if path.is_dir():
            # Try git worktree remove first (cleaner)
            result = subprocess.run(
                ["git", "worktree", "remove", str(path), "--force"],
                check=False,
                capture_output=True,
                text=True,
            )
            # If that fails, force remove directory
            if result.returncode != 0 and path.exists():
                shutil.rmtree(path, ignore_errors=True)

    # Final prune to clean up any remaining metadata
    subprocess.run(
        ["git", "worktree", "prune"],
        check=False,
        capture_output=True,
        text=True,
    )
