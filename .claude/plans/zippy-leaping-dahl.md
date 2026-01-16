# Ralph Wiggum Workflow Testing Strategy

## Executive Summary

This plan defines a comprehensive testing strategy for the Ralph Wiggum agentic workflow system. The core insight is that **testing agentic systems requires testing behavior and invariants, not exact outputs**.

**Key Principles:**
1. Quality gates are deterministic termination conditions (testable)
2. LLM outputs are non-deterministic (don't test exact text)
3. External state changes are observable (test state transitions)
4. Isolation via temporary repos + mocks + namespaces

---

## Problem Statement

### Challenges of Testing Agentic Systems

| Challenge | Why It's Hard | Our Solution |
|-----------|---------------|--------------|
| **Non-deterministic outputs** | Same prompt → different code | Test behavior (gates pass), not exact output |
| **External state coupling** | Linear/git/Cognee state changes | Isolation via worktrees + mocks + tmp repos |
| **Iteration loops** | Agent iterates 1-15 times unpredictably | Quality gates = deterministic termination |
| **Parallel execution** | Multiple agents may deadlock | Dependency graph testing + wave execution |
| **Recovery complexity** | Session interruption → context loss | Checkpoint/restore cycle testing |

### What We Can Test Deterministically

| Component | Deterministic? | Why |
|-----------|----------------|-----|
| Quality gates (lint/type/test) | ✅ Yes | Same code → same exit code |
| State transitions | ✅ Yes | Agent moves through known states |
| External API calls | ✅ Yes | Can mock and verify calls made |
| Termination conditions | ✅ Yes | Max iterations OR gates pass |
| File modifications | ✅ Yes | Observable filesystem changes |
| LLM output text | ❌ No | Varies with temperature/context |

---

## Testing Architecture

### Test Pyramid for Ralph Wiggum

```
                    ┌─────────────────┐
                    │      E2E        │  ← Full epic workflow
                    │   (5-10 min)    │     Parallel agents
                    └────────┬────────┘     Recovery scenarios
                             │
                    ┌────────┴────────┐
                    │   Contract      │  ← Agent ↔ Linear consistency
                    │   (< 30 sec)    │     Plan.json schema stability
                    └────────┬────────┘     Memory buffer contracts
                             │
              ┌──────────────┴──────────────┐
              │        Integration          │  ← Git worktree lifecycle
              │        (< 2 min)            │     Real services (mocked Linear)
              └──────────────┬──────────────┘     Preflight checks
                             │
    ┌────────────────────────┴────────────────────────┐
    │                    Unit                         │  ← Quality gate determinism
    │                  (< 30 sec)                     │     State machine transitions
    └─────────────────────────────────────────────────┘     Config validation
```

### Test Directory Structure

```
tests/
├── ralph/                              # All Ralph-specific tests
│   ├── conftest.py                    # Ralph fixtures, base classes
│   ├── unit/
│   │   ├── test_quality_gates.py      # Gate determinism
│   │   ├── test_state_machine.py      # Agent state transitions
│   │   ├── test_config_validation.py  # Config parsing
│   │   └── test_preflight.py          # Preflight script logic
│   ├── integration/
│   │   ├── test_worktree_lifecycle.py # Git worktree create/cleanup
│   │   ├── test_memory_buffer.py      # WAL buffer persistence
│   │   └── test_preflight_real.py     # Real service checks
│   ├── contract/
│   │   ├── test_plan_schema.py        # plan.json stability
│   │   ├── test_manifest_schema.py    # manifest.json stability
│   │   └── test_linear_contract.py    # Agent ↔ Linear state
│   └── e2e/
│       ├── test_full_epic_dry_run.py  # Complete workflow (dry-run)
│       ├── test_parallel_agents.py    # Wave execution
│       └── test_recovery.py           # Checkpoint/resume
```

---

## Implementation Plan

### Phase 1: Test Infrastructure (Foundation)

#### 1.1 Create RalphTestBase Class

**File:** `testing/base_classes/ralph_test_base.py`

```python
from testing.base_classes.integration_test_base import IntegrationTestBase

class RalphTestBase(IntegrationTestBase):
    """Base class for Ralph Wiggum workflow tests."""

    # No external services required by default (use mocks)
    required_services: list[tuple[str, int]] = []

    def setup_method(self) -> None:
        super().setup_method()
        self._created_worktrees: list[Path] = []
        self._state_snapshot: StateSnapshot | None = None

    def teardown_method(self) -> None:
        # Cleanup worktrees
        for wt in self._created_worktrees:
            self._cleanup_worktree(wt)
        super().teardown_method()

    def capture_state(self, repo_path: Path) -> StateSnapshot:
        """Capture git state before test."""
        self._state_snapshot = StateSnapshot(repo_path)
        return self._state_snapshot

    def assert_state_unchanged(self) -> None:
        """Verify no unintended changes to repo."""
        if self._state_snapshot:
            self._state_snapshot.assert_restored()
```

#### 1.2 Create Test Fixtures

**File:** `testing/fixtures/ralph.py`

```python
@pytest.fixture
def ralph_dry_run_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable dry-run mode: log but don't execute."""
    monkeypatch.setenv("RALPH_DRY_RUN", "true")
    monkeypatch.setenv("RALPH_SKIP_GIT_PUSH", "true")
    monkeypatch.setenv("RALPH_SKIP_LINEAR_UPDATE", "true")

@pytest.fixture
def isolated_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create isolated test repository."""
    repo_path = tmp_path / "test-repo"
    # Clone current repo without remote
    subprocess.run(["git", "clone", "--local", ".", str(repo_path)], check=True)
    subprocess.run(["git", "remote", "remove", "origin"], cwd=repo_path, check=True)
    yield repo_path

@pytest.fixture
def mock_linear_mcp() -> Generator[Mock, None, None]:
    """Mock Linear MCP for unit tests."""
    with patch("ralph.integrations.linear") as mock:
        mock.list_issues.return_value = [...]
        mock.update_issue.return_value = {"success": True}
        yield mock
```

#### 1.3 Add Dry-Run Mode to Ralph

**File:** `.ralph/config.yaml` (add section)

```yaml
testing:
  # Dry-run mode: log actions without executing
  dry_run_env_var: "RALPH_DRY_RUN"

  # Skip specific operations in test mode
  skip_git_push_env_var: "RALPH_SKIP_GIT_PUSH"
  skip_linear_update_env_var: "RALPH_SKIP_LINEAR_UPDATE"
  skip_cognee_sync_env_var: "RALPH_SKIP_COGNEE_SYNC"
```

---

### Phase 2: Unit Tests (Deterministic Components)

#### 2.1 Quality Gate Determinism Tests

**File:** `tests/ralph/unit/test_quality_gates.py`

```python
@pytest.mark.requirement("ralph-test-001")
class TestQualityGateDeterminism:
    """Quality gates must produce same result for same input."""

    def test_lint_gate_idempotent(self) -> None:
        """Lint gate returns same result on repeated runs."""
        code = "def func(): pass"
        result1 = run_lint_gate(code)
        result2 = run_lint_gate(code)
        assert result1 == result2

    def test_typecheck_gate_deterministic(self) -> None:
        """Type check gate is deterministic."""
        code = "def func(x: int) -> str: return str(x)"
        result1 = run_typecheck_gate(code)
        result2 = run_typecheck_gate(code)
        assert result1 == result2

    def test_gates_fail_bad_code(self) -> None:
        """Gates correctly reject invalid code."""
        bad_code = "def func(x: int) -> str: return x"  # Type error
        result = run_typecheck_gate(bad_code)
        assert result.status == "FAIL"
```

#### 2.2 State Machine Tests

**File:** `tests/ralph/unit/test_state_machine.py`

```python
@pytest.mark.requirement("ralph-test-002")
class TestAgentStateMachine:
    """Agent state transitions are deterministic."""

    def test_valid_state_transitions(self) -> None:
        """Agent follows valid state transition graph."""
        valid_transitions = {
            "init": ["impl"],
            "impl": ["lint"],
            "lint": ["impl", "typecheck"],  # Can retry impl
            "typecheck": ["impl", "test"],
            "test": ["impl", "security"],
            "security": ["impl", "constitution"],
            "constitution": ["impl", "commit"],
            "commit": ["COMPLETE", "impl"],  # Next subtask or done
        }

        agent = MockAgent()
        history = agent.run_with_history()

        for i, state in enumerate(history[:-1]):
            next_state = history[i + 1]
            assert next_state in valid_transitions[state]

    def test_termination_guaranteed(self) -> None:
        """Agent always terminates within max iterations."""
        for _ in range(100):  # Fuzz test
            agent = MockAgent(max_iterations=15)
            final = agent.run_until_complete()
            assert final.status in ["COMPLETE", "BLOCKED"]
            assert final.iteration <= 15
```

#### 2.3 Preflight Script Tests

**File:** `tests/ralph/unit/test_preflight.py`

```python
@pytest.mark.requirement("ralph-test-003")
class TestPreflightChecks:
    """Preflight checks work correctly."""

    def test_git_check_in_repo(self, isolated_repo: Path) -> None:
        """Git check passes in valid repo."""
        result = check_git(isolated_repo)
        assert result.status == "PASS"

    def test_git_check_outside_repo(self, tmp_path: Path) -> None:
        """Git check fails outside repo."""
        result = check_git(tmp_path)
        assert result.status == "BLOCKED"

    def test_linear_check_unauthenticated(self, mock_linear_mcp: Mock) -> None:
        """Linear check blocks when unauthenticated."""
        mock_linear_mcp.list_teams.side_effect = AuthError("Not authenticated")
        result = check_linear()
        assert result.status == "BLOCKED"
```

---

### Phase 3: Integration Tests (Real Operations, Isolated)

#### 3.1 Git Worktree Lifecycle Tests

**File:** `tests/ralph/integration/test_worktree_lifecycle.py`

```python
@pytest.mark.requirement("ralph-test-010")
class TestWorktreeLifecycle(RalphTestBase):
    """Git worktree operations work correctly."""

    def test_create_worktree_isolation(self, isolated_repo: Path) -> None:
        """Created worktree is isolated from main repo."""
        # Capture initial state
        self.capture_state(isolated_repo)

        # Create worktree
        wt_path = create_worktree(isolated_repo, "feature/test-task")
        self._created_worktrees.append(wt_path)

        # Verify isolation
        assert wt_path.exists()
        assert (wt_path / ".git").exists()

        # Modify file in worktree
        (wt_path / "test.py").write_text("# Test")

        # Main repo unchanged
        assert not (isolated_repo / "test.py").exists()

    def test_cleanup_worktree(self, isolated_repo: Path) -> None:
        """Worktree cleanup removes all traces."""
        wt_path = create_worktree(isolated_repo, "feature/cleanup-test")

        # Cleanup
        cleanup_worktree(wt_path)

        # Verify removed
        assert not wt_path.exists()
        branches = get_branches(isolated_repo)
        assert "feature/cleanup-test" not in branches

    def test_parallel_worktrees_no_conflict(self, isolated_repo: Path) -> None:
        """Multiple worktrees don't conflict."""
        wt1 = create_worktree(isolated_repo, "feature/agent-1")
        wt2 = create_worktree(isolated_repo, "feature/agent-2")

        # Both can modify different files
        (wt1 / "module_a.py").write_text("# Agent 1")
        (wt2 / "module_b.py").write_text("# Agent 2")

        # Both can commit
        commit_all(wt1, "Agent 1 changes")
        commit_all(wt2, "Agent 2 changes")

        # Verify branches exist
        branches = get_branches(isolated_repo)
        assert "feature/agent-1" in branches
        assert "feature/agent-2" in branches
```

#### 3.2 Memory Buffer Tests

**File:** `tests/ralph/integration/test_memory_buffer.py`

```python
@pytest.mark.requirement("ralph-test-011")
class TestMemoryBuffer(RalphTestBase):
    """Memory buffer (WAL) works correctly."""

    def test_buffer_write_when_cognee_unavailable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Entries buffer locally when Cognee unavailable."""
        # Simulate Cognee unavailable
        monkeypatch.setenv("COGNEE_API_KEY", "")

        buffer = MemoryBuffer(buffer_dir=tmp_path / "memory-buffer")
        entry = MemoryEntry(type="decision", content={"decision": "test"})

        buffer.write(entry)

        # Verify buffered locally
        pending = list((tmp_path / "memory-buffer/pending").glob("*.json"))
        assert len(pending) == 1

    def test_buffer_sync_when_reconnected(self, tmp_path: Path) -> None:
        """Buffered entries sync when Cognee reconnects."""
        buffer = MemoryBuffer(buffer_dir=tmp_path / "memory-buffer")

        # Create pending entry
        entry = MemoryEntry(type="decision", content={"decision": "test"})
        buffer._write_to_buffer(entry)

        # Mock Cognee available
        with patch("cognee.add_content") as mock_add:
            mock_add.return_value = {"success": True}

            # Sync
            report = buffer.sync_pending()

            # Verify synced
            assert report.synced == 1
            assert report.failed == 0
            pending = list((tmp_path / "memory-buffer/pending").glob("*.json"))
            assert len(pending) == 0
```

---

### Phase 4: Contract Tests (Cross-Component Consistency)

#### 4.1 Plan Schema Stability

**File:** `tests/ralph/contract/test_plan_schema.py`

```python
@pytest.mark.requirement("ralph-test-020")
class TestPlanSchemaContract:
    """plan.json schema is stable across versions."""

    def test_plan_schema_backwards_compatible(self) -> None:
        """New plan.json can read old format."""
        # Load old format
        old_plan = {
            "task_id": "T001",
            "status": "in_progress",
            "subtasks": [{"id": "T001.1", "passes": True}],
        }

        # Parse with current schema
        plan = Plan.model_validate(old_plan)

        # All fields accessible
        assert plan.task_id == "T001"
        assert plan.status == "in_progress"

    def test_plan_schema_validates_required_fields(self) -> None:
        """Plan schema rejects missing required fields."""
        invalid_plan = {"status": "in_progress"}  # Missing task_id

        with pytest.raises(ValidationError):
            Plan.model_validate(invalid_plan)
```

#### 4.2 Agent-Linear State Consistency

**File:** `tests/ralph/contract/test_linear_contract.py`

```python
@pytest.mark.requirement("ralph-test-021")
class TestLinearContract:
    """Agent state matches Linear issue state."""

    def test_agent_updates_match_linear_state(
        self,
        mock_linear_mcp: Mock,
    ) -> None:
        """Agent's recorded state matches Linear API calls."""
        # Track all Linear updates
        updates = []
        mock_linear_mcp.update_issue.side_effect = lambda **kw: updates.append(kw)

        # Run agent
        agent = MockAgent(linear=mock_linear_mcp)
        final_state = agent.run_until_complete()

        # Verify final update matches agent state
        last_update = updates[-1]
        assert last_update["state"] == final_state.linear_state
```

---

### Phase 5: E2E Tests (Full Workflow)

#### 5.1 Full Epic Dry-Run Test

**File:** `tests/ralph/e2e/test_full_epic_dry_run.py`

```python
@pytest.mark.requirement("ralph-test-030")
@pytest.mark.slow
class TestFullEpicDryRun(RalphTestBase):
    """Full epic workflow in dry-run mode."""

    def test_spawn_to_complete_dry_run(
        self,
        isolated_repo: Path,
        ralph_dry_run_env: None,
        mock_linear_mcp: Mock,
    ) -> None:
        """Complete epic workflow without side effects."""
        # Capture initial state
        self.capture_state(isolated_repo)

        # Configure mock Linear with test tasks
        mock_linear_mcp.list_issues.return_value = [
            {"id": "LIN-1", "title": "Task 1", "state": "backlog"},
            {"id": "LIN-2", "title": "Task 2", "state": "backlog"},
        ]

        # Run spawn (dry-run)
        result = ralph_spawn(epic="EP999", repo=isolated_repo)

        # Verify dry-run logged what would happen
        assert result.dry_run is True
        assert len(result.would_create_worktrees) == 2
        assert len(result.would_update_issues) == 2

        # Verify NO actual changes
        self.assert_state_unchanged()
        assert not mock_linear_mcp.update_issue.called
```

#### 5.2 Recovery from Interruption

**File:** `tests/ralph/e2e/test_recovery.py`

```python
@pytest.mark.requirement("ralph-test-031")
class TestRecovery(RalphTestBase):
    """Agent recovers from interruption."""

    def test_checkpoint_and_resume(self, isolated_repo: Path) -> None:
        """Agent resumes from checkpoint after interruption."""
        # Start agent, interrupt after 2 iterations
        agent = RalphAgent(repo=isolated_repo)
        agent.run_iterations(2)

        # Verify checkpoint created
        checkpoint_path = isolated_repo / ".ralph/session/checkpoints"
        checkpoints = list(checkpoint_path.glob("*.json"))
        assert len(checkpoints) >= 1

        # Resume from checkpoint
        resumed = RalphAgent.resume_from_checkpoint(checkpoints[-1])
        assert resumed.iteration >= 2

        # Continue to completion
        final = resumed.run_until_complete()
        assert final.status == "COMPLETE"
```

---

## Critical Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `testing/base_classes/ralph_test_base.py` | Base class for Ralph tests |
| `testing/fixtures/ralph.py` | Ralph-specific fixtures |
| `tests/ralph/conftest.py` | Ralph test configuration |
| `tests/ralph/unit/test_quality_gates.py` | Gate determinism tests |
| `tests/ralph/unit/test_state_machine.py` | State transition tests |
| `tests/ralph/unit/test_preflight.py` | Preflight script tests |
| `tests/ralph/integration/test_worktree_lifecycle.py` | Git worktree tests |
| `tests/ralph/integration/test_memory_buffer.py` | WAL buffer tests |
| `tests/ralph/contract/test_plan_schema.py` | Schema stability |
| `tests/ralph/contract/test_linear_contract.py` | Linear consistency |
| `tests/ralph/e2e/test_full_epic_dry_run.py` | Full workflow test |
| `tests/ralph/e2e/test_recovery.py` | Checkpoint/resume test |

### Modified Files

| File | Change |
|------|--------|
| `.ralph/config.yaml` | Add `testing:` section with dry-run env vars |
| `testing/fixtures/__init__.py` | Export Ralph fixtures |
| `pyproject.toml` | Add `ralph` pytest marker |

---

## Verification Plan

### Running the Tests

```bash
# Unit tests only (fast, no services)
uv run pytest tests/ralph/unit/ -v

# Integration tests (needs isolated repo)
uv run pytest tests/ralph/integration/ -v

# Contract tests
uv run pytest tests/ralph/contract/ -v

# E2E tests (slow, full workflow)
uv run pytest tests/ralph/e2e/ -v --slow

# All Ralph tests
uv run pytest tests/ralph/ -v
```

### Validation Criteria

| Test Category | Pass Criteria |
|---------------|---------------|
| **Unit: Gates** | Same code → same result (100% deterministic) |
| **Unit: State** | All transitions follow valid graph |
| **Integration: Worktree** | Isolated, no cross-contamination |
| **Integration: Buffer** | Entries persist, sync correctly |
| **Contract: Schema** | Old formats still parse |
| **E2E: Dry-run** | No actual state changes |
| **E2E: Recovery** | Resume from any checkpoint |

### CI Integration

```yaml
# .github/workflows/ralph-tests.yml
name: Ralph Workflow Tests

on:
  pull_request:
    paths:
      - '.ralph/**'
      - '.claude/skills/ralph-*/**'
      - 'tests/ralph/**'

jobs:
  ralph-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Ralph unit tests
        run: uv run pytest tests/ralph/unit/ -v
      - name: Run Ralph integration tests
        run: uv run pytest tests/ralph/integration/ -v
      - name: Run Ralph contract tests
        run: uv run pytest tests/ralph/contract/ -v
```

---

## Summary

This testing strategy addresses the unique challenges of agentic systems:

1. **Behavioral Testing**: Test what gates pass, not what text is generated
2. **Deterministic Termination**: Quality gates provide testable exit conditions
3. **Isolation**: Temporary repos + worktrees + mocks = no production impact
4. **Property Testing**: Verify invariants (termination, idempotence, consistency)
5. **Dry-Run Mode**: Full workflow testing without side effects
6. **Recovery Testing**: Checkpoint/resume cycles validate resilience

The key insight is that **agentic workflows have deterministic checkpoints** (quality gates, state transitions, external API calls) even though LLM outputs are non-deterministic. We test those checkpoints.
