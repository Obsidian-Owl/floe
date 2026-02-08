"""Semantic layer resource factory for Dagster Definitions.

This module provides a factory function to create semantic layer-related Dagster resources
from CompiledArtifacts plugin configuration. It bridges the gap between the plugin registry
(discovery/loading) and Dagster's resource system.

The factory function handles:
- Loading SemanticLayerPlugin from the PluginRegistry
- Configuring the plugin with its resolved config from CompiledArtifacts
- Creating a Dagster resource dict for use in assets

Example:
    >>> from floe_orchestrator_dagster.resources import create_semantic_resources
    >>> resources = create_semantic_resources(
    ...     semantic_ref=PluginRef(type="cube", version="0.1.0", config={...}),
    ... )
    >>> # resources == {"semantic_layer": CubeSemanticPlugin(...)}

Requirements:
    T047: Create semantic resource factory
    T049: Enable sync_semantic_schemas asset to use semantic_layer resource

See Also:
    - specs/4e-semantic-layer/spec.md
    - packages/floe-core/src/floe_core/plugins/semantic.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

logger = logging.getLogger(__name__)


def create_semantic_resources(
    semantic_ref: PluginRef,
) -> dict[str, Any]:
    """Create Dagster resources dict with SemanticLayerPlugin.

    Loads SemanticLayerPlugin from the PluginRegistry using the resolved
    plugin reference from CompiledArtifacts. Returns the plugin instance
    wrapped in a resources dictionary.

    Args:
        semantic_ref: Resolved semantic layer plugin reference (type, version, config).

    Returns:
        Dictionary with "semantic_layer" key mapped to SemanticLayerPlugin instance.

    Raises:
        PluginNotFoundError: If semantic layer plugin is not installed.
        PluginConfigurationError: If plugin configuration is invalid.

    Example:
        >>> from floe_core.schemas.compiled_artifacts import PluginRef
        >>> resources = create_semantic_resources(
        ...     semantic_ref=PluginRef(type="cube", version="0.1.0", config={...}),
        ... )
        >>> definitions = Definitions(assets=assets, resources=resources)

    Requirements:
        T047: Create semantic resource factory
    """
    from floe_core.plugin_registry import get_registry
    from floe_core.plugin_types import PluginType

    registry = get_registry()

    # Load SemanticLayerPlugin via registry
    logger.info(
        "Loading semantic layer plugin",
        extra={"semantic_type": semantic_ref.type},
    )
    semantic_plugin = registry.get(PluginType.SEMANTIC_LAYER, semantic_ref.type)

    # Configure semantic plugin if config provided
    if semantic_ref.config:
        registry.configure(
            PluginType.SEMANTIC_LAYER, semantic_ref.type, semantic_ref.config
        )

    logger.info(
        "Semantic layer resources created",
        extra={
            "semantic_type": semantic_ref.type,
            "plugin_version": semantic_plugin.version,
        },
    )

    return {"semantic_layer": semantic_plugin}


def try_create_semantic_resources(
    plugins: ResolvedPlugins | None,
) -> dict[str, Any]:
    """Attempt to create semantic layer resources, returning empty dict on failure.

    This is the safe entry point called by create_definitions(). It handles
    the case where the semantic layer plugin is not configured (it's optional
    in CompiledArtifacts) and catches plugin loading errors gracefully.

    Args:
        plugins: Resolved plugin selections from CompiledArtifacts.
            May be None if no plugins are configured.

    Returns:
        Dictionary with "semantic_layer" key if successful, empty dict otherwise.

    Example:
        >>> resources = try_create_semantic_resources(artifacts.plugins)
        >>> # Returns {} if semantic not configured
        >>> # Returns {"semantic_layer": CubeSemanticPlugin} if available
    """
    if plugins is None:
        logger.debug("No plugins configured, skipping semantic layer resource creation")
        return {}

    if plugins.semantic is None:
        logger.debug("No semantic layer plugin configured, skipping resource creation")
        return {}

    try:
        return create_semantic_resources(
            semantic_ref=plugins.semantic,
        )
    except Exception:
        logger.exception(
            "Failed to create semantic layer resources"
            " — this will prevent semantic layer sync from working"
        )
        raise


__all__ = [
    "create_semantic_resources",
    "try_create_semantic_resources",
]
