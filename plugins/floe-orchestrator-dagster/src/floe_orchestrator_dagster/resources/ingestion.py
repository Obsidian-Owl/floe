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

from dagster import ResourceDefinition

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

    def _ingestion_resource(_init_context: Any) -> Any:
        startup = getattr(ingestion_plugin, "startup", None)
        shutdown = getattr(ingestion_plugin, "shutdown", None)
        if callable(startup):
            startup()
        try:
            yield ingestion_plugin
        finally:
            if callable(shutdown):
                shutdown()

    logger.info(
        "Ingestion resources created",
        extra={
            "ingestion_type": ingestion_ref.type,
            "plugin_version": ingestion_plugin.version,
        },
    )

    return {"ingestion": ResourceDefinition(resource_fn=_ingestion_resource)}


def try_create_ingestion_resources(
    plugins: ResolvedPlugins | None,
) -> dict[str, Any]:
    """Create ingestion resources, returning empty dict when unconfigured.

    Returns empty dict when ingestion is not configured. Re-raises exceptions
    when ingestion IS configured but initialization fails (consistent with
    iceberg/semantic/lineage factory behavior).

    Args:
        plugins: Resolved plugin selections from CompiledArtifacts.
            May be None if no plugins are configured.

    Returns:
        Dictionary with "ingestion" key if successful, empty dict if unconfigured.

    Raises:
        Exception: If ingestion IS configured but initialization fails.

    Requirements:
        FR-063: Graceful degradation when ingestion is not configured
        AC-4: Re-raise on configured-but-broken (no exception swallowing)
    """
    if plugins is None:
        logger.warning("ingestion_not_configured")
        return {}

    if plugins.ingestion is None:
        logger.warning("ingestion_not_configured")
        return {}

    try:
        return create_ingestion_resources(
            ingestion_ref=plugins.ingestion,
        )
    except Exception:
        logger.exception("ingestion_creation_failed")
        raise


__all__ = [
    "create_ingestion_resources",
    "try_create_ingestion_resources",
]
