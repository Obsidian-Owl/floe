"""Marquez lineage backend plugin for floe.

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
from pydantic import BaseModel, Field

__all__ = ["MarquezLineageBackendPlugin", "MarquezConfig"]


class MarquezConfig(BaseModel):
    """Configuration schema for Marquez lineage backend.

    This model provides type-safe configuration validation for Marquez
    backend settings, following the Pydantic v2 conventions used throughout
    the floe platform.

    Attributes:
        url: Base URL for Marquez API (e.g., "https://marquez:5000")
        api_key: Optional API key for authentication
        environment: Deployment environment for namespace (e.g., "prod", "staging")
        verify_ssl: Whether to verify SSL certificates (default True)

    Example:
        >>> config = MarquezConfig(
        ...     url="https://marquez:5000",
        ...     environment="staging"
        ... )
        >>> plugin = MarquezLineageBackendPlugin(**config.model_dump())
    """

    url: str = Field(
        default="https://marquez:5000",
        description="Marquez API base URL (use HTTPS in production)",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional API key for authentication",
    )
    environment: str = Field(
        default="prod",
        description="Deployment environment for namespace",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates",
    )


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
         _url: Base URL for Marquez API (e.g., "https://marquez:5000")
        _api_key: Optional API key for authentication

    Example:
        >>> plugin = MarquezLineageBackendPlugin(
        ...     url="https://marquez:5000",
        ...     api_key="secret-key"  # pragma: allowlist secret
        ... )
        >>> config = plugin.get_transport_config()
        >>> config["url"]
        'https://marquez:5000/api/v1/lineage'
    """

    def __init__(
        self,
        url: str = "https://marquez:5000",
        api_key: str | None = None,
        environment: str = "prod",
        verify_ssl: bool = True,
    ) -> None:
        """Initialize Marquez backend plugin.

        Args:
            url: Base URL for Marquez API (default: "https://marquez:5000")
            api_key: Optional API key for authentication
            environment: Deployment environment for namespace (default: "prod")
            verify_ssl: Whether to verify SSL certificates (default: True)
        """
        import logging

        self._url = url.rstrip("/")
        self._api_key = api_key
        self._environment = environment
        self._verify_ssl = verify_ssl

        # Warn if using HTTP for non-localhost URLs
        if url.startswith("http://") and not url.startswith("http://localhost"):
            logging.getLogger(__name__).warning(
                "Using HTTP for Marquez URL - use HTTPS in production"
            )

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
            >>> plugin = MarquezLineageBackendPlugin("https://marquez:5000")
            >>> config = plugin.get_transport_config()
            >>> config
            {
                'type': 'http',
                'url': 'https://marquez:5000/api/v1/lineage',
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

        Uses centralized namespaces to organize lineage data
        by deployment environment and platform.

        Returns:
            Dictionary with namespace strategy configuration:
                - strategy: "centralized" (uses environment.platform format)
                - environment: deployment environment (e.g., "prod")
                - platform: platform identifier (e.g., "floe")

        Example:
            >>> plugin = MarquezLineageBackendPlugin()
            >>> strategy = plugin.get_namespace_strategy()
            >>> strategy["strategy"]
            'centralized'
        """
        return {
            "strategy": "centralized",
            "environment": self._environment,
            "platform": "floe",
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
                    "password": "<SET_VIA_HELM_VALUES>",  # pragma: allowlist secret
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

    def get_config_schema(self) -> type[MarquezConfig]:
        """Return the Pydantic configuration schema for this plugin."""
        return MarquezConfig
