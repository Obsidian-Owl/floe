"""Tracing performance benchmarks.

Measures overhead of OpenTelemetry tracing primitives:
- @traced decorator
- @traced with attributes_fn dynamic attributes
- create_span context manager
- Sanitized vs raw error recording
- Realistic pipeline workloads

Target: <5% overhead for realistic operations (SC-004, SC-006).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from floe_core.telemetry.sanitization import sanitize_error_message
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

    pipeline()


@pytest.mark.benchmark
def test_traced_with_attributes_fn_overhead() -> None:
    """Benchmark @traced decorator with dynamic attributes_fn.

    Measures the additional overhead of computing attributes dynamically
    from function arguments via the attributes_fn parameter.

    Requirements: FR-024, SC-006
    """

    def get_attrs(table_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"table.id": table_id, "table.size": len(table_id)}

    @traced(
        name="dynamic_attributed_operation",
        attributes_fn=get_attrs,
    )
    def work(table_id: str) -> int:
        return sum(range(100))

    work(table_id="benchmark_table")


@pytest.mark.benchmark
def test_sanitized_error_recording_overhead() -> None:
    """Benchmark sanitized error recording vs raw.

    Measures the overhead of sanitize_error_message() when recording
    errors in spans. Should verify <5% overhead compared to raw.

    Requirements: FR-024, SC-006
    """
    error_msg = (
        "Connection failed to https://user:password@example.com/api "
        "with api_key=sk-1234567890 and token=Bearer abc123"
    )

    # Sanitized path (what we use in production)
    with create_span("sanitized_error_test") as span:
        sanitized = sanitize_error_message(error_msg)
        span.set_attribute("exception.message", sanitized)


@pytest.mark.benchmark
def test_raw_error_recording_baseline() -> None:
    """Baseline for error recording without sanitization.

    Provides reference point for calculating sanitization overhead.
    """
    error_msg = (
        "Connection failed to https://user:password@example.com/api "
        "with api_key=sk-1234567890 and token=Bearer abc123"
    )

    # Raw path (no sanitization)
    with create_span("raw_error_test") as span:
        span.set_attribute("exception.message", error_msg)


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

    pipeline()
