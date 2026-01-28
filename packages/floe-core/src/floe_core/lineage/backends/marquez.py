"""Marquez lineage backend plugin.

Provides MarquezLineageBackendPlugin for self-hosted Marquez deployments.
Marquez is the reference implementation of the OpenLineage specification.

See Also:
    - Marquez: https://marquezproject.ai/
    - OpenLineage: https://openlineage.io/
"""

from __future__ import annotations

import urllib.request
from typing import Any

from floe_core.plugins.lineage import LineageBackendPlugin


class MarquezLineageBackendPlugin(LineageBackendPlugin):
    """Lineage backend plugin for Marquez.

    Marquez is the reference implementation of OpenLineage, providing
    a metadata repository for data lineage collection and visualization.

    This plugin configures:
        - HTTP transport to Marquez API endpoint
        - Environment-based namespace strategy
        - Helm values for self-hosted deployment (Marquez + PostgreSQL)
        - Connection validation via Marquez API

    Attributes:
        _url: Base URL for Marquez API (e.g., "http://marquez:5000")
        _api_key: Optional API key for authentication

    Example:
        >>> plugin = MarquezLineageBackendPlugin(
        ...     url="http://marquez:5000",
        ...     api_key="secret-key"  # pragma: allowlist secret
        ... )
        >>> config = plugin.get_transport_config()
        >>> config["url"]
        'http://marquez:5000/api/v1/lineage'
    """

    def __init__(
        self,
        url: str = "http://marquez:5000",
        api_key: str | None = None,
    ) -> None:
        """Initialize Marquez backend plugin.

        Args:
            url: Base URL for Marquez API (default: "http://marquez:5000")
            api_key: Optional API key for authentication
        """
        self._url = url.rstrip("/")
        self._api_key = api_key

    @property
    def name(self) -> str:
        """Plugin name.

        Returns:
            "marquez"
        """
        return "marquez"

    @property
    def version(self) -> str:
        """Plugin version (tracks Marquez version).

        Returns:
            "0.20.0"
        """
        return "0.20.0"

    @property
    def floe_api_version(self) -> str:
        """Required floe API version.

        Returns:
            "1.0"
        """
        return "1.0"

    def get_transport_config(self) -> dict[str, Any]:
        """Generate OpenLineage HTTP transport configuration for Marquez.

        Returns:
            Dictionary with HTTP transport configuration:
                - type: "http"
                - url: Marquez lineage endpoint
                - timeout: Request timeout in seconds
                - api_key: Optional API key for authentication

        Example:
            >>> plugin = MarquezLineageBackendPlugin("http://marquez:5000")
            >>> config = plugin.get_transport_config()
            >>> config
            {
                'type': 'http',
                'url': 'http://marquez:5000/api/v1/lineage',
                'timeout': 5.0,
                'api_key': None
            }
        """
        return {
            "type": "http",
            "url": f"{self._url}/api/v1/lineage",
            "timeout": 5.0,
            "api_key": self._api_key,
        }

    def get_namespace_strategy(self) -> dict[str, Any]:
        """Define namespace strategy for lineage events.

        Uses environment-based namespaces to organize lineage data
        by deployment environment (dev, staging, prod).

        Returns:
            Dictionary with namespace strategy configuration:
                - strategy: "environment_based"
                - template: "floe-{environment}"
                - environment_var: "FLOE_ENVIRONMENT"

        Example:
            >>> plugin = MarquezLineageBackendPlugin()
            >>> strategy = plugin.get_namespace_strategy()
            >>> strategy["template"]
            'floe-{environment}'
        """
        return {
            "strategy": "environment_based",
            "template": "floe-{environment}",
            "environment_var": "FLOE_ENVIRONMENT",
        }

    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying Marquez.

        Returns Helm chart values for self-hosted Marquez deployment,
        including PostgreSQL backend and resource limits.

        Returns:
            Helm values dictionary with Marquez and PostgreSQL configuration.

        Example:
            >>> plugin = MarquezLineageBackendPlugin()
            >>> values = plugin.get_helm_values()
            >>> values["marquez"]["enabled"]
            True
        """
        return {
            "marquez": {
                "enabled": True,
                "image": {
                    "repository": "marquezproject/marquez",
                    "tag": "0.20.0",
                    "pullPolicy": "IfNotPresent",
                },
                "service": {
                    "type": "ClusterIP",
                    "port": 5000,
                },
                "resources": {
                    "limits": {
                        "cpu": "500m",
                        "memory": "512Mi",
                    },
                    "requests": {
                        "cpu": "250m",
                        "memory": "256Mi",
                    },
                },
                "env": {
                    "MARQUEZ_PORT": "5000",
                    "MARQUEZ_ADMIN_PORT": "5001",
                },
            },
            "postgresql": {
                "enabled": True,
                "auth": {
                    "username": "marquez",
                    "password": "marquez",  # pragma: allowlist secret
                    "database": "marquez",
                },
                "primary": {
                    "persistence": {
                        "enabled": True,
                        "size": "8Gi",
                    },
                    "resources": {
                        "limits": {
                            "cpu": "500m",
                            "memory": "512Mi",
                        },
                        "requests": {
                            "cpu": "250m",
                            "memory": "256Mi",
                        },
                    },
                },
            },
        }

    def validate_connection(self) -> bool:
        """Validate connection to Marquez backend.

        Performs a lightweight connectivity test by querying the
        Marquez namespaces endpoint. Should complete within 10 seconds.

        Returns:
            True if connection successful, False otherwise.

        Example:
            >>> plugin = MarquezLineageBackendPlugin("http://localhost:5000")
            >>> if plugin.validate_connection():
            ...     print("Marquez is reachable")
            ... else:
            ...     print("Marquez is unreachable")
        """
        try:
            url = f"{self._url}/api/v1/namespaces"
            req = urllib.request.Request(url, method="GET")

            if self._api_key:
                req.add_header("Authorization", f"Bearer {self._api_key}")

            with urllib.request.urlopen(req, timeout=10) as response:  # noqa: S310  # nosec B310
                return bool(response.status == 200)
        except Exception:
            return False
