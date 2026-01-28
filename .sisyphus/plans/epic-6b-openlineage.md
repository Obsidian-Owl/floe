# Epic 6B: OpenLineage Integration

## TL;DR

> **Quick Summary**: Build a portable, non-blocking OpenLineage lineage subsystem in floe-core with catalog-aware dataset identity, unified emission across orchestrator/quality plugins, dbt manifest extraction, and Marquez backend support. Fix 6 architectural issues in existing plugin ABCs.
> 
> **Deliverables**:
> - Core lineage module (`floe_core/lineage/`) with emitter, events, facets, transport, extractors
> - Upgraded `OrchestratorPlugin.emit_lineage_event()` ABC (portable across Dagster/Airflow/Prefect)
> - Unified lineage emission replacing 3 competing interfaces
> - Catalog-integrated dataset identity (namespace from catalog URI, Iceberg facets)
> - dbt manifest → OpenLineage extractor
> - Dagster plugin wiring fixes (resources + lineage emission in `_asset_fn`)
> - Marquez backend plugin implementation
> - `ResolvedPlugins` schema update (v0.5.0) with `lineage_backend`
> - Full test suite (unit, contract, integration)
> 
> **Estimated Effort**: Large (15 tasks, ~8-10 days with parallelization)
> **Parallel Execution**: YES — 5 waves
> **Critical Path**: Task 1 → Task 3 → Task 5 → Task 8 → Task 12 → Task 15

---

## Context

### Original Request
Comprehensive implementation plan for Epic 6B: OpenLineage Integration — portable lineage across orchestrators, catalog-integrated dataset identity, fix existing ABC issues, full build/test/integration.

### Architectural Issues Identified (all verified in source)
1. **OrchestratorPlugin.emit_lineage_event() too thin** — no run_id, no RunState enum, no facets, no producer (orchestrator.py:317-345)
2. **QualityPlugin has duplicate lineage abstraction** — `OpenLineageEmitter` Protocol in quality.py:53-73 duplicates lineage concerns
3. **Dagster _asset_fn doesn't emit lineage** — calls dbt.run_models() only, never emit_lineage_event()
4. **create_definitions() doesn't wire resources** — returns Definitions(assets=assets) with no resources dict
5. **No catalog-aware dataset identity** — namespace hardcoded as "floe" instead of catalog URI
6. **ResolvedPlugins missing lineage_backend** — confirmed at compiled_artifacts.py:173-226, no lineage_backend field

### Enforced Standards
- OpenLineage ENFORCED (ADR-0007) — all pipelines MUST emit
- Non-blocking emission (REQ-525/526) — FORBIDDEN to block pipeline
- K8s-native (ADR-0016)
- Pydantic v2 frozen models, entry points

### Deferred (explicitly OUT of scope)
- Column-level lineage (SQL parsing)
- dlt ingestion lineage extractors
- Kafka transport
- OTLP transport bridge
- Airflow/Prefect concrete plugins (ABCs designed for them, implementations deferred)

---

## Integration Design

### Entry Point Integration
- [ ] Feature reachable from: Plugin system (entry points `floe.lineage_backends`)
- [ ] Integration point: `floe_core/lineage/__init__.py` exports `LineageEmitter`, `EventBuilder`, `FacetBuilder`
- [ ] Wiring task needed: YES — Task 8 (Dagster), Task 10 (compilation enforcement)

### Dependency Integration
| This Feature Uses | From Package | Integration Point |
|-------------------|--------------|-------------------|
| OpenLineage SDK | openlineage-python>=1.5.0 | `from openlineage.client` |
| CatalogPlugin | floe-core | `catalog.connect()` → namespace URI |
| IcebergTableManager | floe-iceberg | `list_snapshots()` for snapshot facets |
| CompiledArtifacts | floe-core | `ResolvedPlugins.lineage_backend` |
| dbt manifest | floe-core | `compilation/loader.py` parsed dict |
| OTel tracing | floe-core | `telemetry/tracing.py` for trace_id correlation |

### Produces for Others
| Output | Consumers | Contract |
|--------|-----------|----------|
| `LineageEmitter` | OrchestratorPlugin impls | Python Protocol |
| `LineageBackendPlugin` | Marquez, Atlan, OpenMetadata plugins | ABC (existing) |
| `ResolvedPlugins.lineage_backend` | Compilation, runtime | Pydantic v0.5.0 |
| Custom facets | Lineage backends | OpenLineage facet schema |

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest, bun test in packages)
- **User wants tests**: TDD where possible, integration tests with Kind + Marquez
- **Framework**: pytest with `@pytest.mark.requirement("REQ-XXX")` traceability

---

## Task Dependency Graph

| Task | Depends On | Reason | Blocks |
|------|------------|--------|--------|
| 1 | None | Foundation types, no prerequisites | 2, 3, 4, 5, 6, 7 |
| 2 | 1 | Transport uses types from Task 1 | 7, 8 |
| 3 | 1 | Event builder uses types from Task 1 | 5, 7, 8 |
| 4 | 1 | Facet builders use types from Task 1 | 5, 6, 7 |
| 5 | 3, 4 | dbt extractor builds events with facets | 8, 12 |
| 6 | 4 | Catalog facets use facet builders | 8, 12 |
| 7 | 2, 3, 4 | Emitter composes transport + events + facets | 8, 9, 12 |
| 8 | 5, 6, 7 | ABC upgrade needs new types; Dagster wiring needs emitter | 12, 13 |
| 9 | 7 | Marquez plugin uses emitter transport config | 12 |
| 10 | 1 | Schema change uses lineage types | 11, 12 |
| 11 | 10 | Contract tests verify schema changes | 12 |
| 12 | 8, 9, 10, 11 | Integration test needs all components | 15 |
| 13 | 8 | Quality unification refactors quality.py after ABC upgrade | 14 |
| 14 | 13 | Quality contract tests verify refactor | 15 |
| 15 | 12, 14 | Final validation of everything | None |

## Parallel Execution Graph

```
Wave 1 (Start immediately):
├── Task 1:  Core lineage types & protocols (foundation)
└── Task 10: ResolvedPlugins schema + lineage_backend field

Wave 2 (After Wave 1):
├── Task 2:  Transport abstraction (async HTTP, composite)
├── Task 3:  Event builder (RunEvent construction)
├── Task 4:  Facet builders (schema, statistics, quality, custom)
└── Task 11: CompiledArtifacts contract tests (schema v0.5.0)

Wave 3 (After Wave 2):
├── Task 5:  dbt manifest extractor
├── Task 6:  Catalog-aware dataset identity + Iceberg facets
├── Task 7:  LineageEmitter (composes transport + events + facets)
└── Task 9:  Marquez backend plugin

Wave 4 (After Wave 3):
├── Task 8:  ABC upgrade + Dagster wiring fixes
└── Task 13: QualityPlugin lineage unification

Wave 5 (After Wave 4):
├── Task 12: Integration tests (Kind + Marquez)
├── Task 14: Quality contract tests
└── Task 15: Final validation & documentation

Critical Path: Task 1 → Task 3 → Task 7 → Task 8 → Task 12 → Task 15
Estimated Parallel Speedup: ~45% faster than sequential
```

---

## TODOs

### Task 1: Core Lineage Types & Protocols

**What to do**:
- Create `packages/floe-core/src/floe_core/lineage/__init__.py` — public exports
- Create `packages/floe-core/src/floe_core/lineage/types.py`:
  - `RunState` enum: `START`, `RUNNING`, `COMPLETE`, `ABORT`, `FAIL`, `OTHER`
  - `LineageDataset` (Pydantic, frozen): `namespace: str`, `name: str`, `facets: dict[str, Any]` — replaces the dataclass `Dataset` in orchestrator.py
  - `LineageRun`: `run_id: UUID`, `facets: dict[str, Any]`
  - `LineageJob`: `namespace: str`, `name: str`, `facets: dict[str, Any]`
  - `LineageEvent`: `event_type: RunState`, `event_time: datetime`, `run: LineageRun`, `job: LineageJob`, `inputs: list[LineageDataset]`, `outputs: list[LineageDataset]`, `producer: str`
- Create `packages/floe-core/src/floe_core/lineage/protocols.py`:
  - `LineageTransport` Protocol: `async def emit(self, event: LineageEvent) -> None`, `def close(self) -> None`
  - `LineageExtractor` Protocol: `def extract(self, context: Any) -> tuple[list[LineageDataset], list[LineageDataset]]`
- Unit tests: `packages/floe-core/tests/lineage/test_types.py`
  - Test RunState enum values match OpenLineage spec
  - Test LineageDataset/Event Pydantic serialization roundtrip
  - Test frozen immutability

**Must NOT do**:
- Do NOT import openlineage SDK here — these are floe's portable types
- Do NOT remove the existing `Dataset` dataclass from orchestrator.py yet (Task 8 handles migration)

**Recommended Agent Profile**:
- **Category**: `unspecified-low` — straightforward Pydantic models + enums
  - Reason: Well-scoped type definitions, no complex logic
- **Skills**: [`python-programmer`, `pydantic-schemas`]
  - `python-programmer`: Production Python with type hints
  - `pydantic-schemas`: v2 frozen model patterns, Field usage
- **Skills Evaluated but Omitted**:
  - `testing`: Not needed — simple unit tests inline
  - `dagster-orchestration`: No Dagster involvement

**Parallelization**:
- **Can Run In Parallel**: YES (with Task 10)
- **Parallel Group**: Wave 1
- **Blocks**: Tasks 2, 3, 4, 5, 6, 7
- **Blocked By**: None

**References**:
- `packages/floe-core/src/floe_core/plugins/orchestrator.py:105-128` — existing `Dataset` dataclass to supersede
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:173-226` — Pydantic v2 frozen model pattern to follow (`model_config = ConfigDict(frozen=True, extra="forbid")`)
- `packages/floe-core/src/floe_core/plugins/quality.py:52-73` — existing `OpenLineageEmitter` Protocol to eventually replace
- OpenLineage spec: RunState values are START, RUNNING, COMPLETE, ABORT, FAIL, OTHER
- `packages/floe-core/src/floe_core/telemetry/config.py` — similar Pydantic config pattern in same codebase

**Acceptance Criteria**:
- [ ] `RunState` enum has all 6 values matching OpenLineage spec
- [ ] `LineageDataset`, `LineageEvent` round-trip through JSON serialization
- [ ] All models are frozen (assignment raises error)
- [ ] `pytest packages/floe-core/tests/lineage/test_types.py` → PASS
- [ ] `@pytest.mark.requirement("REQ-516")` on event type tests

**Commit**: YES
- Message: `feat(lineage): add core lineage types and protocols`
- Files: `packages/floe-core/src/floe_core/lineage/{__init__,types,protocols}.py`, `packages/floe-core/tests/lineage/test_types.py`

---

### Task 2: Transport Abstraction (Non-Blocking HTTP)

**What to do**:
- Create `packages/floe-core/src/floe_core/lineage/transport.py`:
  - `HttpLineageTransport` implementing `LineageTransport` Protocol:
    - Wraps `openlineage.client.transport.HttpTransport` (or `AsyncHttpTransport` if available)
    - Constructor: `url: str`, `timeout: float = 5.0`, `api_key: str | None = None`
    - `async def emit()` — non-blocking, fire-and-forget with asyncio queue
    - `def close()` — drain queue, close connections
  - `ConsoleLineageTransport` — logs events to structlog, for dev/debug
  - `CompositeLineageTransport` — fans out to multiple transports
  - `NoOpLineageTransport` — silent discard, for testing
- Non-blocking guarantee: use `asyncio.Queue` with background consumer task, emit() is enqueue-only
- If async context not available (sync orchestrator), use `threading.Thread` with `queue.Queue`
- Unit tests: `packages/floe-core/tests/lineage/test_transport.py`
  - Test NoOp transport accepts events without error
  - Test Console transport logs via structlog mock
  - Test Composite fans out to N transports
  - Test HTTP transport doesn't block caller (timing test with slow mock server)

**Must NOT do**:
- Do NOT implement Kafka transport (deferred)
- Do NOT make HTTP transport synchronous — REQ-525/526 FORBIDS blocking pipeline
- Do NOT hardcode Marquez URL — transport is configured from LineageBackendPlugin

**Recommended Agent Profile**:
- **Category**: `unspecified-high` — async/threading complexity needs careful implementation
  - Reason: Non-blocking guarantee requires async queue patterns
- **Skills**: [`python-programmer`]
  - `python-programmer`: Async patterns, threading, production Python
- **Skills Evaluated but Omitted**:
  - `pydantic-schemas`: No Pydantic models in transport layer
  - `dagster-orchestration`: No Dagster involvement

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 3, 4)
- **Parallel Group**: Wave 2
- **Blocks**: Tasks 7, 8
- **Blocked By**: Task 1

**References**:
- `packages/floe-core/src/floe_core/lineage/types.py` (Task 1) — `LineageTransport` Protocol, `LineageEvent` type
- `packages/floe-core/src/floe_core/telemetry/provider.py` — similar async provider pattern in codebase
- OpenLineage Python SDK: `openlineage.client.transport.HttpTransport` — wrap, don't reimplement
- REQ-525: "HTTP transport MUST be non-blocking"
- REQ-526: "Lineage emission FORBIDDEN to block pipeline execution"

**Acceptance Criteria**:
- [ ] `HttpLineageTransport.emit()` returns in <1ms (enqueue only)
- [ ] Background consumer actually sends to HTTP endpoint (mock test)
- [ ] `CompositeTransport` fans out to 3 sub-transports in test
- [ ] `pytest packages/floe-core/tests/lineage/test_transport.py` → PASS
- [ ] `@pytest.mark.requirement("REQ-525")` on non-blocking test
- [ ] `@pytest.mark.requirement("REQ-526")` on fire-and-forget test

**Commit**: YES
- Message: `feat(lineage): add non-blocking transport abstraction`
- Files: `packages/floe-core/src/floe_core/lineage/transport.py`, tests

---

### Task 3: Event Builder

**What to do**:
- Create `packages/floe-core/src/floe_core/lineage/events.py`:
  - `EventBuilder` class:
    - `__init__(producer: str, default_namespace: str)`
    - `start_run(job_name: str, job_namespace: str | None, run_id: UUID | None, inputs, outputs, run_facets, job_facets) -> LineageEvent`
    - `complete_run(run_id: UUID, job_name: str, ...) -> LineageEvent`
    - `fail_run(run_id: UUID, job_name: str, error_message: str | None, ...) -> LineageEvent`
  - Converts floe `LineageEvent` → OpenLineage SDK `RunEvent` for transport
  - `to_openlineage_event(event: LineageEvent) -> dict` — serialization to OL wire format
- Unit tests: `packages/floe-core/tests/lineage/test_events.py`
  - Test START event has correct structure
  - Test COMPLETE event preserves run_id from START
  - Test FAIL event includes ErrorMessageRunFacet
  - Test producer field set correctly

**Must NOT do**:
- Do NOT include dbt-specific logic (that's Task 5)
- Do NOT include facet construction (that's Task 4)

**Recommended Agent Profile**:
- **Category**: `unspecified-low` — builder pattern, straightforward
  - Reason: Clear mapping from floe types to OL SDK types
- **Skills**: [`python-programmer`]
  - `python-programmer`: Builder pattern, UUID handling
- **Skills Evaluated but Omitted**:
  - `pydantic-schemas`: Events are constructed, not validated from user input

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 2, 4)
- **Parallel Group**: Wave 2
- **Blocks**: Tasks 5, 7, 8
- **Blocked By**: Task 1

**References**:
- `packages/floe-core/src/floe_core/lineage/types.py` (Task 1) — `LineageEvent`, `RunState`, `LineageJob`, `LineageRun`
- OpenLineage spec: `RunEvent(eventType, eventTime, run, job, producer, inputs, outputs)`
- OpenLineage Python SDK: `from openlineage.client.event_v2 import RunEvent, Run, Job`

**Acceptance Criteria**:
- [ ] `EventBuilder.start_run()` produces valid LineageEvent with RunState.START
- [ ] `to_openlineage_event()` output matches OpenLineage JSON schema structure
- [ ] run_id is auto-generated UUID4 if not provided
- [ ] `pytest packages/floe-core/tests/lineage/test_events.py` → PASS
- [ ] `@pytest.mark.requirement("REQ-516")` on event emission tests
- [ ] `@pytest.mark.requirement("REQ-518")` on job identity tests

**Commit**: YES
- Message: `feat(lineage): add event builder for RunEvent construction`
- Files: `packages/floe-core/src/floe_core/lineage/events.py`, tests

---

### Task 4: Facet Builders

**What to do**:
- Create `packages/floe-core/src/floe_core/lineage/facets.py`:
  - `SchemaFacetBuilder`: Build `SchemaDatasetFacet` from column definitions
    - `from_columns(columns: list[dict]) -> dict` — takes `[{"name": "id", "type": "INTEGER"}]`
    - `from_iceberg_schema(schema: IcebergSchema) -> dict` — converts PyIceberg schema
  - `StatisticsFacetBuilder`: Build `OutputStatisticsOutputDatasetFacet`
    - `from_snapshot(snapshot: SnapshotInfo) -> dict` — uses added_records, added_files
  - `QualityFacetBuilder`: Build `DataQualityAssertionsDatasetFacet`
    - `from_check_results(results: list[QualityCheckResult]) -> dict`
  - `TraceCorrelationFacetBuilder`: Build custom `TraceCorrelationRunFacet`
    - `from_otel_context() -> dict` — extracts trace_id, span_id from current OTel context
  - `ParentRunFacetBuilder`: Build `ParentRunFacet`
    - `from_parent(parent_run_id: UUID, parent_job: str, parent_namespace: str) -> dict`
  - `SQLJobFacetBuilder`: Build `SQLJobFacet`
    - `from_query(sql: str) -> dict`
  - `IcebergSnapshotFacetBuilder`: Custom facet
    - `from_snapshot(snapshot: SnapshotInfo) -> dict` — snapshot_id, timestamp, operation
- Register custom facets with `_schemaURL` following OL custom facet spec
- Unit tests: `packages/floe-core/tests/lineage/test_facets.py`
  - Test schema facet from column list
  - Test statistics facet from mock SnapshotInfo
  - Test quality facet from QualityCheckResult
  - Test trace correlation extracts OTel context
  - Test custom facet _schemaURL format

**Must NOT do**:
- Do NOT implement column-level lineage facets (deferred)
- Do NOT import Dagster or Airflow — facets are orchestrator-agnostic

**Recommended Agent Profile**:
- **Category**: `unspecified-low` — data mapping, no complex logic
  - Reason: Straightforward dict construction from typed inputs
- **Skills**: [`python-programmer`, `pydantic-schemas`]
  - `python-programmer`: Dict construction, typing
  - `pydantic-schemas`: QualityCheckResult schema understanding
- **Skills Evaluated but Omitted**:
  - `dagster-orchestration`: Facets are orchestrator-agnostic
  - `dbt-transformations`: dbt-specific extraction is Task 5

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 2, 3)
- **Parallel Group**: Wave 2
- **Blocks**: Tasks 5, 6, 7
- **Blocked By**: Task 1

**References**:
- `packages/floe-core/src/floe_core/schemas/quality_score.py` — `QualityCheckResult` schema for quality facets
- `packages/floe-core/src/floe_core/telemetry/tracing.py` — OTel context extraction pattern
- `packages/floe-core/src/floe_core/lineage/types.py` (Task 1) — `LineageDataset` facets dict
- OpenLineage spec: SchemaDatasetFacet fields = `[{name, type, description}]`
- OpenLineage custom facet: `_schemaURL: "https://floe.dev/lineage/facets/v1/IcebergSnapshotFacet.json"`
- REQ-521: trace_id in lineage events
- REQ-529: custom facets
- REQ-531: Iceberg dataset facets

**Acceptance Criteria**:
- [ ] `SchemaFacetBuilder.from_columns()` produces valid SchemaDatasetFacet dict
- [ ] `TraceCorrelationFacetBuilder.from_otel_context()` extracts real trace_id when OTel active
- [ ] All custom facets have `_schemaURL` field
- [ ] `pytest packages/floe-core/tests/lineage/test_facets.py` → PASS
- [ ] `@pytest.mark.requirement("REQ-521")` on trace correlation test
- [ ] `@pytest.mark.requirement("REQ-529")` on custom facet test
- [ ] `@pytest.mark.requirement("REQ-531")` on Iceberg facet test

**Commit**: YES
- Message: `feat(lineage): add facet builders for schema, statistics, quality, trace`
- Files: `packages/floe-core/src/floe_core/lineage/facets.py`, tests

---

### Task 5: dbt Manifest Extractor

**What to do**:
- Create `packages/floe-core/src/floe_core/lineage/extractors/__init__.py`
- Create `packages/floe-core/src/floe_core/lineage/extractors/dbt.py`:
  - `DbtLineageExtractor` implementing `LineageExtractor` Protocol:
    - `__init__(manifest: dict, default_namespace: str, schema_facet_builder: SchemaFacetBuilder)`
    - `extract_model(node_uid: str) -> tuple[list[LineageDataset], list[LineageDataset]]`
      - Inputs: from `manifest["parent_map"][node_uid]` or `nodes[uid]["depends_on"]["nodes"]`
      - Output: the model itself as LineageDataset
      - Dataset name: `{database}.{schema}.{alias or name}` per OL dbt convention
    - `extract_test(node_uid: str) -> list[LineageDataset]` — datasets tested
    - `build_schema_facet(node_uid: str) -> dict` — from `nodes[uid]["columns"]`
    - `extract_all_models() -> dict[str, tuple[list[LineageDataset], list[LineageDataset]]]`
  - Handle missing columns gracefully (dbt columns often lack types)
- Unit tests: `packages/floe-core/tests/lineage/extractors/test_dbt.py`
  - Test with real-ish manifest fixture (3 models: source → staging → mart)
  - Test parent_map extraction produces correct inputs
  - Test dataset naming: `{db}.{schema}.{name}`
  - Test model with no columns produces empty schema facet
  - Test test node extraction

**Must NOT do**:
- Do NOT parse SQL for column lineage (deferred)
- Do NOT import dbt packages — manifest is already a parsed dict
- Do NOT create dbt runner — this only reads manifest

**Recommended Agent Profile**:
- **Category**: `unspecified-low` — dict traversal, clear mapping
  - Reason: Well-documented manifest structure, straightforward extraction
- **Skills**: [`python-programmer`, `dbt-transformations`]
  - `python-programmer`: Dict traversal, dataclass construction
  - `dbt-transformations`: Manifest structure knowledge (parent_map, nodes, depends_on)
- **Skills Evaluated but Omitted**:
  - `dagster-orchestration`: No Dagster involvement in extraction

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 6, 7, 9)
- **Parallel Group**: Wave 3
- **Blocks**: Task 8
- **Blocked By**: Tasks 3, 4

**References**:
- `packages/floe-core/src/floe_core/compilation/dbt_test_mapper.py` — existing dbt manifest traversal pattern (maps dbt tests → QualityCheck)
- `packages/floe-core/src/floe_core/compilation/loader.py` — how manifest is loaded as raw dict
- `packages/floe-core/src/floe_core/lineage/facets.py` (Task 4) — `SchemaFacetBuilder`
- `packages/floe-core/src/floe_core/lineage/types.py` (Task 1) — `LineageDataset`
- dbt manifest: `nodes[uid]["depends_on"]["nodes"]`, `nodes[uid]["columns"]`, `nodes[uid]["database"]`, `nodes[uid]["schema"]`, `nodes[uid]["alias"]`
- REQ-522: dbt model lineage integration

**Acceptance Criteria**:
- [ ] 3-model manifest fixture produces correct lineage graph (source→staging→mart)
- [ ] Dataset names follow `{database}.{schema}.{name}` convention
- [ ] Models with no columns produce datasets with empty schema facet (not error)
- [ ] `pytest packages/floe-core/tests/lineage/extractors/test_dbt.py` → PASS
- [ ] `@pytest.mark.requirement("REQ-522")` on extraction tests
- [ ] `@pytest.mark.requirement("REQ-519")` on input dataset tests

**Commit**: YES
- Message: `feat(lineage): add dbt manifest lineage extractor`
- Files: `packages/floe-core/src/floe_core/lineage/extractors/{__init__,dbt}.py`, tests

---

### Task 6: Catalog-Aware Dataset Identity & Iceberg Facets

**What to do**:
- Create `packages/floe-core/src/floe_core/lineage/catalog_integration.py`:
  - `CatalogDatasetResolver`:
    - `__init__(catalog_plugin: CatalogPlugin | None, default_namespace: str)`
    - `resolve_namespace() -> str` — returns catalog URI (e.g., `polaris://catalog.example.com/warehouse`) or falls back to default_namespace
    - `resolve_dataset(table_name: str) -> LineageDataset` — loads table from catalog, builds dataset with schema facet from Iceberg schema
    - `enrich_with_snapshot(dataset: LineageDataset, table_name: str) -> LineageDataset` — adds IcebergSnapshotFacet from latest snapshot
  - Namespace strategy per REQ-517:
    - `SimpleNamespaceStrategy`: single static namespace
    - `CentralizedNamespaceStrategy`: `{env}.{platform}` pattern
    - `DataMeshNamespaceStrategy`: `{domain}.{product_name}` pattern (ADR-0038)
  - `NamespaceResolver`:
    - `__init__(strategy: str, catalog_plugin: CatalogPlugin | None, config: ObservabilityConfig)`
    - `resolve_job_namespace() -> str` — producer identity
    - `resolve_dataset_namespace(table_identifier: str) -> str` — data source identity
- Unit tests: `packages/floe-core/tests/lineage/test_catalog_integration.py`
  - Test namespace from mock catalog plugin URI
  - Test fallback when no catalog plugin
  - Test data mesh namespace pattern
  - Test Iceberg schema → SchemaDatasetFacet conversion
  - Test snapshot enrichment

**Must NOT do**:
- Do NOT require catalog plugin at runtime — graceful degradation to default namespace
- Do NOT call catalog during pipeline execution path (only during planning/init phase)

**Recommended Agent Profile**:
- **Category**: `unspecified-low` — integration plumbing with clear interfaces
  - Reason: Orchestrating existing plugins, not complex logic
- **Skills**: [`python-programmer`, `pyiceberg-storage`, `polaris-catalog`]
  - `python-programmer`: Integration code
  - `pyiceberg-storage`: Iceberg schema/snapshot API knowledge
  - `polaris-catalog`: Catalog URI patterns, namespace conventions
- **Skills Evaluated but Omitted**:
  - `dbt-transformations`: No dbt involvement here

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 5, 7, 9)
- **Parallel Group**: Wave 3
- **Blocks**: Task 8
- **Blocked By**: Task 4

**References**:
- `packages/floe-core/src/floe_core/plugins/catalog.py` — CatalogPlugin ABC, `connect()`, `load_table()`
- `packages/floe-core/src/floe_core/lineage/facets.py` (Task 4) — `SchemaFacetBuilder.from_iceberg_schema()`, `IcebergSnapshotFacetBuilder`
- `packages/floe-core/src/floe_core/lineage/types.py` (Task 1) — `LineageDataset`
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` — `ObservabilityConfig` has `lineage_namespace`
- OpenLineage spec: dataset namespace = data SOURCE (e.g., `polaris://host/warehouse`), job namespace = producer
- REQ-517: Namespace strategy (Simple/Centralized/Data Mesh)
- REQ-528: Namespace validation
- REQ-531: Iceberg dataset facets

**Acceptance Criteria**:
- [ ] Catalog URI correctly becomes dataset namespace (`polaris://...`)
- [ ] No-catalog fallback produces `ObservabilityConfig.lineage_namespace` value
- [ ] DataMesh strategy produces `{domain}.{product}` namespace
- [ ] Iceberg schema converts to SchemaDatasetFacet with correct field types
- [ ] `pytest packages/floe-core/tests/lineage/test_catalog_integration.py` → PASS
- [ ] `@pytest.mark.requirement("REQ-517")` on namespace strategy tests
- [ ] `@pytest.mark.requirement("REQ-531")` on Iceberg facet tests

**Commit**: YES
- Message: `feat(lineage): add catalog-aware dataset identity and Iceberg facets`
- Files: `packages/floe-core/src/floe_core/lineage/catalog_integration.py`, tests

---

### Task 7: LineageEmitter (Composition Root)

**What to do**:
- Create `packages/floe-core/src/floe_core/lineage/emitter.py`:
  - `LineageEmitter` class (the unified interface — replaces 3 competing ones):
    - `__init__(transport: LineageTransport, event_builder: EventBuilder, namespace_resolver: NamespaceResolver)`
    - `emit_start(job_name: str, run_id: UUID | None, inputs, outputs, run_facets, job_facets) -> UUID` — returns run_id
    - `emit_complete(run_id: UUID, job_name: str, outputs, output_facets) -> None`
    - `emit_fail(run_id: UUID, job_name: str, error_message: str | None, run_facets) -> None`
    - Non-blocking: delegates to transport.emit()
    - Thread-safe: can be called from any orchestrator context
  - `create_emitter(backend_plugin: LineageBackendPlugin, catalog_plugin: CatalogPlugin | None, config: ObservabilityConfig) -> LineageEmitter` — factory function
  - Update `packages/floe-core/src/floe_core/lineage/__init__.py` — export `LineageEmitter`, `create_emitter`
- Unit tests: `packages/floe-core/tests/lineage/test_emitter.py`
  - Test emit_start returns UUID, event sent to transport
  - Test emit_complete uses same run_id
  - Test emit_fail includes error facet
  - Test factory wires transport from backend plugin config
  - Test without catalog plugin (graceful degradation)

**Must NOT do**:
- Do NOT make emitter orchestrator-specific — it's the portable layer
- Do NOT include synchronous emission path
- Do NOT import Dagster/Airflow

**Recommended Agent Profile**:
- **Category**: `unspecified-high` — composition root tying everything together
  - Reason: Must correctly compose transport, events, facets, namespace resolution
- **Skills**: [`python-programmer`]
  - `python-programmer`: Composition patterns, factory functions, thread safety
- **Skills Evaluated but Omitted**:
  - `dagster-orchestration`: Emitter is orchestrator-agnostic
  - `pydantic-schemas`: No new schemas

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 5, 6, 9)
- **Parallel Group**: Wave 3
- **Blocks**: Tasks 8, 9, 12
- **Blocked By**: Tasks 2, 3, 4

**References**:
- `packages/floe-core/src/floe_core/lineage/transport.py` (Task 2) — `LineageTransport`
- `packages/floe-core/src/floe_core/lineage/events.py` (Task 3) — `EventBuilder`
- `packages/floe-core/src/floe_core/lineage/catalog_integration.py` (Task 6) — `NamespaceResolver`
- `packages/floe-core/src/floe_core/lineage/types.py` (Task 1) — all types
- `packages/floe-core/src/floe_core/plugins/lineage.py` — `LineageBackendPlugin.get_transport_config()`
- REQ-516: Event emission (RunStart/RunEnd/RunFail)
- REQ-527: Lineage backend plugin integration

**Acceptance Criteria**:
- [ ] `emit_start()` → transport receives LineageEvent with RunState.START
- [ ] `emit_complete()` correlates with start via run_id
- [ ] `emit_fail()` includes ErrorMessageRunFacet when error_message provided
- [ ] Factory function creates working emitter from mock backend plugin
- [ ] `pytest packages/floe-core/tests/lineage/test_emitter.py` → PASS
- [ ] `@pytest.mark.requirement("REQ-516")` on emission tests
- [ ] `@pytest.mark.requirement("REQ-527")` on backend integration test

**Commit**: YES
- Message: `feat(lineage): add LineageEmitter composition root and factory`
- Files: `packages/floe-core/src/floe_core/lineage/emitter.py`, updated `__init__.py`, tests

---

### Task 8: ABC Upgrade + Dagster Wiring Fixes (Issues 1, 3, 4, 5)

**What to do**:

**8a. Upgrade OrchestratorPlugin ABC** (`packages/floe-core/src/floe_core/plugins/orchestrator.py`):
- Replace `emit_lineage_event()` signature:
  ```python
  # OLD (remove):
  def emit_lineage_event(self, event_type: str, job: str, inputs: list[Dataset], outputs: list[Dataset]) -> None

  # NEW:
  def emit_lineage_event(
      self,
      event_type: RunState,
      job_name: str,
      job_namespace: str | None = None,
      run_id: UUID | None = None,
      inputs: list[LineageDataset] | None = None,
      outputs: list[LineageDataset] | None = None,
      run_facets: dict[str, Any] | None = None,
      job_facets: dict[str, Any] | None = None,
      producer: str | None = None,
  ) -> UUID:
  ```
- Add `def get_lineage_emitter(self) -> LineageEmitter | None` — default returns None, overridden by impls
- Deprecate old `Dataset` dataclass — add deprecation notice, alias to `LineageDataset`
- Import `RunState`, `LineageDataset`, `LineageEmitter` from `floe_core.lineage`

**8b. Fix Dagster plugin** (in floe-dagster package — find actual path):
- Wire `_asset_fn()` to call `emit_lineage_event()` with START before `dbt.run_models()`, COMPLETE/FAIL after
- Wire `create_definitions()` to include resources dict: `Definitions(assets=assets, resources={"dbt": dbt_resource})`
- Use `DbtLineageExtractor` (Task 5) to get inputs/outputs from manifest
- Use `CatalogDatasetResolver` (Task 6) for namespace resolution instead of hardcoded "floe"
- Set `_lineage_backend` from plugin config

**8c. Tests**:
- Unit: updated orchestrator ABC test verifying new signature
- Unit: Dagster plugin test verifying emit calls (mock transport)
- Unit: Dagster create_definitions returns resources

**Must NOT do**:
- Do NOT break existing tests that reference old `Dataset` — keep as deprecated alias
- Do NOT add Airflow/Prefect implementations (ABCs designed for them, impls deferred)
- Do NOT make emit_lineage_event() synchronous

**Recommended Agent Profile**:
- **Category**: `unspecified-high` — touching core ABCs + Dagster integration, high risk
  - Reason: ABC changes affect ALL orchestrator plugins; Dagster wiring requires careful resource management
- **Skills**: [`python-programmer`, `dagster-orchestration`, `dbt-transformations`]
  - `python-programmer`: ABC patterns, deprecation handling
  - `dagster-orchestration`: Definitions, resources, asset functions
  - `dbt-transformations`: dbtRunner integration in asset_fn
- **Skills Evaluated but Omitted**:
  - `pydantic-schemas`: ABC methods, not Pydantic models

**Parallelization**:
- **Can Run In Parallel**: YES (with Task 13)
- **Parallel Group**: Wave 4
- **Blocks**: Tasks 12, 13
- **Blocked By**: Tasks 5, 6, 7

**References**:
- `packages/floe-core/src/floe_core/plugins/orchestrator.py:158-370` — FULL file, ABC to modify
- `packages/floe-core/src/floe_core/plugins/orchestrator.py:105-128` — `Dataset` dataclass to deprecate
- `packages/floe-core/src/floe_core/plugins/orchestrator.py:316-345` — current `emit_lineage_event()` to replace
- Dagster plugin (find via `grep -r "class DagsterOrchestratorPlugin" packages/`) — `_asset_fn`, `create_definitions`, `_build_openlineage_event`
- `packages/floe-core/src/floe_core/lineage/emitter.py` (Task 7) — `LineageEmitter`
- `packages/floe-core/src/floe_core/lineage/extractors/dbt.py` (Task 5) — `DbtLineageExtractor`
- `packages/floe-core/src/floe_core/lineage/catalog_integration.py` (Task 6) — `CatalogDatasetResolver`
- Issue 1: orchestrator.py:317 — event_type is raw string
- Issue 3: Dagster _asset_fn never calls emit_lineage_event
- Issue 4: create_definitions returns no resources
- Issue 5: namespace hardcoded as "floe"

**Acceptance Criteria**:
- [ ] `emit_lineage_event()` accepts `RunState` enum (not raw string)
- [ ] `emit_lineage_event()` accepts `run_id`, `run_facets`, `job_facets`, `producer`
- [ ] `emit_lineage_event()` returns `UUID` (the run_id used)
- [ ] Old `Dataset` still importable (deprecated alias)
- [ ] Dagster `_asset_fn` emits START before dbt.run_models(), COMPLETE/FAIL after
- [ ] Dagster `create_definitions()` includes resources dict
- [ ] Dagster uses catalog-aware namespace (not hardcoded "floe")
- [ ] `pytest` on orchestrator + dagster tests → PASS
- [ ] `@pytest.mark.requirement("REQ-516")` on event emission
- [ ] `@pytest.mark.requirement("REQ-519")` on input datasets
- [ ] `@pytest.mark.requirement("REQ-520")` on output datasets

**Commit**: YES
- Message: `feat(lineage): upgrade OrchestratorPlugin ABC and wire Dagster lineage emission`
- Files: `orchestrator.py`, Dagster plugin file, tests

---

### Task 9: Marquez Backend Plugin

**What to do**:
- Create `packages/floe-marquez/` (or as module in floe-core depending on package structure):
  - `marquez_plugin.py`:
    - `MarquezLineageBackendPlugin(LineageBackendPlugin)`:
      - `name` → "marquez"
      - `get_transport_config()` → `{"type": "http", "url": "http://marquez:5000/api/v1/lineage", "timeout": 5.0}`
      - `get_namespace_strategy()` → environment-based default
      - `get_helm_values()` → Marquez + PostgreSQL Helm values
      - `validate_connection()` → `GET /api/v1/namespaces` health check
    - Entry point: `[project.entry-points."floe.lineage_backends"]` `marquez = "..."`
- Create `testing/k8s/services/marquez.yaml` — K8s manifest for Marquez in Kind cluster
- Create `testing/fixtures/lineage.py` — test fixtures:
  - `mock_lineage_emitter()` — NoOp transport emitter
  - `mock_lineage_backend()` — Mock MarquezPlugin
  - `sample_lineage_event()` — fixture event for assertions
- Unit tests: `packages/floe-marquez/tests/test_marquez_plugin.py`
  - Test transport config structure
  - Test helm values include PostgreSQL
  - Test validate_connection with mock HTTP (success + failure)

**Must NOT do**:
- Do NOT implement Atlan or OpenMetadata plugins (separate epics)
- Do NOT embed Marquez client logic — use OpenLineage HTTP transport

**Recommended Agent Profile**:
- **Category**: `unspecified-low` — concrete plugin implementation following existing patterns
  - Reason: Clear ABC to implement, well-documented Marquez API
- **Skills**: [`python-programmer`, `helm-k8s-deployment`]
  - `python-programmer`: Plugin implementation
  - `helm-k8s-deployment`: Marquez Helm values, K8s service manifest
- **Skills Evaluated but Omitted**:
  - `dagster-orchestration`: No Dagster involvement
  - `polaris-catalog`: No catalog involvement

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 5, 6, 7)
- **Parallel Group**: Wave 3
- **Blocks**: Task 12
- **Blocked By**: Task 7 (needs emitter to exist for test fixtures)

**References**:
- `packages/floe-core/src/floe_core/plugins/lineage.py` — `LineageBackendPlugin` ABC to implement
- `packages/floe-core/src/floe_core/plugin_metadata.py` — `PluginMetadata` base class pattern
- `packages/floe-core/src/floe_core/plugin_types.py:51` — `LINEAGE_BACKEND = "floe.lineage_backends"` entry point group
- Marquez API: `POST /api/v1/lineage`, `GET /api/v1/namespaces` for health check
- `testing/fixtures/` — existing fixture patterns (e.g., polling, postgres, dagster fixtures)
- REQ-527: Lineage backend plugin integration

**Acceptance Criteria**:
- [ ] `MarquezLineageBackendPlugin` passes `isinstance(plugin, LineageBackendPlugin)`
- [ ] Transport config has correct Marquez endpoint URL
- [ ] Helm values include Marquez + PostgreSQL configuration
- [ ] Entry point registered in pyproject.toml
- [ ] `testing/k8s/services/marquez.yaml` is valid K8s manifest
- [ ] `testing/fixtures/lineage.py` exports usable test fixtures
- [ ] `pytest packages/floe-marquez/tests/` → PASS
- [ ] `@pytest.mark.requirement("REQ-527")` on plugin tests

**Commit**: YES
- Message: `feat(lineage): add Marquez backend plugin and test fixtures`
- Files: marquez plugin, testing fixtures, K8s manifest

---

### Task 10: ResolvedPlugins Schema Update (v0.5.0)

**What to do**:
- Edit `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`:
  - Add `lineage_backend: PluginRef | None = Field(default=None, description="Resolved lineage backend plugin (optional)")` to `ResolvedPlugins` class (after `semantic` field, line ~226)
  - Bump version constant (if exists) to 0.5.0
- Edit `packages/floe-core/src/floe_core/compilation/resolver.py`:
  - Add lineage_backend resolution in `resolve_plugins()` — resolve from `PluginsConfig.lineage_backend`
- Edit `packages/floe-core/src/floe_core/schemas/plugins.py`:
  - Verify `PluginsConfig.lineage_backend` field exists (it does at line 288) — no changes needed
- Add lineage enforcement in compilation:
  - If `ObservabilityConfig.lineage == True` and `ResolvedPlugins.lineage_backend is None` → compilation warning (not error, for backward compat)
- Unit tests: `packages/floe-core/tests/schemas/test_compiled_artifacts.py`
  - Test ResolvedPlugins with lineage_backend field
  - Test backward compat: existing artifacts without lineage_backend still deserialize
  - Test compilation warning when lineage enabled but no backend

**Must NOT do**:
- Do NOT make lineage_backend required — optional for backward compatibility
- Do NOT change PluginsConfig (already has lineage_backend)

**Recommended Agent Profile**:
- **Category**: `quick` — small schema addition, clear pattern
  - Reason: Adding one Pydantic field following exact existing pattern
- **Skills**: [`python-programmer`, `pydantic-schemas`]
  - `python-programmer`: Schema editing
  - `pydantic-schemas`: Pydantic v2 Field patterns, frozen model updates
- **Skills Evaluated but Omitted**:
  - `dagster-orchestration`: No orchestrator involvement

**Parallelization**:
- **Can Run In Parallel**: YES (with Task 1)
- **Parallel Group**: Wave 1
- **Blocks**: Tasks 11, 12
- **Blocked By**: None

**References**:
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:173-226` — `ResolvedPlugins` class to modify
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py:211-226` — existing optional plugin fields pattern (catalog, storage, ingestion, semantic)
- `packages/floe-core/src/floe_core/compilation/resolver.py:61-108` — `resolve_plugins()` function to update
- `packages/floe-core/src/floe_core/schemas/plugins.py:288` — `PluginsConfig.lineage_backend` already exists
- Issue 6: ResolvedPlugins doesn't carry lineage_backend
- REQ-530: Lineage enforcement in compilation

**Acceptance Criteria**:
- [ ] `ResolvedPlugins(compute=..., orchestrator=..., lineage_backend=PluginRef(type="marquez"))` succeeds
- [ ] `ResolvedPlugins(compute=..., orchestrator=...)` still works (lineage_backend=None)
- [ ] `resolve_plugins()` resolves lineage_backend from manifest
- [ ] Compilation warns when lineage=True but no backend
- [ ] `pytest packages/floe-core/tests/schemas/test_compiled_artifacts.py` → PASS
- [ ] `@pytest.mark.requirement("REQ-530")` on enforcement test

**Commit**: YES
- Message: `feat(lineage): add lineage_backend to ResolvedPlugins (v0.5.0)`
- Files: `compiled_artifacts.py`, `resolver.py`, tests

---

### Task 11: CompiledArtifacts Contract Tests

**What to do**:
- Update/create contract tests for CompiledArtifacts v0.5.0:
  - Test serialization roundtrip with lineage_backend field
  - Test cross-package compatibility (any package importing ResolvedPlugins works with new field)
  - Test backward compatibility: v0.4.0 artifacts (no lineage_backend) deserialize cleanly
  - Test forward compatibility: v0.5.0 artifacts with lineage_backend are ignored by older code (graceful)
- Follow existing contract test patterns in `testing/`

**Must NOT do**:
- Do NOT test lineage logic — only schema compatibility

**Recommended Agent Profile**:
- **Category**: `quick` — focused contract tests
  - Reason: Small, well-scoped test additions
- **Skills**: [`python-programmer`, `testing`]
  - `python-programmer`: Test code
  - `testing`: Contract test patterns, cross-package testing
- **Skills Evaluated but Omitted**:
  - `pydantic-schemas`: Tests validate behavior, don't create schemas

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 2, 3, 4)
- **Parallel Group**: Wave 2
- **Blocks**: Task 12
- **Blocked By**: Task 10

**References**:
- `packages/floe-core/tests/` — existing test patterns
- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py` (updated in Task 10)
- `testing/` — cross-package test utilities

**Acceptance Criteria**:
- [ ] v0.5.0 ResolvedPlugins serializes/deserializes with lineage_backend
- [ ] v0.4.0 JSON (no lineage_backend) deserializes to v0.5.0 model (None default)
- [ ] `pytest` contract tests → PASS

**Commit**: YES (group with Task 10)
- Message: `test(lineage): add contract tests for ResolvedPlugins v0.5.0`

---

### Task 12: Integration Tests (Kind + Marquez)

**What to do**:
- Create `packages/floe-core/tests/integration/test_lineage_integration.py`:
  - End-to-end test: compile artifacts → create emitter → emit START/COMPLETE → verify in Marquez API
  - Uses `testing/k8s/services/marquez.yaml` (Task 9) deployed in Kind cluster
  - Uses `testing/fixtures/lineage.py` (Task 9) for setup
  - Test scenarios:
    1. Emit dbt model lineage (3-model chain) → query Marquez API for lineage graph
    2. Emit with Iceberg facets → verify facets in Marquez response
    3. Emit FAIL event → verify error facet in Marquez
    4. Trace correlation → verify trace_id in run facets
  - Mark with `@pytest.mark.integration` and `@pytest.mark.k8s`
- Create `packages/floe-core/tests/integration/test_dagster_lineage.py`:
  - Test Dagster asset execution emits lineage events (mock transport)
  - Test create_definitions includes resources

**Must NOT do**:
- Do NOT test Airflow/Prefect (deferred)
- Do NOT test column-level lineage (deferred)

**Recommended Agent Profile**:
- **Category**: `unspecified-high` — complex multi-service integration
  - Reason: K8s Kind cluster, multiple services, API verification
- **Skills**: [`python-programmer`, `testing`, `helm-k8s-deployment`, `dagster-orchestration`]
  - `python-programmer`: Integration test code
  - `testing`: Integration test patterns, K8s test infrastructure
  - `helm-k8s-deployment`: Kind cluster, service deployment
  - `dagster-orchestration`: Dagster asset execution testing
- **Skills Evaluated but Omitted**:
  - `dbt-transformations`: dbt tested via manifest fixture, not live dbt

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 14, 15)
- **Parallel Group**: Wave 5
- **Blocks**: Task 15
- **Blocked By**: Tasks 8, 9, 10, 11

**References**:
- `testing/fixtures/` — existing fixtures (dagster, polling, postgres patterns)
- `testing/k8s/` — existing K8s test infrastructure
- `testing/k8s/services/marquez.yaml` (Task 9)
- `testing/fixtures/lineage.py` (Task 9)
- Marquez API: `GET /api/v1/lineage?nodeId={nodeId}&depth=3` for graph query
- All REQ-516 through REQ-531

**Acceptance Criteria**:
- [ ] Marquez receives events emitted by LineageEmitter
- [ ] Marquez API returns correct lineage graph for 3-model chain
- [ ] Facets (schema, statistics, Iceberg snapshot) visible in Marquez response
- [ ] Trace correlation ID present in run facets
- [ ] Dagster asset emits START/COMPLETE events
- [ ] `pytest -m integration packages/floe-core/tests/integration/test_lineage_integration.py` → PASS

**Commit**: YES
- Message: `test(lineage): add integration tests with Kind + Marquez`
- Files: integration test files

---

### Task 13: QualityPlugin Lineage Unification (Issue 2)

**What to do**:
- Edit `packages/floe-core/src/floe_core/plugins/quality.py`:
  - Deprecate `OpenLineageEmitter` Protocol (quality.py:52-73)
  - Deprecate `get_lineage_emitter()` method (quality.py:364)
  - Add new method: `def get_quality_facets(self, results: list[QualityCheckResult]) -> dict` — returns DataQualityAssertionsDatasetFacet dict
  - Quality lineage now flows through the unified `LineageEmitter` (Task 7):
    - Orchestrator calls `lineage_emitter.emit_complete(outputs=[dataset_with_quality_facets])`
    - Quality plugin only provides facet data, not emission
- Update any quality plugin implementations to use new pattern
- Unit tests: verify deprecated methods still work (backward compat) but new path is preferred

**Must NOT do**:
- Do NOT remove deprecated Protocol yet — keep for one version cycle
- Do NOT change QualityCheckResult schema

**Recommended Agent Profile**:
- **Category**: `unspecified-low` — deprecation + new method, clear pattern
  - Reason: Well-scoped refactor following established deprecation patterns
- **Skills**: [`python-programmer`, `testing`]
  - `python-programmer`: Deprecation patterns, Protocol evolution
  - `testing`: Backward compatibility testing
- **Skills Evaluated but Omitted**:
  - `dagster-orchestration`: Quality unification is orchestrator-agnostic

**Parallelization**:
- **Can Run In Parallel**: YES (with Task 8)
- **Parallel Group**: Wave 4
- **Blocks**: Task 14
- **Blocked By**: Task 8 (needs unified emitter pattern established)

**References**:
- `packages/floe-core/src/floe_core/plugins/quality.py:52-73` — `OpenLineageEmitter` Protocol to deprecate
- `packages/floe-core/src/floe_core/plugins/quality.py:364-400` — `get_lineage_emitter()` to deprecate
- `packages/floe-core/src/floe_core/lineage/facets.py` (Task 4) — `QualityFacetBuilder`
- `packages/floe-core/src/floe_core/lineage/emitter.py` (Task 7) — `LineageEmitter` as unified interface
- Issue 2: QualityPlugin has duplicate lineage abstraction
- REQ-524: Quality check lineage

**Acceptance Criteria**:
- [ ] `OpenLineageEmitter` Protocol marked deprecated (warnings.warn)
- [ ] `get_lineage_emitter()` marked deprecated
- [ ] New `get_quality_facets()` returns valid DataQualityAssertionsDatasetFacet
- [ ] Old code calling `get_lineage_emitter()` still works (deprecation warning only)
- [ ] `pytest` quality plugin tests → PASS
- [ ] `@pytest.mark.requirement("REQ-524")` on quality lineage tests

**Commit**: YES
- Message: `refactor(lineage): unify quality lineage through LineageEmitter, deprecate OpenLineageEmitter`
- Files: `quality.py`, tests

---

### Task 14: Quality Contract Tests

**What to do**:
- Update quality plugin contract tests to verify:
  - Deprecated `get_lineage_emitter()` still returns compatible object
  - New `get_quality_facets()` method exists and returns valid dict
  - Quality results flow through unified lineage path
- Cross-package: ensure quality plugin implementations in other packages still pass

**Must NOT do**:
- Do NOT test lineage emission end-to-end (that's Task 12)

**Recommended Agent Profile**:
- **Category**: `quick` — focused contract test updates
  - Reason: Small test additions for backward compatibility
- **Skills**: [`python-programmer`, `testing`]

**Parallelization**:
- **Can Run In Parallel**: YES (with Tasks 12, 15)
- **Parallel Group**: Wave 5
- **Blocks**: Task 15
- **Blocked By**: Task 13

**References**:
- Quality plugin tests in existing test suite
- `packages/floe-core/src/floe_core/plugins/quality.py` (updated in Task 13)

**Acceptance Criteria**:
- [ ] Backward compat: old quality plugin code still works
- [ ] New `get_quality_facets()` produces correct facet structure
- [ ] `pytest` quality contract tests → PASS

**Commit**: YES (group with Task 13)
- Message: `test(lineage): add quality lineage unification contract tests`

---

### Task 15: Final Validation & Documentation

**What to do**:
- Run full test suite: `pytest packages/floe-core/` → all pass
- Run type check: `mypy packages/floe-core/src/floe_core/lineage/` → clean
- Run linter: `ruff check packages/floe-core/src/floe_core/lineage/` → clean
- Verify all requirements traced:
  - REQ-516 through REQ-531 each have at least one `@pytest.mark.requirement`
- Update `packages/floe-core/src/floe_core/lineage/__init__.py` with complete public API
- Verify entry points registered for Marquez plugin
- Create checklist summary of deferred items (column lineage, Kafka, dlt, OTLP)

**Must NOT do**:
- Do NOT write external documentation files (README updates deferred)
- Do NOT implement deferred items

**Recommended Agent Profile**:
- **Category**: `quick` — validation and verification
  - Reason: Running commands, checking output
- **Skills**: [`python-programmer`, `testing`]

**Parallelization**:
- **Can Run In Parallel**: NO (final gate)
- **Parallel Group**: Wave 5 (after 12, 14)
- **Blocks**: None (final task)
- **Blocked By**: Tasks 12, 14

**References**:
- All files created in Tasks 1-14
- Requirements doc: `docs/requirements/06-observability-lineage/02-openlineage.md`

**Acceptance Criteria**:
- [ ] `pytest packages/floe-core/` → ALL PASS
- [ ] `mypy packages/floe-core/src/floe_core/lineage/` → 0 errors
- [ ] `ruff check packages/floe-core/src/floe_core/lineage/` → 0 errors
- [ ] All REQ-516 through REQ-531 traced to at least one test
- [ ] Marquez entry point discoverable: `python -c "from importlib.metadata import entry_points; print([e for e in entry_points(group='floe.lineage_backends')])`

**Commit**: YES
- Message: `chore(lineage): final validation and public API exports`

---

## Commit Strategy

| After Task | Message | Key Files | Verification |
|------------|---------|-----------|--------------|
| 1 | `feat(lineage): add core lineage types and protocols` | lineage/{types,protocols}.py | pytest test_types.py |
| 2 | `feat(lineage): add non-blocking transport abstraction` | lineage/transport.py | pytest test_transport.py |
| 3 | `feat(lineage): add event builder` | lineage/events.py | pytest test_events.py |
| 4 | `feat(lineage): add facet builders` | lineage/facets.py | pytest test_facets.py |
| 5 | `feat(lineage): add dbt manifest extractor` | lineage/extractors/dbt.py | pytest test_dbt.py |
| 6 | `feat(lineage): add catalog-aware dataset identity` | lineage/catalog_integration.py | pytest test_catalog.py |
| 7 | `feat(lineage): add LineageEmitter composition root` | lineage/emitter.py | pytest test_emitter.py |
| 8 | `feat(lineage): upgrade ABC and wire Dagster` | orchestrator.py, dagster plugin | pytest orchestrator + dagster |
| 9 | `feat(lineage): add Marquez backend plugin` | floe-marquez, fixtures, k8s | pytest marquez tests |
| 10+11 | `feat(lineage): add lineage_backend to ResolvedPlugins v0.5.0` | compiled_artifacts.py, resolver.py | pytest schema + contract |
| 12 | `test(lineage): add integration tests` | integration tests | pytest -m integration |
| 13+14 | `refactor(lineage): unify quality lineage` | quality.py | pytest quality tests |
| 15 | `chore(lineage): final validation` | __init__.py | full suite |

---

## Success Criteria

### Verification Commands
```bash
# Unit tests
pytest packages/floe-core/tests/lineage/ -v  # All lineage unit tests

# Type checking
mypy packages/floe-core/src/floe_core/lineage/  # 0 errors

# Lint
ruff check packages/floe-core/src/floe_core/lineage/  # 0 errors

# Contract tests
pytest -m contract packages/floe-core/tests/  # Schema compatibility

# Integration tests (requires Kind cluster)
pytest -m integration packages/floe-core/tests/integration/test_lineage_integration.py

# Requirement traceability
grep -r "REQ-5[12][0-9]" packages/floe-core/tests/ | sort | uniq  # All REQ-516-531 traced

# Entry point discovery
python -c "from importlib.metadata import entry_points; eps = entry_points(group='floe.lineage_backends'); print(f'{len(list(eps))} lineage backends found')"
```

### Final Checklist
- [ ] All 6 architectural issues resolved (Issues 1-6)
- [ ] Non-blocking emission guaranteed (REQ-525/526)
- [ ] Catalog-aware dataset identity (not hardcoded "floe")
- [ ] Unified lineage interface (3 competing interfaces → 1)
- [ ] dbt manifest → lineage extraction working
- [ ] Dagster assets emit lineage events
- [ ] Marquez receives and serves lineage graph
- [ ] ResolvedPlugins v0.5.0 backward compatible
- [ ] All tests pass (unit, contract, integration)
- [ ] mypy + ruff clean
- [ ] All REQ-516 through REQ-531 traced
- [ ] Deferred items documented: column lineage, Kafka, dlt, OTLP, Airflow/Prefect impls
