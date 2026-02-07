"""Configuration models for the dlt ingestion plugin.

This module defines the Pydantic v2 configuration models used by
DltIngestionPlugin for managing data ingestion pipelines.

Models:
    - RetryConfig: Retry behavior with exponential backoff
    - IngestionSourceConfig: Per-source ingestion configuration
    - DltIngestionConfig: Top-level plugin configuration

Requirements Covered:
    - FR-067: DltIngestionConfig Pydantic model
    - FR-068: sources list of IngestionSourceConfig
    - FR-069: IngestionSourceConfig fields
    - FR-070: catalog_config for Polaris connection
    - FR-071: Optional retry_config
    - FR-072: Pydantic v2 field validators
    - FR-073: SecretStr for credentials
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from typing_extensions import Self

# Valid values for source_type, write_mode, and schema_contract.
# Extracted as module constants to avoid duplicate string literals (S1192).
VALID_SOURCE_TYPES = frozenset({"rest_api", "sql_database", "filesystem"})
VALID_WRITE_MODES = frozenset({"append", "replace", "merge"})
VALID_SCHEMA_CONTRACTS = frozenset({"evolve", "freeze", "discard_value"})

__all__ = [
    "DltIngestionConfig",
    "IngestionSourceConfig",
    "RetryConfig",
    "VALID_SOURCE_TYPES",
    "VALID_WRITE_MODES",
    "VALID_SCHEMA_CONTRACTS",
]


class RetryConfig(BaseModel):
    """Configuration for retry behavior with exponential backoff.

    Controls how the plugin retries transient errors during ingestion
    pipeline execution.

    Args:
        max_retries: Maximum number of retry attempts for transient errors.
        initial_delay_seconds: Initial delay before first retry (doubles each attempt).

    Example:
        >>> config = RetryConfig(max_retries=5, initial_delay_seconds=2.0)
        >>> config.max_retries
        5
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts for transient errors",
    )
    initial_delay_seconds: float = Field(
        default=1.0,
        gt=0.0,
        le=60.0,
        description="Initial delay in seconds before first retry (exponential backoff base)",
    )


class IngestionSourceConfig(BaseModel):
    """Configuration for a single ingestion data source.

    Defines how to connect to and ingest data from one external source.
    Each source becomes a separate orchestrator execution unit.

    Args:
        name: Unique identifier for this source (used in pipeline naming).
        source_type: Type of data source (rest_api, sql_database, filesystem).
        source_config: Source-specific configuration parameters.
        destination_table: Target Iceberg table path (e.g., "bronze.raw_customers").
        write_mode: How to write data (append, replace, merge).
        schema_contract: How to handle schema changes (evolve, freeze, discard_value).
        cursor_field: Optional field name for incremental loading cursor.
        primary_key: Optional primary key field(s) for merge write mode.
        credentials: Optional credentials for source authentication.

    Example:
        >>> source = IngestionSourceConfig(
        ...     name="salesforce_contacts",
        ...     source_type="rest_api",
        ...     source_config={"base_url": "https://api.salesforce.com"},
        ...     destination_table="bronze.raw_contacts",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique identifier for this source",
    )
    source_type: str = Field(
        ...,
        description="Type of data source (rest_api, sql_database, filesystem)",
    )
    source_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific configuration parameters",
    )
    destination_table: str = Field(
        ...,
        min_length=1,
        description="Target Iceberg table path (e.g., 'bronze.raw_customers')",
    )
    write_mode: str = Field(
        default="append",
        description="Write mode: append, replace, or merge",
    )
    schema_contract: str = Field(
        default="evolve",
        description="Schema contract: evolve, freeze, or discard_value",
    )
    cursor_field: str | None = Field(
        default=None,
        description="Field name for cursor-based incremental loading",
    )
    primary_key: str | list[str] | None = Field(
        default=None,
        description="Primary key field(s) for merge write mode",
    )
    credentials: SecretStr | None = Field(
        default=None,
        description="Optional credentials for source authentication",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate source name contains only valid identifier characters.

        Args:
            v: The source name to validate.

        Returns:
            The validated source name.

        Raises:
            ValueError: If name contains invalid characters.
        """
        if not v.replace("_", "").replace("-", "").isalnum():
            msg = (
                f"Source name '{v}' contains invalid characters. "
                "Only alphanumeric, underscore, and hyphen are allowed."
            )
            raise ValueError(msg)
        return v

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """Validate source_type is one of the supported types.

        Args:
            v: The source type to validate.

        Returns:
            The validated source type.

        Raises:
            ValueError: If source_type is not supported.
        """
        if v not in VALID_SOURCE_TYPES:
            msg = f"source_type must be one of {sorted(VALID_SOURCE_TYPES)}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("write_mode")
    @classmethod
    def validate_write_mode(cls, v: str) -> str:
        """Validate write_mode is one of the supported modes.

        Args:
            v: The write mode to validate.

        Returns:
            The validated write mode.

        Raises:
            ValueError: If write_mode is not supported.
        """
        if v not in VALID_WRITE_MODES:
            msg = f"write_mode must be one of {sorted(VALID_WRITE_MODES)}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("schema_contract")
    @classmethod
    def validate_schema_contract(cls, v: str) -> str:
        """Validate schema_contract is one of the supported modes.

        Args:
            v: The schema contract to validate.

        Returns:
            The validated schema contract.

        Raises:
            ValueError: If schema_contract is not supported.
        """
        if v not in VALID_SCHEMA_CONTRACTS:
            msg = (
                f"schema_contract must be one of {sorted(VALID_SCHEMA_CONTRACTS)}, got '{v}'"
            )
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_merge_requires_primary_key(self) -> Self:
        """Validate that merge write mode has a primary key configured.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If write_mode is 'merge' but primary_key is not set.
        """
        if self.write_mode == "merge" and not self.primary_key:
            msg = "primary_key is required when write_mode is 'merge'"
            raise ValueError(msg)
        return self


class DltIngestionConfig(BaseModel):
    """Top-level configuration for the dlt ingestion plugin.

    This is the configuration model returned by
    ``DltIngestionPlugin.get_config_schema()`` and used for validating
    ingestion configuration from ``floe.yaml``.

    Args:
        sources: List of ingestion source configurations (at least one required).
        catalog_config: Polaris catalog connection configuration.
        retry_config: Optional retry behavior configuration.

    Example:
        >>> config = DltIngestionConfig(
        ...     sources=[
        ...         IngestionSourceConfig(
        ...             name="github_events",
        ...             source_type="rest_api",
        ...             destination_table="bronze.raw_github_events",
        ...         ),
        ...     ],
        ...     catalog_config={
        ...         "uri": "http://polaris:8181/api/catalog",
        ...         "warehouse": "floe_warehouse",
        ...     },
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sources: list[IngestionSourceConfig] = Field(
        ...,
        min_length=1,
        description="List of ingestion source configurations",
    )
    catalog_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Polaris catalog connection configuration",
    )
    retry_config: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry behavior configuration for transient errors",
    )

    @field_validator("sources")
    @classmethod
    def validate_unique_source_names(
        cls, v: list[IngestionSourceConfig],
    ) -> list[IngestionSourceConfig]:
        """Validate that all source names are unique.

        Args:
            v: The list of source configurations.

        Returns:
            The validated source list.

        Raises:
            ValueError: If duplicate source names are found.
        """
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            msg = f"Duplicate source names found: {sorted(set(duplicates))}"
            raise ValueError(msg)
        return v
