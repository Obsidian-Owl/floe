"""E2E test configuration for Ralph Wiggum workflow.

This conftest.py provides E2E-specific fixtures with longer timeouts
and full workflow setup.

E2E tests exercise complete workflows:
- spawn → work → integrate → cleanup
- Quality gate chains
- State machine transitions
- Parallel agent coordination
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from testing.base_classes.ralph_test_base import RalphTestBase


@pytest.fixture
def e2e_timeout() -> int:
    """Default timeout for E2E tests in seconds."""
    return 300  # 5 minutes


@pytest.fixture
def agent_state_dir(tmp_path: Path) -> Path:
    """Create a complete .agent directory structure.

    Returns:
        Path to .agent directory with all required files.
    """
    agent_dir = tmp_path / ".agent"
    agent_dir.mkdir()

    # Create activity.md
    (agent_dir / "activity.md").write_text(
        "# Agent Activity Log\n\n"
        "## Session Start\n\n"
        "- Initialized at test start\n"
    )

    # Create PROMPT.md
    (agent_dir / "PROMPT.md").write_text(
        "# Agent Instructions\n\n"
        "This is a test agent. Follow the plan.json subtasks.\n"
    )

    # Create constitution.md (copy from .specify/memory if exists)
    constitution_path = Path.cwd() / ".specify" / "memory" / "constitution.md"
    if constitution_path.exists():
        (agent_dir / "constitution.md").write_text(constitution_path.read_text())
    else:
        (agent_dir / "constitution.md").write_text(
            "# Test Constitution\n\n"
            "1. Tests MUST pass\n"
            "2. Code MUST be clean\n"
        )

    return agent_dir


@pytest.fixture
def e2e_plan_json(agent_state_dir: Path) -> dict[str, Any]:
    """Create a plan.json for E2E testing.

    Returns:
        Dictionary with plan structure, also written to agent_state_dir/plan.json.
    """
    plan = {
        "task_id": "E2E-001",
        "linear_id": "FLO-E2E",
        "epic": "EPTEST",
        "status": "in_progress",
        "subtasks": [
            {"id": "E2E-001.1", "description": "Create test file", "passes": False},
            {"id": "E2E-001.2", "description": "Run quality gates", "passes": False},
            {"id": "E2E-001.3", "description": "Commit changes", "passes": False},
        ],
        "iteration": 1,
        "max_iterations": 15,
        "completion_signal": None,
    }

    (agent_state_dir / "plan.json").write_text(json.dumps(plan, indent=2))
    return plan


@pytest.fixture
def e2e_worktree(
    request: pytest.FixtureRequest,
) -> Generator[Path, None, None]:
    """Create a real worktree for E2E testing.

    This fixture creates an actual git worktree and cleans it up
    after the test completes.

    Yields:
        Path to the created worktree.
    """
    # Get a unique name based on test function
    node_name: str = getattr(request.node, "name", "test")
    test_name: str = node_name[:20]  # Truncate long names

    # Create a test base instance to use its worktree management
    base = RalphTestBase()
    base.setup_method()

    try:
        worktree = base.create_test_worktree(f"e2e-{test_name}")
        yield worktree
    finally:
        base.teardown_method()


@pytest.fixture
def e2e_manifest(tmp_path: Path) -> Path:
    """Create a manifest.json for E2E testing.

    Returns:
        Path to manifest.json file.
    """
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
    }

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path
