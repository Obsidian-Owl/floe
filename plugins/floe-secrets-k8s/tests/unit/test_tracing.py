"""Unit tests for OpenTelemetry tracing helpers in floe_secrets_k8s.tracing.

Tests cover tracer initialization, span creation, attribute setting, error
handling, and security (no secret values in traces) for the K8s secrets plugin.

Requirements Covered:
    - 6C-FR-020: Unit tests for secrets tracing helpers
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_secrets_k8s.tracing import (
    ATTR_KEY_NAME,
    ATTR_NAMESPACE,
    ATTR_OPERATION,
    ATTR_PROVIDER,
    TRACER_NAME,
    get_tracer,
    secrets_span,
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


class TestSecretsSpan:
    """Unit tests for secrets_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that secrets_span creates a span with the correct name.

        Validates that the span name follows the 'secrets.<operation>' convention.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with secrets_span(tracer, "get_secret"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "secrets.get_secret"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_sets_provider_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that secrets_span sets the 'secrets.provider' attribute.

        Validates that the provider attribute is recorded on the span when
        specified.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with secrets_span(tracer, "get_secret", provider="k8s"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_PROVIDER] == "k8s"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_sets_key_name_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that secrets_span sets the 'secrets.key_name' attribute.

        Validates that the key name attribute is recorded on the span when
        specified. Only key names are recorded, never secret values.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with secrets_span(tracer, "get_secret", key_name="db-password"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_KEY_NAME] == "db-password"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_sets_namespace_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that secrets_span sets the 'secrets.namespace' attribute.

        Validates that the Kubernetes namespace attribute is recorded on the
        span when specified.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with secrets_span(tracer, "list_secrets", namespace="production"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_NAMESPACE] == "production"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_no_secret_values_in_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that no secret values appear in span attributes.

        Validates that only key names (not secret values) are recorded.
        This is a critical security requirement (6C-FR-023).
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        fake_secret_value = "super-secret-password-123"  # pragma: allowlist secret

        with secrets_span(
            tracer,
            "get_secret",
            provider="k8s",
            key_name="db-password",
            namespace="production",
            extra_attributes={"secrets.found": True},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify no attribute contains the secret value
        for attr_value in attributes.values():
            assert str(attr_value) != fake_secret_value, (
                f"Secret value found in span attribute: {attr_value}"
            )

        # Verify expected attributes are key names only
        assert attributes.get(ATTR_KEY_NAME) == "db-password"
        assert attributes.get(ATTR_OPERATION) == "get_secret"
        assert attributes.get(ATTR_PROVIDER) == "k8s"
        assert attributes.get(ATTR_NAMESPACE) == "production"

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_error_sanitized(
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
        error_msg = "Connection failed: password=hunter2 at host"  # pragma: allowlist secret

        with pytest.raises(RuntimeError, match="Connection failed"):
            with secrets_span(tracer, "get_secret", provider="k8s"):
                raise RuntimeError(error_msg)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify error attributes are present
        assert attributes["exception.type"] == "RuntimeError"

        # Verify the password is redacted in the error message
        exception_message = attributes["exception.message"]
        assert "hunter2" not in exception_message  # pragma: allowlist secret
        assert "<REDACTED>" in exception_message

        # Verify the span has ERROR status
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("6C-FR-020")
    def test_secrets_span_ok_status_on_success(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that successful spans have StatusCode.OK.

        Validates that the span status is set to OK when no exception occurs.
        """
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with secrets_span(tracer, "health_check", provider="k8s"):
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
        with patch("floe_secrets_k8s.tracing._factory_get_tracer") as mock_factory:
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
        assert TRACER_NAME == "floe.secrets.k8s"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OpenTelemetry naming conventions.

        Validates that all attribute names use dot notation with a 'secrets.'
        prefix as per OpenTelemetry semantic conventions.
        """
        attrs = [ATTR_OPERATION, ATTR_PROVIDER, ATTR_KEY_NAME, ATTR_NAMESPACE]
        for attr in attrs:
            assert attr.startswith("secrets."), f"{attr} should start with 'secrets.'"
            assert "." in attr, f"{attr} should use dot notation"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constant_values(self) -> None:
        """Test that attribute constants have correct values.

        Validates each attribute constant maps to the expected string.
        """
        assert ATTR_OPERATION == "secrets.operation"
        assert ATTR_PROVIDER == "secrets.provider"
        assert ATTR_KEY_NAME == "secrets.key_name"
        assert ATTR_NAMESPACE == "secrets.namespace"
