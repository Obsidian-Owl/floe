# Decisions

## D1 — State transition: shipped → (none) without going through sw-learn

**Rule**: DISAMBIGUATION (protocols/decision.md). Prior `currentWork` had status `shipped` (test-infra-convergence / security-hardening). sw-learn was not run. User invoked sw-design with an argument requesting new work. Reading the charter's intent, the purpose of the `shipped → (none)` transition via sw-learn is knowledge capture. The user has chosen to skip knowledge capture and start new work — a legitimate choice. Per the abandoned→(none) mechanics documented in sw-design's state constraints, clear `currentWork` to null (and reset `workUnits`) before creating the new design.

**Recorded as**: state update — `currentWork` cleared, `workUnits` reset, new design created under id `test-infra-drift-elimination`.

## D2 — Work ID: `test-infra-drift-elimination`

**Rule**: DISAMBIGUATION (name should reflect outcome, not symptom). Alternatives considered:
- `test-infra-contract-test` — describes one deliverable, not the whole design
- `test-infra-single-source-of-truth` — accurate, too long
- `fix-test-runner-yaml` — names a symptom, invites scope creep
- `test-infra-drift-elimination` — describes the outcome: after this lands, drift is structurally impossible

**Choice**: `test-infra-drift-elimination`.

## D3 — Primary pattern: chart templating over raw manifests + generation

**Rule**: DISAMBIGUATION (simplest solution grounded in research + existing repo idioms). The chart already defines the helpers we need. Every production service in the platform uses them. The test jobs are the sole outliers maintaining a parallel hardcoded copy. The fix is not to add a second layer of enforcement (contract test alone) but to eliminate the parallelism.

**Alternatives evaluated and rejected** (detailed in design.md "Why not the alternatives"):
- Contract test only → catches drift, doesn't prevent it. Maintenance tax unchanged.
- Generate-at-build → two sources of truth + a generator, stale output problem.
- `helm upgrade --set tests.enabled=true` → mutates release history, risks rollback pollution.

**Choice**: Move test jobs into `charts/floe-platform/templates/tests/`, render via `helm template -s ... | kubectl apply -f -`.

## D4 — Contract test uses pytest, not conftest/Rego

**Rule**: DISAMBIGUATION (repo consistency). `tests/contract/test_helm_security_contexts.py` already establishes the pattern. Using the same approach lowers reviewer cognitive load and lets us reuse the `rendered_manifests` fixture directly.

**Escalation check**: This is a choice between two valid tools. Per CLAUDE.md Principle 9, escalate design choices. Justification for not escalating here: the default (pytest) is strongly indicated by existing repo pattern, the alternative (Rego) adds tooling footprint with no unique capability at this scale, and the choice is fully reversible. Recording the choice here lets the user veto it at the gate review without an extra round-trip. If the user prefers Rego, task 4 swaps one file.

**Choice**: pytest under `tests/contract/`. Alternative documented in `design.md` § Why not the alternatives.

## D5 — Cleanup scope: delete `testing/k8s/jobs/` and `testing/k8s/rbac/` directories entirely

**Rule**: DISAMBIGUATION + CLAUDE.md "pre-alpha, no backcompat needed". Once the chart renders all test manifests, the raw directories have zero purpose. Leaving them as stubs is the exact pattern that produced the `test-runner.yaml` rot. Pre-alpha status means we do not need a deprecation window.

**Choice**: delete both directories in task 3. Contract test AC1 asserts they stay gone.

## D6 — Env var unification: absorb both old names

**Rule**: DISAMBIGUATION (least surprise for callers who memorized either env var name). `common.sh` reads `KIND_CLUSTER_NAME`, then `KIND_CLUSTER`, defaults to `floe`, and exposes a single canonical `FLOE_KIND_CLUSTER`. Old names continue to work; new code uses only the canonical. No hard cutover.

**Choice**: absorb + deprecate (old names work, grep check in contract test ensures new code doesn't add more).

## D7 — Single work unit, 4 tasks, not a decomposition

**Rule**: DISAMBIGUATION (decomposition only when units are independently shippable). The four tasks are tightly coupled: each breaks the previous's test pass condition if reordered. One work unit, four sequential tasks.

**Choice**: single unit, sw-plan turns this into a linear task list.

## D8 — No escalation to user at design gate beyond the normal sw-design handoff

**Rule**: CLAUDE.md Principle 9 requires escalation for design choices. This design *is* the escalation — the user will see it at the sw-design gate and can veto or revise before sw-plan runs. Every alternative considered is documented in design.md so the user can select a different branch with minimal rework. No mid-design `AskUserQuestion` is needed because the user's argument already specified the direction ("implement resilient patterns", "naming conventions in manifests").

**Choice**: present at gate, do not block on mid-design questions.

---

## Planning-phase decisions

## D9 — Single unit, flat layout (no decomposition)

**Rule**: DISAMBIGUATION (decompose only when units are independently shippable). The four tasks are sequentially dependent: you cannot delete raw manifests before scripts stop referencing them, you cannot retarget scripts before the chart templates exist, you cannot add the contract test until raw manifests are gone. Decomposing would produce three units where two are incomplete-without-the-others — classic false decomposition.

**Choice**: single flat-layout unit. `spec.md` + `plan.md` in `.specwright/work/test-infra-drift-elimination/`. No `units/` subdir. No `integration-criteria.md` (only generated for multi-unit work).

## D10 — Tier annotations per AC

**Rule**: protocols/testing-strategy.md — apply tier tags declaratively based on TESTING.md boundary classification.

Tier assignments:
- **contract**: ACs that assert properties of rendered chart output or repo structure (static/offline). AC-1, AC-2, AC-3, AC-4, AC-5, AC-7, AC-9, AC-11. Runs in `tests/contract/`.
- **integration**: ACs that execute shell/Python code and assert behavior without requiring a full cluster. AC-6 (`common.sh` subshell sourcing), AC-8 (script dispatch). Runs in `tests/unit/` or `tests/integration/` depending on mock boundary — `common.sh` unit test is fine in `tests/unit/` since it only subshells bash.
- **e2e**: AC-10 requires a live Kind cluster on Hetzner DevPod. Tier: e2e.

**Choice**: each AC in spec.md carries a `[tier: X]` annotation inline with its falsifying test. sw-build's tier-aware dispatch picks up the tags automatically.

## D11 — Carry-forward of security-hardening AC-8

**Rule**: protocols/assumptions.md — shipped acceptance criteria from previous work units are inherited constraints, not rewritten. Security-hardening AC-8 (standard runner Role: no list/watch on secrets, get retained) constrains the new `rbac-standard.yaml` chart template. AC-4 in this spec explicitly asserts this.

**Choice**: AC-4's falsifying test includes an assertion that standard runner Role does not contain `list`/`watch` on `secrets`. Prevents regression of shipped AC-8.

## D12 — `fullnameOverride` retained as-is

**Rule**: DISAMBIGUATION — user's argument did not direct removal; design explicitly keeps it; contract test AC-9 asserts it stays pinned. Removing it is a separate concern with broader blast radius (every subchart, every helm-unittest asserting a literal fullname would need review).

**Choice**: `fullnameOverride: floe-platform` stays in `values-test.yaml`. `floe_service_name` respects it implicitly via `$FLOE_RELEASE_NAME`. A future work unit can untangle it if desired.

