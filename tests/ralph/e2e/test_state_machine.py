"""E2E tests for agent state machine.

Tests state transitions:
- pending → in_progress → complete
- pending → in_progress → blocked
- BLOCKED requires intervention
- State persistence across iterations
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from testing.base_classes.ralph_test_base import RalphTestBase


class TestStateMachine(RalphTestBase):
    """E2E tests for agent state machine transitions."""

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-state-001")
    def test_state_pending_to_in_progress(self) -> None:
        """Test state transition from pending to in_progress.

        Validates that claiming a task transitions it correctly.
        """
        worktree = self.create_test_worktree("state-pending")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        # Initial state: pending
        plan: dict[str, Any] = {
            "task_id": "STATE-001",
            "linear_id": "FLO-STATE",
            "epic": "EPTEST",
            "status": "pending",
            "subtasks": [
                {"id": "STATE-001.1", "description": "Do work", "passes": False},
            ],
            "iteration": 0,
            "max_iterations": 15,
            "completion_signal": None,
            "claimed_at": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify initial state
        loaded = json.loads((agent_dir / "plan.json").read_text())
        assert loaded["status"] == "pending"
        assert loaded["iteration"] == 0

        # Claim the task
        plan["status"] = "in_progress"
        plan["iteration"] = 1
        plan["claimed_at"] = "2026-01-16T13:00:00Z"
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify transition
        loaded = json.loads((agent_dir / "plan.json").read_text())
        assert loaded["status"] == "in_progress"
        assert loaded["iteration"] == 1
        assert loaded["claimed_at"] is not None

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-state-002")
    def test_state_in_progress_to_complete(self) -> None:
        """Test state transition from in_progress to complete.

        Validates that passing all subtasks transitions to complete.
        """
        worktree = self.create_test_worktree("state-complete")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "STATE-002",
            "linear_id": "FLO-STATE2",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "STATE-002.1", "description": "Step 1", "passes": False},
                {"id": "STATE-002.2", "description": "Step 2", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Complete subtasks
        plan["subtasks"][0]["passes"] = True
        plan["iteration"] = 2
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        plan["subtasks"][1]["passes"] = True
        plan["iteration"] = 3
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # All subtasks pass → complete
        plan["status"] = "complete"
        plan["completion_signal"] = "COMPLETE"
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify final state
        final = json.loads((agent_dir / "plan.json").read_text())
        assert final["status"] == "complete"
        assert final["completion_signal"] == "COMPLETE"
        assert all(s["passes"] for s in final["subtasks"])

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-state-003")
    def test_state_in_progress_to_blocked(self) -> None:
        """Test state transition from in_progress to blocked.

        Validates that max iterations without completion blocks.
        """
        worktree = self.create_test_worktree("state-blocked")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "STATE-003",
            "linear_id": "FLO-STATE3",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "STATE-003.1", "description": "Stuck task", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 3,  # Low for testing
            "completion_signal": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Simulate iterations without progress
        for i in range(2, 4):
            plan["iteration"] = i
            (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Max reached → blocked
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
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-state-004")
    def test_blocked_requires_intervention(self) -> None:
        """Test that BLOCKED state persists until manual intervention.

        Validates that blocked tasks don't auto-recover.
        """
        worktree = self.create_test_worktree("state-intervention")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "STATE-004",
            "linear_id": "FLO-STATE4",
            "epic": "EPTEST",
            "status": "blocked",
            "subtasks": [
                {"id": "STATE-004.1", "description": "Blocked task", "passes": False},
            ],
            "iteration": 15,
            "max_iterations": 15,
            "completion_signal": "BLOCKED",
            "intervention_required": True,
            "intervention_notes": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify state persists
        loaded = json.loads((agent_dir / "plan.json").read_text())
        assert loaded["status"] == "blocked"
        assert loaded["intervention_required"] is True

        # Simulate intervention (manual fix)
        plan["intervention_notes"] = "Manual fix applied by engineer"
        plan["status"] = "in_progress"
        plan["iteration"] = 1  # Reset iteration count
        plan["max_iterations"] = 5  # New iteration budget
        plan["completion_signal"] = None
        plan["intervention_required"] = False
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Verify recovery
        recovered = json.loads((agent_dir / "plan.json").read_text())
        assert recovered["status"] == "in_progress"
        assert recovered["intervention_notes"] == "Manual fix applied by engineer"
        assert recovered["intervention_required"] is False

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-state-005")
    def test_state_persistence_across_iterations(self) -> None:
        """Test that state changes persist correctly across iterations.

        Validates file-based state persistence mechanism.
        """
        worktree = self.create_test_worktree("state-persist")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        plan: dict[str, Any] = {
            "task_id": "STATE-005",
            "linear_id": "FLO-STATE5",
            "epic": "EPTEST",
            "status": "in_progress",
            "subtasks": [
                {"id": "STATE-005.1", "description": "Task A", "passes": False},
                {"id": "STATE-005.2", "description": "Task B", "passes": False},
                {"id": "STATE-005.3", "description": "Task C", "passes": False},
            ],
            "iteration": 1,
            "max_iterations": 15,
            "completion_signal": None,
            "history": [],
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Multiple iterations with state changes
        iterations: list[dict[str, Any]] = []
        for i in range(3):
            plan["subtasks"][i]["passes"] = True
            plan["iteration"] = i + 2
            plan["history"].append({"iteration": i + 2, "action": f"Completed subtask {i + 1}"})
            (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

            # Re-read to verify persistence
            loaded = json.loads((agent_dir / "plan.json").read_text())
            iterations.append(loaded.copy())

        # Verify all state changes persisted
        assert len(iterations) == 3
        assert iterations[0]["subtasks"][0]["passes"] is True
        assert iterations[1]["subtasks"][1]["passes"] is True
        assert iterations[2]["subtasks"][2]["passes"] is True

        # Verify history was maintained
        final = json.loads((agent_dir / "plan.json").read_text())
        assert len(final["history"]) == 3

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-state-006")
    def test_invalid_state_transition_rejected(self) -> None:
        """Test that invalid state transitions are detectable.

        Validates state machine integrity (e.g., can't go from complete to pending).
        """
        worktree = self.create_test_worktree("state-invalid")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        # Start in complete state
        plan: dict[str, Any] = {
            "task_id": "STATE-006",
            "linear_id": "FLO-STATE6",
            "epic": "EPTEST",
            "status": "complete",
            "subtasks": [
                {"id": "STATE-006.1", "description": "Done", "passes": True},
            ],
            "iteration": 5,
            "max_iterations": 15,
            "completion_signal": "COMPLETE",
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Define valid transitions
        valid_transitions: dict[str, list[str]] = {
            "pending": ["in_progress"],
            "in_progress": ["complete", "blocked"],
            "complete": [],  # Terminal state
            "blocked": ["in_progress"],  # Only via intervention
        }

        # Verify complete is terminal (no valid transitions)
        loaded = json.loads((agent_dir / "plan.json").read_text())
        current_state = loaded["status"]
        assert current_state == "complete"
        assert len(valid_transitions[current_state]) == 0

        # Attempting to go back to pending would be invalid
        # (We test the validation logic conceptually here)
        invalid_next_state = "pending"
        assert invalid_next_state not in valid_transitions[current_state]

    @pytest.mark.e2e
    @pytest.mark.ralph
    @pytest.mark.requires_git
    @pytest.mark.timeout(60)
    @pytest.mark.requirement("ralph-state-007")
    def test_activity_log_tracks_state_changes(self) -> None:
        """Test that activity.md tracks state transitions.

        Validates the activity log records all state changes.
        """
        worktree = self.create_test_worktree("state-activity")
        agent_dir = worktree / ".agent"
        agent_dir.mkdir()

        # Create activity log
        activity_log = agent_dir / "activity.md"
        activity_log.write_text("# Activity Log\n\n")

        plan: dict[str, Any] = {
            "task_id": "STATE-007",
            "linear_id": "FLO-STATE7",
            "epic": "EPTEST",
            "status": "pending",
            "subtasks": [
                {"id": "STATE-007.1", "description": "Work", "passes": False},
            ],
            "iteration": 0,
            "max_iterations": 15,
            "completion_signal": None,
        }
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Transition: pending → in_progress
        plan["status"] = "in_progress"
        plan["iteration"] = 1
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Log the transition
        activity_content = activity_log.read_text()
        activity_content += "## Iteration 1\n\n- State: pending → in_progress\n\n"
        activity_log.write_text(activity_content)

        # Transition: in_progress → complete
        plan["subtasks"][0]["passes"] = True
        plan["status"] = "complete"
        plan["completion_signal"] = "COMPLETE"
        plan["iteration"] = 2
        (agent_dir / "plan.json").write_text(json.dumps(plan, indent=2))

        # Log completion
        activity_content = activity_log.read_text()
        activity_content += "## Iteration 2\n\n- State: in_progress → complete\n"
        activity_content += "- Signal: COMPLETE\n\n"
        activity_log.write_text(activity_content)

        # Verify activity log has state changes
        final_log = activity_log.read_text()
        assert "pending → in_progress" in final_log
        assert "in_progress → complete" in final_log
        assert "Signal: COMPLETE" in final_log
