"""Custom metric definitions for contract monitoring.

This module provides custom metrics support, allowing users to define and record
application-specific metrics beyond the built-in contract monitoring metrics.

Tasks: T079 (Epic 3D)
Requirements: 3D-FR-046
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)


class CustomMetricDefinition(BaseModel):
    """Definition of a custom metric for contract monitoring.

    Custom metrics allow tracking of application-specific measurements beyond
    the built-in freshness, schema drift, quality, and availability checks.

    Attributes:
        name: Unique name of the metric (e.g., "ingestion_rate").
        description: Human-readable description of what the metric measures.
        unit: Unit of measurement (e.g., "count", "seconds", "percent", "records/sec").
        labels: List of label key names for dimensional metrics (e.g., ["pipeline_name", "environment"]).

    Example:
        >>> metric = CustomMetricDefinition(
        ...     name="rows_processed",
        ...     description="Total rows processed per batch",
        ...     unit="count",
        ...     labels=["pipeline_name"],
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str
    unit: str
    labels: list[str] = Field(default_factory=list)


class MetricRecorder:
    """Records custom metric values with timestamps and labels.

    The MetricRecorder maintains a registry of custom metric definitions and
    stores emitted metric values for later aggregation and analysis.

    Example:
        >>> recorder = MetricRecorder()
        >>> metric_def = CustomMetricDefinition(
        ...     name="processing_time",
        ...     description="Time to process batch",
        ...     unit="seconds",
        ... )
        >>> recorder.register(metric_def)
        >>> recorder.emit("processing_time", 5.25)
        >>> recordings = recorder.get_recordings("processing_time")
    """

    def __init__(self) -> None:
        """Initialize the metric recorder."""
        self._metrics: dict[str, CustomMetricDefinition] = {}
        self._recordings: dict[str, list[dict[str, Any]]] = {}
        self._log = logger.bind(component="metric_recorder")

    def register(self, definition: CustomMetricDefinition) -> None:
        """Register a custom metric definition.

        Args:
            definition: The metric definition to register.

        Raises:
            ValueError: If a metric with this name is already registered.
        """
        if definition.name in self._metrics:
            msg = f"Metric '{definition.name}' is already registered"
            raise ValueError(msg)

        self._metrics[definition.name] = definition
        self._recordings[definition.name] = []

        self._log.info(
            "metric_registered",
            metric_name=definition.name,
            unit=definition.unit,
            labels=definition.labels,
        )

    def emit(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Emit a value for a registered metric.

        Args:
            name: Name of the metric to emit.
            value: The measured value.
            labels: Optional label key-value pairs for dimensional metrics.

        Raises:
            KeyError: If the metric is not registered.
        """
        if name not in self._metrics:
            msg = f"Metric '{name}' is not registered"
            raise KeyError(msg)

        recording = {
            "value": value,
            "labels": labels if labels is not None else {},
            "timestamp": datetime.now(tz=timezone.utc),
        }

        self._recordings[name].append(recording)

        self._log.debug(
            "metric_emitted",
            metric_name=name,
            value=value,
            labels=labels if labels is not None else {},
        )

    def get_registered(self) -> list[CustomMetricDefinition]:
        """Get all registered metric definitions.

        Returns:
            List of all registered CustomMetricDefinition instances.
        """
        return list(self._metrics.values())

    def get_recordings(self, name: str) -> list[dict[str, Any]]:
        """Get all recordings for a metric.

        Args:
            name: Name of the metric to retrieve recordings for.

        Returns:
            List of recordings, each containing: {"value": float, "labels": dict, "timestamp": datetime}.

        Raises:
            KeyError: If the metric is not registered.
        """
        if name not in self._metrics:
            msg = f"Metric '{name}' is not registered"
            raise KeyError(msg)

        return list(self._recordings[name])
