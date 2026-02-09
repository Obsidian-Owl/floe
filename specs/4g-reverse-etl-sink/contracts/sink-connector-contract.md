# Contract: SinkConnector ABC Interface

**Version**: 1.0.0
**Package**: floe-core
**Module**: `floe_core.plugins.sink`

## ABC Definition

```python
class SinkConnector(ABC):
    """Must have exactly 4 abstract methods."""

    @abstractmethod
    def list_available_sinks(self) -> list[str]: ...

    @abstractmethod
    def create_sink(self, config: SinkConfig) -> Any: ...

    @abstractmethod
    def write(self, sink: Any, data: Any, **kwargs: Any) -> EgressResult: ...

    @abstractmethod
    def get_source_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]: ...
```

## Stability Guarantees

- **MUST** have exactly 4 abstract methods (no more, no fewer)
- **MUST** be importable from `floe_core.plugins`
- **MUST NOT** inherit from `PluginMetadata` or `IngestionPlugin`
- **MUST** work as standalone ABC (no forced inheritance)
- **MUST** work as mixin with `IngestionPlugin`

## Dataclass Contracts

### SinkConfig Fields (stable)

| Field | Type | Required |
|-------|------|----------|
| sink_type | str | Yes |
| connection_config | dict[str, Any] | No (default {}) |
| field_mapping | dict[str, str] \| None | No |
| retry_config | dict[str, Any] \| None | No |
| batch_size | int \| None | No |

### EgressResult Fields (stable)

| Field | Type | Required |
|-------|------|----------|
| success | bool | Yes |
| rows_delivered | int | No (default 0) |
| bytes_transmitted | int | No (default 0) |
| duration_seconds | float | No (default 0.0) |
| checksum | str | No (default "") |
| delivery_timestamp | str | No (default "") |
| idempotency_key | str | No (default "") |
| destination_record_ids | list[str] | No (default []) |
| errors | list[str] | No (default []) |

## Versioning Rules

- Adding optional fields to SinkConfig/EgressResult: MINOR bump
- Removing fields or changing types: MAJOR bump (breaking)
- Adding abstract methods to SinkConnector: MAJOR bump (breaking)
