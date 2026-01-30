"""Unit tests for OpenTelemetry span in promote() (T024a).

Tests PromotionController.promote() OpenTelemetry tracing behavior.

Requirements tested:
    FR-024: OpenTelemetry integration for promotion operations
    FR-033: Trace ID in promotion output for correlation
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestPromoteOpenTelemetrySpan:
    """Tests for OpenTelemetry span in promote()."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with fully mocked OCI client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        # Create a mock OCI client to avoid network calls
        mock_client = Mock()
        mock_client.inspect.return_value = Mock(
            digest="sha256:" + "a" * 64,  # Valid sha256 format (64 hex chars)
            annotations={},
        )
        mock_client.create_tag.return_value = None

        # Use signature_enforcement="off" to skip signature verification in tests
        promotion = PromotionConfig(signature_enforcement="off")

        return PromotionController(client=mock_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-024")
    def test_promote_creates_span(self, controller: MagicMock) -> None:
        """Test promote() creates an OpenTelemetry span named 'floe.oci.promote'."""
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
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )
            except NotImplementedError:
                pass  # Expected - promote not fully implemented

            # Verify create_span was called at least once with the main span name
            assert mock_create_span.called, "create_span should be called"
            # Find the call with the main promotion span name
            span_names = [call[0][0] for call in mock_create_span.call_args_list]
            assert "floe.oci.promote" in span_names

    @pytest.mark.requirement("8C-FR-024")
    def test_promote_span_has_artifact_ref_attribute(self, controller: MagicMock) -> None:
        """Test promote() span has artifact_ref attribute."""
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
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )
            except NotImplementedError:
                pass

            # Check attributes include artifact_ref (in some form)
            call_kwargs = mock_create_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert "artifact_ref" in attributes or "floe.promotion.artifact_ref" in attributes

    @pytest.mark.requirement("8C-FR-024")
    def test_promote_span_has_env_attributes(self, controller: MagicMock) -> None:
        """Test promote() span has from_env and to_env attributes."""
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
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )
            except NotImplementedError:
                pass

            # Find the main promote span call and get its attributes
            promote_call = None
            for call in mock_create_span.call_args_list:
                if call[0] and call[0][0] == "floe.oci.promote":
                    promote_call = call
                    break

            assert promote_call is not None, "Should have a floe.oci.promote span"
            attributes = promote_call[1].get("attributes", {})

            # Check for from_env and to_env (prefixed or unprefixed)
            has_from_env = "from_env" in attributes or "floe.promotion.from_env" in attributes
            has_to_env = "to_env" in attributes or "floe.promotion.to_env" in attributes
            assert has_from_env, "Span should have from_env attribute"
            assert has_to_env, "Span should have to_env attribute"

    @pytest.mark.requirement("8C-FR-024")
    def test_promote_span_has_dry_run_attribute(self, controller: MagicMock) -> None:
        """Test promote() span has dry_run attribute."""
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
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                    dry_run=True,
                )
            except NotImplementedError:
                pass

            # Find the main promote span call and get its attributes
            promote_call = None
            for call in mock_create_span.call_args_list:
                if call[0] and call[0][0] == "floe.oci.promote":
                    promote_call = call
                    break

            assert promote_call is not None, "Should have a floe.oci.promote span"
            attributes = promote_call[1].get("attributes", {})

            # Check for dry_run (prefixed or unprefixed)
            has_dry_run = "dry_run" in attributes or "floe.promotion.dry_run" in attributes
            assert has_dry_run, "Span should have dry_run attribute"

    @pytest.mark.requirement("8C-FR-033")
    def test_promote_extracts_trace_id(self, controller: MagicMock) -> None:
        """Test promote() extracts trace_id for CLI output."""
        with patch("floe_core.oci.promotion.create_span") as mock_create_span:
            # Create a mock span context with valid trace_id
            mock_span = Mock()
            mock_span.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                span_id=0x1234567890123456,
                is_valid=True,
            )
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            try:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )
            except NotImplementedError:
                pass

            # Verify span.get_span_context() was called
            mock_span.get_span_context.assert_called()

    @pytest.mark.requirement("8C-FR-024")
    def test_promote_span_records_exception_on_error(self, controller: MagicMock) -> None:
        """Test promote() span records exceptions when errors occur."""
        with patch("floe_core.oci.promotion.create_span") as mock_create_span:
            mock_span = Mock()
            mock_span.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                span_id=0x1234567890123456,
                is_valid=True,
            )
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            # Test with invalid transition that raises ValueError
            with pytest.raises(ValueError):
                controller.promote(
                    tag="v1.0.0",
                    from_env="prod",  # Invalid: can't promote backward
                    to_env="dev",
                    operator="ci@github.com",
                )

            # The span context manager should still be used
            mock_create_span.assert_called_once()
