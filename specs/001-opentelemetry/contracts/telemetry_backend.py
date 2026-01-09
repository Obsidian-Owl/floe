"""TelemetryBackendPlugin ABC (Contract Version: 1.0.0).

Abstract base class for pluggable telemetry backends.
Platform Teams select backend via manifest.yaml; Data Engineers inherit.

Layer 3 (Backend) is PLUGGABLE via this interface.
Layers 1 (Emission) and 2 (Collection) are ENFORCED.

Entry point: floe.telemetry_backends
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PluginMetadata(BaseModel):
    """Plugin metadata required by all TelemetryBackendPlugin implementations.

    Attributes:
        name: Plugin identifier (e.g., 'jaeger', 'datadog', 'grafana-cloud')
        version: Plugin version following semver
        floe_api_version: Compatible floe-core API version
        description: Human-readable plugin description

    Examples:
        >>> metadata = PluginMetadata(
        ...     name="jaeger",
        ...     version="1.0.0",
        ...     floe_api_version="2.0.0",
        ...     description="Jaeger distributed tracing backend",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Plugin identifier (lowercase, hyphen-separated)",
    )
    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+.*$",
        description="Plugin version (semver)",
    )
    floe_api_version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+.*$",
        description="Compatible floe-core API version",
    )
    description: str = Field(
        default="",
        max_length=256,
        description="Human-readable plugin description",
    )


class TelemetryBackendPlugin(ABC):
    """Abstract base class for pluggable OTLP telemetry backends.

    Layer 3 (Backend) is PLUGGABLE via this interface.
    Platform teams select backend via manifest.yaml.

    Entry point: floe.telemetry_backends

    Implementations:
        - JaegerTelemetryPlugin: Self-hosted Jaeger
        - DatadogTelemetryPlugin: Datadog SaaS
        - GrafanaCloudTelemetryPlugin: Grafana Cloud SaaS
        - ConsoleTelemetryPlugin: Local development (stdout)

    Examples:
        >>> class JaegerTelemetryPlugin(TelemetryBackendPlugin):
        ...     @property
        ...     def metadata(self) -> PluginMetadata:
        ...         return PluginMetadata(
        ...             name="jaeger",
        ...             version="1.0.0",
        ...             floe_api_version="2.0.0",
        ...         )
        ...
        ...     def get_otlp_exporter_config(self) -> dict[str, Any]:
        ...         return {
        ...             "otlp/jaeger": {
        ...                 "endpoint": "jaeger-collector:4317",
        ...                 "tls": {"insecure": True},
        ...             }
        ...         }
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata.

        Returns:
            PluginMetadata with name, version, and floe_api_version.
        """
        ...

    @abstractmethod
    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector exporter configuration.

        Returns dictionary fragment for OTLP Collector config exporters section.
        The key should be unique (e.g., 'otlp/jaeger', 'otlp/datadog').

        Returns:
            Dictionary for OTLP Collector config exporters section.

        Examples:
            >>> plugin.get_otlp_exporter_config()
            {
                "otlp/jaeger": {
                    "endpoint": "jaeger-collector:4317",
                    "tls": {"insecure": True}
                }
            }
        """
        ...

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for backend deployment.

        Returns Helm values dictionary for deploying the backend.
        Returns empty dict for SaaS backends (Datadog, Grafana Cloud).

        Returns:
            Helm values dict. Empty for SaaS backends.

        Examples:
            >>> # Self-hosted backend
            >>> plugin.get_helm_values()
            {"jaeger": {"enabled": True, "allInOne": {"enabled": True}}}

            >>> # SaaS backend (no Helm deployment needed)
            >>> plugin.get_helm_values()
            {}
        """
        ...

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate backend connectivity.

        Performs health check to verify backend is reachable
        and credentials (if any) are valid.

        Returns:
            True if backend reachable and credentials valid.

        Raises:
            ConnectionError: If backend is unreachable.
            AuthenticationError: If credentials are invalid.
        """
        ...

    def get_pipeline_config(self) -> dict[str, Any]:
        """Generate OTLP Collector pipeline configuration.

        Default implementation creates standard traces/metrics/logs pipelines.
        Override for custom pipeline configurations.

        Returns:
            Dictionary for OTLP Collector config pipelines section.
        """
        exporter_name = list(self.get_otlp_exporter_config().keys())[0]
        return {
            "traces": {
                "receivers": ["otlp"],
                "processors": ["batch"],
                "exporters": [exporter_name],
            },
            "metrics": {
                "receivers": ["otlp"],
                "processors": ["batch"],
                "exporters": [exporter_name],
            },
            "logs": {
                "receivers": ["otlp"],
                "processors": ["batch"],
                "exporters": [exporter_name],
            },
        }
