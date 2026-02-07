# Data Model: DltIngestionPlugin (Epic 4F)

**Created**: 2026-02-07
**Status**: Complete
**Source**: spec.md Key Entities section

## Overview

This document defines the Pydantic models, dataclasses, and data structures for the dlt ingestion plugin. All Pydantic models use v2 syntax with strict validation. Existing floe-core dataclasses (`IngestionConfig`, `IngestionResult`) are NOT modified.

## Module Constants

```python
# SonarQube S1192 compliance - extract repeated string literals
ALLOWED_SOURCE_TYPES = frozenset({"rest_api", "sql_database", "filesystem"})
"""Supported dlt source types for initial implementation."""

ALLOWED_WRITE_MODES = frozenset({"append", "replace", "merge"})
"""Supported write dispositions mapping to dlt write_disposition."""

ALLOWED_SCHEMA_CONTRACTS = frozenset({"evolve", "freeze", "discard_value"})
"""Supported dlt schema contract modes."""

SOURCE_TYPE_FIELD_DESCRIPTION = "Data source type (rest_api, sql_database, filesystem)"
"""Shared description for source_type fields."""
```

## Core Entities

### 1. DltIngestionConfig

Top-level configuration for the DltIngestionPlugin instance.

```python
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class DltIngestionConfig(BaseModel):
    """Configuration for DltIngestionPlugin.

    Passed from CompiledArtifacts.plugins.ingestion.config
    through the plugin registry.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    sources: list[IngestionSourceConfig] = Field(
        ...,
        min_length=1,
        description="Data sources to ingest (at least one required)"
    )
    catalog_config: dict[str, Any] = Field(
        ...,
        description="Polaris REST catalog connection details (uri, warehouse)"
    )
    retry_config: RetryConfig | None = Field(
        default=None,
        description="Optional retry parameters for transient errors"
    )
```

### 2. IngestionSourceConfig

Per-source configuration defining how to extract and load data.

```python
class IngestionSourceConfig(BaseModel):
    """Configuration for a single ingestion source.

    Each source becomes one orchestrator execution unit.
    Maps to dlt pipeline + source configuration.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique source identifier within this config"
    )
    source_type: str = Field(
        ...,
        description=SOURCE_TYPE_FIELD_DESCRIPTION
    )
    source_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific parameters (API base URL, DB connection, file path)"
    )
    destination_table: str = Field(
        ...,
        min_length=1,
        description="Iceberg table path (e.g., 'bronze.raw_customers')"
    )
    write_mode: str = Field(
        default="append",
        description="Write disposition: append, replace, or merge"
    )
    schema_contract: str = Field(
        default="evolve",
        description="Schema contract: evolve, freeze, or discard_value"
    )
    cursor_field: str | None = Field(
        default=None,
        description="Field for incremental loading (e.g., 'updated_at')"
    )
    primary_key: str | list[str] | None = Field(
        default=None,
        description="Primary key column(s) for merge write mode"
    )

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """Validate source_type is in allowed set."""
        if v not in ALLOWED_SOURCE_TYPES:
            msg = f"source_type must be one of {sorted(ALLOWED_SOURCE_TYPES)}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("write_mode")
    @classmethod
    def validate_write_mode(cls, v: str) -> str:
        """Validate write_mode is in allowed set."""
        if v not in ALLOWED_WRITE_MODES:
            msg = f"write_mode must be one of {sorted(ALLOWED_WRITE_MODES)}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("schema_contract")
    @classmethod
    def validate_schema_contract(cls, v: str) -> str:
        """Validate schema_contract is in allowed set."""
        if v not in ALLOWED_SCHEMA_CONTRACTS:
            msg = f"schema_contract must be one of {sorted(ALLOWED_SCHEMA_CONTRACTS)}, got '{v}'"
            raise ValueError(msg)
        return v
```

### 3. RetryConfig

Configuration for tenacity-based retry behavior.

```python
class RetryConfig(BaseModel):
    """Retry configuration for transient pipeline errors.

    Applied via tenacity decorator on the run() method.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for transient errors (0 = no retry)"
    )
    initial_delay_seconds: float = Field(
        default=1.0,
        gt=0,
        le=60.0,
        description="Initial delay for exponential backoff"
    )
```

### 4. ErrorCategory (Enum)

Error taxonomy for categorizing dlt pipeline failures.

```python
from enum import Enum


class ErrorCategory(str, Enum):
    """Classification of pipeline errors for retry logic.

    Used by categorize_error() to determine retry behavior.
    """
    TRANSIENT = "transient"        # Network timeout, rate limit — retryable
    PERMANENT = "permanent"        # Auth failure, missing resource — not retryable
    PARTIAL = "partial"            # Partial load — partially retryable
    CONFIGURATION = "configuration"  # Invalid config — not retryable
```

### 5. Error Hierarchy

Custom exception classes carrying pipeline context.

```python
class IngestionError(Exception):
    """Base error for ingestion plugin operations.

    All ingestion errors carry pipeline context for debugging.
    """
    def __init__(
        self,
        message: str,
        source_type: str = "",
        destination_table: str = "",
        pipeline_name: str = "",
        category: ErrorCategory = ErrorCategory.TRANSIENT,
    ) -> None:
        super().__init__(message)
        self.source_type = source_type
        self.destination_table = destination_table
        self.pipeline_name = pipeline_name
        self.category = category


class SourceConnectionError(IngestionError):
    """Source is unreachable or refuses connection.

    Raised during create_pipeline() when source validation fails.
    Default category: TRANSIENT (may be temporary).
    """
    pass


class DestinationWriteError(IngestionError):
    """Failed to write data to Iceberg destination.

    Raised during run() when the load step fails.
    Default category: TRANSIENT (may be temporary).
    """
    pass


class SchemaContractViolation(IngestionError):
    """Schema change rejected by freeze or discard_value contract.

    Raised during run() when schema evolution is blocked.
    Default category: PERMANENT (requires human intervention).
    """
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, category=ErrorCategory.PERMANENT, **kwargs)


class PipelineConfigurationError(IngestionError):
    """Invalid pipeline configuration or missing dependencies.

    Raised during create_pipeline() or startup() for config errors.
    Default category: CONFIGURATION (fix config, don't retry).
    """
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, category=ErrorCategory.CONFIGURATION, **kwargs)
```

## Existing Entities (Unchanged — from floe-core)

These entities are defined in `packages/floe-core/src/floe_core/plugins/ingestion.py` and are NOT modified by Epic 4F.

### IngestionConfig (dataclass)

```python
@dataclass
class IngestionConfig:
    """Pipeline configuration — parameter for create_pipeline()."""
    source_type: str
    source_config: dict[str, Any] = field(default_factory=lambda: {})
    destination_table: str = ""
    write_mode: str = "append"
    schema_contract: str = "evolve"
```

### IngestionResult (dataclass)

```python
@dataclass
class IngestionResult:
    """Pipeline execution result — return type for run()."""
    success: bool
    rows_loaded: int = 0
    bytes_written: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=lambda: [])
```

## Relationships

```
DltIngestionConfig
  ├── sources: list[IngestionSourceConfig]  (1:N, required, min 1)
  ├── catalog_config: dict                  (1:1, required)
  └── retry_config: RetryConfig | None      (1:0..1, optional)

IngestionSourceConfig
  ├── maps to → IngestionConfig              (1:1, conversion in create_pipeline)
  └── maps to → dlt.pipeline + dlt.source   (1:1, runtime)

DltIngestionPlugin
  ├── config: DltIngestionConfig             (1:1, constructor param)
  ├── create_pipeline(IngestionConfig) → dlt pipeline object
  ├── run(pipeline) → IngestionResult
  └── get_destination_config(dict) → dict

ErrorCategory enum
  └── used by → IngestionError.category      (1:1)
  └── used by → categorize_error() → retry decision
```

## Validation Rules

### Config Validation
1. `sources` must have at least 1 element
2. `source_type` must be one of: `rest_api`, `sql_database`, `filesystem`
3. `write_mode` must be one of: `append`, `replace`, `merge`
4. `schema_contract` must be one of: `evolve`, `freeze`, `discard_value`
5. `primary_key` should be provided when `write_mode="merge"` (warning if missing)
6. `cursor_field` enables incremental loading when provided
7. `name` must be unique within the `sources` list

### Error Validation
1. All errors carry context: `source_type`, `destination_table`, `pipeline_name`
2. `SchemaContractViolation` always has `category=PERMANENT`
3. `PipelineConfigurationError` always has `category=CONFIGURATION`

### Retry Rules
1. `max_retries=0` disables retry entirely
2. Only `TRANSIENT` and `PARTIAL` errors are retried
3. `PERMANENT` and `CONFIGURATION` errors fail immediately
4. Backoff: `initial_delay * 2^attempt` (exponential via tenacity)

## JSON Schema Export

All Pydantic models export JSON Schema for IDE autocomplete:

```bash
# Generate schemas
python -c "from floe_ingestion_dlt.config import DltIngestionConfig; print(DltIngestionConfig.model_json_schema())"
```

Schema files stored in `specs/4f-ingestion-plugin/contracts/schemas/`.
