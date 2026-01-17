"""floe-iceberg: IcebergTableManager utility for PyIceberg table operations.

This package provides an internal utility class for Iceberg table operations,
wrapping PyIceberg complexity with a consistent API for table creation,
schema evolution, writes, and snapshot management.

IcebergTableManager is NOT a plugin - Iceberg is enforced (ADR-0005), not pluggable.
It accepts CatalogPlugin and StoragePlugin via dependency injection.

Example:
    >>> from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
    >>> from floe_iceberg.models import TableConfig, WriteConfig, WriteMode
    >>>
    >>> manager = IcebergTableManager(
    ...     catalog_plugin=polaris_plugin,
    ...     storage_plugin=s3_plugin,
    ...     config=IcebergTableManagerConfig(max_commit_retries=3),
    ... )
    >>> table = manager.create_table(table_config)
    >>> manager.write_data(table, data, WriteConfig(mode=WriteMode.APPEND))

Modules:
    manager: IcebergTableManager class
    io_manager: IcebergIOManager for Dagster integration
    models: Pydantic configuration models
    errors: Custom exception types
    telemetry: OpenTelemetry instrumentation
    compaction: Compaction strategy implementations
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    # Core manager (implemented in later tasks)
    "IcebergTableManager",
    "IcebergTableManagerConfig",
    # IOManager for Dagster (implemented in later tasks)
    "IcebergIOManager",
    "IcebergIOManagerConfig",
    # Models - will be populated as implemented
    # Errors - will be populated as implemented
]


# Lazy imports to avoid circular dependencies and improve startup time
# These will be uncommented as the modules are implemented
def __getattr__(name: str) -> object:
    """Lazy import of package components."""
    if name == "IcebergTableManager":
        from floe_iceberg.manager import IcebergTableManager

        return IcebergTableManager
    if name == "IcebergTableManagerConfig":
        from floe_iceberg.models import IcebergTableManagerConfig

        return IcebergTableManagerConfig
    if name == "IcebergIOManager":
        from floe_iceberg.io_manager import IcebergIOManager

        return IcebergIOManager
    if name == "IcebergIOManagerConfig":
        from floe_iceberg.models import IcebergIOManagerConfig

        return IcebergIOManagerConfig
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
