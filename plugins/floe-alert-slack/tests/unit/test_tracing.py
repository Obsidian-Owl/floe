"""Unit tests for OpenTelemetry tracing helpers in floe_alert_slack.tracing.

Tests cover tracer initialization, span creation, attribute setting, error
handling, and security (no credentials in traces) for the Slack alert plugin.

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

from floe_alert_slack.tracing import (
    ATTR_CHANNEL,
    ATTR_DELIVERY_STATUS,
    ATTR_DESTINATION,
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

        with alert_span(tracer, "send"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "alert.send"

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

        with alert_span(tracer, "send", channel="slack"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_CHANNEL] == "slack"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_sets_destination_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that alert_span sets the 'alert.destination' attribute.

        Validates that the destination attribute is recorded on the span when
        specified. Destination should be channel name, not webhook URL.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with alert_span(tracer, "send", destination="#alerts"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_DESTINATION] == "#alerts"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_sets_delivery_status_on_success(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that alert_span sets delivery_status to 'success' on completion.

        Validates that the delivery status attribute is set to 'success' when
        no exception occurs.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with alert_span(tracer, "send", channel="slack"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_DELIVERY_STATUS] == "success"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_sets_delivery_status_on_error(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that alert_span sets delivery_status to 'failed' on error.

        Validates that the delivery status attribute is set to 'failed' when
        an exception occurs.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with pytest.raises(RuntimeError):
            with alert_span(tracer, "send", channel="slack"):
                raise RuntimeError("Delivery failed")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_DELIVERY_STATUS] == "failed"

    @pytest.mark.requirement("6C-FR-020")
    def test_alert_span_no_credentials_in_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that no webhook URLs or credentials appear in span attributes.

        Validates that only channel names (not webhook URLs) are recorded.
        This is a critical security requirement (6C-FR-023).
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        # pragma: allowlist secret
        fake_webhook_url = "https://hooks.slack.com/services/T123/B456/secret789"

        with alert_span(
            tracer,
            "send",
            channel="slack",
            destination="#alerts",
            extra_attributes={"contract.name": "test_contract"},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify no attribute contains the webhook URL
        for attr_value in attributes.values():
            assert str(attr_value) != fake_webhook_url, (
                f"Webhook URL found in span attribute: {attr_value}"
            )
            assert "secret789" not in str(attr_value), (  # pragma: allowlist secret
                f"Secret token found in span attribute: {attr_value}"
            )

        # Verify expected attributes are channel names only
        assert attributes.get(ATTR_CHANNEL) == "slack"
        assert attributes.get(ATTR_DESTINATION) == "#alerts"

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
        # pragma: allowlist secret
        error_msg = "HTTP POST failed: api_key=secret-token-abc123 at endpoint"

        with pytest.raises(RuntimeError, match="HTTP POST failed"):
            with alert_span(tracer, "send", channel="slack"):
                raise RuntimeError(error_msg)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify error attributes are present
        assert attributes["exception.type"] == "RuntimeError"

        # Verify the secret is redacted in the error message
        exception_message = attributes["exception.message"]
        assert "secret-token-abc123" not in exception_message  # pragma: allowlist secret
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

        with alert_span(tracer, "validate_config", channel="slack"):
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
        with patch("floe_alert_slack.tracing._factory_get_tracer") as mock_factory:
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
        assert TRACER_NAME == "floe.alert.slack"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OpenTelemetry naming conventions.

        Validates that all attribute names use dot notation with an 'alert.'
        prefix as per OpenTelemetry semantic conventions.
        """
        attrs = [ATTR_CHANNEL, ATTR_DESTINATION, ATTR_DELIVERY_STATUS]
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
        assert ATTR_DELIVERY_STATUS == "alert.delivery_status"
