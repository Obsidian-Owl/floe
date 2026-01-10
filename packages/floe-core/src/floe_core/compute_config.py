"""Compute Configuration Models for floe-core.

This module defines the Pydantic models for compute plugin configuration.
These models are the data contracts between manifest.yaml and ComputePlugin.

Models:
    - ConnectionStatus: Enum for health check status
    - ConnectionResult: Result of validate_connection()
    - ResourceSpec: K8s resource requirements
    - ComputeConfig: Base configuration for compute plugins
    - AttachConfig: DuckDB ATTACH configuration
    - DuckDBConfig: DuckDB-specific configuration
    - CatalogConfig: Iceberg catalog configuration

Example:
    >>> from floe_core.compute_config import (
    ...     ConnectionStatus,
    ...     ConnectionResult,
    ...     DuckDBConfig,
    ... )
    >>> config = DuckDBConfig(path=":memory:", memory_limit="4GB")
    >>> result = ConnectionResult(
    ...     status=ConnectionStatus.HEALTHY,
    ...     latency_ms=23.5,
    ...     message="Connected successfully"
    ... )
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ConnectionStatus(Enum):
    """Health check status for compute connections.

    Used by validate_connection() to report connection health.

    Values:
        HEALTHY: Connection successful, all checks passed.
        DEGRADED: Connection works but with issues (e.g., extension not loaded).
        UNHEALTHY: Connection failed.

    Example:
        >>> status = ConnectionStatus.HEALTHY
        >>> status.value
        'healthy'
    """

    HEALTHY = "healthy"
    """Connection successful, all checks passed."""

    DEGRADED = "degraded"
    """Connection works but with issues (e.g., extension not loaded)."""

    UNHEALTHY = "unhealthy"
    """Connection failed."""


class ConnectionResult(BaseModel):
    """Result of validate_connection() health check.

    Returned by ComputePlugin.validate_connection() to report connection
    health status, latency, and any warnings.

    Attributes:
        status: Health status (HEALTHY, DEGRADED, UNHEALTHY).
        latency_ms: Connection latency in milliseconds.
        message: Human-readable status message.
        warnings: Optional list of warning messages.

    Example:
        >>> result = ConnectionResult(
        ...     status=ConnectionStatus.HEALTHY,
        ...     latency_ms=23.5,
        ...     message="Connection successful"
        ... )
        >>> result.status
        <ConnectionStatus.HEALTHY: 'healthy'>
    """

    model_config = ConfigDict(frozen=True)

    status: ConnectionStatus
    latency_ms: float = Field(..., ge=0, description="Connection latency in milliseconds")
    message: str = Field(default="", description="Human-readable status message")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


class ResourceSpec(BaseModel):
    """K8s resource requirements for dbt job pods.

    Defines CPU, memory, and ephemeral storage requests and limits for
    Kubernetes job pods running dbt transforms.

    Attributes:
        cpu_request: CPU request in K8s format (e.g., "100m", "1").
        cpu_limit: CPU limit in K8s format.
        memory_request: Memory request in K8s format (e.g., "256Mi", "1Gi").
        memory_limit: Memory limit in K8s format.
        ephemeral_storage_request: Ephemeral storage request for dbt target/.
        ephemeral_storage_limit: Ephemeral storage limit.

    Example:
        >>> spec = ResourceSpec(
        ...     cpu_request="500m",
        ...     cpu_limit="2000m",
        ...     memory_request="1Gi",
        ...     memory_limit="4Gi"
        ... )
        >>> spec.cpu_limit
        '2000m'
    """

    model_config = ConfigDict(frozen=True)

    cpu_request: str = Field(default="100m", description="CPU request (K8s format)")
    cpu_limit: str = Field(default="1000m", description="CPU limit (K8s format)")
    memory_request: str = Field(default="256Mi", description="Memory request (K8s format)")
    memory_limit: str = Field(default="1Gi", description="Memory limit (K8s format)")
    ephemeral_storage_request: str = Field(default="100Mi", description="Ephemeral storage request")
    ephemeral_storage_limit: str = Field(default="1Gi", description="Ephemeral storage limit")


# Workload size presets for K8s resource requirements
WORKLOAD_PRESETS: dict[str, ResourceSpec] = {
    "small": ResourceSpec(
        cpu_request="100m",
        cpu_limit="500m",
        memory_request="256Mi",
        memory_limit="512Mi",
        ephemeral_storage_request="100Mi",
        ephemeral_storage_limit="500Mi",
    ),
    "medium": ResourceSpec(
        cpu_request="500m",
        cpu_limit="2000m",
        memory_request="1Gi",
        memory_limit="4Gi",
        ephemeral_storage_request="500Mi",
        ephemeral_storage_limit="2Gi",
    ),
    "large": ResourceSpec(
        cpu_request="2000m",
        cpu_limit="8000m",
        memory_request="4Gi",
        memory_limit="16Gi",
        ephemeral_storage_request="1Gi",
        ephemeral_storage_limit="5Gi",
    ),
}


class ComputeConfig(BaseModel):
    """Configuration for a compute target.

    Base configuration model passed to ComputePlugin methods. Contains
    common settings and plugin-specific connection parameters.

    Attributes:
        plugin: Compute plugin name (e.g., "duckdb", "snowflake").
        timeout_seconds: Query timeout in seconds.
        threads: Number of parallel query threads.
        connection: Plugin-specific connection settings.
        credentials: Runtime credentials (resolved from env/secrets).

    Example:
        >>> config = ComputeConfig(
        ...     plugin="duckdb",
        ...     threads=8,
        ...     connection={"path": ":memory:"}
        ... )
        >>> config.plugin
        'duckdb'
    """

    model_config = ConfigDict(extra="allow")

    plugin: str = Field(..., min_length=1, description="Compute plugin name")
    timeout_seconds: int = Field(
        default=3600, ge=1, le=86400, description="Query timeout in seconds"
    )
    threads: int = Field(default=4, ge=1, le=64, description="Parallel query threads")
    connection: dict[str, Any] = Field(
        default_factory=dict, description="Plugin-specific connection settings"
    )
    credentials: dict[str, SecretStr] = Field(
        default_factory=dict, description="Runtime credentials"
    )


class AttachConfig(BaseModel):
    """Configuration for DuckDB ATTACH statement.

    Defines how to attach an external Iceberg catalog to DuckDB.

    Attributes:
        path: Attach path (e.g., "iceberg:catalog_name").
        alias: Database alias in DuckDB.
        type: Attachment type (default: "iceberg").
        options: Additional options (catalog_uri, credentials, etc.).

    Example:
        >>> attach = AttachConfig(
        ...     path="iceberg:polaris",
        ...     alias="iceberg_catalog",
        ...     options={"catalog_uri": "http://polaris:8181/api/catalog"}
        ... )
        >>> attach.alias
        'iceberg_catalog'
    """

    model_config = ConfigDict(frozen=True)

    path: str = Field(..., description="Attach path (e.g., 'iceberg:catalog_name')")
    alias: str = Field(..., description="Database alias in DuckDB")
    type: str = Field(default="iceberg", description="Attachment type")
    options: dict[str, str] = Field(default_factory=dict, description="Additional options")


class DuckDBConfig(ComputeConfig):
    """DuckDB-specific compute configuration.

    Extends ComputeConfig with DuckDB-specific settings for in-memory,
    file-based, and Iceberg-attached modes.

    Attributes:
        plugin: Fixed to "duckdb" (discriminator).
        path: Database path (":memory:" for in-memory).
        memory_limit: Maximum memory for DuckDB (e.g., "4GB").
        extensions: DuckDB extensions to load (e.g., ["iceberg", "httpfs"]).
        attach: List of Iceberg catalogs to attach.

    Example:
        >>> config = DuckDBConfig(
        ...     path=":memory:",
        ...     memory_limit="8GB",
        ...     extensions=["iceberg", "httpfs"]
        ... )
        >>> config.path
        ':memory:'
    """

    plugin: Literal["duckdb"] = "duckdb"
    path: str = Field(default=":memory:", description="Database path")
    memory_limit: str = Field(default="4GB", description="Maximum memory for DuckDB")
    extensions: list[str] = Field(default_factory=list, description="Extensions to load")
    attach: list[AttachConfig] = Field(
        default_factory=list, description="Iceberg catalogs to attach"
    )

    @field_validator("memory_limit")
    @classmethod
    def validate_memory_limit(cls, v: str) -> str:
        """Validate memory_limit format (must end with GB or MB)."""
        if not v.endswith(("GB", "MB")):
            msg = "memory_limit must end with GB or MB"
            raise ValueError(msg)
        return v


class CatalogConfig(BaseModel):
    """Configuration for Iceberg catalog attachment.

    Used by get_catalog_attachment_sql() to generate SQL for attaching
    to a REST catalog like Polaris.

    Attributes:
        catalog_type: Catalog type (e.g., "rest", "glue").
        catalog_uri: Catalog REST endpoint.
        catalog_name: Catalog name in floe platform.
        warehouse: S3 warehouse path (optional).
        credentials: OAuth2 or IAM credentials.

    Example:
        >>> catalog = CatalogConfig(
        ...     catalog_type="rest",
        ...     catalog_uri="http://polaris:8181/api/catalog",
        ...     catalog_name="floe"
        ... )
        >>> catalog.catalog_name
        'floe'
    """

    model_config = ConfigDict(frozen=True)

    catalog_type: str = Field(..., description="Catalog type (rest, glue)")
    catalog_uri: str = Field(..., description="Catalog REST endpoint")
    catalog_name: str = Field(..., description="Catalog name")
    warehouse: str | None = Field(default=None, description="S3 warehouse path")
    credentials: dict[str, SecretStr] = Field(
        default_factory=dict, description="OAuth2 or IAM credentials"
    )
