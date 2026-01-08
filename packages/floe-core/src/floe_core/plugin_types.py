"""Plugin type definitions for floe-core.

This module defines the PluginType enum, which enumerates all 11 plugin categories
in the floe platform. Each plugin type corresponds to a specific entry point group
used for plugin discovery.

Example:
    >>> from floe_core.plugin_types import PluginType
    >>> PluginType.COMPUTE.entry_point_group
    'floe.computes'
"""

from __future__ import annotations

from enum import Enum


class PluginType(Enum):
    """Enumeration of the 11 plugin categories in the floe platform.

    Each enum member has a `value` that is the entry point group name used
    for plugin discovery via `importlib.metadata.entry_points()`.

    Attributes:
        COMPUTE: Where dbt transforms execute (DuckDB, Snowflake, etc.)
        ORCHESTRATOR: Job scheduling and execution (Dagster, Airflow)
        CATALOG: Iceberg table catalog (Polaris, AWS Glue)
        STORAGE: Object storage for Iceberg data (S3, GCS, Azure)
        TELEMETRY_BACKEND: OTLP telemetry backend (Jaeger, OTEL Collector)
        LINEAGE_BACKEND: OpenLineage backend (Marquez, Datahub)
        DBT: dbt compilation environment
        SEMANTIC_LAYER: Business intelligence API (Cube, dbt Semantic Layer)
        INGESTION: Data loading from sources (dlt, Airbyte)
        SECRETS: Credential management (Vault, AWS Secrets Manager)
        IDENTITY: Authentication provider (OAuth, OIDC)

    Example:
        >>> PluginType.COMPUTE.entry_point_group
        'floe.computes'
        >>> PluginType.CATALOG.entry_point_group
        'floe.catalogs'
    """

    COMPUTE = "floe.computes"
    ORCHESTRATOR = "floe.orchestrators"
    CATALOG = "floe.catalogs"
    STORAGE = "floe.storage"
    TELEMETRY_BACKEND = "floe.telemetry_backends"
    LINEAGE_BACKEND = "floe.lineage_backends"
    DBT = "floe.dbt"
    SEMANTIC_LAYER = "floe.semantic_layers"
    INGESTION = "floe.ingestion"
    SECRETS = "floe.secrets"
    IDENTITY = "floe.identity"

    @property
    def entry_point_group(self) -> str:
        """Return the entry point group name for this plugin type.

        Returns:
            The entry point group string (e.g., 'floe.computes').
        """
        return self.value

    @classmethod
    def all_entry_point_groups(cls) -> list[str]:
        """Return all entry point group names.

        Returns:
            List of all 11 entry point group strings.

        Example:
            >>> PluginType.all_entry_point_groups()
            ['floe.computes', 'floe.orchestrators', ...]
        """
        return [member.value for member in cls]

    @classmethod
    def from_entry_point_group(cls, group: str) -> PluginType:
        """Get PluginType from an entry point group name.

        Args:
            group: Entry point group string (e.g., 'floe.computes').

        Returns:
            The corresponding PluginType enum member.

        Raises:
            ValueError: If the group is not a valid floe entry point group.

        Example:
            >>> PluginType.from_entry_point_group('floe.computes')
            <PluginType.COMPUTE: 'floe.computes'>
        """
        for member in cls:
            if member.value == group:
                return member
        valid_groups = ", ".join(cls.all_entry_point_groups())
        raise ValueError(f"Unknown entry point group: {group}. Valid groups: {valid_groups}")
