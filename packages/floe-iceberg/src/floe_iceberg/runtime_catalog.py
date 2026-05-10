"""Translate Floe runtime catalog projections into PyIceberg connection config."""

from __future__ import annotations

from typing import Any

from floe_core.schemas.compiled_artifacts import RuntimeCatalogConnection


def runtime_catalog_connection_to_pyiceberg_config(
    connection: RuntimeCatalogConnection | None,
) -> dict[str, Any]:
    """Return PyIceberg catalog connection properties for a runtime projection."""
    if connection is None:
        return {}

    config: dict[str, Any] = {}
    if connection.catalog_uri is not None:
        config["uri"] = connection.catalog_uri
    if connection.warehouse is not None:
        config["warehouse"] = connection.warehouse
    if connection.storage_endpoint is not None:
        config["s3.endpoint"] = connection.storage_endpoint
    if connection.region is not None:
        config["s3.region"] = connection.region
    if connection.path_style_access is not None:
        config["s3.path-style-access"] = str(connection.path_style_access).lower()
    config.update(connection.properties)
    return config
