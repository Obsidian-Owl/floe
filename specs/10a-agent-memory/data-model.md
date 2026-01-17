# Data Model: Agent Memory (Cognee Integration)

**Feature**: Epic 10A - Agent Memory
**Date**: 2026-01-14
**Status**: Design Complete

---

## Overview

This document defines the data entities for the Agent Memory system. Entities are organized into three categories:
1. **Configuration** - Settings and credentials
2. **State Management** - Sync tracking and checkpoints
3. **Query Results** - Search responses and context

All entities use Pydantic v2 models with `ConfigDict(frozen=True, extra="forbid")` for immutability and strict validation.

---

## Entity Definitions

### 1. Configuration Entities

#### AgentMemoryConfig

**Purpose**: Root configuration for the agent-memory system.

```python
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from typing import Literal

class AgentMemoryConfig(BaseModel):
    """Configuration for agent-memory system."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Cognee Cloud settings
    cognee_api_url: str = Field(
        default="https://api.cognee.ai",
        description="Cognee Cloud API endpoint"
    )
    cognee_api_key: SecretStr = Field(
        ...,
        description="Cognee Cloud API key (from environment)"
    )

    # LLM settings (for cognify)
    llm_provider: Literal["openai", "anthropic"] = Field(
        default="openai",
        description="LLM provider for entity extraction"
    )
    llm_api_key: SecretStr = Field(
        ...,
        description="LLM API key (from environment)"
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model for cognify operations"
    )

    # Dataset naming
    architecture_dataset: str = Field(
        default="architecture",
        description="Dataset name for architecture docs"
    )
    governance_dataset: str = Field(
        default="governance",
        description="Dataset name for constitution/rules"
    )
    codebase_dataset: str = Field(
        default="codebase",
        description="Dataset name for docstrings"
    )
    skills_dataset: str = Field(
        default="skills",
        description="Dataset name for Claude skills"
    )

    # Operational settings
    batch_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per batch for cognify"
    )
    search_top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Default number of search results"
    )
```

**Relationships**:
- Used by `CogneeClient` for API authentication
- Used by `CogneeSync` for dataset naming

**Validation Rules**:
- `cognee_api_key` and `llm_api_key` must be non-empty SecretStr
- `batch_size` between 1 and 100
- `search_top_k` between 1 and 50

---

#### ContentSource

**Purpose**: Defines a source of content to be indexed.

```python
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from uuid import UUID

class ContentSource(BaseModel):
    """A source of content to be indexed."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: Literal["directory", "file", "glob"] = Field(
        ...,
        description="Type of content source"
    )
    path: Path = Field(
        ...,
        description="Path or glob pattern"
    )
    dataset: str = Field(
        ...,
        description="Target dataset name"
    )
    file_extensions: list[str] = Field(
        default=[".md", ".py"],
        description="File extensions to include"
    )
    exclude_patterns: list[str] = Field(
        default=[],
        description="Glob patterns to exclude"
    )
```

**Relationships**:
- Multiple `ContentSource` entries define what to index
- Each maps to a Cognee dataset

**State Transitions**: N/A (immutable configuration)

---

### 2. State Management Entities

#### SyncState

**Purpose**: Tracks overall sync state for the knowledge graph.

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from uuid import UUID

class SyncState(BaseModel):
    """Tracks sync state for the knowledge graph."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    last_sync_timestamp: datetime | None = Field(
        default=None,
        description="When last sync completed"
    )
    last_sync_status: Literal["success", "partial", "failed"] | None = Field(
        default=None,
        description="Status of last sync"
    )
    indexed_file_count: int = Field(
        default=0,
        ge=0,
        description="Number of files currently indexed"
    )
    pending_file_count: int = Field(
        default=0,
        ge=0,
        description="Number of files awaiting sync"
    )
    datasets: dict[str, DatasetState] = Field(
        default_factory=dict,
        description="State per dataset"
    )
```

**Relationships**:
- Contains multiple `DatasetState` entries
- Updated by `CogneeSync` after operations

**State Transitions**:
```
initial → syncing → success
                  → partial (some files failed)
                  → failed (all files failed)
```

---

#### DatasetState

**Purpose**: Tracks state for a specific Cognee dataset.

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class DatasetState(BaseModel):
    """State for a specific dataset."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_name: str = Field(
        ...,
        description="Dataset name in Cognee"
    )
    dataset_id: UUID | None = Field(
        default=None,
        description="Cognee dataset UUID"
    )
    last_cognify_timestamp: datetime | None = Field(
        default=None,
        description="When cognify last completed"
    )
    pipeline_status: Literal[
        "not_started",
        "initiated",
        "processing",
        "completed",
        "errored"
    ] = Field(
        default="not_started",
        description="Current pipeline status"
    )
    item_count: int = Field(
        default=0,
        ge=0,
        description="Number of items in dataset"
    )
```

**State Transitions**:
```
not_started → initiated → processing → completed
                                     → errored
```

---

#### FileChecksum

**Purpose**: Tracks content hash for drift detection.

```python
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

class FileChecksum(BaseModel):
    """Content hash for drift detection."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: Path = Field(
        ...,
        description="Relative path from repo root"
    )
    content_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of file content"
    )
    last_indexed: datetime = Field(
        ...,
        description="When file was last indexed"
    )
    dataset: str = Field(
        ...,
        description="Dataset file was indexed to"
    )
```

**Relationships**:
- Stored in `.cognee/checksums.json`
- Used by `drift.py` to detect changes

---

#### BatchCheckpoint

**Purpose**: Resume point for batch operations.

```python
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class BatchCheckpoint(BaseModel):
    """Resume point for batch operations."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: UUID = Field(
        ...,
        description="Unique operation identifier"
    )
    operation_type: Literal["init", "sync", "rebuild"] = Field(
        ...,
        description="Type of batch operation"
    )
    started_at: datetime = Field(
        ...,
        description="When operation started"
    )
    total_items: int = Field(
        ...,
        ge=0,
        description="Total items to process"
    )
    completed_items: int = Field(
        default=0,
        ge=0,
        description="Items successfully processed"
    )
    failed_items: list[Path] = Field(
        default_factory=list,
        description="Items that failed processing"
    )
    last_processed: Path | None = Field(
        default=None,
        description="Last successfully processed item"
    )
```

**State Transitions**:
```
created → processing → completed
                     → interrupted (can resume)
                     → failed (too many errors)
```

---

### 3. Query Result Entities

#### SearchResult

**Purpose**: Result from a knowledge graph search.

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

class SearchResult(BaseModel):
    """Result from knowledge graph search."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(
        ...,
        description="Original search query"
    )
    search_type: str = Field(
        ...,
        description="Search type used (GRAPH_COMPLETION, etc.)"
    )
    results: list[SearchResultItem] = Field(
        default_factory=list,
        description="Ordered list of results"
    )
    total_count: int = Field(
        default=0,
        ge=0,
        description="Total matching items"
    )
    execution_time_ms: int = Field(
        default=0,
        ge=0,
        description="Query execution time in milliseconds"
    )

class SearchResultItem(BaseModel):
    """Individual search result item."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str = Field(
        ...,
        description="Retrieved content"
    )
    source_path: str | None = Field(
        default=None,
        description="Source file path if available"
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relevance score (0-1)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
```

---

#### SessionContext

**Purpose**: Captured context for session recovery.

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

class SessionContext(BaseModel):
    """Captured context for session recovery."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: UUID = Field(
        ...,
        description="Unique session identifier"
    )
    captured_at: datetime = Field(
        ...,
        description="When context was captured"
    )
    active_work_areas: list[str] = Field(
        default_factory=list,
        description="Files/areas being worked on"
    )
    recent_decisions: list[DecisionRecord] = Field(
        default_factory=list,
        description="Recent architectural decisions"
    )
    related_closed_tasks: list[str] = Field(
        default_factory=list,
        description="Related completed work"
    )
    conversation_summary: str | None = Field(
        default=None,
        description="Summary of session conversation"
    )

class DecisionRecord(BaseModel):
    """Record of an architectural decision made during session."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: str = Field(
        ...,
        description="What was decided"
    )
    rationale: str = Field(
        ...,
        description="Why this decision was made"
    )
    alternatives_considered: list[str] = Field(
        default_factory=list,
        description="Other options evaluated"
    )
    timestamp: datetime = Field(
        ...,
        description="When decision was made"
    )
```

---

### 4. Operational Entities

#### HealthStatus

**Purpose**: System health check result.

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class HealthStatus(BaseModel):
    """System health check result."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Overall system status"
    )
    checked_at: datetime = Field(
        ...,
        description="When health check ran"
    )
    cognee_cloud: ComponentStatus = Field(
        ...,
        description="Cognee Cloud connection status"
    )
    llm_provider: ComponentStatus = Field(
        ...,
        description="LLM provider status"
    )
    local_state: ComponentStatus = Field(
        ...,
        description="Local state files status"
    )

class ComponentStatus(BaseModel):
    """Status of individual component."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Component status"
    )
    message: str = Field(
        default="",
        description="Status message or error"
    )
    response_time_ms: int | None = Field(
        default=None,
        ge=0,
        description="Response time in milliseconds"
    )
```

---

#### CoverageReport

**Purpose**: Report comparing indexed content to filesystem.

```python
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

class CoverageReport(BaseModel):
    """Coverage analysis comparing indexed to filesystem."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_filesystem_files: int = Field(
        ...,
        ge=0,
        description="Files found on filesystem"
    )
    total_indexed_files: int = Field(
        ...,
        ge=0,
        description="Files indexed in Cognee"
    )
    missing_files: list[Path] = Field(
        default_factory=list,
        description="Files on filesystem but not indexed"
    )
    orphaned_files: list[Path] = Field(
        default_factory=list,
        description="Files indexed but not on filesystem"
    )
    coverage_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of files indexed"
    )
```

---

#### DriftReport

**Purpose**: Report of stale/orphaned entries.

```python
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

class DriftReport(BaseModel):
    """Drift detection report."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    stale_entries: list[DriftEntry] = Field(
        default_factory=list,
        description="Entries with changed content"
    )
    orphaned_entries: list[DriftEntry] = Field(
        default_factory=list,
        description="Entries for deleted files"
    )
    renamed_candidates: list[RenamePair] = Field(
        default_factory=list,
        description="Possible renames (same hash, different path)"
    )

class DriftEntry(BaseModel):
    """Single drift entry."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: Path = Field(
        ...,
        description="Path of drifted file"
    )
    indexed_hash: str = Field(
        ...,
        description="Hash when indexed"
    )
    current_hash: str | None = Field(
        default=None,
        description="Current hash (None if deleted)"
    )
    dataset: str = Field(
        ...,
        description="Dataset containing entry"
    )

class RenamePair(BaseModel):
    """Possible rename detection."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    old_path: Path = Field(
        ...,
        description="Original indexed path"
    )
    new_path: Path = Field(
        ...,
        description="New path on filesystem"
    )
    content_hash: str = Field(
        ...,
        description="Matching content hash"
    )
```

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Configuration                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AgentMemoryConfig ──────┬──────► ContentSource[]                │
│         │                │                                       │
│         │                └──────► Dataset names                  │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │ CogneeClient │ (uses config for API auth)                    │
│  └──────────────┘                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      State Management                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SyncState ─────────────────► DatasetState[] (per dataset)       │
│      │                                                           │
│      ▼                                                           │
│  FileChecksum[] ──────────► .cognee/checksums.json               │
│      │                                                           │
│      ▼                                                           │
│  BatchCheckpoint ─────────► .cognee/checkpoints/{id}.json        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Query Results                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SearchResult ──────────────► SearchResultItem[]                 │
│                                                                  │
│  SessionContext ────────────► DecisionRecord[]                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Operational                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  HealthStatus ──────────────► ComponentStatus[] (per component)  │
│                                                                  │
│  CoverageReport ────────────► missing/orphaned paths             │
│                                                                  │
│  DriftReport ───────────────► DriftEntry[], RenamePair[]         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Storage Locations

| Entity | Storage | Format |
|--------|---------|--------|
| `AgentMemoryConfig` | Environment + `.cognee/config.yaml` | YAML |
| `SyncState` | `.cognee/state.json` | JSON |
| `FileChecksum[]` | `.cognee/checksums.json` | JSON dict by path |
| `BatchCheckpoint` | `.cognee/checkpoints/{id}.json` | JSON |
| `SearchResult` | In-memory (API response) | Pydantic model |
| `SessionContext` | Cognee Cloud (save_interaction) | Stored in graph |
| `HealthStatus` | In-memory (CLI output) | Pydantic model |
| `CoverageReport` | In-memory (CLI output) | Pydantic model |
| `DriftReport` | In-memory (CLI output) | Pydantic model |
