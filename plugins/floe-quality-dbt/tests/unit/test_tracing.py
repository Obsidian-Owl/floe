"""Unit tests for OpenTelemetry tracing helpers in floe_quality_dbt.tracing.

Tests cover tracer initialization, span creation, attribute setting, error
handling, and security (no PII/raw data in traces) for the dbt quality plugin.

Requirements Covered:
    - 6C-FR-020: Unit tests for quality tracing helpers
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_quality_dbt.tracing import (
    ATTR_CHECKS_COUNT,
    ATTR_DATA_SOURCE,
    ATTR_FAIL_COUNT,
    ATTR_OPERATION,
    ATTR_PASS_COUNT,
    ATTR_PROVIDER,
    ATTR_ROWS_CHECKED,
    ATTR_SUITE_NAME,
    TRACER_NAME,
    get_tracer,
    quality_span,
    record_result,
)


@pytest.fixture
def tracer_with_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create a TracerProvider with an InMemorySpanExporter for testing.

    Returns:
        Tuple of (TracerProvider, InMemorySpanExporter) for span verification.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestQualitySpan:
    """Unit tests for quality_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_quality_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that quality_span creates a span with the correct name.

        Validates that the span name follows the 'quality.<operation>' convention.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_checks"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "quality.run_checks"

    @pytest.mark.requirement("6C-FR-020")
    def test_quality_span_sets_provider_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that quality_span sets the 'quality.provider' attribute.

        Validates that the provider attribute is always set to 'dbt_expectations'.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_suite"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_PROVIDER] == "dbt_expectations"

    @pytest.mark.requirement("6C-FR-020")
    def test_quality_span_sets_suite_name_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that quality_span sets the 'quality.suite_name' attribute.

        Validates that the suite name attribute is recorded on the span when
        specified.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_suite", suite_name="users_suite"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_SUITE_NAME] == "users_suite"

    @pytest.mark.requirement("6C-FR-020")
    def test_quality_span_sets_data_source_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that quality_span sets the 'quality.data_source' attribute.

        Validates that the data source (model name) attribute is recorded on
        the span when specified.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_checks", data_source="customers"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_DATA_SOURCE] == "customers"

    @pytest.mark.requirement("6C-FR-020")
    def test_quality_span_sets_checks_count_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that quality_span sets the 'quality.checks_count' attribute.

        Validates that the number of checks is recorded on the span when
        specified.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_suite", checks_count=15):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_CHECKS_COUNT] == 15

    @pytest.mark.requirement("6C-FR-020")
    def test_quality_span_no_pii_in_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that no PII or raw data values appear in span attributes.

        Validates that only operation metadata (names, counts) are recorded.
        This is a critical security requirement (6C-FR-023).
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        fake_sensitive_data = "john.doe@example.com"  # pragma: allowlist secret

        with quality_span(
            tracer,
            "validate_expectations",
            suite_name="email_validation",
            data_source="users",
            checks_count=5,
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify no attribute contains sensitive data
        for attr_value in attributes.values():
            assert str(attr_value) != fake_sensitive_data, (
                f"Sensitive data found in span attribute: {attr_value}"
            )

        # Verify expected attributes are metadata only
        assert attributes.get(ATTR_SUITE_NAME) == "email_validation"
        assert attributes.get(ATTR_DATA_SOURCE) == "users"
        assert attributes.get(ATTR_CHECKS_COUNT) == 5

    @pytest.mark.requirement("6C-FR-020")
    def test_quality_span_error_sanitized(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that error messages are sanitized before recording on span.

        Validates that credentials in error messages are redacted via
        sanitize_error_message before being set as span attributes.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        # Error message containing a fake credential
        error_msg = "dbt failed: password=secret123 at database"  # pragma: allowlist secret

        with pytest.raises(RuntimeError, match="dbt failed"):
            with quality_span(tracer, "run_suite", suite_name="users"):
                raise RuntimeError(error_msg)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify error attributes are present
        assert attributes["exception.type"] == "RuntimeError"

        # Verify the password is redacted in the error message
        exception_message = attributes["exception.message"]
        assert "secret123" not in exception_message  # pragma: allowlist secret
        assert "<REDACTED>" in exception_message

        # Verify the span has ERROR status
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("6C-FR-020")
    def test_quality_span_ok_status_on_success(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that successful spans have StatusCode.OK.

        Validates that the span status is set to OK when no exception occurs.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_checks", suite_name="test_suite"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    @pytest.mark.requirement("6C-FR-020")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test that get_tracer returns a valid OpenTelemetry tracer.

        Validates that the function delegates to the factory with the
        correct tracer name constant.
        """
        with patch("floe_quality_dbt.tracing._factory_get_tracer") as mock_factory:
            from unittest.mock import MagicMock

            mock_tracer = MagicMock()
            mock_factory.return_value = mock_tracer

            result = get_tracer()

            assert result is mock_tracer
            mock_factory.assert_called_once_with(TRACER_NAME)


class TestRecordResult:
    """Unit tests for record_result helper function."""

    @pytest.mark.requirement("6C-FR-021")
    def test_record_result_sets_pass_count(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that record_result sets the 'quality.pass_count' attribute.

        Validates that the number of passed checks is recorded on the span.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_suite", suite_name="test") as span:
            record_result(span, pass_count=8)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_PASS_COUNT] == 8

    @pytest.mark.requirement("6C-FR-021")
    def test_record_result_sets_fail_count(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that record_result sets the 'quality.fail_count' attribute.

        Validates that the number of failed checks is recorded on the span.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_suite", suite_name="test") as span:
            record_result(span, fail_count=2)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_FAIL_COUNT] == 2

    @pytest.mark.requirement("6C-FR-021")
    def test_record_result_sets_rows_checked(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that record_result sets the 'quality.rows_checked' attribute.

        Validates that the total number of rows checked is recorded on the span.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_suite", suite_name="test") as span:
            record_result(span, rows_checked=10000)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_ROWS_CHECKED] == 10000

    @pytest.mark.requirement("6C-FR-021")
    def test_record_result_sets_all_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that record_result sets all result attributes together.

        Validates that pass_count, fail_count, and rows_checked can all be
        set in a single call.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with quality_span(tracer, "run_suite", suite_name="test") as span:
            record_result(span, pass_count=12, fail_count=3, rows_checked=5000)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_PASS_COUNT] == 12
        assert attributes[ATTR_FAIL_COUNT] == 3
        assert attributes[ATTR_ROWS_CHECKED] == 5000


class TestConstants:
    """Unit tests for tracing constants definition."""

    @pytest.mark.requirement("6C-FR-020")
    def test_tracer_name_constant(self) -> None:
        """Test that TRACER_NAME constant matches expected value.

        Validates the tracer name follows OpenTelemetry naming conventions.
        """
        assert TRACER_NAME == "floe.quality.dbt"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OpenTelemetry naming conventions.

        Validates that all attribute names use dot notation with a 'quality.'
        prefix as per OpenTelemetry semantic conventions.
        """
        attrs = [
            ATTR_OPERATION,
            ATTR_PROVIDER,
            ATTR_SUITE_NAME,
            ATTR_DATA_SOURCE,
            ATTR_CHECKS_COUNT,
            ATTR_PASS_COUNT,
            ATTR_FAIL_COUNT,
            ATTR_ROWS_CHECKED,
        ]
        for attr in attrs:
            assert attr.startswith("quality."), f"{attr} should start with 'quality.'"
            assert "." in attr, f"{attr} should use dot notation"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constant_values(self) -> None:
        """Test that attribute constants have correct values.

        Validates each attribute constant maps to the expected string.
        """
        assert ATTR_OPERATION == "quality.operation"
        assert ATTR_PROVIDER == "quality.provider"
        assert ATTR_SUITE_NAME == "quality.suite_name"
        assert ATTR_DATA_SOURCE == "quality.data_source"
        assert ATTR_CHECKS_COUNT == "quality.checks_count"
        assert ATTR_PASS_COUNT == "quality.pass_count"
        assert ATTR_FAIL_COUNT == "quality.fail_count"
        assert ATTR_ROWS_CHECKED == "quality.rows_checked"
