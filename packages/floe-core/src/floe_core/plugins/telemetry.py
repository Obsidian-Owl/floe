"""TelemetryBackendPlugin ABC for telemetry backend plugins.

This module defines the abstract base class for telemetry plugins that
provide OTLP telemetry backend functionality. Telemetry plugins are
responsible for:
- Configuring OTLP Collector exporters for backend-specific protocols
- Providing Helm values for deploying self-hosted backends (Jaeger, etc.)
- Validating connectivity to the telemetry backend

Example:
    >>> from floe_core.plugins.telemetry import TelemetryBackendPlugin
    >>> class JaegerPlugin(TelemetryBackendPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "jaeger"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


class TelemetryBackendPlugin(PluginMetadata):
    """Abstract base class for OTLP telemetry backend plugins.

    TelemetryBackendPlugin extends PluginMetadata with telemetry-specific
    methods for configuring OTLP collectors and backends. Implementations
    include Jaeger, Datadog, and Grafana Cloud.

    The telemetry architecture follows a three-layer model:
    - Layer 1 (Enforced): OpenTelemetry SDK emission
    - Layer 2 (Enforced): OTLP Collector aggregation
    - Layer 3 (Pluggable): Backend storage/visualization (this plugin)

    Inherited from PluginMetadata (abstract properties):
        - name: Plugin identifier (e.g., 'jaeger', 'console', 'datadog')
        - version: Plugin version following semver (e.g., '1.0.0')
        - floe_api_version: Compatible floe-core API version (e.g., '1.0')

    Inherited from PluginMetadata (optional, with defaults):
        - description: Human-readable plugin description (default: "")
        - dependencies: List of plugin dependencies (default: [])
        - health_check(): Returns HealthStatus (default: HEALTHY)
        - startup(): Called on plugin initialization (default: no-op)
        - shutdown(): Called on plugin teardown (default: no-op)
        - get_config_schema(): Returns config JSON schema (default: None)

    Telemetry-specific abstract methods (MUST implement):
        - get_otlp_exporter_config(): Returns OTLP Collector exporter config
        - get_helm_values(): Returns Helm values for backend deployment
        - validate_connection(): Validates backend connectivity

    Example:
        >>> class JaegerPlugin(TelemetryBackendPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "jaeger"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     @property
        ...     def description(self) -> str:
        ...         return "Jaeger distributed tracing backend"
        ...
        ...     def get_otlp_exporter_config(self) -> dict:
        ...         return {
        ...             "exporters": {"jaeger": {"endpoint": "jaeger:14250"}},
        ...             "service": {"pipelines": {"traces": {"exporters": ["jaeger"]}}}
        ...         }

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
        - ADR-0035: Telemetry architecture
    """

    @abstractmethod
    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector exporter configuration.

        Creates the configuration for the OTLP Collector's exporter section
        that sends telemetry data to this backend.

        Returns:
            Dictionary matching OTLP Collector config schema, including:
                - exporters: Backend-specific exporter configuration
                - service.pipelines: Pipeline configuration for traces/metrics/logs

        Example:
            >>> config = plugin.get_otlp_exporter_config()
            >>> config
            {
                'exporters': {
                    'jaeger': {
                        'endpoint': 'jaeger:14250',
                        'tls': {'insecure': True}
                    }
                },
                'service': {
                    'pipelines': {
                        'traces': {
                            'receivers': ['otlp'],
                            'processors': ['batch'],
                            'exporters': ['jaeger']
                        }
                    }
                }
            }
        """
        ...

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying backend services.

        Returns Helm chart values for self-hosted telemetry backends
        (e.g., Jaeger). Returns an empty dict for SaaS backends (Datadog)
        that don't require deployment.

        Returns:
            Helm values dictionary for backend chart, or empty dict
            if backend is external (SaaS).

        Example:
            >>> # Jaeger (self-hosted) returns deployment config
            >>> jaeger_plugin.get_helm_values()
            {
                'collector': {'resources': {'limits': {'cpu': '500m'}}},
                'query': {'resources': {'limits': {'cpu': '250m'}}}
            }

            >>> # Datadog (SaaS) returns empty dict
            >>> datadog_plugin.get_helm_values()
            {}
        """
        ...

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate connection to the telemetry backend.

        Performs a lightweight connectivity test to verify the backend
        is reachable. Should complete within 10 seconds.

        Returns:
            True if connection successful, False otherwise.

        Example:
            >>> if plugin.validate_connection():
            ...     print("Backend reachable")
            ... else:
            ...     print("Backend unreachable - check configuration")
        """
        ...
