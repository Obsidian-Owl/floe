"""Core lineage types for OpenLineage integration.

These types provide floe's portable abstraction over the OpenLineage SDK.
They are frozen, validated Pydantic models that enforce immutability and
strict validation.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
    - OpenLineage spec: https://openlineage.io/docs/spec/
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    """Return current UTC time with timezone info (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


class RunState(str, Enum):
    """OpenLineage run state values.

    These match the OpenLineage specification exactly.
    See: https://openlineage.io/docs/spec/run-state/

    Attributes:
        START: Run has started
        RUNNING: Run is in progress
        COMPLETE: Run completed successfully
        ABORT: Run was aborted
        FAIL: Run failed
        OTHER: Other state (use sparingly)
    """

    START = "START"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    ABORT = "ABORT"
    FAIL = "FAIL"
    OTHER = "OTHER"


class LineageDataset(BaseModel):
    """A dataset in the lineage graph.

    Represents an input or output dataset for a job run.
    Datasets are identified by namespace + name.

    Attributes:
        namespace: Dataset namespace (e.g., "prod", "staging")
        name: Dataset name (e.g., "db.schema.table")
        facets: Additional metadata as OpenLineage facets
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(
        ...,
        min_length=1,
        description="Dataset namespace (e.g., 'prod', 'staging')",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Dataset name (e.g., 'db.schema.table')",
    )
    facets: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata as OpenLineage facets",
    )


class LineageRun(BaseModel):
    """A run instance in the lineage graph.

    Represents a single execution of a job.
    Each run has a unique ID.

    Attributes:
        run_id: Unique identifier for this run
        facets: Additional metadata as OpenLineage facets
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this run",
    )
    facets: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata as OpenLineage facets",
    )


class LineageJob(BaseModel):
    """A job in the lineage graph.

    Represents a data processing job (e.g., dbt model, Dagster asset).
    Jobs are identified by namespace + name.

    Attributes:
        namespace: Job namespace (e.g., "floe", "airflow")
        name: Job name (e.g., "dbt_run_customers")
        facets: Additional metadata as OpenLineage facets
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(
        ...,
        min_length=1,
        description="Job namespace (e.g., 'floe', 'airflow')",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Job name (e.g., 'dbt_run_customers')",
    )
    facets: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata as OpenLineage facets",
    )


class LineageEvent(BaseModel):
    """An OpenLineage event.

    Represents a state transition in a job run.
    Events are emitted to lineage backends (Marquez, Atlan, etc.).

    Attributes:
        event_type: Type of event (START, COMPLETE, FAIL, etc.)
        event_time: Timestamp of the event
        run: Run instance
        job: Job being executed
        inputs: Input datasets
        outputs: Output datasets
        producer: Producer identifier (default: "floe")
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: RunState = Field(
        ...,
        description="Type of event (START, COMPLETE, FAIL, etc.)",
    )
    event_time: datetime = Field(
        default_factory=_utc_now,
        description="Timestamp of the event (UTC with timezone)",
    )
    run: LineageRun = Field(
        default_factory=LineageRun,
        description="Run instance",
    )
    job: LineageJob = Field(
        ...,
        description="Job being executed",
    )
    inputs: list[LineageDataset] = Field(
        default_factory=list,
        description="Input datasets",
    )
    outputs: list[LineageDataset] = Field(
        default_factory=list,
        description="Output datasets",
    )
    producer: str = Field(
        default="floe",
        min_length=1,
        description="Producer identifier (default: 'floe')",
    )
