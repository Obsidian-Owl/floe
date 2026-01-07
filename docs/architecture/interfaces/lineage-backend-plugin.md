# LineageBackendPlugin

**Purpose**: Pluggable OpenLineage backends for data lineage
**Location**: `floe_core/interfaces/lineage.py`
**Entry Point**: `floe.lineage_backends`
**ADR**: [ADR-0035: Observability Plugin Interface](../adr/0035-observability-plugin-interface.md)

LineageBackendPlugin separates lineage collection (OpenLineage events, enforced) from backend storage/visualization (pluggable). This enables integration with existing data catalogs and lineage tools.

> **Note**: OpenLineage event emission is **enforced** across all floe pipelines. This plugin only controls where lineage data is sent.

## Interface Definition

```python
from abc import ABC, abstractmethod
from typing import Any

class LineageBackendPlugin(ABC):
    """Plugin interface for OpenLineage backends.

    Configure backends for storing and visualizing data lineage graphs.
    """

    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def get_transport_config(self) -> dict[str, Any]:
        """Generate OpenLineage transport configuration.

        Returns:
            Dictionary containing OpenLineage transport config.
            Example for HTTP backend:
            {
                "type": "http",
                "url": "https://lineage.example.com/api/v1/lineage",
                "auth": {"type": "api_key", "api_key": "${LINEAGE_API_KEY}"}
            }
        """
        pass

    @abstractmethod
    def get_namespace_mapping(self) -> dict[str, str]:
        """Generate namespace mapping for lineage events.

        Returns:
            Dictionary mapping floe namespaces to lineage backend namespaces.
            Example:
            {
                "default": "floe_default",
                "analytics": "floe_analytics"
            }
        """
        pass
```

## Reference Implementations

| Plugin | Description | Self-Hosted |
|--------|-------------|-------------|
| `MarquezLineagePlugin` | Local/self-hosted lineage (default) | Yes |
| `AtlanLineagePlugin` | SaaS data catalog and governance | No |
| `OpenMetadataLineagePlugin` | Open-source data catalog | Yes |

## Related Documents

- [ADR-0035: Observability Plugin Interface](../adr/0035-observability-plugin-interface.md)
- [Plugin Architecture](../plugin-architecture.md)
- [TelemetryBackendPlugin](telemetry-backend-plugin.md) - Companion observability plugin
