"""Iceberg resource factory for Dagster Definitions.

This module provides a factory function to create Iceberg-related Dagster resources
(IcebergIOManager) from CompiledArtifacts plugin configuration. It bridges the gap
between the plugin registry (discovery/loading) and Dagster's resource system.

The factory function handles:
- Loading CatalogPlugin and StoragePlugin from the PluginRegistry
- Configuring plugins with their resolved config from CompiledArtifacts
- Instantiating IcebergTableManager with the loaded plugins
- Creating IcebergIOManager wrapped in a Dagster resource dict

Example:
    >>> from floe_orchestrator_dagster.resources import create_iceberg_resources
    >>> resources = create_iceberg_resources(
    ...     catalog_ref=PluginRef(type="polaris", version="0.1.0", config={...}),
    ...     storage_ref=PluginRef(type="s3", version="1.0.0", config={...}),
    ... )
    >>> # resources == {"iceberg": IcebergIOManager(...)}

Requirements:
    T108: Extract catalog/storage config from CompiledArtifacts
    T109: Use PluginRegistry to load CatalogPlugin and StoragePlugin
    T110: Instantiate IcebergTableManager
    T111: Wire IcebergIOManager into Dagster Definitions resources
    T112: Create reusable create_iceberg_resources() factory function

See Also:
    - specs/4d-storage-plugin/contracts/iceberg_io_manager_api.md
    - packages/floe-iceberg/src/floe_iceberg/manager.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

logger = logging.getLogger(__name__)

# Default namespace for Iceberg tables when not configured
_DEFAULT_NAMESPACE = "default"


def create_iceberg_resources(
    catalog_ref: PluginRef,
    storage_ref: PluginRef,
    default_namespace: str = _DEFAULT_NAMESPACE,
) -> dict[str, Any]:
    """Create Dagster resources dict with IcebergIOManager.

    Loads CatalogPlugin and StoragePlugin from the PluginRegistry using
    the resolved plugin references from CompiledArtifacts. Instantiates
    IcebergTableManager and wraps it in an IcebergIOManager.

    Args:
        catalog_ref: Resolved catalog plugin reference (type, version, config).
        storage_ref: Resolved storage plugin reference (type, version, config).
        default_namespace: Default Iceberg namespace for tables.

    Returns:
        Dictionary with "iceberg" key mapped to IcebergIOManager instance.

    Raises:
        PluginNotFoundError: If catalog or storage plugin is not installed.
        PluginConfigurationError: If plugin configuration is invalid.
        ConnectionError: If unable to connect to catalog.

    Example:
        >>> from floe_core.schemas.compiled_artifacts import PluginRef
        >>> resources = create_iceberg_resources(
        ...     catalog_ref=PluginRef(type="polaris", version="0.1.0", config={...}),
        ...     storage_ref=PluginRef(type="s3", version="1.0.0", config={...}),
        ... )
        >>> definitions = Definitions(assets=assets, resources=resources)

    Requirements:
        T109: Load plugins via PluginRegistry
        T110: Instantiate IcebergTableManager
        T111: Create IcebergIOManager resource
        T112: Reusable factory function
    """
    from floe_core.plugin_registry import get_registry
    from floe_core.plugin_types import PluginType
    from floe_iceberg import IcebergTableManager
    from floe_orchestrator_dagster.io_manager import create_iceberg_io_manager

    registry = get_registry()

    # T109: Load CatalogPlugin via registry
    logger.info(
        "Loading catalog plugin",
        extra={"catalog_type": catalog_ref.type},
    )
    catalog_plugin = registry.get(PluginType.CATALOG, catalog_ref.type)

    # Configure catalog plugin if config provided
    if catalog_ref.config:
        registry.configure(PluginType.CATALOG, catalog_ref.type, catalog_ref.config)

    # T109: Load StoragePlugin via registry
    logger.info(
        "Loading storage plugin",
        extra={"storage_type": storage_ref.type},
    )
    storage_plugin = registry.get(PluginType.STORAGE, storage_ref.type)

    # Configure storage plugin if config provided
    if storage_ref.config:
        registry.configure(PluginType.STORAGE, storage_ref.type, storage_ref.config)

    # T110: Instantiate IcebergTableManager with loaded plugins
    logger.info(
        "Creating IcebergTableManager",
        extra={
            "catalog_plugin": catalog_ref.type,
            "storage_plugin": storage_ref.type,
        },
    )
    table_manager = IcebergTableManager(
        catalog_plugin=catalog_plugin,
        storage_plugin=storage_plugin,
    )

    # T111: Create IcebergIOManager
    io_manager = create_iceberg_io_manager(
        table_manager=table_manager,
        namespace=default_namespace,
    )

    logger.info(
        "Iceberg resources created",
        extra={
            "catalog_type": catalog_ref.type,
            "storage_type": storage_ref.type,
            "namespace": default_namespace,
        },
    )

    return {"iceberg": io_manager}


def try_create_iceberg_resources(
    plugins: ResolvedPlugins | None,
) -> dict[str, Any]:
    """Attempt to create Iceberg resources, returning empty dict on failure.

    This is the safe entry point called by create_definitions(). It handles
    the case where catalog or storage plugins are not configured (both are
    optional in CompiledArtifacts) and catches plugin loading errors gracefully.

    Args:
        plugins: Resolved plugin selections from CompiledArtifacts.
            May be None if no plugins are configured.

    Returns:
        Dictionary with "iceberg" key if successful, empty dict otherwise.

    Example:
        >>> resources = try_create_iceberg_resources(artifacts.plugins)
        >>> # Returns {} if catalog or storage not configured
        >>> # Returns {"iceberg": IcebergIOManager} if both are available
    """
    if plugins is None:
        logger.debug("No plugins configured, skipping Iceberg resource creation")
        return {}

    if plugins.catalog is None:
        logger.debug("No catalog plugin configured, skipping Iceberg resource creation")
        return {}

    if plugins.storage is None:
        logger.debug("No storage plugin configured, skipping Iceberg resource creation")
        return {}

    try:
        return create_iceberg_resources(
            catalog_ref=plugins.catalog,
            storage_ref=plugins.storage,
        )
    except Exception:
        logger.warning(
            "Failed to create Iceberg resources, continuing without Iceberg support",
            exc_info=True,
        )
        return {}


__all__ = [
    "create_iceberg_resources",
    "try_create_iceberg_resources",
]
