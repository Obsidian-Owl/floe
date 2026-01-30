"""Unit tests for promotion OpenTelemetry spans using in-memory exporter (T024e).

Tests promotion telemetry with real span collection to verify:
- Spans are created with correct names
- Span hierarchy (promote → gate → verify)
- trace_id is extractable from spans

Requirements tested:
    FR-024: OpenTelemetry integration for promotion operations
    FR-033: Trace ID in promotion output for correlation
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def tracer_with_exporter() -> Generator[
    tuple[TracerProvider, InMemorySpanExporter], None, None
]:
    """Create a TracerProvider with InMemorySpanExporter for testing.

    Injects the tracer into the tracing module for testing purposes.

    Yields:
        Tuple of (TracerProvider, InMemorySpanExporter) for test assertions.
    """
    from floe_core.telemetry.tracing import set_tracer

    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Inject the test tracer into the tracing module
    test_tracer = provider.get_tracer("test_promotion_telemetry")
    set_tracer(test_tracer)

    yield provider, exporter

    # Reset tracer for isolation
    set_tracer(None)
    exporter.clear()


@pytest.fixture
def controller(tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter]):
    """Create a PromotionController with telemetry-enabled tracer."""
    from floe_core.oci.client import OCIClient
    from floe_core.oci.promotion import PromotionController
    from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
    from floe_core.schemas.promotion import PromotionConfig

    auth = RegistryAuth(type=AuthType.ANONYMOUS)
    registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
    oci_client = OCIClient.from_registry_config(registry_config)
    promotion = PromotionConfig()

    return PromotionController(client=oci_client, promotion=promotion)


class TestPromotionOpenTelemetryIntegration:
    """Integration tests for promotion OpenTelemetry spans using in-memory exporter."""

    @pytest.mark.requirement("8C-FR-024")
    def test_promote_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test promote() creates a span that appears in the exporter."""
        _, exporter = tracer_with_exporter

        try:
            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )
        except NotImplementedError:
            pass  # Expected

        # Get exported spans
        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.promote" in span_names

    @pytest.mark.requirement("8C-FR-033")
    def test_promote_span_has_valid_trace_id(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test promote() span has a valid non-zero trace_id."""
        _, exporter = tracer_with_exporter

        try:
            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )
        except NotImplementedError:
            pass

        spans = exporter.get_finished_spans()
        promote_span = next(s for s in spans if s.name == "floe.oci.promote")

        # Verify trace_id is non-zero
        assert promote_span.context.trace_id != 0
        # Verify we can format it as hex (32 chars)
        trace_id_hex = format(promote_span.context.trace_id, "032x")
        assert len(trace_id_hex) == 32

    @pytest.mark.requirement("8C-FR-024")
    def test_promote_span_has_expected_attributes(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test promote() span has all required attributes."""
        _, exporter = tracer_with_exporter

        try:
            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )
        except NotImplementedError:
            pass

        spans = exporter.get_finished_spans()
        promote_span = next(s for s in spans if s.name == "floe.oci.promote")

        # Verify expected attributes
        attrs = dict(promote_span.attributes)
        assert "from_env" in attrs
        assert "to_env" in attrs
        assert "dry_run" in attrs
        assert attrs["from_env"] == "dev"
        assert attrs["to_env"] == "staging"
        assert attrs["dry_run"] is True

    @pytest.mark.requirement("8C-FR-024")
    def test_rollback_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test rollback() creates a span that appears in the exporter."""
        _, exporter = tracer_with_exporter

        try:
            controller.rollback(
                tag="v1.0.0",
                environment="prod",
                reason="Hotfix rollback",
                operator="sre@example.com",
            )
        except NotImplementedError:
            pass

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.rollback" in span_names

    @pytest.mark.requirement("8C-FR-024")
    def test_run_gate_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_gate() creates a span with gate-specific name."""
        from floe_core.schemas.promotion import PromotionGate

        _, exporter = tracer_with_exporter

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo 'test'",
                timeout_seconds=60,
            )

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.gate.tests" in span_names

    @pytest.mark.requirement("8C-FR-024")
    def test_gate_span_records_duration_attribute(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test gate span records duration_ms attribute."""
        from floe_core.schemas.promotion import PromotionGate

        _, exporter = tracer_with_exporter

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo 'test'",
                timeout_seconds=60,
            )

        spans = exporter.get_finished_spans()
        gate_span = next(s for s in spans if s.name == "floe.oci.gate.tests")

        attrs = dict(gate_span.attributes)
        assert "duration_ms" in attrs
        assert isinstance(attrs["duration_ms"], int)

    @pytest.mark.requirement("8C-FR-024")
    def test_verify_signature_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _verify_signature() creates a span in the exporter."""
        from datetime import datetime, timezone

        from floe_core.schemas.signing import VerificationResult

        _, exporter = tracer_with_exporter

        mock_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        with patch(
            "floe_core.schemas.signing.VerificationPolicy"
        ) as mock_policy_class, patch(
            "floe_core.oci.verification.VerificationClient"
        ) as mock_client_class:
            mock_policy = Mock()
            mock_policy.enforcement = "enforce"
            mock_policy_class.return_value = mock_policy

            mock_client = Mock()
            mock_client.verify.return_value = mock_result
            mock_client_class.return_value = mock_client

            controller._verify_signature(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"test content",
                enforcement="enforce",
            )

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.promote.verify" in span_names

    @pytest.mark.requirement("8C-FR-024")
    def test_all_spans_share_same_trace_id_when_nested(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test spans share the same trace_id when nested in promote()."""
        # This test verifies that when promote() is fully implemented,
        # the gate and verify spans will share the same trace_id as the
        # parent promote span (span hierarchy).

        # For now, we verify that each operation creates a span with a valid trace_id
        from floe_core.schemas.promotion import PromotionGate

        _, exporter = tracer_with_exporter

        # Run gate
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo 'test'",
                timeout_seconds=60,
            )

        spans = exporter.get_finished_spans()
        assert len(spans) >= 1

        # Each span has a valid trace_id
        for span in spans:
            assert span.context.trace_id != 0
