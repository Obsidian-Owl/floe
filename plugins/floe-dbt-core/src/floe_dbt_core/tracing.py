"""OpenTelemetry tracing helpers for the DBT Core Plugin.

This module provides utilities for instrumenting dbt operations with
OpenTelemetry spans. All dbt operations (compile, run, test, lint)
emit spans for observability.

Security:
    - Spans MUST NOT include credentials, PII, or sensitive data
    - Only include operation metadata (project path, target, command)

Example:
    >>> from floe_dbt_core.tracing import get_tracer, dbt_span
    >>> tracer = get_tracer()
    >>> with dbt_span(tracer, "compile", project_dir="/path/to/project") as span:
    ...     # perform operation
    ...     span.set_attribute("dbt.manifest.models", 42)

Requirements:
    NFR-006: Observability through OpenTelemetry instrumentation
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import Iterator

# Tracer name follows OpenTelemetry naming conventions
TRACER_NAME = "floe.dbt.core"

# Semantic attribute names for dbt operations
ATTR_DBT_COMMAND = "dbt.command"
ATTR_DBT_PROJECT_DIR = "dbt.project_dir"
ATTR_DBT_PROFILES_DIR = "dbt.profiles_dir"
ATTR_DBT_TARGET = "dbt.target"
ATTR_DBT_SELECT = "dbt.select"
ATTR_DBT_EXCLUDE = "dbt.exclude"
ATTR_DBT_FULL_REFRESH = "dbt.full_refresh"
ATTR_DBT_MODELS_RUN = "dbt.models_run"
ATTR_DBT_TESTS_RUN = "dbt.tests_run"
ATTR_DBT_FAILURES = "dbt.failures"
ATTR_DBT_EXECUTION_TIME = "dbt.execution_time_seconds"
ATTR_DBT_RUNTIME = "dbt.runtime"
ATTR_DBT_VERSION = "dbt.version"
ATTR_DBT_FIX = "dbt.lint.fix"
ATTR_DBT_FILES_CHECKED = "dbt.lint.files_checked"
ATTR_DBT_FILES_FIXED = "dbt.lint.files_fixed"
ATTR_DBT_ISSUES_FOUND = "dbt.lint.issues_found"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for dbt operations.

    Returns a thread-safe tracer instance from the factory configured for
    the dbt-core plugin. If no tracer provider is configured or initialization
    fails, returns a no-op tracer.

    Returns:
        OpenTelemetry Tracer instance.

    Example:
        >>> tracer = get_tracer()
        >>> with tracer.start_as_current_span("my_operation"):
        ...     pass
    """
    return _factory_get_tracer(TRACER_NAME)


@contextmanager
def dbt_span(
    tracer: trace.Tracer,
    command: str,
    *,
    project_dir: str | None = None,
    profiles_dir: str | None = None,
    target: str | None = None,
    select: str | None = None,
    exclude: str | None = None,
    full_refresh: bool | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating dbt operation spans.

    Creates an OpenTelemetry span with standard dbt attributes.
    The span automatically records duration and handles exceptions.

    Args:
        tracer: OpenTelemetry tracer instance.
        command: dbt command name (e.g., "compile", "run", "test", "lint").
        project_dir: Path to dbt project directory.
        profiles_dir: Path to directory containing profiles.yml.
        target: dbt target name (e.g., "dev", "prod").
        select: dbt selection syntax.
        exclude: dbt exclusion syntax.
        full_refresh: Whether full refresh mode is enabled.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with dbt_span(
        ...     tracer,
        ...     "run",
        ...     project_dir="/path/to/project",
        ...     target="dev",
        ...     select="tag:daily"
        ... ) as span:
        ...     # perform dbt run
        ...     span.set_attribute("dbt.models_run", 10)
    """
    span_name = f"dbt.{command}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {ATTR_DBT_COMMAND: command}

    if project_dir is not None:
        attributes[ATTR_DBT_PROJECT_DIR] = project_dir
    if profiles_dir is not None:
        attributes[ATTR_DBT_PROFILES_DIR] = profiles_dir
    if target is not None:
        attributes[ATTR_DBT_TARGET] = target
    if select is not None:
        attributes[ATTR_DBT_SELECT] = select
    if exclude is not None:
        attributes[ATTR_DBT_EXCLUDE] = exclude
    if full_refresh is not None:
        attributes[ATTR_DBT_FULL_REFRESH] = full_refresh
    if extra_attributes:
        attributes.update(extra_attributes)

    with tracer.start_as_current_span(span_name, attributes=attributes) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            # Record exception but DO NOT include sensitive details
            span.set_status(Status(StatusCode.ERROR, str(type(e).__name__)))
            span.record_exception(e)
            raise


def set_result_attributes(
    span: trace.Span,
    *,
    models_run: int | None = None,
    tests_run: int | None = None,
    failures: int | None = None,
    execution_time: float | None = None,
    files_checked: int | None = None,
    files_fixed: int | None = None,
    issues_found: int | None = None,
) -> None:
    """Set result attributes on a dbt operation span.

    Adds completion information to a span after dbt operation finishes.

    Args:
        span: The span to add result attributes to.
        models_run: Number of models executed.
        tests_run: Number of tests executed.
        failures: Number of failures.
        execution_time: Execution time in seconds.
        files_checked: Number of files checked (for lint).
        files_fixed: Number of files fixed (for lint).
        issues_found: Number of issues found (for lint).

    Example:
        >>> with dbt_span(tracer, "run", project_dir="/path") as span:
        ...     result = run_dbt()
        ...     set_result_attributes(
        ...         span,
        ...         models_run=result.models_run,
        ...         failures=result.failures,
        ...         execution_time=result.execution_time_seconds
        ...     )
    """
    if models_run is not None:
        span.set_attribute(ATTR_DBT_MODELS_RUN, models_run)
    if tests_run is not None:
        span.set_attribute(ATTR_DBT_TESTS_RUN, tests_run)
    if failures is not None:
        span.set_attribute(ATTR_DBT_FAILURES, failures)
    if execution_time is not None:
        span.set_attribute(ATTR_DBT_EXECUTION_TIME, execution_time)
    if files_checked is not None:
        span.set_attribute(ATTR_DBT_FILES_CHECKED, files_checked)
    if files_fixed is not None:
        span.set_attribute(ATTR_DBT_FILES_FIXED, files_fixed)
    if issues_found is not None:
        span.set_attribute(ATTR_DBT_ISSUES_FOUND, issues_found)


def set_runtime_attributes(
    span: trace.Span,
    *,
    runtime: str | None = None,
    dbt_version: str | None = None,
) -> None:
    """Set runtime metadata attributes on a span.

    Adds dbt runtime information to a span.

    Args:
        span: The span to add runtime attributes to.
        runtime: Runtime type (e.g., "core", "fusion").
        dbt_version: dbt version string.

    Example:
        >>> with dbt_span(tracer, "compile", project_dir="/path") as span:
        ...     set_runtime_attributes(span, runtime="core", dbt_version="1.7.0")
    """
    if runtime is not None:
        span.set_attribute(ATTR_DBT_RUNTIME, runtime)
    if dbt_version is not None:
        span.set_attribute(ATTR_DBT_VERSION, dbt_version)
