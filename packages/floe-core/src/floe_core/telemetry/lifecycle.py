"""Shared plugin lifecycle observability helpers."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.telemetry.context import clean_attribute_value, is_secret_attribute_key
from floe_core.telemetry.metrics import MetricRecorder
from floe_core.telemetry.tracing import create_span

if TYPE_CHECKING:
    from collections.abc import Generator

    from opentelemetry.trace import Span

PluginLifecycleAttributeValue = str | int | float | bool
LIFECYCLE_DURATION_METRIC = "floe.plugin.lifecycle.duration"
LIFECYCLE_FAILURES_METRIC = "floe.plugin.lifecycle.failures"

_FAILURE_STATUSES = frozenset(("failure", "error", "unhealthy", "degraded"))

logger = structlog.get_logger(__name__)


def plugin_lifecycle_attributes(
    *,
    plugin_type: str,
    plugin_name: str,
    plugin_version: str,
    floe_api_version: str,
    phase: str,
    status: str,
    error_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, PluginLifecycleAttributeValue]:
    """Return secret-free attributes for plugin lifecycle telemetry."""
    attrs: dict[str, PluginLifecycleAttributeValue] = {
        "floe.plugin.type": plugin_type,
        "floe.plugin.name": plugin_name,
        "floe.plugin.version": plugin_version,
        "floe.plugin.floe_api_version": floe_api_version,
        "floe.plugin.lifecycle.phase": phase,
        "floe.plugin.lifecycle.status": status,
    }
    if error_type is not None:
        attrs["floe.error.type"] = error_type
    if extra:
        attrs.update(
            {
                key: clean_attribute_value(value)
                for key, value in extra.items()
                if not is_secret_attribute_key(key)
            }
        )
    return attrs


def lifecycle_metric_labels(
    *,
    plugin_type: str,
    plugin_name: str,
    phase: str,
    status: str,
) -> dict[str, str]:
    """Return bounded-cardinality labels for plugin lifecycle metrics."""
    return {
        "floe.plugin.type": plugin_type,
        "floe.plugin.name": plugin_name,
        "floe.plugin.lifecycle.phase": phase,
        "floe.plugin.lifecycle.status": status,
    }


@dataclass
class PluginLifecycleObservation:
    """In-flight lifecycle observation for a single plugin operation."""

    plugin_type: str
    plugin_name: str
    plugin_version: str
    floe_api_version: str
    phase: str
    span: Span
    metrics: MetricRecorder
    started_at: float
    recorded: bool = False

    def finish(
        self,
        *,
        status: str,
        error_type: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Record final span attributes and lifecycle metrics once."""
        if self.recorded:
            return

        duration_seconds = time.perf_counter() - self.started_at
        attrs = plugin_lifecycle_attributes(
            plugin_type=self.plugin_type,
            plugin_name=self.plugin_name,
            plugin_version=self.plugin_version,
            floe_api_version=self.floe_api_version,
            phase=self.phase,
            status=status,
            error_type=error_type,
            extra=extra,
        )
        for key, value in attrs.items():
            self.span.set_attribute(key, value)

        logger.debug(
            "plugin_lifecycle.observed",
            **attrs,
            duration_seconds=duration_seconds,
        )

        labels = lifecycle_metric_labels(
            plugin_type=self.plugin_type,
            plugin_name=self.plugin_name,
            phase=self.phase,
            status=status,
        )
        self._record_duration(duration_seconds, labels)
        if error_type is not None or status in _FAILURE_STATUSES:
            self._record_failure(labels)

        self.recorded = True

    def _record_duration(
        self,
        duration_seconds: float,
        labels: dict[str, str],
    ) -> None:
        """Record lifecycle duration while keeping telemetry non-invasive."""
        try:
            self.metrics.record_histogram(
                LIFECYCLE_DURATION_METRIC,
                duration_seconds,
                labels=labels,
                description="Plugin lifecycle operation duration",
                unit="s",
            )
        except Exception as e:  # pragma: no cover - defensive telemetry isolation
            logger.debug("plugin_lifecycle.duration_metric_failed", error=str(e))

    def _record_failure(self, labels: dict[str, str]) -> None:
        """Record lifecycle failure while keeping telemetry non-invasive."""
        try:
            self.metrics.increment(
                LIFECYCLE_FAILURES_METRIC,
                labels=labels,
                description="Plugin lifecycle operation failures",
                unit="1",
            )
        except Exception as e:  # pragma: no cover - defensive telemetry isolation
            logger.debug("plugin_lifecycle.failure_metric_failed", error=str(e))


@contextmanager
def observe_plugin_lifecycle(
    *,
    plugin_type: str,
    plugin_name: str,
    plugin_version: str,
    floe_api_version: str,
    phase: str,
    status: str = "started",
    error_status: str = "failure",
    extra: dict[str, Any] | None = None,
    metrics: MetricRecorder | None = None,
) -> Generator[PluginLifecycleObservation, None, None]:
    """Observe a plugin lifecycle operation with span and metric emission."""
    metric_recorder = metrics or MetricRecorder(name="floe.plugin.lifecycle", version="1.0.0")
    with create_span(
        f"floe.plugin.lifecycle.{phase}",
        plugin_lifecycle_attributes(
            plugin_type=plugin_type,
            plugin_name=plugin_name,
            plugin_version=plugin_version,
            floe_api_version=floe_api_version,
            phase=phase,
            status=status,
            extra=extra,
        ),
    ) as span:
        observation = PluginLifecycleObservation(
            plugin_type=plugin_type,
            plugin_name=plugin_name,
            plugin_version=plugin_version,
            floe_api_version=floe_api_version,
            phase=phase,
            span=span,
            metrics=metric_recorder,
            started_at=time.perf_counter(),
        )
        try:
            yield observation
        except Exception as e:
            observation.finish(status=error_status, error_type=type(e).__name__)
            raise
        finally:
            if not observation.recorded:
                observation.finish(status="success")


__all__ = [
    "LIFECYCLE_DURATION_METRIC",
    "LIFECYCLE_FAILURES_METRIC",
    "PluginLifecycleAttributeValue",
    "PluginLifecycleObservation",
    "lifecycle_metric_labels",
    "observe_plugin_lifecycle",
    "plugin_lifecycle_attributes",
]
