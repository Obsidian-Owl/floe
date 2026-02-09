# Data Model: Epic 4G — Reverse ETL (SinkConnector)

**Feature**: Reverse ETL (SinkConnector)
**Date**: 2026-02-10

## Entities

### SinkConnector (ABC Mixin)

**Location**: `packages/floe-core/src/floe_core/plugins/sink.py`
**Type**: Abstract Base Class (standalone mixin)
**Inherits from**: `ABC` (NOT PluginMetadata — FR-015)

| Method | Type | Signature | Description |
|--------|------|-----------|-------------|
| `list_available_sinks` | abstract | `() -> list[str]` | Returns supported sink type identifiers |
| `create_sink` | abstract | `(config: SinkConfig) -> Any` | Creates configured destination object |
| `write` | abstract | `(sink: Any, data: Any, **kwargs: Any) -> EgressResult` | Pushes data to destination |
| `get_source_config` | abstract | `(catalog_config: dict[str, Any]) -> dict[str, Any]` | Returns Iceberg Gold read config |

**Relationships**:
- Used as mixin with `IngestionPlugin` (e.g., `DltIngestionPlugin(IngestionPlugin, SinkConnector)`)
- Also usable standalone (any class can implement SinkConnector independently)
- Runtime detection via `isinstance(plugin, SinkConnector)`

---

### SinkConfig (Dataclass)

**Location**: `packages/floe-core/src/floe_core/plugins/sink.py`
**Type**: `@dataclass`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sink_type` | `str` | (required) | Sink identifier (e.g., "rest_api", "sql_database") |
| `connection_config` | `dict[str, Any]` | `{}` | Destination-specific connection configuration |
| `field_mapping` | `dict[str, str] \| None` | `None` | Source-to-destination column name translation |
| `retry_config` | `dict[str, Any] \| None` | `None` | Retry policy configuration |
| `batch_size` | `int \| None` | `None` | Auto-chunking size (None = all rows at once) |

**Validation**: Runtime validation in implementation, not in dataclass itself (mirrors IngestionConfig pattern).

---

### EgressResult (Dataclass)

**Location**: `packages/floe-core/src/floe_core/plugins/sink.py`
**Type**: `@dataclass`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `success` | `bool` | (required) | Whether the egress operation succeeded |
| `rows_delivered` | `int` | `0` | Number of rows delivered to destination |
| `bytes_transmitted` | `int` | `0` | Bytes transmitted to destination |
| `duration_seconds` | `float` | `0.0` | Execution duration in seconds |
| `checksum` | `str` | `""` | SHA-256 checksum of delivered payload |
| `delivery_timestamp` | `str` | `""` | ISO-8601 delivery timestamp |
| `idempotency_key` | `str` | `""` | Key for retry deduplication |
| `destination_record_ids` | `list[str]` | `[]` | IDs returned by destination API |
| `errors` | `list[str]` | `[]` | Error messages if failed |

**Mirrors**: `IngestionResult` structure with additional load-assurance fields.

---

### DestinationConfig (Pydantic Model)

**Location**: `packages/floe-core/src/floe_core/schemas/floe_spec.py`
**Type**: `BaseModel` with `ConfigDict(frozen=True, extra="forbid")`

| Field | Type | Default | Validation | Description |
|-------|------|---------|------------|-------------|
| `name` | `str` | (required) | min_length=1, max_length=100 | Destination identifier |
| `sink_type` | `str` | (required) | min_length=1 | Sink type (e.g., "rest_api") |
| `connection_secret_ref` | `str` | (required) | SECRET_NAME_PATTERN, max_length=253 | K8s Secret reference |
| `source_table` | `str \| None` | `None` | | Iceberg Gold table path |
| `config` | `dict[str, Any] \| None` | `None` | | Destination-specific config |
| `field_mapping` | `dict[str, str] \| None` | `None` | | Column name translation |
| `batch_size` | `int \| None` | `None` | ge=1 | Batch size for auto-chunking |

**Validators**:
- `validate_name`: Alphanumeric + hyphens/underscores only
- `validate_connection_secret_ref`: Must match `SECRET_NAME_PATTERN`
- Model-level: Checked against `FORBIDDEN_ENVIRONMENT_FIELDS`

**Added to FloeSpec as**: `destinations: list[DestinationConfig] | None = Field(default=None)`

---

### SinkWhitelistError (Exception)

**Location**: `packages/floe-core/src/floe_core/schemas/plugins.py`
**Type**: Exception class

| Attribute | Type | Description |
|-----------|------|-------------|
| `sink_type` | `str` | The rejected sink type |
| `approved_sinks` | `list[str]` | List of approved sink types |

**Mirrors**: `PluginWhitelistError` structure.

---

## Entity Relationships

```
PlatformManifest (manifest.yaml)
├── approved_sinks: list[str] | None   ──validates──>  DestinationConfig.sink_type
└── governance: GovernanceConfig

FloeSpec (floe.yaml)
├── destinations: list[DestinationConfig] | None
│   ├── DestinationConfig
│   │   ├── connection_secret_ref  ──references──>  K8s Secret
│   │   └── sink_type  ──validated against──>  SinkConnector.list_available_sinks()
│   └── ...
└── transforms: list[TransformSpec]

SinkConnector (ABC Mixin)
├── SinkConfig  ──input to──>  create_sink(), write()
├── EgressResult  ──output of──>  write()
└── Implemented by: DltIngestionPlugin(IngestionPlugin, SinkConnector)
```

## State Transitions

### Egress Operation Lifecycle

```
IDLE -> CONFIGURING -> READY -> WRITING -> COMPLETED/FAILED
  |        |             |        |
  |        +-- SinkConfigurationError (invalid config)
  |                       |        +-- SinkWriteError (write failure)
  |                       |        +-- SinkConnectionError (dest unreachable)
  |                       +-- create_sink() success
  +-- list_available_sinks() / get_source_config()
```

### EgressResult States

| State | success | rows_delivered | errors |
|-------|---------|----------------|--------|
| Full success | `True` | `> 0` | `[]` |
| Empty dataset | `True` | `0` | `[]` |
| Partial failure | `False` | `> 0` | `["partial: N rows failed"]` |
| Complete failure | `False` | `0` | `["connection timeout", ...]` |
