"""Plugin configuration models for manifest schema.

This module provides models for plugin selection and configuration
across all 12 pluggable platform components.

Implements:
    - FR-006: Plugin Selection
    - FR-007: Plugin Registry Validation
    - FR-008: Plugin-Specific Configuration
    - FR-010: Secret Reference Handling (connection_secret_ref validation)
    - FR-018: Domain Plugin Whitelist Validation
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from floe_core.schemas.secrets import SECRET_NAME_PATTERN

# Known plugin types per category (built-in registry)
# In production, this would be populated from entry points
PLUGIN_REGISTRY: dict[str, list[str]] = {
    "compute": ["duckdb", "snowflake", "spark", "bigquery", "databricks"],
    "orchestrator": ["dagster", "airflow", "prefect"],
    "catalog": ["polaris", "glue", "hive"],
    "storage": ["s3", "gcs", "azure-blob", "minio"],
    "semantic_layer": ["cube", "dbt-semantic-layer"],
    "ingestion": ["dlt", "airbyte"],
    "secrets": ["k8s-secrets", "eso", "vault"],
    "telemetry_backend": ["console", "jaeger", "datadog", "grafana-cloud"],
    "lineage_backend": ["marquez", "atlan", "openmetadata"],
    "identity": ["k8s-rbac", "custom"],
    "dbt": ["local", "fusion"],
    "quality": ["great-expectations", "soda", "dbt-expectations"],
}
"""Registry of known plugin types per category.

This is the built-in default registry. In production environments,
plugins are discovered via entry points (floe.{category}).
"""


class PluginWhitelistError(Exception):
    """Raised when a plugin selection violates the enterprise whitelist.

    In 3-tier mode, enterprise manifests can restrict which plugins
    domains are allowed to use via approved_plugins.

    Attributes:
        category: The plugin category (e.g., "compute")
        plugin_type: The plugin type that was rejected
        approved_plugins: List of plugins that are approved for this category

    Example:
        >>> raise PluginWhitelistError(
        ...     category="compute",
        ...     plugin_type="spark",
        ...     approved_plugins=["duckdb", "snowflake"]
        ... )
    """

    def __init__(
        self,
        category: str,
        plugin_type: str,
        approved_plugins: list[str],
    ) -> None:
        """Initialize PluginWhitelistError.

        Args:
            category: The plugin category (e.g., "compute")
            plugin_type: The plugin type that was rejected
            approved_plugins: List of plugins that are approved
        """
        self.category = category
        self.plugin_type = plugin_type
        self.approved_plugins = approved_plugins
        approved_str = ", ".join(approved_plugins)
        message = (
            f"Plugin '{plugin_type}' is not in the approved whitelist for category "
            f"'{category}'. Approved plugins: [{approved_str}]"
        )
        super().__init__(message)


class PluginSelection(BaseModel):
    """A choice of specific plugin for a platform capability.

    Represents the selection of a particular plugin implementation
    for one of the 12 pluggable platform components.

    Attributes:
        type: Plugin name (e.g., "duckdb", "snowflake", "dagster")
        version: Plugin version (semver) for reproducibility
        config: Plugin-specific configuration options
        connection_secret_ref: Reference to K8s Secret for credentials

    Example:
        >>> selection = PluginSelection(
        ...     type="duckdb",
        ...     version="0.9.0",
        ...     config={"threads": 4, "memory_limit": "8GB"},
        ...     connection_secret_ref="db-credentials"
        ... )
        >>> selection.type
        'duckdb'

    Validation Rules:
        - type: Required, must match registered plugin name (validated at runtime)
        - version: Optional semver string for reproducibility
        - config: Optional dict for plugin-specific settings
        - connection_secret_ref: Optional K8s Secret name for credentials

    See Also:
        - data-model.md: PluginSelection entity specification
        - PluginsConfig: Container for all plugin selections
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "type": "duckdb",
                    "version": "0.9.0",
                    "config": {"threads": 4},
                },
                {
                    "type": "snowflake",
                    "version": "2.0.0",
                    "connection_secret_ref": "snowflake-credentials",
                },
            ]
        },
    )

    type: Annotated[
        str,
        Field(
            min_length=1,
            description="Plugin name (must match registered plugin)",
            examples=["duckdb", "snowflake", "dagster", "polaris"],
        ),
    ]
    version: str | None = Field(
        default=None,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Plugin version (semver) for reproducibility",
        examples=["0.9.0", "1.2.3"],
    )
    config: dict[str, Any] | None = Field(
        default=None,
        description="Plugin-specific configuration options",
    )
    connection_secret_ref: (
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=253,  # K8s Secret name limit
                pattern=SECRET_NAME_PATTERN,
                description="K8s Secret name for credentials (lowercase alphanumeric with hyphens)",
                examples=["polaris-credentials", "snowflake-creds"],
            ),
        ]
        | None
    ) = None

    @field_validator("type")
    @classmethod
    def validate_type_not_whitespace(cls, v: str) -> str:
        """Validate that type is not whitespace-only.

        Args:
            v: The plugin type value

        Returns:
            The validated type (stripped)

        Raises:
            ValueError: If type is whitespace-only
        """
        stripped = v.strip()
        if not stripped:
            raise ValueError("Plugin type cannot be empty or whitespace-only")
        return stripped


class PluginsConfig(BaseModel):
    """Configuration for all pluggable platform components.

    Defines plugin selections for all 12 platform capability categories.
    Each category corresponds to an entry point group (floe.{category}).

    Per ADR-0035, observability is split into two independent categories:
    - telemetry_backend: OTLP-based backends (Jaeger, Datadog, Grafana Cloud)
    - lineage_backend: OpenLineage-based backends (Marquez, Atlan, OpenMetadata)

    This enables mixed backends (e.g., Datadog for telemetry + Atlan for lineage).

    Attributes:
        compute: Compute engine (DuckDB, Snowflake, Spark, BigQuery, Databricks)
        orchestrator: Workflow orchestration (Dagster, Airflow 3.x, Prefect)
        catalog: Data catalog (Polaris, AWS Glue, Hive)
        storage: Object storage (S3, GCS, Azure Blob, MinIO)
        semantic_layer: Semantic layer (Cube, dbt Semantic Layer)
        ingestion: Data ingestion (dlt, Airbyte)
        secrets: Secret management (K8s Secrets, ESO, Vault)
        telemetry_backend: Telemetry backend - OTLP (Jaeger, Datadog, Grafana Cloud)
        lineage_backend: Lineage backend - OpenLineage (Marquez, Atlan, OpenMetadata)
        identity: Identity/auth (K8s RBAC, custom)
        dbt: dbt execution (local, fusion)
        quality: Data quality (Great Expectations, Soda, dbt Expectations)

    Example:
        >>> plugins = PluginsConfig(
        ...     compute=PluginSelection(type="duckdb"),
        ...     orchestrator=PluginSelection(type="dagster"),
        ...     catalog=PluginSelection(type="polaris"),
        ... )
        >>> plugins.compute.type
        'duckdb'

    See Also:
        - data-model.md: PluginsConfig entity specification
        - Constitution Principle II: 12 plugin categories
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "compute": {"type": "duckdb"},
                    "orchestrator": {"type": "dagster"},
                    "catalog": {"type": "polaris"},
                }
            ]
        },
    )

    # Core compute and orchestration
    compute: PluginSelection | None = Field(
        default=None,
        description="Compute engine (duckdb, snowflake, spark, bigquery, databricks)",
    )
    orchestrator: PluginSelection | None = Field(
        default=None,
        description="Workflow orchestration (dagster, airflow, prefect)",
    )

    # Data management
    catalog: PluginSelection | None = Field(
        default=None,
        description="Data catalog (polaris, glue, hive)",
    )
    storage: PluginSelection | None = Field(
        default=None,
        description="Object storage (s3, gcs, azure-blob, minio)",
    )

    # Analytics and consumption
    semantic_layer: PluginSelection | None = Field(
        default=None,
        description="Semantic layer (cube, dbt-semantic-layer)",
    )

    # Data movement
    ingestion: PluginSelection | None = Field(
        default=None,
        description="Data ingestion (dlt, airbyte)",
    )

    # Platform services
    secrets: PluginSelection | None = Field(
        default=None,
        description="Secret management (k8s-secrets, eso, vault)",
    )
    telemetry_backend: PluginSelection | None = Field(
        default=None,
        description="Telemetry backend - OTLP (jaeger, datadog, grafana-cloud)",
    )
    lineage_backend: PluginSelection | None = Field(
        default=None,
        description="Lineage backend - OpenLineage (marquez, atlan, openmetadata)",
    )
    identity: PluginSelection | None = Field(
        default=None,
        description="Identity/auth (k8s-rbac, custom)",
    )

    # Transformation
    dbt: PluginSelection = Field(
        default_factory=lambda: PluginSelection(type="core"),
        description="dbt execution runtime (core, fusion). Defaults to 'core'.",
    )

    # Data quality
    quality: PluginSelection | None = Field(
        default=None,
        description="Data quality (great-expectations, soda, dbt-expectations)",
    )


def get_available_plugins(category: str) -> list[str]:
    """Get the list of available plugins for a category.

    Returns the list of known plugin types for the specified category.
    In production, this would query the entry point registry.

    Args:
        category: Plugin category (e.g., "compute", "orchestrator")

    Returns:
        List of available plugin names for the category

    Raises:
        ValueError: If category is unknown

    Example:
        >>> plugins = get_available_plugins("compute")
        >>> "duckdb" in plugins
        True
    """
    if category not in PLUGIN_REGISTRY:
        valid_categories = ", ".join(sorted(PLUGIN_REGISTRY.keys()))
        raise ValueError(
            f"Unknown plugin category '{category}'. Valid categories: [{valid_categories}]"
        )
    return list(PLUGIN_REGISTRY[category])


def validate_plugin_selection(category: str, plugin_type: str) -> None:
    """Validate that a plugin type is valid for the given category.

    Checks the plugin type against the registry of known plugins.
    This enables early validation with helpful error messages.

    Args:
        category: Plugin category (e.g., "compute", "orchestrator")
        plugin_type: The plugin type to validate

    Raises:
        ValueError: If plugin type is not in the registry for this category

    Example:
        >>> validate_plugin_selection("compute", "duckdb")  # OK
        >>> validate_plugin_selection("compute", "invalid")  # Raises ValueError
    """
    available = get_available_plugins(category)
    if plugin_type not in available:
        available_str = ", ".join(available)
        raise ValueError(
            f"Plugin '{plugin_type}' is not a valid {category} plugin. "
            f"Available plugins: [{available_str}]"
        )


def validate_domain_plugin_whitelist(
    category: str,
    plugin_type: str,
    approved_plugins: dict[str, list[str]],
) -> None:
    """Validate that a domain plugin selection is within enterprise whitelist.

    In 3-tier mode, enterprise manifests can restrict which plugins
    domains are allowed to use via the approved_plugins field.

    Args:
        category: Plugin category (e.g., "compute", "orchestrator")
        plugin_type: The plugin type being selected
        approved_plugins: Enterprise whitelist mapping category to allowed plugins

    Raises:
        PluginWhitelistError: If plugin is not in whitelist for the category

    Example:
        >>> validate_domain_plugin_whitelist(
        ...     category="compute",
        ...     plugin_type="duckdb",
        ...     approved_plugins={"compute": ["duckdb", "snowflake"]}
        ... )  # OK

        >>> validate_domain_plugin_whitelist(
        ...     category="compute",
        ...     plugin_type="spark",
        ...     approved_plugins={"compute": ["duckdb", "snowflake"]}
        ... )  # Raises PluginWhitelistError
    """
    # If category not in whitelist, all plugins are allowed
    if category not in approved_plugins:
        return

    # If category in whitelist, plugin must be in approved list
    approved = approved_plugins[category]
    if plugin_type not in approved:
        raise PluginWhitelistError(
            category=category,
            plugin_type=plugin_type,
            approved_plugins=approved,
        )


__all__ = [
    "PluginSelection",
    "PluginsConfig",
    "PluginWhitelistError",
    "PLUGIN_REGISTRY",
    "get_available_plugins",
    "validate_plugin_selection",
    "validate_domain_plugin_whitelist",
]
