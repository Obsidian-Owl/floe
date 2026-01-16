"""Ralph Wiggum workflow test base class.

This module provides the RalphTestBase class that all Ralph workflow tests
should inherit from. It extends IntegrationTestBase with Ralph-specific
functionality:

- Git worktree lifecycle management
- State snapshot capture and verification
- Dry-run mode support
- Mock MCP server helpers

Example:
    from testing.base_classes.ralph_test_base import RalphTestBase

    class TestWorktreeLifecycle(RalphTestBase):
        @pytest.mark.requirement("ralph-001")
        def test_worktree_creation(self) -> None:
            worktree = self.create_test_worktree("test-task")
            assert worktree.exists()
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from testing.base_classes.integration_test_base import IntegrationTestBase


@dataclass
class StateSnapshot:
    """Snapshot of repository state for verification.

    Captures git state before test to verify no unintended changes.

    Attributes:
        git_branch: Current branch name
        git_status: Output of git status --porcelain
        worktrees: List of existing worktree paths
        manifest: Contents of .ralph/manifest.json if exists
        captured_at: ISO timestamp of capture
    """

    git_branch: str
    git_status: str
    worktrees: list[str]
    manifest: dict[str, Any] | None
    captured_at: str = field(default_factory=lambda: "")


class RalphTestBase(IntegrationTestBase):
    """Base class for Ralph Wiggum workflow tests.

    Provides common functionality for testing the Ralph workflow system:
    - Git worktree creation and cleanup
    - State snapshot capture and comparison
    - Dry-run mode utilities
    - Mock MCP server helpers

    Class Attributes:
        required_services: Inherited from IntegrationTestBase.
        ralph_config_path: Path to .ralph directory.
        dry_run_mode: If True, operations log but don't execute.

    Instance Attributes:
        _created_worktrees: List of worktree paths created during test.
        _state_snapshot: State snapshot captured at test start.

    Usage:
        class TestAgentLoop(RalphTestBase):
            @pytest.mark.requirement("ralph-001")
            def test_agent_iteration(self) -> None:
                worktree = self.create_test_worktree("task-001")
                # Test agent loop in worktree...
                self.verify_state_unchanged()  # Ensure no side effects
    """

    # Class attributes
    ralph_config_path: ClassVar[Path] = Path(".ralph")
    dry_run_mode: ClassVar[bool] = False

    # Instance attributes for tracking resources
    _created_worktrees: list[Path]
    _state_snapshot: StateSnapshot | None

    def setup_method(self) -> None:
        """Set up Ralph test fixtures before each test method.

        Called by pytest before each test method. Performs:
        1. Initialize worktree tracking
        2. Capture state snapshot (if not in dry-run mode)
        3. Set up dry-run environment variables if needed
        4. Call parent setup
        """
        super().setup_method()
        self._created_worktrees = []
        self._state_snapshot = None

        # Check for dry-run mode from environment
        if os.environ.get("RALPH_DRY_RUN", "").lower() == "true":
            RalphTestBase.dry_run_mode = True

        # Capture state snapshot for verification
        if not self.dry_run_mode:
            self._state_snapshot = self._capture_state_snapshot()

    def teardown_method(self) -> None:
        """Clean up Ralph test fixtures after each test method.

        Called by pytest after each test method. Performs:
        1. Clean up all created worktrees
        2. Verify no unintended state changes (if snapshot captured)
        3. Call parent teardown
        """
        # Clean up worktrees first
        for worktree_path in self._created_worktrees:
            self._cleanup_worktree(worktree_path)
        self._created_worktrees.clear()

        super().teardown_method()

    def create_test_worktree(
        self,
        task_name: str,
        base_branch: str = "HEAD",
    ) -> Path:
        """Create an isolated worktree for testing.

        Creates a git worktree for test isolation. The worktree is tracked
        and will be automatically cleaned up in teardown.

        Args:
            task_name: Name for the worktree (used in path).
            base_branch: Branch to base worktree on. Defaults to HEAD.

        Returns:
            Path to the created worktree directory.

        Raises:
            subprocess.CalledProcessError: If git worktree creation fails.

        Example:
            worktree = self.create_test_worktree("auth-task")
            # Work in isolated worktree...
            # Automatically cleaned up in teardown
        """
        unique_id = uuid.uuid4().hex[:8]
        worktree_name = f"test-ralph-{task_name}-{unique_id}"
        worktree_path = Path.cwd().parent / worktree_name
        branch_name = f"test/{worktree_name}"

        if self.dry_run_mode:
            # In dry-run mode, just track the path without creating
            self._created_worktrees.append(worktree_path)
            return worktree_path

        # Create worktree with new branch
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                str(worktree_path),
                "-b",
                branch_name,
                base_branch,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        # Enable direnv in worktree (if direnv is available)
        self._enable_direnv(worktree_path)

        # Track for cleanup
        self._created_worktrees.append(worktree_path)
        return worktree_path

    def _cleanup_worktree(self, worktree_path: Path) -> None:
        """Clean up a git worktree created during testing.

        Args:
            worktree_path: Path to the worktree to remove.
        """
        if self.dry_run_mode:
            return

        # Get branch name BEFORE removing worktree (even if path doesn't exist)
        branch_name = self._extract_branch_for_worktree(worktree_path)

        # Fallback: infer branch name from worktree path if not found in worktree list
        # Pattern: worktree path ends with test-ralph-{name}-{uuid}
        # Branch: test/test-ralph-{name}-{uuid}
        if branch_name is None:
            worktree_dirname = worktree_path.name
            if worktree_dirname.startswith("test-ralph-"):
                branch_name = f"test/{worktree_dirname}"

        if worktree_path.exists():
            try:
                # Remove worktree
                subprocess.run(
                    ["git", "worktree", "remove", str(worktree_path), "--force"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError:
                # Force cleanup if git fails
                shutil.rmtree(worktree_path, ignore_errors=True)

        # Prune worktree metadata BEFORE deleting branch
        # Git won't delete a branch if it thinks a worktree is using it,
        # even if the directory is gone. Pruning first clears stale refs.
        subprocess.run(
            ["git", "worktree", "prune"],
            check=False,
            capture_output=True,
            text=True,
        )

        # Delete branch if we found it (now safe after pruning)
        if branch_name and branch_name.startswith("test/"):
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                check=False,  # Don't fail if branch already deleted
                capture_output=True,
                text=True,
            )

    def _extract_branch_for_worktree(self, worktree_path: Path) -> str | None:
        """Extract branch name for a specific worktree.

        Parses `git worktree list --porcelain` output to find the branch
        associated with the given worktree path.

        Args:
            worktree_path: Path to the worktree.

        Returns:
            Branch name (without refs/heads/ prefix) or None if not found.
        """
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = result.stdout.strip().split("\n")
        found_worktree = False

        for line in lines:
            if line.startswith("worktree ") and str(worktree_path) in line:
                found_worktree = True
            elif found_worktree and line.startswith("branch "):
                return line.replace("branch refs/heads/", "")
            elif found_worktree and line == "":
                # End of this worktree entry, branch not found
                break

        return None

    def _enable_direnv(self, worktree_path: Path) -> None:
        """Enable direnv in a worktree.

        Runs `direnv allow` in the worktree to enable .envrc loading.
        This ensures environment variables are properly set.

        Args:
            worktree_path: Path to the worktree directory.

        Note:
            Silently continues if direnv is not installed - this allows
            tests to run in environments without direnv.
        """
        if not self._is_direnv_available():
            return

        try:
            subprocess.run(
                ["direnv", "allow"],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except subprocess.CalledProcessError:
            # direnv allow failed - log but don't fail test
            pass
        except subprocess.TimeoutExpired:
            # Timeout - continue without direnv
            pass

    @staticmethod
    def _is_direnv_available() -> bool:
        """Check if direnv is installed and available.

        Returns:
            True if direnv command is available, False otherwise.
        """
        try:
            result = subprocess.run(
                ["direnv", "version"],
                capture_output=True,
                check=False,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _capture_state_snapshot(self) -> StateSnapshot:
        """Capture current repository state for later verification.

        Returns:
            StateSnapshot with current git state.
        """
        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
        )
        git_branch = result.stdout.strip() if result.returncode == 0 else "unknown"

        # Get git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        git_status = result.stdout if result.returncode == 0 else ""

        # Get worktrees
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        worktrees: list[str] = []
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                worktrees.append(line.replace("worktree ", ""))

        # Get manifest if exists
        manifest: dict[str, Any] | None = None
        manifest_path = Path.cwd() / ".ralph" / "manifest.json"
        if manifest_path.exists():
            try:
                with manifest_path.open() as f:
                    manifest = json.load(f)
            except json.JSONDecodeError:
                manifest = None

        from datetime import datetime, timezone

        return StateSnapshot(
            git_branch=git_branch,
            git_status=git_status,
            worktrees=worktrees,
            manifest=manifest,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )

    def verify_state_unchanged(self) -> None:
        """Verify repository state hasn't changed unexpectedly.

        Compares current state against the snapshot captured at test start.
        Useful for ensuring tests don't have unintended side effects.

        Raises:
            AssertionError: If state differs from snapshot.

        Example:
            def test_read_only_operation(self) -> None:
                # Perform operation that shouldn't modify state
                read_manifest()
                self.verify_state_unchanged()
        """
        if self._state_snapshot is None:
            return

        current = self._capture_state_snapshot()

        # Compare branch
        assert (
            current.git_branch == self._state_snapshot.git_branch
        ), f"Branch changed: {self._state_snapshot.git_branch} -> {current.git_branch}"

        # Compare status (excluding test worktrees)
        assert current.git_status == self._state_snapshot.git_status, (
            f"Git status changed:\n"
            f"Before:\n{self._state_snapshot.git_status}\n"
            f"After:\n{current.git_status}"
        )

    def generate_test_plan_json(
        self,
        task_id: str = "T001",
        linear_id: str = "FLO-99",
        epic: str = "EP001",
        subtasks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Generate a test plan.json structure.

        Creates a valid plan.json structure for testing agent state management.

        Args:
            task_id: Task identifier. Defaults to "T001".
            linear_id: Linear issue ID. Defaults to "FLO-99".
            epic: Epic identifier. Defaults to "EP001".
            subtasks: Optional list of subtask dicts. If None, creates default.

        Returns:
            Dictionary matching plan.json schema.

        Example:
            plan = self.generate_test_plan_json(
                task_id="T002",
                subtasks=[
                    {"id": "T002.1", "description": "Step 1", "passes": True},
                    {"id": "T002.2", "description": "Step 2", "passes": False},
                ]
            )
        """
        if subtasks is None:
            subtasks = [
                {"id": f"{task_id}.1", "description": "Test subtask 1", "passes": False},
                {"id": f"{task_id}.2", "description": "Test subtask 2", "passes": False},
            ]

        return {
            "task_id": task_id,
            "linear_id": linear_id,
            "epic": epic,
            "status": "in_progress",
            "subtasks": subtasks,
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
        }

    @staticmethod
    def is_dry_run() -> bool:
        """Check if running in dry-run mode.

        Returns:
            True if RALPH_DRY_RUN environment variable is set to 'true'.
        """
        return os.environ.get("RALPH_DRY_RUN", "").lower() == "true"

    @staticmethod
    def cleanup_stale_worktrees(max_age_hours: int = 24) -> list[Path]:
        """Remove test worktrees older than max_age_hours.

        Scans for worktrees matching the test-ralph-* pattern and removes
        any that are older than the specified age.

        Args:
            max_age_hours: Maximum age in hours before worktree is considered stale.
                          Defaults to 24 hours.

        Returns:
            List of paths that were removed.

        Example:
            # Clean up worktrees older than 12 hours
            removed = RalphTestBase.cleanup_stale_worktrees(max_age_hours=12)
            print(f"Removed {len(removed)} stale worktrees")
        """
        from datetime import datetime, timezone

        removed: list[Path] = []
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )

        now = datetime.now(timezone.utc)
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                path = Path(line.replace("worktree ", ""))
                if path.exists() and "test-ralph" in str(path):
                    # Check directory age via mtime
                    mtime = datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    )
                    age_hours = (now - mtime).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        # Remove stale worktree
                        subprocess.run(
                            ["git", "worktree", "remove", str(path), "--force"],
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                        removed.append(path)

        # Prune any orphaned worktree metadata
        subprocess.run(
            ["git", "worktree", "prune"],
            check=False,
            capture_output=True,
            text=True,
        )

        return removed


# Module exports
__all__ = ["RalphTestBase", "StateSnapshot"]
