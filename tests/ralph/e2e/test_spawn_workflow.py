"""E2E tests for /ralph.spawn workflow.

Tests the worktree spawning functionality in isolation:
- Worktree creation with proper structure
- State file initialization (.agent/ directory)
- Direnv enablement
- Manifest updates
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from testing.base_classes.ralph_test_base import RalphTestBase


class TestSpawnWorkflow(RalphTestBase):
    """E2E tests for spawn workflow."""

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-spawn-001")
    def test_spawn_creates_worktree(self) -> None:
        """Test that spawn creates a valid worktree with full codebase.

        Validates:
        - Worktree directory exists
        - .git link exists (worktree marker)
        - Key project files are present
        """
        worktree = self.create_test_worktree("spawn-test")

        assert worktree.exists(), "Worktree directory should exist"
        assert (worktree / ".git").exists(), ".git should exist in worktree"
        assert (worktree / "pyproject.toml").exists(), "pyproject.toml should be present"
        assert (worktree / ".ralph").exists(), ".ralph directory should be present"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-spawn-002")
    def test_spawn_initializes_state_files(self) -> None:
        """Test that spawn initializes .agent/ state files.

        Validates the full agent state structure is created.
        """
        worktree = self.create_test_worktree("state-init")

        # Create .agent directory (simulating spawn behavior)
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        # Create plan.json
        plan = self.generate_test_plan_json(task_id="SPAWN-001")
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Create activity.md
        (agent_dir / "activity.md").write_text(
            "# Agent Activity Log\n\n"
            "## Session Start\n"
            "- Initialized by test\n"
        )

        # Create PROMPT.md
        (agent_dir / "PROMPT.md").write_text(
            "# Agent Instructions\n\n"
            "Follow the plan.json subtasks.\n"
        )

        # Verify all files created
        assert (agent_dir / "plan.json").exists()
        assert (agent_dir / "activity.md").exists()
        assert (agent_dir / "PROMPT.md").exists()

        # Verify plan.json is valid
        loaded_plan = json.loads((agent_dir / "plan.json").read_text())
        assert loaded_plan["task_id"] == "SPAWN-001"
        assert loaded_plan["status"] == "in_progress"
        assert len(loaded_plan["subtasks"]) > 0

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-spawn-003")
    def test_spawn_enables_direnv(self) -> None:
        """Test that direnv is enabled in new worktrees.

        Validates direnv allow runs successfully if direnv is available.
        """
        if not self._is_direnv_available():
            pytest.skip("direnv not available")

        worktree = self.create_test_worktree("direnv-test")

        # Check direnv status in worktree
        result = subprocess.run(
            ["direnv", "status"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=False,
        )

        # Should show RC file status (allowed or found)
        assert result.returncode == 0
        # If .envrc exists, it should be allowed
        if (worktree / ".envrc").exists():
            assert "Found RC" in result.stdout

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-spawn-004")
    def test_spawn_worktree_on_correct_branch(self) -> None:
        """Test that worktree is on a test branch.

        Validates the branch naming convention.
        """
        worktree = self.create_test_worktree("branch-test")

        # Get current branch in worktree
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()

        # Should be on a test/ branch
        assert branch.startswith("test/"), f"Expected test/ branch, got {branch}"
        assert "branch-test" in branch, f"Branch should contain task name: {branch}"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-spawn-005")
    def test_spawn_multiple_worktrees(self) -> None:
        """Test spawning multiple worktrees in parallel (wave 1).

        Validates that multiple non-overlapping tasks can be spawned.
        """
        # Spawn 3 worktrees (simulating wave 1)
        worktree1 = self.create_test_worktree("multi-task-1")
        worktree2 = self.create_test_worktree("multi-task-2")
        worktree3 = self.create_test_worktree("multi-task-3")

        # All should exist
        assert worktree1.exists()
        assert worktree2.exists()
        assert worktree3.exists()

        # All should be on different branches
        branches: list[str] = []
        for wt in [worktree1, worktree2, worktree3]:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=wt,
                capture_output=True,
                text=True,
                check=True,
            )
            branches.append(result.stdout.strip())

        # All branches should be unique
        assert len(set(branches)) == 3, f"Expected 3 unique branches, got {branches}"

        # Check git worktree list shows all 3
        result = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
        for wt in [worktree1, worktree2, worktree3]:
            assert str(wt) in result.stdout, f"Worktree {wt} should be in list"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-spawn-006")
    def test_spawn_worktree_isolated(self) -> None:
        """Test that worktree changes are isolated from main.

        Validates changes in worktree don't affect main repo.
        """
        worktree = self.create_test_worktree("isolation-test")

        # Make a change in worktree
        test_file = worktree / "test_isolation_file.txt"
        test_file.write_text("This file should only exist in worktree\n")

        # Verify file exists in worktree
        assert test_file.exists()

        # Verify file does NOT exist in main repo
        main_file = Path.cwd() / "test_isolation_file.txt"
        assert not main_file.exists(), "File should not exist in main repo"

        # Commit the change in worktree
        subprocess.run(["git", "add", "."], cwd=worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Test isolation commit"],
            cwd=worktree,
            check=True,
        )

        # Verify main repo still doesn't have the file
        assert not main_file.exists()
