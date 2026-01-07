# TelemetryBackendPlugin

**Purpose**: Pluggable OTLP backends for traces, metrics, and logs
**Location**: `floe_core/interfaces/telemetry.py`
**Entry Point**: `floe.telemetry_backends`
**ADR**: [ADR-0035: Observability Plugin Interface](../adr/0035-observability-plugin-interface.md)

TelemetryBackendPlugin separates telemetry collection (OpenTelemetry SDK, enforced) from backend storage/visualization (pluggable). This enables organizations to use existing observability infrastructure while maintaining standardized telemetry emission.

> **Note**: OpenTelemetry instrumentation is **enforced** across all floe components. This plugin only controls where telemetry data is sent.

## Interface Definition

```python
from abc import ABC, abstractmethod
from typing import Any

class TelemetryBackendPlugin(ABC):
    """Plugin interface for OTLP telemetry backends.

    Configure backends for storing and visualizing OpenTelemetry
    traces, metrics, and logs.
    """

    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector exporter configuration.

        Returns:
            Dictionary containing OTLP exporter config for the backend.
            Example for Datadog:
            {
                "exporters": {
                    "datadog": {
                        "api": {"key": "${env:DD_API_KEY}"},
                        "site": "datadoghq.com"
                    }
                }
            }
        """
        pass

    @abstractmethod
    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate Helm values for deploying backend services.

        Returns:
            Dictionary with Helm chart values for backend services.
            Example for Jaeger:
            {
                "jaeger": {
                    "enabled": true,
                    "collector": {"service": {"type": "ClusterIP"}},
                    "query": {"service": {"type": "LoadBalancer"}}
                }
            }
        """
        pass
```

## Reference Implementations

| Plugin | Description | Self-Hosted |
|--------|-------------|-------------|
| `JaegerTelemetryPlugin` | Local/self-hosted observability (default) | Yes |
| `DatadogTelemetryPlugin` | SaaS APM and distributed tracing | No |
| `GrafanaCloudTelemetryPlugin` | Managed Grafana + Tempo + Loki | No |

## Related Documents

- [ADR-0035: Observability Plugin Interface](../adr/0035-observability-plugin-interface.md)
- [Plugin Architecture](../plugin-system/index.md)
- [LineageBackendPlugin](lineage-backend-plugin.md) - Companion observability plugin
