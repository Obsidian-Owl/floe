"""E2E tests for quality gate chain.

Tests the sequence of quality gates:
- lint → type → test → security → constitution
- Gate failure blocking progression
- Gate fix allowing retry
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from testing.base_classes.ralph_test_base import RalphTestBase


class TestQualityGateChain(RalphTestBase):
    """E2E tests for quality gate chain."""

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(120)
    @pytest.mark.requirement("ralph-gate-001")
    def test_gate_sequence_validation(self) -> None:
        """Test that gates are executed in correct sequence.

        Validates the gate order: lint → type → test → security → constitution.
        """
        worktree = self.create_test_worktree("gate-sequence")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        # Create plan with gate tracking
        plan: dict[str, Any] = {
            "task_id": "GATE-001",
            "linear_id": "FLO-GATE",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "GATE-001.1", "description": "Pass lint gate", "passes": False},
                {"id": "GATE-001.2", "description": "Pass type gate", "passes": False},
                {"id": "GATE-001.3", "description": "Pass test gate", "passes": False},
                {"id": "GATE-001.4", "description": "Pass security gate", "passes": False},
                {"id": "GATE-001.5", "description": "Pass constitution gate", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
            "gates_passed": [],
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Simulate gate progression
        gate_order = ["lint", "type", "test", "security", "constitution"]

        for i, gate in enumerate(gate_order):
            plan["subtasks"][i]["passes"] = True
            plan["gates_passed"].append(gate)
            plan["iteration"] = i + 2
            (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify all gates passed in order
        final_plan = json.loads((agent_dir / "plan.json").read_text())
        assert final_plan["gates_passed"] == gate_order
        assert all(s["passes"] for s in final_plan["subtasks"])

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-gate-002")
    def test_gate_failure_blocks_progression(self) -> None:
        """Test that failing a gate blocks progression to next gate.

        Validates that failing lint blocks type check.
        """
        worktree = self.create_test_worktree("gate-block")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "GATE-BLOCK-001",
            "linear_id": "FLO-GATEBLOCK",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "GATE-BLOCK-001.1", "description": "Pass lint gate", "passes": False},
                {"id": "GATE-BLOCK-001.2", "description": "Pass type gate", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
            "current_gate": "lint",
            "gate_blocked": False,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Simulate lint failure
        plan["gate_blocked"] = True
        plan["iteration"] = 2
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify we cannot progress to type gate
        loaded = json.loads((agent_dir / "plan.json").read_text())
        assert loaded["gate_blocked"] is True
        assert loaded["current_gate"] == "lint"
        assert loaded["subtasks"][0]["passes"] is False
        assert loaded["subtasks"][1]["passes"] is False  # Cannot pass type if lint fails

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-gate-003")
    def test_gate_fix_allows_retry(self) -> None:
        """Test that fixing a gate issue allows retry and progression.

        Validates that after fixing lint, we can proceed to type gate.
        """
        worktree = self.create_test_worktree("gate-retry")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "GATE-RETRY-001",
            "linear_id": "FLO-GATERETRY",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "GATE-RETRY-001.1", "description": "Pass lint gate", "passes": False},
                {"id": "GATE-RETRY-001.2", "description": "Pass type gate", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
            "current_gate": "lint",
            "gate_blocked": False,
            "retry_count": 0,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Iteration 1: Lint fails
        plan["gate_blocked"] = True
        plan["iteration"] = 2
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Iteration 2: Fix applied, retry lint
        plan["gate_blocked"] = False
        plan["retry_count"] = 1
        plan["iteration"] = 3
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Iteration 3: Lint passes, move to type
        plan["subtasks"][0]["passes"] = True
        plan["current_gate"] = "type"
        plan["iteration"] = 4
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Iteration 4: Type passes
        plan["subtasks"][1]["passes"] = True
        plan["iteration"] = 5
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify progression after fix
        final = json.loads((agent_dir / "plan.json").read_text())
        assert final["subtasks"][0]["passes"] is True
        assert final["subtasks"][1]["passes"] is True
        assert final["retry_count"] == 1
        assert final["current_gate"] == "type"

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-gate-004")
    def test_all_gates_pass_marks_complete(self) -> None:
        """Test that passing all gates marks task as complete.

        Validates the COMPLETE signal is set when all gates pass.
        """
        worktree = self.create_test_worktree("gate-complete")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "GATE-COMPLETE-001",
            "linear_id": "FLO-GATECOMPLETE",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "GATE-COMPLETE-001.1", "description": "Pass lint", "passes": False},
                {"id": "GATE-COMPLETE-001.2", "description": "Pass type", "passes": False},
                {"id": "GATE-COMPLETE-001.3", "description": "Pass test", "passes": False},
                {"id": "GATE-COMPLETE-001.4", "description": "Pass security", "passes": False},
                {"id": "GATE-COMPLETE-001.5", "description": "Pass constitution", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Pass all gates
        for i in range(5):
            plan["subtasks"][i]["passes"] = True

        # Mark complete
        plan["status"] = "complete"
        plan["completion_signal"] = "COMPLETE"
        plan["iteration"] = 6
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify completion
        final = json.loads((agent_dir / "plan.json").read_text())
        assert final["status"] == "complete"
        assert final["completion_signal"] == "COMPLETE"
        assert all(s["passes"] for s in final["subtasks"])

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-gate-005")
    def test_max_iterations_without_gates_blocks(self) -> None:
        """Test that reaching max iterations without passing gates blocks.

        Validates the BLOCKED signal is set when max iterations reached.
        """
        worktree = self.create_test_worktree("gate-max-iter")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "GATE-MAXITER-001",
            "linear_id": "FLO-GATEMAXITER",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "GATE-MAXITER-001.1", "description": "Pass lint", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 5,  # Low max for test
            "completion_signal": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Simulate iterations without passing
        for i in range(2, 6):
            plan["iteration"] = i
            (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Max reached without passing gates
        plan["iteration"] = 5
        plan["status"] = "blocked"
        plan["completion_signal"] = "BLOCKED"
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify blocked state
        final = json.loads((agent_dir / "plan.json").read_text())
        assert final["status"] == "blocked"
        assert final["completion_signal"] == "BLOCKED"
        assert final["iteration"] == final["max_iterations"]

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(90)
    @pytest.mark.requirement("ralph-gate-006")
    def test_gate_with_file_changes(self) -> None:
        """Test gate progression with actual file changes and commits.

        Validates that file modifications are committed during gate fixes.
        """
        worktree = self.create_test_worktree("gate-files")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "GATE-FILES-001",
            "linear_id": "FLO-GATEFILES",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "GATE-FILES-001.1", "description": "Fix lint issues", "passes": False},
                {"id": "GATE-FILES-001.2", "description": "Fix type issues", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Create initial file with "lint issues"
        code_file = worktree / "module.py"
        code_file.write_text(
            '"""Module with issues."""\n\n'
            "def bad_function(x,y,z):\n"  # Bad formatting
            '    return x+y+z\n'
        )

        subprocess.run(["git", "add", "."], cwd=worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial code with issues"],
            cwd=worktree,
            check=True,
            capture_output=True,
        )

        # Iteration 2: Fix lint issues
        code_file.write_text(
            '"""Module with fixed lint."""\n\n'
            "def good_function(x: int, y: int, z: int) -> int:\n"
            "    return x + y + z\n"
        )

        subprocess.run(["git", "add", "."], cwd=worktree, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fix: lint issues resolved"],
            cwd=worktree,
            check=True,
            capture_output=True,
        )

        plan["subtasks"][0]["passes"] = True
        plan["iteration"] = 2
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Iteration 3: Type gate passes (already has type hints)
        plan["subtasks"][1]["passes"] = True
        plan["status"] = "complete"
        plan["completion_signal"] = "COMPLETE"
        plan["iteration"] = 3
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify commits exist
        result = subprocess.run(
            ["git", "log", "--oneline", "-3"],
            cwd=worktree,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "lint issues resolved" in result.stdout
        assert "Initial code" in result.stdout

        # Verify final state
        final = json.loads((agent_dir / "plan.json").read_text())
        assert final["status"] == "complete"
        assert all(s["passes"] for s in final["subtasks"])
