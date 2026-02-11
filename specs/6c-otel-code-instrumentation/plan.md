# Implementation Plan: OTel Code Instrumentation

**Branch**: `6c-otel-code-instrumentation` | **Date**: 2026-02-10 | **Spec**: `specs/6c-otel-code-instrumentation/spec.md`
**Input**: Feature specification from `/specs/6c-otel-code-instrumentation/spec.md`

## Summary

Epic 6C closes instrumentation gaps across all 21 plugins and 2 core packages in the floe platform. The work consists of six workstreams: (1) promote `sanitize_error_message()` to floe-core, (2) unify the two divergent `@traced` decorators into one, (3) add `tracing.py` modules to 15 uninstrumented/partially-instrumented plugins, (4) migrate floe-iceberg to the unified `@traced`, (5) add `tracer_name` property to `PluginMetadata` and wire an instrumentation audit into `compile_pipeline`, and (6) write comprehensive tests using `InMemorySpanExporter` for every new tracing module.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: opentelemetry-api>=1.39.0, opentelemetry-sdk>=1.20.0, structlog>=24.0, pydantic>=2.0
**Storage**: N/A (instrumentation only, no persistence)
**Testing**: pytest with `InMemorySpanExporter` + `SimpleSpanProcessor` + `TracerProvider(sampler=ALWAYS_ON)`
**Target Platform**: Linux/K8s (same as all floe packages)
**Project Type**: Monorepo — changes span 2 packages + 19 plugins
**Performance Goals**: Tracing overhead <5% of operation time (SC-006, existing benchmark at `benchmarks/test_tracing_perf.py`)
**Constraints**: No breaking changes to existing plugin APIs; `tracer_name` on PluginMetadata must be optional
**Scale/Scope**: 19 plugins + 2 core packages, ~15 new `tracing.py` modules, ~19 new test files, 1 unified decorator, 1 audit function

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package — each plugin's `tracing.py` lives in that plugin; shared utilities in floe-core
- [x] No SQL parsing/validation in Python — N/A (no SQL work)
- [x] No orchestration logic outside floe-dagster — N/A

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface — `tracer_name` added as optional property on `PluginMetadata` ABC
- [x] Plugin registered via entry point — existing plugins, no new registrations
- [x] PluginMetadata declares name, version, floe_api_version — existing, no changes to required fields

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved — OpenTelemetry is ENFORCED per constitution; this epic expands enforcement
- [x] Pluggable choices documented in manifest.yaml — N/A

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts — audit hooks into compile_pipeline which produces CompiledArtifacts
- [x] Pydantic v2 models for all schemas — FloeSpanAttributes already Pydantic v2
- [x] Contract changes follow versioning rules — PluginMetadata change is additive (MINOR)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster — OTel tests use InMemorySpanExporter (no external services needed; unit tier)
- [x] No `pytest.skip()` usage — strict compliance
- [x] `@pytest.mark.requirement()` on all tests

**Principle VI: Security First**
- [x] Input validation via Pydantic — FloeSpanAttributes validated
- [x] Credentials use SecretStr — `sanitize_error_message()` strips credentials from span error messages
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only — tracing is Layer 1 (Foundation)
- [x] Layer ownership respected

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted — this is the ENTIRE purpose of the epic
- [x] OpenLineage events for data transformations — N/A (lineage plugin gets tracing, not lineage changes)

## Research Findings

### R1: Two Divergent @traced Implementations

**floe-core** (`packages/floe-core/src/floe_core/telemetry/tracing.py:97-199`):
- Parameters: `name`, `attributes` (static dict), `floe_attributes` (FloeSpanAttributes)
- Supports sync AND async functions
- Uses `get_tracer()` from `_TRACER_NAME = "floe_core.telemetry"`
- Error handling: `span.set_status(Status(StatusCode.ERROR, str(e)))` then `span.record_exception(e)` — raw, unsanitized

**floe-iceberg** (`packages/floe-iceberg/src/floe_iceberg/telemetry.py:107-200`):
- Parameters: `operation_name`, `attributes` (static dict), `attributes_fn` (dynamic callable)
- Supports sync ONLY — no async support
- Uses `get_tracer()` from `TRACER_NAME = "floe-iceberg"`
- Error handling: `span.record_exception(exc)` then `span.set_status(...)` — reversed order, also raw
- Extra feature: `attributes_fn` receives `(*args, **kwargs)` and returns dict; silently catches extraction failures

**Unification strategy**: Merge both into floe-core's `@traced` by adding `attributes_fn` parameter. Keep async support. Add `sanitize_error_message()` to error recording.

### R2: Existing tracing.py Pattern (Reference: floe-catalog-polaris)

The canonical pattern for plugin tracing modules:
1. `TRACER_NAME` constant (e.g., `"floe.catalog.polaris"`)
2. Semantic attribute constants (e.g., `ATTR_CATALOG_NAME`, `ATTR_NAMESPACE`)
3. `get_tracer()` function wrapping `_factory_get_tracer(TRACER_NAME)`
4. Domain context manager (e.g., `catalog_span()`) using `@contextmanager`
5. Error handling with `span.set_status()` + `span.record_exception()`
6. Optional helper functions (e.g., `_sanitize_uri()`, `set_error_attributes()`)

### R3: Plugins Using Inline Tracing (No tracing.py)

These plugins use `_factory_get_tracer` directly in their main `plugin.py`:
- **floe-secrets-infisical**: Has `_TRACER_NAME`, `_get_tracer()`, and span attribute constants defined inline in plugin.py — needs extraction to tracing.py
- **floe-identity-keycloak**: Same pattern — inline `_TRACER_NAME` and `_factory_get_tracer` in plugin.py
- **floe-orchestrator-dagster**: Uses `_get_tracer` in `assets/semantic_sync.py` only
- **floe-quality-dbt**: Try/except import of `_factory_get_tracer` with fallback to None
- **floe-quality-gx**: Same try/except pattern as quality-dbt
- **floe-compute-duckdb**: Has integration test for OTel but no dedicated tracing module

### R4: sanitize_error_message() Location

Currently at `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py:83-110`.
Uses two regex patterns:
- `_SENSITIVE_KEY_PATTERN`: Matches `password=`, `secret_key=`, `access_key=`, `token=`, `api_key=`, `authorization=`, `credential=`
- `_URL_CREDENTIAL_PATTERN`: Matches `://user:pass@host`
Truncates to `max_length` (default 500).

Must be promoted to `floe_core.telemetry.sanitization` as a public utility.

### R5: Raw span.record_exception() Calls

Found **25+ raw `span.record_exception(e)` calls** across the codebase that bypass sanitization:
- floe-core: telemetry/tracing.py (3), rbac/generator.py (1), oci/*.py (6)
- floe-iceberg: telemetry.py (1), _compaction_manager.py (1)
- floe-catalog-polaris: tracing.py (1)
- floe-identity-keycloak: plugin.py (3)
- floe-dbt-core: tracing.py (1)
- floe-semantic-cube: tracing.py (1), plugin.py (2)
- floe-ingestion-dlt: tracing.py (0 — already uses sanitized recording)

All need migration to use `sanitize_error_message()`.

### R6: PluginMetadata ABC

At `packages/floe-core/src/floe_core/plugin_metadata.py:76-261`. Abstract properties: `name`, `version`, `floe_api_version`. Optional: `description`, `dependencies`. No `tracer_name` property exists — needs addition as optional with default `None`.

### R7: Compilation Pipeline Audit Hook

`compile_pipeline()` at `packages/floe-core/src/floe_core/compilation/stages.py:125-299` has 6 stages. The ENFORCE stage (stage 4, lines 250-289) already handles sink whitelist validation. An instrumentation audit warning fits naturally here — after plugin resolution (stage 3) and before compilation (stage 5).

### R8: Test Infrastructure

Standard fixture pattern (from `packages/floe-core/tests/unit/test_telemetry/test_tracing.py`):
```python
exporter = InMemorySpanExporter()
provider = TracerProvider(sampler=ALWAYS_ON)
provider.add_span_processor(SimpleSpanProcessor(exporter))
test_tracer = provider.get_tracer("test_name")
set_tracer(test_tracer)  # Inject into module under test
```
16 files already use `InMemorySpanExporter`. Benchmark at `benchmarks/test_tracing_perf.py`.

### R9: 14 Plugin Types (PluginType Enum)

From `packages/floe-core/src/floe_core/plugin_types.py`: COMPUTE, ORCHESTRATOR, CATALOG, STORAGE, TELEMETRY_BACKEND, LINEAGE_BACKEND, DBT, SEMANTIC_LAYER, INGESTION, SECRETS, IDENTITY, QUALITY, RBAC, ALERT_CHANNEL.

21 concrete plugins across these 14 types. Telemetry backends (console, jaeger) excluded from instrumentation per clarification.

## Project Structure

### Documentation (this feature)

```text
specs/6c-otel-code-instrumentation/
├── plan.md              # This file
├── research.md          # Phase 0 output (inlined in plan)
├── checklists/
│   └── requirements.md  # Quality checklist (created)
└── contracts/
    └── unified-traced-api.md  # Phase 1: unified @traced contract
```

### Source Code (repository root)

```text
# floe-core (shared utilities + audit)
packages/floe-core/src/floe_core/
├── telemetry/
│   ├── tracing.py              # MODIFY: Add attributes_fn param to @traced + sanitized errors
│   └── sanitization.py         # NEW: Promoted sanitize_error_message()
├── plugin_metadata.py          # MODIFY: Add optional tracer_name property
└── compilation/
    └── stages.py               # MODIFY: Add instrumentation audit to ENFORCE stage

# floe-iceberg (migration)
packages/floe-iceberg/src/floe_iceberg/
└── telemetry.py                # MODIFY: Remove local @traced, import from floe-core

# Plugin tracing modules (NEW — 11 new tracing.py files)
plugins/floe-alert-alertmanager/src/floe_alert_alertmanager/tracing.py   # NEW
plugins/floe-alert-email/src/floe_alert_email/tracing.py                 # NEW
plugins/floe-alert-slack/src/floe_alert_slack/tracing.py                 # NEW
plugins/floe-alert-webhook/src/floe_alert_webhook/tracing.py             # NEW
plugins/floe-lineage-marquez/src/floe_lineage_marquez/tracing.py         # NEW
plugins/floe-secrets-k8s/src/floe_secrets_k8s/tracing.py                 # NEW
plugins/floe-network-security-k8s/src/floe_network_security_k8s/tracing.py  # NEW
plugins/floe-rbac-k8s/src/floe_rbac_k8s/tracing.py                      # NEW
plugins/floe-compute-duckdb/src/floe_compute_duckdb/tracing.py           # NEW
plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/tracing.py   # NEW
plugins/floe-dbt-fusion/src/floe_dbt_fusion/tracing.py                   # NEW

# Plugin tracing modules (EXTRACT from plugin.py — 4 plugins)
plugins/floe-secrets-infisical/src/floe_secrets_infisical/tracing.py     # NEW (extract from plugin.py)
plugins/floe-identity-keycloak/src/floe_identity_keycloak/tracing.py     # NEW (extract from plugin.py)
plugins/floe-quality-dbt/src/floe_quality_dbt/tracing.py                 # NEW (extract from plugin.py)
plugins/floe-quality-gx/src/floe_quality_gx/tracing.py                   # NEW (extract from plugin.py)

# Existing tracing modules (MODIFY — add sanitized error recording)
plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py         # MODIFY
plugins/floe-dbt-core/src/floe_dbt_core/tracing.py                      # MODIFY
plugins/floe-semantic-cube/src/floe_semantic_cube/tracing.py             # MODIFY
plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py             # MODIFY (remove private impl)

# Tests — one per tracing module
plugins/floe-alert-alertmanager/tests/unit/test_tracing.py               # NEW
plugins/floe-alert-email/tests/unit/test_tracing.py                      # NEW
plugins/floe-alert-slack/tests/unit/test_tracing.py                      # NEW
plugins/floe-alert-webhook/tests/unit/test_tracing.py                    # NEW
plugins/floe-lineage-marquez/tests/unit/test_tracing.py                  # NEW
plugins/floe-secrets-k8s/tests/unit/test_tracing.py                      # NEW
plugins/floe-secrets-infisical/tests/unit/test_tracing.py                # NEW
plugins/floe-network-security-k8s/tests/unit/test_tracing.py             # NEW
plugins/floe-rbac-k8s/tests/unit/test_tracing.py                        # NEW
plugins/floe-compute-duckdb/tests/unit/test_tracing.py                   # NEW
plugins/floe-orchestrator-dagster/tests/unit/test_tracing.py             # NEW
plugins/floe-identity-keycloak/tests/unit/test_tracing.py                # NEW (replaces mock-based test_otel_tracing.py)
plugins/floe-quality-dbt/tests/unit/test_tracing.py                      # NEW
plugins/floe-quality-gx/tests/unit/test_tracing.py                       # NEW
plugins/floe-dbt-fusion/tests/unit/test_tracing.py                       # NEW

# Core tests
packages/floe-core/tests/unit/test_telemetry/test_sanitization.py        # NEW
packages/floe-core/tests/unit/test_telemetry/test_traced_unified.py      # NEW (extended @traced tests)
packages/floe-core/tests/unit/test_plugin_metadata_tracer.py             # NEW
packages/floe-core/tests/unit/compilation/test_instrumentation_audit.py  # NEW

# Contract tests
tests/contract/test_plugin_instrumentation_contract.py                   # NEW

# Benchmark extension
benchmarks/test_tracing_perf.py                                          # MODIFY (add overhead benchmark)
```

**Structure Decision**: Monorepo with per-plugin `tracing.py` modules following the established pattern from floe-catalog-polaris. Each plugin owns its own tracing code. Shared utilities live in `floe_core.telemetry`.

## Implementation Phases

### Phase 1: Error Sanitization Promotion (Foundation)

**Goal**: Make `sanitize_error_message()` a public, shared utility in floe-core.

**Files**:
- **NEW**: `packages/floe-core/src/floe_core/telemetry/sanitization.py` — Copy and promote from floe-ingestion-dlt
- **MODIFY**: `packages/floe-core/src/floe_core/telemetry/__init__.py` — Export `sanitize_error_message`
- **MODIFY**: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py` — Replace private impl with import from floe-core
- **NEW**: `packages/floe-core/tests/unit/test_telemetry/test_sanitization.py` — Unit tests

**Tests** (test_sanitization.py):
- URL credential redaction: `://user:pass@host` → `://<REDACTED>@host`
- Key-value redaction: `password=secret123` → `password=<REDACTED>`
- Multiple sensitive keys: `access_key=xxx secret_key=yyy` both redacted
- Truncation to max_length
- Clean strings pass through unchanged
- Empty string returns empty
- Very long error message truncated correctly

**Dependency**: None — this is the foundation all other phases build on.

### Phase 2: Unified @traced Decorator

**Goal**: Merge floe-core's `@traced` and floe-iceberg's `@traced` into one API.

**Files**:
- **MODIFY**: `packages/floe-core/src/floe_core/telemetry/tracing.py`
  - Add `attributes_fn: Callable[..., dict[str, Any]] | None = None` parameter
  - Use `sanitize_error_message()` in error recording
  - Keep existing sync + async support
  - Wrap `attributes_fn` call in try/except (fail-safe, log warning)

**Unified API**:
```python
@traced(
    name="custom.span.name",           # Optional custom span name
    attributes={"key": "value"},        # Optional static attributes
    floe_attributes=FloeSpanAttributes(...),  # Optional semantic conventions
    attributes_fn=lambda *a, **kw: {},  # Optional dynamic attributes
)
def my_function(): ...
```

**Tests** (test_traced_unified.py — extends existing test_tracing.py):
- `attributes_fn` receives correct args/kwargs
- `attributes_fn` failure logged but doesn't break function execution
- `attributes_fn` + `attributes` + `floe_attributes` all compose correctly
- Error recording uses `sanitize_error_message()`
- Async function with `attributes_fn` works correctly
- Nested spans preserve parent-child relationship

**Dependency**: Phase 1 (sanitize_error_message).

### Phase 3: floe-iceberg Migration

**Goal**: Remove floe-iceberg's local `@traced` and use the unified one from floe-core.

**Files**:
- **MODIFY**: `packages/floe-iceberg/src/floe_iceberg/telemetry.py`
  - Remove `traced()` function definition (lines 87-200)
  - Keep `TRACER_NAME`, `get_tracer()`, and `__all__`
  - Import `traced` from `floe_core.telemetry.tracing`
  - Re-export `traced` for backwards compatibility in `__all__`
- **MODIFY**: All files importing from `floe_iceberg.telemetry.traced` — update to use `operation_name` → `name` mapping

**Tests**: Run existing floe-iceberg tests to verify no regression. No new tests needed — existing tests cover the behavior.

**Dependency**: Phase 2 (unified @traced).

### Phase 4: PluginMetadata tracer_name Property

**Goal**: Add optional `tracer_name` property to `PluginMetadata` ABC for instrumentation audit.

**Files**:
- **MODIFY**: `packages/floe-core/src/floe_core/plugin_metadata.py`
  - Add optional property:
    ```python
    @property
    def tracer_name(self) -> str | None:
        """OpenTelemetry tracer name for this plugin.
        Override to report instrumentation status to the audit system.
        Returns: Tracer name string, or None if uninstrumented.
        """
        return None
    ```
- **MODIFY**: Each of the 19 instrumented plugins — override `tracer_name` to return their `TRACER_NAME`
- **NEW**: `packages/floe-core/tests/unit/test_plugin_metadata_tracer.py`

**Tests**:
- Default `tracer_name` returns None
- Plugin with `tracer_name` override returns correct name
- Multiple plugins have unique tracer names

**Dependency**: None (can run in parallel with Phase 1-2).

### Phase 5: Plugin Instrumentation — New tracing.py Modules

**Goal**: Create `tracing.py` modules for all 15 uninstrumented/partially-instrumented plugins.

This is the largest phase. Each plugin needs:
1. `tracing.py` with: `TRACER_NAME`, semantic attribute constants, `get_tracer()`, domain context manager
2. `plugin.py` modifications to use the context manager
3. `tracer_name` property override on the plugin class

**Sub-phases by plugin category**:

#### 5A: Alert Plugins (4 plugins — alertmanager, email, slack, webhook)

Shared pattern — `alert_span()` context manager:
```python
TRACER_NAME = "floe.alert.{type}"
ATTR_CHANNEL = "alert.channel"
ATTR_DESTINATION = "alert.destination"
ATTR_DELIVERY_STATUS = "alert.delivery_status"
```

#### 5B: Security/RBAC Plugins (network-security-k8s, rbac-k8s)

`security_span()` context manager:
```python
TRACER_NAME = "floe.security.{type}"
ATTR_POLICY_TYPE = "security.policy_type"
ATTR_RESOURCE_COUNT = "security.resource_count"
```

#### 5C: Secrets Plugins (secrets-k8s, extract secrets-infisical)

`secrets_span()` context manager:
```python
TRACER_NAME = "floe.secrets.{type}"
ATTR_PROVIDER = "secrets.provider"
ATTR_KEY_NAME = "secrets.key_name"
# MUST NOT include secret values
```

#### 5D: Quality Plugins (extract quality-dbt, extract quality-gx)

`quality_span()` context manager:
```python
TRACER_NAME = "floe.quality.{type}"
ATTR_CHECK_NAME = "quality.check_name"
ATTR_ROWS_CHECKED = "quality.rows_checked"
ATTR_PASS_COUNT = "quality.pass_count"
```

#### 5E: Compute/Orchestrator/Lineage/DBT/Identity (remaining 5)

Each gets its domain-specific context manager:
- `compute_span()` for floe-compute-duckdb
- `orchestrator_span()` for floe-orchestrator-dagster
- `lineage_span()` for floe-lineage-marquez
- `dbt_fusion_span()` for floe-dbt-fusion
- `identity_span()` for floe-identity-keycloak (extract from plugin.py inline tracing)

**Dependency**: Phase 1 (sanitize_error_message for error recording).

### Phase 6: Sanitize Existing raw record_exception() Calls

**Goal**: Replace all raw `span.record_exception(e)` calls with sanitized error recording.

**Files** (modify ~12 files):
- `packages/floe-core/src/floe_core/telemetry/tracing.py` — create_span error handling
- `packages/floe-core/src/floe_core/rbac/generator.py`
- `packages/floe-core/src/floe_core/oci/verification.py`
- `packages/floe-core/src/floe_core/oci/metrics.py`
- `packages/floe-core/src/floe_core/oci/attestation.py`
- `packages/floe-iceberg/src/floe_iceberg/_compaction_manager.py`
- `packages/floe-iceberg/src/floe_iceberg/telemetry.py`
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py`
- `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py`
- `plugins/floe-dbt-core/src/floe_dbt_core/tracing.py`
- `plugins/floe-semantic-cube/src/floe_semantic_cube/tracing.py`
- `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`

**Pattern replacement**:
```python
# Before:
span.record_exception(e)

# After:
from floe_core.telemetry.sanitization import sanitize_error_message
span.set_attribute("exception.type", type(e).__name__)
span.set_attribute("exception.message", sanitize_error_message(str(e)))
```

**Dependency**: Phase 1 (sanitize_error_message must exist).

### Phase 7: Instrumentation Audit in Compilation

**Goal**: Add `verify_plugin_instrumentation()` and wire it into the compile pipeline.

**Files**:
- **NEW**: `packages/floe-core/src/floe_core/telemetry/audit.py`
  - `verify_plugin_instrumentation(plugins: list[PluginMetadata]) -> list[str]` — returns list of warning messages
  - Iterates plugins, checks `tracer_name is not None`
  - Skips telemetry backends (console, jaeger) by plugin type
- **MODIFY**: `packages/floe-core/src/floe_core/compilation/stages.py`
  - In ENFORCE stage, after sink whitelist validation, call `verify_plugin_instrumentation()`
  - Emit structured `logger.warning("uninstrumented_plugin", ...)` for each gap
- **NEW**: `packages/floe-core/tests/unit/compilation/test_instrumentation_audit.py`

**Tests**:
- All plugins instrumented → zero warnings
- One plugin uninstrumented → warning with plugin name and type
- Telemetry backends skipped → no warning for console/jaeger
- Audit callable programmatically (not just in compile pipeline)

**Dependency**: Phase 4 (tracer_name on PluginMetadata).

### Phase 8: Contract Test + Benchmark

**Goal**: Add contract test for instrumentation completeness and extend performance benchmark.

**Files**:
- **NEW**: `tests/contract/test_plugin_instrumentation_contract.py`
  - Load all registered plugins via entry points
  - Assert 19 of 21 have non-None `tracer_name`
  - Assert each tracer_name follows `"floe.{category}.{implementation}"` convention
- **MODIFY**: `benchmarks/test_tracing_perf.py`
  - Add benchmark for overhead of `@traced` with `attributes_fn`
  - Add benchmark comparing sanitized vs raw error recording

**Dependency**: Phases 4, 5 (all plugins must have tracer_name).

### Phase 9: Test Coverage for All New Tracing Modules

**Goal**: Every new `tracing.py` module has a corresponding `test_tracing.py`.

Each test file follows this pattern:
```python
@pytest.fixture
def tracer_with_exporter() -> Generator[...]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    # Inject tracer for the specific plugin module
    yield provider, exporter

class TestDomainSpan:
    @pytest.mark.requirement("6C-FR-XXX")
    def test_span_created_with_correct_name(self): ...
    def test_span_has_domain_attributes(self): ...
    def test_span_records_success_status(self): ...
    def test_span_records_error_with_sanitized_message(self): ...
    def test_span_does_not_include_secrets(self): ...
```

**Dependency**: Phases 1, 5 (tracing modules must exist).

## Dependency Graph

```
Phase 1 (sanitization)
  ├──► Phase 2 (unified @traced)
  │       └──► Phase 3 (iceberg migration)
  ├──► Phase 5 (new tracing.py modules)
  │       └──► Phase 9 (tests for new modules)
  └──► Phase 6 (sanitize existing calls)

Phase 4 (tracer_name property)  [parallel with 1-2]
  ├──► Phase 7 (audit in compilation)
  └──► Phase 8 (contract test + benchmark)

Phase 5 + Phase 4 ──► Phase 8 (contract test needs both)
All Phases ──► Phase 9 (final test sweep)
```

## Files Summary

| File | Phases | Changes |
|------|--------|---------|
| `floe_core/telemetry/sanitization.py` | 1 | **NEW** — promoted `sanitize_error_message()` |
| `floe_core/telemetry/tracing.py` | 2, 6 | Add `attributes_fn`, sanitized errors in `@traced` and `create_span` |
| `floe_core/telemetry/audit.py` | 7 | **NEW** — `verify_plugin_instrumentation()` |
| `floe_core/plugin_metadata.py` | 4 | Add optional `tracer_name` property |
| `floe_core/compilation/stages.py` | 7 | Wire audit into ENFORCE stage |
| `floe_iceberg/telemetry.py` | 3 | Remove local `@traced`, import unified |
| 15 plugin `tracing.py` files | 5 | **NEW** — domain context managers |
| 4 existing plugin `tracing.py` files | 6 | Sanitized error recording |
| ~8 core/plugin files with raw record_exception | 6 | Replace with sanitized pattern |
| 19 plugin `test_tracing.py` files | 9 | **NEW** — InMemorySpanExporter tests |
| 4 core test files | 1, 2, 4, 7 | **NEW** — sanitization, unified traced, metadata, audit |
| 1 contract test | 8 | **NEW** — instrumentation completeness |
| 1 benchmark file | 8 | Extended with overhead tests |

**Total**: ~22 new files, ~20 modified files, ~0 deleted files

## Verification

After all phases:

```bash
# 1. Run all Epic 6C tests
pytest packages/floe-core/tests/unit/test_telemetry/ \
       packages/floe-core/tests/unit/test_plugin_metadata_tracer.py \
       packages/floe-core/tests/unit/compilation/test_instrumentation_audit.py \
       plugins/*/tests/unit/test_tracing.py \
       tests/contract/test_plugin_instrumentation_contract.py -v

# 2. Type check modified files
mypy --strict packages/floe-core/src/floe_core/telemetry/ \
              packages/floe-core/src/floe_core/plugin_metadata.py \
              packages/floe-iceberg/src/floe_iceberg/telemetry.py

# 3. Lint check
ruff check packages/floe-core/src/ plugins/*/src/

# 4. Verify zero raw record_exception calls remain outside sanitization
# (Should only appear inside sanitize_error_message or test mocks)
rg "span\.record_exception" --type py -l | grep -v test | grep -v sanitization

# 5. Verify all plugins have tracer_name
pytest tests/contract/test_plugin_instrumentation_contract.py -v

# 6. Run benchmark
pytest benchmarks/test_tracing_perf.py -v --benchmark-only

# 7. Full unit test suite (regression check)
make test-unit
```

## Complexity Tracking

> No constitution violations. All work fits within existing architecture.

| Aspect | Justification |
|--------|--------------|
| 15 new tracing.py files | Each is ~60-80 lines following the established pattern. Templatable. |
| New module `sanitization.py` | Promotion of existing private code, not new functionality |
| PluginMetadata change | Additive optional property — no breaking change |
| Compilation pipeline hook | Follows established pattern (sink whitelist validation) |
