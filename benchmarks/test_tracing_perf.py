"""Tracing performance benchmarks.

Measures overhead of OpenTelemetry tracing primitives:
- @traced decorator
- create_span context manager
- Realistic pipeline workloads

Target: <5% overhead for realistic operations (SC-004).
"""

from __future__ import annotations

import json

import pytest

from floe_core.telemetry.tracing import create_span, traced


@pytest.mark.benchmark
def test_traced_decorator_overhead() -> None:
    """Benchmark @traced decorator overhead.

    Measures the per-span overhead of using the @traced decorator
    on a lightweight function.
    """

    @traced
    def work() -> int:
        return sum(range(100))

    for _ in range(1000):
        work()


@pytest.mark.benchmark
def test_create_span_overhead() -> None:
    """Benchmark create_span context manager overhead.

    Measures the per-span overhead of using the create_span
    context manager.
    """

    def work() -> int:
        with create_span("test_span"):
            return sum(range(100))

    for _ in range(1000):
        work()


@pytest.mark.benchmark
def test_nested_spans_overhead() -> None:
    """Benchmark nested span overhead.

    Measures overhead when creating parent-child span hierarchies.
    """

    def work() -> int:
        with create_span("parent"):
            with create_span("child_1"):
                result = sum(range(50))
            with create_span("child_2"):
                result += sum(range(50))
        return result

    for _ in range(500):
        work()


@pytest.mark.benchmark
def test_traced_with_attributes_overhead() -> None:
    """Benchmark @traced decorator with custom attributes.

    Measures additional overhead when setting span attributes.
    """

    @traced(
        name="attributed_operation",
        attributes={"component": "test", "version": "1.0"},
    )
    def work() -> int:
        return sum(range(100))

    for _ in range(1000):
        work()


@pytest.mark.benchmark
def test_realistic_pipeline_with_tracing() -> None:
    """Benchmark realistic workload with tracing.

    Simulates a data processing pipeline with JSON serialization.
    Target: <5% overhead vs untraced baseline.
    """

    @traced(name="pipeline")
    def pipeline() -> float:
        # Simulate data processing
        data = {"items": [{"id": i, "value": i * 2.5} for i in range(100)]}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        return sum(item["value"] for item in parsed["items"])

    for _ in range(100):
        pipeline()


@pytest.mark.benchmark
def test_baseline_no_tracing() -> None:
    """Baseline measurement without tracing.

    Provides reference point for calculating tracing overhead.
    """

    def pipeline() -> float:
        data = {"items": [{"id": i, "value": i * 2.5} for i in range(100)]}
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        return sum(item["value"] for item in parsed["items"])

    for _ in range(100):
        pipeline()
