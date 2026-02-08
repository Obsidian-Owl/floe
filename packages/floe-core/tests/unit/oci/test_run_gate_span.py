"""Unit tests for OpenTelemetry span in _run_gate() (T024c).

Tests PromotionController._run_gate() OpenTelemetry tracing behavior.

Requirements tested:
    FR-024: OpenTelemetry integration for promotion operations
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from floe_core.schemas.promotion import PromotionGate


class TestRunGateOpenTelemetrySpan:
    """Tests for OpenTelemetry span in _run_gate()."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked OCI client."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-024")
    def test_run_gate_creates_span_with_gate_name(self, controller: MagicMock) -> None:
        """Test _run_gate() creates span named 'floe.oci.gate.{gate_name}'."""
        with (
            patch("floe_core.oci.promotion.create_span") as mock_create_span,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            # Mock subprocess to return success
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo 'test'",
                timeout_seconds=60,
            )

            # Verify create_span was called with gate-specific name
            mock_create_span.assert_called_once()
            call_args = mock_create_span.call_args
            assert call_args[0][0] == "floe.oci.gate.tests"

    @pytest.mark.requirement("8C-FR-024")
    def test_run_gate_span_includes_different_gate_types(self, controller: MagicMock) -> None:
        """Test _run_gate() span name includes correct gate type."""
        with (
            patch("floe_core.oci.promotion.create_span") as mock_create_span,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            # Test security_scan gate
            controller._run_gate(
                gate=PromotionGate.SECURITY_SCAN,
                command="echo 'scan'",
                timeout_seconds=120,
            )

            call_args = mock_create_span.call_args
            assert call_args[0][0] == "floe.oci.gate.security_scan"

    @pytest.mark.requirement("8C-FR-024")
    def test_run_gate_span_has_gate_type_attribute(self, controller: MagicMock) -> None:
        """Test _run_gate() span has gate_type attribute."""
        with (
            patch("floe_core.oci.promotion.create_span") as mock_create_span,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo 'test'",
                timeout_seconds=60,
            )

            call_args = mock_create_span.call_args
            attributes = call_args[1].get("attributes", {})
            assert "gate_type" in attributes
            assert attributes["gate_type"] == "tests"

    @pytest.mark.requirement("8C-FR-024")
    def test_run_gate_span_has_timeout_attribute(self, controller: MagicMock) -> None:
        """Test _run_gate() span has timeout_seconds attribute."""
        with (
            patch("floe_core.oci.promotion.create_span") as mock_create_span,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo 'test'",
                timeout_seconds=90,
            )

            call_args = mock_create_span.call_args
            attributes = call_args[1].get("attributes", {})
            assert "timeout_seconds" in attributes
            assert attributes["timeout_seconds"] == 90

    @pytest.mark.requirement("8C-FR-024")
    def test_run_gate_span_records_duration(self, controller: MagicMock) -> None:
        """Test _run_gate() records duration_ms on span."""
        with (
            patch("floe_core.oci.promotion.create_span") as mock_create_span,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

            result = controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo 'test'",
                timeout_seconds=60,
            )

            # The span should have set_attribute called with duration_ms
            mock_span.set_attribute.assert_any_call("duration_ms", result.duration_ms)
