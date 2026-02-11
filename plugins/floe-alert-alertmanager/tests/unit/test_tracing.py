"""Unit tests for OpenTelemetry tracing helpers in floe_alert_alertmanager.tracing.

Tests cover tracer initialization, span creation, attribute setting, error
handling, and security (no alert content in traces) for the Alertmanager
alert plugin.

Requirements Covered:
    - 6C-FR-020: Unit tests for alert tracing helpers
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_alert_alertmanager.tracing import (
    ATTR_CHANNEL,
    ATTR_DELIVERY_STATUS,
    ATTR_DESTINATION,
    ATTR_SEVERITY,
    TRACER_NAME,
    alert_span,
    get_tracer,
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


class TestAlertSpan:
    """Unit tests for alert_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that alert_span creates a span with the correct name.

        Validates that the span name follows the 'alert.<operation>' convention.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with alert_span(tracer, "send_alert"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "alert.send_alert"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_sets_channel_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that alert_span sets the 'alert.channel' attribute.

        Validates that the channel attribute is recorded on the span when
        specified.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with alert_span(tracer, "send_alert", channel="alertmanager"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_CHANNEL] == "alertmanager"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_sets_destination_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that alert_span sets the 'alert.destination' attribute.

        Validates that the destination attribute is recorded on the span when
        specified.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with alert_span(
            tracer,
            "send_alert",
            destination="https://alertmanager:9093",
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_DESTINATION] == "https://alertmanager:9093"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_sets_severity_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that alert_span sets the 'alert.severity' attribute.

        Validates that the severity attribute is recorded on the span when
        specified.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with alert_span(tracer, "send_alert", severity="critical"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_SEVERITY] == "critical"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_no_alert_content_in_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that no alert content appears in span attributes.

        Validates that only metadata (not alert content) is recorded.
        This is a critical security requirement (6C-FR-023).
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        fake_alert_content = "CRITICAL: Database password compromised"  # pragma: allowlist secret

        with alert_span(
            tracer,
            "send_alert",
            channel="alertmanager",
            destination="https://alertmanager:9093",
            severity="critical",
            extra_attributes={"alert.delivered": True},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify no attribute contains the alert content
        for attr_value in attributes.values():
            assert str(attr_value) != fake_alert_content, (
                f"Alert content found in span attribute: {attr_value}"
            )

        # Verify expected attributes are metadata only
        assert attributes.get(ATTR_CHANNEL) == "alertmanager"
        assert attributes.get(ATTR_DESTINATION) == "https://alertmanager:9093"
        assert attributes.get(ATTR_SEVERITY) == "critical"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_error_sanitized(
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
        error_msg = "Connection failed: api_key=secret123 at host"  # pragma: allowlist secret

        with pytest.raises(RuntimeError, match="Connection failed"):
            with alert_span(tracer, "send_alert", channel="alertmanager"):
                raise RuntimeError(error_msg)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify error attributes are present
        assert attributes["exception.type"] == "RuntimeError"

        # Verify the api_key is redacted in the error message
        exception_message = attributes["exception.message"]
        assert "secret123" not in exception_message  # pragma: allowlist secret
        assert "<REDACTED>" in exception_message

        # Verify the span has ERROR status
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_ok_status_on_success(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that successful spans have StatusCode.OK.

        Validates that the span status is set to OK when no exception occurs.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with alert_span(tracer, "validate_config", channel="alertmanager"):
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
        with patch("floe_alert_alertmanager.tracing._factory_get_tracer") as mock_factory:
            from unittest.mock import MagicMock

            mock_tracer = MagicMock()
            mock_factory.return_value = mock_tracer

            result = get_tracer()

            assert result is mock_tracer
            mock_factory.assert_called_once_with(TRACER_NAME)


class TestConstants:
    """Unit tests for tracing constants definition."""

    @pytest.mark.requirement("6C-FR-020")
    def test_tracer_name_constant(self) -> None:
        """Test that TRACER_NAME constant matches expected value.

        Validates the tracer name follows OpenTelemetry naming conventions.
        """
        assert TRACER_NAME == "floe.alert.alertmanager"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OpenTelemetry naming conventions.

        Validates that all attribute names use dot notation with an 'alert.'
        prefix as per OpenTelemetry semantic conventions.
        """
        attrs = [ATTR_CHANNEL, ATTR_DESTINATION, ATTR_SEVERITY, ATTR_DELIVERY_STATUS]
        for attr in attrs:
            assert attr.startswith("alert."), f"{attr} should start with 'alert.'"
            assert "." in attr, f"{attr} should use dot notation"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constant_values(self) -> None:
        """Test that attribute constants have correct values.

        Validates each attribute constant maps to the expected string.
        """
        assert ATTR_CHANNEL == "alert.channel"
        assert ATTR_DESTINATION == "alert.destination"
        assert ATTR_SEVERITY == "alert.severity"
        assert ATTR_DELIVERY_STATUS == "alert.delivery_status"
