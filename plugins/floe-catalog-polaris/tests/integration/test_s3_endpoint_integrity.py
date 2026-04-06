"""Integration test: client S3 endpoint survives table load (AC-2).

Connects to a real Polaris catalog with s3.endpoint configured, loads a
table, and asserts the FileIO uses the client-provided endpoint — not a
server-provided override.

Requirements:
    AC-2: PyIceberg client S3 endpoint MUST survive table load
"""

from __future__ import annotations

import logging
import os
import uuid

import pytest
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType

from floe_catalog_polaris.config import PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

logger = logging.getLogger(__name__)


def _get_minio_endpoint() -> str:
    """Get MinIO endpoint for tests.

    Returns:
        MinIO S3-compatible endpoint URL.
    """
    return os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")


@pytest.mark.integration
@pytest.mark.requirement("AC-2")
def test_client_s3_endpoint_survives_table_load(
    polaris_config: PolarisCatalogConfig,
) -> None:
    """Client s3.endpoint is preserved after loading a table from Polaris.

    Creates a table via Polaris, then loads it using
    load_table_with_client_endpoint(). Asserts the FileIO properties
    use the client-provided s3.endpoint, not a server override.
    """
    client_endpoint = _get_minio_endpoint()
    namespace = f"test_ep_{uuid.uuid4().hex[:8]}"

    plugin = PolarisCatalogPlugin(config=polaris_config)

    # Connect with explicit s3.endpoint
    catalog = plugin.connect(
        {
            "s3.endpoint": client_endpoint,
            "s3.path-style-access": "true",
        }
    )

    try:
        # Create namespace and table
        catalog.create_namespace(namespace)  # type: ignore[union-attr]

        schema = Schema(
            NestedField(field_id=1, name="id", field_type=LongType(), required=True),
            NestedField(field_id=2, name="name", field_type=StringType(), required=False),
        )
        table_name = f"{namespace}.test_endpoint"
        catalog.create_table(table_name, schema=schema)  # type: ignore[union-attr]

        # Load table with client endpoint fixup
        table = plugin.load_table_with_client_endpoint(table_name)

        # Assert the FileIO uses the client endpoint
        io_props = getattr(table.io, "properties", {})
        assert io_props.get("s3.endpoint") == client_endpoint, (
            f"FileIO s3.endpoint is '{io_props.get('s3.endpoint')}', "
            f"expected client endpoint '{client_endpoint}'"
        )

    finally:
        # Cleanup: drop table and namespace
        try:
            catalog.drop_table(table_name)  # type: ignore[union-attr]
        except Exception:
            logger.warning("cleanup_drop_table_failed", exc_info=True)
        try:
            catalog.drop_namespace(namespace)  # type: ignore[union-attr]
        except Exception:
            logger.warning("cleanup_drop_namespace_failed", exc_info=True)


@pytest.mark.integration
@pytest.mark.requirement("AC-2")
def test_plugin_stores_endpoint_from_connect(
    polaris_config: PolarisCatalogConfig,
) -> None:
    """Plugin stores client s3.endpoint after connect() for later fixup."""
    client_endpoint = _get_minio_endpoint()

    plugin = PolarisCatalogPlugin(config=polaris_config)
    plugin.connect(
        {
            "s3.endpoint": client_endpoint,
            "s3.path-style-access": "true",
        }
    )

    assert plugin._client_s3_endpoint == client_endpoint
