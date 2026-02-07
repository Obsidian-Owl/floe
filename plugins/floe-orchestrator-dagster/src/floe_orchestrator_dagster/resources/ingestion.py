"""Ingestion resource factory for Dagster Definitions.

This module provides factory functions to create ingestion-related Dagster
resources from CompiledArtifacts plugin configuration. It follows the same
pattern as semantic.py and iceberg.py.

Example:
    >>> from floe_orchestrator_dagster.resources import create_ingestion_resources
    >>> resources = create_ingestion_resources(
    ...     ingestion_ref=PluginRef(type="dlt", version="0.1.0", config={...}),
    ... )
    >>> # resources == {"ingestion": DltIngestionPlugin(...)}

Requirements:
    T033: Create ingestion resource factory (FR-059, FR-062)
    FR-063: Graceful degradation when ingestion is not configured

See Also:
    - specs/4f-ingestion-plugin/spec.md
    - packages/floe-core/src/floe_core/plugins/ingestion.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

logger = logging.getLogger(__name__)


def create_ingestion_resources(
    ingestion_ref: PluginRef,
) -> dict[str, Any]:
    """Create Dagster resources dict with IngestionPlugin.

    Loads IngestionPlugin from the PluginRegistry using the resolved
    plugin reference from CompiledArtifacts. Returns the plugin instance
    wrapped in a resources dictionary.

    Args:
        ingestion_ref: Resolved ingestion plugin reference (type, version, config).

    Returns:
        Dictionary with "ingestion" key mapped to IngestionPlugin instance.

    Raises:
        PluginNotFoundError: If ingestion plugin is not installed.
        PluginConfigurationError: If plugin configuration is invalid.

    Example:
        >>> from floe_core.schemas.compiled_artifacts import PluginRef
        >>> resources = create_ingestion_resources(
        ...     ingestion_ref=PluginRef(type="dlt", version="0.1.0", config={...}),
        ... )
        >>> definitions = Definitions(assets=assets, resources=resources)

    Requirements:
        T033: Create ingestion resource factory (FR-059)
    """
    from floe_core.plugin_registry import get_registry
    from floe_core.plugin_types import PluginType

    registry = get_registry()

    # Load IngestionPlugin via registry
    logger.info(
        "Loading ingestion plugin",
        extra={"ingestion_type": ingestion_ref.type},
    )
    ingestion_plugin = registry.get(PluginType.INGESTION, ingestion_ref.type)

    # Configure ingestion plugin if config provided
    if ingestion_ref.config:
        registry.configure(PluginType.INGESTION, ingestion_ref.type, ingestion_ref.config)

    logger.info(
        "Ingestion resources created",
        extra={
            "ingestion_type": ingestion_ref.type,
            "plugin_version": ingestion_plugin.version,
        },
    )

    return {"ingestion": ingestion_plugin}


def try_create_ingestion_resources(
    plugins: ResolvedPlugins | None,
) -> dict[str, Any]:
    """Attempt to create ingestion resources, returning empty dict on failure.

    This is the safe entry point called by create_definitions(). It handles
    the case where the ingestion plugin is not configured (it's optional
    in CompiledArtifacts) and catches plugin loading errors gracefully.

    Args:
        plugins: Resolved plugin selections from CompiledArtifacts.
            May be None if no plugins are configured.

    Returns:
        Dictionary with "ingestion" key if successful, empty dict otherwise.

    Example:
        >>> resources = try_create_ingestion_resources(artifacts.plugins)
        >>> # Returns {} if ingestion not configured
        >>> # Returns {"ingestion": DltIngestionPlugin} if available

    Requirements:
        FR-063: Graceful degradation when ingestion is not configured
    """
    if plugins is None:
        logger.debug("No plugins configured, skipping ingestion resource creation")
        return {}

    if plugins.ingestion is None:
        logger.debug("No ingestion plugin configured, skipping resource creation")
        return {}

    try:
        return create_ingestion_resources(
            ingestion_ref=plugins.ingestion,
        )
    except Exception:
        logger.exception(
            "Failed to create ingestion resources — ingestion pipelines will not be available"
        )
        raise


__all__ = [
    "create_ingestion_resources",
    "try_create_ingestion_resources",
]
