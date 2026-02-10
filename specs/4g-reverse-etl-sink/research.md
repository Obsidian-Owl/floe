# Research: Epic 4G — Reverse ETL (SinkConnector)

**Feature**: Reverse ETL (SinkConnector)
**Date**: 2026-02-10
**Status**: Complete — all NEEDS CLARIFICATION resolved

## Prior Decisions

- **Option C: ABC Mixin** (scored 8.2/10) was selected during Epic 4F research over Option A (new plugin type, 6.1/10) and Option B (decorator pattern, 7.0/10). SinkConnector is an opt-in mixin, not a 12th plugin type.
- **PyArrow Table** as `write()` data format — matches Iceberg's native format, dlt supports natively.
- **Push-only delivery** — matches industry standard (Census, Hightouch, Fivetran).
- **Rich delivery receipt** — EgressResult mirrors IngestionResult symmetry with load-assurance fields.
- **Manifest whitelist** — `approved_sinks` follows `approved_plugins` pattern.

## Research Topics

### R1: IngestionPlugin ABC Pattern (RESOLVED)

**Question**: What patterns does the existing ingestion ABC follow?

**Finding**: `packages/floe-core/src/floe_core/plugins/ingestion.py` uses:
- `@dataclass` for DTOs (IngestionConfig, IngestionResult) — NOT Pydantic
- `class IngestionPlugin(PluginMetadata)` inherits from PluginMetadata ABC
- `@abstractmethod` with `...` ellipsis body
- Return type `Any` for pipeline objects (avoiding hard dependencies)
- `field(default_factory=lambda: [])` for mutable defaults

**Decision**: SinkConnector ABC will follow the exact same pattern:
- Dataclasses for SinkConfig and EgressResult (not Pydantic)
- Standalone ABC (not inheriting PluginMetadata) per FR-015
- `Any` return type for sink objects
- Same import/export pattern in `__init__.py`

### R2: DltIngestionPlugin Implementation Pattern (RESOLVED)

**Question**: How does the dlt plugin implement the ABC?

**Finding**: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`:
- Class: `class DltIngestionPlugin(IngestionPlugin)`
- State: `self._started: bool`, `self._dlt_version: str | None`
- Lifecycle: `startup()`, `shutdown()`, `health_check()`
- All methods check `if not self._started` before operating
- OTel: Every method wrapped in `ingestion_span()` context manager
- Error handling: Catches exceptions, categorizes with `categorize_error()`, logs with `record_ingestion_error()`

**Decision**: DltIngestionPlugin will add SinkConnector as a second mixin:
- `class DltIngestionPlugin(IngestionPlugin, SinkConnector):`
- SinkConnector methods will also check `self._started`
- SinkConnector methods will use `egress_span()` for OTel
- Existing ingestion behaviour unchanged

### R3: Error Class Hierarchy (RESOLVED)

**Question**: How are errors structured?

**Finding**: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/errors.py`:
- `ErrorCategory` enum: TRANSIENT, PERMANENT, PARTIAL, CONFIGURATION
- `IngestionError(Exception)` base with keyword-only `source_type`, `destination_table`, `pipeline_name`, `category`
- Context suffix auto-appended: `[source_type=X, destination_table=Y]`
- Subclasses override default `category` parameter

**Decision**: Add 3 new error classes following same pattern:
- `SinkConnectionError(IngestionError)` — default TRANSIENT
- `SinkWriteError(IngestionError)` — default TRANSIENT
- `SinkConfigurationError(IngestionError)` — default CONFIGURATION

### R4: OTel Tracing Pattern (RESOLVED)

**Question**: How is OpenTelemetry instrumentation structured?

**Finding**: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py`:
- `TRACER_NAME = "floe.ingestion.dlt"` constant
- `ATTR_*` constants for all span attributes (avoids typos)
- `@contextmanager ingestion_span()` — creates span, sets attributes, handles OK/ERROR status
- `record_ingestion_result(span, result)` — sets result attributes
- `record_ingestion_error(span, error)` — sets error attributes with truncation

**Decision**: Add egress-specific tracing mirroring this pattern:
- `ATTR_SINK_TYPE`, `ATTR_SINK_DESTINATION`, `ATTR_SINK_ROWS_WRITTEN`, `ATTR_SINK_DURATION_MS`, `ATTR_SINK_STATUS`
- `egress_span()` context manager
- `record_egress_result()`, `record_egress_error()`

### R5: FloeSpec Schema Extension (RESOLVED)

**Question**: How should destinations be added to FloeSpec?

**Finding**: FloeSpec uses `ConfigDict(frozen=True, extra="forbid")` with optional fields:
- `output_ports: list[OutputPort] | None = Field(default=None, alias="outputPorts")`
- `schedule: ScheduleSpec | None = Field(default=None)`
- `FORBIDDEN_ENVIRONMENT_FIELDS` recursive check prevents credentials

**Decision**: Add `DestinationConfig` Pydantic model and optional field:
- `destinations: list[DestinationConfig] | None = Field(default=None)`
- DestinationConfig uses `connection_secret_ref` (not raw credentials)
- Validates against `SECRET_NAME_PATTERN` from `floe_core.schemas.secrets`

### R6: Manifest Governance Pattern (RESOLVED)

**Question**: How does the manifest whitelist work?

**Finding**: `PlatformManifest` has:
- `approved_plugins: dict[str, list[str]] | None` — scope-constrained to enterprise
- `validate_scope_constraints()` model_validator enforces C004
- `PluginWhitelistError` exception with `category`, `plugin_type`, `approved_plugins` attributes
- `validate_domain_plugin_whitelist()` standalone function

**Decision**: Add `approved_sinks: list[str] | None` to PlatformManifest:
- Same scope constraint (enterprise only)
- New `SinkWhitelistError` exception mirroring PluginWhitelistError
- New `validate_sink_whitelist()` function

### R7: Test Patterns (RESOLVED)

**Question**: What test patterns are used for ABC and schema testing?

**Finding**:
- ABC tests: Instantiation with incomplete impl raises TypeError, complete impl succeeds
- Schema tests: Pydantic ValidationError expectations, frozen model enforcement
- Contract tests: `tests/contract/test_ingestion_plugin_abc.py` tests ABC definition stability
- All tests: `@pytest.mark.requirement()` markers, docstrings, type hints
- Fixtures: Factory pattern for mock entry points, sample configs

**Decision**: Follow these exact patterns for all new tests.

### R8: dlt @dlt.destination API (RESOLVED)

**Question**: How does dlt's destination decorator work?

**Finding**: dlt >= 1.20.0 supports custom destinations via `@dlt.destination()` decorator or `dlt.destination()` function. The decorator wraps a callable that receives items/batches and writes them to the target system.

**Decision**: `create_sink()` will use dlt's destination API to create a configured destination. The exact API usage will follow dlt's documentation at implementation time.

## Alternatives Considered

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| Plugin pattern | Mixin ABC | New plugin type | Zero breaking changes, no 12th type needed |
| Data format | PyArrow Table | Pandas DataFrame | Native Iceberg format, zero-copy, typed |
| Delivery model | Push only | Push + Pull | Industry standard, simpler, matches dlt |
| Governance | Manifest whitelist | Per-destination RBAC | Consistent with approved_plugins pattern |
| ABC location | New `sink.py` | Extend `ingestion.py` | FR-015: standalone implementable |
| Config DTOs | Dataclasses | Pydantic | Mirrors IngestionConfig/IngestionResult |
