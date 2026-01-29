"""Event builder and conversion utilities for OpenLineage integration.

This module provides high-level utilities for constructing and converting
LineageEvent instances. The EventBuilder class simplifies event creation
with sensible defaults, while to_openlineage_event() converts events to
the OpenLineage wire format.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
    - OpenLineage spec: https://openlineage.io/docs/spec/
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from floe_core.lineage.types import (
    LineageDataset,
    LineageEvent,
    LineageJob,
    LineageRun,
    RunState,
)


class EventBuilder:
    """Builder for constructing LineageEvent instances.

    Provides convenience methods for creating START, COMPLETE, and FAIL events
    with sensible defaults. Handles run_id generation and namespace resolution.

    Attributes:
        producer: Producer identifier (e.g., "floe", "floe-dagster")
        default_namespace: Default namespace for jobs when not specified

    Example:
        >>> builder = EventBuilder(producer="floe", default_namespace="production")
        >>> start_event = builder.start_run(
        ...     job_name="dbt_run_customers",
        ...     inputs=[LineageDataset(namespace="raw", name="customers")],
        ...     outputs=[LineageDataset(namespace="staging", name="stg_customers")],
        ... )
        >>> complete_event = builder.complete_run(
        ...     run_id=start_event.run.run_id,
        ...     job_name="dbt_run_customers",
        ... )
    """

    def __init__(self, producer: str = "floe", default_namespace: str = "default") -> None:
        """Initialize the event builder.

        Args:
            producer: Producer identifier (default: "floe")
            default_namespace: Default namespace for jobs (default: "default")
        """
        self.producer = producer
        self.default_namespace = default_namespace

    def start_run(
        self,
        job_name: str,
        job_namespace: str | None = None,
        run_id: UUID | None = None,
        inputs: list[LineageDataset] | None = None,
        outputs: list[LineageDataset] | None = None,
        run_facets: dict[str, Any] | None = None,
        job_facets: dict[str, Any] | None = None,
    ) -> LineageEvent:
        """Create a START event for a job run.

        Args:
            job_name: Name of the job
            job_namespace: Namespace of the job (uses default_namespace if None)
            run_id: Unique run identifier (auto-generated if None)
            inputs: Input datasets for this run
            outputs: Output datasets for this run
            run_facets: Additional run metadata as OpenLineage facets
            job_facets: Additional job metadata as OpenLineage facets

        Returns:
            LineageEvent with RunState.START
        """
        namespace = job_namespace if job_namespace is not None else self.default_namespace
        rid = run_id if run_id is not None else uuid4()

        return LineageEvent(
            event_type=RunState.START,
            run=LineageRun(run_id=rid, facets=run_facets or {}),
            job=LineageJob(namespace=namespace, name=job_name, facets=job_facets or {}),
            inputs=inputs or [],
            outputs=outputs or [],
            producer=self.producer,
        )

    def complete_run(
        self,
        run_id: UUID,
        job_name: str,
        job_namespace: str | None = None,
        inputs: list[LineageDataset] | None = None,
        outputs: list[LineageDataset] | None = None,
        run_facets: dict[str, Any] | None = None,
        job_facets: dict[str, Any] | None = None,
    ) -> LineageEvent:
        """Create a COMPLETE event for a job run.

        Args:
            run_id: Unique run identifier (must match START event)
            job_name: Name of the job
            job_namespace: Namespace of the job (uses default_namespace if None)
            inputs: Input datasets for this run
            outputs: Output datasets for this run
            run_facets: Additional run metadata as OpenLineage facets
            job_facets: Additional job metadata as OpenLineage facets

        Returns:
            LineageEvent with RunState.COMPLETE
        """
        namespace = job_namespace if job_namespace is not None else self.default_namespace

        return LineageEvent(
            event_type=RunState.COMPLETE,
            run=LineageRun(run_id=run_id, facets=run_facets or {}),
            job=LineageJob(namespace=namespace, name=job_name, facets=job_facets or {}),
            inputs=inputs or [],
            outputs=outputs or [],
            producer=self.producer,
        )

    def fail_run(
        self,
        run_id: UUID,
        job_name: str,
        error_message: str | None = None,
        job_namespace: str | None = None,
        run_facets: dict[str, Any] | None = None,
    ) -> LineageEvent:
        """Create a FAIL event for a job run.

        Args:
            run_id: Unique run identifier (must match START event)
            job_name: Name of the job
            error_message: Error message to include in ErrorMessageRunFacet
            job_namespace: Namespace of the job (uses default_namespace if None)
            run_facets: Additional run metadata as OpenLineage facets

        Returns:
            LineageEvent with RunState.FAIL
        """
        namespace = job_namespace if job_namespace is not None else self.default_namespace
        facets = run_facets.copy() if run_facets else {}

        # Add ErrorMessageRunFacet if error_message provided
        if error_message is not None:
            facets["errorMessage"] = {
                "_producer": self.producer,
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ErrorMessageRunFacet.json",
                "message": error_message,
                "programmingLanguage": "python",
            }

        return LineageEvent(
            event_type=RunState.FAIL,
            run=LineageRun(run_id=run_id, facets=facets),
            job=LineageJob(namespace=namespace, name=job_name, facets={}),
            inputs=[],
            outputs=[],
            producer=self.producer,
        )


def to_openlineage_event(event: LineageEvent) -> dict[str, Any]:
    """Convert a LineageEvent to OpenLineage wire format.

    Transforms a LineageEvent instance into the JSON-serializable dictionary
    format expected by OpenLineage backends (Marquez, Atlan, etc.).

    Args:
        event: The LineageEvent to convert

    Returns:
        Dictionary in OpenLineage wire format with keys:
        - eventType: Event type as string (e.g., "START")
        - eventTime: ISO 8601 timestamp with Z suffix
        - run: Run object with runId and facets
        - job: Job object with namespace, name, and facets
        - inputs: List of input dataset objects
        - outputs: List of output dataset objects
        - producer: Producer identifier

    Example:
        >>> event = LineageEvent(
        ...     event_type=RunState.START,
        ...     job=LineageJob(namespace="floe", name="test_job"),
        ... )
        >>> wire_format = to_openlineage_event(event)
        >>> wire_format["eventType"]
        'START'
        >>> "eventTime" in wire_format
        True
    """
    return {
        "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json",
        "eventType": event.event_type.value,
        "eventTime": event.event_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "run": {
            "runId": str(event.run.run_id),
            "facets": event.run.facets,
        },
        "job": {
            "namespace": event.job.namespace,
            "name": event.job.name,
            "facets": event.job.facets,
        },
        "inputs": [
            {
                "namespace": d.namespace,
                "name": d.name,
                "facets": d.facets,
            }
            for d in event.inputs
        ],
        "outputs": [
            {
                "namespace": d.namespace,
                "name": d.name,
                "facets": d.facets,
            }
            for d in event.outputs
        ],
        "producer": event.producer,
    }
