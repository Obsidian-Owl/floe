"""MetricRecorder: OpenTelemetry metrics abstraction.

This module provides the MetricRecorder class for recording metrics
(counters, gauges, histograms) with OpenTelemetry.

Contract Version: 1.0.0

Requirements Covered:
- FR-012: Record pipeline run duration as histogram metric
- FR-013: Record asset materialization counts as counter metric
- FR-014: Record error rates by component as counter metric

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from opentelemetry import metrics

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter as CounterType
    from opentelemetry.metrics import Meter


class MetricRecorder:
    """OpenTelemetry metrics recorder.

    Provides a simplified interface for recording metrics with OpenTelemetry.
    Handles counter, gauge, and histogram instrument creation and caching.

    Attributes:
        meter: The OpenTelemetry Meter instance.

    Examples:
        >>> recorder = MetricRecorder()
        >>> recorder.increment("requests_total", labels={"method": "GET"})
        >>> recorder.increment("errors", value=2, labels={"type": "validation"})

    See Also:
        - FR-013: Asset materialization counting
        - FR-014: Error rate tracking
    """

    def __init__(
        self,
        name: str = "floe.telemetry",
        version: str = "1.0.0",
    ) -> None:
        """Initialize MetricRecorder.

        Args:
            name: The name of the meter (identifies the instrumentation library).
            version: The version of the meter.
        """
        self._meter: Meter = metrics.get_meter(name, version)
        self._counters: dict[str, CounterType] = {}

    def increment(
        self,
        name: str,
        value: int = 1,
        *,
        labels: dict[str, Any] | None = None,
        description: str | None = None,
        unit: str | None = None,
    ) -> None:
        """Increment a counter metric.

        Creates or reuses a counter with the specified name and adds the value.
        Counters are monotonically increasing metrics, suitable for counting
        events like requests, errors, or asset materializations.

        Args:
            name: The name of the counter metric.
            value: The value to add (must be positive). Defaults to 1.
            labels: Optional dictionary of attribute key-value pairs.
            description: Optional description for the counter.
            unit: Optional unit for the counter (e.g., "1" for counts).

        Examples:
            >>> recorder.increment("asset_materializations", labels={"status": "success"})
            >>> recorder.increment("errors", value=5, labels={"component": "compiler"})
        """
        counter = self._get_or_create_counter(
            name,
            description=description,
            unit=unit,
        )

        attributes: dict[str, Any] = labels if labels is not None else {}
        counter.add(value, attributes=attributes)

    def _get_or_create_counter(
        self,
        name: str,
        *,
        description: str | None = None,
        unit: str | None = None,
    ) -> CounterType:
        """Get or create a counter by name.

        Caches counters to avoid recreating them on every increment call.

        Args:
            name: The name of the counter.
            description: Optional description.
            unit: Optional unit.

        Returns:
            The Counter instrument.
        """
        if name not in self._counters:
            kwargs: dict[str, str] = {}
            if description is not None:
                kwargs["description"] = description
            if unit is not None:
                kwargs["unit"] = unit

            self._counters[name] = self._meter.create_counter(name, **kwargs)

        return self._counters[name]


__all__ = [
    "MetricRecorder",
]
