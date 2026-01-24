"""floe-iceberg: IcebergTableManager utility for PyIceberg table operations.

This package provides an internal utility class for Iceberg table operations,
wrapping PyIceberg complexity with a consistent API for table creation,
schema evolution, writes, and snapshot management.

IcebergTableManager is NOT a plugin - Iceberg is enforced (ADR-0005), not pluggable.
It accepts CatalogPlugin and StoragePlugin via dependency injection.

Note: IOManager for Dagster integration is NOT part of this package. Orchestrator-specific
integrations belong in the respective orchestrator plugins (e.g., floe-orchestrator-dagster).
floe-iceberg is orchestrator-agnostic.

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
    models: Pydantic configuration models
    errors: Custom exception types
    telemetry: OpenTelemetry instrumentation
    compaction: Compaction strategy implementations
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    # Core manager (orchestrator-agnostic)
    "IcebergTableManager",
    "IcebergTableManagerConfig",
    # Schema drift detection
    "DriftDetector",
    # Note: IOManager is NOT exported here - it belongs in orchestrator plugins
    # See: plugins/floe-orchestrator-dagster/ (Epic 4B)
]


# Lazy imports to avoid circular dependencies and improve startup time
def __getattr__(name: str) -> object:
    """Lazy import of package components."""
    if name == "IcebergTableManager":
        from floe_iceberg.manager import IcebergTableManager

        return IcebergTableManager
    if name == "IcebergTableManagerConfig":
        from floe_iceberg.models import IcebergTableManagerConfig

        return IcebergTableManagerConfig
    if name == "DriftDetector":
        from floe_iceberg.drift_detector import DriftDetector

        return DriftDetector
    # Note: IcebergIOManager is NOT available from floe-iceberg
    # IOManager belongs in orchestrator plugins (e.g., floe-orchestrator-dagster)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
