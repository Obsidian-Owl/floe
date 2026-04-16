# Decisions: E2E Permanent Fixes

## D-1: Use purge_table + S3 prefix deletion instead of purge_table alone
- **Type:** DISAMBIGUATION
- **Rule applied:** Evidence-based (Polaris bugs #1195, #1448 confirm server-side purge is unreliable)
- **Alternatives:** (A) purge_table only, (B) S3 prefix deletion only, (C) both
- **Choice:** C — belt-and-suspenders ensures complete cleanup regardless of Polaris behavior
- **Reversibility:** Type 2 (easily changed)

## D-2: PostgreSQL over H2 for Polaris persistence
- **Type:** DISAMBIGUATION
- **Rule applied:** Prefer infrastructure already deployed (PostgreSQL is running; H2 is undocumented in Helm chart)
- **Alternatives:** (A) PostgreSQL, (B) H2 file-based, (C) keep in-memory + re-bootstrap
- **Choice:** A — zero new infrastructure, officially documented
- **Reversibility:** Type 2

## D-3: Fail early on missing manifest instead of fallback values
- **Type:** DISAMBIGUATION
- **Rule applied:** Fail fast principle (Constitution Principle IX — Escalation Over Assumption)
- **Alternatives:** (A) keep fallback values, (B) fail with error, (C) warn and use fallback
- **Choice:** B — silent fallback with wrong values is worse than a clear error
- **Reversibility:** Type 2

## D-4: Defer in-cluster test runner to separate design
- **Type:** DISAMBIGUATION  
- **Rule applied:** Scope containment — the 4 fixes are independently valuable and smaller scope
- **Alternatives:** (A) include in-cluster runner in this design, (B) defer to separate work
- **Choice:** B — in-cluster runner is a larger effort with different blast radius
- **Reversibility:** Type 2

## D-5: Change parentRun→parent in production code AND unit tests simultaneously
- **Type:** DISAMBIGUATION
- **Rule applied:** Spec compliance (OpenLineage standard renamed the key)
- **Alternatives:** (A) change only production code, (B) change both, (C) support both keys
- **Choice:** B — unit tests should assert spec-correct behavior; E2E test already handles both keys
- **Reversibility:** Type 2

## D-6: Four independent work units vs single monolithic change
- **Type:** DISAMBIGUATION
- **Rule applied:** Each fix is independently testable and deployable; decomposition enables incremental progress
- **Choice:** Four work units ordered by dependency (purge → persistence → config → lineage)
- **Reversibility:** Type 2

## D-7 (Planning): Work unit ordering
- **Type:** DISAMBIGUATION
- **Rule applied:** Dependency order — purge is prerequisite-free, persistence needs purge working, config needs persistence alignment, lineage is independent but least impactful
- **Choice:** iceberg-purge → polaris-persistence → config-source-of-truth → lineage-template
- **Reversibility:** Type 2

## D-8 (Pivot): Replace code generation with runtime loader (Option B)
- **Type:** DISAMBIGUATION — user-directed pivot
- **Rule applied:** User chose Option B after architectural analysis showed 96% boilerplate, module-load crashes, and divergent code paths
- **Alternatives:** (A) Fix templates, (B) Runtime loader, (C) Full dynamic discovery
- **Choice:** B — achieves same reliability as C with minimal blast radius; reuses existing `create_definitions()` engine
- **Reversibility:** Type 2 (definitions.py files are regenerable)
- **Rationale:** The code generation approach is fundamentally flawed — it creates N copies of logic that should exist once. The dynamic `create_definitions()` path already handles everything correctly; the loader bridges Dagster module discovery to it.

## D-9 (Pivot): Iceberg export as post-hook, not inline code
- **Type:** DISAMBIGUATION
- **Rule applied:** DRY — 84-line function exists in 3 generated files identically
- **Choice:** Extract to `floe_orchestrator_dagster.export.iceberg`, attach as post-materialization hook
- **Reversibility:** Type 2

## D-10 (Pivot): Retain simplified generate_entry_point_code()
- **Type:** DISAMBIGUATION
- **Rule applied:** Backward compatibility — users may rely on `floe compile --generate-definitions`
- **Choice:** Keep the method but generate the thin loader pattern instead of the 187-line template
- **Reversibility:** Type 2

## D-11 (Pivot): Loader is NEW @dbt_assets path, NOT delegate to create_definitions()
- **Type:** DISAMBIGUATION — resolved by architect critic (BLOCK)
- **Rule applied:** `create_definitions()` uses per-model `@asset`; generated code uses `@dbt_assets`. These are fundamentally different Dagster APIs. Loader must match generated code pattern.
- **Alternatives:** (A) delegate to `create_definitions()`, (B) implement `@dbt_assets` in loader
- **Choice:** B — loader is the canonical `@dbt_assets` path. `create_definitions()` remains for SDK use.
- **Reversibility:** Type 2

## D-13 (Pivot): Expand to 5 remaining work units covering all 6 audit BLOCKERs
- **Type:** DISAMBIGUATION — user-directed ("Yes - they must be solved!!! These are critical issues!!!")
- **Rule applied:** User explicitly rejected deferral of DX-004 and DBT-001
- **Alternatives:** (A) Defer DX-004/DBT-001 to separate work, (B) Include all BLOCKERs
- **Choice:** B — all 6 BLOCKERs get work units: runtime-loader (DX-001/002), loud-failures (DX-003/CON-001), config-merge-fix (DX-004), credential-consolidation (DBT-001), e2e-proof (validation)
- **Reversibility:** Type 2
- **Rationale:** User considers all BLOCKERs critical to alpha readiness. No deferral.

## D-14 (Pivot): Runtime-loader AC-3 defers factory semantics to loud-failures unit
- **Type:** DISAMBIGUATION
- **Rule applied:** Separation of concerns — loader wraps factories as-is (unit 5), factory semantics fixed separately (unit 6)
- **Choice:** Loader propagates factory exceptions through ResourceDefinition but does not modify factory behavior. Unit 6 fixes the factories themselves.
- **Reversibility:** Type 2

## D-15 (Pivot): E2E proof as final validation unit
- **Type:** DISAMBIGUATION
- **Rule applied:** Testing must prove fixes work, not just that code compiles. User: "strict, strong testing practices"
- **Choice:** Dedicated unit 9 with E2E tests mapping to each audit BLOCKER. No production code — pure validation.
- **Reversibility:** Type 2

## D-12 (Pivot): Lineage emission matches dynamic path quality
- **Type:** DISAMBIGUATION
- **Rule applied:** The dynamic path (plugin.py:553-578) has superior lineage emission: TraceCorrelationFacetBuilder, emit_fail, fallback uuid4(). Generated code had simplified version. Loader adopts the better pattern.
- **Choice:** Full lineage pattern from dynamic path
- **Reversibility:** Type 2
