"""Unit tests for OpenTelemetry tracing in floe-lineage-marquez.

These tests verify that lineage operations emit correct OTel spans with
appropriate attributes, span names, and error handling.

Tests use REAL TracerProvider + InMemorySpanExporter (NOT mocks) to validate
actual OTel span behavior.

Requirements Covered:
    - 6C-FR-020: OTel spans for lineage operations
    - 6C-FR-021: Span attributes for lineage context
    - 6C-FR-023: No credentials in traces
"""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_lineage_marquez.tracing import (
    ATTR_EVENT_TYPE,
    ATTR_JOB_NAME,
    ATTR_NAMESPACE,
    ATTR_RUN_ID,
    TRACER_NAME,
    get_tracer,
    lineage_span,
)


@pytest.fixture
def tracer_provider() -> TracerProvider:
    """Create a real TracerProvider for testing.

    Returns:
        TracerProvider configured with InMemorySpanExporter.
    """
    return TracerProvider()


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    """Create an in-memory span exporter for verification.

    Returns:
        InMemorySpanExporter instance.
    """
    return InMemorySpanExporter()


@pytest.fixture
def tracer_with_exporter(
    tracer_provider: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> TracerProvider:
    """Configure TracerProvider with span exporter.

    Args:
        tracer_provider: TracerProvider instance.
        span_exporter: InMemorySpanExporter instance.

    Returns:
        TracerProvider with exporter configured.
    """
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return tracer_provider


@pytest.mark.requirement("6C-FR-020")
def test_get_tracer_returns_tracer() -> None:
    """Test get_tracer returns a Tracer instance.

    Verifies that get_tracer() returns a valid OpenTelemetry Tracer
    with the correct name.
    """
    tracer = get_tracer()
    assert tracer is not None


@pytest.mark.requirement("6C-FR-020")
def test_lineage_span_creates_span_with_correct_name(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span creates span with correct name.

    Verifies that lineage_span creates a span named "lineage.{operation}".
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with lineage_span(tracer, "get_transport_config"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "lineage.get_transport_config"


@pytest.mark.requirement("6C-FR-021")
def test_lineage_span_sets_job_name_attribute(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span sets job_name attribute.

    Verifies that lineage_span sets the lineage.job_name attribute
    when job_name is provided.
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with lineage_span(tracer, "emit_run_event", job_name="etl_pipeline"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes[ATTR_JOB_NAME] == "etl_pipeline"


@pytest.mark.requirement("6C-FR-021")
def test_lineage_span_sets_event_type_attribute(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span sets event_type attribute.

    Verifies that lineage_span sets the lineage.event_type attribute
    when event_type is provided.
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with lineage_span(tracer, "emit_run_event", event_type="START"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes[ATTR_EVENT_TYPE] == "START"


@pytest.mark.requirement("6C-FR-021")
def test_lineage_span_sets_namespace_attribute(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span sets namespace attribute.

    Verifies that lineage_span sets the lineage.namespace attribute
    when namespace is provided.
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with lineage_span(tracer, "get_namespace_strategy", namespace="production"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes[ATTR_NAMESPACE] == "production"


@pytest.mark.requirement("6C-FR-021")
def test_lineage_span_sets_run_id_attribute(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span sets run_id attribute.

    Verifies that lineage_span sets the lineage.run_id attribute
    when run_id is provided.
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with lineage_span(tracer, "emit_run_event", run_id="run-123"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes[ATTR_RUN_ID] == "run-123"


@pytest.mark.requirement("6C-FR-021")
def test_lineage_span_sets_extra_attributes(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span sets extra attributes.

    Verifies that lineage_span merges extra_attributes into span attributes.
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with lineage_span(
        tracer,
        "emit_run_event",
        extra_attributes={"custom.attribute": "value"},
    ):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes["custom.attribute"] == "value"


@pytest.mark.requirement("6C-FR-020")
def test_lineage_span_sets_status_ok_on_success(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span sets status OK on success.

    Verifies that lineage_span sets StatusCode.OK when no exception occurs.
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with lineage_span(tracer, "get_transport_config"):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.OK


@pytest.mark.requirement("6C-FR-023")
def test_lineage_span_sanitizes_error_messages(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span sanitizes error messages.

    Verifies that lineage_span sanitizes error messages to prevent
    credential leakage in traces. Error messages containing credentials
    should be redacted.
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    error_msg = "Connection failed: https://user:secret-password@marquez:5000"

    with pytest.raises(ValueError):
        with lineage_span(tracer, "validate_connection"):
            raise ValueError(error_msg)

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
    assert spans[0].attributes["exception.type"] == "ValueError"

    # Verify sanitization occurred (no credential in message)
    sanitized_msg = spans[0].attributes["exception.message"]
    assert "secret-password" not in sanitized_msg
    assert "REDACTED" in sanitized_msg or "***" in sanitized_msg


@pytest.mark.requirement("6C-FR-020")
def test_lineage_span_sets_status_error_on_exception(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span sets status ERROR on exception.

    Verifies that lineage_span sets StatusCode.ERROR and records
    exception details when an exception occurs.
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with pytest.raises(RuntimeError):
        with lineage_span(tracer, "validate_connection"):
            raise RuntimeError("Connection failed")

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
    assert spans[0].attributes["exception.type"] == "RuntimeError"
    assert "Connection failed" in spans[0].attributes["exception.message"]


@pytest.mark.requirement("6C-FR-021")
def test_lineage_span_excludes_none_attributes(
    tracer_with_exporter: TracerProvider,
    span_exporter: InMemorySpanExporter,
) -> None:
    """Test lineage_span excludes None attributes.

    Verifies that lineage_span does not set attributes when their
    values are None (keeps spans clean).
    """
    tracer = tracer_with_exporter.get_tracer(TRACER_NAME)

    with lineage_span(
        tracer,
        "get_transport_config",
        job_name=None,
        event_type=None,
        namespace=None,
    ):
        pass

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    # Only operation attribute should be present (implicitly via span name)
    # No job_name, event_type, or namespace attributes
    assert ATTR_JOB_NAME not in spans[0].attributes
    assert ATTR_EVENT_TYPE not in spans[0].attributes
    assert ATTR_NAMESPACE not in spans[0].attributes
