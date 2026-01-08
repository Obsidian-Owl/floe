"""CatalogPlugin ABC for Iceberg catalog plugins.

This module defines the abstract base class for catalog plugins that
provide Iceberg table catalog functionality. Catalog plugins are responsible for:
- Connecting to Iceberg REST catalogs (Polaris, AWS Glue, etc.)
- Creating and managing namespaces
- Vending short-lived credentials for table access

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

from floe_core.plugin_metadata import PluginMetadata

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
        - connect() method
        - create_namespace() method
        - vend_credentials() method

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
        ...     def vend_credentials(self, table_path: str, operations: list[str]) -> dict:
        ...         return {"access_key": "...", "secret_key": "...", "token": "..."}

    See Also:
        - PluginMetadata: Base class with common plugin attributes
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
