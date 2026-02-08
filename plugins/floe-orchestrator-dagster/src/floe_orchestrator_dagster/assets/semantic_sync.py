"""Semantic layer schema synchronization asset.

This module provides a Dagster asset that synchronizes semantic layer schemas
from the dbt manifest. It's designed to run after dbt models are materialized
to ensure the semantic layer (e.g., Cube) has up-to-date schema definitions.

The asset uses the semantic_layer resource (SemanticLayerPlugin) to delegate
the actual sync operation to the plugin implementation.

Example:
    >>> from dagster import Definitions
    >>> from floe_orchestrator_dagster.assets.semantic_sync import sync_semantic_schemas
    >>> from floe_orchestrator_dagster.resources import try_create_semantic_resources
    >>>
    >>> resources = try_create_semantic_resources(artifacts.plugins)
    >>> defs = Definitions(assets=[sync_semantic_schemas], resources=resources)

Requirements:
    T049: Create sync_semantic_schemas asset
    FR-004: Sync semantic schemas from dbt manifest
    FR-011: OTel tracing for observability

See Also:
    - specs/4e-semantic-layer/spec.md
    - packages/floe-core/src/floe_core/plugins/semantic.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from dagster import asset
from floe_core.telemetry.tracer_factory import get_tracer as _get_tracer

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default paths (can be overridden via context config)
_DEFAULT_MANIFEST_PATH = Path("target/manifest.json")
_DEFAULT_OUTPUT_DIR = Path("cube/schema")


@asset(
    name="sync_semantic_schemas",
    description="Synchronize semantic layer schemas from dbt manifest",
    required_resource_keys={"semantic_layer"},
)
def sync_semantic_schemas(context, semantic_layer) -> list[str]:  # noqa: ANN001
    """Synchronize semantic layer schemas from dbt manifest.

    This asset runs after dbt models are materialized to generate or update
    semantic layer schema files (e.g., Cube YAML files) based on the dbt
    manifest. It uses the semantic_layer resource to delegate the sync
    operation to the plugin implementation.

    Args:
        context: AssetExecutionContext (Dagster asset execution context).
            Type hint omitted due to Dagster limitations with future annotations.
        semantic_layer: SemanticLayerPlugin resource instance.
            Type hint omitted due to Dagster limitations with future annotations.

    Returns:
        List of generated schema file paths as strings.

    Raises:
        FileNotFoundError: If the dbt manifest doesn't exist.
        ValidationError: If the manifest is invalid.

    Requirements:
        T049: Create sync_semantic_schemas asset
        FR-004: Sync from dbt manifest
        FR-011: OTel tracing
    """
    # Extract config from context or use defaults
    manifest_path = Path(
        context.op_config.get("manifest_path", str(_DEFAULT_MANIFEST_PATH))
        if context.op_config
        else str(_DEFAULT_MANIFEST_PATH)
    )
    output_dir = Path(
        context.op_config.get("output_dir", str(_DEFAULT_OUTPUT_DIR))
        if context.op_config
        else str(_DEFAULT_OUTPUT_DIR)
    )

    # FR-011: OTel tracing via core tracer factory
    # Factory returns NoOpTracer gracefully if OTel is not configured
    tracer = _get_tracer("floe.orchestrator.semantic")
    with tracer.start_as_current_span(
        "floe.orchestrator.sync_semantic_schemas",
        attributes={
            "semantic.manifest_path": str(manifest_path),
            "semantic.output_dir": str(output_dir),
        },
    ) as span:
        context.log.info(
            f"Syncing semantic schemas from {manifest_path} to {output_dir}"
        )

        generated_files = semantic_layer.sync_from_dbt_manifest(
            manifest_path=manifest_path,
            output_dir=output_dir,
        )

        file_paths = [str(f) for f in generated_files]
        span.set_attribute("semantic.generated_file_count", len(file_paths))

        context.log.info(
            f"Semantic schema sync complete: {len(file_paths)} files generated"
        )

        logger.info(
            "Semantic schema sync completed",
            extra={
                "manifest_path": str(manifest_path),
                "output_dir": str(output_dir),
                "file_count": len(file_paths),
            },
        )

        return file_paths


__all__ = ["sync_semantic_schemas"]
