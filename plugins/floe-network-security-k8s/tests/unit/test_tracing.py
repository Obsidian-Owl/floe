"""Unit tests for OpenTelemetry tracing helpers in floe_network_security_k8s.tracing.

Requirements Covered:
    - 6C-FR-020: Unit tests for security tracing helpers
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_network_security_k8s.tracing import (
    ATTR_NAMESPACE,
    ATTR_POLICY_TYPE,
    ATTR_PSS_LEVEL,
    ATTR_RESOURCE_COUNT,
    TRACER_NAME,
    get_tracer,
    security_span,
)


@pytest.fixture
def tracer_with_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create a TracerProvider with an InMemorySpanExporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestSecuritySpan:
    """Unit tests for security_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that security_span creates a span named 'security.<operation>'."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with security_span(tracer, "generate_network_policy"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "security.generate_network_policy"

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_sets_policy_type_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that security_span sets the 'security.policy_type' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with security_span(tracer, "generate_network_policy", policy_type="NetworkPolicy"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_POLICY_TYPE] == "NetworkPolicy"

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_sets_resource_count_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that security_span sets the 'security.resource_count' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with security_span(tracer, "generate_default_deny", resource_count=3):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_RESOURCE_COUNT] == 3

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_sets_namespace_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that security_span sets the 'security.namespace' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with security_span(tracer, "generate_network_policy", namespace="floe-prod"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_NAMESPACE] == "floe-prod"

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_sets_pss_level_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that security_span sets the 'security.pss_level' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with security_span(tracer, "generate_pss_labels", pss_level="restricted"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_PSS_LEVEL] == "restricted"

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_no_sensitive_data_in_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that no sensitive policy details appear in span attributes."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with security_span(
            tracer,
            "generate_network_policy",
            policy_type="NetworkPolicy",
            namespace="floe-prod",
            resource_count=2,
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        # Verify no CIDR blocks or IP addresses in attributes
        for attr_key, attr_value in attributes.items():
            if attr_value is not None and isinstance(attr_value, str):
                assert "10.0.0" not in attr_value, f"Attribute {attr_key} contains sensitive CIDR"
                assert "192.168" not in attr_value, f"Attribute {attr_key} contains sensitive CIDR"

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_error_sanitized(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that error messages are sanitized before recording on span."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        error_msg = "Policy failed: token=secret123 at cluster"  # pragma: allowlist secret

        with pytest.raises(RuntimeError, match="Policy failed"):
            with security_span(tracer, "generate_network_policy"):
                raise RuntimeError(error_msg)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        assert attributes["exception.type"] == "RuntimeError"
        exception_message = str(attributes["exception.message"])
        assert "secret123" not in exception_message  # pragma: allowlist secret
        assert "<REDACTED>" in exception_message
        assert spans[0].status.status_code == StatusCode.ERROR

    @pytest.mark.requirement("6C-FR-020")
    def test_security_span_ok_status_on_success(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that successful spans have StatusCode.OK."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with security_span(tracer, "generate_pss_labels"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    @pytest.mark.requirement("6C-FR-020")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test that get_tracer delegates to factory with correct name."""
        with patch("floe_network_security_k8s.tracing._factory_get_tracer") as mock_factory:
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
        """Test that TRACER_NAME follows naming convention."""
        assert TRACER_NAME == "floe.security.network"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OTel naming conventions."""
        attrs = [ATTR_POLICY_TYPE, ATTR_RESOURCE_COUNT, ATTR_NAMESPACE, ATTR_PSS_LEVEL]
        for attr in attrs:
            assert attr.startswith("security."), f"{attr} should start with 'security.'"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constant_values(self) -> None:
        """Test that attribute constants have correct values."""
        assert ATTR_POLICY_TYPE == "security.policy_type"
        assert ATTR_RESOURCE_COUNT == "security.resource_count"
        assert ATTR_NAMESPACE == "security.namespace"
        assert ATTR_PSS_LEVEL == "security.pss_level"
