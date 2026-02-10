"""Unit tests for Infisical secrets plugin tracing module.

Tests the OpenTelemetry tracing utilities provided by
floe_secrets_infisical.tracing, including secrets_span context manager,
get_tracer factory, record_result helper, and attribute constants.

Requirements Covered:
    - 6C-FR-020: OTel spans for secrets operations
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_secrets_infisical.tracing import (
    ATTR_KEY_NAME,
    ATTR_OPERATION,
    ATTR_PROVIDER,
    TRACER_NAME,
    get_tracer,
    record_result,
    secrets_span,
)

if TYPE_CHECKING:
    pass


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    """In-memory span exporter for capturing spans in tests.

    Returns:
        InMemorySpanExporter instance for assertion.
    """
    return InMemorySpanExporter()


@pytest.fixture
def tracer_with_exporter(
    span_exporter: InMemorySpanExporter,
) -> trace.Tracer:
    """Tracer backed by in-memory exporter for test assertions.

    Args:
        span_exporter: The in-memory exporter to attach.

    Returns:
        OpenTelemetry Tracer instance with in-memory export.
    """
    provider = TracerProvider(resource=Resource.create({}))
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    return provider.get_tracer("test.secrets.infisical")


class TestSecretsSpan:
    """Test suite for secrets_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test secrets_span creates a span named 'secrets.{operation}'.

        Verifies the span naming convention follows the pattern
        'secrets.<operation>' for all secrets operations.
        """
        with secrets_span(tracer_with_exporter, "get_secret"):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "secrets.get_secret"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_sets_provider_attribute(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test secrets_span sets the 'secrets.provider' attribute.

        Verifies the provider attribute is recorded on the span
        when specified.
        """
        with secrets_span(
            tracer_with_exporter, "get_secret", provider="infisical"
        ):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs[ATTR_PROVIDER] == "infisical"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_sets_key_name_attribute(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test secrets_span sets the 'secrets.key_name' attribute.

        Verifies the key name (NOT the secret value) is recorded
        on the span for traceability.
        """
        with secrets_span(
            tracer_with_exporter,
            "get_secret",
            provider="infisical",
            key_name="db-password",
        ):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs[ATTR_KEY_NAME] == "db-password"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_no_secret_values_in_attributes(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test that no secret values appear in span attributes.

        Security check: only key names and metadata should be in
        span attributes, never actual secret values.
        """
        secret_value = "super-secret-password-12345"  # noqa: S105
        with secrets_span(
            tracer_with_exporter,
            "get_secret",
            provider="infisical",
            key_name="db-password",
            extra_attributes={"secrets.path": "/production/db"},
        ) as span:
            # Simulate recording result without the value
            record_result(span, found=True)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None

        # Verify no attribute contains the secret value
        for attr_value in attrs.values():
            assert secret_value not in str(attr_value)

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_error_sanitized(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test that exception messages are sanitized in span attributes.

        Verifies that sensitive data like passwords in error messages
        are redacted before being recorded on the span.
        """
        with pytest.raises(RuntimeError):
            with secrets_span(
                tracer_with_exporter,
                "get_secret",
                provider="infisical",
                key_name="db-password",
            ):
                raise RuntimeError(
                    "Connection failed: password=secret123 at host"  # pragma: allowlist secret
                )

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs["exception.type"] == "RuntimeError"
        exc_msg = attrs["exception.message"]
        assert isinstance(exc_msg, str)
        assert "secret123" not in exc_msg  # pragma: allowlist secret
        assert "<REDACTED>" in exc_msg

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_ok_status_on_success(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test that secrets_span sets OK status on successful completion.

        Verifies the span status is set to OK when no exception occurs
        within the context manager.
        """
        with secrets_span(
            tracer_with_exporter,
            "get_secret",
            provider="infisical",
        ):
            pass  # Happy path

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_error_status_on_exception(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test that secrets_span sets ERROR status when exception raised.

        Verifies the span status is set to ERROR and the exception
        propagates normally.
        """
        with pytest.raises(ValueError, match="test error"):
            with secrets_span(
                tracer_with_exporter,
                "set_secret",
                provider="infisical",
            ):
                raise ValueError("test error")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_sets_operation_attribute(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test that secrets_span sets the operation attribute.

        Verifies the 'secrets.operation' attribute is always set
        with the operation name.
        """
        with secrets_span(tracer_with_exporter, "delete_secret"):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs[ATTR_OPERATION] == "delete_secret"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_extra_attributes(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test that extra_attributes are merged into span attributes.

        Verifies custom attributes passed via extra_attributes
        appear on the finished span.
        """
        with secrets_span(
            tracer_with_exporter,
            "list_secrets",
            provider="infisical",
            extra_attributes={"secrets.path": "/production", "secrets.prefix": "db-"},
        ):
            pass

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs["secrets.path"] == "/production"
        assert attrs["secrets.prefix"] == "db-"


class TestGetTracer:
    """Test suite for get_tracer factory function."""

    @pytest.mark.requirement("6C-FR-020")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test that get_tracer returns a valid Tracer instance.

        Verifies the factory function returns an object conforming
        to the OpenTelemetry Tracer interface.
        """
        tracer = get_tracer()
        assert tracer is not None
        # Verify it has the start_as_current_span method (Tracer interface)
        assert hasattr(tracer, "start_as_current_span")

    @pytest.mark.requirement("6C-FR-020")
    def test_tracer_name_constant(self) -> None:
        """Test that TRACER_NAME follows naming conventions.

        Verifies the tracer name constant matches the expected
        OpenTelemetry naming pattern for this plugin.
        """
        assert TRACER_NAME == "floe.secrets.infisical"


class TestRecordResult:
    """Test suite for record_result helper function."""

    @pytest.mark.requirement("6C-FR-020")
    def test_record_result_sets_found_attribute(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test record_result sets the 'secrets.found' attribute.

        Verifies the found attribute is recorded correctly for
        get_secret result tracking.
        """
        with secrets_span(tracer_with_exporter, "get_secret") as span:
            record_result(span, found=True)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs["secrets.found"] is True

    @pytest.mark.requirement("6C-FR-020")
    def test_record_result_sets_count_attribute(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test record_result sets the 'secrets.count' attribute.

        Verifies the count attribute is recorded correctly for
        list_secrets result tracking.
        """
        with secrets_span(tracer_with_exporter, "list_secrets") as span:
            record_result(span, count=5)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs["secrets.count"] == 5

    @pytest.mark.requirement("6C-FR-020")
    def test_record_result_sets_operation_type(
        self,
        tracer_with_exporter: trace.Tracer,
        span_exporter: InMemorySpanExporter,
    ) -> None:
        """Test record_result sets the 'secrets.operation_type' attribute.

        Verifies the operation_type attribute is recorded for
        distinguishing create vs update in set_secret.
        """
        with secrets_span(tracer_with_exporter, "set_secret") as span:
            record_result(span, operation_type="create")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs is not None
        assert attrs["secrets.operation_type"] == "create"
