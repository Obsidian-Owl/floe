# Decisions: Salvage Branch Wrap-Up

## D-1: Single work unit, single PR (not decomposed)
**Rule applied**: DISAMBIGUATION — blast radius is local and both changes share `values-test.yaml`.
**Alternatives considered**:
- (A) Two PRs — one per original feature branch. Rejected: forces rebase of `values-test.yaml`; no blast-radius isolation since both land at the E2E boundary.
- (B) Three PRs — split iceberg-purge into "replace drop_table" vs "S3 sweep". Rejected: artificial; tests are one file, code is one function, reviewers have to context-switch.
- (C) **Single PR (chosen)**. Minimal rebase surface, single reviewer pass.

## D-2: Move `test_iceberg_purge.py` to `tests/unit/` rather than fix the E2E autouse fixture
**Rule applied**: Type 1 vs Type 2 — fixing the autouse fixture is a structural Type 1 change with broader blast radius; moving one test file is a local Type 2 change.
**Alternatives considered**:
- (A) Fix the E2E autouse fixture to skip when collected tests have no infrastructure markers. Rejected as out of scope — captured in assumptions.md A-6 for deferral.
- (B) Add a `tests/e2e/unit/` subdirectory with its own conftest overriding the autouse. Rejected: doubles test-location surface area; the file doesn't belong under `tests/e2e/` anyway because it uses mocks and imports no service clients (DIR-004).
- (C) **Move to `tests/unit/test_iceberg_purge.py` (chosen)**. Correct tier per test-organization.md. Update `_DBT_UTILS_PATH` to reflect new location.

## D-3: Keep the belt-and-suspenders S3 sweep even if Polaris #1195/#1448 gets fixed
**Rule applied**: DISAMBIGUATION — the cost of the sweep is small (one httpx call pair per namespace), the cost of stale metadata files is a silent cross-test contamination that wastes hours to debug.
**Alternatives considered**:
- (A) Gate the sweep behind a `POLARIS_VERSION <` check. Rejected: version detection adds complexity for minor savings.
- (B) **Keep unconditional (chosen)**. Simplicity wins; remove in a future cleanup once Polaris upstream is verified fixed in CI.

## D-4 (REVISED after critic BLOCK): Canonical path is `polaris.persistence.jdbc.*`, remove `polaris.env[QUARKUS_DATASOURCE_*]` duplication
**Context change**: The critic correctly flagged that the original D-4 made an unverified claim about Quarkus env-var precedence. Reading `templates/configmap-polaris.yaml:31-46`, the template **renders `quarkus.datasource.password={{ .password }}` into `application.properties`** when `persistence.jdbc.password` is set. So the chart-native path already wires credentials through the configmap — `polaris.env[QUARKUS_DATASOURCE_*]` is the duplicate, not `persistence.jdbc.*`.

**Rule applied**: DISAMBIGUATION — chart-native path wins over escape hatch when both work.

**Alternatives considered**:
- (A) Keep `polaris.env` canonical, remove `persistence.jdbc.*`. Rejected: would break the chart template's conditional JDBC block (the block's purpose is to render from `persistence.jdbc.*`); also makes the new helm unittest AC-2 (which asserts the rendered `quarkus.datasource.jdbc.url=...` property) meaningless.
- (B) **Keep both (original D-4)**. Rejected: duplication is a maintenance hazard; Quarkus env-var precedence means a future edit that changes one and not the other causes silent drift.
- (C) **Canonical = `persistence.jdbc.*` (chosen)**. Aligns with chart template. Remove duplicated `QUARKUS_DATASOURCE_JDBC_URL / USERNAME / PASSWORD / DB_KIND` from `polaris.env` in values-test.yaml. Verify: after removal, (1) helm unittest AC-1 must be updated because it asserts `polaris.env` contains those entries; (2) the bootstrap Job and deployment must still start against JDBC via the rendered application.properties.

**Residual risk**: If Polaris / Quarkus requires any of these values as real env vars (not config file) for some JVM startup reason, removing them will break runtime. AC-4 (pod restart durability test) is the behavioral gate that catches this — if Polaris comes up and serves traffic after restart with the config-file-only path, the decision is validated.

## D-5 (REVISED): E2E-tier ACs 4 and 5 must defeat Accomplishment Simulator
**Rule applied**: `quality-escalation.md` side-effect verification.
**Revision driver**: Critic correctly pointed out that the first-pass AC-4 and AC-5 wording was itself vulnerable to the Accomplishment Simulator pattern — listing a bootstrap namespace proves nothing, asserting zero objects on a never-populated prefix proves nothing.

**Strengthened requirements** (see design.md AC-4 / AC-5 for full text):
- AC-4: unique non-bootstrap namespace with populated table; fresh catalog client after restart; assert table UUID survives
- AC-5: INSERT ≥10 rows first, assert N > 0 before purge, assert 0 after — N→0 delta proves the delete code path executed

**Status**: Recorded as ACs 4 and 5 with `[tier: e2e]` annotation. Implementation in the build phase.

## D-6: Defer demo namespace coupling verification to build-phase docs, not a test
**Rule applied**: DISAMBIGUATION — the critic flagged that `dbt_utils.py:246,250` hardcodes a `<product>_raw` / `<product>` namespace convention for purging, but none of the salvage artifacts verify that the demo dbt projects actually write to those namespaces in Polaris.

**Alternatives considered**:
- (A) Add an integration test that runs `dbt seed` and asserts Polaris contains `customer_360_raw`. Rejected: this is a heavyweight test for what is really a documentation gap; the existing mock tests verify the call contract.
- (B) Grep `demo/*/profiles.yml` for the namespace convention. Rejected: profiles.yml is generated at E2E runtime by the `dbt_e2e_profile` fixture, not checked in at design-time.
- (C) **Document the namespace mapping in as-built notes during build phase (chosen)**. AC-9 captures this: the build phase must confirm and document the convention in the PR description. If the convention is wrong, AC-5 (S3 purge test with real data) will fail because the purge will no-op.

**Status**: AC-9 recorded. If discovery during build reveals the convention is broken, escalate via AskUserQuestion — do not silently "fix" the mapping.

## D-7: AC-5 imports `_purge_iceberg_namespace` via `importlib` with a unique module name; AC-4 does not import `dbt_utils` at all
**Rule applied**: DISAMBIGUATION — the test must be the function's runtime contract, not a shared-state trap.
**Context**: Critic B2 flagged that `dbt_utils.py` has a module-level `_catalog_cache: dict` that the function under test reads and writes. If the AC-5 test imports `dbt_utils` by the normal name, a second importer in the same pytest process (including AC-4, if it also imported) would share the cache, undermining both tests' "fresh client" invariants.

**Alternatives considered**:
- (A) Factor `_purge_iceberg_namespace` into an importable module. Rejected: cross-cutting refactor to production code path for a test concern; violates "no new production code" budget.
- (B) Run AC-5 in a subprocess (`python -c`). Rejected: obscures assertions, complicates credential passing, hurts debuggability.
- (C) **Import via `importlib.util.spec_from_file_location` with a unique module name, defensively clear the cache, and require AC-4 to NOT import `dbt_utils` at all (chosen)**. Each test gets full isolation: AC-4 builds its catalog inline; AC-5 gets a fresh module instance with a fresh cache because `importlib.util.module_from_spec` creates a brand-new object regardless of `sys.modules` state (and the unique name ensures no collision if `sys.modules` *is* consulted elsewhere).

**Residual risk**: If a future developer adds a non-test importer of `dbt_utils` in the same process with a side effect that mutates its own module's cache, the AC-5 isolated instance remains unaffected because module instances do not share globals. Low risk, worth the simplicity.

## D-8: AC-10 (explicit E2E execution) is a first-class acceptance criterion
**Rule applied**: DISAMBIGUATION — "written but never run" is the workflow-level Accomplishment Simulator. The test-level anti-fake defenses in AC-4/AC-5 are meaningless if no one actually runs them before the PR merges.

**Alternatives considered**:
- (A) Fold E2E execution into AC-4/AC-5 directly (don't create a new AC). Rejected: mixes "the test exists" with "the test was run" — ambiguous for reviewers.
- (B) Require CI to run `make test-e2e` as a merge gate. Rejected: CI E2E is not part of this wrap-up's scope and is flaky/slow; would couple this PR to a separate infra change.
- (C) **Add AC-10 requiring a build-phase `make test-e2e` invocation with pasted output evidence (chosen)**. The human gate (PR review) reads the evidence; the merge is not automatically blocked by CI, but a missing AC-10 evidence block visibly fails code review.

**Status**: AC-10 recorded. Tester MUST run `make test-e2e` (or `make test-e2e-host` for dev-loop speed) at least once during Task 5 and capture the passing output in as-built notes.
