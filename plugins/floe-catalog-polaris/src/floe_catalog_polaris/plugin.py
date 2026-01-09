"""PolarisCatalogPlugin implementation for floe.

This module provides the concrete CatalogPlugin implementation for Apache Polaris,
enabling Iceberg catalog management via the Polaris REST API.

Example:
    >>> from floe_catalog_polaris.plugin import PolarisCatalogPlugin
    >>> from floe_catalog_polaris.config import PolarisCatalogConfig, OAuth2Config
    >>> config = PolarisCatalogConfig(
    ...     uri="https://polaris.example.com/api/catalog",
    ...     warehouse="my_warehouse",
    ...     oauth2=OAuth2Config(
    ...         client_id="client",
    ...         client_secret="secret",
    ...         token_url="https://auth.example.com/oauth/token",
    ...     ),
    ... )
    >>> plugin = PolarisCatalogPlugin(config=config)
    >>> plugin.name
    'polaris'

Requirements Covered:
    - FR-006: PolarisCatalogPlugin implements CatalogPlugin ABC
    - FR-004: Plugin metadata (name, version, floe_api_version)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from floe_core import CatalogPlugin, HealthState, HealthStatus
from floe_core.plugins.catalog import Catalog
from pyiceberg.catalog import load_catalog

from floe_catalog_polaris.config import PolarisCatalogConfig
from floe_catalog_polaris.errors import PYICEBERG_EXCEPTION_TYPES, map_pyiceberg_error
from floe_catalog_polaris.retry import with_retry
from floe_catalog_polaris.tracing import catalog_span, get_tracer, set_error_attributes

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pyiceberg.catalog import Catalog as PyIcebergCatalog

logger = structlog.get_logger(__name__)


class PolarisCatalogPlugin(CatalogPlugin):
    """Polaris catalog plugin implementing the CatalogPlugin ABC.

    This plugin provides Iceberg catalog functionality via Apache Polaris,
    including namespace management, table operations, and credential vending.

    Attributes:
        config: The PolarisCatalogConfig instance for this plugin.

    Example:
        >>> config = PolarisCatalogConfig(...)
        >>> plugin = PolarisCatalogPlugin(config=config)
        >>> plugin.startup()
        >>> try:
        ...     catalog = plugin.connect({})
        ...     namespaces = plugin.list_namespaces()
        ... finally:
        ...     plugin.shutdown()
    """

    def __init__(self, config: PolarisCatalogConfig) -> None:
        """Initialize the Polaris catalog plugin.

        Args:
            config: Configuration for connecting to Polaris catalog.
        """
        self._config = config
        self._catalog: PyIcebergCatalog | None = None

    @property
    def config(self) -> PolarisCatalogConfig:
        """Return the plugin configuration.

        Returns:
            The PolarisCatalogConfig instance used to configure this plugin.
        """
        return self._config

    # =========================================================================
    # PluginMetadata abstract properties
    # =========================================================================

    @property
    def name(self) -> str:
        """Return the plugin name.

        Returns:
            The plugin identifier "polaris".
        """
        return "polaris"

    @property
    def version(self) -> str:
        """Return the plugin version.

        Returns:
            The plugin version in semver format.
        """
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Return the required floe API version.

        Returns:
            The minimum floe API version this plugin requires.
        """
        return "0.1"

    @property
    def description(self) -> str:
        """Return the plugin description.

        Returns:
            Human-readable description of the plugin.
        """
        return "Apache Polaris catalog plugin for Iceberg table management"

    @property
    def dependencies(self) -> list[str]:
        """Return the list of plugin dependencies.

        Returns:
            List of plugin names this plugin depends on (empty for this plugin).
        """
        return []

    # =========================================================================
    # Configuration methods
    # =========================================================================

    def get_config_schema(self) -> type[BaseModel]:
        """Return the configuration schema for this plugin.

        Returns:
            The PolarisCatalogConfig Pydantic model class.
        """
        return PolarisCatalogConfig

    # =========================================================================
    # Lifecycle methods
    # =========================================================================

    def startup(self) -> None:
        """Initialize the plugin.

        Called when the plugin is activated. Performs any necessary
        initialization such as validating configuration or pre-warming
        connections.
        """
        # Stub implementation - will be enhanced in later tasks

    def shutdown(self) -> None:
        """Clean up plugin resources.

        Called when the platform shuts down. Closes any open connections
        and releases resources.
        """
        # Stub implementation - will be enhanced in later tasks

    # =========================================================================
    # CatalogPlugin abstract methods
    # =========================================================================

    def connect(self, config: dict[str, Any]) -> Catalog:
        """Connect to the Polaris catalog using PyIceberg REST catalog.

        Establishes a connection to the Polaris REST catalog using OAuth2
        client credentials authentication. The connection uses the plugin's
        stored configuration, optionally merged with additional config.

        Args:
            config: Additional connection configuration. Merged with
                the plugin's stored configuration. Supported keys:
                - scope: OAuth2 scope override (default: "PRINCIPAL_ROLE:ALL")
                - Additional PyIceberg catalog configuration

        Returns:
            A PyIceberg-compatible Catalog instance.

        Raises:
            ConnectionError: If unable to connect to the catalog.
            AuthenticationError: If OAuth2 credentials are invalid.

        Example:
            >>> plugin = PolarisCatalogPlugin(config)
            >>> catalog = plugin.connect({})
            >>> namespaces = catalog.list_namespaces()
        """
        tracer = get_tracer()
        with catalog_span(
            tracer,
            "connect",
            catalog_name="polaris",
            catalog_uri=self._config.uri,
            warehouse=self._config.warehouse,
        ) as span:
            log = logger.bind(
                uri=self._config.uri,
                warehouse=self._config.warehouse,
            )
            log.info("connecting_to_polaris_catalog")

            try:
                # Build OAuth2 credential string in format expected by PyIceberg
                # PyIceberg accepts "client_id:client_secret" format
                client_id = self._config.oauth2.client_id
                client_secret = self._config.oauth2.client_secret.get_secret_value()
                credential = f"{client_id}:{client_secret}"

                # Build catalog configuration
                catalog_config: dict[str, Any] = {
                    "type": "rest",
                    "uri": self._config.uri,
                    "warehouse": self._config.warehouse,
                    "credential": credential,
                    # Enable automatic token refresh
                    "token-refresh-enabled": "true",
                }

                # Add OAuth2 token URL if different from default catalog endpoint
                # PyIceberg defaults to {uri}/v1/oauth/tokens if not specified
                token_url = self._config.oauth2.token_url
                if token_url:
                    catalog_config["oauth2-server-uri"] = token_url

                # Add scope if configured
                scope = config.get("scope", self._config.oauth2.scope)
                if scope:
                    catalog_config["scope"] = scope

                # Merge any additional configuration from the config argument
                for key, value in config.items():
                    if key not in ("scope",):  # Already handled above
                        catalog_config[key] = value

                log.debug("catalog_config_built", config_keys=list(catalog_config.keys()))

                # Load the PyIceberg REST catalog with retry for transient failures
                # Using "polaris" as the catalog name for identification
                load_with_retry = with_retry(
                    load_catalog,
                    max_retries=self._config.max_retries,
                )
                self._catalog = load_with_retry("polaris", **catalog_config)

                log.info("polaris_catalog_connected")

                # Return the catalog (which implements the Catalog protocol)
                return self._catalog  # type: ignore[return-value]

            except PYICEBERG_EXCEPTION_TYPES as e:
                # Map PyIceberg exceptions to floe errors
                set_error_attributes(span, e)
                log.error("polaris_catalog_connection_failed", error=str(e))
                raise map_pyiceberg_error(
                    e,
                    catalog_uri=self._config.uri,
                    operation="connect",
                ) from e

            except Exception as e:
                # Catch any other unexpected exceptions
                set_error_attributes(span, e)
                log.error("polaris_catalog_connection_failed", error=str(e))
                raise

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a new namespace in the Polaris catalog.

        Args:
            namespace: Namespace name to create.
            properties: Optional namespace properties.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """
        # Stub - will be implemented in later tasks
        raise NotImplementedError("create_namespace() not yet implemented")

    def list_namespaces(self, parent: str | None = None) -> list[str]:
        """List namespaces in the Polaris catalog.

        Args:
            parent: Optional parent namespace to filter by.

        Returns:
            List of namespace names.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """
        # Stub - will be implemented in later tasks
        raise NotImplementedError("list_namespaces() not yet implemented")

    def delete_namespace(self, namespace: str) -> None:
        """Delete a namespace from the Polaris catalog.

        Args:
            namespace: Namespace name to delete.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """
        # Stub - will be implemented in later tasks
        raise NotImplementedError("delete_namespace() not yet implemented")

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a new Iceberg table in the Polaris catalog.

        Args:
            identifier: Full table identifier (e.g., "bronze.customers").
            schema: Iceberg schema definition.
            location: Optional storage location override.
            properties: Optional table properties.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """
        # Stub - will be implemented in later tasks
        raise NotImplementedError("create_table() not yet implemented")

    def list_tables(self, namespace: str) -> list[str]:
        """List tables in a namespace.

        Args:
            namespace: Namespace to list tables from.

        Returns:
            List of table identifiers.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """
        # Stub - will be implemented in later tasks
        raise NotImplementedError("list_tables() not yet implemented")

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop an Iceberg table from the Polaris catalog.

        Args:
            identifier: Full table identifier.
            purge: If True, also delete underlying data files.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """
        # Stub - will be implemented in later tasks
        raise NotImplementedError("drop_table() not yet implemented")

    def vend_credentials(
        self,
        table_path: str,
        operations: list[str],
    ) -> dict[str, Any]:
        """Vend short-lived credentials for table access.

        Args:
            table_path: Full table path.
            operations: List of operations to allow.

        Returns:
            Dictionary containing temporary credentials.

        Raises:
            NotImplementedError: This method is not yet implemented.
        """
        # Stub - will be implemented in later tasks
        raise NotImplementedError("vend_credentials() not yet implemented")

    def health_check(self, timeout: float = 1.0) -> HealthStatus:
        """Check Polaris catalog connectivity and health.

        Performs a lightweight operation to verify the catalog is reachable
        and responding within the timeout period.

        Args:
            timeout: Maximum time in seconds to wait for response.

        Returns:
            HealthStatus indicating whether catalog is healthy.
        """
        # Stub - returns unhealthy until actual implementation
        # Will be implemented in later tasks with real connectivity check
        _ = timeout  # Intentionally unused for stub
        return HealthStatus(
            state=HealthState.UNHEALTHY,
            message="Polaris catalog not connected",
            details={"reason": "Plugin not yet connected to catalog"},
        )
