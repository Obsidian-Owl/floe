"""CatalogPlugin pytest fixtures for unit and integration tests.

Provides mock catalog plugin fixtures for unit tests and real catalog
plugin fixtures for integration tests running in Kind cluster.

Example:
    from testing.fixtures.catalog import mock_catalog_plugin, MockCatalogPlugin

    def test_with_mock_catalog():
        plugin = MockCatalogPlugin()
        plugin.connect({})
        plugin.create_namespace("test_ns")
        assert "test_ns" in plugin.list_namespaces()

Requirements Covered:
    - REQ-041: CatalogPlugin test fixtures
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

if TYPE_CHECKING:
    from floe_core import CatalogPlugin


class CatalogTestConfig(BaseModel):
    """Configuration for catalog plugin testing.

    Provides configuration for both mock and real catalog plugin tests.
    Uses environment variables with sensible defaults for local development.

    Attributes:
        catalog_type: Type of catalog to use (polaris, glue, hive, mock).
        uri: Catalog REST API endpoint URL.
        warehouse: Default warehouse name.
        credential: OAuth2 client credentials (client_id:client_secret).
        namespace_prefix: Prefix for test namespaces (for isolation).
        k8s_namespace: K8s namespace where catalog runs.
    """

    model_config = ConfigDict(frozen=True)

    catalog_type: str = Field(default_factory=lambda: os.environ.get("CATALOG_TYPE", "mock"))
    uri: str = Field(
        default_factory=lambda: os.environ.get("CATALOG_URI", "http://polaris:8181/api/catalog")
    )
    warehouse: str = Field(
        default_factory=lambda: os.environ.get("CATALOG_WAREHOUSE", "test_warehouse")
    )
    credential: SecretStr = Field(
        default_factory=lambda: SecretStr(os.environ.get("CATALOG_CREDENTIAL", "root:secret"))
    )
    namespace_prefix: str = Field(
        default_factory=lambda: os.environ.get("CATALOG_NAMESPACE_PREFIX", "test")
    )
    k8s_namespace: str = Field(default="floe-test")

    @property
    def k8s_uri(self) -> str:
        """Get K8s DNS URI for catalog service."""
        if "://" in self.uri:
            proto, rest = self.uri.split("://", 1)
            host_port, path = rest.split("/", 1) if "/" in rest else (rest, "")
            host = host_port.split(":")[0]
            port = host_port.split(":")[1] if ":" in host_port else "8181"
            k8s_host = f"{host}.{self.k8s_namespace}.svc.cluster.local"
            return f"{proto}://{k8s_host}:{port}/{path}"
        return self.uri


class CatalogConnectionError(Exception):
    """Raised when catalog plugin connection fails."""

    pass


class MockCatalog:
    """Mock PyIceberg-compatible catalog for unit tests.

    Provides an in-memory implementation of the Catalog protocol
    for testing without requiring a real catalog service.

    Example:
        >>> catalog = MockCatalog()
        >>> catalog.create_namespace(("test",))
        >>> catalog.list_namespaces()
        [('test',)]
    """

    def __init__(self) -> None:
        """Initialize mock catalog with empty state."""
        self._namespaces: dict[tuple[str, ...], dict[str, str]] = {}
        self._tables: dict[str, dict[str, Any]] = {}

    def list_namespaces(self, parent: tuple[str, ...] | None = None) -> list[tuple[str, ...]]:
        """List all namespaces in the catalog.

        Args:
            parent: Optional parent namespace tuple to filter by.

        Returns:
            List of namespace tuples.
        """
        if parent is None:
            return list(self._namespaces.keys())
        return [ns for ns in self._namespaces if ns[: len(parent)] == parent]

    def create_namespace(
        self,
        namespace: tuple[str, ...] | str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a namespace in the catalog.

        Args:
            namespace: Namespace as tuple or dot-separated string.
            properties: Optional namespace properties.

        Raises:
            ValueError: If namespace already exists.
        """
        if isinstance(namespace, str):
            namespace = tuple(namespace.split("."))
        if namespace in self._namespaces:
            raise ValueError(f"Namespace {namespace} already exists")
        self._namespaces[namespace] = properties or {}

    def drop_namespace(self, namespace: tuple[str, ...] | str) -> None:
        """Drop a namespace from the catalog.

        Args:
            namespace: Namespace as tuple or dot-separated string.

        Raises:
            KeyError: If namespace does not exist.
        """
        if isinstance(namespace, str):
            namespace = tuple(namespace.split("."))
        if namespace not in self._namespaces:
            raise KeyError(f"Namespace {namespace} not found")
        # Check for tables in namespace
        ns_prefix = ".".join(namespace)
        for table_id in self._tables:
            if table_id.startswith(ns_prefix + "."):
                raise ValueError(f"Namespace {namespace} is not empty")
        del self._namespaces[namespace]

    def list_tables(self, namespace: str | tuple[str, ...]) -> list[tuple[str, ...]]:
        """List tables in a namespace.

        Args:
            namespace: Namespace name or tuple.

        Returns:
            List of table identifier tuples.
        """
        if isinstance(namespace, tuple):
            namespace = ".".join(namespace)
        result: list[tuple[str, ...]] = []
        for table_id in self._tables:
            parts = table_id.rsplit(".", 1)
            if len(parts) == 2 and parts[0] == namespace:
                result.append(tuple(table_id.split(".")))
        return result

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> Any:
        """Create a table in the catalog.

        Args:
            identifier: Full table identifier (e.g., "ns.table").
            schema: Iceberg schema definition.
            location: Optional storage location.
            properties: Optional table properties.

        Returns:
            Mock table object.

        Raises:
            ValueError: If table already exists.
        """
        if identifier in self._tables:
            raise ValueError(f"Table {identifier} already exists")
        self._tables[identifier] = {
            "schema": schema,
            "location": location or f"s3://mock/{identifier}",
            "properties": properties or {},
        }
        return self._tables[identifier]

    def drop_table(
        self,
        identifier: str,
        purge_requested: bool = False,  # noqa: ARG002
    ) -> None:
        """Drop a table from the catalog.

        Args:
            identifier: Full table identifier.
            purge_requested: If True, purge underlying data. Not used by mock.

        Raises:
            KeyError: If table does not exist.
        """
        del purge_requested  # Unused in mock implementation
        if identifier not in self._tables:
            raise KeyError(f"Table {identifier} not found")
        del self._tables[identifier]

    def load_table(self, identifier: str) -> Any:
        """Load a table from the catalog.

        Args:
            identifier: Full table identifier.

        Returns:
            Mock table object.

        Raises:
            KeyError: If table does not exist.
        """
        if identifier not in self._tables:
            raise KeyError(f"Table {identifier} not found")
        return MockTable(identifier, self._tables[identifier])


class MockTable:
    """Mock Iceberg table for unit tests.

    Provides a minimal table object with io.properties for credential vending.
    """

    def __init__(self, identifier: str, data: dict[str, Any]) -> None:
        """Initialize mock table.

        Args:
            identifier: Table identifier.
            data: Table metadata dict.
        """
        self.identifier = identifier
        self.schema = data.get("schema", {})
        self.location = data.get("location", "")
        self.properties = data.get("properties", {})
        self.io = MockTableIO()


class MockTableIO:
    """Mock table IO with properties dict for credential vending."""

    def __init__(self) -> None:
        """Initialize with mock credential properties."""
        self.properties: dict[str, str] = {
            "s3.access-key-id": "MOCK_ACCESS_KEY",
            "s3.secret-access-key": "MOCK_SECRET_KEY",
            "s3.session-token": "MOCK_SESSION_TOKEN",
            "s3.session-token-expires-at": "2099-12-31T23:59:59Z",
        }


class MockCatalogPlugin:
    """Mock CatalogPlugin implementation for unit tests.

    Provides an in-memory implementation of the CatalogPlugin ABC
    for testing without requiring real catalog infrastructure.

    Example:
        >>> plugin = MockCatalogPlugin()
        >>> plugin.connect({})
        >>> plugin.create_namespace("test_ns")
        >>> assert "test_ns" in plugin.list_namespaces()
    """

    def __init__(self, config: CatalogTestConfig | None = None) -> None:
        """Initialize mock plugin.

        Args:
            config: Optional test configuration.
        """
        self._config = config or CatalogTestConfig()
        self._catalog: MockCatalog | None = None
        self._connected = False

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "mock"

    @property
    def version(self) -> str:
        """Return the plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Return the required floe API version."""
        return "0.1"

    @property
    def description(self) -> str:
        """Return the plugin description."""
        return "Mock catalog plugin for testing"

    @property
    def dependencies(self) -> list[str]:
        """Return plugin dependencies."""
        return []

    def connect(
        self,
        config: dict[str, Any],  # noqa: ARG002
    ) -> MockCatalog:
        """Connect to the mock catalog.

        Args:
            config: Connection configuration (ignored for mock).

        Returns:
            MockCatalog instance.
        """
        del config  # Unused in mock implementation
        self._catalog = MockCatalog()
        self._connected = True
        return self._catalog

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a namespace in the mock catalog.

        Args:
            namespace: Namespace name to create.
            properties: Optional namespace properties.

        Raises:
            RuntimeError: If not connected.
        """
        if self._catalog is None:
            raise RuntimeError("Catalog not connected. Call connect() first.")
        self._catalog.create_namespace(namespace, properties)

    def list_namespaces(self, parent: str | None = None) -> list[str]:
        """List namespaces in the mock catalog.

        Args:
            parent: Optional parent namespace.

        Returns:
            List of namespace names.

        Raises:
            RuntimeError: If not connected.
        """
        if self._catalog is None:
            raise RuntimeError("Catalog not connected. Call connect() first.")
        parent_tuple = tuple(parent.split(".")) if parent else None
        namespaces = self._catalog.list_namespaces(parent_tuple)
        return [".".join(ns) for ns in namespaces]

    def delete_namespace(self, namespace: str) -> None:
        """Delete a namespace from the mock catalog.

        Args:
            namespace: Namespace name to delete.

        Raises:
            RuntimeError: If not connected.
        """
        if self._catalog is None:
            raise RuntimeError("Catalog not connected. Call connect() first.")
        self._catalog.drop_namespace(namespace)

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a table in the mock catalog.

        Args:
            identifier: Full table identifier.
            schema: Iceberg schema definition.
            location: Optional storage location.
            properties: Optional table properties.

        Raises:
            RuntimeError: If not connected.
        """
        if self._catalog is None:
            raise RuntimeError("Catalog not connected. Call connect() first.")
        self._catalog.create_table(identifier, schema, location, properties)

    def list_tables(self, namespace: str) -> list[str]:
        """List tables in a namespace.

        Args:
            namespace: Namespace name.

        Returns:
            List of table identifiers.

        Raises:
            RuntimeError: If not connected.
        """
        if self._catalog is None:
            raise RuntimeError("Catalog not connected. Call connect() first.")
        tables = self._catalog.list_tables(namespace)
        return [".".join(t) for t in tables]

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop a table from the mock catalog.

        Args:
            identifier: Full table identifier.
            purge: If True, purge underlying data.

        Raises:
            RuntimeError: If not connected.
        """
        if self._catalog is None:
            raise RuntimeError("Catalog not connected. Call connect() first.")
        self._catalog.drop_table(identifier, purge)

    def vend_credentials(
        self,
        table_path: str,
        operations: list[str],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Vend mock credentials for table access.

        Args:
            table_path: Full table path.
            operations: List of operations (ignored for mock).

        Returns:
            Dictionary with mock credentials.

        Raises:
            RuntimeError: If not connected.
        """
        del operations  # Unused in mock implementation
        if self._catalog is None:
            raise RuntimeError("Catalog not connected. Call connect() first.")
        table = self._catalog.load_table(table_path)
        return {
            "access_key": table.io.properties.get("s3.access-key-id", ""),
            "secret_key": table.io.properties.get("s3.secret-access-key", ""),
            "token": table.io.properties.get("s3.session-token", ""),
            "expiration": table.io.properties.get("s3.session-token-expires-at", ""),
        }

    def health_check(
        self,
        timeout: float = 1.0,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Check mock catalog health.

        Args:
            timeout: Health check timeout (ignored for mock).

        Returns:
            Health status dict.
        """
        del timeout  # Unused in mock implementation
        return {
            "state": "healthy" if self._connected else "unhealthy",
            "message": "Mock catalog" + (" connected" if self._connected else " not connected"),
            "details": {"connected": self._connected},
        }


def create_mock_catalog_plugin(
    config: CatalogTestConfig | None = None,
) -> MockCatalogPlugin:
    """Create a mock catalog plugin for unit testing.

    Args:
        config: Optional test configuration.

    Returns:
        MockCatalogPlugin instance.

    Example:
        >>> plugin = create_mock_catalog_plugin()
        >>> plugin.connect({})
        >>> plugin.create_namespace("test")
    """
    return MockCatalogPlugin(config)


@contextmanager
def mock_catalog_plugin_context(
    config: CatalogTestConfig | None = None,
) -> Generator[MockCatalogPlugin, None, None]:
    """Context manager for mock catalog plugin.

    Creates and connects a mock plugin on entry, no cleanup needed on exit.

    Args:
        config: Optional test configuration.

    Yields:
        Connected MockCatalogPlugin instance.

    Example:
        with mock_catalog_plugin_context() as plugin:
            plugin.create_namespace("test")
            assert "test" in plugin.list_namespaces()
    """
    plugin = create_mock_catalog_plugin(config)
    plugin.connect({})
    yield plugin


def generate_unique_namespace(prefix: str = "test") -> str:
    """Generate a unique namespace name for test isolation.

    Args:
        prefix: Namespace prefix.

    Returns:
        Unique namespace name like "test_abc12345".

    Example:
        >>> ns = generate_unique_namespace("mytest")
        >>> ns.startswith("mytest_")
        True
    """
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{suffix}"


def create_polaris_catalog_plugin(
    config: CatalogTestConfig | None = None,
) -> CatalogPlugin:
    """Create a real Polaris catalog plugin for integration testing.

    Requires the floe-catalog-polaris package to be installed.

    Args:
        config: Optional test configuration.

    Returns:
        PolarisCatalogPlugin instance.

    Raises:
        CatalogConnectionError: If plugin creation fails.

    Example:
        >>> plugin = create_polaris_catalog_plugin()
        >>> plugin.connect({})
    """
    try:
        # Optional import - floe-catalog-polaris is not a required dependency
        from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin
    except ImportError as e:
        raise CatalogConnectionError(
            "floe-catalog-polaris not installed. Install with: pip install floe-catalog-polaris"
        ) from e

    if config is None:
        config = CatalogTestConfig()

    try:
        # Parse credential into client_id:client_secret
        cred_value = config.credential.get_secret_value()
        parts = cred_value.split(":", 1)
        client_id = parts[0]
        client_secret = parts[1] if len(parts) > 1 else ""

        # Derive token URL from catalog URI
        # Default: {uri}/v1/oauth/tokens (PyIceberg convention)
        token_url = (
            f"{config.uri.rstrip('/').rsplit('/api/catalog', 1)[0]}/api/catalog/v1/oauth/tokens"
        )

        polaris_config = PolarisCatalogConfig(
            uri=config.uri,
            warehouse=config.warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
            ),
        )
        return PolarisCatalogPlugin(config=polaris_config)
    except Exception as e:
        raise CatalogConnectionError(f"Failed to create Polaris catalog plugin: {e}") from e


@contextmanager
def polaris_catalog_plugin_context(
    config: CatalogTestConfig | None = None,
) -> Generator[CatalogPlugin, None, None]:
    """Context manager for Polaris catalog plugin.

    Creates and connects a Polaris plugin on entry, no cleanup needed on exit.

    Args:
        config: Optional test configuration.

    Yields:
        Connected PolarisCatalogPlugin instance.

    Raises:
        CatalogConnectionError: If connection fails.

    Example:
        with polaris_catalog_plugin_context() as plugin:
            namespaces = plugin.list_namespaces()
    """
    plugin = create_polaris_catalog_plugin(config)
    plugin.connect({})
    yield plugin


def get_catalog_connection_info(config: CatalogTestConfig) -> dict[str, Any]:
    """Get connection info dictionary (for logging/debugging).

    Args:
        config: Catalog test configuration.

    Returns:
        Dictionary with connection info (credential masked).
    """
    return {
        "catalog_type": config.catalog_type,
        "uri": config.uri,
        "warehouse": config.warehouse,
        "namespace_prefix": config.namespace_prefix,
        "k8s_namespace": config.k8s_namespace,
        "k8s_uri": config.k8s_uri,
    }


__all__ = [
    "CatalogConnectionError",
    "CatalogTestConfig",
    "MockCatalog",
    "MockCatalogPlugin",
    "MockTable",
    "MockTableIO",
    "create_mock_catalog_plugin",
    "create_polaris_catalog_plugin",
    "generate_unique_namespace",
    "get_catalog_connection_info",
    "mock_catalog_plugin_context",
    "polaris_catalog_plugin_context",
]
