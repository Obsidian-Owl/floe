"""Lineage event emitter for orchestrating event emission.

Provides LineageEmitter class that coordinates EventBuilder and LineageTransport
to emit OpenLineage events, plus a create_emitter() factory function.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from floe_core.lineage.events import EventBuilder
from floe_core.lineage.protocols import LineageTransport
from floe_core.lineage.transport import (
    ConsoleLineageTransport,
    HttpLineageTransport,
    NoOpLineageTransport,
)
from floe_core.lineage.types import LineageDataset


class LineageEmitter:
    """High-level emitter that coordinates event building and transport.

    Combines an EventBuilder (for constructing LineageEvent instances) with
    a LineageTransport (for delivering them to a backend). Provides async
    methods for the standard run lifecycle: start, complete, fail.

    Attributes:
        transport: The transport used for event delivery.
        event_builder: The builder used for event construction.
        default_namespace: Default namespace for jobs.

    Example:
        >>> emitter = LineageEmitter(transport, EventBuilder(), "production")
        >>> run_id = await emitter.emit_start("my_job")
        >>> await emitter.emit_complete(run_id, "my_job")
    """

    def __init__(
        self,
        transport: LineageTransport,
        event_builder: EventBuilder,
        default_namespace: str = "default",
    ) -> None:
        """Initialize the emitter.

        Args:
            transport: Transport for delivering lineage events.
            event_builder: Builder for constructing lineage events.
            default_namespace: Default namespace for jobs.
        """
        self.transport = transport
        self.event_builder = event_builder
        self.default_namespace = default_namespace

    async def emit_start(
        self,
        job_name: str,
        run_id: UUID | None = None,
        inputs: list[LineageDataset] | None = None,
        outputs: list[LineageDataset] | None = None,
        run_facets: dict[str, Any] | None = None,
        job_facets: dict[str, Any] | None = None,
    ) -> UUID:
        """Emit a START event for a job run.

        Args:
            job_name: Name of the job.
            run_id: Unique run identifier (auto-generated if None).
            inputs: Input datasets for this run.
            outputs: Output datasets for this run.
            run_facets: Additional run metadata as OpenLineage facets.
            job_facets: Additional job metadata as OpenLineage facets.

        Returns:
            The run_id for this run (generated or provided).
        """
        event = self.event_builder.start_run(
            job_name=job_name,
            run_id=run_id,
            inputs=inputs,
            outputs=outputs,
            run_facets=run_facets,
            job_facets=job_facets,
        )
        await self.transport.emit(event)
        return event.run.run_id

    async def emit_complete(
        self,
        run_id: UUID,
        job_name: str,
        outputs: list[LineageDataset] | None = None,
        run_facets: dict[str, Any] | None = None,
        job_facets: dict[str, Any] | None = None,
    ) -> None:
        """Emit a COMPLETE event for a job run.

        Args:
            run_id: Unique run identifier (must match START event).
            job_name: Name of the job.
            outputs: Output datasets for this run.
            run_facets: Additional run metadata as OpenLineage facets.
            job_facets: Additional job metadata as OpenLineage facets.
        """
        event = self.event_builder.complete_run(
            run_id=run_id,
            job_name=job_name,
            outputs=outputs,
            run_facets=run_facets,
            job_facets=job_facets,
        )
        await self.transport.emit(event)

    async def emit_fail(
        self,
        run_id: UUID,
        job_name: str,
        error_message: str | None = None,
        run_facets: dict[str, Any] | None = None,
    ) -> None:
        """Emit a FAIL event for a job run.

        Args:
            run_id: Unique run identifier (must match START event).
            job_name: Name of the job.
            error_message: Error message to include in ErrorMessageRunFacet.
            run_facets: Additional run metadata as OpenLineage facets.
        """
        event = self.event_builder.fail_run(
            run_id=run_id,
            job_name=job_name,
            error_message=error_message,
            run_facets=run_facets,
        )
        await self.transport.emit(event)

    def close(self) -> None:
        """Close the underlying transport and release resources."""
        self.transport.close()


def create_emitter(
    transport_config: dict[str, Any] | None = None,
    default_namespace: str = "default",
    producer: str = "floe",
) -> LineageEmitter:
    """Factory function to create a LineageEmitter from configuration.

    Creates the appropriate transport based on the config ``type`` field,
    an EventBuilder, and wires them into a LineageEmitter.

    Args:
        transport_config: Transport configuration dict. Supported types:
            - ``{"type": "http", "url": "...", "timeout": 5.0, "api_key": "..."}``
            - ``{"type": "console"}``
            - ``None`` or ``{"type": None}`` → NoOp transport
        default_namespace: Default namespace for jobs.
        producer: Producer identifier for events.

    Returns:
        Configured LineageEmitter instance.

    Example:
        >>> emitter = create_emitter({"type": "console"}, default_namespace="prod")
        >>> run_id = await emitter.emit_start("my_job")
    """
    transport: LineageTransport

    if transport_config is None or transport_config.get("type") is None:
        transport = NoOpLineageTransport()
    elif transport_config["type"] == "http":
        transport = HttpLineageTransport(
            url=transport_config["url"],
            timeout=transport_config.get("timeout", 5.0),
            api_key=transport_config.get("api_key"),
        )
    elif transport_config["type"] == "console":
        transport = ConsoleLineageTransport()
    else:
        transport = NoOpLineageTransport()

    event_builder = EventBuilder(producer=producer, default_namespace=default_namespace)
    return LineageEmitter(transport, event_builder, default_namespace)
