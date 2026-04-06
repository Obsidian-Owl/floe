"""Contract test: S3 endpoint preservation through config chain (AC-3).

Traces the s3.endpoint from CompiledArtifacts.plugins.storage.config.endpoint
through to the catalog config dict passed to PyIceberg, asserting no
intermediate layer silently replaces it or introduces table-default.* keys.

This is a cross-package contract test (floe_core + floe_catalog_polaris).

Requirements:
    AC-3: S3 endpoint flows from manifest.yaml through to PyIceberg FileIO
          without corruption
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins


def _make_polaris_config() -> PolarisCatalogConfig:
    """Create a minimal Polaris config for testing."""
    return PolarisCatalogConfig(
        uri="http://polaris:8181/api/catalog",
        warehouse="test-warehouse",
        oauth2=OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="http://polaris:8181/api/catalog/v1/oauth/tokens",
        ),
    )


def _make_resolved_plugins(storage_endpoint: str) -> ResolvedPlugins:
    """Create ResolvedPlugins with storage config containing the endpoint."""
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=PluginRef(
            type="polaris",
            version="0.1.0",
            config={"uri": "http://polaris:8181/api/catalog"},
        ),
        storage=PluginRef(
            type="s3",
            version="1.0.0",
            config={"endpoint": storage_endpoint},
        ),
        ingestion=None,
        semantic=None,
    )


@pytest.mark.requirement("AC-3")
def test_endpoint_preserved_through_connect() -> None:
    """Client s3.endpoint in connect() config is stored for later use.

    The endpoint defined in manifest.yaml flows through compiled_artifacts
    storage.config.endpoint into the catalog connect() config dict. Verify
    the plugin preserves it without corruption.
    """
    client_endpoint = "http://external-minio:9000"
    plugin = PolarisCatalogPlugin(config=_make_polaris_config())

    captured_config: dict[str, str] = {}

    def mock_load_catalog(name: str, **kwargs: str) -> MagicMock:
        captured_config.update(kwargs)
        return MagicMock()

    with patch(
        "floe_catalog_polaris.plugin.load_catalog",
        side_effect=mock_load_catalog,
    ):
        plugin.connect({"s3.endpoint": client_endpoint})

    # s3.endpoint MUST appear in the config passed to load_catalog
    assert captured_config.get("s3.endpoint") == client_endpoint

    # Plugin MUST store the client endpoint for post-load fixup
    assert plugin._client_s3_endpoint == client_endpoint


@pytest.mark.requirement("AC-3")
def test_no_table_default_keys_in_connect_config() -> None:
    """Connect config dict MUST NOT contain any table-default.* keys.

    table-default.* keys cause PyIceberg to override client config at the
    table level. The connect() config dict should only contain catalog-level
    keys.
    """
    plugin = PolarisCatalogPlugin(config=_make_polaris_config())

    captured_config: dict[str, str] = {}

    def mock_load_catalog(name: str, **kwargs: str) -> MagicMock:
        captured_config.update(kwargs)
        return MagicMock()

    with patch(
        "floe_catalog_polaris.plugin.load_catalog",
        side_effect=mock_load_catalog,
    ):
        plugin.connect(
            {
                "s3.endpoint": "http://minio:9000",
                "s3.region": "us-east-1",
            }
        )

    table_default_keys = [k for k in captured_config if k.startswith("table-default.")]
    assert table_default_keys == [], (
        f"Connect config contains table-default.* keys: {table_default_keys}. "
        "These cause PyIceberg to override client-side config at table level."
    )


@pytest.mark.requirement("AC-3")
def test_endpoint_survives_table_load_fixup() -> None:
    """After table load, client endpoint MUST be re-applied to FileIO.

    Even if the server returns table-default.s3.endpoint in table metadata,
    load_table_with_client_endpoint() must restore the client value.
    """
    client_endpoint = "http://external-minio:9000"
    server_endpoint = "http://k8s-internal-minio:9000"

    plugin = PolarisCatalogPlugin(config=_make_polaris_config())
    plugin._client_s3_endpoint = client_endpoint

    mock_catalog = MagicMock()
    plugin._catalog = mock_catalog

    # Simulate server returning a different endpoint in table metadata
    mock_table = MagicMock()
    mock_table.io.properties = {
        "s3.endpoint": server_endpoint,
        "s3.region": "us-east-1",
    }
    mock_catalog.load_table.return_value = mock_table

    table = plugin.load_table_with_client_endpoint("bronze.customers")

    # Client endpoint MUST survive — server override replaced
    assert table.io.properties["s3.endpoint"] == client_endpoint


@pytest.mark.requirement("AC-3")
def test_storage_plugin_ref_carries_endpoint() -> None:
    """CompiledArtifacts storage plugin ref MUST carry the endpoint value.

    This validates the contract: storage.config.endpoint in CompiledArtifacts
    is the authoritative source of the S3 endpoint value.
    """
    endpoint = "http://my-s3-endpoint:9000"
    plugins = _make_resolved_plugins(endpoint)

    assert plugins.storage is not None
    assert plugins.storage.config is not None
    assert plugins.storage.config["endpoint"] == endpoint
