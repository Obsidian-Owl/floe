"""Integration test fixtures for floe-catalog-polaris.

Integration tests require real Polaris instance running in Kind cluster.
Tests should inherit from IntegrationTestBase and use @pytest.mark.integration marker.

Fixtures provided:
    - polaris_config: PolarisCatalogConfig with test credentials
    - polaris_plugin: Connected PolarisCatalogPlugin instance
    - polaris_catalog: PyIceberg RestCatalog instance
    - test_namespace: Unique namespace with auto-cleanup
    - test_table: Sample table in unique namespace with auto-cleanup
    - simple_schema: Simple Iceberg schema for testing

Usage:
    @pytest.mark.integration
    def test_something(polaris_plugin: PolarisCatalogPlugin) -> None:
        namespaces = polaris_plugin.list_namespaces()
        assert isinstance(namespaces, list)
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr
from pyiceberg.catalog import Catalog
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType
from testing.fixtures.services import check_service_health

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

if TYPE_CHECKING:
    pass


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require Polaris)"
    )
    config.addinivalue_line(
        "markers",
        "requires_sts: marks tests requiring STS-enabled storage backend",
    )


def _get_polaris_host() -> str:
    """Get the Polaris host for the current environment.

    Returns:
        Hostname for Polaris (localhost for Kind cluster).
    """
    # For Kind cluster, services are exposed via NodePort on localhost
    return os.environ.get("POLARIS_HOST", "localhost")


def _get_polaris_port() -> int:
    """Get the Polaris port for the current environment.

    Returns:
        Port number for Polaris REST API.
    """
    return int(os.environ.get("POLARIS_PORT", "8181"))


@pytest.fixture(scope="session")
def polaris_host() -> str:
    """Get Polaris host from environment or default.

    Returns:
        Polaris host address.
    """
    return _get_polaris_host()


@pytest.fixture(scope="session")
def polaris_port() -> int:
    """Get Polaris port from environment or default.

    Returns:
        Polaris port number.
    """
    return _get_polaris_port()


@pytest.fixture(scope="session")
def polaris_uri(polaris_host: str, polaris_port: int) -> str:
    """Get Polaris URI from environment or construct from host/port.

    Returns:
        Polaris REST API URI.
    """
    return os.environ.get(
        "POLARIS_URI",
        f"http://{polaris_host}:{polaris_port}/api/catalog",
    )


@pytest.fixture(scope="session")
def polaris_warehouse() -> str:
    """Get Polaris warehouse name from environment or use default.

    Returns:
        Warehouse name for tests.
    """
    return os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")


@pytest.fixture(scope="session")
def polaris_token_url(polaris_host: str, polaris_port: int) -> str:
    """Get Polaris OAuth2 token URL.

    Returns:
        OAuth2 token endpoint URL.
    """
    return os.environ.get(
        "POLARIS_TOKEN_URL",
        f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
    )


@pytest.fixture(scope="session")
def polaris_client_id() -> str:
    """Get Polaris client ID from environment or default.

    Returns:
        OAuth2 client ID.
    """
    return os.environ.get("POLARIS_CLIENT_ID", "test-admin")


@pytest.fixture(scope="session")
def polaris_client_secret() -> str:
    """Get Polaris client secret from environment or default.

    Returns:
        OAuth2 client secret.
    """
    return os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")


@pytest.fixture(scope="session")
def polaris_config(
    polaris_uri: str,
    polaris_warehouse: str,
    polaris_token_url: str,
    polaris_client_id: str,
    polaris_client_secret: str,
) -> PolarisCatalogConfig:
    """Create Polaris configuration for integration tests.

    This is a session-scoped fixture to avoid recreating config for each test.

    Returns:
        PolarisCatalogConfig with test credentials.

    Raises:
        pytest.fail: If Polaris is not accessible.
    """
    # Verify Polaris is accessible before creating config
    host = _get_polaris_host()
    port = _get_polaris_port()

    if not check_service_health(host, port, timeout=5.0):
        pytest.fail(
            f"Polaris not accessible at {host}:{port}\nStart the Kind cluster with: make kind-up"
        )

    return PolarisCatalogConfig(
        uri=polaris_uri,
        warehouse=polaris_warehouse,
        oauth2=OAuth2Config(
            client_id=polaris_client_id,
            client_secret=SecretStr(polaris_client_secret),
            token_url=polaris_token_url,
            scope="PRINCIPAL_ROLE:ALL",
        ),
    )


@pytest.fixture
def polaris_plugin(
    polaris_config: PolarisCatalogConfig,
) -> Generator[PolarisCatalogPlugin, None, None]:
    """Create a connected PolarisCatalogPlugin for testing.

    This fixture creates a new plugin instance and connects it to Polaris.
    The connection is closed after the test.

    Yields:
        Connected PolarisCatalogPlugin instance.
    """
    plugin = PolarisCatalogPlugin(config=polaris_config)
    plugin.connect({})
    yield plugin
    # Plugin doesn't have explicit close(), connection cleanup handled by GC


@pytest.fixture
def polaris_catalog(polaris_plugin: PolarisCatalogPlugin) -> Catalog:
    """Get the underlying PyIceberg Catalog from the plugin.

    Useful for tests that need direct access to PyIceberg operations.

    Returns:
        PyIceberg Catalog instance (RestCatalog).
    """
    catalog = polaris_plugin._catalog
    if catalog is None:
        pytest.fail("Plugin not connected - catalog is None")
    return catalog


@pytest.fixture
def simple_schema() -> Schema:
    """Return a simple Iceberg schema for testing.

    Returns:
        PyIceberg Schema with id (long) and name (string) fields.
    """
    return Schema(
        NestedField(field_id=1, name="id", field_type=LongType(), required=True),
        NestedField(field_id=2, name="name", field_type=StringType(), required=False),
    )


def _generate_unique_namespace(prefix: str = "test") -> str:
    """Generate a unique namespace name for testing.

    Args:
        prefix: Prefix for the namespace name.

    Returns:
        Unique namespace name (e.g., "test_a1b2c3d4").
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_namespace(
    polaris_plugin: PolarisCatalogPlugin,
) -> Generator[str, None, None]:
    """Create a unique namespace for testing with auto-cleanup.

    Creates a new namespace with a unique name before the test and
    deletes it (along with any tables) after the test completes.

    Yields:
        Unique namespace name.

    Example:
        def test_something(test_namespace: str, polaris_plugin) -> None:
            # Namespace already created
            tables = polaris_plugin.list_tables(test_namespace)
            # After test, namespace is automatically deleted
    """
    namespace = _generate_unique_namespace("test")

    # Create the namespace
    polaris_plugin.create_namespace(namespace)

    yield namespace

    # Cleanup: delete tables first, then namespace
    try:
        tables = polaris_plugin.list_tables(namespace)
        for table in tables:
            try:
                polaris_plugin.drop_table(table, purge=True)
            except Exception:
                pass  # Best effort cleanup
    except Exception:
        pass  # Namespace might be empty or already deleted

    try:
        polaris_plugin.delete_namespace(namespace)
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture
def test_table(
    polaris_plugin: PolarisCatalogPlugin,
    simple_schema: Schema,
) -> Generator[str, None, None]:
    """Create a test table in a unique namespace with auto-cleanup.

    Creates a new namespace and table before the test and cleans up
    both after the test completes.

    Yields:
        Fully qualified table name (e.g., "test_a1b2c3d4.customers").

    Example:
        def test_table_ops(test_table: str, polaris_plugin) -> None:
            # Table already exists at test_table path
            metadata = polaris_plugin.get_table_metadata(test_table)
            # After test, table and namespace are deleted
    """
    namespace = _generate_unique_namespace("tbl")
    table_name = f"{namespace}.customers"

    # Create namespace and table
    polaris_plugin.create_namespace(namespace)
    polaris_plugin.create_table(table_name, simple_schema)

    yield table_name

    # Cleanup: drop table then namespace
    try:
        polaris_plugin.drop_table(table_name, purge=True)
    except Exception:
        pass  # Best effort cleanup

    try:
        polaris_plugin.delete_namespace(namespace)
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture
def unique_namespace_name() -> str:
    """Generate a unique namespace name without creating it.

    Useful when you need the name but want to control creation yourself.

    Returns:
        Unique namespace name string.
    """
    return _generate_unique_namespace("ns")


@pytest.fixture
def unique_table_name(unique_namespace_name: str) -> str:
    """Generate a unique fully-qualified table name without creating it.

    Useful when you need the name but want to control creation yourself.

    Returns:
        Unique table name string (namespace.table format).
    """
    return f"{unique_namespace_name}.test_table"
