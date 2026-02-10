"""OpenTelemetry tracing helpers for the dbt-expectations Quality Plugin.

This module provides utilities for instrumenting quality check operations with
OpenTelemetry spans. Operations like run_checks, run_suite, and validate_expectations
emit spans for observability.

Security:
    - Spans MUST NOT include PII, raw data values, or credentials
    - Only include operation metadata (check names, counts, model names)

Example:
    >>> from floe_quality_dbt.tracing import get_tracer, quality_span
    >>> tracer = get_tracer()
    >>> with quality_span(tracer, "run_suite", suite_name="my_suite", checks_count=5) as span:
    ...     # perform validation
    ...     record_result(span, pass_count=4, fail_count=1, rows_checked=1000)

Requirements Covered:
    - 6C-FR-020: OTel spans for quality check operations
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from floe_core.telemetry.sanitization import sanitize_error_message
from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import Iterator

# Tracer name follows OpenTelemetry naming conventions
TRACER_NAME = "floe.quality.dbt"

# Semantic attribute names for quality operations
ATTR_OPERATION = "quality.operation"
ATTR_PROVIDER = "quality.provider"
ATTR_CHECK_NAME = "quality.check_name"
ATTR_SUITE_NAME = "quality.suite_name"
ATTR_DATA_SOURCE = "quality.data_source"
ATTR_CHECKS_COUNT = "quality.checks_count"
ATTR_ROWS_CHECKED = "quality.rows_checked"
ATTR_PASS_COUNT = "quality.pass_count"
ATTR_FAIL_COUNT = "quality.fail_count"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for quality operations.

    Returns a thread-safe tracer instance from the factory configured for
    the dbt-expectations quality plugin. If no tracer provider is configured or
    initialization fails, returns a no-op tracer.

    Returns:
        OpenTelemetry Tracer instance.

    Example:
        >>> tracer = get_tracer()
        >>> with tracer.start_as_current_span("my_operation"):
        ...     pass
    """
    return _factory_get_tracer(TRACER_NAME)


@contextmanager
def quality_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    suite_name: str | None = None,
    data_source: str | None = None,
    checks_count: int | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating quality operation spans.

    Creates an OpenTelemetry span with standard quality attributes.
    The span automatically records duration and handles exceptions.

    SECURITY: Never pass raw data values, PII, or credentials as attributes.
    Only operation metadata is safe to include.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "run_checks", "run_suite", "validate_expectations").
        suite_name: Name of the quality suite being executed.
        data_source: Data source identifier (model name, table name).
        checks_count: Number of checks in the suite.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with quality_span(
        ...     tracer,
        ...     "run_suite",
        ...     suite_name="my_suite",
        ...     data_source="users",
        ...     checks_count=10,
        ... ) as span:
        ...     record_result(span, pass_count=9, fail_count=1)
    """
    span_name = f"quality.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {
        ATTR_OPERATION: operation,
        ATTR_PROVIDER: "dbt_expectations",
    }

    if suite_name is not None:
        attributes[ATTR_SUITE_NAME] = suite_name
    if data_source is not None:
        attributes[ATTR_DATA_SOURCE] = data_source
    if checks_count is not None:
        attributes[ATTR_CHECKS_COUNT] = checks_count
    if extra_attributes:
        attributes.update(extra_attributes)

    with tracer.start_as_current_span(
        span_name,
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            sanitized = sanitize_error_message(str(e))
            span.set_status(Status(StatusCode.ERROR, type(e).__name__))
            span.set_attribute("exception.type", type(e).__name__)
            span.set_attribute("exception.message", sanitized)
            raise


def record_result(
    span: trace.Span,
    *,
    pass_count: int | None = None,
    fail_count: int | None = None,
    rows_checked: int | None = None,
) -> None:
    """Record quality check results on a span.

    Sets span attributes for completed quality check operations.
    Never records raw data values -- only aggregated metrics.

    Args:
        span: The active span to add attributes to.
        pass_count: Number of checks that passed.
        fail_count: Number of checks that failed.
        rows_checked: Total number of data rows checked.

    Example:
        >>> with quality_span(tracer, "run_suite", suite_name="users") as span:
        ...     result = run_dbt_tests()
        ...     record_result(span, pass_count=10, fail_count=2, rows_checked=5000)
    """
    if pass_count is not None:
        span.set_attribute(ATTR_PASS_COUNT, pass_count)
    if fail_count is not None:
        span.set_attribute(ATTR_FAIL_COUNT, fail_count)
    if rows_checked is not None:
        span.set_attribute(ATTR_ROWS_CHECKED, rows_checked)


__all__ = [
    "ATTR_CHECK_NAME",
    "ATTR_CHECKS_COUNT",
    "ATTR_DATA_SOURCE",
    "ATTR_FAIL_COUNT",
    "ATTR_OPERATION",
    "ATTR_PASS_COUNT",
    "ATTR_PROVIDER",
    "ATTR_ROWS_CHECKED",
    "ATTR_SUITE_NAME",
    "TRACER_NAME",
    "get_tracer",
    "quality_span",
    "record_result",
]
