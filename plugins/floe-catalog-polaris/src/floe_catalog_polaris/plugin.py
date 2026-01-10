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

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog
from floe_core import CatalogPlugin, HealthState, HealthStatus, NotSupportedError
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

                # Add X-Iceberg-Access-Delegation header for credential vending
                # When enabled, Polaris returns vended credentials in table load response
                # See: https://iceberg.apache.org/docs/latest/rest-catalog/#credential-vending
                if self._config.credential_vending_enabled:
                    catalog_config["header.X-Iceberg-Access-Delegation"] = "vended-credentials"

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

        Creates a namespace (database/schema) in the Iceberg catalog.
        Namespaces organize tables into logical groups. Supports hierarchical
        namespace paths using dot notation (e.g., "domain.product.bronze").

        Args:
            namespace: Namespace name to create. Supports dot notation for
                hierarchical namespaces (e.g., "bronze", "domain.product.silver").
            properties: Optional namespace properties such as:
                - location: Storage location (e.g., "s3://bucket/path")
                - owner: Namespace owner
                - description: Human-readable description
                - Custom metadata key-value pairs

        Raises:
            ConflictError: If namespace already exists.
            AuthenticationError: If lacking permission to create namespaces.
            CatalogUnavailableError: If catalog is unreachable.

        Example:
            >>> plugin.create_namespace("bronze", {"location": "s3://bucket/bronze"})
            >>> plugin.create_namespace("domain.product.silver")
        """
        tracer = get_tracer()
        with catalog_span(
            tracer,
            "create_namespace",
            catalog_name="polaris",
            catalog_uri=self._config.uri,
            warehouse=self._config.warehouse,
            namespace=namespace,
        ) as span:
            log = logger.bind(
                namespace=namespace,
                uri=self._config.uri,
            )
            log.info("creating_namespace")

            try:
                if self._catalog is None:
                    raise RuntimeError("Catalog not connected. Call connect() first.")

                # Use empty dict if no properties provided
                ns_properties = properties or {}

                # Create the namespace via PyIceberg catalog
                self._catalog.create_namespace(namespace, properties=ns_properties)

                log.info("namespace_created", properties=list(ns_properties.keys()))

            except PYICEBERG_EXCEPTION_TYPES as e:
                # Map PyIceberg exceptions to floe errors
                set_error_attributes(span, e)
                log.error("create_namespace_failed", error=str(e))
                raise map_pyiceberg_error(
                    e,
                    catalog_uri=self._config.uri,
                    operation="create_namespace",
                ) from e

            except Exception as e:
                # Catch any other unexpected exceptions
                set_error_attributes(span, e)
                log.error("create_namespace_failed", error=str(e))
                raise

    def list_namespaces(self, parent: str | None = None) -> list[str]:
        """List namespaces in the Polaris catalog.

        Returns all namespaces, optionally filtered by parent namespace
        for hierarchical catalogs. Namespaces are returned as dot-notation
        strings for hierarchical namespaces.

        Args:
            parent: Optional parent namespace to filter by. If None,
                returns top-level namespaces. If specified, returns
                child namespaces under the parent.

        Returns:
            List of namespace names as strings. Multi-level namespaces
            are returned with dot notation (e.g., "domain.product.bronze").

        Raises:
            AuthenticationError: If lacking permission to list namespaces.
            CatalogUnavailableError: If catalog is unreachable.

        Example:
            >>> plugin.list_namespaces()
            ['bronze', 'silver', 'gold']
            >>> plugin.list_namespaces(parent="silver")
            ['silver.customers', 'silver.orders']
        """
        tracer = get_tracer()
        extra_attrs = {"parent_namespace": parent} if parent else None
        with catalog_span(
            tracer,
            "list_namespaces",
            catalog_name="polaris",
            catalog_uri=self._config.uri,
            warehouse=self._config.warehouse,
            extra_attributes=extra_attrs,
        ) as span:
            log = logger.bind(
                parent=parent,
                uri=self._config.uri,
            )
            log.info("listing_namespaces")

            try:
                if self._catalog is None:
                    raise RuntimeError("Catalog not connected. Call connect() first.")

                # PyIceberg returns list of tuples, e.g., [("bronze",), ("silver",)]
                # or for hierarchical: [("domain", "product", "bronze")]
                if parent:
                    # Convert parent string to tuple for PyIceberg
                    parent_tuple = tuple(parent.split("."))
                    raw_namespaces = self._catalog.list_namespaces(parent_tuple)
                else:
                    raw_namespaces = self._catalog.list_namespaces()

                # Convert tuples to dot-notation strings
                namespaces = [".".join(ns) for ns in raw_namespaces]

                log.info("namespaces_listed", count=len(namespaces))

                return namespaces

            except PYICEBERG_EXCEPTION_TYPES as e:
                # Map PyIceberg exceptions to floe errors
                set_error_attributes(span, e)
                log.error("list_namespaces_failed", error=str(e))
                raise map_pyiceberg_error(
                    e,
                    catalog_uri=self._config.uri,
                    operation="list_namespaces",
                ) from e

            except Exception as e:
                # Catch any other unexpected exceptions
                set_error_attributes(span, e)
                log.error("list_namespaces_failed", error=str(e))
                raise

    def delete_namespace(self, namespace: str) -> None:
        """Delete a namespace from the Polaris catalog.

        Deletes an empty namespace from the catalog. The namespace must not
        contain any tables - use drop_table() first to remove all tables.

        Args:
            namespace: Namespace name to delete. Supports dot notation for
                hierarchical namespaces (e.g., "domain.product.bronze").

        Raises:
            NotFoundError: If namespace does not exist.
            NotSupportedError: If namespace is not empty (contains tables).
            AuthenticationError: If lacking permission to delete namespaces.
            CatalogUnavailableError: If catalog is unreachable.

        Example:
            >>> plugin.delete_namespace("bronze")
            >>> plugin.delete_namespace("domain.product.silver")
        """
        tracer = get_tracer()
        with catalog_span(
            tracer,
            "delete_namespace",
            catalog_name="polaris",
            catalog_uri=self._config.uri,
            warehouse=self._config.warehouse,
            namespace=namespace,
        ) as span:
            log = logger.bind(
                namespace=namespace,
                uri=self._config.uri,
            )
            log.info("deleting_namespace")

            try:
                if self._catalog is None:
                    raise RuntimeError("Catalog not connected. Call connect() first.")

                # Drop the namespace via PyIceberg catalog
                self._catalog.drop_namespace(namespace)

                log.info("namespace_deleted")

            except PYICEBERG_EXCEPTION_TYPES as e:
                # Map PyIceberg exceptions to floe errors
                set_error_attributes(span, e)
                log.error("delete_namespace_failed", error=str(e))
                raise map_pyiceberg_error(
                    e,
                    catalog_uri=self._config.uri,
                    operation="delete_namespace",
                ) from e

            except Exception as e:
                # Catch any other unexpected exceptions
                set_error_attributes(span, e)
                log.error("delete_namespace_failed", error=str(e))
                raise

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a new Iceberg table in the Polaris catalog.

        Creates an Iceberg table with the specified schema. The table
        location defaults to the warehouse location if not specified.

        Args:
            identifier: Full table identifier (e.g., "bronze.customers").
            schema: Iceberg schema definition as a dictionary with:
                - type: "struct"
                - fields: List of field definitions with id, name, type, required
            location: Optional storage location override (e.g., "s3://bucket/path").
            properties: Optional table properties (e.g., {"write.format.default": "parquet"}).

        Raises:
            ConflictError: If table already exists.
            NotFoundError: If namespace does not exist.
            AuthenticationError: If lacking permission to create tables.
            CatalogUnavailableError: If catalog is unreachable.

        Example:
            >>> schema = {"type": "struct", "fields": [...]}
            >>> plugin.create_table("bronze.customers", schema)
        """
        tracer = get_tracer()
        with catalog_span(
            tracer,
            "create_table",
            catalog_name="polaris",
            catalog_uri=self._config.uri,
            warehouse=self._config.warehouse,
            table_full_name=identifier,
        ) as span:
            log = logger.bind(
                table=identifier,
                uri=self._config.uri,
            )
            log.info("creating_table")

            try:
                if self._catalog is None:
                    raise RuntimeError("Catalog not connected. Call connect() first.")

                # Build kwargs for PyIceberg create_table
                kwargs: dict[str, Any] = {}
                if location:
                    kwargs["location"] = location
                if properties:
                    kwargs["properties"] = properties

                # Create the table via PyIceberg catalog
                self._catalog.create_table(identifier, schema, **kwargs)

                log.info("table_created", location=location)

            except PYICEBERG_EXCEPTION_TYPES as e:
                # Map PyIceberg exceptions to floe errors
                set_error_attributes(span, e)
                log.error("create_table_failed", error=str(e))
                raise map_pyiceberg_error(
                    e,
                    catalog_uri=self._config.uri,
                    operation="create_table",
                ) from e

            except Exception as e:
                # Catch any other unexpected exceptions
                set_error_attributes(span, e)
                log.error("create_table_failed", error=str(e))
                raise

    def list_tables(self, namespace: str) -> list[str]:
        """List tables in a namespace.

        Returns all table identifiers within the specified namespace.

        Args:
            namespace: Namespace to list tables from (e.g., "bronze").

        Returns:
            List of full table identifiers (e.g., ["bronze.customers", "bronze.orders"]).

        Raises:
            NotFoundError: If namespace does not exist.
            AuthenticationError: If lacking permission to list tables.
            CatalogUnavailableError: If catalog is unreachable.

        Example:
            >>> plugin.list_tables("bronze")
            ['bronze.customers', 'bronze.orders', 'bronze.products']
        """
        tracer = get_tracer()
        with catalog_span(
            tracer,
            "list_tables",
            catalog_name="polaris",
            catalog_uri=self._config.uri,
            warehouse=self._config.warehouse,
            namespace=namespace,
        ) as span:
            log = logger.bind(
                namespace=namespace,
                uri=self._config.uri,
            )
            log.info("listing_tables")

            try:
                if self._catalog is None:
                    raise RuntimeError("Catalog not connected. Call connect() first.")

                # PyIceberg returns list of tuples: [(namespace, table_name), ...]
                raw_tables = self._catalog.list_tables(namespace)

                # Convert tuples to dot-notation strings
                tables = [".".join(table) for table in raw_tables]

                log.info("tables_listed", count=len(tables))

                return tables

            except PYICEBERG_EXCEPTION_TYPES as e:
                # Map PyIceberg exceptions to floe errors
                set_error_attributes(span, e)
                log.error("list_tables_failed", error=str(e))
                raise map_pyiceberg_error(
                    e,
                    catalog_uri=self._config.uri,
                    operation="list_tables",
                ) from e

            except Exception as e:
                # Catch any other unexpected exceptions
                set_error_attributes(span, e)
                log.error("list_tables_failed", error=str(e))
                raise

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop an Iceberg table from the Polaris catalog.

        Removes the table metadata from the catalog. If purge is True,
        also deletes the underlying data files.

        Args:
            identifier: Full table identifier (e.g., "bronze.customers").
            purge: If True, also delete underlying data files. Defaults to False.

        Raises:
            NotFoundError: If table does not exist.
            AuthenticationError: If lacking permission to drop tables.
            CatalogUnavailableError: If catalog is unreachable.

        Example:
            >>> plugin.drop_table("staging.temp_table")
            >>> plugin.drop_table("staging.old_data", purge=True)  # Also delete files
        """
        tracer = get_tracer()
        with catalog_span(
            tracer,
            "drop_table",
            catalog_name="polaris",
            catalog_uri=self._config.uri,
            warehouse=self._config.warehouse,
            table_full_name=identifier,
        ) as span:
            log = logger.bind(
                table=identifier,
                purge=purge,
                uri=self._config.uri,
            )
            log.info("dropping_table")

            try:
                if self._catalog is None:
                    raise RuntimeError("Catalog not connected. Call connect() first.")

                # Drop the table via PyIceberg catalog
                # Note: purge_requested is supported by RestCatalog but not
                # in base Catalog type stubs
                self._catalog.drop_table(identifier, purge_requested=purge)  # type: ignore[call-arg]

                log.info("table_dropped")

            except PYICEBERG_EXCEPTION_TYPES as e:
                # Map PyIceberg exceptions to floe errors
                set_error_attributes(span, e)
                log.error("drop_table_failed", error=str(e))
                raise map_pyiceberg_error(
                    e,
                    catalog_uri=self._config.uri,
                    operation="drop_table",
                ) from e

            except Exception as e:
                # Catch any other unexpected exceptions
                set_error_attributes(span, e)
                log.error("drop_table_failed", error=str(e))
                raise

    def vend_credentials(
        self,
        table_path: str,
        operations: list[str],
    ) -> dict[str, Any]:
        """Vend short-lived credentials for table access.

        Returns temporary credentials scoped to specific table operations.
        This implements the credential vending pattern for secure table access
        without exposing long-lived credentials.

        The Polaris catalog supports credential vending via the Iceberg REST
        X-Iceberg-Access-Delegation header. When enabled, the catalog returns
        temporary AWS STS credentials scoped to the table's storage location.

        Args:
            table_path: Full table path (e.g., "bronze.customers").
            operations: List of operations to allow (e.g., ["READ"], ["READ", "WRITE"]).

        Returns:
            Dictionary containing temporary credentials:
                - access_key: Temporary access key
                - secret_key: Temporary secret key
                - token: Session token (if applicable)
                - expiration: Credential expiration timestamp (ISO 8601)

        Raises:
            NotSupportedError: If credential_vending_enabled is False in config.
            RuntimeError: If catalog not connected.
            NotFoundError: If table does not exist.
            AuthenticationError: If lacking permission for requested operations.
            CatalogUnavailableError: If catalog is unreachable.

        Example:
            >>> creds = plugin.vend_credentials(
            ...     table_path="silver.dim_customers",
            ...     operations=["READ", "WRITE"]
            ... )
            >>> creds["access_key"]
            'ASIA...'
        """
        tracer = get_tracer()
        with catalog_span(
            tracer,
            "vend_credentials",
            catalog_name="polaris",
            catalog_uri=self._config.uri,
            warehouse=self._config.warehouse,
            table_full_name=table_path,
            extra_attributes={
                # OTel semantic conventions
                "db.system": "iceberg",
                # floe-specific attributes
                "floe.catalog.system": "polaris",
                "floe.catalog.operations": operations,
            },
        ) as span:
            log = logger.bind(
                table=table_path,
                operations=operations,
                uri=self._config.uri,
            )

            # Check if credential vending is enabled
            if not self._config.credential_vending_enabled:
                log.warning("credential_vending_disabled")
                raise NotSupportedError(
                    operation="vend_credentials",
                    catalog_name="polaris",
                    reason=(
                        "Credential vending not supported. "
                        "Configure storage credentials directly in compute plugin."
                    ),
                )

            log.info("vending_credentials")

            try:
                if self._catalog is None:
                    raise RuntimeError("Catalog not connected. Call connect() first.")

                # Load the table - PyIceberg will request vended credentials
                # via the X-Iceberg-Access-Delegation header when supported
                table = self._catalog.load_table(table_path)

                # Extract credentials from table IO properties using helper
                # PyIceberg stores vended credentials in table.io.properties dict
                from floe_catalog_polaris.credentials import (
                    extract_credentials_from_io_properties,
                )

                io_properties = table.io.properties
                credentials = extract_credentials_from_io_properties(io_properties)

                log.info(
                    "credentials_vended",
                    has_token=bool(credentials.get("token")),
                )

                return credentials

            except PYICEBERG_EXCEPTION_TYPES as e:
                # Map PyIceberg exceptions to floe errors
                set_error_attributes(span, e)
                log.error("vend_credentials_failed", error=str(e))
                raise map_pyiceberg_error(
                    e,
                    catalog_uri=self._config.uri,
                    operation="vend_credentials",
                ) from e

            except Exception as e:
                # Catch any other unexpected exceptions
                set_error_attributes(span, e)
                log.error("vend_credentials_failed", error=str(e))
                raise

    def health_check(self, timeout: float = 1.0) -> HealthStatus:
        """Check Polaris catalog connectivity and health.

        Performs a lightweight operation (list_namespaces) to verify the catalog
        is reachable and responding within the timeout period.

        Args:
            timeout: Maximum time in seconds to wait for response.
                Defaults to 1.0 second. Must be between 0.1 and 10.0 seconds.

        Returns:
            HealthStatus indicating whether catalog is healthy, including
            response_time_ms and checked_at timestamp in details.

        Raises:
            ValueError: If timeout is not between 0.1 and 10.0 seconds.

        Example:
            >>> status = plugin.health_check(timeout=2.0)
            >>> if status.state == HealthState.HEALTHY:
            ...     print(f"Catalog OK ({status.details['response_time_ms']:.1f}ms)")
        """
        # Validate timeout parameter
        if not (0.1 <= timeout <= 10.0):
            raise ValueError(f"timeout must be between 0.1 and 10.0 seconds, got {timeout}")

        log = logger.bind(operation="health_check", timeout=timeout)
        checked_at = datetime.now(timezone.utc)
        start_time = time.perf_counter()

        # Check if plugin is connected
        if self._catalog is None:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log.warning("health_check_not_connected")
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="Polaris catalog not connected",
                details={
                    "reason": "Plugin not yet connected to catalog",
                    "response_time_ms": elapsed_ms,
                    "checked_at": checked_at,
                    "timeout": timeout,
                },
            )

        tracer = get_tracer()
        with catalog_span(
            tracer,
            "health_check",
            catalog_name="polaris",
            warehouse=self._config.warehouse,
        ) as span:
            try:
                # Use list_namespaces as lightweight health probe with timeout
                def _probe() -> None:
                    if self._catalog is not None:
                        self._catalog.list_namespaces()

                executor = ThreadPoolExecutor(max_workers=1)
                try:
                    future = executor.submit(_probe)
                    try:
                        future.result(timeout=timeout)
                    except FuturesTimeoutError:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        log.warning(
                            "health_check_timeout",
                            response_time_ms=elapsed_ms,
                            timeout=timeout,
                        )
                        if span is not None:
                            span.set_attribute("health.status", "unhealthy")
                            span.set_attribute("health.response_time_ms", elapsed_ms)
                        return HealthStatus(
                            state=HealthState.UNHEALTHY,
                            message=f"Health check timed out after {timeout}s",
                            details={
                                "reason": "timeout",
                                "response_time_ms": elapsed_ms,
                                "checked_at": checked_at,
                                "timeout": timeout,
                            },
                        )
                finally:
                    # Shutdown without waiting for thread to complete
                    executor.shutdown(wait=False)

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log.info(
                    "health_check_success",
                    response_time_ms=elapsed_ms,
                    healthy=True,
                )
                if span is not None:
                    span.set_attribute("health.status", "healthy")
                    span.set_attribute("health.response_time_ms", elapsed_ms)

                return HealthStatus(
                    state=HealthState.HEALTHY,
                    message="Polaris catalog responding normally",
                    details={
                        "response_time_ms": elapsed_ms,
                        "checked_at": checked_at,
                        "timeout": timeout,
                    },
                )

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                error_message = str(e) if str(e) else type(e).__name__
                log.warning(
                    "health_check_failed",
                    response_time_ms=elapsed_ms,
                    error=error_message,
                )
                if span is not None:
                    span.set_attribute("health.status", "unhealthy")
                    span.set_attribute("health.response_time_ms", elapsed_ms)
                    set_error_attributes(span, e)

                return HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message=f"Health check failed: {error_message}",
                    details={
                        "reason": "probe_failed",
                        "error": error_message,
                        "response_time_ms": elapsed_ms,
                        "checked_at": checked_at,
                        "timeout": timeout,
                    },
                )
