"""Iceberg export functionality."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from inspect import getattr_static
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

import floe_core.plugin_registry as _plugin_registry_module
from floe_core.plugin_types import PluginType
from floe_core.plugins.catalog import CatalogPlugin
from floe_core.plugins.storage import StoragePlugin
from floe_core.schemas.compiled_artifacts import CompiledArtifacts
from floe_iceberg.errors import (
    is_stale_table_metadata_error,
    stale_table_metadata_error_from_exception,
)
from floe_iceberg.models import IcebergTableManagerConfig, StaleTableRecoveryMode

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@runtime_checkable
class WriteCapableIcebergCatalog(Protocol):
    """Iceberg catalog operations required by configured dbt export."""

    def create_namespace(self, namespace: str) -> None:
        """Create an Iceberg namespace."""
        ...

    def load_table(self, identifier: str) -> Any:
        """Load an Iceberg table."""
        ...

    def create_table(self, identifier: str, schema: Any) -> Any:
        """Create an Iceberg table."""
        ...


class EndpointPreservingTableLoader(Protocol):
    """Optional catalog plugin hook for endpoint-preserving table loads."""

    def load_table_with_client_endpoint(self, identifier: str) -> Any:
        """Load an Iceberg table while preserving client-side storage endpoint config."""
        ...


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


def _require_write_capable_catalog(
    catalog: object,
    catalog_type: str,
) -> WriteCapableIcebergCatalog:
    """Return catalog when it supports write operations required for export."""
    required_methods: Sequence[str] = ("create_namespace", "load_table", "create_table")
    missing_methods = [
        method for method in required_methods if not callable(getattr(catalog, method, None))
    ]
    if missing_methods:
        missing = ", ".join(missing_methods)
        raise RuntimeError(
            f"Catalog plugin {catalog_type} did not return a write-capable Iceberg catalog; "
            f"missing method(s): {missing}"
        )
    return cast(WriteCapableIcebergCatalog, catalog)


def _load_table_for_overwrite(
    catalog_plugin: object,
    catalog: WriteCapableIcebergCatalog,
    identifier: str,
) -> Any:
    """Load a table for overwrite using endpoint-preserving plugin hook when available."""
    method_marker = getattr_static(
        catalog_plugin,
        "load_table_with_client_endpoint",
        None,
    )
    method = getattr(catalog_plugin, "load_table_with_client_endpoint", None)
    if method_marker is not None and callable(method):
        endpoint_preserving_loader = cast(EndpointPreservingTableLoader, catalog_plugin)
        return endpoint_preserving_loader.load_table_with_client_endpoint(identifier)
    return catalog.load_table(identifier)


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
    from pyiceberg.exceptions import NoSuchTableError

    catalog_connection_config = storage_plugin.get_pyiceberg_catalog_config()
    iceberg_config = IcebergTableManagerConfig.from_governance(artifacts.governance)
    catalog = _require_write_capable_catalog(
        catalog_plugin.connect(config=catalog_connection_config),
        catalog_type,
    )

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
            try:
                iceberg_table = _load_table_for_overwrite(
                    catalog_plugin,
                    catalog,
                    iceberg_id,
                )
                iceberg_table.overwrite(arrow_table)
            except NoSuchTableError:
                iceberg_table = catalog.create_table(
                    iceberg_id,
                    schema=arrow_table.schema,
                )
                iceberg_table.append(arrow_table)
            except Exception as exc:
                if not is_stale_table_metadata_error(exc):
                    raise

                stale_error = stale_table_metadata_error_from_exception(
                    table_identifier=iceberg_id,
                    recovery_mode=iceberg_config.stale_table_recovery_mode,
                    original_error=exc,
                )
                if iceberg_config.stale_table_recovery_mode is StaleTableRecoveryMode.STRICT:
                    raise stale_error from exc

                context.log.warning(
                    "Repairing stale Iceberg table registration for %s: %s",
                    iceberg_id,
                    stale_error.metadata_location or "unknown metadata location",
                )
                catalog_plugin.drop_table(iceberg_id, purge=False)
                catalog = _require_write_capable_catalog(
                    catalog_plugin.connect(config=catalog_connection_config),
                    catalog_type,
                )
                iceberg_table = catalog.create_table(
                    iceberg_id,
                    schema=arrow_table.schema,
                )
                iceberg_table.append(arrow_table)
            table_names.append(iceberg_id)
            context.log.info(
                "Exported %s to Iceberg (%d rows)",
                table_name,
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
