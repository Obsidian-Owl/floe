"""Iceberg export functionality."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import floe_core.plugin_registry as _plugin_registry_module
from floe_core.plugin_types import PluginType
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _is_safe_identifier(name: str) -> bool:
    """Validate a SQL identifier against a safe pattern.

    Args:
        name: Identifier string to validate.

    Returns:
        True if the identifier is safe for use in SQL.
    """
    return bool(_SAFE_IDENTIFIER_RE.match(name))


def export_dbt_to_iceberg(
    context: Any,
    product_name: str,
    project_dir: Path,
    artifacts: CompiledArtifacts,
) -> None:
    """Export dbt model outputs from DuckDB to Iceberg tables.

    Args:
        context: Dagster context for logging.
        product_name: Product name (e.g., "customer-360").
        project_dir: Path to the dbt project directory.
        artifacts: Parsed CompiledArtifacts object (not read from disk).
    """
    if artifacts.plugins is None or artifacts.plugins.catalog is None:
        context.log.info("No catalog plugin configured — skipping Iceberg export")
        return

    if artifacts.plugins.storage is None:
        context.log.info("No storage plugin configured — skipping Iceberg export")
        return

    safe_name = product_name.replace("-", "_")
    duckdb_path = f"/tmp/{safe_name}.duckdb"

    catalog_config = artifacts.plugins.catalog.config
    storage_config = artifacts.plugins.storage.config

    registry = _plugin_registry_module.get_registry()
    catalog_type = artifacts.plugins.catalog.type
    storage_type = artifacts.plugins.storage.type
    # configure() validates config and applies it to the cached plugin instance.
    # get() then returns that configured instance for the runtime connection.
    validated_config = registry.configure(PluginType.CATALOG, catalog_type, catalog_config or {})
    if validated_config is None:
        raise RuntimeError(f"Catalog plugin config for {catalog_type} could not be validated")
    catalog_plugin = registry.get(PluginType.CATALOG, catalog_type)

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

    if not Path(duckdb_path).exists():
        raise RuntimeError(f"Configured Iceberg export DuckDB file not found: {duckdb_path}")

    import duckdb
    from pyiceberg.exceptions import NoSuchTableError

    s3_config = {f"s3.{k}": v for k, v in (storage_config or {}).items()}
    catalog = catalog_plugin.connect(config=s3_config)

    product_namespace = safe_name

    try:
        catalog.create_namespace(product_namespace)
        context.log.info("Created Iceberg namespace: %s", product_namespace)
    except Exception as exc:
        exc_name = type(exc).__name__
        if "AlreadyExists" in exc_name or "already exists" in str(exc).lower():
            context.log.debug("Namespace %s already exists", product_namespace)
        else:
            raise

    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
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
            try:
                iceberg_table = catalog.load_table(iceberg_id)
                iceberg_table.overwrite(arrow_table)
            except NoSuchTableError:
                iceberg_table = catalog.create_table(
                    iceberg_id,
                    schema=arrow_table.schema,
                )
                iceberg_table.append(arrow_table)
            context.log.info(
                "Exported %s to Iceberg (%d rows)",
                table_name,
                arrow_table.num_rows,
            )
    finally:
        conn.close()
