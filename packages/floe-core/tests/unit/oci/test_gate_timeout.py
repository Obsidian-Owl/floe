"""Unit tests for gate timeout handling (T017, T017a).

Tests PromotionController._run_gate() timeout behavior.

Requirements tested:
    FR-012a: Gate timeout configuration
    FR-012b: SIGTERM on timeout
    FR-012c: SIGKILL after grace period
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestGateTimeoutHandling:
    """Tests for gate execution timeout handling."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-012a")
    def test_gate_completes_within_timeout(self, controller: MagicMock) -> None:
        """Test gate completing within timeout returns PASSED."""
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="OK", stderr="")

            result = controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo 'test passed'",
                timeout_seconds=30,
            )

            assert result.status == GateStatus.PASSED
            assert result.gate == PromotionGate.TESTS
            assert result.duration_ms >= 0
            assert result.error is None

    @pytest.mark.requirement("8C-FR-012a")
    def test_gate_fails_returns_failed_status(self, controller: MagicMock) -> None:
        """Test gate with non-zero exit code returns FAILED."""
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Test failed")

            result = controller._run_gate(
                gate=PromotionGate.TESTS,
                command="exit 1",
                timeout_seconds=30,
            )

            assert result.status == GateStatus.FAILED
            assert result.gate == PromotionGate.TESTS
            assert result.error is not None
            assert "failed" in result.error.lower() or "exit" in result.error.lower()

    @pytest.mark.requirement("8C-FR-012b")
    def test_gate_exceeding_timeout_returns_failed(self, controller: MagicMock) -> None:
        """Test gate exceeding timeout returns FAILED with timeout error."""
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        # Patch at the module level where subprocess is used
        with patch("floe_core.oci.promotion.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 100", timeout=1)

            # Also patch Popen to avoid actual process creation in timeout handler
            with patch("floe_core.oci.promotion.subprocess.Popen") as mock_popen:
                mock_process = Mock()
                mock_process.wait.return_value = None
                mock_popen.return_value = mock_process

                result = controller._run_gate(
                    gate=PromotionGate.TESTS,
                    command="sleep 100",
                    timeout_seconds=1,
                )

                assert result.status == GateStatus.FAILED
                assert result.gate == PromotionGate.TESTS
                assert result.error is not None
                assert "timed out" in result.error.lower()
                assert result.duration_ms >= 0  # Duration recorded even on timeout

    @pytest.mark.requirement("8C-FR-012c")
    def test_timeout_sends_sigterm_then_sigkill(self, controller: MagicMock) -> None:
        """Test timeout handling sends SIGTERM then SIGKILL after grace period."""
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        # Create a mock process that simulates hanging after SIGTERM
        mock_process = Mock()
        mock_process.returncode = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=5)

        # First, subprocess.run must raise TimeoutExpired to trigger the escalation path
        with patch("floe_core.oci.promotion.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 100", timeout=1)

            # Then subprocess.Popen is used for SIGTERM/SIGKILL escalation
            with patch("floe_core.oci.promotion.subprocess.Popen") as mock_popen:
                mock_popen.return_value = mock_process

                result = controller._run_gate(
                    gate=PromotionGate.TESTS,
                    command="sleep 100",
                    timeout_seconds=1,
                )

                # Verify Popen was called for escalation
                mock_popen.assert_called_once()
                # Should have attempted SIGTERM
                mock_process.terminate.assert_called()
                # Should have attempted SIGKILL after grace period
                mock_process.kill.assert_called()
                assert result.status == GateStatus.FAILED
                assert "timed out" in result.error.lower()

    @pytest.mark.requirement("8C-FR-012a")
    def test_gate_records_duration_on_success(self, controller: MagicMock) -> None:
        """Test duration_ms is recorded on successful gate execution."""
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="OK", stderr="")

            result = controller._run_gate(
                gate=PromotionGate.TESTS,
                command="echo test",
                timeout_seconds=30,
            )

            assert result.duration_ms >= 0
            assert result.status == GateStatus.PASSED

    @pytest.mark.requirement("8C-FR-012a")
    def test_gate_records_duration_on_timeout(self, controller: MagicMock) -> None:
        """Test duration_ms is recorded even when gate times out."""
        from floe_core.schemas.promotion import GateStatus, PromotionGate

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=5)

            result = controller._run_gate(
                gate=PromotionGate.TESTS,
                command="sleep 100",
                timeout_seconds=5,
            )

            assert result.duration_ms >= 0
            assert result.status == GateStatus.FAILED
