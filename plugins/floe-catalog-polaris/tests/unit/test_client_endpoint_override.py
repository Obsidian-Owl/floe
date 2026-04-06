"""Unit tests for client S3 endpoint override after table load (AC-5).

Verifies that PolarisCatalogPlugin.load_table_with_client_endpoint()
re-applies the client-provided s3.endpoint to the table's FileIO
properties, guarding against server-side table-default overrides.

Requirements:
    AC-5: Polaris catalog plugin applies client endpoint override after table load
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin


def _make_config() -> PolarisCatalogConfig:
    """Create a minimal PolarisCatalogConfig for testing."""
    return PolarisCatalogConfig(
        uri="http://polaris:8181/api/catalog",
        warehouse="test-warehouse",
        oauth2=OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="http://polaris:8181/api/catalog/v1/oauth/tokens",
        ),
    )


def _make_plugin_with_catalog(
    client_endpoint: str,
    server_endpoint: str,
) -> tuple[PolarisCatalogPlugin, MagicMock]:
    """Create a plugin with a mock catalog that returns a table with server endpoint.

    Args:
        client_endpoint: The client-provided s3.endpoint.
        server_endpoint: The server-side s3.endpoint in table metadata.

    Returns:
        Tuple of (plugin, mock_table).
    """
    plugin = PolarisCatalogPlugin(config=_make_config())

    # Simulate connect() having stored the client endpoint
    plugin._client_s3_endpoint = client_endpoint

    # Mock catalog
    mock_catalog = MagicMock()
    plugin._catalog = mock_catalog

    # Mock table with FileIO that has server-provided endpoint
    mock_table = MagicMock()
    mock_table.io.properties = {
        "s3.endpoint": server_endpoint,
        "s3.region": "us-east-1",
    }
    mock_catalog.load_table.return_value = mock_table

    return plugin, mock_table


@pytest.mark.requirement("AC-5")
def test_client_endpoint_overrides_server_endpoint() -> None:
    """Client s3.endpoint replaces server-provided endpoint after table load."""
    client_ep = "http://external-minio:9000"
    server_ep = "http://k8s-internal-minio:9000"

    plugin, mock_table = _make_plugin_with_catalog(client_ep, server_ep)

    result = plugin.load_table_with_client_endpoint("bronze.customers")

    assert result is mock_table
    assert mock_table.io.properties["s3.endpoint"] == client_ep
    plugin._catalog.load_table.assert_called_once_with("bronze.customers")


@pytest.mark.requirement("AC-5")
def test_client_endpoint_preserved_when_server_matches() -> None:
    """Client endpoint unchanged when server already has correct value."""
    endpoint = "http://minio:9000"

    plugin, mock_table = _make_plugin_with_catalog(endpoint, endpoint)

    result = plugin.load_table_with_client_endpoint("bronze.customers")

    assert result is mock_table
    assert mock_table.io.properties["s3.endpoint"] == endpoint
    plugin._catalog.load_table.assert_called_once_with("bronze.customers")


@pytest.mark.requirement("AC-5")
def test_no_client_endpoint_leaves_server_endpoint_unchanged() -> None:
    """When no client endpoint was set, server endpoint is not modified."""
    plugin = PolarisCatalogPlugin(config=_make_config())
    plugin._client_s3_endpoint = None

    mock_catalog = MagicMock()
    plugin._catalog = mock_catalog

    server_ep = "http://k8s-internal:9000"
    mock_table = MagicMock()
    mock_table.io.properties = {"s3.endpoint": server_ep}
    mock_catalog.load_table.return_value = mock_table

    plugin.load_table_with_client_endpoint("bronze.customers")

    assert mock_table.io.properties["s3.endpoint"] == server_ep
    mock_catalog.load_table.assert_called_once_with("bronze.customers")


@pytest.mark.requirement("AC-5")
def test_raises_when_no_catalog_connection() -> None:
    """load_table_with_client_endpoint raises when no catalog exists."""
    from floe_core.plugin_errors import CatalogUnavailableError

    plugin = PolarisCatalogPlugin(config=_make_config())
    # _catalog is None (no connect() call)

    with pytest.raises(CatalogUnavailableError, match="No catalog connection"):
        plugin.load_table_with_client_endpoint("bronze.customers")


@pytest.mark.requirement("AC-5")
def test_connect_stores_client_s3_endpoint() -> None:
    """connect() stores the client s3.endpoint from config for later use."""
    plugin = PolarisCatalogPlugin(config=_make_config())

    with patch(
        "floe_catalog_polaris.plugin.load_catalog",
        return_value=MagicMock(),
    ):
        plugin.connect({"s3.endpoint": "http://my-endpoint:9000"})

    assert plugin._client_s3_endpoint == "http://my-endpoint:9000"


@pytest.mark.requirement("AC-5")
def test_connect_without_s3_endpoint_stores_none() -> None:
    """connect() without s3.endpoint stores None."""
    plugin = PolarisCatalogPlugin(config=_make_config())

    with patch(
        "floe_catalog_polaris.plugin.load_catalog",
        return_value=MagicMock(),
    ):
        plugin.connect({})

    assert plugin._client_s3_endpoint is None
