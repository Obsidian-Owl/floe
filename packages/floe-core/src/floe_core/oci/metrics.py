"""OpenTelemetry metrics for OCI registry operations.

This module provides metrics instrumentation for OCI client operations including
push, pull, inspect, and list. Implements counters, histograms, and gauges per
the observability specification in research.md section 8.

Metrics Emitted:
    Counters:
        - floe_oci_operations_total: Total operations by type, status, and registry
        - floe_oci_cache_operations_total: Cache operations by type (hit/miss/evict)

    Histograms:
        - floe_oci_operation_duration_seconds: Operation duration distribution
        - floe_oci_artifact_size_bytes: Artifact size distribution

    Gauges:
        - floe_oci_circuit_breaker_state: Circuit breaker state (0=closed, 1=open, 2=half_open)
        - floe_oci_cache_size_bytes: Current cache size in bytes
        - floe_oci_cache_entries_count: Current number of cache entries

Trace Spans:
    - floe.oci.push: Full push operation
    - floe.oci.pull: Full pull operation
    - floe.oci.inspect: Metadata inspection
    - floe.oci.list: Tag listing
    - floe.oci.auth: Authentication step
    - floe.oci.upload_layer: Individual layer upload
    - floe.oci.download_layer: Individual layer download

Example:
    >>> from floe_core.oci.metrics import OCIMetrics
    >>>
    >>> # Create metrics instance
    >>> metrics = OCIMetrics()
    >>>
    >>> # Record operation
    >>> with metrics.operation_timer("push", "harbor.example.com"):
    ...     result = push_artifact()
    >>>
    >>> # Record success/failure
    >>> metrics.record_operation("push", "harbor.example.com", success=True)
    >>>
    >>> # Record cache operation
    >>> metrics.record_cache_operation("hit")

See Also:
    - specs/08a-oci-client/research.md: Section 8 - OpenTelemetry Metrics
    - floe_core.telemetry.metrics: Base MetricRecorder class
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from enum import IntEnum
from typing import TYPE_CHECKING, Any

import structlog
from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import Generator

    from opentelemetry.metrics import Counter, Histogram
    from opentelemetry.metrics._internal.instrument import Gauge
    from opentelemetry.trace import Span, Tracer


logger = structlog.get_logger(__name__)


class CircuitBreakerStateValue(IntEnum):
    """Numeric values for circuit breaker state gauge."""

    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2


class OCIMetrics:
    """OpenTelemetry metrics collector for OCI operations.

    Provides instrumentation for all OCI client operations with consistent
    metric naming and labeling. Thread-safe via OpenTelemetry SDK.

    Metric Naming Convention:
        All metrics are prefixed with `floe_oci_` to avoid collisions with
        other instrumentation libraries.

    Label Conventions:
        - operation: push, pull, inspect, list
        - status: success, failure
        - registry: Registry hostname (e.g., harbor.example.com)
        - cache_operation: hit, miss, evict, expire

    Example:
        >>> metrics = OCIMetrics()
        >>>
        >>> # Record a push operation
        >>> start = time.monotonic()
        >>> try:
        ...     result = push_artifact()
        ...     metrics.record_operation("push", "harbor.example.com", success=True)
        ...     metrics.record_duration("push", "harbor.example.com", time.monotonic() - start)
        ... except Exception:
        ...     metrics.record_operation("push", "harbor.example.com", success=False)
        ...     raise
        >>>
        >>> # Or use the context manager
        >>> with metrics.operation_timer("push", "harbor.example.com"):
        ...     result = push_artifact()
    """

    # Metric names (module constants for reuse in tests)
    OPERATIONS_TOTAL = "floe_oci_operations_total"
    CACHE_OPERATIONS_TOTAL = "floe_oci_cache_operations_total"
    OPERATION_DURATION_SECONDS = "floe_oci_operation_duration_seconds"
    ARTIFACT_SIZE_BYTES = "floe_oci_artifact_size_bytes"
    CIRCUIT_BREAKER_STATE = "floe_oci_circuit_breaker_state"
    CACHE_SIZE_BYTES = "floe_oci_cache_size_bytes"
    CACHE_ENTRIES_COUNT = "floe_oci_cache_entries_count"

    # Span names
    SPAN_PUSH = "floe.oci.push"
    SPAN_PULL = "floe.oci.pull"
    SPAN_INSPECT = "floe.oci.inspect"
    SPAN_LIST = "floe.oci.list"
    SPAN_AUTH = "floe.oci.auth"
    SPAN_UPLOAD_LAYER = "floe.oci.upload_layer"
    SPAN_DOWNLOAD_LAYER = "floe.oci.download_layer"

    def __init__(
        self,
        meter_name: str = "floe.oci",
        meter_version: str = "1.0.0",
        tracer_name: str = "floe.oci",
    ) -> None:
        """Initialize OCI metrics collector.

        Args:
            meter_name: Name for the OpenTelemetry meter.
            meter_version: Version for the meter.
            tracer_name: Name for the OpenTelemetry tracer.
        """
        self._meter = metrics.get_meter(meter_name, meter_version)
        self._tracer: Tracer = trace.get_tracer(tracer_name)

        # Initialize instruments (lazy creation via properties)
        self._operations_counter: Counter | None = None
        self._cache_operations_counter: Counter | None = None
        self._duration_histogram: Histogram | None = None
        self._size_histogram: Histogram | None = None
        self._circuit_breaker_gauge: Gauge | None = None
        self._cache_size_gauge: Gauge | None = None
        self._cache_entries_gauge: Gauge | None = None

    @property
    def operations_counter(self) -> Counter:
        """Get or create the operations counter."""
        if self._operations_counter is None:
            self._operations_counter = self._meter.create_counter(
                self.OPERATIONS_TOTAL,
                unit="1",
                description="Total number of OCI operations by type, status, and registry",
            )
        return self._operations_counter

    @property
    def cache_operations_counter(self) -> Counter:
        """Get or create the cache operations counter."""
        if self._cache_operations_counter is None:
            self._cache_operations_counter = self._meter.create_counter(
                self.CACHE_OPERATIONS_TOTAL,
                unit="1",
                description="Total number of cache operations by type",
            )
        return self._cache_operations_counter

    @property
    def duration_histogram(self) -> Histogram:
        """Get or create the duration histogram."""
        if self._duration_histogram is None:
            self._duration_histogram = self._meter.create_histogram(
                self.OPERATION_DURATION_SECONDS,
                unit="s",
                description="Duration of OCI operations in seconds",
            )
        return self._duration_histogram

    @property
    def size_histogram(self) -> Histogram:
        """Get or create the artifact size histogram."""
        if self._size_histogram is None:
            self._size_histogram = self._meter.create_histogram(
                self.ARTIFACT_SIZE_BYTES,
                unit="By",
                description="Size of artifacts in bytes",
            )
        return self._size_histogram

    @property
    def circuit_breaker_gauge(self) -> Gauge:
        """Get or create the circuit breaker state gauge."""
        if self._circuit_breaker_gauge is None:
            self._circuit_breaker_gauge = self._meter.create_gauge(
                self.CIRCUIT_BREAKER_STATE,
                unit="1",
                description="Circuit breaker state (0=closed, 1=open, 2=half_open)",
            )
        return self._circuit_breaker_gauge

    @property
    def cache_size_gauge(self) -> Gauge:
        """Get or create the cache size gauge."""
        if self._cache_size_gauge is None:
            self._cache_size_gauge = self._meter.create_gauge(
                self.CACHE_SIZE_BYTES,
                unit="By",
                description="Current cache size in bytes",
            )
        return self._cache_size_gauge

    @property
    def cache_entries_gauge(self) -> Gauge:
        """Get or create the cache entries gauge."""
        if self._cache_entries_gauge is None:
            self._cache_entries_gauge = self._meter.create_gauge(
                self.CACHE_ENTRIES_COUNT,
                unit="1",
                description="Current number of cache entries",
            )
        return self._cache_entries_gauge

    def record_operation(
        self,
        operation: str,
        registry: str,
        *,
        success: bool,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record an OCI operation completion.

        Args:
            operation: Operation type (push, pull, inspect, list).
            registry: Registry hostname or URI.
            success: Whether the operation succeeded.
            labels: Additional labels to add to the metric.
        """
        attributes: dict[str, Any] = {
            "operation": operation,
            "registry": self._normalize_registry(registry),
            "status": "success" if success else "failure",
        }
        if labels:
            attributes.update(labels)

        self.operations_counter.add(1, attributes=attributes)

        logger.debug(
            "oci_operation_recorded",
            operation=operation,
            registry=registry,
            success=success,
        )

    def record_duration(
        self,
        operation: str,
        registry: str,
        duration_seconds: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record the duration of an OCI operation.

        Args:
            operation: Operation type (push, pull, inspect, list).
            registry: Registry hostname or URI.
            duration_seconds: Duration in seconds.
            labels: Additional labels to add to the metric.
        """
        attributes: dict[str, Any] = {
            "operation": operation,
            "registry": self._normalize_registry(registry),
        }
        if labels:
            attributes.update(labels)

        self.duration_histogram.record(duration_seconds, attributes=attributes)

    def record_artifact_size(
        self,
        operation: str,
        size_bytes: int,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record artifact size for push/pull operations.

        Args:
            operation: Operation type (push or pull).
            size_bytes: Size of the artifact in bytes.
            labels: Additional labels to add to the metric.
        """
        attributes: dict[str, Any] = {"operation": operation}
        if labels:
            attributes.update(labels)

        self.size_histogram.record(size_bytes, attributes=attributes)

    def record_cache_operation(
        self,
        operation: str,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a cache operation.

        Args:
            operation: Cache operation type (hit, miss, evict, expire).
            labels: Additional labels to add to the metric.
        """
        attributes: dict[str, Any] = {"operation": operation}
        if labels:
            attributes.update(labels)

        self.cache_operations_counter.add(1, attributes=attributes)

    def set_circuit_breaker_state(
        self,
        registry: str,
        state: CircuitBreakerStateValue,
    ) -> None:
        """Set the circuit breaker state for a registry.

        Args:
            registry: Registry hostname or URI.
            state: Circuit breaker state value.
        """
        attributes: dict[str, Any] = {
            "registry": self._normalize_registry(registry),
        }
        self.circuit_breaker_gauge.set(int(state), attributes=attributes)

    def set_cache_stats(
        self,
        size_bytes: int,
        entry_count: int,
    ) -> None:
        """Set cache statistics gauges.

        Args:
            size_bytes: Current cache size in bytes.
            entry_count: Current number of cache entries.
        """
        self.cache_size_gauge.set(size_bytes)
        self.cache_entries_gauge.set(entry_count)

    @contextmanager
    def operation_timer(
        self,
        operation: str,
        registry: str,
        *,
        labels: dict[str, str] | None = None,
    ) -> Generator[None, None, None]:
        """Context manager to time an OCI operation.

        Records both duration and success/failure status automatically.

        Args:
            operation: Operation type (push, pull, inspect, list).
            registry: Registry hostname or URI.
            labels: Additional labels to add to metrics.

        Yields:
            None

        Example:
            >>> with metrics.operation_timer("push", "harbor.example.com"):
            ...     push_artifact()  # Duration and status recorded automatically
        """
        start_time = time.monotonic()
        success = False
        try:
            yield
            success = True
        finally:
            duration = time.monotonic() - start_time
            self.record_duration(operation, registry, duration, labels=labels)
            self.record_operation(operation, registry, success=success, labels=labels)

    @contextmanager
    def create_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """Create a trace span for an OCI operation.

        Args:
            name: Span name (use SPAN_* constants).
            attributes: Optional span attributes.

        Yields:
            The created span for additional attribute setting.

        Example:
            >>> with metrics.create_span(OCIMetrics.SPAN_PUSH, {"registry": "harbor"}) as span:
            ...     span.set_attribute("artifact.tag", "v1.0.0")
            ...     push_artifact()
        """
        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def _normalize_registry(self, registry: str) -> str:
        """Normalize registry URI to hostname for metric labels.

        Args:
            registry: Registry URI (e.g., oci://harbor.example.com/namespace/repo).

        Returns:
            Normalized hostname (e.g., harbor.example.com).
        """
        # Remove oci:// prefix if present
        if registry.startswith("oci://"):
            registry = registry[6:]

        # Extract hostname (first path component or before /)
        if "/" in registry:
            return registry.split("/")[0]
        return registry


# Module-level singleton for convenience
_default_metrics: OCIMetrics | None = None


def get_oci_metrics() -> OCIMetrics:
    """Get the default OCI metrics instance.

    Returns:
        The default OCIMetrics singleton.
    """
    global _default_metrics
    if _default_metrics is None:
        _default_metrics = OCIMetrics()
    return _default_metrics


def set_oci_metrics(metrics_instance: OCIMetrics | None) -> None:
    """Set the default OCI metrics instance (for testing).

    Args:
        metrics_instance: OCIMetrics instance or None to reset.
    """
    global _default_metrics
    _default_metrics = metrics_instance


__all__ = [
    "CircuitBreakerStateValue",
    "OCIMetrics",
    "get_oci_metrics",
    "set_oci_metrics",
]
