# Decisions: E2E Tunnel Resilience

## D1: Layered Resilience Over Architecture Replacement

**Decision**: Add SSH keepalive + watchdog + test resilience instead of replacing with kubefwd or in-cluster runner.
**Rule**: DISAMBIGUATION — simplest reversible change that addresses root cause.
**Alternatives considered**:
- kubefwd: Better auto-reconnect but still depends on K8s API tunnel; adds sudo requirement; /etc/hosts cleanup risk
- In-cluster runner: Eliminates all tunneling but requires build cycle changes, result extraction plumbing, and loses local debugger
**Why this**: The current architecture is sound — only the keepalive and recovery are missing. 3 layers of defense-in-depth with ~60 lines of changes vs. architecture replacement.

## D2: pytest-rerunfailures Over pytest-retry

**Decision**: Use pytest-rerunfailures (v16.1) over pytest-retry (v1.7.0).
**Rule**: DISAMBIGUATION — more mature, more flexible filtering.
**Rationale**: `--rerun-except AssertionError` is exactly the filter we need. pytest-retry doesn't retry fixture setup failures, which is where most infrastructure errors manifest. pytest-rerunfailures is maintained by pytest-dev (official).

## D3: Smoke Gate Uses pytest.exit() Not pytest.fail()

**Decision**: Use `pytest.exit(returncode=3)` to abort the entire session when infrastructure is dead.
**Rule**: DISAMBIGUATION — minimize blast radius of known-dead infrastructure.
**Rationale**: When Dagster/Polaris/MinIO are all unreachable, running 230 tests to get 72 identical ERRORs wastes 48 minutes. A clean abort with returncode 3 (distinct from test failures at returncode 1) makes the failure immediately actionable.

## D4: ServiceEndpoint for Telemetry Instead of New Env Vars

**Decision**: Use existing `ServiceEndpoint` abstraction for OTel/OpenLineage endpoints.
**Rule**: DISAMBIGUATION — reuse existing abstraction over introducing new env vars.
**Rationale**: `ServiceEndpoint` already handles host/port resolution with K8s DNS fallback. Adding new env vars (`OTEL_HOST`, `MARQUEZ_HOST`) would create parallel resolution paths.

## D5: Single Work Unit (No Decomposition)

**Decision**: Implement as a single work unit with 6 tasks, not multi-unit.
**Rule**: DISAMBIGUATION — blast radius is local/adjacent, total ~70 lines across 5 files.
**Rationale**: No task has systemic blast radius. All tasks are independently testable within one unit. Decomposition would add overhead without benefit.

## D6: Scope Rerun Config to E2E Only

**Decision**: Configure pytest-rerunfailures via `pytest_configure` hook in `tests/e2e/conftest.py`, not global `addopts`.
**Rule**: DISAMBIGUATION — minimize blast radius.
**Rationale**: Global `addopts` would apply reruns to unit/contract/integration tests where `ConnectionError` might indicate a real bug, not infrastructure flakiness. E2E-scoped config ensures reruns only apply where tunnel instability is the failure mode.

## D7: Start New Work Unit (Not Continue e2e-five-failures)

**Decision**: Create new work unit `e2e-tunnel-resilience` instead of adding to `e2e-five-failures`.
**Rule**: DISAMBIGUATION — different scope, different blast radius.
**Rationale**: `e2e-five-failures` fixed test/prod bugs (assetSelection, lockfiles, pod readiness). This work unit fixes infrastructure reliability. Different scope = different work unit.
