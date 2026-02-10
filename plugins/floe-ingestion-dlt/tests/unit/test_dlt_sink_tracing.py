"""Unit tests for dlt sink egress tracing functions.

Epic 4G: Reverse-ETL sink implementation.

Tests for egress_span(), record_egress_result(), record_egress_error()
and egress-specific attribute constants. These functions provide OpenTelemetry
tracing for reverse-ETL sink operations (writing data to external systems).

Pattern matches existing ingestion_span() in the same module.
"""

from __future__ import annotations

import pytest
from floe_core.plugins.sink import EgressResult
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_ingestion_dlt.tracing import (
    ATTR_ERROR_CATEGORY,
    ATTR_ERROR_MESSAGE,
    ATTR_ERROR_TYPE,
    ATTR_SINK_DESTINATION,
    ATTR_SINK_DURATION_MS,
    ATTR_SINK_ROWS_WRITTEN,
    ATTR_SINK_STATUS,
    ATTR_SINK_TYPE,
    egress_span,
    record_egress_error,
    record_egress_result,
)


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    """In-memory span exporter for test assertions."""
    return InMemorySpanExporter()


@pytest.fixture
def tracer(span_exporter: InMemorySpanExporter) -> trace.Tracer:
    """Tracer with in-memory exporter for test assertions."""
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider.get_tracer("test.egress")


class TestEgressTracing:
    """Test suite for egress tracing functions."""

    @pytest.mark.requirement("4G-FR-010")
    def test_egress_span_creates_span_with_sink_type(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test egress_span creates span with sink_type attribute."""
        with egress_span(tracer, "write", sink_type="rest_api"):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes is not None
        assert spans[0].attributes[ATTR_SINK_TYPE] == "rest_api"

    @pytest.mark.requirement("4G-FR-010")
    def test_egress_span_creates_span_with_destination(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test egress_span creates span with destination attribute."""
        with egress_span(tracer, "write", destination="gold.customers"):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes is not None
        assert spans[0].attributes[ATTR_SINK_DESTINATION] == "gold.customers"

    @pytest.mark.requirement("4G-FR-010")
    def test_egress_span_sets_ok_status_on_success(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test egress_span sets OK status when no exception occurs."""
        with egress_span(tracer, "write", sink_type="rest_api"):
            pass  # Happy path

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    @pytest.mark.requirement("4G-FR-010")
    def test_egress_span_sets_error_status_on_exception(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test egress_span sets ERROR status when exception raised."""
        with pytest.raises(ValueError, match="test error"):
            with egress_span(tracer, "write", sink_type="rest_api"):
                raise ValueError("test error")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("4G-FR-010")
    def test_record_egress_result_sets_all_attributes(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test record_egress_result sets all result attributes on span."""
        result = EgressResult(
            success=True,
            rows_delivered=100,
            bytes_transmitted=5000,
            duration_seconds=1.5,
        )

        with egress_span(tracer, "write", sink_type="rest_api") as span:
            record_egress_result(span, result)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs[ATTR_SINK_STATUS] == "success"
        assert attrs[ATTR_SINK_ROWS_WRITTEN] == 100
        assert attrs[ATTR_SINK_DURATION_MS] == pytest.approx(1500.0)

    @pytest.mark.requirement("4G-FR-010")
    def test_record_egress_error_sets_error_type(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test record_egress_error sets error type attribute."""
        error = ValueError("test error")

        with egress_span(tracer, "write", sink_type="rest_api") as span:
            record_egress_error(span, error)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs[ATTR_ERROR_TYPE] == "ValueError"

    @pytest.mark.requirement("4G-FR-010")
    def test_record_egress_error_truncates_message(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test record_egress_error truncates long error messages to 500 chars."""
        long_message = "x" * 1000
        error = ValueError(long_message)

        with egress_span(tracer, "write", sink_type="rest_api") as span:
            record_egress_error(span, error)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        error_message = attrs[ATTR_ERROR_MESSAGE]
        assert isinstance(error_message, str)
        assert len(error_message) <= 500

    @pytest.mark.requirement("4G-FR-010")
    def test_record_egress_error_sets_category(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test record_egress_error sets error category attribute."""
        error = ConnectionError("network failure")

        with egress_span(tracer, "write", sink_type="rest_api") as span:
            record_egress_error(span, error, category="transient")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs[ATTR_ERROR_CATEGORY] == "transient"

    @pytest.mark.requirement("4G-FR-010")
    def test_egress_span_operation_name_prefix(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test egress_span creates span name with 'egress.' prefix."""
        with egress_span(tracer, "write", sink_type="rest_api"):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name.startswith("egress.")


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message utility function."""

    @pytest.mark.requirement("4G-FR-049")
    def test_sanitize_strips_url_credentials(self) -> None:
        """Test URL credential patterns are redacted."""
        from floe_ingestion_dlt.tracing import sanitize_error_message

        msg = "Failed to connect to http://user:secret@host:5432/db"  # pragma: allowlist secret
        result = sanitize_error_message(msg)
        assert "secret" not in result
        assert "<REDACTED>" in result

    @pytest.mark.requirement("4G-FR-049")
    def test_sanitize_strips_key_value_credentials(self) -> None:
        """Test key=value credential patterns are redacted."""
        from floe_ingestion_dlt.tracing import sanitize_error_message

        pw_value = "Z" * 12  # noqa: S105
        key_value = "A" * 8  # noqa: S105
        msg = f"Config error: password={pw_value} and api_key={key_value}"
        result = sanitize_error_message(msg)
        assert pw_value not in result
        assert key_value not in result
        assert "password=<REDACTED>" in result

    @pytest.mark.requirement("4G-FR-049")
    def test_sanitize_truncates_long_messages(self) -> None:
        """Test messages are truncated to max_length."""
        from floe_ingestion_dlt.tracing import sanitize_error_message

        msg = "x" * 1000
        result = sanitize_error_message(msg, max_length=500)
        assert len(result) == 500

    @pytest.mark.requirement("4G-FR-049")
    def test_sanitize_passes_clean_strings_through(self) -> None:
        """Test clean strings are returned unchanged."""
        from floe_ingestion_dlt.tracing import sanitize_error_message

        msg = "Simple error: table not found"
        result = sanitize_error_message(msg)
        assert result == msg

    @pytest.mark.requirement("4G-FR-049")
    def test_sanitize_handles_empty_string(self) -> None:
        """Test empty string input returns empty string."""
        from floe_ingestion_dlt.tracing import sanitize_error_message

        assert sanitize_error_message("") == ""

    @pytest.mark.requirement("4G-FR-049")
    def test_sanitize_strips_access_key_pattern(self) -> None:
        """Test access_key patterns are redacted."""
        from floe_ingestion_dlt.tracing import sanitize_error_message

        test_value = "X" * 20  # noqa: S105
        msg = f"S3 error: access_key={test_value}"
        result = sanitize_error_message(msg)
        assert test_value not in result
        assert "<REDACTED>" in result

    @pytest.mark.requirement("4G-FR-049")
    def test_sanitize_strips_secret_key_pattern(self) -> None:
        """Test secret_key patterns are redacted."""
        from floe_ingestion_dlt.tracing import sanitize_error_message

        test_value = "Y" * 20  # noqa: S105
        msg = f"Error: secret_key={test_value}"
        result = sanitize_error_message(msg)
        assert test_value not in result
        assert "<REDACTED>" in result


class TestSpanExceptionRecording:
    """Tests that span exceptions are recorded safely (not via record_exception)."""

    @pytest.mark.requirement("4G-FR-049")
    def test_egress_span_records_sanitized_exception(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test egress_span records sanitized exception attributes, not raw."""
        with pytest.raises(ValueError):
            with egress_span(tracer, "write", sink_type="rest_api"):
                raise ValueError("password=secret123 connection failed")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs["exception.type"] == "ValueError"
        exc_msg = attrs["exception.message"]
        assert isinstance(exc_msg, str)
        assert "secret123" not in exc_msg
        assert "<REDACTED>" in exc_msg

    @pytest.mark.requirement("4G-FR-049")
    def test_ingestion_span_records_sanitized_exception(
        self, tracer: trace.Tracer, span_exporter: InMemorySpanExporter
    ) -> None:
        """Test ingestion_span records sanitized exception attributes, not raw."""
        from floe_ingestion_dlt.tracing import ingestion_span

        with pytest.raises(RuntimeError):
            with ingestion_span(tracer, "run", source_type="rest_api"):
                raise RuntimeError("token=abc123 auth failed")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs["exception.type"] == "RuntimeError"
        exc_msg = attrs["exception.message"]
        assert isinstance(exc_msg, str)
        assert "abc123" not in exc_msg
