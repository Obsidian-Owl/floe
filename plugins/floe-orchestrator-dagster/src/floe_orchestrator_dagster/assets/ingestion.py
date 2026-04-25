"""Ingestion asset definitions for Dagster orchestrator (T034).

This module provides FloeIngestionTranslator and create_ingestion_assets()
for mapping dlt ingestion pipelines to Dagster assets with floe naming
conventions.

Requirements:
    T034: Create ingestion asset factory
    FR-061: Asset naming convention ingestion__{source}__{resource}
    FR-064: Asset metadata includes source_type and destination_table

See Also:
    - specs/4f-ingestion-plugin/spec.md
    - packages/floe-core/src/floe_core/plugins/ingestion.py
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from dagster import AssetKey, asset
from floe_core.plugins.ingestion import IngestionConfig

if TYPE_CHECKING:
    from dagster import AssetsDefinition
    from dlt.extract.resource import DltResource
    from floe_core.schemas.compiled_artifacts import PluginRef

logger = logging.getLogger(__name__)
_UNSAFE_ASSET_NAME_CHARS = re.compile(r"[^a-zA-Z0-9_]")


class FloeIngestionTranslator:
    """Custom DagsterDltTranslator for floe ingestion naming conventions.

    Maps dlt resources to Dagster asset keys using the pattern::

        ingestion__{source_name}__{resource_name}

    Optionally enriches asset metadata with ``source_type`` and
    ``destination_table`` attributes.

    Args:
        source_type: Type of the ingestion source (e.g., "rest_api", "sql_database").
        destination_table: Iceberg destination table path.

    Example:
        >>> from dagster_dlt import dlt_assets
        >>> translator = FloeIngestionTranslator(
        ...     source_type="rest_api",
        ...     destination_table="raw.github_issues",
        ... )
        >>> # Use with @dlt_assets(dagster_dlt_translator=translator)

    Requirements:
        FR-061: Asset naming convention ingestion__{source}__{resource}
        FR-064: Asset metadata includes source_type and destination_table
    """

    def __init__(
        self,
        source_type: str = "",
        destination_table: str = "",
    ) -> None:
        from dagster_dlt import DagsterDltTranslator

        # Validate that we're compatible with DagsterDltTranslator
        self._base_translator = DagsterDltTranslator()
        self._source_type = source_type
        self._destination_table = destination_table

    def get_asset_key(self, resource: DltResource) -> AssetKey:
        """Generate asset key following floe naming convention.

        Produces keys in the pattern ``ingestion__{source}__{resource}``
        using the dlt resource's source_name and name properties.

        Args:
            resource: dlt resource to generate key for.

        Returns:
            AssetKey with floe ingestion naming convention.

        Requirements:
            FR-061: Asset naming convention ingestion__{source}__{resource}
        """
        return AssetKey(f"ingestion__{resource.source_name}__{resource.name}")

    def get_metadata(self, resource: DltResource) -> Mapping[str, Any]:
        """Generate metadata including source_type and destination_table.

        Args:
            resource: dlt resource to generate metadata for.

        Returns:
            Metadata mapping with source_type and destination_table if set.

        Requirements:
            FR-064: Asset metadata includes source_type and destination_table
        """
        metadata: dict[str, Any] = {}
        if self._source_type:
            metadata["source_type"] = self._source_type
        if self._destination_table:
            metadata["destination_table"] = self._destination_table
        return metadata


def create_ingestion_assets(
    ingestion_ref: PluginRef,
) -> list[AssetsDefinition]:
    """Create Dagster asset definitions for ingestion pipelines.

    Creates helper assets only when source configuration already contains
    explicit executable dlt source objects. Normal compiled JSON ingestion
    configuration is not executable yet and fails loudly.

    For direct dlt integration, use FloeIngestionTranslator with the
    ``@dlt_assets`` decorator instead.

    Args:
        ingestion_ref: Resolved ingestion plugin reference from CompiledArtifacts.

    Returns:
        List containing ingestion runner asset definitions.

    Example:
        >>> from floe_core.schemas.compiled_artifacts import PluginRef
        >>> source = build_dlt_source_somewhere_else()
        >>> ref = PluginRef(
        ...     type="dlt",
        ...     version="0.1.0",
        ...     config={
        ...         "sources": [{
        ...             "name": "github_events",
        ...             "source_type": "rest_api",
        ...             "source_config": {"source": source},
        ...             "destination_table": "bronze.github_events",
        ...         }]
        ...     },
        ... )
        >>> assets = create_ingestion_assets(ref)
        >>> len(assets)
        1

    Requirements:
        T034: Create ingestion asset factory
        FR-060: Orchestrator creates execution units from ingestion config
    """
    ingestion_type = ingestion_ref.type
    ingestion_version = ingestion_ref.version
    ingestion_config = ingestion_ref.config or {}
    source_configs = _source_configs(ingestion_config)
    assets: list[AssetsDefinition] = []
    asset_names: set[str] = set()

    for source_config in source_configs:
        asset_name = f"run_ingestion_{_safe_source_name(str(source_config['name']))}"
        if asset_name in asset_names:
            raise ValueError(f"normalized ingestion asset name collision: {asset_name}")
        asset_names.add(asset_name)
        _validate_executable_source(source_config)
        assets.append(
            _create_ingestion_asset(
                ingestion_type=ingestion_type,
                ingestion_version=ingestion_version,
                asset_name=asset_name,
                source_config=source_config,
            )
        )

    logger.info(
        "Created ingestion assets",
        extra={
            "ingestion_type": ingestion_type,
            "ingestion_version": ingestion_version,
        },
    )

    return assets


def _source_configs(ingestion_config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract source configs from real sources[] or legacy flat config."""
    if not ingestion_config:
        raise ValueError(
            "Dagster ingestion helper requires sources or explicit executable source config"
        )
    sources = ingestion_config.get("sources")
    if sources is None:
        return [{"name": ingestion_config.get("name", "pipelines"), **dict(ingestion_config)}]
    if not sources:
        raise ValueError("Dagster ingestion helper requires at least one ingestion source")
    return [dict(source) for source in sources]


def _validate_executable_source(source_config: Mapping[str, Any]) -> None:
    """Require an explicit non-JSON dlt source object before creating assets."""
    source_ref = (source_config.get("source_config") or {}).get("source")
    if source_ref is None or isinstance(
        source_ref,
        str | bytes | int | float | bool | dict | list | tuple | set,
    ):
        source_name = source_config.get("name", "<unnamed>")
        raise ValueError(
            "Dagster ingestion helper requires source_config.source to contain an "
            f"executable dlt source object for source {source_name!r}; normal compiled "
            "JSON config cannot construct runnable ingestion assets yet."
        )


def _safe_source_name(source_name: str) -> str:
    """Return a Dagster-safe deterministic source name."""
    safe_name = _UNSAFE_ASSET_NAME_CHARS.sub("_", source_name).strip("_")
    if not safe_name:
        return "source"
    if safe_name[0].isdigit():
        return f"source_{safe_name}"
    return safe_name


def _table_name(destination_table: str) -> str:
    """Extract the physical table name from a namespace-qualified table."""
    return destination_table.rsplit(".", 1)[-1]


def _create_ingestion_asset(
    *,
    ingestion_type: str,
    ingestion_version: str,
    asset_name: str,
    source_config: dict[str, Any],
) -> AssetsDefinition:
    source_name = str(source_config["name"])

    @asset(
        name=asset_name,
        required_resource_keys=frozenset({"ingestion"}),
        description=(
            f"Execute ingestion source {source_name} via {ingestion_type} plugin. "
            "Delegates to the IngestionPlugin resource for pipeline creation and execution."
        ),
        metadata={
            "ingestion_type": ingestion_type,
            "ingestion_version": ingestion_version,
            "source_name": source_name,
            "source_type": source_config.get("source_type", ""),
            "destination_table": source_config.get("destination_table", ""),
        },
    )
    def _run_ingestion_source(context) -> Any:  # noqa: ANN001
        """Execute one configured ingestion source via the ingestion plugin resource."""
        ingestion_plugin = context.resources.ingestion
        context.log.info(
            f"Ingestion asset {asset_name} triggered via "
            f"{ingestion_plugin.name} v{ingestion_plugin.version}"
        )
        config = IngestionConfig(
            source_type=source_config["source_type"],
            source_config=source_config.get("source_config") or {},
            destination_table=source_config["destination_table"],
            write_mode=source_config.get("write_mode", "append"),
            schema_contract=source_config.get("schema_contract", "evolve"),
        )
        pipeline = ingestion_plugin.create_pipeline(config)
        run_kwargs = {
            "write_disposition": config.write_mode,
            "table_name": _table_name(config.destination_table),
            "schema_contract": config.schema_contract,
            "cursor_field": source_config.get("cursor_field"),
            "primary_key": source_config.get("primary_key"),
        }
        source = config.source_config.get("source")
        if source is not None:
            run_kwargs["source"] = source

        result = ingestion_plugin.run(pipeline, **run_kwargs)

        if not result.success:
            errors = ", ".join(str(error) for error in getattr(result, "errors", []))
            raise RuntimeError(f"Ingestion pipeline failed: {errors or 'unknown error'}")

        return result

    return _run_ingestion_source


__all__ = [
    "FloeIngestionTranslator",
    "create_ingestion_assets",
]
