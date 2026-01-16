"""E2E tests for full Ralph workflow cycle.

Tests complete workflows:
- spawn → simulate work → integrate → cleanup
- Parallel task execution
- Dependency-based wave execution
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from testing.base_classes.ralph_test_base import RalphTestBase


class TestFullWorkflow(RalphTestBase):
    """E2E tests for complete workflow cycles."""

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(120)
    @pytest.mark.requirement("ralph-workflow-001")
    def test_full_cycle_single_task(self) -> None:
        """Test complete workflow: spawn → work → verify → cleanup.

        This test exercises the full lifecycle of a single agent task.
        """
        # 1. SPAWN: Create worktree
        worktree = self.create_test_worktree("full-cycle")
        assert worktree.exists()

        # 2. INITIALIZE: Create .agent state directory
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan = self.generate_test_plan_json(task_id="FULL-001")
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))
        (agent_dir / "activity.md").write_text("# Activity Log\n\n- Started\n")

        # 3. SIMULATE AGENT WORK: Create a file and commit
        test_file = worktree / "agent_output.py"
        test_file.write_text(
            '"""Agent-generated module."""\n\ndef hello() -> str:\n    return "Hello from agent"\n'
        )

        subprocess.run(["git", "add", "."], cwd=worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: agent implementation"],
            cwd=worktree,
            check=True,
            capture_output=True,
        )

        # 4. UPDATE STATE: Mark subtasks complete
        plan["subtasks"][0]["passes"] = True
        plan["subtasks"][1]["passes"] = True
        plan["status"] = "complete"
        plan["completion_signal"] = "COMPLETE"
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # 5. VERIFY: Check worktree has the commit
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "agent implementation" in result.stdout

        # 6. Verify plan.json shows complete
        final_plan = json.loads((agent_dir / "plan.json").read_text())
        assert final_plan["status"] == "complete"
        assert final_plan["completion_signal"] == "COMPLETE"

        # Cleanup happens automatically in teardown

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(180)
    @pytest.mark.requirement("ralph-workflow-002")
    def test_full_cycle_parallel_tasks(self) -> None:
        """Test parallel execution of non-overlapping tasks.

        Simulates Wave 1 with 3 independent tasks working in parallel.
        """
        # 1. SPAWN: Create 3 worktrees (Wave 1)
        worktree1 = self.create_test_worktree("parallel-auth")
        worktree2 = self.create_test_worktree("parallel-catalog")
        worktree3 = self.create_test_worktree("parallel-compute")

        worktrees = [worktree1, worktree2, worktree3]
        task_names = ["auth", "catalog", "compute"]

        # 2. INITIALIZE: Set up each worktree
        for wt, name in zip(worktrees, task_names, strict=True):
            agent_dir = wt / ".agent"
            agent_dir.mkdir()

            plan = self.generate_test_plan_json(task_id=f"PAR-{name.upper()}")
            (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # 3. SIMULATE PARALLEL WORK: Each creates different files
        for wt, name in zip(worktrees, task_names, strict=True):
            # Each agent creates a file in its domain
            module_file = wt / f"{name}_module.py"
            module_file.write_text(
                f'"""Module for {name}."""\n\n'
                f"def {name}_function() -> str:\n"
                f'    return "{name} works"\n'
            )

            subprocess.run(["git", "add", "."], cwd=wt, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"feat({name}): implementation"],
                cwd=wt,
                check=True,
                capture_output=True,
            )

            # Update plan to complete
            agent_dir = wt / ".agent"
            plan = json.loads((agent_dir / "plan.json").read_text())
            plan["status"] = "complete"
            plan["completion_signal"] = "COMPLETE"
            (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # 4. VERIFY: All worktrees have independent commits
        for wt, name in zip(worktrees, task_names, strict=True):
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                cwd=wt,
                capture_output=True,
                text=True,
                check=True,
            )
            assert name in result.stdout, f"Worktree {wt} should have {name} commit"

        # 5. VERIFY: Changes don't appear in other worktrees
        # Each worktree should only have its own module file
        for wt, name in zip(worktrees, task_names, strict=True):
            own_file = wt / f"{name}_module.py"
            assert own_file.exists(), f"{own_file} should exist"

            # Other module files should NOT exist
            for other_name in task_names:
                if other_name != name:
                    other_file = wt / f"{other_name}_module.py"
                    assert not other_file.exists(), f"{other_file} should NOT exist in {wt}"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-workflow-003")
    def test_worktree_commit_history_isolated(self) -> None:
        """Test that worktree commits don't affect main repo.

        Validates complete isolation between worktree and main.
        """
        # Capture main repo HEAD before
        main_head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Create worktree and make commits
        worktree = self.create_test_worktree("commit-isolation")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        # Make multiple commits in worktree
        for i in range(3):
            test_file = worktree / f"commit_{i}.txt"
            test_file.write_text(f"Commit {i} content\n")
            subprocess.run(["git", "add", "."], cwd=worktree, check=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=worktree,
                check=True,
                capture_output=True,
            )

        # Verify worktree has the commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Commit 0" in result.stdout
        assert "Commit 2" in result.stdout

        # Verify main repo HEAD unchanged
        main_head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert main_head_before == main_head_after, "Main repo HEAD should not change"

        # Verify files don't exist in main repo
        for i in range(3):
            main_file = Path.cwd() / f"commit_{i}.txt"
            assert not main_file.exists(), f"File should not exist in main: {main_file}"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-workflow-004")
    def test_workflow_with_subtask_progression(self) -> None:
        """Test agent progressing through subtasks.

        Validates the subtask state machine: false → true progression.
        """
        worktree = self.create_test_worktree("subtask-progress")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        # Initial plan with 3 subtasks
        plan: dict[str, Any] = {
            "task_id": "SUBTASK-001",
            "linear_id": "FLO-SUBTASK",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "SUBTASK-001.1", "description": "Step 1", "passes": False},
                {"id": "SUBTASK-001.2", "description": "Step 2", "passes": False},
                {"id": "SUBTASK-001.3", "description": "Step 3", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Simulate iteration 1: complete subtask 1
        plan["subtasks"][0]["passes"] = True
        plan["iteration"] = 2
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify state
        loaded = json.loads((agent_dir / "plan.json").read_text())
        assert loaded["subtasks"][0]["passes"] is True
        assert loaded["subtasks"][1]["passes"] is False
        assert loaded["iteration"] == 2

        # Simulate iteration 2: complete subtask 2
        plan["subtasks"][1]["passes"] = True
        plan["iteration"] = 3
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Simulate iteration 3: complete subtask 3 and mark complete
        plan["subtasks"][2]["passes"] = True
        plan["iteration"] = 4
        plan["status"] = "complete"
        plan["completion_signal"] = "COMPLETE"
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Final verification
        final = json.loads((agent_dir / "plan.json").read_text())
        assert all(s["passes"] for s in final["subtasks"]), "All subtasks should pass"
        assert final["status"] == "complete"
        assert final["completion_signal"] == "COMPLETE"
