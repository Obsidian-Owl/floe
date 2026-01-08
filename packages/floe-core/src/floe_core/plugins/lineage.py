"""LineageBackendPlugin ABC for lineage backend plugins.

This module defines the abstract base class for lineage plugins that
provide OpenLineage backend functionality. Lineage plugins are responsible for:
- Configuring OpenLineage HTTP transport for backend-specific endpoints
- Defining namespace strategies for lineage events
- Providing Helm values for deploying self-hosted backends (Marquez, etc.)
- Validating connectivity to the lineage backend

Example:
    >>> from floe_core.plugins.lineage import LineageBackendPlugin
    >>> class MarquezPlugin(LineageBackendPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "marquez"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


class LineageBackendPlugin(PluginMetadata):
    """Abstract base class for OpenLineage backend plugins.

    LineageBackendPlugin extends PluginMetadata with lineage-specific
    methods for configuring OpenLineage backends. Implementations include
    Marquez, Atlan, and OpenMetadata.

    Unlike TelemetryBackendPlugin, lineage uses direct HTTP transport
    (not OTLP Collector), as OpenLineage events have different routing
    requirements than telemetry data.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - get_transport_config() method
        - get_namespace_strategy() method
        - get_helm_values() method
        - validate_connection() method

    Example:
        >>> class MarquezPlugin(LineageBackendPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "marquez"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def get_transport_config(self) -> dict:
        ...         return {
        ...             "type": "http",
        ...             "url": "http://marquez:5000/api/v1/lineage"
        ...         }

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
        - ADR-0035: Lineage architecture
    """

    @abstractmethod
    def get_transport_config(self) -> dict[str, Any]:
        """Generate OpenLineage HTTP transport configuration.

        Creates the configuration for OpenLineage HTTP transport
        to send lineage events to this backend.

        Returns:
            Dictionary with transport configuration including:
                - type: Must be "http"
                - url: Backend endpoint URL
                - timeout: Request timeout in seconds
                - Additional backend-specific options

        Example:
            >>> config = plugin.get_transport_config()
            >>> config
            {
                'type': 'http',
                'url': 'http://marquez:5000/api/v1/lineage',
                'timeout': 5.0,
                'endpoint': 'api/v1/lineage'
            }
        """
        ...

    @abstractmethod
    def get_namespace_strategy(self) -> dict[str, Any]:
        """Define namespace strategy for lineage events.

        Configures how namespaces are generated for OpenLineage events.
        Namespaces organize lineage data by environment or other criteria.

        Returns:
            Dictionary with namespace strategy configuration including:
                - strategy: Strategy name (e.g., "environment_based", "static")
                - template: Namespace template string
                - Additional strategy-specific options

        Example:
            >>> config = plugin.get_namespace_strategy()
            >>> config
            {
                'strategy': 'environment_based',
                'template': 'floe-{environment}',
                'environment_var': 'FLOE_ENVIRONMENT'
            }
        """
        ...

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying backend services.

        Returns Helm chart values for self-hosted lineage backends
        (e.g., Marquez). Returns an empty dict for SaaS backends (Atlan)
        that don't require deployment.

        Returns:
            Helm values dictionary for backend chart, or empty dict
            if backend is external (SaaS).

        Example:
            >>> # Marquez (self-hosted) returns deployment config
            >>> marquez_plugin.get_helm_values()
            {
                'marquez': {'resources': {'limits': {'cpu': '500m'}}},
                'postgresql': {'enabled': True}
            }

            >>> # Atlan (SaaS) returns empty dict
            >>> atlan_plugin.get_helm_values()
            {}
        """
        ...

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate connection to the lineage backend.

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
