"""Unit tests for OpenTelemetry tracing helpers in floe_rbac_k8s.tracing.

Tests cover tracer initialization, span creation, attribute setting, error
sanitization, and status codes for the K8s RBAC security plugin.

Requirements Covered:
    - 6C-FR-020: OTel spans for RBAC security operations
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_rbac_k8s.tracing import (
    ATTR_OPERATION,
    ATTR_POLICY_TYPE,
    ATTR_RESOURCE_COUNT,
    TRACER_NAME,
    get_tracer,
    security_span,
)


@pytest.fixture
def tracer_with_exporter() -> tuple[object, InMemorySpanExporter]:
    """Create a tracer backed by an in-memory exporter for span inspection.

    Returns:
        Tuple of (tracer, exporter) where the exporter captures all finished
        spans for assertion.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(TRACER_NAME)
    return tracer, exporter


class TestSecuritySpan:
    """Unit tests for security_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: tuple[object, InMemorySpanExporter],
    ) -> None:
        """Test that security_span creates a span named 'security.{operation}'.

        Validates that the span name follows the security.{operation} convention
        used for RBAC security operations.
        """
        tracer, exporter = tracer_with_exporter

        with security_span(tracer, "generate_role"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "security.generate_role"

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_sets_policy_type_attribute(
        self,
        tracer_with_exporter: tuple[object, InMemorySpanExporter],
    ) -> None:
        """Test that security_span sets the security.policy_type attribute.

        Validates that the policy_type parameter is recorded as a span
        attribute for identifying the K8s resource type being generated.
        """
        tracer, exporter = tracer_with_exporter

        with security_span(tracer, "generate_role", policy_type="Role"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs[ATTR_POLICY_TYPE] == "Role"

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_sets_resource_count_attribute(
        self,
        tracer_with_exporter: tuple[object, InMemorySpanExporter],
    ) -> None:
        """Test that security_span sets the security.resource_count attribute.

        Validates that the resource_count parameter is recorded as a span
        attribute for tracking the number of resources involved.
        """
        tracer, exporter = tracer_with_exporter

        with security_span(tracer, "generate_role", resource_count=5):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs[ATTR_RESOURCE_COUNT] == 5

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_error_sanitized(
        self,
        tracer_with_exporter: tuple[object, InMemorySpanExporter],
    ) -> None:
        """Test that security_span sanitizes error messages containing credentials.

        Validates that sensitive information such as passwords in error messages
        is redacted before being recorded in span attributes (FR-049).
        """
        tracer, exporter = tracer_with_exporter

        with pytest.raises(RuntimeError, match="connection failed"):
            with security_span(tracer, "generate_role", policy_type="Role"):
                raise RuntimeError(
                    "connection failed password=supersecret123"  # pragma: allowlist secret
                )

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})

        # Error message should be sanitized - password value redacted
        error_msg = attrs["exception.message"]
        assert "supersecret123" not in error_msg  # pragma: allowlist secret
        assert "<REDACTED>" in error_msg
        assert attrs["exception.type"] == "RuntimeError"

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_ok_status_on_success(
        self,
        tracer_with_exporter: tuple[object, InMemorySpanExporter],
    ) -> None:
        """Test that security_span sets StatusCode.OK on successful completion.

        Validates that spans for operations that complete without error
        are marked with OK status code.
        """
        tracer, exporter = tracer_with_exporter

        with security_span(tracer, "generate_namespace", policy_type="Namespace"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK


class TestGetTracer:
    """Unit tests for get_tracer function."""

    @pytest.mark.requirement("6C-FR-020")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test that get_tracer returns an OpenTelemetry tracer instance.

        Validates that the function delegates to the factory with the
        correct RBAC tracer name constant.
        """
        # Patch via sys.modules to avoid __getattr__ in __init__.py on Python 3.10
        import floe_rbac_k8s.tracing as _tracing_mod

        with patch.object(_tracing_mod, "_factory_get_tracer") as mock_factory:
            mock_tracer = MagicMock()
            mock_factory.return_value = mock_tracer

            result = get_tracer()

            assert result is mock_tracer
            mock_factory.assert_called_once_with(TRACER_NAME)


class TestConstants:
    """Unit tests for tracing constants."""

    @pytest.mark.requirement("6C-FR-020")
    def test_tracer_name_value(self) -> None:
        """Test that TRACER_NAME has the correct value.

        Validates that the tracer name follows OpenTelemetry naming
        conventions for the RBAC security plugin.
        """
        assert TRACER_NAME == "floe.security.rbac"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_values(self) -> None:
        """Test that attribute constants have correct values.

        Validates that all security attribute name constants use
        dot notation with the security prefix.
        """
        assert ATTR_OPERATION == "security.operation"
        assert ATTR_POLICY_TYPE == "security.policy_type"
        assert ATTR_RESOURCE_COUNT == "security.resource_count"
