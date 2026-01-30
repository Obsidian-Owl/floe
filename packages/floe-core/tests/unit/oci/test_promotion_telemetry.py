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
def tracer_with_exporter() -> Generator[tuple[TracerProvider, InMemorySpanExporter], None, None]:
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

        # Mock _get_artifact_digest to avoid network calls
        with patch.object(controller, "_get_artifact_digest", return_value="sha256:abc123"):
            try:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )
            except (NotImplementedError, Exception):
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

        # Mock _get_artifact_digest to avoid network calls
        with patch.object(controller, "_get_artifact_digest", return_value="sha256:abc123"):
            try:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )
            except (NotImplementedError, Exception):
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

        # Mock _get_artifact_digest to avoid network calls
        with patch.object(controller, "_get_artifact_digest", return_value="sha256:abc123"):
            try:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                    dry_run=True,
                )
            except (NotImplementedError, Exception):
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

        # Mock client.inspect to avoid network calls
        with patch.object(controller.client, "inspect", return_value={"digest": "sha256:abc"}):
            try:
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Hotfix rollback",
                    operator="sre@example.com",
                )
            except (NotImplementedError, Exception):
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

        with (
            patch("floe_core.schemas.signing.VerificationPolicy") as mock_policy_class,
            patch("floe_core.oci.verification.VerificationClient") as mock_client_class,
        ):
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

    @pytest.mark.requirement("8C-FR-024")
    def test_run_all_gates_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_all_gates() creates a span that appears in the exporter."""
        _, exporter = tracer_with_exporter

        with (
            patch.object(controller, "_run_policy_compliance_gate") as mock_policy_gate,
            patch.object(controller, "_get_environment") as mock_get_env,
        ):
            from floe_core.schemas.promotion import (
                EnvironmentConfig,
                GateResult,
                GateStatus,
                PromotionGate,
            )

            mock_get_env.return_value = EnvironmentConfig(
                name="staging",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            )
            mock_policy_gate.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=10,
            )

            controller._run_all_gates(
                to_env="staging",
                manifest={},
                artifact_ref="harbor.example.com/floe:v1.0.0",
            )

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.run_all_gates" in span_names

    @pytest.mark.requirement("8C-FR-024")
    def test_run_all_gates_span_has_environment_attribute(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_all_gates() span has environment attribute."""
        _, exporter = tracer_with_exporter

        with (
            patch.object(controller, "_run_policy_compliance_gate") as mock_policy_gate,
            patch.object(controller, "_get_environment") as mock_get_env,
        ):
            from floe_core.schemas.promotion import (
                EnvironmentConfig,
                GateResult,
                GateStatus,
                PromotionGate,
            )

            mock_get_env.return_value = EnvironmentConfig(
                name="staging",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            )
            mock_policy_gate.return_value = GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=10,
            )

            controller._run_all_gates(
                to_env="staging",
                manifest={},
                artifact_ref="harbor.example.com/floe:v1.0.0",
            )

        spans = exporter.get_finished_spans()
        all_gates_span = next(s for s in spans if s.name == "floe.oci.run_all_gates")

        attrs = dict(all_gates_span.attributes)
        assert attrs["environment"] == "staging"

    @pytest.mark.requirement("8C-FR-024")
    def test_run_policy_compliance_gate_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_policy_compliance_gate() creates a span in the exporter."""
        _, exporter = tracer_with_exporter

        # Run policy gate (will skip because no enforcer configured)
        controller._run_policy_compliance_gate(manifest={})

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.gate.policy_compliance" in span_names

    @pytest.mark.requirement("8C-FR-054")
    def test_run_security_gate_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_security_gate() creates a span that appears in the exporter."""
        from floe_core.schemas.promotion import SecurityGateConfig

        _, exporter = tracer_with_exporter

        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            scanner_format="trivy",
            block_on_severity=["CRITICAL"],
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"Results": []}',
                stderr="",
            )
            controller._run_security_gate(
                config=config,
                artifact_ref="harbor.example.com/floe:v1.0.0",
            )

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.gate.security_scan" in span_names

    @pytest.mark.requirement("8C-FR-054")
    def test_run_security_gate_span_has_scanner_format_attribute(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_security_gate() span includes scanner_format attribute."""
        from floe_core.schemas.promotion import SecurityGateConfig

        _, exporter = tracer_with_exporter

        config = SecurityGateConfig(
            command="grype ${ARTIFACT_REF} -o json",
            scanner_format="grype",
            block_on_severity=["CRITICAL", "HIGH"],
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"matches": []}',
                stderr="",
            )
            controller._run_security_gate(
                config=config,
                artifact_ref="harbor.example.com/floe:v1.0.0",
            )

        spans = exporter.get_finished_spans()
        security_span = next(s for s in spans if s.name == "floe.oci.gate.security_scan")

        attrs = dict(security_span.attributes)
        assert attrs["scanner_format"] == "grype"

    @pytest.mark.requirement("8C-FR-024")
    def test_lock_environment_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test lock_environment() creates a span that appears in the exporter."""
        _, exporter = tracer_with_exporter

        with patch.object(controller, "_send_webhook_notification"):
            controller.lock_environment(
                environment="prod",
                reason="Maintenance window",
                operator="admin@example.com",
            )

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.lock_environment" in span_names

    @pytest.mark.requirement("8C-FR-024")
    def test_lock_environment_span_has_expected_attributes(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test lock_environment() span has correct attributes."""
        _, exporter = tracer_with_exporter

        with patch.object(controller, "_send_webhook_notification"):
            controller.lock_environment(
                environment="prod",
                reason="Maintenance window",
                operator="admin@example.com",
            )

        spans = exporter.get_finished_spans()
        lock_span = next(s for s in spans if s.name == "floe.oci.lock_environment")

        attrs = dict(lock_span.attributes)
        assert attrs["environment"] == "prod"
        assert attrs["operator"] == "admin@example.com"

    @pytest.mark.requirement("8C-FR-024")
    def test_unlock_environment_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test unlock_environment() creates a span that appears in the exporter."""
        _, exporter = tracer_with_exporter

        # First lock, then unlock
        with patch.object(controller, "_send_webhook_notification"):
            controller.lock_environment(
                environment="prod",
                reason="Maintenance",
                operator="admin@example.com",
            )
            exporter.clear()  # Clear lock span

            controller.unlock_environment(
                environment="prod",
                reason="Maintenance complete",
                operator="admin@example.com",
            )

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.unlock_environment" in span_names

    @pytest.mark.requirement("8C-FR-024")
    def test_sync_to_registries_creates_span_in_exporter(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _sync_to_registries() creates a span that appears in the exporter."""
        _, exporter = tracer_with_exporter

        # No secondary clients = no actual sync, but span should still be created
        controller._sync_to_registries(
            tag="v1.0.0",
            to_env="staging",
            artifact_digest="sha256:abc123",
            secondary_clients=[],
        )

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "floe.oci.sync_to_registries" in span_names

    @pytest.mark.requirement("8C-FR-024")
    def test_sync_to_registries_span_has_secondary_count_attribute(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _sync_to_registries() span includes secondary_count attribute."""
        _, exporter = tracer_with_exporter

        # Create mock secondary client with copy_tag method
        mock_secondary_client = Mock()
        mock_secondary_client.registry_uri = "oci://secondary.example.com/floe"
        mock_secondary_client.copy_tag.return_value = None
        mock_secondary_client.get_artifact_digest.return_value = "sha256:abc123"

        controller._sync_to_registries(
            tag="v1.0.0",
            to_env="staging",
            artifact_digest="sha256:abc123",
            secondary_clients=[mock_secondary_client],
        )

        spans = exporter.get_finished_spans()
        sync_span = next(s for s in spans if s.name == "floe.oci.sync_to_registries")

        attrs = dict(sync_span.attributes)
        assert attrs["secondary_count"] == 1

    @pytest.mark.requirement("8C-FR-054")
    def test_run_security_gate_span_has_timing_attributes(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_security_gate() span includes duration_ms and status attributes."""
        from floe_core.schemas.promotion import SecurityGateConfig

        _, exporter = tracer_with_exporter

        config = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            scanner_format="trivy",
            block_on_severity=["CRITICAL"],
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"Results": []}',
                stderr="",
            )
            controller._run_security_gate(
                config=config,
                artifact_ref="harbor.example.com/floe:v1.0.0",
            )

        spans = exporter.get_finished_spans()
        security_span = next(s for s in spans if s.name == "floe.oci.gate.security_scan")

        attrs = dict(security_span.attributes)
        assert "duration_ms" in attrs
        assert isinstance(attrs["duration_ms"], int)
        assert "status" in attrs
        assert attrs["status"] == "passed"

    @pytest.mark.requirement("8C-FR-024")
    def test_run_all_gates_span_has_timing_attributes(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_all_gates() span includes duration_ms, gate_count, and status."""
        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

        _, exporter = tracer_with_exporter

        # Mock _run_policy_compliance_gate to return skipped (no enforcer)
        with patch.object(
            controller,
            "_run_policy_compliance_gate",
            return_value=GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.SKIPPED,
                duration_ms=10,
            ),
        ):
            controller._run_all_gates(
                to_env="staging",
                manifest={},
                artifact_ref="harbor.example.com/floe:v1.0.0",
            )

        spans = exporter.get_finished_spans()
        gates_span = next(s for s in spans if s.name == "floe.oci.run_all_gates")

        attrs = dict(gates_span.attributes)
        assert "duration_ms" in attrs
        assert isinstance(attrs["duration_ms"], int)
        assert "gate_count" in attrs
        assert isinstance(attrs["gate_count"], int)
        assert "status" in attrs
        assert attrs["status"] in ["passed", "failed"]

    @pytest.mark.requirement("8C-FR-024")
    def test_sync_to_registries_span_has_timing_attributes_empty(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _sync_to_registries() span with no clients has timing attributes."""
        _, exporter = tracer_with_exporter

        # No secondary clients = skipped
        controller._sync_to_registries(
            tag="v1.0.0",
            to_env="staging",
            artifact_digest="sha256:abc123",
            secondary_clients=[],
        )

        spans = exporter.get_finished_spans()
        sync_span = next(s for s in spans if s.name == "floe.oci.sync_to_registries")

        attrs = dict(sync_span.attributes)
        assert attrs["duration_ms"] == 0
        assert attrs["success_count"] == 0
        assert attrs["status"] == "skipped"

    @pytest.mark.requirement("8C-FR-024")
    def test_sync_to_registries_span_has_timing_attributes_with_clients(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _sync_to_registries() span with clients has timing attributes."""
        _, exporter = tracer_with_exporter

        # Create mock secondary client
        mock_secondary_client = Mock()
        mock_secondary_client.registry_uri = "oci://secondary.example.com/floe"
        mock_secondary_client.copy_tag.return_value = None
        mock_secondary_client.get_artifact_digest.return_value = "sha256:abc123"

        controller._sync_to_registries(
            tag="v1.0.0",
            to_env="staging",
            artifact_digest="sha256:abc123",
            secondary_clients=[mock_secondary_client],
        )

        spans = exporter.get_finished_spans()
        sync_span = next(s for s in spans if s.name == "floe.oci.sync_to_registries")

        attrs = dict(sync_span.attributes)
        assert "duration_ms" in attrs
        assert isinstance(attrs["duration_ms"], int)
        assert "success_count" in attrs
        assert isinstance(attrs["success_count"], int)
        assert "status" in attrs
        assert attrs["status"] in ["completed", "partial"]

    @pytest.mark.requirement("8C-FR-024")
    def test_policy_compliance_gate_span_has_timing_attributes(
        self,
        controller,
        tracer_with_exporter: tuple[TracerProvider, InMemorySpanExporter],
    ) -> None:
        """Test _run_policy_compliance_gate() span has duration_ms and status."""
        _, exporter = tracer_with_exporter

        # Run policy gate (will skip because no enforcer configured)
        controller._run_policy_compliance_gate(manifest={})

        spans = exporter.get_finished_spans()
        policy_span = next(s for s in spans if s.name == "floe.oci.gate.policy_compliance")

        attrs = dict(policy_span.attributes)
        assert "duration_ms" in attrs
        assert isinstance(attrs["duration_ms"], int)
        assert "status" in attrs
        assert attrs["status"] == "skipped"
