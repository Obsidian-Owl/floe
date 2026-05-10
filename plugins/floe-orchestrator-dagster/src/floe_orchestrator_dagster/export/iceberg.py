"""Iceberg export functionality."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import floe_core.plugin_registry as _plugin_registry_module
from floe_core.plugin_types import PluginType
from floe_core.plugins.catalog import CatalogPlugin
from floe_core.plugins.storage import StoragePlugin
from floe_core.schemas.compiled_artifacts import CompiledArtifacts
from floe_iceberg.models import IcebergTableManagerConfig
from floe_iceberg.writer import (
    DefaultIcebergTableWriter,
)

from floe_orchestrator_dagster.runtime_catalog_config import runtime_catalog_config

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass
class IcebergExportResult:
    """Result proving the Iceberg export wrote concrete table outputs."""

    tables_written: int
    table_names: list[str]


def _is_safe_identifier(name: str) -> bool:
    """Validate a SQL identifier against a safe pattern.

    Args:
        name: Identifier string to validate.

    Returns:
        True if the identifier is safe for use in SQL.
    """
    return bool(_SAFE_IDENTIFIER_RE.match(name))


def _duckdb_profile_path(raw_path: str, project_dir: Path, product_name: str) -> str:
    """Return a file-backed DuckDB path resolved from dbt profile config."""
    if raw_path == ":memory:":
        raise RuntimeError(
            "Configured Iceberg export requires a file-backed DuckDB profile path "
            f"for product {product_name}; got ':memory:'."
        )
    path = Path(raw_path)
    if path.is_absolute():
        return raw_path
    return str((project_dir / path).resolve())


def _resolve_duckdb_path_from_profiles(
    artifacts: CompiledArtifacts,
    product_name: str,
    project_dir: Path,
) -> str:
    """Resolve the DuckDB database path from compiled dbt profiles."""
    profiles = artifacts.dbt_profiles
    if not isinstance(profiles, dict) or not profiles:
        raise RuntimeError(
            "CompiledArtifacts.dbt_profiles is required to resolve the DuckDB output "
            f"path for configured Iceberg export of product {product_name}."
        )

    profile = profiles.get(product_name)
    if profile is None:
        metadata_product_name = getattr(getattr(artifacts, "metadata", None), "product_name", None)
        if isinstance(metadata_product_name, str):
            profile = profiles.get(metadata_product_name)
    if profile is None and len(profiles) == 1:
        profile = next(iter(profiles.values()))

    if not isinstance(profile, dict):
        raise RuntimeError(
            "CompiledArtifacts.dbt_profiles does not contain a profile object for "
            f"product {product_name}."
        )

    outputs = profile.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise RuntimeError(
            "CompiledArtifacts.dbt_profiles does not contain dbt outputs for "
            f"product {product_name}."
        )

    target = profile.get("target")
    if not isinstance(target, str) or not target:
        raise RuntimeError(
            "CompiledArtifacts.dbt_profiles must declare an active dbt target for "
            f"configured Iceberg export of product {product_name}."
        )

    if target not in outputs:
        raise RuntimeError(
            f"Active dbt target '{target}' was not found in compiled dbt outputs for "
            f"configured Iceberg export of product {product_name}."
        )

    output = outputs.get(target)
    if not isinstance(output, dict):
        raise RuntimeError(
            f"Active dbt target '{target}' is not a dbt output object for configured "
            f"Iceberg export of product {product_name}."
        )

    output_type = output.get("type")
    if output_type != "duckdb":
        raise RuntimeError(
            f"Configured Iceberg export requires active dbt target '{target}' for "
            f"product {product_name} to be DuckDB; got {output_type!r}."
        )

    raw_path = output.get("path")
    if isinstance(raw_path, str) and raw_path:
        return _duckdb_profile_path(raw_path, project_dir, product_name)

    raise RuntimeError(
        f"Active DuckDB dbt target '{target}' does not define a file-backed path for "
        f"configured Iceberg export of product {product_name}."
    )


def _runtime_catalog_connection_config(artifacts: CompiledArtifacts) -> dict[str, Any]:
    """Return PyIceberg connection config derived from compiled deployment bindings."""
    deployment = artifacts.deployment
    if deployment is None:
        return {}

    from floe_core.runtime_catalog_connection import build_runtime_catalog_connection
    from floe_iceberg.runtime_catalog import runtime_catalog_connection_to_pyiceberg_config

    connection = build_runtime_catalog_connection(
        storage=deployment.storage,
        catalog=deployment.catalog,
    )
    return runtime_catalog_connection_to_pyiceberg_config(connection)


def export_dbt_to_iceberg(
    context: Any,
    product_name: str,
    project_dir: Path,
    artifacts: CompiledArtifacts,
) -> IcebergExportResult:
    """Export dbt model outputs from DuckDB to Iceberg tables.

    Args:
        context: Dagster context for logging.
        product_name: Product name (e.g., "customer-360").
        project_dir: Path to the dbt project directory.
        artifacts: Parsed CompiledArtifacts object (not read from disk).
    """
    if artifacts.plugins is None or artifacts.plugins.catalog is None:
        context.log.info("No catalog plugin configured — skipping Iceberg export")
        return IcebergExportResult(tables_written=0, table_names=[])

    if artifacts.plugins.storage is None:
        context.log.info("No storage plugin configured — skipping Iceberg export")
        return IcebergExportResult(tables_written=0, table_names=[])

    safe_name = product_name.replace("-", "_")
    duckdb_path = _resolve_duckdb_path_from_profiles(
        artifacts=artifacts,
        product_name=product_name,
        project_dir=project_dir,
    )

    catalog_config = runtime_catalog_config(
        artifacts.plugins.catalog.type,
        artifacts.plugins.catalog.config,
    )
    storage_config = artifacts.plugins.storage.config

    registry = _plugin_registry_module.get_registry()
    catalog_type = artifacts.plugins.catalog.type
    storage_type = artifacts.plugins.storage.type
    # configure() validates config and applies it to the cached plugin instance.
    # get() then returns that configured instance for the runtime connection.
    validated_config = registry.configure(PluginType.CATALOG, catalog_type, catalog_config)
    if validated_config is None:
        raise RuntimeError(f"Catalog plugin config for {catalog_type} could not be validated")
    catalog_plugin = cast(CatalogPlugin, registry.get(PluginType.CATALOG, catalog_type))

    # Force storage plugin loading/configuration on the export path so invalid
    # storage config cannot reuse stale cached plugin state.
    registry.get(PluginType.STORAGE, storage_type)
    validated_storage_config = registry.configure(
        PluginType.STORAGE,
        storage_type,
        storage_config or {},
    )
    if validated_storage_config is None:
        raise RuntimeError(f"Storage plugin config for {storage_type} could not be validated")
    storage_plugin = cast(StoragePlugin, registry.get(PluginType.STORAGE, storage_type))

    if not Path(duckdb_path).exists():
        raise RuntimeError(
            f"DuckDB output file is missing for configured Iceberg export: {duckdb_path}"
        )

    import duckdb

    catalog_connection_config = _runtime_catalog_connection_config(artifacts)
    iceberg_config = IcebergTableManagerConfig.from_governance(artifacts.governance)
    writer = DefaultIcebergTableWriter(
        catalog_plugin=catalog_plugin,
        storage_plugin=storage_plugin,
        catalog_connection_config=catalog_connection_config,
        config=iceberg_config,
    )

    product_namespace = safe_name

    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        namespace_ensured = False
        table_names: list[str] = []
        tables_df = conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema NOT IN ('information_schema', 'pg_catalog')"
        ).fetchall()

        for schema_name, table_name in tables_df:
            if not _is_safe_identifier(schema_name) or not _is_safe_identifier(table_name):
                context.log.warning(
                    "Skipping unsafe identifier: %s.%s",
                    schema_name,
                    table_name,
                )
                continue
            if schema_name != "main":
                qualified = f'"{schema_name}"."{table_name}"'
            else:
                qualified = f'"{table_name}"'
            query = f"SELECT * FROM {qualified}"  # nosec B608
            arrow_table = conn.execute(query).fetch_arrow_table()
            if arrow_table.num_rows == 0:
                continue

            iceberg_id = f"{product_namespace}.{table_name}"
            if not namespace_ensured:
                writer.ensure_namespace(product_namespace)
                namespace_ensured = True
            writer.write_table(iceberg_id, arrow_table, mode="overwrite")
            table_names.append(iceberg_id)
            context.log.info(
                "Exported %s to Iceberg (%d rows)",
                iceberg_id,
                arrow_table.num_rows,
            )

        if not table_names:
            raise RuntimeError(
                f"Configured Iceberg export wrote no tables for product {product_name}"
            )
        return IcebergExportResult(
            tables_written=len(table_names),
            table_names=table_names,
        )
    finally:
        conn.close()
