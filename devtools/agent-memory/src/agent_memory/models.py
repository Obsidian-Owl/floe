"""Data models for agent-memory state management and operations.

Provides Pydantic models for:
- State management: SyncState, DatasetState, FileChecksum, BatchCheckpoint
- Query results: SearchResult, SearchResultItem, SessionContext, DecisionRecord
- Operations: HealthStatus, ComponentStatus, CoverageReport, DriftReport
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# State Management Models
# =============================================================================


class DatasetState(BaseModel):
    """State for a specific Cognee dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_name: str = Field(
        ...,
        description="Dataset name in Cognee",
    )
    dataset_id: UUID | None = Field(
        default=None,
        description="Cognee dataset UUID",
    )
    last_cognify_timestamp: datetime | None = Field(
        default=None,
        description="When cognify last completed",
    )
    pipeline_status: Literal[
        "not_started",
        "initiated",
        "processing",
        "completed",
        "errored",
    ] = Field(
        default="not_started",
        description="Current pipeline status",
    )
    item_count: int = Field(
        default=0,
        ge=0,
        description="Number of items in dataset",
    )


class SyncState(BaseModel):
    """Tracks overall sync state for the knowledge graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    last_sync_timestamp: datetime | None = Field(
        default=None,
        description="When last sync completed",
    )
    last_sync_status: Literal["success", "partial", "failed"] | None = Field(
        default=None,
        description="Status of last sync",
    )
    indexed_file_count: int = Field(
        default=0,
        ge=0,
        description="Number of files currently indexed",
    )
    pending_file_count: int = Field(
        default=0,
        ge=0,
        description="Number of files awaiting sync",
    )
    datasets: dict[str, DatasetState] = Field(
        default_factory=dict,
        description="State per dataset",
    )


class FileChecksum(BaseModel):
    """Content hash for drift detection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: Path = Field(
        ...,
        description="Relative path from repo root",
    )
    content_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of file content",
    )
    last_indexed: datetime = Field(
        ...,
        description="When file was last indexed",
    )
    dataset: str = Field(
        ...,
        description="Dataset file was indexed to",
    )


class BatchCheckpoint(BaseModel):
    """Resume point for batch operations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation_id: UUID = Field(
        ...,
        description="Unique operation identifier",
    )
    operation_type: Literal["init", "sync", "rebuild"] = Field(
        ...,
        description="Type of batch operation",
    )
    started_at: datetime = Field(
        ...,
        description="When operation started",
    )
    total_items: int = Field(
        ...,
        ge=0,
        description="Total items to process",
    )
    completed_items: int = Field(
        default=0,
        ge=0,
        description="Items successfully processed",
    )
    failed_items: list[Path] = Field(
        default_factory=list,
        description="Items that failed processing",
    )
    last_processed: Path | None = Field(
        default=None,
        description="Last successfully processed item",
    )


# =============================================================================
# Query Result Models
# =============================================================================


class SearchResultItem(BaseModel):
    """Individual search result item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str = Field(
        ...,
        description="Retrieved content",
    )
    source_path: str | None = Field(
        default=None,
        description="Source file path if available",
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relevance score (0-1)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )


class SearchResult(BaseModel):
    """Result from knowledge graph search."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(
        ...,
        description="Original search query",
    )
    search_type: str = Field(
        ...,
        description="Search type used (GRAPH_COMPLETION, etc.)",
    )
    results: list[SearchResultItem] = Field(
        default_factory=list,
        description="Ordered list of results",
    )
    total_count: int = Field(
        default=0,
        ge=0,
        description="Total matching items",
    )
    execution_time_ms: int = Field(
        default=0,
        ge=0,
        description="Query execution time in milliseconds",
    )


class DecisionRecord(BaseModel):
    """Record of an architectural decision made during session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: str = Field(
        ...,
        description="What was decided",
    )
    rationale: str = Field(
        ...,
        description="Why this decision was made",
    )
    alternatives_considered: list[str] = Field(
        default_factory=list,
        description="Other options evaluated",
    )
    timestamp: datetime = Field(
        ...,
        description="When decision was made",
    )


class SessionContext(BaseModel):
    """Captured context for session recovery."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: UUID = Field(
        ...,
        description="Unique session identifier",
    )
    captured_at: datetime = Field(
        ...,
        description="When context was captured",
    )
    active_work_areas: list[str] = Field(
        default_factory=list,
        description="Files/areas being worked on",
    )
    recent_decisions: list[DecisionRecord] = Field(
        default_factory=list,
        description="Recent architectural decisions",
    )
    related_closed_tasks: list[str] = Field(
        default_factory=list,
        description="Related completed work",
    )
    conversation_summary: str | None = Field(
        default=None,
        description="Summary of session conversation",
    )


# =============================================================================
# Operational Models
# =============================================================================


class ComponentStatus(BaseModel):
    """Status of individual component."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Component status",
    )
    message: str = Field(
        default="",
        description="Status message or error",
    )
    response_time_ms: int | None = Field(
        default=None,
        ge=0,
        description="Response time in milliseconds",
    )


class HealthStatus(BaseModel):
    """System health check result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Overall system status",
    )
    checked_at: datetime = Field(
        ...,
        description="When health check ran",
    )
    cognee_cloud: ComponentStatus = Field(
        ...,
        description="Cognee Cloud connection status",
    )
    llm_provider: ComponentStatus = Field(
        ...,
        description="LLM provider status",
    )
    local_state: ComponentStatus = Field(
        ...,
        description="Local state files status",
    )


class CoverageReport(BaseModel):
    """Coverage analysis comparing indexed to filesystem."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_filesystem_files: int = Field(
        ...,
        ge=0,
        description="Files found on filesystem",
    )
    total_indexed_files: int = Field(
        ...,
        ge=0,
        description="Files indexed in Cognee",
    )
    missing_files: list[Path] = Field(
        default_factory=list,
        description="Files on filesystem but not indexed",
    )
    orphaned_files: list[Path] = Field(
        default_factory=list,
        description="Files indexed but not on filesystem",
    )
    coverage_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of files indexed",
    )


class DriftEntry(BaseModel):
    """Single drift entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: Path = Field(
        ...,
        description="Path of drifted file",
    )
    indexed_hash: str = Field(
        ...,
        description="Hash when indexed",
    )
    current_hash: str | None = Field(
        default=None,
        description="Current hash (None if deleted)",
    )
    dataset: str = Field(
        ...,
        description="Dataset containing entry",
    )


class RenamePair(BaseModel):
    """Possible rename detection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    old_path: Path = Field(
        ...,
        description="Original indexed path",
    )
    new_path: Path = Field(
        ...,
        description="New path on filesystem",
    )
    content_hash: str = Field(
        ...,
        description="Matching content hash",
    )


class DriftReport(BaseModel):
    """Drift detection report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stale_entries: list[DriftEntry] = Field(
        default_factory=list,
        description="Entries with changed content",
    )
    orphaned_entries: list[DriftEntry] = Field(
        default_factory=list,
        description="Entries for deleted files",
    )
    renamed_candidates: list[RenamePair] = Field(
        default_factory=list,
        description="Possible renames (same hash, different path)",
    )
