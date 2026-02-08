"""Protocols for lineage integration.

These protocols define the interfaces that lineage backends and extractors
must implement. They enable pluggable lineage backends (Marquez, Atlan, etc.)
and custom lineage extraction logic.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from floe_core.lineage.types import LineageDataset, LineageEvent


@runtime_checkable
class LineageTransport(Protocol):
    """Protocol for lineage event transport.

    Implementations emit lineage events to backends (Marquez, Atlan, etc.).
    This protocol abstracts over the OpenLineage SDK's transport layer.

    Example:
        >>> class HttpTransport:
        ...     async def emit(self, event: LineageEvent) -> None:
        ...         # Send event to HTTP endpoint
        ...         pass
        ...     def close(self) -> None:
        ...         # Clean up resources
        ...         pass
    """

    async def emit(self, event: LineageEvent) -> None:
        """Emit a lineage event to the backend.

        Args:
            event: The lineage event to emit
        """
        ...

    def close(self) -> None:
        """Close the transport and clean up resources."""
        ...


@runtime_checkable
class LineageExtractor(Protocol):
    """Protocol for lineage extraction.

    Implementations extract lineage information from execution contexts
    (e.g., Dagster asset context, Airflow task context).

    Example:
        >>> class DagsterExtractor:
        ...     def extract(self, context: Any) -> tuple[list, list]:
        ...         # Extract inputs and outputs from Dagster context
        ...         inputs = [LineageDataset(namespace="prod", name="input_table")]
        ...         outputs = [LineageDataset(namespace="prod", name="output_table")]
        ...         return (inputs, outputs)
    """

    def extract(
        self, context: Any
    ) -> tuple[list[LineageDataset], list[LineageDataset]]:
        """Extract lineage information from execution context.

        Args:
            context: Execution context (e.g., Dagster AssetExecutionContext)

        Returns:
            Tuple of (inputs, outputs) as LineageDataset lists
        """
        ...
