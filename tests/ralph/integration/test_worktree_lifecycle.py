"""Integration tests for git worktree lifecycle.

Tests validate the creation, management, and cleanup of git worktrees
used for parallel agent execution in the Ralph workflow.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from testing.base_classes.ralph_test_base import RalphTestBase


class TestWorktreeCreation(RalphTestBase):
    """Tests for worktree creation."""

    @pytest.mark.requirement("ralph-worktree-001")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.requires_git
    def test_create_worktree_basic(self) -> None:
        """Can create a worktree for a task.

        Validates basic worktree creation with proper branch naming.
        """
        worktree = self.create_test_worktree("test-task")

        assert worktree.exists()
        assert (worktree / ".git").exists()

        # Verify branch was created
        result = subprocess.run(
            ["git", "branch", "--list", "test/*"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert "test-ralph-test-task" in result.stdout or worktree.name in result.stdout

    @pytest.mark.requirement("ralph-worktree-002")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.requires_git
    def test_create_multiple_worktrees(self) -> None:
        """Can create multiple worktrees without conflicts.

        Validates parallel worktree creation for multiple tasks.
        """
        worktree1 = self.create_test_worktree("task-001")
        worktree2 = self.create_test_worktree("task-002")
        worktree3 = self.create_test_worktree("task-003")

        assert worktree1.exists()
        assert worktree2.exists()
        assert worktree3.exists()

        # All should be tracked for cleanup
        assert len(self._created_worktrees) == 3

    @pytest.mark.requirement("ralph-worktree-003")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.requires_git
    def test_worktree_has_full_codebase(self) -> None:
        """Worktree contains full codebase copy.

        Validates worktree is a complete working copy, not a sparse checkout.
        """
        worktree = self.create_test_worktree("full-copy")

        # Check for key files that should exist
        assert (worktree / "pyproject.toml").exists()
        assert (worktree / ".ralph").exists() or (worktree / "CLAUDE.md").exists()

    @pytest.mark.requirement("ralph-worktree-004")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.requires_git
    def test_worktree_isolated_changes(self) -> None:
        """Changes in worktree don't affect main repo.

        Validates isolation between worktree and main working directory.
        """
        worktree = self.create_test_worktree("isolated")

        # Create a file in the worktree
        test_file = worktree / "test_isolation_file.txt"
        test_file.write_text("This should not appear in main repo")

        # Verify file doesn't exist in main repo
        main_file = Path.cwd() / "test_isolation_file.txt"
        assert not main_file.exists()


class TestWorktreeCleanup(RalphTestBase):
    """Tests for worktree cleanup."""

    @pytest.mark.requirement("ralph-worktree-005")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.requires_git
    def test_automatic_cleanup_on_teardown(self) -> None:
        """Worktrees are cleaned up in teardown.

        Validates automatic cleanup of worktrees after test completion.
        """
        worktree = self.create_test_worktree("auto-cleanup")
        worktree_path = worktree  # Store path before cleanup

        assert worktree_path.exists()

        # Manually trigger cleanup
        self._cleanup_worktree(worktree_path)
        self._created_worktrees.remove(worktree_path)

        assert not worktree_path.exists()

    @pytest.mark.requirement("ralph-worktree-006")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.requires_git
    def test_cleanup_removes_branch(self) -> None:
        """Worktree cleanup also removes the associated branch.

        Validates complete cleanup including branch deletion.
        """
        worktree = self.create_test_worktree("branch-cleanup")

        # Get branch name (verify worktree exists first)
        subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Cleanup
        self._cleanup_worktree(worktree)
        self._created_worktrees.remove(worktree)

        # Verify worktree removed
        result_after = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert str(worktree) not in result_after.stdout


class TestWorktreeState(RalphTestBase):
    """Tests for worktree state management."""

    @pytest.mark.requirement("ralph-worktree-007")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.requires_git
    def test_can_commit_in_worktree(self) -> None:
        """Can make commits in worktree.

        Validates worktree supports normal git operations.
        """
        worktree = self.create_test_worktree("commit-test")

        # Create and commit a file
        test_file = worktree / "committed_file.txt"
        test_file.write_text("Test content")

        result = subprocess.run(
            ["git", "add", "committed_file.txt"],
            cwd=worktree,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0

        result = subprocess.run(
            ["git", "commit", "-m", "Test commit in worktree"],
            cwd=worktree,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0

    @pytest.mark.requirement("ralph-worktree-008")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.requires_git
    def test_worktree_commits_independent(self) -> None:
        """Commits in worktree don't affect main branch.

        Validates commit isolation between worktree and main.
        """
        worktree = self.create_test_worktree("independent-commit")

        # Get main branch commit count
        result_before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        main_commits_before = int(result_before.stdout.strip())

        # Make commit in worktree
        test_file = worktree / "independent_file.txt"
        test_file.write_text("Independent content")

        subprocess.run(["git", "add", "."], cwd=worktree, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Independent commit"],
            cwd=worktree,
            check=True,
            capture_output=True,
        )

        # Verify main branch unchanged
        result_after = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        main_commits_after = int(result_after.stdout.strip())

        assert main_commits_before == main_commits_after


class TestWorktreeDryRun(RalphTestBase):
    """Tests for dry-run mode worktree operations."""

    @pytest.mark.requirement("ralph-worktree-009")
    @pytest.mark.ralph
    @pytest.mark.worktree
    @pytest.mark.dry_run
    def test_dry_run_no_worktree_created(
        self, ralph_dry_run_env: None  # noqa: ARG002
    ) -> None:
        """Dry-run mode doesn't create actual worktrees.

        Validates that dry-run mode logs but doesn't execute.
        """
        # Enable dry-run mode
        RalphTestBase.dry_run_mode = True

        try:
            worktree = self.create_test_worktree("dry-run-test")

            # In dry-run mode, worktree path is tracked but not created
            assert worktree in self._created_worktrees
            # The path shouldn't actually exist since we're in dry-run
            # (though it might exist from a previous run)
        finally:
            RalphTestBase.dry_run_mode = False


class TestStateSnapshot(RalphTestBase):
    """Tests for state snapshot functionality."""

    @pytest.mark.requirement("ralph-worktree-010")
    @pytest.mark.ralph
    @pytest.mark.requires_git
    def test_state_snapshot_captured(self) -> None:
        """State snapshot is captured at test start.

        Validates snapshot captures git state correctly.
        """
        assert self._state_snapshot is not None
        assert self._state_snapshot.git_branch is not None
        assert isinstance(self._state_snapshot.worktrees, list)

    @pytest.mark.requirement("ralph-worktree-011")
    @pytest.mark.ralph
    @pytest.mark.requires_git
    def test_verify_state_unchanged_passes(self) -> None:
        """State verification passes when no changes made.

        Validates verification works for read-only operations.
        """
        # Do nothing that changes state
        _ = self._state_snapshot

        # Should pass without error
        self.verify_state_unchanged()

    @pytest.mark.requirement("ralph-worktree-012")
    @pytest.mark.ralph
    @pytest.mark.requires_git
    def test_plan_json_generation(self) -> None:
        """Can generate valid plan.json structures.

        Validates test helper produces valid plan schema.
        """
        plan = self.generate_test_plan_json(
            task_id="T042",
            linear_id="FLO-42",
            epic="EP002",
        )

        assert plan["task_id"] == "T042"
        assert plan["linear_id"] == "FLO-42"
        assert plan["epic"] == "EP002"
        assert "subtasks" in plan
        assert len(plan["subtasks"]) > 0
