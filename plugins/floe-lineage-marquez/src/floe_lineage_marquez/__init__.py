"""Marquez lineage backend plugin for floe.

Provides MarquezLineageBackendPlugin for self-hosted Marquez deployments.
Marquez is the reference implementation of the OpenLineage specification.

See Also:
    - Marquez: https://marquezproject.ai/
    - OpenLineage: https://openlineage.io/
"""

from __future__ import annotations

import ipaddress
import logging
import os
import urllib.request
from typing import Any
from urllib.parse import urlparse

from floe_core.plugins.lineage import LineageBackendPlugin
from pydantic import BaseModel, Field, field_validator

__all__ = ["MarquezLineageBackendPlugin", "MarquezConfig"]

logger = logging.getLogger(__name__)

# SECURITY: Known localhost hostnames (exact match only)
_LOCALHOST_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "localhost.localdomain",
    }
)


def _is_localhost(hostname: str) -> bool:
    """Check if hostname represents localhost.

    SECURITY: Uses exact hostname matching and proper IP address parsing
    to prevent bypass attacks like 'localhost.attacker.com'.

    Args:
        hostname: The hostname to check.

    Returns:
        True if the hostname is localhost or a loopback IP address.
    """
    # Check known localhost hostnames (case-insensitive, exact match)
    if hostname.lower() in _LOCALHOST_HOSTNAMES:
        return True

    # Check if it's a loopback IP address
    try:
        addr = ipaddress.ip_address(hostname)
        # Handle IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1)
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            return addr.ipv4_mapped.is_loopback
        return addr.is_loopback
    except ValueError:
        # Not a valid IP address - must match hostname exactly
        return False


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

    @field_validator("url")
    @classmethod
    def validate_url_security(cls, v: str) -> str:
        """Validate URL format and enforce HTTPS for non-localhost URLs.

        SECURITY NOTES:
            - HTTP is ONLY allowed for localhost/loopback addresses (127.0.0.1, ::1)
            - This is intentional for local development and testing environments
            - Production deployments MUST use HTTPS URLs which are enforced here
            - Uses proper URL parsing to prevent bypass attacks (not substring matching)
            - The localhost exception is safe because loopback traffic never leaves host
            - Override with FLOE_ALLOW_INSECURE_HTTP=true for development environments

        Args:
            v: The URL to validate.

        Returns:
            Validated and normalized URL.

        Raises:
            ValueError: If URL is HTTP and not localhost (without override).
        """
        # Strip trailing slashes for consistency
        v = v.rstrip("/")

        # SECURITY: HTTP is only allowed for localhost addresses by default.
        # This is safe because loopback traffic never leaves the host.
        # Production deployments must use HTTPS.
        if v.startswith("http://"):
            # SECURITY: Parse URL to extract actual hostname
            # Never use substring matching - vulnerable to bypass
            parsed = urlparse(v)
            hostname = parsed.hostname or ""

            # Check if it's actually localhost (proper validation)
            if _is_localhost(hostname):
                return v

            # Allow HTTP with explicit environment variable override
            if os.environ.get("FLOE_ALLOW_INSECURE_HTTP", "").lower() == "true":
                logger.critical(
                    "INSECURE HTTP enabled for Marquez URL '%s' - "
                    "development use only! Set FLOE_ALLOW_INSECURE_HTTP=false "
                    "before deploying to production.",
                    hostname,
                )
                return v

            raise ValueError(
                f"HTTP not allowed for '{hostname}'. "
                "url must use HTTPS for non-localhost URLs. "
                "HTTP is only allowed for localhost development. "
                "Set FLOE_ALLOW_INSECURE_HTTP=true to override (not recommended)."
            )

        if not v.startswith("https://"):
            raise ValueError("url must start with https:// or http://localhost")

        return v


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

        Note:
            URL validation is performed by MarquezConfig.validate_url_security().
            HTTP is only allowed for localhost. Use FLOE_ALLOW_INSECURE_HTTP=true
            to override for development environments.
        """
        # Validate URL security using MarquezConfig validator
        validated_config = MarquezConfig(
            url=url,
            api_key=api_key,
            environment=environment,
            verify_ssl=verify_ssl,
        )

        self._url = validated_config.url
        self._api_key = validated_config.api_key
        self._environment = validated_config.environment
        self._verify_ssl = validated_config.verify_ssl

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
                    # SECURITY: Use Kubernetes Secret for credentials (Bitnami pattern)
                    # Secret must contain the keys specified in secretKeys
                    # See: https://github.com/bitnami/charts/tree/main/bitnami/postgresql
                    "existingSecret": "marquez-postgresql-credentials",  # pragma: allowlist secret
                    "secretKeys": {  # pragma: allowlist secret
                        "adminPasswordKey": "postgres-password",  # pragma: allowlist secret
                        "userPasswordKey": "password",  # pragma: allowlist secret
                    },
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

            with urllib.request.urlopen(
                req, timeout=10
            ) as response:  # noqa: S310  # nosec B310
                return bool(response.status == 200)
        except Exception:
            return False

    def get_config_schema(self) -> type[MarquezConfig]:
        """Return the Pydantic configuration schema for this plugin."""
        return MarquezConfig
