# Decisions: E2E Alpha Stability

## D1: curl + REST API over other hook replacement approaches

**Decision**: Replace `bitnami/kubectl` with `curlimages/curl` + K8s REST API

**Alternatives considered**:
1. Remove VCT labels entirely (eliminates hook) — Medium complexity, requires VCT label audit
2. `imagePullPolicy: Never` + mandatory pre-load — Partial fix, converts to fast-fail not resolution
3. Increase `activeDeadlineSeconds` — Band-aid, doesn't solve image pull or Bitnami EOL

**Resolution rule**: DISAMBIGUATION — charter favours self-maintaining solutions. curl approach eliminates Bitnami dependency, uses already-pre-loaded image, and requires no future maintenance when K8s versions advance.

## D2: `:memory:` path fix over plugin generator enhancement

**Decision**: Fix `profiles.yml` directly (Phase 1) rather than building plugin generator enhancement (Phase 3)

**Rationale**: The `:memory:` fix is correct for all demo products and aligns with compiled artifacts. The plugin generator enhancement is a separate concern (ensuring alignment for future custom products) and should not block alpha stability.

**Resolution rule**: Simplest correct solution first. Track enhancement separately.

## D3: `context.run.run_id` over other parent ID candidates

**Decision**: Use Dagster's `context.run.run_id` as the OpenLineage parent run ID

**Alternatives considered**:
1. Keep `run_id` from `emit_start()` — Wrong semantically (asset-level, not orchestrator-level)
2. Generate a new UUID — Would break lineage graph (not connected to any real run)
3. Use `context.run.parent_run_id` — Only set for re-executions, `None` for normal runs

**Resolution rule**: OpenLineage ParentRunFacet spec defines parent as "the orchestrator run that launched this job". Dagster's `context.run.run_id` is exactly that.

## D4: Phase structure — quick wins first

**Decision**: Split into Phase 1 (quick wins, 4/7 fixes) and Phase 2 (helm resilience, 3/7 fixes) rather than a single large unit.

**Rationale**: Phase 1 fixes are trivial, low-risk, and independently shippable. Shipping them first reduces the failure count immediately while Phase 2 (more complex template rewrite) is developed and tested.

## D5: Track Phase 3 items as issues, not specs

**Decision**: Phase 3 items (upstream datacontract-cli issue, plugin generator enhancement, hook documentation) are tracked as GitHub issues, not specwright work units.

**Rationale**: These are independent improvements that don't block alpha stability. They should be prioritized in normal backlog grooming, not bundled with this fix batch.

## D6: Three work units, ordered by dependency and risk

**Decision**: Decompose into 3 units:
1. `unit-1-config-fixes` — Fix A + Fix B (config-only, zero code changes)
2. `unit-2-parentrun-wiring` — Fix C (one Python code change)
3. `unit-3-helm-hook-curl` — Fix D (Helm template rewrite + tests)

**Rationale**: Units are ordered by increasing complexity and risk. Unit 1 has no code changes (lowest risk). Unit 2 is a single-line Python fix. Unit 3 is the most complex (template rewrite, test updates, setup script). Each is independently shippable and testable. Fix A and Fix B are bundled because they're both config-only changes with no code.

**Resolution rule**: DISAMBIGUATION — blast radius boundaries. Config-only vs Python code vs Helm templates are natural unit boundaries.
