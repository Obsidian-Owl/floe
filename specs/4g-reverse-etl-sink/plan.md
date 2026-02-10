# Implementation Plan: Epic 4G — Reverse ETL (SinkConnector)

**Branch**: `4g-reverse-etl-sink` | **Date**: 2026-02-10 | **Spec**: `specs/4g-reverse-etl-sink/spec.md`
**Input**: Feature specification from `/specs/4g-reverse-etl-sink/spec.md`

## Summary

Add the `SinkConnector` opt-in ABC mixin to the floe plugin system, enabling plugins to push curated data from the Iceberg Gold layer to external SaaS APIs and databases. The default implementation uses dlt's `@dlt.destination` decorator via the existing `DltIngestionPlugin`. This is a **mixin, not a new plugin type** — zero breaking changes to existing code, schemas, or the 12 plugin type count.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: pydantic>=2.0, pyarrow, dlt[iceberg]>=1.20.0, structlog>=24.0, opentelemetry-api>=1.0, tenacity>=8.0
**Storage**: Iceberg Gold layer tables (read-side via Polaris catalog)
**Testing**: pytest (unit + contract + integration)
**Target Platform**: Linux (K8s-native)
**Project Type**: Monorepo (floe-core + floe-ingestion-dlt plugin)
**Performance Goals**: Write operations complete within 5s for datasets ≤1000 rows (SC-007)
**Constraints**: Full backwards compatibility, no breaking changes to existing schemas/contracts
**Scale/Scope**: ABC + 1 implementation (dlt), optional floe.yaml schema, governance whitelist

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (SinkConnector ABC in floe-core, dlt impl in floe-ingestion-dlt)
- [x] No SQL parsing/validation in Python (dbt owns SQL — not relevant to egress)
- [x] No orchestration logic outside floe-dagster (egress scheduling deferred to Epic 4B)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC mixin)
- [x] Plugin registered via entry point (reuses existing `floe.ingestion` entry point — no new entry point)
- [x] PluginMetadata declares name, version, floe_api_version (inherited via IngestionPlugin)

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg as source format, OTel for tracing)
- [x] Pluggable choices documented in manifest.yaml (approved_sinks whitelist)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (destinations NOT compiled into artifacts in this epic — per assumption)
- [x] Pydantic v2 for schema validation models (DestinationConfig); dataclasses for runtime DTOs (SinkConfig, EgressResult) per IngestionConfig/IngestionResult pattern
- [x] Contract changes follow versioning rules (additive only = MINOR bump)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (SinkConfig, DestinationConfig)
- [x] Credentials use SecretStr (connection_secret_ref pattern, no hardcoded creds)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest → floe.yaml → runtime)
- [x] Layer ownership respected (Platform Team owns approved_sinks, Data Team owns destinations)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (egress_span context manager, ATTR_SINK_* attributes)
- [x] OpenLineage events for data transformations (deferred — egress is data movement, not transformation)

## Project Structure

### Documentation (this feature)

```text
specs/4g-reverse-etl-sink/
├── plan.md              # This file
├── spec.md              # Feature specification (18 FRs, 4 user stories)
├── checklists/
│   └── requirements.md  # Quality checklist (24/24 PASS)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# floe-core: ABC + dataclasses + schema changes
packages/floe-core/src/floe_core/
├── plugins/
│   ├── sink.py                          # NEW: SinkConnector ABC, SinkConfig, EgressResult
│   └── __init__.py                      # MODIFY: Add sink exports
├── schemas/
│   ├── floe_spec.py                     # MODIFY: Add DestinationConfig + destinations field
│   ├── manifest.py                      # MODIFY: Add approved_sinks field
│   └── plugins.py                       # MODIFY: Add SinkWhitelistError + validate fn

# floe-ingestion-dlt: dlt SinkConnector implementation
plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/
├── plugin.py                            # MODIFY: Add SinkConnector mixin to DltIngestionPlugin
├── errors.py                            # MODIFY: Add SinkConnectionError, SinkWriteError, SinkConfigurationError
├── tracing.py                           # MODIFY: Add ATTR_SINK_* constants, egress_span(), record_egress_result()

# Tests
packages/floe-core/tests/unit/
├── test_sink_connector.py               # NEW: ABC enforcement, isinstance detection, dataclass validation
├── test_floe_spec_destinations.py       # NEW: DestinationConfig schema validation
├── test_manifest_approved_sinks.py      # NEW: Governance whitelist validation

plugins/floe-ingestion-dlt/tests/unit/
├── test_dlt_sink_connector.py           # NEW: dlt SinkConnector method tests
├── test_dlt_sink_tracing.py             # NEW: OTel span tests
├── test_dlt_sink_errors.py              # NEW: Error handling tests

tests/contract/
├── test_sink_connector_contract.py      # NEW: ABC stability, cross-package interface
├── test_egress_schema_contract.py       # NEW: DestinationConfig + SinkConfig schema stability
```

**Structure Decision**: Monorepo with modifications to 2 existing packages (floe-core, floe-ingestion-dlt). One new source file (`sink.py`), multiple modified files, ~12 new test files across unit/contract tiers.

---

## Phase 1: SinkConnector ABC + Data Models (floe-core)

**Goal**: Define the SinkConnector mixin ABC, SinkConfig dataclass, and EgressResult dataclass in `floe-core`. This is the foundation — all subsequent phases build on it.

**Covers**: FR-001, FR-002, FR-003, FR-004, FR-014, FR-015

### Files Created/Modified

**NEW: `packages/floe-core/src/floe_core/plugins/sink.py`**

Mirror the structure of `ingestion.py`:

- `SinkConfig` dataclass:
  - `sink_type: str` — identifier (e.g., "rest_api", "sql_database")
  - `connection_config: dict[str, Any]` — destination-specific config
  - `field_mapping: dict[str, str] | None = None` — column name translation (FR-014)
  - `retry_config: dict[str, Any] | None = None` — retry policy config
  - `batch_size: int | None = None` — auto-chunking (None = all rows at once)

- `EgressResult` dataclass:
  - `success: bool`
  - `rows_delivered: int = 0`
  - `bytes_transmitted: int = 0`
  - `duration_seconds: float = 0.0`
  - `checksum: str = ""` — SHA-256 of payload
  - `delivery_timestamp: str = ""` — ISO-8601 datetime
  - `idempotency_key: str = ""` — for retry deduplication
  - `destination_record_ids: list[str] = field(default_factory=list)` — IDs from destination API
  - `errors: list[str] = field(default_factory=list)`

- `SinkConnector(ABC)` — standalone mixin (NOT inheriting from PluginMetadata or IngestionPlugin):
  - `list_available_sinks() -> list[str]` — abstract
  - `create_sink(config: SinkConfig) -> Any` — abstract
  - `write(sink: Any, data: Any, **kwargs: Any) -> EgressResult` — abstract (data is pyarrow.Table at runtime, typed as Any to avoid hard dep)
  - `get_source_config(catalog_config: dict[str, Any]) -> dict[str, Any]` — abstract

**MODIFY: `packages/floe-core/src/floe_core/plugins/__init__.py`**

Add imports and exports:
```python
# Sink/Egress plugin (Epic 4G)
from floe_core.plugins.sink import (
    EgressResult,
    SinkConfig,
    SinkConnector,
)
```

Add to `__all__`: `"SinkConnector"`, `"SinkConfig"`, `"EgressResult"`

### Tests

**NEW: `packages/floe-core/tests/unit/test_sink_connector.py`**

- Test ABC enforcement: class inheriting SinkConnector without implementing methods raises TypeError
- Test standalone usage: SinkConnector works without IngestionPlugin (FR-015)
- Test mixin usage: class(IngestionPlugin, SinkConnector) works, isinstance() returns True for both
- Test isinstance detection: plain IngestionPlugin returns False for isinstance(_, SinkConnector) (FR-004)
- Test SinkConfig defaults and validation
- Test EgressResult defaults and field types
- Test EgressResult with empty rows (edge case: rows_delivered=0 is valid)

---

## Phase 2: dlt SinkConnector Implementation (floe-ingestion-dlt)

**Goal**: Make `DltIngestionPlugin` implement the `SinkConnector` mixin, gaining bidirectional data movement.

**Covers**: FR-005, FR-006, FR-007, FR-008, FR-009, FR-010, FR-013, FR-016

### Files Modified

**MODIFY: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`**

- Change class declaration: `class DltIngestionPlugin(IngestionPlugin, SinkConnector):`
- Implement 4 abstract methods:
  - `list_available_sinks()` → returns `["rest_api", "sql_database"]` minimum (FR-006)
  - `create_sink(config: SinkConfig)` → creates dlt destination from config (FR-007)
  - `write(sink, data, **kwargs)` → pushes Arrow table, auto-chunks by batch_size, returns EgressResult (FR-008)
  - `get_source_config(catalog_config)` → returns Iceberg Gold layer read config via Polaris (FR-009)
- `write()` handles:
  - Auto-chunking when `batch_size` is set
  - Rate limiting via configurable backoff (tenacity)
  - Empty dataset → EgressResult(rows_delivered=0, success=True)
  - SHA-256 checksum of delivered payload
  - Idempotency key generation
  - Structured error reporting (FR-013)

**MODIFY: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/errors.py`**

Add new error classes following existing pattern (ErrorCategory enum already exists):
- `SinkConnectionError` — destination unreachable, authentication failure
- `SinkWriteError` — write operation failed (rate limit, timeout, partial failure)
- `SinkConfigurationError` — invalid sink config (bad sink_type, missing fields)

**MODIFY: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py`**

Add egress-specific OTel instrumentation (FR-010):
- Constants: `ATTR_SINK_TYPE`, `ATTR_SINK_DESTINATION`, `ATTR_SINK_ROWS_WRITTEN`, `ATTR_SINK_DURATION_MS`, `ATTR_SINK_STATUS`
- `egress_span(tracer, operation, sink_type)` — context manager mirroring `ingestion_span()`
- `record_egress_result(span, result: EgressResult)` — sets span attributes from result
- `record_egress_error(span, error: Exception)` — records error on span

### Tests

**NEW: `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_connector.py`**

- Test `isinstance(DltIngestionPlugin(...), SinkConnector)` → True
- Test `list_available_sinks()` returns list with ≥2 entries
- Test `create_sink()` with valid SinkConfig
- Test `create_sink()` with invalid config → SinkConfigurationError
- Test `write()` with mock data → EgressResult with correct metrics
- Test `write()` with empty Arrow table → success, rows_delivered=0
- Test `write()` with batch_size auto-chunking
- Test `get_source_config()` returns valid Iceberg read config

**NEW: `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_tracing.py`**

- Test egress_span creates span with correct name and attributes
- Test record_egress_result sets all expected attributes
- Test record_egress_error sets error status

**NEW: `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_errors.py`**

- Test SinkConnectionError includes sink_type and message
- Test SinkWriteError includes retry count and HTTP status
- Test SinkConfigurationError includes config details

---

## Phase 3: FloeSpec `destinations:` Schema (floe-core)

**Goal**: Add optional `destinations:` section to `floe.yaml` schema for declaring reverse ETL targets.

**Covers**: FR-011, FR-012, FR-018

### Files Modified

**MODIFY: `packages/floe-core/src/floe_core/schemas/floe_spec.py`**

Add new Pydantic model:

```python
class DestinationConfig(BaseModel):
    """Configuration for a reverse ETL destination in floe.yaml."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str  # Destination name (identifier)
    sink_type: str  # Must match a SinkConnector-supported type
    connection_secret_ref: str  # K8s Secret name (FR-018)
    source_table: str | None = None  # Optional Iceberg Gold table
    config: dict[str, Any] | None = None  # Destination-specific config
    field_mapping: dict[str, str] | None = None  # Column name translation
    batch_size: int | None = None  # Optional batch size override
```

Add to `FloeSpec`:
```python
destinations: list[DestinationConfig] | None = Field(
    default=None,
    description="Optional reverse ETL destinations (Epic 4G)",
)
```

Key constraints:
- `connection_secret_ref` uses existing `SECRET_NAME_PATTERN` from `floe_core.schemas.secrets`
- Hardcoded credentials rejected by forbidding them via `extra="forbid"` + `FORBIDDEN_ENVIRONMENT_FIELDS` check
- Fully optional (FR-012) — `None` default means existing floe.yaml files validate unchanged

### Tests

**NEW: `packages/floe-core/tests/unit/test_floe_spec_destinations.py`**

- Test FloeSpec with destinations validates correctly
- Test FloeSpec WITHOUT destinations validates (backwards compatibility, FR-012)
- Test DestinationConfig with all required fields
- Test DestinationConfig with invalid sink_type (still validates at schema level — whitelist check is in compiler/manifest)
- Test DestinationConfig rejects hardcoded credentials (connection_string, password etc.)
- Test DestinationConfig with field_mapping and batch_size
- Test duplicate destination names

---

## Phase 4: Manifest Governance — approved_sinks Whitelist

**Goal**: Platform engineers can restrict which sink types data engineers target.

**Covers**: FR-017

### Files Modified

**MODIFY: `packages/floe-core/src/floe_core/schemas/manifest.py`**

Add field to `PlatformManifest`:
```python
approved_sinks: list[str] | None = Field(
    default=None,
    description="Enterprise whitelist of approved sink types for reverse ETL",
)
```

Follows same pattern as `approved_plugins`. Scope constraint: only valid for `scope="enterprise"` (add check to `validate_scope_constraints`).

**MODIFY: `packages/floe-core/src/floe_core/schemas/plugins.py`**

Add new error class mirroring `PluginWhitelistError`:
```python
class SinkWhitelistError(Exception):
    """Raised when a sink type violates the enterprise whitelist."""
    def __init__(self, sink_type: str, approved_sinks: list[str]) -> None: ...
```

Add validation function mirroring `validate_domain_plugin_whitelist`:
```python
def validate_sink_whitelist(
    sink_type: str,
    approved_sinks: list[str],
) -> None:
    """Validate that a sink type is within the approved whitelist."""
```

### Tests

**NEW: `packages/floe-core/tests/unit/test_manifest_approved_sinks.py`**

- Test approved_sinks field validates on PlatformManifest
- Test approved_sinks=None means all sinks allowed (backwards compatible)
- Test approved_sinks only valid for scope="enterprise"
- Test SinkWhitelistError raised for unapproved sink type
- Test SinkWhitelistError not raised for approved sink type
- Test validate_sink_whitelist with empty whitelist

---

## Phase 5: Contract Tests + Integration Wiring

**Goal**: Ensure cross-package contract stability and integration correctness.

**Covers**: SC-004, SC-005, SC-006

### Files Created

**NEW: `tests/contract/test_sink_connector_contract.py`**

- Test SinkConnector ABC is importable from `floe_core.plugins`
- Test SinkConfig is importable from `floe_core.plugins`
- Test EgressResult is importable from `floe_core.plugins`
- Test SinkConnector has exactly 4 abstract methods
- Test a mock class implementing SinkConnector + IngestionPlugin satisfies both interfaces
- Test schema stability: SinkConfig and EgressResult fields match expected contract

**NEW: `tests/contract/test_egress_schema_contract.py`**

- Test DestinationConfig schema matches expected fields
- Test FloeSpec JSON schema includes optional destinations
- Test PlatformManifest JSON schema includes optional approved_sinks
- Test backwards compatibility: existing FloeSpec fixtures validate without destinations

---

## Dependency Order

```
Phase 1 (ABC + data models)
    ↓
Phase 2 (dlt implementation)  ←── depends on Phase 1 (imports SinkConnector)
    ↓
Phase 3 (FloeSpec schema)     ←── independent of Phase 2 (could parallelize)
    ↓
Phase 4 (Manifest governance) ←── independent of Phase 2/3 (could parallelize)
    ↓
Phase 5 (Contract tests)      ←── depends on all prior phases
```

Phases 3 and 4 can be parallelized after Phase 1.

## Complexity Tracking

> No Constitution Check violations. All phases align with established patterns.

| Decision | Rationale |
|----------|-----------|
| New file `sink.py` instead of extending `ingestion.py` | Separation of concerns — SinkConnector is independently implementable (FR-015) and should not clutter the ingestion module |
| `data: Any` in write() signature | Avoids hard pyarrow dependency in floe-core ABC. Runtime type is pyarrow.Table, documented in docstring. Same pattern as `create_pipeline() -> Any` in IngestionPlugin |
| Dataclasses (not Pydantic) for SinkConfig/EgressResult | Mirrors IngestionConfig/IngestionResult pattern in existing `ingestion.py`. These are runtime DTOs, not schema validation models |
| DestinationConfig as Pydantic model | This IS a schema validation model (part of FloeSpec), so Pydantic is correct here |
