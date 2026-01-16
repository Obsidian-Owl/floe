"""E2E tests for cleanup robustness.

Tests edge cases and failure recovery for the cleanup system:
- Idempotent cleanup (running twice doesn't error)
- Missing worktree handling
- Orphaned branch cleanup
- Stale worktree detection
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from testing.base_classes.ralph_test_base import RalphTestBase


class TestCleanupRobustness(RalphTestBase):
    """E2E tests for cleanup robustness."""

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-cleanup-001")
    def test_cleanup_idempotent(self) -> None:
        """Test that running cleanup twice doesn't error.

        Validates idempotent cleanup behavior.
        """
        worktree = self.create_test_worktree("idempotent-test")
        worktree_path = worktree  # Save path before cleanup

        # First cleanup (via teardown simulation)
        self._cleanup_worktree(worktree_path)

        # Second cleanup should not error
        self._cleanup_worktree(worktree_path)

        # Worktree should not exist
        assert not worktree_path.exists()

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-cleanup-002")
    def test_cleanup_missing_worktree(self) -> None:
        """Test cleanup handles already-deleted worktree gracefully.

        Validates that cleanup works even if worktree directory was
        manually deleted.
        """
        worktree = self.create_test_worktree("missing-test")
        worktree_path = worktree

        # Get branch name before deleting
        branch_name = self._extract_branch_for_worktree(worktree_path)
        assert branch_name is not None, "Should have found branch"

        # Manually delete the worktree directory (simulating external deletion)
        shutil.rmtree(worktree_path, ignore_errors=True)
        assert not worktree_path.exists()

        # Cleanup should still work (remove branch, prune metadata)
        self._cleanup_worktree(worktree_path)

        # Branch should be deleted
        result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )
        assert branch_name not in result.stdout, f"Branch {branch_name} should be deleted"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-cleanup-003")
    def test_cleanup_orphaned_branch(self) -> None:
        """Test cleanup removes orphaned branches.

        Validates that branches are cleaned up even when worktree
        removal fails or worktree is already gone.
        """
        worktree = self.create_test_worktree("orphan-test")
        branch_name = self._extract_branch_for_worktree(worktree)

        assert branch_name is not None
        assert branch_name.startswith("test/")

        # Force remove worktree without using our cleanup (simulating crash)
        subprocess.run(
            ["git", "worktree", "remove", str(worktree), "--force"],
            check=False,
            capture_output=True,
        )

        # Branch should still exist at this point
        result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )
        # Note: git worktree remove with --force may or may not delete the branch

        # Now cleanup should handle the orphaned state
        self._cleanup_worktree(worktree)

        # After cleanup, branch should be gone
        result = subprocess.run(
            ["git", "branch", "--list", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )
        assert branch_name not in result.stdout

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-cleanup-004")
    def test_extract_branch_for_worktree(self) -> None:
        """Test branch extraction works correctly.

        Validates the fixed branch extraction logic.
        """
        worktree = self.create_test_worktree("extract-test")

        # Extract branch name
        branch_name = self._extract_branch_for_worktree(worktree)

        assert branch_name is not None, "Should find branch for worktree"
        assert branch_name.startswith("test/"), f"Expected test/ prefix: {branch_name}"
        assert "extract-test" in branch_name, f"Should contain task name: {branch_name}"

        # Verify it matches what git reports in the worktree
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        actual_branch = result.stdout.strip()
        assert branch_name == actual_branch, f"Extracted {branch_name} != actual {actual_branch}"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-cleanup-005")
    def test_cleanup_preserves_non_test_branches(self) -> None:
        """Test that cleanup only removes test/* branches.

        Validates that cleanup doesn't accidentally remove real branches.
        """
        # Create a test worktree
        worktree = self.create_test_worktree("preserve-test")

        # Get current main branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        main_branch = result.stdout.strip()

        # Cleanup the test worktree
        self._cleanup_worktree(worktree)

        # Main branch should still exist
        result = subprocess.run(
            ["git", "branch", "--list", main_branch],
            capture_output=True,
            text=True,
            check=False,
        )
        assert main_branch in result.stdout, f"Main branch {main_branch} should be preserved"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-cleanup-006")
    def test_stale_worktree_detection(self) -> None:
        """Test stale worktree detection by age.

        Validates the cleanup_stale_worktrees functionality.
        Note: This test uses max_age_hours=0 to treat any worktree as stale.
        """
        # Create a worktree
        worktree = self.create_test_worktree("stale-test")
        assert worktree.exists()

        # Remove from tracked list so teardown doesn't clean it
        self._created_worktrees.remove(worktree)

        # Call stale cleanup with 0 hours (everything is stale)
        removed = self.cleanup_stale_worktrees(max_age_hours=0)

        # Our worktree should have been removed
        assert worktree in removed or not worktree.exists(), "Stale worktree should be removed"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.requirement("ralph-cleanup-007")
    def test_git_prune_runs(self) -> None:
        """Test that git worktree prune runs during cleanup.

        Validates that orphaned worktree metadata is cleaned up.
        """
        worktree = self.create_test_worktree("prune-test")

        # Cleanup should run prune
        self._cleanup_worktree(worktree)

        # After cleanup, git worktree list should be clean
        result = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Should not contain our worktree
        assert str(worktree) not in result.stdout
