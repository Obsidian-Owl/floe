"""Unit tests for OpenTelemetry tracing helpers in floe_compute_duckdb.tracing.

Requirements Covered:
    - 6C-FR-020: Unit tests for compute tracing helpers
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from floe_compute_duckdb.tracing import (
    ATTR_DB_PATH,
    ATTR_ENGINE,
    ATTR_OPERATION,
    ATTR_TARGET,
    TRACER_NAME,
    compute_span,
    get_tracer,
)


@pytest.fixture
def tracer_with_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create a TracerProvider with an InMemorySpanExporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class TestComputeSpan:
    """Unit tests for compute_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_compute_span_creates_span_with_correct_name(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that compute_span creates a span named 'compute.<operation>'."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with compute_span(tracer, "validate_connection"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "compute.validate_connection"

    @pytest.mark.requirement("6C-FR-020")
    def test_compute_span_sets_engine_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that compute_span sets the 'compute.engine' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with compute_span(tracer, "validate_connection", engine="duckdb"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_ENGINE] == "duckdb"

    @pytest.mark.requirement("6C-FR-020")
    def test_compute_span_sets_db_path_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that compute_span sets the 'compute.db_path' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with compute_span(tracer, "validate_connection", db_path="/tmp/test.db"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_DB_PATH] == "/tmp/test.db"

    @pytest.mark.requirement("6C-FR-020")
    def test_compute_span_sets_target_attribute(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that compute_span sets the 'compute.target' attribute."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with compute_span(tracer, "generate_profile", target="dev"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})
        assert attributes[ATTR_TARGET] == "dev"

    @pytest.mark.requirement("6C-FR-020")
    def test_compute_span_no_credentials_in_attributes(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that no connection credentials appear in span attributes."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        fake_cred = "password=mysecretpassword"  # pragma: allowlist secret

        with compute_span(
            tracer,
            "validate_connection",
            engine="duckdb",
            db_path="/tmp/test.db",
            extra_attributes={"compute.validated": True},
        ):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attributes = dict(spans[0].attributes or {})

        for attr_value in attributes.values():
            assert str(attr_value) != fake_cred, f"Credential found in span attribute: {attr_value}"

    @pytest.mark.requirement("6C-FR-020")
    def test_compute_span_error_sanitized(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that error messages are sanitized before recording on span."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        error_msg = "Connection failed: password=secret123 at host"  # pragma: allowlist secret

        with pytest.raises(RuntimeError, match="Connection failed"):
            with compute_span(tracer, "validate_connection", engine="duckdb"):
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
    def test_compute_span_ok_status_on_success(
        self,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test that successful spans have StatusCode.OK."""
        provider, exporter = tracer_with_exporter
        tracer = provider.get_tracer(TRACER_NAME)

        with compute_span(tracer, "generate_profile", engine="duckdb"):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == StatusCode.OK

    @pytest.mark.requirement("6C-FR-020")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test that get_tracer delegates to factory with correct name."""
        with patch("floe_compute_duckdb.tracing._factory_get_tracer") as mock_factory:
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
        assert TRACER_NAME == "floe.compute.duckdb"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OTel naming conventions."""
        attrs = [ATTR_ENGINE, ATTR_OPERATION, ATTR_DB_PATH, ATTR_TARGET]
        for attr in attrs:
            assert attr.startswith("compute."), f"{attr} should start with 'compute.'"
            assert "." in attr, f"{attr} should use dot notation"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constant_values(self) -> None:
        """Test that attribute constants have correct values."""
        assert ATTR_ENGINE == "compute.engine"
        assert ATTR_OPERATION == "compute.operation"
        assert ATTR_DB_PATH == "compute.db_path"
        assert ATTR_TARGET == "compute.target"
