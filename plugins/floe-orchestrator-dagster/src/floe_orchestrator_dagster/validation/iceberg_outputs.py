"""Validate that configured Iceberg outputs exist for compiled artifacts."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import floe_core.plugin_registry as _plugin_registry_module
from floe_core.plugin_types import PluginType
from floe_core.schemas.compiled_artifacts import CompiledArtifacts


@dataclass
class IcebergOutputValidationResult:
    """Result of validating expected Iceberg table outputs."""

    expected_table_names: list[str]
    table_names: list[str]


def _product_namespace(artifacts: CompiledArtifacts) -> str:
    """Return the Iceberg namespace derived from compiled product metadata."""
    return artifacts.metadata.product_name.replace("-", "_")


def _qualify_table(namespace: str, table_name: str) -> str:
    """Qualify an unqualified table name with the product namespace."""
    if "." in table_name:
        return table_name
    return f"{namespace}.{table_name}"


def expected_iceberg_tables(
    artifacts: CompiledArtifacts,
    expected_tables: Sequence[str] | None = None,
) -> list[str]:
    """Return fully qualified Iceberg table identifiers expected for artifacts.

    Args:
        artifacts: Compiled artifact contract for the deployed product.
        expected_tables: Optional explicit table names. Unqualified names are
            resolved under the product namespace from compiled metadata. When
            omitted, all compiled transform model names are expected.

    Returns:
        Fully qualified Iceberg table identifiers.
    """
    namespace = _product_namespace(artifacts)
    if expected_tables is None:
        expected_tables = [model.name for model in artifacts.transforms.models]
    return [_qualify_table(namespace, table_name) for table_name in expected_tables]


def _connect_catalog_from_artifacts(artifacts: CompiledArtifacts) -> Any:
    """Connect to the configured catalog using catalog/storage plugin config."""
    plugins = artifacts.plugins
    if plugins is None or plugins.catalog is None:
        raise RuntimeError("CompiledArtifacts has no catalog plugin configured")
    if plugins.storage is None:
        raise RuntimeError("CompiledArtifacts has no storage plugin configured")

    registry = _plugin_registry_module.get_registry()
    catalog_ref = plugins.catalog
    storage_ref = plugins.storage

    validated_catalog_config = registry.configure(
        PluginType.CATALOG,
        catalog_ref.type,
        catalog_ref.config or {},
    )
    if validated_catalog_config is None:
        raise RuntimeError(f"Catalog plugin config for {catalog_ref.type} could not be validated")
    catalog_plugin = registry.get(PluginType.CATALOG, catalog_ref.type)

    validated_storage_config = registry.configure(
        PluginType.STORAGE,
        storage_ref.type,
        storage_ref.config or {},
    )
    if validated_storage_config is None:
        raise RuntimeError(f"Storage plugin config for {storage_ref.type} could not be validated")

    storage_config = storage_ref.config or {}
    storage_connection_config = {f"s3.{key}": value for key, value in storage_config.items()}
    return catalog_plugin.connect(config=storage_connection_config)


def validate_iceberg_outputs(
    artifacts: CompiledArtifacts,
    expected_tables: Sequence[str] | None = None,
) -> IcebergOutputValidationResult:
    """Validate that all expected Iceberg tables can be loaded.

    Args:
        artifacts: Compiled artifact contract for the deployed product.
        expected_tables: Optional explicit table names. Unqualified names are
            resolved under the product namespace from compiled metadata.

    Returns:
        Validation result with expected and confirmed table identifiers.

    Raises:
        RuntimeError: If catalog/storage config is absent, plugin validation
            fails, or any expected Iceberg table cannot be loaded.
    """
    expected_table_names = expected_iceberg_tables(artifacts, expected_tables)
    if not expected_table_names:
        raise RuntimeError("No expected Iceberg tables were derived from CompiledArtifacts")

    catalog = _connect_catalog_from_artifacts(artifacts)

    loaded_tables: list[str] = []
    load_errors: dict[str, str] = {}
    for table_name in expected_table_names:
        try:
            catalog.load_table(table_name)
        except Exception as exc:  # noqa: BLE001 - preserve per-table diagnostics.
            load_errors[table_name] = f"{type(exc).__name__}: {exc}"
        else:
            loaded_tables.append(table_name)

    if load_errors:
        details = "; ".join(f"{name} ({error})" for name, error in load_errors.items())
        raise RuntimeError(f"Expected Iceberg table(s) not found: {details}")

    return IcebergOutputValidationResult(
        expected_table_names=expected_table_names,
        table_names=loaded_tables,
    )


def validate_iceberg_outputs_from_file(
    artifacts_path: Path,
    expected_tables: Sequence[str] | None = None,
) -> IcebergOutputValidationResult:
    """Load CompiledArtifacts from disk and validate expected Iceberg tables."""
    artifacts = CompiledArtifacts.model_validate_json(artifacts_path.read_text())
    return validate_iceberg_outputs(
        artifacts=artifacts,
        expected_tables=expected_tables,
    )


def _parse_expected_tables(values: Sequence[str]) -> list[str] | None:
    """Parse repeated/comma-separated table CLI values."""
    tables: list[str] = []
    for value in values:
        tables.extend(table.strip() for table in value.split(",") if table.strip())
    return tables or None


def _main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for in-cluster validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts-path",
        type=Path,
        required=True,
        help="Path to compiled_artifacts.json in the deployed product environment.",
    )
    parser.add_argument(
        "--expected-table",
        action="append",
        default=[],
        help="Expected Iceberg table name. May be repeated or comma-separated.",
    )
    args = parser.parse_args(argv)

    result = validate_iceberg_outputs_from_file(
        artifacts_path=args.artifacts_path,
        expected_tables=_parse_expected_tables(args.expected_table),
    )
    print(
        json.dumps(
            {
                "expected_table_names": result.expected_table_names,
                "table_names": result.table_names,
                "tables_validated": len(result.table_names),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
