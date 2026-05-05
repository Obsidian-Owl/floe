"""Unit tests for resolving product ingestion sources into plugin config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins
from floe_core.schemas.floe_spec import (
    FloeMetadata,
    FloeSpec,
    ProductIngestionSpec,
    TransformSpec,
)
from floe_core.schemas.manifest import PlatformManifest


def _spec_with_ingestion() -> FloeSpec:
    return FloeSpec(
        api_version="floe.dev/v1",
        kind="FloeSpec",
        metadata=FloeMetadata(name="orders-product", version="1.0.0"),
        transforms=[TransformSpec(name="orders")],
        ingestion=ProductIngestionSpec.model_validate(
            {
                "sources": [
                    {
                        "name": "orders_csv",
                        "sourceType": "filesystem",
                        "format": "csv",
                        "path": "./data/customers.csv",
                        "destinationTable": "bronze.orders",
                        "writeMode": "merge",
                        "schemaContract": "freeze",
                        "cursorField": "updated_at",
                        "primaryKey": ["order_id"],
                    }
                ]
            }
        ),
    )


def _plugins_with_ingestion_config() -> ResolvedPlugins:
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0", config={}),
        orchestrator=PluginRef(type="dagster", version="1.5.0", config={}),
        ingestion=PluginRef(
            type="dlt",
            version="0.1.0",
            config={
                "catalog_config": {
                    "uri": "http://polaris:8181/api/catalog",
                    "warehouse": "floe",
                },
                "retry_config": {"max_retries": 5, "initial_delay_seconds": 2.0},
            },
        ),
    )


def test_resolve_ingestion_config_merges_product_sources() -> None:
    """Manifest-selected ingestion receives product-owned sources."""
    from floe_core.compilation.resolver import resolve_ingestion_config

    resolved = resolve_ingestion_config(_spec_with_ingestion(), _plugins_with_ingestion_config())

    assert resolved.ingestion is not None
    assert resolved.ingestion.type == "dlt"
    assert resolved.ingestion.config is not None
    assert resolved.ingestion.config["sources"] == [
        {
            "name": "orders_csv",
            "source_type": "filesystem",
            "destination_table": "bronze.orders",
            "write_mode": "merge",
            "schema_contract": "freeze",
            "cursor_field": "updated_at",
            "primary_key": ["order_id"],
            "source_config": {"format": "csv", "path": "./data/customers.csv"},
        }
    ]
    assert "format" not in resolved.ingestion.config["sources"][0]
    assert "path" not in resolved.ingestion.config["sources"][0]


def test_resolve_ingestion_config_preserves_manifest_config() -> None:
    """Existing manifest-level ingestion config survives source resolution."""
    from floe_core.compilation.resolver import resolve_ingestion_config

    resolved = resolve_ingestion_config(_spec_with_ingestion(), _plugins_with_ingestion_config())

    assert resolved.ingestion is not None
    assert resolved.ingestion.config is not None
    assert resolved.ingestion.config["catalog_config"] == {
        "uri": "http://polaris:8181/api/catalog",
        "warehouse": "floe",
    }
    assert resolved.ingestion.config["retry_config"] == {
        "max_retries": 5,
        "initial_delay_seconds": 2.0,
    }


def test_resolve_ingestion_config_fails_without_ingestion_plugin() -> None:
    """Product ingestion requires a manifest-selected ingestion plugin."""
    from floe_core.compilation.errors import CompilationException
    from floe_core.compilation.resolver import resolve_ingestion_config

    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0", config={}),
        orchestrator=PluginRef(type="dagster", version="1.5.0", config={}),
    )

    with pytest.raises(CompilationException) as exc_info:
        resolve_ingestion_config(_spec_with_ingestion(), plugins)

    assert exc_info.value.error.code == "E201"
    assert exc_info.value.error.context == {"product": "orders-product"}


def test_compile_pipeline_merges_product_ingestion_sources(
    tmp_path: Path,
    patch_version_compat: Any,
    mock_compute_plugin: Any,
) -> None:
    """Stage 3 merges floe.yaml ingestion into compiled plugin artifacts."""
    _ = (patch_version_compat, mock_compute_plugin)

    from floe_core.compilation.stages import compile_pipeline

    spec_path = tmp_path / "floe.yaml"
    spec_path.write_text(
        """
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: orders-product
  version: 1.0.0
transforms:
  - name: orders
ingestion:
  sources:
    - name: orders_csv
      sourceType: filesystem
      format: csv
      path: data/orders.csv
      destinationTable: bronze.orders
      writeMode: append
"""
    )
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        """
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
  ingestion:
    type: dlt
    config:
      catalog_config:
        uri: http://polaris:8181/api/catalog
      retry_config:
        max_retries: 5
        initial_delay_seconds: 2.0
"""
    )

    artifacts = compile_pipeline(spec_path, manifest_path, emit_lineage=False)

    assert artifacts.plugins.ingestion is not None
    assert artifacts.plugins.ingestion.config is not None
    assert artifacts.plugins.ingestion.config["catalog_config"] == {
        "uri": "http://polaris:8181/api/catalog"
    }
    assert artifacts.plugins.ingestion.config["sources"] == [
        {
            "name": "orders_csv",
            "source_type": "filesystem",
            "destination_table": "bronze.orders",
            "write_mode": "append",
            "schema_contract": "evolve",
            "source_config": {"format": "csv", "path": "data/orders.csv"},
        }
    ]
    assert "format" not in artifacts.plugins.ingestion.config["sources"][0]
    assert "path" not in artifacts.plugins.ingestion.config["sources"][0]


def test_compile_pipeline_fails_when_product_ingestion_has_no_plugin(
    tmp_path: Path,
    patch_version_compat: Any,
    mock_compute_plugin: Any,
) -> None:
    """Compilation rejects product ingestion without manifest plugin selection."""
    _ = (patch_version_compat, mock_compute_plugin)

    from floe_core.compilation.errors import CompilationException
    from floe_core.compilation.stages import compile_pipeline

    spec_path = tmp_path / "floe.yaml"
    spec_path.write_text(
        """
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: orders-product
  version: 1.0.0
transforms:
  - name: orders
ingestion:
  sources:
    - name: orders_csv
      sourceType: filesystem
      format: csv
      path: data/orders.csv
      destinationTable: bronze.orders
"""
    )
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        """
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
"""
    )

    with pytest.raises(CompilationException) as exc_info:
        compile_pipeline(spec_path, manifest_path, emit_lineage=False)

    assert exc_info.value.error.code == "E201"


def test_no_ingestion_spec_returns_same_plugins() -> None:
    """Products without ingestion do not alter resolved plugin refs."""
    from floe_core.compilation.resolver import resolve_ingestion_config

    spec = FloeSpec(
        api_version="floe.dev/v1",
        kind="FloeSpec",
        metadata=FloeMetadata(name="orders-product", version="1.0.0"),
        transforms=[TransformSpec(name="orders")],
    )
    plugins = _plugins_with_ingestion_config()

    assert resolve_ingestion_config(spec, plugins) is plugins


def test_manifest_selected_dlt_receives_product_ingestion_sources() -> None:
    """resolve_plugins output can be enriched with product ingestion sources."""
    from floe_core.compilation.resolver import resolve_ingestion_config, resolve_plugins

    manifest = PlatformManifest(
        api_version="floe.dev/v1",
        kind="Manifest",
        metadata={"name": "test-platform", "version": "1.0.0", "owner": "test"},
        plugins={
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
            "ingestion": {
                "type": "dlt",
                "version": "0.1.0",
                "config": {"catalog_config": {"warehouse": "floe"}},
            },
        },
    )

    resolved = resolve_ingestion_config(_spec_with_ingestion(), resolve_plugins(manifest))

    assert resolved.ingestion is not None
    assert resolved.ingestion.config is not None
    assert resolved.ingestion.config["catalog_config"] == {"warehouse": "floe"}
    assert resolved.ingestion.config["sources"][0]["source_type"] == "filesystem"
