"""Metrics performance benchmarks.

Measures overhead of OpenTelemetry metrics primitives:
- Counter increment
- Gauge set
- Histogram record

These benchmarks ensure metric recording doesn't introduce
significant latency in hot paths.
"""

from __future__ import annotations

import pytest

from floe_core.telemetry.metrics import MetricRecorder


@pytest.mark.benchmark
def test_metric_increment_overhead() -> None:
    """Benchmark MetricRecorder.increment() overhead.

    Measures counter increment latency for monitoring
    event counting in hot paths (e.g., request counting).
    """
    recorder = MetricRecorder()

    for _ in range(1000):
        recorder.increment("test.counter", labels={"status": "success"})


@pytest.mark.benchmark
def test_metric_increment_no_labels() -> None:
    """Benchmark counter increment without labels.

    Measures baseline increment overhead without attribute allocation.
    """
    recorder = MetricRecorder()

    for _ in range(1000):
        recorder.increment("test.counter.simple")


@pytest.mark.benchmark
def test_metric_gauge_overhead() -> None:
    """Benchmark MetricRecorder.set_gauge() overhead.

    Measures gauge set latency for monitoring current values
    (e.g., queue depth, memory usage).
    """
    recorder = MetricRecorder()

    for _ in range(1000):
        recorder.set_gauge("test.gauge", value=42, labels={"queue": "default"})


@pytest.mark.benchmark
def test_metric_histogram_overhead() -> None:
    """Benchmark MetricRecorder.record_histogram() overhead.

    Measures histogram recording latency for monitoring
    distributions (e.g., request duration, response size).
    """
    recorder = MetricRecorder()

    for _ in range(1000):
        recorder.record_histogram("test.duration", value=42.5, unit="ms")


@pytest.mark.benchmark
def test_metric_histogram_with_labels() -> None:
    """Benchmark histogram with multiple labels.

    Measures overhead when recording with high-cardinality attributes.
    """
    recorder = MetricRecorder()

    for _ in range(1000):
        recorder.record_histogram(
            "test.duration",
            value=42.5,
            labels={"method": "GET", "status": "200", "path": "/api/v1/users"},
        )


@pytest.mark.benchmark
def test_mixed_metrics_overhead() -> None:
    """Benchmark mixed metric operations.

    Simulates realistic monitoring scenario with multiple metric types.
    """
    recorder = MetricRecorder()

    for i in range(500):
        recorder.increment("requests.total", labels={"status": "success"})
        recorder.set_gauge("queue.depth", value=i % 100)
        recorder.record_histogram("request.duration", value=float(i % 1000))
