"""dlt Ingestion Plugin for floe.

This package provides the DltIngestionPlugin implementation for data ingestion
using dlt (data load tool). It supports loading data from REST APIs, SQL databases,
and filesystem sources into Iceberg tables via the platform's catalog.

Example:
    >>> from floe_core.plugins import get_plugin
    >>> ingestion = get_plugin("ingestion", "dlt")
    >>> pipeline = ingestion.create_pipeline(config)
    >>> result = ingestion.run(pipeline)

Public API:
    - DltIngestionPlugin: Main plugin class (implements IngestionPlugin ABC)
    - DltIngestionConfig: Configuration model for dlt ingestion
    - IngestionSourceConfig: Per-source configuration
    - RetryConfig: Retry behavior configuration
    - ErrorCategory: Error categorization enum
    - IngestionError: Base exception class
    - Error subclasses: SourceConnectionError, DestinationWriteError, etc.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Configuration exports
from floe_ingestion_dlt.config import (
    VALID_SCHEMA_CONTRACTS,
    VALID_SOURCE_TYPES,
    VALID_WRITE_MODES,
    DltIngestionConfig,
    IngestionSourceConfig,
    RetryConfig,
)

# Error hierarchy exports
from floe_ingestion_dlt.errors import (
    DestinationWriteError,
    ErrorCategory,
    IngestionError,
    PipelineConfigurationError,
    SchemaContractViolation,
    SourceConnectionError,
)

# Plugin export
from floe_ingestion_dlt.plugin import DltIngestionPlugin

# Retry utilities
from floe_ingestion_dlt.retry import (
    categorize_error,
    create_retry_decorator,
    is_retryable,
)

# Tracing utilities
from floe_ingestion_dlt.tracing import (
    get_tracer,
    ingestion_span,
    record_ingestion_error,
    record_ingestion_result,
)

__all__ = [
    "__version__",
    # Configuration
    "DltIngestionConfig",
    "IngestionSourceConfig",
    "RetryConfig",
    "VALID_SCHEMA_CONTRACTS",
    "VALID_SOURCE_TYPES",
    "VALID_WRITE_MODES",
    # Errors
    "DestinationWriteError",
    "ErrorCategory",
    "IngestionError",
    "PipelineConfigurationError",
    "SchemaContractViolation",
    "SourceConnectionError",
    # Plugin
    "DltIngestionPlugin",
    # Retry
    "categorize_error",
    "create_retry_decorator",
    "is_retryable",
    # Tracing
    "get_tracer",
    "ingestion_span",
    "record_ingestion_error",
    "record_ingestion_result",
]
