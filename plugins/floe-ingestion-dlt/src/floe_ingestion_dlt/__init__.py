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
"""

from __future__ import annotations

__version__ = "0.1.0"

# Public API exports - imported here so entry point resolves correctly.
# DltIngestionPlugin is the entry point target: floe_ingestion_dlt:DltIngestionPlugin
from floe_ingestion_dlt.config import (
    DltIngestionConfig,
    IngestionSourceConfig,
    RetryConfig,
)
from floe_ingestion_dlt.plugin import DltIngestionPlugin

__all__ = [
    "__version__",
    "DltIngestionConfig",
    "DltIngestionPlugin",
    "IngestionSourceConfig",
    "RetryConfig",
]
