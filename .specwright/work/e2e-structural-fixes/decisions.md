# Decisions: E2E Structural Fixes

## D1: Scope — Focus on structural fixes, not tactical patches

**Decision**: Design long-term structural solutions only. No SSH keepalive,
no port-forward watchdogs, no retry band-aids.

**Rule applied**: User instruction — "I want the long term solutions - no tactical fixes"

**Rationale**: Tactical fixes (SSH keepalive, watchdog processes) address symptoms.
The user wants to eliminate the root cause: tests depending on fragile tunnel/port-forward
infrastructure.

## D2: In-cluster test runner as primary fix

**Decision**: Prioritize completing the in-cluster test runner over alternatives
like kubefwd or improved port-forwarding.

**Rule applied**: DISAMBIGUATION — codebase context. The in-cluster infrastructure
is already 90% built (Dockerfile, Job manifests, ServiceEndpoint, RBAC). Completing
it requires fixing 2 hardcoded lines + build flow. kubefwd would add a new dependency
and still depend on K8s API tunnels.

**Alternatives considered**:
- kubefwd: Replaces 9 port-forwards with 1, but still needs K8s API tunnel. Adds sudo requirement.
- Improved test-e2e.sh: Watchdog + reconnect, but still fundamentally fragile.
- GitHub Actions CI: Eliminates SSH tunnel (Kind on GHA runner), but doesn't help DevPod.

## D3: Three-fix design (ranked by impact)

**Decision**: Design three structural fixes ranked by bang-for-buck:
1. In-cluster test runner (45+ failures eliminated)
2. K8sRunLauncher image config (4-10 cascade failures)
3. Conftest hardcoding elimination (enables #1, fixes OTel/lineage independently)

**Rule applied**: DISAMBIGUATION — quantitative impact analysis from failure categorization.

## D4: Work unit decomposition

**Decision**: Single work unit (not multi-unit). All three fixes are tightly coupled —
the in-cluster runner depends on conftest fixes, and K8sRunLauncher fix is small enough
to bundle.

**Rule applied**: Decomposition criteria — all changes needed for any fix to be testable
end-to-end. Independent units would each require full E2E validation.

## D5: Flat layout (single work unit)

**Decision**: Use flat layout (spec.md + plan.md in work dir root), not multi-unit.

**Rule applied**: Design decision D4 already determined single work unit.
All fixes are tightly coupled — in-cluster runner depends on conftest fixes,
and profile isolation may resolve itself once compilation endpoints are fixed.
5 tasks, all in one unit.

## D6: Task ordering — root cause first

**Decision**: T1 (conftest fix) → T2 (error messages) → T5 (profile investigation)
→ T3 (orchestration script) → T4 (charts verification).

**Rule applied**: DISAMBIGUATION — fix root cause first, then check cascading failures
before building infrastructure. T5 (profile) must follow T1 to determine if it's a
cascade failure.

## D7: Architect BLOCK resolved — Job manifest exists

**Decision**: Architect flagged `test-e2e.yaml` as non-existent. Verified: file exists
at `testing/k8s/jobs/test-e2e.yaml` with Job name `floe-test-e2e`. The architect confused
it with the older `test-runner.yaml`. BLOCK dismissed, no changes needed.

## D8: Existing work unit is shipped — start fresh

**Decision**: Start new work unit `e2e-structural-fixes`. Previous work
`e2e-in-cluster-ci` is shipped.

**Rule applied**: `protocols/state.md` — `currentWork.status === "shipped"` + argument provided → new work.
