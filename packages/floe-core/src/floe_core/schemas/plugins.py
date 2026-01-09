"""Plugin configuration models for manifest schema.

This module provides models for plugin selection and configuration
across all 11 pluggable platform components.

Implements:
    - FR-006: Plugin Selection
    - FR-008: Plugin-Specific Configuration
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class PluginSelection(BaseModel):
    """A choice of specific plugin for a platform capability.

    Represents the selection of a particular plugin implementation
    for one of the 11 pluggable platform components.

    Attributes:
        type: Plugin name (e.g., "duckdb", "snowflake", "dagster")
        config: Plugin-specific configuration options
        connection_secret_ref: Reference to K8s Secret for credentials

    Example:
        >>> selection = PluginSelection(
        ...     type="duckdb",
        ...     config={"threads": 4, "memory_limit": "8GB"},
        ...     connection_secret_ref="db-credentials"
        ... )
        >>> selection.type
        'duckdb'

    Validation Rules:
        - type: Required, must match registered plugin name (validated at runtime)
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
                    "config": {"threads": 4},
                },
                {
                    "type": "snowflake",
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
    config: dict[str, Any] | None = Field(
        default=None,
        description="Plugin-specific configuration options",
    )
    connection_secret_ref: str | None = Field(
        default=None,
        description="K8s Secret name for credentials",
    )


class PluginsConfig(BaseModel):
    """Configuration for all pluggable platform components.

    Defines plugin selections for all 11 platform capability categories.
    Each category corresponds to an entry point group (floe.{category}).

    Attributes:
        compute: Compute engine (DuckDB, Snowflake, Spark, BigQuery, Databricks)
        orchestrator: Workflow orchestration (Dagster, Airflow 3.x, Prefect)
        catalog: Data catalog (Polaris, AWS Glue, Hive)
        storage: Object storage (S3, GCS, Azure Blob, MinIO)
        semantic_layer: Semantic layer (Cube, dbt Semantic Layer)
        ingestion: Data ingestion (dlt, Airbyte)
        secrets: Secret management (K8s Secrets, ESO, Vault)
        observability: Observability (Jaeger, Datadog, Grafana Cloud)
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
        - Constitution Principle II: 11 plugin categories
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
    observability: PluginSelection | None = Field(
        default=None,
        description="Observability (jaeger, datadog, grafana-cloud)",
    )
    identity: PluginSelection | None = Field(
        default=None,
        description="Identity/auth (k8s-rbac, custom)",
    )

    # Transformation
    dbt: PluginSelection | None = Field(
        default=None,
        description="dbt execution (local, fusion)",
    )

    # Data quality
    quality: PluginSelection | None = Field(
        default=None,
        description="Data quality (great-expectations, soda, dbt-expectations)",
    )


__all__ = [
    "PluginSelection",
    "PluginsConfig",
]
