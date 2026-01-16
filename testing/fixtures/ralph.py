"""Ralph Wiggum workflow test fixtures.

This module provides pytest fixtures for testing the Ralph Wiggum
workflow system:

- dry_run_env: Enable dry-run mode (no side effects)
- isolated_repo: Create isolated test repository
- mock_linear_mcp: Mock Linear MCP responses
- test_manifest: Generate test manifest.json
- test_plan_json: Generate test plan.json

Example:
    def test_spawn_dry_run(dry_run_env: None, test_manifest: Path) -> None:
        # Test spawning with dry-run mode enabled
        result = spawn_agents("EP001")
        assert result.worktrees_created == 0  # No actual creation
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def ralph_dry_run_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable dry-run mode for Ralph operations.

    Sets environment variables that disable actual execution:
    - RALPH_DRY_RUN=true: Log operations without executing
    - RALPH_SKIP_GIT_PUSH=true: Skip git push commands
    - RALPH_SKIP_LINEAR_UPDATE=true: Skip Linear API calls

    Usage:
        def test_spawn_workflow(ralph_dry_run_env: None) -> None:
            # Operations will log but not execute
            spawn_agents("EP001")
    """
    monkeypatch.setenv("RALPH_DRY_RUN", "true")
    monkeypatch.setenv("RALPH_SKIP_GIT_PUSH", "true")
    monkeypatch.setenv("RALPH_SKIP_LINEAR_UPDATE", "true")


@pytest.fixture
def isolated_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create an isolated test repository.

    Clones the current repository to a temporary location with remote
    removed. All git operations are confined to this isolated copy.

    Yields:
        Path to the isolated repository root.

    Usage:
        def test_worktree_creation(isolated_repo: Path) -> None:
            os.chdir(isolated_repo)
            # Git operations are isolated here
            subprocess.run(["git", "worktree", "add", ...])
    """
    repo_path = tmp_path / "test-repo"

    # Clone current repo (local clone, fast)
    subprocess.run(
        ["git", "clone", "--local", ".", str(repo_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    # Remove remote to prevent accidental pushes
    subprocess.run(
        ["git", "remote", "remove", "origin"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )

    # Store original directory
    original_cwd = Path.cwd()

    try:
        yield repo_path
    finally:
        # Return to original directory
        os.chdir(original_cwd)

        # Clean up any worktrees in the isolated repo
        worktree_result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

        for line in worktree_result.stdout.split("\n"):
            if line.startswith("worktree ") and str(repo_path) in line:
                wt_path = line.replace("worktree ", "")
                if wt_path != str(repo_path):  # Don't remove main worktree
                    subprocess.run(
                        ["git", "worktree", "remove", wt_path, "--force"],
                        cwd=repo_path,
                        capture_output=True,
                        check=False,
                    )


@pytest.fixture
def mock_linear_mcp() -> Generator[MagicMock, None, None]:
    """Mock Linear MCP server for testing.

    Provides a mock that simulates Linear MCP responses without
    making actual API calls. Useful for unit testing components
    that interact with Linear.

    Yields:
        MagicMock configured with default Linear responses.

    Usage:
        def test_linear_integration(mock_linear_mcp: MagicMock) -> None:
            mock_linear_mcp.list_issues.return_value = [
                {"id": "FLO-1", "title": "Test Issue", "state": "backlog"}
            ]
            # Test code that calls Linear MCP
    """
    mock = MagicMock()

    # Default responses for common operations
    mock.list_teams.return_value = [
        {"id": "team-1", "name": "floe", "key": "FLO"}
    ]

    mock.list_issues.return_value = [
        {
            "id": "issue-1",
            "identifier": "FLO-1",
            "title": "Test Issue",
            "state": {"name": "Backlog"},
            "project": {"name": "EP001"},
        }
    ]

    mock.get_issue.return_value = {
        "id": "issue-1",
        "identifier": "FLO-1",
        "title": "Test Issue",
        "description": "Test description",
        "state": {"name": "Backlog"},
        "project": {"name": "EP001"},
    }

    mock.update_issue.return_value = {"success": True}
    mock.create_comment.return_value = {"id": "comment-1"}

    yield mock


@pytest.fixture
def test_manifest(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a test manifest.json file.

    Generates a valid manifest.json in a temporary location
    for testing manifest operations.

    Yields:
        Path to the test manifest.json file.

    Usage:
        def test_manifest_loading(test_manifest: Path) -> None:
            manifest = load_manifest(test_manifest.parent)
            assert manifest["schema_version"] == "1.0.0"
    """
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "orchestration": {
            "max_parallel_agents": 5,
            "max_iterations_per_task": 15,
            "stale_worktree_hours": 24,
            "auto_cleanup": True,
        },
        "active_agents": [],
        "completed_today": [],
        "statistics": {
            "total_tasks_completed": 0,
            "average_duration_minutes": 0,
        },
    }

    manifest_path = ralph_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    yield manifest_path


@pytest.fixture
def test_plan_json() -> dict[str, Any]:
    """Generate a test plan.json structure.

    Returns a valid plan.json dictionary for testing agent state.

    Returns:
        Dictionary matching plan.json schema.

    Usage:
        def test_plan_parsing(test_plan_json: dict) -> None:
            plan = AgentPlan.from_dict(test_plan_json)
            assert plan.task_id == "T001"
    """
    return {
        "task_id": "T001",
        "linear_id": "FLO-99",
        "epic": "EP001",
        "status": "in_progress",
        "subtasks": [
            {"id": "T001.1", "description": "Create interface", "passes": True},
            {"id": "T001.2", "description": "Add tests", "passes": False},
            {"id": "T001.3", "description": "Validate constitution", "passes": False},
        ],
        "iteration": 2,
        "max_iterations": 15,
        "completion_signal": None,
    }


@pytest.fixture
def test_activity_md(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a test activity.md file.

    Generates a sample activity.md log file for testing agent logging.

    Yields:
        Path to the test activity.md file.

    Usage:
        def test_activity_logging(test_activity_md: Path) -> None:
            log_activity(test_activity_md.parent, "Test entry")
            content = test_activity_md.read_text()
            assert "Test entry" in content
    """
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir(parents=True, exist_ok=True)

    activity_content = """# Agent Activity Log

## 2026-01-16

### Iteration 1
- Started task T001
- Running lint gate... PASS
- Running type gate... PASS

### Iteration 2
- Running test gate... FAIL
- Error: test_catalog_creation failed
- Analyzing failure...
"""

    activity_path = agent_dir / "activity.md"
    activity_path.write_text(activity_content)

    yield activity_path


@pytest.fixture
def memory_buffer_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a test memory buffer directory structure.

    Sets up the .ralph/memory-buffer/ directory with pending/synced/failed
    subdirectories for testing the write-ahead buffer.

    Yields:
        Path to the memory-buffer directory.

    Usage:
        def test_buffer_write(memory_buffer_dir: Path) -> None:
            buffer = MemoryBuffer(memory_buffer_dir)
            buffer.write(entry)
            assert (memory_buffer_dir / "pending").glob("*.json")
    """
    buffer_dir = tmp_path / ".ralph" / "memory-buffer"
    (buffer_dir / "pending").mkdir(parents=True)
    (buffer_dir / "synced").mkdir(parents=True)
    (buffer_dir / "failed").mkdir(parents=True)

    yield buffer_dir


@pytest.fixture
def mock_cognee_client() -> Generator[MagicMock, None, None]:
    """Mock Cognee client for testing memory operations.

    Provides a mock that simulates Cognee API responses without
    making actual network calls.

    Yields:
        MagicMock configured with default Cognee responses.

    Usage:
        def test_memory_save(mock_cognee_client: MagicMock) -> None:
            mock_cognee_client.add_content.return_value = {"id": "mem-1"}
            # Test code that uses Cognee
    """
    mock = MagicMock()

    mock.search.return_value = MagicMock(
        items=[],
        total=0,
    )

    mock.add_content.return_value = {"id": "content-1", "status": "added"}

    yield mock


# Module exports
__all__ = [
    "ralph_dry_run_env",
    "isolated_repo",
    "mock_linear_mcp",
    "test_manifest",
    "test_plan_json",
    "test_activity_md",
    "memory_buffer_dir",
    "mock_cognee_client",
]
