# Tasks: OTel Code Instrumentation

**Input**: Design documents from `/specs/6c-otel-code-instrumentation/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.
Tests are mandatory per spec (US5 is P0, FR-020 through FR-024 require tests).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## User Story / Priority Map

| Story | Title | Priority | Plan Phases |
|-------|-------|----------|-------------|
| US1 | Every Plugin Operation Creates Spans | P0 | 5, 6, 9 |
| US2 | Unified @traced Decorator | P1 | 2, 3 |
| US3 | Plugin Instrumentation Audit at Startup | P1 | 4, 7 |
| US4 | Span Error Sanitization Across All Plugins | P2 | 1, 6 |
| US5 | Comprehensive Test Coverage | P0 | 8, 9 |

---

## Phase 1: Foundational — Error Sanitization Utility

**Purpose**: Promote `sanitize_error_message()` to floe-core as shared utility. This is the foundation all other phases build on — every new tracing module and every error recording change depends on this utility existing.

**CRITICAL**: No plugin tracing work can begin until this phase is complete.

- [ ] T001 [US4] Create `sanitize_error_message()` in `packages/floe-core/src/floe_core/telemetry/sanitization.py` — promote from `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py:83-110` with `_SENSITIVE_KEY_PATTERN`, `_URL_CREDENTIAL_PATTERN`, max_length truncation
- [ ] T002 [US4] Export `sanitize_error_message` from `packages/floe-core/src/floe_core/telemetry/__init__.py`
- [ ] T003 [US4] Write unit tests in `packages/floe-core/tests/unit/test_telemetry/test_sanitization.py` — URL credential redaction, key-value redaction, multiple sensitive keys, truncation, clean passthrough, empty string, very long message (FR-014)
- [ ] T004 [US4] Replace private impl in `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py` — import `sanitize_error_message` from `floe_core.telemetry.sanitization` instead of local `_sanitize_message`, remove private copies of `_SENSITIVE_KEY_PATTERN` and `_URL_CREDENTIAL_PATTERN`

**Checkpoint**: `sanitize_error_message()` available as public API in floe-core. Run `pytest packages/floe-core/tests/unit/test_telemetry/test_sanitization.py -v` to verify.

---

## Phase 2: Foundational — Unified @traced Decorator + PluginMetadata

**Purpose**: Unify the two divergent `@traced` APIs AND add `tracer_name` property to PluginMetadata. These are independent workstreams that can run in parallel, both blocking later phases.

### US2: Unified @traced Decorator

- [ ] T005 [US2] Add `attributes_fn` parameter to `@traced` decorator in `packages/floe-core/src/floe_core/telemetry/tracing.py` — add `attributes_fn: Callable[..., dict[str, Any]] | None = None`, wrap in try/except (fail-safe), use `sanitize_error_message()` in error recording (FR-008, FR-009, FR-010)
- [ ] T006 [US2] Write tests for unified `@traced` in `packages/floe-core/tests/unit/test_telemetry/test_traced_unified.py` — attributes_fn receives correct args/kwargs, attributes_fn failure logged but non-fatal, attributes_fn + attributes + floe_attributes compose, error recording uses sanitize_error_message, async with attributes_fn, nested spans (FR-023)
- [ ] T007 [US2] Migrate floe-iceberg to unified `@traced` — modify `packages/floe-iceberg/src/floe_iceberg/telemetry.py` to remove local `traced()` definition (lines 87-200), import from `floe_core.telemetry.tracing`, re-export for backwards compat; update callers using `operation_name=` to `name=` (FR-011)
- [ ] T008 [US2] Run existing floe-iceberg tests to verify no regression after migration

### US3: PluginMetadata tracer_name Property

- [ ] T009 [P] [US3] Add optional `tracer_name` property to `PluginMetadata` in `packages/floe-core/src/floe_core/plugin_metadata.py` — default returns `None`, docstring explains purpose (FR-015)
- [ ] T010 [P] [US3] Write unit tests in `packages/floe-core/tests/unit/test_plugin_metadata_tracer.py` — default returns None, override returns correct name, multiple plugins have unique tracer names

**Checkpoint**: Unified `@traced` passes all tests including new attributes_fn tests. floe-iceberg tests still pass. PluginMetadata has `tracer_name`. Run `pytest packages/floe-core/tests/unit/test_telemetry/ packages/floe-iceberg/tests/ packages/floe-core/tests/unit/test_plugin_metadata_tracer.py -v`.

---

## Phase 3: US1 — Security & Secrets Plugin Instrumentation (Tier 1)

**Goal**: Instrument the 4 security-sensitive plugins first — secrets access and identity/RBAC operations are high-value for audit trail.

**Independent Test**: Run each plugin's `test_tracing.py` with `InMemorySpanExporter` to verify spans created with correct names, attributes, and error recording.

### Tests for Phase 3

- [ ] T011 [P] [US5] Write tracing test for floe-secrets-infisical in `plugins/floe-secrets-infisical/tests/unit/test_tracing.py` — span name, secrets.provider attr, secrets.key_name attr, NO secret values in attrs, error sanitized (FR-020, FR-021)
- [ ] T012 [P] [US5] Write tracing test for floe-secrets-k8s in `plugins/floe-secrets-k8s/tests/unit/test_tracing.py` — same pattern as T011
- [ ] T013 [P] [US5] Write tracing test for floe-identity-keycloak in `plugins/floe-identity-keycloak/tests/unit/test_tracing.py` — replaces mock-based test_otel_tracing.py with InMemorySpanExporter-based test (FR-020, FR-021)
- [ ] T014 [P] [US5] Write tracing test for floe-rbac-k8s in `plugins/floe-rbac-k8s/tests/unit/test_tracing.py` — span name, security.policy_type attr, error sanitized

### Implementation for Phase 3

- [ ] T015 [P] [US1] Create `tracing.py` for floe-secrets-infisical — extract from `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py` inline tracing into `plugins/floe-secrets-infisical/src/floe_secrets_infisical/tracing.py` with `TRACER_NAME="floe.secrets.infisical"`, `secrets_span()` context manager, `ATTR_PROVIDER`, `ATTR_KEY_NAME` constants (FR-003)
- [ ] T016 [P] [US1] Create `tracing.py` for floe-secrets-k8s in `plugins/floe-secrets-k8s/src/floe_secrets_k8s/tracing.py` — `TRACER_NAME="floe.secrets.k8s"`, `secrets_span()` context manager, same attr constants (FR-003)
- [ ] T017 [P] [US1] Create `tracing.py` for floe-identity-keycloak — extract from `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py` inline tracing into `plugins/floe-identity-keycloak/src/floe_identity_keycloak/tracing.py` with `TRACER_NAME="floe.identity.keycloak"`, `identity_span()` context manager (FR-007 identity part)
- [ ] T018 [P] [US1] Create `tracing.py` for floe-rbac-k8s in `plugins/floe-rbac-k8s/src/floe_rbac_k8s/tracing.py` — `TRACER_NAME="floe.security.rbac"`, `security_span()` context manager, `ATTR_POLICY_TYPE`, `ATTR_RESOURCE_COUNT` (FR-007)
- [ ] T019 [US1] Wire `secrets_span()` into floe-secrets-infisical plugin.py — replace inline tracer usage with context manager calls for `get_secret`, `set_secret`, `delete_secret`, `list_secrets`
- [ ] T020 [US1] Wire `secrets_span()` into floe-secrets-k8s plugin.py
- [ ] T021 [US1] Wire `identity_span()` into floe-identity-keycloak plugin.py — replace inline tracing
- [ ] T022 [US1] Wire `security_span()` into floe-rbac-k8s plugin.py
- [ ] T023 [US1] Override `tracer_name` property in all 4 plugin classes (floe-secrets-infisical, floe-secrets-k8s, floe-identity-keycloak, floe-rbac-k8s)

**Checkpoint**: 4 security plugins instrumented with tests. Run `pytest plugins/floe-secrets-infisical/tests/unit/test_tracing.py plugins/floe-secrets-k8s/tests/unit/test_tracing.py plugins/floe-identity-keycloak/tests/unit/test_tracing.py plugins/floe-rbac-k8s/tests/unit/test_tracing.py -v`.

---

## Phase 4: US1 — Alert & Quality & Lineage Plugin Instrumentation (Tier 2)

**Goal**: Instrument 7 plugins — 4 alert, 2 quality, 1 lineage.

**Independent Test**: Same InMemorySpanExporter pattern per plugin.

### Tests for Phase 4

- [ ] T024 [P] [US5] Write tracing test for floe-alert-alertmanager in `plugins/floe-alert-alertmanager/tests/unit/test_tracing.py` — alert.channel attr, alert.destination attr, delivery status (FR-020, FR-021)
- [ ] T025 [P] [US5] Write tracing test for floe-alert-email in `plugins/floe-alert-email/tests/unit/test_tracing.py`
- [ ] T026 [P] [US5] Write tracing test for floe-alert-slack in `plugins/floe-alert-slack/tests/unit/test_tracing.py`
- [ ] T027 [P] [US5] Write tracing test for floe-alert-webhook in `plugins/floe-alert-webhook/tests/unit/test_tracing.py`
- [ ] T028 [P] [US5] Write tracing test for floe-quality-dbt in `plugins/floe-quality-dbt/tests/unit/test_tracing.py` — quality.check_name attr, quality.rows_checked attr (FR-020, FR-021)
- [ ] T029 [P] [US5] Write tracing test for floe-quality-gx in `plugins/floe-quality-gx/tests/unit/test_tracing.py`
- [ ] T030 [P] [US5] Write tracing test for floe-lineage-marquez in `plugins/floe-lineage-marquez/tests/unit/test_tracing.py` — lineage.job_name attr, lineage.event_type attr (FR-020, FR-021)

### Implementation for Phase 4

- [ ] T031 [P] [US1] Create `tracing.py` for floe-alert-alertmanager in `plugins/floe-alert-alertmanager/src/floe_alert_alertmanager/tracing.py` — `TRACER_NAME="floe.alert.alertmanager"`, `alert_span()` context manager, `ATTR_CHANNEL`, `ATTR_DESTINATION`, `ATTR_DELIVERY_STATUS` (FR-001, FR-018)
- [ ] T032 [P] [US1] Create `tracing.py` for floe-alert-email in `plugins/floe-alert-email/src/floe_alert_email/tracing.py` — `TRACER_NAME="floe.alert.email"`, same pattern (FR-001, FR-018)
- [ ] T033 [P] [US1] Create `tracing.py` for floe-alert-slack in `plugins/floe-alert-slack/src/floe_alert_slack/tracing.py` — `TRACER_NAME="floe.alert.slack"`, same pattern (FR-001, FR-018)
- [ ] T034 [P] [US1] Create `tracing.py` for floe-alert-webhook in `plugins/floe-alert-webhook/src/floe_alert_webhook/tracing.py` — `TRACER_NAME="floe.alert.webhook"`, same pattern (FR-001, FR-018)
- [ ] T035 [P] [US1] Create `tracing.py` for floe-quality-dbt — extract from `plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py` inline tracing into `plugins/floe-quality-dbt/src/floe_quality_dbt/tracing.py` with `TRACER_NAME="floe.quality.dbt"`, `quality_span()` context manager, `ATTR_CHECK_NAME`, `ATTR_ROWS_CHECKED`, `ATTR_PASS_COUNT` (FR-004, FR-018)
- [ ] T036 [P] [US1] Create `tracing.py` for floe-quality-gx — extract from `plugins/floe-quality-gx/src/floe_quality_gx/plugin.py` into `plugins/floe-quality-gx/src/floe_quality_gx/tracing.py` with `TRACER_NAME="floe.quality.gx"`, same pattern (FR-004, FR-018)
- [ ] T037 [P] [US1] Create `tracing.py` for floe-lineage-marquez in `plugins/floe-lineage-marquez/src/floe_lineage_marquez/tracing.py` — `TRACER_NAME="floe.lineage.marquez"`, `lineage_span()` context manager, `ATTR_JOB_NAME`, `ATTR_EVENT_TYPE` (FR-002, FR-018)
- [ ] T038 [US1] Wire `alert_span()` into all 4 alert plugin.py files — wrap `send_alert()` and `health_check()` in context managers
- [ ] T039 [US1] Wire `quality_span()` into floe-quality-dbt plugin.py and executor.py — wrap `run_checks()`, `parse_results()`
- [ ] T040 [US1] Wire `quality_span()` into floe-quality-gx plugin.py, executor.py, lineage.py
- [ ] T041 [US1] Wire `lineage_span()` into floe-lineage-marquez __init__.py — wrap `emit_run_event()`, `emit_dataset_event()`
- [ ] T042 [US1] Override `tracer_name` property in all 7 plugin classes

**Checkpoint**: 11 of 19 plugins instrumented (4 security + 7 from this phase). Run `pytest plugins/floe-alert-*/tests/unit/test_tracing.py plugins/floe-quality-*/tests/unit/test_tracing.py plugins/floe-lineage-marquez/tests/unit/test_tracing.py -v`.

---

## Phase 5: US1 — Compute, Orchestrator, Network, DBT-Fusion Plugin Instrumentation (Tier 3)

**Goal**: Instrument remaining 4 plugins (compute-duckdb, orchestrator-dagster, network-security-k8s, dbt-fusion).

**Independent Test**: Same InMemorySpanExporter pattern per plugin.

### Tests for Phase 5

- [ ] T043 [P] [US5] Write tracing test for floe-compute-duckdb in `plugins/floe-compute-duckdb/tests/unit/test_tracing.py` — compute.engine attr, compute.operation attr (FR-020, FR-021)
- [ ] T044 [P] [US5] Write tracing test for floe-orchestrator-dagster in `plugins/floe-orchestrator-dagster/tests/unit/test_tracing.py` — orchestrator.operation attr, orchestrator.asset_key attr (FR-020, FR-021)
- [ ] T045 [P] [US5] Write tracing test for floe-network-security-k8s in `plugins/floe-network-security-k8s/tests/unit/test_tracing.py` — security.policy_type attr, security.resource_count attr (FR-020, FR-021)
- [ ] T046 [P] [US5] Write tracing test for floe-dbt-fusion in `plugins/floe-dbt-fusion/tests/unit/test_tracing.py` — dbt_fusion.mode attr (core vs cloud), dbt_fusion.fallback attr (FR-020, FR-021)

### Implementation for Phase 5

- [ ] T047 [P] [US1] Create `tracing.py` for floe-compute-duckdb in `plugins/floe-compute-duckdb/src/floe_compute_duckdb/tracing.py` — `TRACER_NAME="floe.compute.duckdb"`, `compute_span()` context manager, `ATTR_ENGINE`, `ATTR_OPERATION` (FR-005, FR-018)
- [ ] T048 [P] [US1] Create `tracing.py` for floe-orchestrator-dagster in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/tracing.py` — `TRACER_NAME="floe.orchestrator.dagster"`, `orchestrator_span()` context manager, `ATTR_OPERATION`, `ATTR_ASSET_KEY` (FR-006, FR-018)
- [ ] T049 [P] [US1] Create `tracing.py` for floe-network-security-k8s in `plugins/floe-network-security-k8s/src/floe_network_security_k8s/tracing.py` — `TRACER_NAME="floe.security.network"`, `security_span()` context manager (FR-007, FR-018)
- [ ] T050 [P] [US1] Create `tracing.py` for floe-dbt-fusion in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/tracing.py` — `TRACER_NAME="floe.dbt.fusion"`, `dbt_fusion_span()` context manager, `ATTR_MODE`, `ATTR_FALLBACK` (FR-018)
- [ ] T051 [US1] Wire `compute_span()` into floe-compute-duckdb plugin.py — wrap `get_profiles()`, `validate_connection()`
- [ ] T052 [US1] Wire `orchestrator_span()` into floe-orchestrator-dagster plugin.py and assets/ — wrap `create_definitions()`, IO manager ops, `semantic_sync.py`
- [ ] T053 [US1] Wire `security_span()` into floe-network-security-k8s plugin.py — wrap `create_network_policy()`, `validate_policy()`
- [ ] T054 [US1] Wire `dbt_fusion_span()` into floe-dbt-fusion plugin.py, detection.py, fallback.py — wrap `compile()`, `run()`, `test()`
- [ ] T055 [US1] Override `tracer_name` property in all 4 plugin classes

**Checkpoint**: 15 of 19 plugins instrumented. Plus 4 already instrumented (polaris, dbt-core, semantic-cube, ingestion-dlt) = 19 total. Run `pytest plugins/floe-compute-duckdb/tests/unit/test_tracing.py plugins/floe-orchestrator-dagster/tests/unit/test_tracing.py plugins/floe-network-security-k8s/tests/unit/test_tracing.py plugins/floe-dbt-fusion/tests/unit/test_tracing.py -v`.

---

## Phase 6: US1/US3 — Already-Instrumented Plugin Updates + tracer_name

**Goal**: Add `tracer_name` override to the 4 already-instrumented plugins AND add sanitized error recording to their existing tracing modules. Wire existing plugins into the audit system.

- [ ] T056 [P] [US3] Override `tracer_name` in floe-catalog-polaris `PluginMetadata` — return `"floe.catalog.polaris"`
- [ ] T057 [P] [US3] Override `tracer_name` in floe-dbt-core `PluginMetadata` — return `"floe.dbt.core"`
- [ ] T058 [P] [US3] Override `tracer_name` in floe-semantic-cube `PluginMetadata` — return `"floe.semantic.cube"`
- [ ] T059 [P] [US3] Override `tracer_name` in floe-ingestion-dlt `PluginMetadata` — return `"floe.ingestion.dlt"`
- [ ] T060 [P] [US4] Update `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py` — use `sanitize_error_message()` from floe-core in error recording (FR-013)
- [ ] T061 [P] [US4] Update `plugins/floe-dbt-core/src/floe_dbt_core/tracing.py` — use `sanitize_error_message()` from floe-core
- [ ] T062 [P] [US4] Update `plugins/floe-semantic-cube/src/floe_semantic_cube/tracing.py` — use `sanitize_error_message()` from floe-core
- [ ] T063 [P] [US4] Update `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py` — use `sanitize_error_message()` for 2 raw `span.record_exception` calls

**Checkpoint**: All 19 instrumented plugins now have `tracer_name` and sanitized error recording.

---

## Phase 7: US4 — Sanitize Remaining Raw record_exception Calls

**Goal**: Replace all remaining raw `span.record_exception(e)` calls in core packages with sanitized error recording pattern.

- [ ] T064 [P] [US4] Sanitize error recording in `packages/floe-core/src/floe_core/telemetry/tracing.py` — `create_span()` error handling (3 call sites)
- [ ] T065 [P] [US4] Sanitize error recording in `packages/floe-core/src/floe_core/rbac/generator.py` (1 call site)
- [ ] T066 [P] [US4] Sanitize error recording in `packages/floe-core/src/floe_core/oci/verification.py`, `oci/metrics.py`, `oci/attestation.py` (6 call sites)
- [ ] T067 [P] [US4] Sanitize error recording in `packages/floe-iceberg/src/floe_iceberg/telemetry.py` (1 call site)
- [ ] T068 [P] [US4] Sanitize error recording in `packages/floe-iceberg/src/floe_iceberg/_compaction_manager.py` (1 call site)
- [ ] T069 [US4] Verify zero raw `span.record_exception` calls remain — run `rg "span\.record_exception" --type py -l | grep -v test | grep -v sanitization` and confirm empty output (SC-004)

**Checkpoint**: Zero raw `span.record_exception(e)` calls remain outside the sanitization utility.

---

## Phase 8: US3 — Instrumentation Audit in Compilation Pipeline

**Goal**: Create `verify_plugin_instrumentation()` and wire it into the ENFORCE stage of `compile_pipeline()`.

- [ ] T070 [US3] Write tests for instrumentation audit in `packages/floe-core/tests/unit/compilation/test_instrumentation_audit.py` — all plugins instrumented yields zero warnings, one uninstrumented yields warning with plugin name/type, telemetry backends skipped, audit callable programmatically (FR-016, FR-017)
- [ ] T071 [US3] Create `verify_plugin_instrumentation()` in `packages/floe-core/src/floe_core/telemetry/audit.py` — iterate plugins, check `tracer_name is not None`, skip telemetry backends by plugin type, return list of warning strings (FR-016)
- [ ] T072 [US3] Wire `verify_plugin_instrumentation()` into ENFORCE stage in `packages/floe-core/src/floe_core/compilation/stages.py` — call after sink whitelist validation, emit structured `logger.warning("uninstrumented_plugin", ...)` for each gap (FR-017)

**Checkpoint**: `floe compile` emits warnings for uninstrumented plugins. Run `pytest packages/floe-core/tests/unit/compilation/test_instrumentation_audit.py -v`.

---

## Phase 9: US5 — Contract Test, Benchmark, & Final Verification

**Goal**: Add cross-package contract test for instrumentation completeness and extend performance benchmarks. Final quality sweep.

### Contract Test

- [ ] T073 [US5] Write contract test in `tests/contract/test_plugin_instrumentation_contract.py` — load all registered plugins via entry points, assert 19 of 21 have non-None `tracer_name`, assert each tracer_name follows `"floe.{category}.{implementation}"` naming convention (FR-022, SC-001)

### Performance Benchmark

- [ ] T074 [US5] Extend `benchmarks/test_tracing_perf.py` — add benchmark for `@traced` with `attributes_fn` overhead, add benchmark comparing sanitized vs raw error recording, verify <5% overhead (FR-024, SC-006)

### Final Verification

- [ ] T075 Run full test suite — `pytest packages/floe-core/tests/unit/test_telemetry/ packages/floe-core/tests/unit/test_plugin_metadata_tracer.py packages/floe-core/tests/unit/compilation/test_instrumentation_audit.py plugins/*/tests/unit/test_tracing.py tests/contract/test_plugin_instrumentation_contract.py -v`
- [ ] T076 Type check all modified files — `mypy --strict packages/floe-core/src/floe_core/telemetry/ packages/floe-core/src/floe_core/plugin_metadata.py packages/floe-iceberg/src/floe_iceberg/telemetry.py`
- [ ] T077 Lint check — `ruff check packages/floe-core/src/ plugins/*/src/`
- [ ] T078 Verify zero raw `span.record_exception` outside sanitization — `rg "span\.record_exception" --type py -l | grep -v test | grep -v sanitization` (SC-004)
- [ ] T079 Verify all plugins have tracer_name — `pytest tests/contract/test_plugin_instrumentation_contract.py -v` (SC-001)
- [ ] T080 Run performance benchmark — `pytest benchmarks/test_tracing_perf.py -v --benchmark-only` (SC-006)
- [ ] T081 Full regression — `make test-unit` (SC-002, SC-007)

**Checkpoint**: All success criteria verified. Epic 6C complete.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Error Sanitization)          ← BLOCKS everything
  ├──► Phase 2 (Unified @traced + PluginMetadata)  [US2+US3 in parallel]
  │       ├──► Phase 3 (Security plugins)
  │       │       ├──► Phase 4 (Alert/Quality/Lineage plugins)
  │       │       │       └──► Phase 5 (Compute/Orchestrator/Network/DBT-Fusion)
  │       │       └──► Phase 6 (Existing plugin updates)
  │       └──► Phase 7 (Raw record_exception sanitization)
  └──► Phase 6 (can start after Phase 1 for sanitization work)

Phase 2 US3 (PluginMetadata tracer_name) ──► Phase 8 (Audit)
Phase 5 + Phase 6 ──► Phase 8 (All plugins must have tracer_name)
All Phases ──► Phase 9 (Final verification)
```

### User Story Dependencies

- **US4** (Error Sanitization, P2): Foundation — start first despite P2 priority because US1/US2/US5 depend on it
- **US2** (Unified @traced, P1): Depends on US4 completion
- **US3** (Audit, P1): PluginMetadata change is independent; wiring depends on US1 completing
- **US1** (Plugin Spans, P0): Depends on US4 (sanitization utility); each plugin tier is independent
- **US5** (Tests, P0): Tests written alongside implementations in Phases 3-5; contract test in Phase 9

### Within Each Plugin Phase

1. Write test FIRST (fails initially)
2. Create tracing.py module (all [P] within phase)
3. Wire into plugin.py
4. Override tracer_name
5. Tests pass

### Parallel Opportunities

**Phase 2**: T005-T008 (US2) can run in parallel with T009-T010 (US3)
**Phase 3**: All 4 tracing.py files (T015-T018) can be created in parallel; all 4 tests (T011-T014) in parallel
**Phase 4**: All 7 tracing.py files (T031-T037) in parallel; all 7 tests (T024-T030) in parallel
**Phase 5**: All 4 tracing.py files (T047-T050) in parallel; all 4 tests (T043-T046) in parallel
**Phase 6**: All 8 tasks (T056-T063) in parallel
**Phase 7**: All 5 sanitization tasks (T064-T068) in parallel

---

## Parallel Example: Phase 3 (Security Plugins)

```bash
# Launch all tests in parallel:
Task: "Write tracing test for floe-secrets-infisical" (T011)
Task: "Write tracing test for floe-secrets-k8s" (T012)
Task: "Write tracing test for floe-identity-keycloak" (T013)
Task: "Write tracing test for floe-rbac-k8s" (T014)

# Launch all tracing.py modules in parallel:
Task: "Create tracing.py for floe-secrets-infisical" (T015)
Task: "Create tracing.py for floe-secrets-k8s" (T016)
Task: "Create tracing.py for floe-identity-keycloak" (T017)
Task: "Create tracing.py for floe-rbac-k8s" (T018)
```

---

## Implementation Strategy

### Foundation First

1. Complete Phase 1: Error sanitization utility (4 tasks)
2. Complete Phase 2: Unified @traced + PluginMetadata (6 tasks, 2 parallel workstreams)
3. **VALIDATE**: Core infrastructure ready — run unified decorator tests and metadata tests

### Plugin Instrumentation by Priority Tier

4. Complete Phase 3: Security plugins (13 tasks) — highest audit value
5. Complete Phase 4: Alert/Quality/Lineage plugins (19 tasks) — broadest coverage
6. Complete Phase 5: Compute/Orchestrator/Network/DBT-Fusion plugins (13 tasks) — remaining
7. Complete Phase 6: Existing plugin updates (8 tasks, all parallel)

### Sanitization + Audit + Verification

8. Complete Phase 7: Raw record_exception sanitization (6 tasks)
9. Complete Phase 8: Instrumentation audit in compile pipeline (3 tasks)
10. Complete Phase 9: Contract test + benchmark + final verification (9 tasks)

### Incremental Checkpoints

Each phase produces independently verifiable output:
- Phase 1: `sanitize_error_message()` in floe-core ✓
- Phase 2: Unified `@traced` + `tracer_name` property ✓
- Phase 3: 4 security plugins instrumented ✓
- Phase 4: +7 plugins instrumented (11 new total) ✓
- Phase 5: +4 plugins instrumented (15 new total) ✓
- Phase 6: +4 existing plugins updated (19 total) ✓
- Phase 7: Zero raw exception recording ✓
- Phase 8: Audit wired into compilation ✓
- Phase 9: All success criteria verified ✓

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to user story for requirement traceability
- Each plugin tracing.py follows the canonical pattern from floe-catalog-polaris (R2 in plan)
- Telemetry backends (console, jaeger) are excluded from instrumentation — infinite loop risk
- Tests use InMemorySpanExporter pattern (R8 in plan)
- All error recording uses sanitize_error_message() (FR-013, FR-014)
- 81 total tasks across 9 phases
