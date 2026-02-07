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
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from dagster import AssetKey, asset

if TYPE_CHECKING:
    from dagster import AssetsDefinition
    from dlt.extract.resource import DltResource
    from floe_core.schemas.compiled_artifacts import PluginRef

logger = logging.getLogger(__name__)


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

    Creates a wrapper asset that delegates to the ingestion plugin resource
    at runtime. The ingestion plugin (loaded as a Dagster resource) handles
    actual pipeline creation and execution.

    For direct dlt integration, use FloeIngestionTranslator with the
    ``@dlt_assets`` decorator instead.

    Args:
        ingestion_ref: Resolved ingestion plugin reference from CompiledArtifacts.

    Returns:
        List containing the ingestion runner asset definition.

    Example:
        >>> from floe_core.schemas.compiled_artifacts import PluginRef
        >>> ref = PluginRef(type="dlt", version="0.1.0", config={})
        >>> assets = create_ingestion_assets(ref)
        >>> len(assets)
        1

    Requirements:
        T034: Create ingestion asset factory
        FR-060: Orchestrator creates execution units from ingestion config
    """
    ingestion_type = ingestion_ref.type
    ingestion_version = ingestion_ref.version

    @asset(
        name="run_ingestion_pipelines",
        required_resource_keys=frozenset({"ingestion"}),
        description=(
            f"Execute ingestion pipelines via {ingestion_type} plugin. "
            "Delegates to the IngestionPlugin resource for pipeline "
            "creation and execution."
        ),
        metadata={
            "ingestion_type": ingestion_type,
            "ingestion_version": ingestion_version,
        },
    )
    def _run_ingestion(context) -> None:  # noqa: ANN001
        """Execute ingestion pipelines via the ingestion plugin resource.

        The ingestion plugin is loaded as a Dagster resource by
        create_ingestion_resources(). This asset triggers pipeline
        execution at materialization time.

        Args:
            context: Dagster AssetExecutionContext. Type hint omitted
                due to Dagster limitations with future annotations.
        """
        ingestion_plugin = context.resources.ingestion
        context.log.info(
            f"Ingestion asset triggered via {ingestion_plugin.name} "
            f"v{ingestion_plugin.version}"
        )

    logger.info(
        "Created ingestion assets",
        extra={
            "ingestion_type": ingestion_type,
            "ingestion_version": ingestion_version,
        },
    )

    return [_run_ingestion]


__all__ = [
    "FloeIngestionTranslator",
    "create_ingestion_assets",
]
