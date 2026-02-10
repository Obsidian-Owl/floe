"""Error types for the dlt ingestion plugin.

This module defines the exception hierarchy and error categorization
for the dlt ingestion plugin. All errors inherit from IngestionError.

Error Categories (FR-051):
    - TRANSIENT: Retryable (HTTP 429/503, network timeout, connection reset)
    - PERMANENT: Not retryable (HTTP 401/403, missing resource, permission denied)
    - PARTIAL: Partially retryable (incomplete batch load)
    - CONFIGURATION: Setup error (HTTP 400/404, invalid config, missing source package)

Exception Hierarchy:
    IngestionError (base)
    ├── SourceConnectionError (source unreachable)
    ├── DestinationWriteError (Iceberg write failure)
    ├── SchemaContractViolation (schema change rejected)
    └── PipelineConfigurationError (invalid pipeline config)

Requirements Covered:
    - FR-051: Error categorization with concrete criteria
    - FR-055: Custom exception hierarchy
    - FR-056: Source context in all errors
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "DestinationWriteError",
    "ErrorCategory",
    "IngestionError",
    "PipelineConfigurationError",
    "SchemaContractViolation",
    "SinkConfigurationError",
    "SinkConnectionError",
    "SinkWriteError",
    "SourceConnectionError",
]


class ErrorCategory(Enum):
    """Categorization of ingestion errors for retry decisions.

    Each category determines whether and how the error should be retried.

    Attributes:
        TRANSIENT: Retryable errors (network timeout, rate limit, temporary unavailability).
            HTTP 429, 503, connection reset, socket timeout.
        PERMANENT: Non-retryable errors (invalid credentials, missing resource).
            HTTP 401, 403, permission denied.
        PARTIAL: Partially retryable errors (incomplete batch load).
            Some records loaded, some failed.
        CONFIGURATION: Setup errors requiring user intervention.
            HTTP 400, 404, invalid config, missing source package.

    Example:
        >>> from floe_ingestion_dlt.errors import ErrorCategory
        >>> ErrorCategory.TRANSIENT.value
        'transient'
    """

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    PARTIAL = "partial"
    CONFIGURATION = "configuration"


class IngestionError(Exception):
    """Base exception for all dlt ingestion plugin errors.

    All plugin-specific exceptions inherit from this class, enabling
    callers to catch any ingestion-related error with a single except clause.

    Args:
        message: Human-readable error description.
        source_type: Type of data source (e.g., "rest_api", "sql_database").
        destination_table: Target Iceberg table path.
        pipeline_name: dlt pipeline name for state isolation.
        category: Error category for retry decisions.

    Example:
        >>> raise IngestionError(
        ...     "Pipeline execution failed",
        ...     source_type="rest_api",
        ...     destination_table="bronze.raw_events",
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        destination_table: str | None = None,
        pipeline_name: str | None = None,
        category: ErrorCategory = ErrorCategory.PERMANENT,
    ) -> None:
        self.message = message
        self.source_type = source_type
        self.destination_table = destination_table
        self.pipeline_name = pipeline_name
        self.category = category

        # Build context suffix for debugging (FR-056)
        context_parts: list[str] = []
        if source_type is not None:
            context_parts.append(f"source_type={source_type}")
        if destination_table is not None:
            context_parts.append(f"destination_table={destination_table}")
        if pipeline_name is not None:
            context_parts.append(f"pipeline={pipeline_name}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        super().__init__(f"{message}{context_str}")


class SourceConnectionError(IngestionError):
    """Error connecting to the data source.

    Raised when the source is unreachable during pipeline creation or execution.
    Typically categorized as TRANSIENT (network issues) or PERMANENT (auth failures).

    Args:
        message: Human-readable error description.
        source_type: Type of data source.
        destination_table: Target Iceberg table path.
        pipeline_name: dlt pipeline name.
        category: Error category (default: TRANSIENT for connection issues).

    Example:
        >>> raise SourceConnectionError(
        ...     "Connection refused",
        ...     source_type="sql_database",
        ...     category=ErrorCategory.TRANSIENT,
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        destination_table: str | None = None,
        pipeline_name: str | None = None,
        category: ErrorCategory = ErrorCategory.TRANSIENT,
    ) -> None:
        super().__init__(
            message,
            source_type=source_type,
            destination_table=destination_table,
            pipeline_name=pipeline_name,
            category=category,
        )


class DestinationWriteError(IngestionError):
    """Error writing data to the Iceberg destination.

    Raised when the dlt pipeline fails to write data to Iceberg tables.
    The plugin catches the failure and wraps it in this error; Iceberg/dlt
    handle transaction rollback via snapshot isolation (FR-057).

    Args:
        message: Human-readable error description.
        source_type: Type of data source.
        destination_table: Target Iceberg table path.
        pipeline_name: dlt pipeline name.
        category: Error category (default: TRANSIENT for write failures).

    Example:
        >>> raise DestinationWriteError(
        ...     "Failed to commit Iceberg snapshot",
        ...     destination_table="bronze.raw_orders",
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        destination_table: str | None = None,
        pipeline_name: str | None = None,
        category: ErrorCategory = ErrorCategory.TRANSIENT,
    ) -> None:
        super().__init__(
            message,
            source_type=source_type,
            destination_table=destination_table,
            pipeline_name=pipeline_name,
            category=category,
        )


class SchemaContractViolation(IngestionError):
    """Schema change rejected by contract enforcement.

    Raised when the source schema changes and the configured schema
    contract mode does not allow the change (e.g., ``freeze`` mode
    rejecting a new column).

    Args:
        message: Human-readable error description.
        source_type: Type of data source.
        destination_table: Target Iceberg table path.
        pipeline_name: dlt pipeline name.
        category: Error category (default: PERMANENT for contract violations).

    Example:
        >>> raise SchemaContractViolation(
        ...     "New column 'phone' rejected by freeze contract",
        ...     destination_table="bronze.raw_contacts",
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        destination_table: str | None = None,
        pipeline_name: str | None = None,
        category: ErrorCategory = ErrorCategory.PERMANENT,
    ) -> None:
        super().__init__(
            message,
            source_type=source_type,
            destination_table=destination_table,
            pipeline_name=pipeline_name,
            category=category,
        )


class PipelineConfigurationError(IngestionError):
    """Invalid pipeline configuration.

    Raised when the pipeline cannot be configured due to invalid settings,
    missing source packages, or incompatible configuration combinations.

    Args:
        message: Human-readable error description.
        source_type: Type of data source.
        destination_table: Target Iceberg table path.
        pipeline_name: dlt pipeline name.
        category: Error category (default: CONFIGURATION).

    Example:
        >>> raise PipelineConfigurationError(
        ...     "Source package 'dlt-rest-api' is not installed",
        ...     source_type="rest_api",
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        destination_table: str | None = None,
        pipeline_name: str | None = None,
        category: ErrorCategory = ErrorCategory.CONFIGURATION,
    ) -> None:
        super().__init__(
            message,
            source_type=source_type,
            destination_table=destination_table,
            pipeline_name=pipeline_name,
            category=category,
        )


class SinkConnectionError(IngestionError):
    """Error connecting to the reverse ETL sink destination.

    Raised when the sink destination is unreachable during sink creation
    or write operations. Typically categorized as TRANSIENT (network issues)
    or PERMANENT (authentication failures).

    Args:
        message: Human-readable error description.
        source_type: Type of data source.
        destination_table: Target Iceberg table path.
        pipeline_name: dlt pipeline name.
        category: Error category (default: TRANSIENT for connection issues).

    Example:
        >>> raise SinkConnectionError(
        ...     "Destination API returned 503",
        ...     source_type="rest_api",
        ...     category=ErrorCategory.TRANSIENT,
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        destination_table: str | None = None,
        pipeline_name: str | None = None,
        category: ErrorCategory = ErrorCategory.TRANSIENT,
    ) -> None:
        super().__init__(
            message,
            source_type=source_type,
            destination_table=destination_table,
            pipeline_name=pipeline_name,
            category=category,
        )


class SinkWriteError(IngestionError):
    """Error writing data to the reverse ETL sink destination.

    Raised when the write operation fails due to rate limiting, timeout,
    or partial failure. The plugin wraps the failure; destination-specific
    rollback is the responsibility of the sink connector implementation.

    Args:
        message: Human-readable error description.
        source_type: Type of data source.
        destination_table: Target Iceberg table path.
        pipeline_name: dlt pipeline name.
        category: Error category (default: TRANSIENT for write failures).

    Example:
        >>> raise SinkWriteError(
        ...     "Rate limit exceeded (HTTP 429)",
        ...     destination_table="gold.customers",
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        destination_table: str | None = None,
        pipeline_name: str | None = None,
        category: ErrorCategory = ErrorCategory.TRANSIENT,
    ) -> None:
        super().__init__(
            message,
            source_type=source_type,
            destination_table=destination_table,
            pipeline_name=pipeline_name,
            category=category,
        )


class SinkConfigurationError(IngestionError):
    """Invalid sink configuration for reverse ETL.

    Raised when the sink cannot be configured due to invalid settings,
    unsupported sink types, or missing connection details.

    Args:
        message: Human-readable error description.
        source_type: Type of data source.
        destination_table: Target Iceberg table path.
        pipeline_name: dlt pipeline name.
        category: Error category (default: CONFIGURATION).

    Example:
        >>> raise SinkConfigurationError(
        ...     "Unsupported sink type 'ftp'",
        ...     source_type="ftp",
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        destination_table: str | None = None,
        pipeline_name: str | None = None,
        category: ErrorCategory = ErrorCategory.CONFIGURATION,
    ) -> None:
        super().__init__(
            message,
            source_type=source_type,
            destination_table=destination_table,
            pipeline_name=pipeline_name,
            category=category,
        )
