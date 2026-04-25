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
from typing import Any

from dagster import asset
from floe_core.telemetry.tracer_factory import get_tracer as _get_tracer

logger = logging.getLogger(__name__)

# Default paths (can be overridden via context config)
_DEFAULT_MANIFEST_PATH = Path("target/manifest.json")
_DEFAULT_OUTPUT_DIR = Path("cube/schema")


def _sync_semantic_schemas(
    context: Any,
    *,
    default_manifest_path: Path,
    default_output_dir: Path,
) -> list[str]:
    """Synchronize semantic layer schemas from dbt manifest.

    This asset runs after dbt models are materialized to generate or update
    semantic layer schema files (e.g., Cube YAML files) based on the dbt
    manifest. It uses the semantic_layer resource to delegate the sync
    operation to the plugin implementation.

    Args:
        context: AssetExecutionContext (Dagster asset execution context).
            Type hint omitted due to Dagster limitations with future annotations.
        default_manifest_path: Manifest path used when op_config does not override it.
        default_output_dir: Output directory used when op_config does not override it.

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
    op_config = context.op_config or {}
    manifest_path = Path(op_config.get("manifest_path", str(default_manifest_path)))
    output_dir = Path(op_config.get("output_dir", str(default_output_dir)))
    semantic_layer = context.resources.semantic_layer

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
        context.log.info(f"Syncing semantic schemas from {manifest_path} to {output_dir}")

        generated_files = semantic_layer.sync_from_dbt_manifest(
            manifest_path=manifest_path,
            output_dir=output_dir,
        )

        file_paths = [str(f) for f in generated_files]
        span.set_attribute("semantic.generated_file_count", len(file_paths))

        context.log.info(f"Semantic schema sync complete: {len(file_paths)} files generated")

        logger.info(
            "Semantic schema sync completed",
            extra={
                "manifest_path": str(manifest_path),
                "output_dir": str(output_dir),
                "file_count": len(file_paths),
            },
        )

        return file_paths


def create_sync_semantic_schemas_asset(
    *,
    manifest_path: Path,
    output_dir: Path,
) -> Any:
    """Create a semantic schema sync asset bound to product runtime paths.

    Args:
        manifest_path: dbt manifest path for the product project directory.
        output_dir: Semantic schema output directory for the product.

    Returns:
        Dagster asset definition that reads the semantic plugin from
        ``context.resources.semantic_layer``.
    """

    @asset(
        name="sync_semantic_schemas",
        description="Synchronize semantic layer schemas from dbt manifest",
        required_resource_keys={"semantic_layer"},
    )
    def _sync_semantic_schemas_asset(context) -> list[str]:  # noqa: ANN001
        return _sync_semantic_schemas(
            context,
            default_manifest_path=manifest_path,
            default_output_dir=output_dir,
        )

    return _sync_semantic_schemas_asset


sync_semantic_schemas = create_sync_semantic_schemas_asset(
    manifest_path=_DEFAULT_MANIFEST_PATH,
    output_dir=_DEFAULT_OUTPUT_DIR,
)


__all__ = ["create_sync_semantic_schemas_asset", "sync_semantic_schemas"]
