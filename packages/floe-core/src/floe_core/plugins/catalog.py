"""CatalogPlugin ABC for Iceberg catalog plugins.

This module defines the abstract base class for catalog plugins that
provide Iceberg table catalog functionality. Catalog plugins are responsible for:
- Connecting to Iceberg REST catalogs (Polaris, AWS Glue, etc.)
- Creating and managing namespaces
- Creating, listing, and dropping tables
- Vending short-lived credentials for table access
- Health checking catalog connectivity

Example:
    >>> from floe_core.plugins.catalog import CatalogPlugin
    >>> class PolarisPlugin(CatalogPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "polaris"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata

if TYPE_CHECKING:
    pass


@runtime_checkable
class Catalog(Protocol):
    """Protocol for PyIceberg-compatible catalog interface.

    This protocol defines the minimal interface expected from a PyIceberg
    Catalog object. It allows type checking without requiring pyiceberg
    as a runtime dependency of floe-core.

    See Also:
        - pyiceberg.catalog.Catalog: Full PyIceberg catalog interface
    """

    def list_namespaces(self) -> list[tuple[str, ...]]:
        """List all namespaces in the catalog."""
        ...

    def list_tables(self, namespace: str) -> list[str]:
        """List all tables in a namespace."""
        ...

    def load_table(self, identifier: str) -> Any:
        """Load a table by identifier."""
        ...


class CatalogPlugin(PluginMetadata):
    """Abstract base class for Iceberg catalog plugins.

    CatalogPlugin extends PluginMetadata with catalog-specific methods
    for managing Iceberg table catalogs. Implementations include Polaris,
    AWS Glue, Unity Catalog, and Hive Metastore.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - connect(): Establish connection to catalog
        - create_namespace(): Create a new namespace
        - list_namespaces(): List namespaces in catalog
        - delete_namespace(): Delete a namespace
        - create_table(): Create a new Iceberg table
        - list_tables(): List tables in a namespace
        - drop_table(): Drop an Iceberg table
        - vend_credentials(): Vend short-lived credentials for table access

    Optional methods with default implementations:
        - health_check(): Check catalog connectivity (default returns unhealthy)

    Example:
        >>> class PolarisPlugin(CatalogPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "polaris"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def connect(self, config: dict) -> Catalog:
        ...         from pyiceberg.catalog import load_catalog
        ...         return load_catalog("polaris", **config)
        ...
        ...     def create_namespace(self, namespace: str, properties: dict | None = None) -> None:
        ...         self._catalog.create_namespace(namespace, properties or {})
        ...
        ...     def list_namespaces(self, parent: str | None = None) -> list[str]:
        ...         return [ns[0] for ns in self._catalog.list_namespaces(parent)]
        ...
        ...     def delete_namespace(self, namespace: str) -> None:
        ...         self._catalog.drop_namespace(namespace)
        ...
        ...     def create_table(self, identifier: str, schema: dict, **kwargs) -> None:
        ...         self._catalog.create_table(identifier, schema, **kwargs)
        ...
        ...     def list_tables(self, namespace: str) -> list[str]:
        ...         return self._catalog.list_tables(namespace)
        ...
        ...     def drop_table(self, identifier: str, purge: bool = False) -> None:
        ...         self._catalog.drop_table(identifier, purge=purge)
        ...
        ...     def vend_credentials(self, table_path: str, operations: list[str]) -> dict:
        ...         return {"access_key": "...", "secret_key": "...", "token": "..."}

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - HealthStatus: Health check result model
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @abstractmethod
    def connect(self, config: dict[str, Any]) -> Catalog:
        """Connect to the catalog and return a PyIceberg Catalog instance.

        Establishes a connection to the Iceberg catalog using the provided
        configuration. The returned Catalog object can be used for all
        subsequent catalog operations.

        Args:
            config: Catalog connection configuration including:
                - uri: Catalog REST endpoint (e.g., "http://polaris:8181/api/catalog")
                - warehouse: Warehouse identifier
                - credential: OAuth2 client credentials (if required)
                - Additional catalog-specific options

        Returns:
            A PyIceberg-compatible Catalog instance.

        Raises:
            ConnectionError: If unable to connect to the catalog.
            AuthenticationError: If credentials are invalid.

        Example:
            >>> config = {
            ...     "uri": "http://polaris:8181/api/catalog",
            ...     "warehouse": "floe_warehouse",
            ...     "credential": "client_id:client_secret"
            ... }
            >>> catalog = plugin.connect(config)
            >>> catalog.list_namespaces()
            [('bronze',), ('silver',), ('gold',)]
        """
        ...

    @abstractmethod
    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a new namespace in the catalog.

        Creates a namespace (database/schema) in the Iceberg catalog.
        Namespaces organize tables into logical groups (e.g., bronze,
        silver, gold medallion layers).

        Args:
            namespace: Namespace name to create (e.g., "bronze", "silver.customers").
            properties: Optional namespace properties (e.g., {"location": "s3://..."}).

        Raises:
            NamespaceAlreadyExistsError: If namespace already exists.
            PermissionError: If lacking permission to create namespaces.

        Example:
            >>> plugin.create_namespace("bronze", {"location": "s3://bucket/bronze"})
            >>> plugin.create_namespace("silver")
        """
        ...

    @abstractmethod
    def vend_credentials(
        self,
        table_path: str,
        operations: list[str],
    ) -> dict[str, Any]:
        """Vend short-lived credentials for table access.

        Returns temporary credentials scoped to specific table operations.
        This implements the credential vending pattern for secure table access
        without exposing long-lived credentials.

        Args:
            table_path: Full table path (e.g., "bronze.raw_customers").
            operations: List of operations to allow (e.g., ["READ"], ["READ", "WRITE"]).

        Returns:
            Dictionary containing temporary credentials:
                - access_key: Temporary access key
                - secret_key: Temporary secret key
                - token: Session token (if applicable)
                - expiration: Credential expiration timestamp

        Raises:
            PermissionError: If lacking permission for requested operations.
            TableNotFoundError: If table does not exist.

        Example:
            >>> creds = plugin.vend_credentials(
            ...     table_path="silver.dim_customers",
            ...     operations=["READ", "WRITE"]
            ... )
            >>> creds
            {
                'access_key': 'ASIA...',
                'secret_key': '...',
                'token': '...',
                'expiration': '2024-01-15T12:00:00Z'
            }
        """
        ...

    @abstractmethod
    def list_namespaces(self, parent: str | None = None) -> list[str]:
        """List namespaces in the catalog.

        Returns all namespaces, optionally filtered by parent namespace
        for hierarchical catalogs.

        Args:
            parent: Optional parent namespace to filter by. If None,
                returns top-level namespaces.

        Returns:
            List of namespace names (e.g., ["bronze", "silver", "gold"]).

        Raises:
            ConnectionError: If not connected to catalog.
            PermissionError: If lacking permission to list namespaces.

        Example:
            >>> plugin.list_namespaces()
            ['bronze', 'silver', 'gold']
            >>> plugin.list_namespaces(parent="silver")
            ['silver.customers', 'silver.orders']
        """
        ...

    @abstractmethod
    def delete_namespace(self, namespace: str) -> None:
        """Delete a namespace from the catalog.

        Removes a namespace and optionally its contents. Most catalogs
        require the namespace to be empty before deletion.

        Args:
            namespace: Namespace name to delete (e.g., "bronze").

        Raises:
            NamespaceNotFoundError: If namespace does not exist.
            NamespaceNotEmptyError: If namespace contains tables.
            PermissionError: If lacking permission to delete.

        Example:
            >>> plugin.delete_namespace("staging")
        """
        ...

    @abstractmethod
    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a new Iceberg table in the catalog.

        Creates an Iceberg table with the specified schema. The table
        location defaults to the warehouse location if not specified.

        Args:
            identifier: Full table identifier (e.g., "bronze.raw_customers").
            schema: Iceberg schema definition as a dictionary with fields:
                - type: "struct"
                - fields: List of field definitions with id, name, type, required
            location: Optional storage location override (e.g., "s3://bucket/path").
            properties: Optional table properties (e.g., {"write.format.default": "parquet"}).

        Raises:
            TableAlreadyExistsError: If table already exists.
            NamespaceNotFoundError: If namespace does not exist.
            PermissionError: If lacking permission to create tables.
            ValidationError: If schema is invalid.

        Example:
            >>> schema = {
            ...     "type": "struct",
            ...     "fields": [
            ...         {"id": 1, "name": "id", "type": "long", "required": True},
            ...         {"id": 2, "name": "name", "type": "string", "required": False}
            ...     ]
            ... }
            >>> plugin.create_table("bronze.customers", schema)
        """
        ...

    @abstractmethod
    def list_tables(self, namespace: str) -> list[str]:
        """List tables in a namespace.

        Returns all table identifiers within the specified namespace.

        Args:
            namespace: Namespace to list tables from (e.g., "bronze").

        Returns:
            List of table identifiers (e.g., ["bronze.customers", "bronze.orders"]).

        Raises:
            NamespaceNotFoundError: If namespace does not exist.
            PermissionError: If lacking permission to list tables.

        Example:
            >>> plugin.list_tables("bronze")
            ['bronze.raw_customers', 'bronze.raw_orders', 'bronze.raw_products']
        """
        ...

    @abstractmethod
    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop an Iceberg table from the catalog.

        Removes the table metadata from the catalog. If purge is True,
        also deletes the underlying data files.

        Args:
            identifier: Full table identifier (e.g., "bronze.raw_customers").
            purge: If True, also delete underlying data files. Defaults to False.

        Raises:
            TableNotFoundError: If table does not exist.
            PermissionError: If lacking permission to drop tables.

        Example:
            >>> plugin.drop_table("staging.temp_table")
            >>> plugin.drop_table("staging.old_data", purge=True)  # Also delete files
        """
        ...

    def health_check(self, timeout: float = 1.0) -> HealthStatus:
        """Check catalog connectivity and health.

        Performs a lightweight operation (e.g., list namespaces) to verify
        the catalog is reachable and responding within the timeout period.

        This method overrides the base PluginMetadata.health_check() to add
        timeout support. Concrete implementations should override to provide
        actual health checks with timeout handling.

        Args:
            timeout: Maximum time in seconds to wait for response.
                Defaults to 1.0 second.

        Returns:
            HealthStatus indicating whether catalog is healthy.

        Example:
            >>> status = plugin.health_check(timeout=2.0)
            >>> if status.state == HealthState.HEALTHY:
            ...     print(f"Catalog OK ({status.details.get('latency_ms')}ms)")
            ... else:
            ...     print(f"Catalog unhealthy: {status.message}")
        """
        return HealthStatus(
            state=HealthState.UNHEALTHY,
            message="health_check not implemented - subclass must override",
            details={"timeout": timeout},
        )
