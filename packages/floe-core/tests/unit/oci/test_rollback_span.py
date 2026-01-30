"""Unit tests for OpenTelemetry span in rollback() (T024b).

Tests PromotionController.rollback() OpenTelemetry tracing behavior.

Requirements tested:
    FR-024: OpenTelemetry integration for promotion operations
    FR-033: Trace ID in promotion output for correlation
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestRollbackOpenTelemetrySpan:
    """Tests for OpenTelemetry span in rollback()."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with fully mocked OCI client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        # Create a mock OCI client to avoid network calls
        mock_client = Mock()
        mock_client.inspect.return_value = Mock(
            digest="sha256:" + "a" * 64,  # Valid sha256 format
            annotations={},
        )
        mock_client.create_tag.return_value = None
        mock_client.list.return_value = []  # Empty list for rollback number calculation

        # Use signature_enforcement="off" to skip verification in tests
        promotion = PromotionConfig(signature_enforcement="off")

        return PromotionController(client=mock_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-024")
    def test_rollback_creates_span(self, controller: MagicMock) -> None:
        """Test rollback() creates an OpenTelemetry span named 'floe.oci.rollback'."""
        with patch("floe_core.oci.promotion.create_span") as mock_create_span:
            mock_span = Mock()
            mock_span.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                span_id=0x1234567890123456,
                is_valid=True,
            )
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            try:
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Hotfix rollback",
                    operator="sre@example.com",
                )
            except NotImplementedError:
                pass  # Expected - rollback not fully implemented

            # Verify create_span was called with correct name
            mock_create_span.assert_called_once()
            call_kwargs = mock_create_span.call_args
            assert call_kwargs[0][0] == "floe.oci.rollback"

    @pytest.mark.requirement("8C-FR-024")
    def test_rollback_span_has_artifact_ref_attribute(
        self, controller: MagicMock
    ) -> None:
        """Test rollback() span has artifact_ref attribute."""
        with patch("floe_core.oci.promotion.create_span") as mock_create_span:
            mock_span = Mock()
            mock_span.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                span_id=0x1234567890123456,
                is_valid=True,
            )
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            try:
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Hotfix rollback",
                    operator="sre@example.com",
                )
            except NotImplementedError:
                pass

            # Check attributes include artifact_ref
            call_kwargs = mock_create_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert "artifact_ref" in attributes

    @pytest.mark.requirement("8C-FR-024")
    def test_rollback_span_has_environment_attribute(
        self, controller: MagicMock
    ) -> None:
        """Test rollback() span has environment attribute."""
        with patch("floe_core.oci.promotion.create_span") as mock_create_span:
            mock_span = Mock()
            mock_span.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                span_id=0x1234567890123456,
                is_valid=True,
            )
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            try:
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Hotfix rollback",
                    operator="sre@example.com",
                )
            except NotImplementedError:
                pass

            call_kwargs = mock_create_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert "environment" in attributes
            assert attributes["environment"] == "prod"

    @pytest.mark.requirement("8C-FR-024")
    def test_rollback_span_has_reason_attribute(self, controller: MagicMock) -> None:
        """Test rollback() span has reason attribute."""
        with patch("floe_core.oci.promotion.create_span") as mock_create_span:
            mock_span = Mock()
            mock_span.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                span_id=0x1234567890123456,
                is_valid=True,
            )
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            try:
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Hotfix rollback",
                    operator="sre@example.com",
                )
            except NotImplementedError:
                pass

            call_kwargs = mock_create_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert "reason" in attributes
            assert attributes["reason"] == "Hotfix rollback"

    @pytest.mark.requirement("8C-FR-033")
    def test_rollback_extracts_trace_id(self, controller: MagicMock) -> None:
        """Test rollback() extracts trace_id for CLI output."""
        with patch("floe_core.oci.promotion.create_span") as mock_create_span:
            mock_span = Mock()
            mock_span.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                span_id=0x1234567890123456,
                is_valid=True,
            )
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            try:
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Hotfix rollback",
                    operator="sre@example.com",
                )
            except NotImplementedError:
                pass

            # Verify span.get_span_context() was called
            mock_span.get_span_context.assert_called()
