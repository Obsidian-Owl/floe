"""Unit tests for OpenTelemetry span in _verify_signature() (T024d).

Tests PromotionController._verify_signature() OpenTelemetry tracing behavior.

Requirements tested:
    FR-024: OpenTelemetry integration for promotion operations
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestVerifySignatureOpenTelemetrySpan:
    """Tests for OpenTelemetry span in _verify_signature()."""

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
    def test_verify_signature_creates_span(self, controller: MagicMock) -> None:
        """Test _verify_signature() creates span named 'floe.oci.promote.verify'."""
        from floe_core.schemas.signing import VerificationResult

        mock_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        with (
            patch("floe_core.oci.promotion.create_span") as mock_create_span,
            patch("floe_core.schemas.signing.VerificationPolicy") as mock_policy_class,
            patch("floe_core.oci.verification.VerificationClient") as mock_client_class,
        ):
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

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

            # Verify create_span was called with correct name
            mock_create_span.assert_called_once()
            call_args = mock_create_span.call_args
            assert call_args[0][0] == "floe.oci.promote.verify"

    @pytest.mark.requirement("8C-FR-024")
    def test_verify_signature_span_has_enforcement_attribute(
        self, controller: MagicMock
    ) -> None:
        """Test _verify_signature() span has enforcement_mode attribute."""
        from floe_core.schemas.signing import VerificationResult

        mock_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        with (
            patch("floe_core.oci.promotion.create_span") as mock_create_span,
            patch("floe_core.schemas.signing.VerificationPolicy") as mock_policy_class,
            patch("floe_core.oci.verification.VerificationClient") as mock_client_class,
        ):
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            mock_policy = Mock()
            mock_policy.enforcement = "warn"
            mock_policy_class.return_value = mock_policy

            mock_client = Mock()
            mock_client.verify.return_value = mock_result
            mock_client_class.return_value = mock_client

            controller._verify_signature(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"test content",
                enforcement="warn",
            )

            call_args = mock_create_span.call_args
            attributes = call_args[1].get("attributes", {})
            assert "enforcement_mode" in attributes
            assert attributes["enforcement_mode"] == "warn"

    @pytest.mark.requirement("8C-FR-024")
    def test_verify_signature_span_skipped_when_enforcement_off(
        self, controller: MagicMock
    ) -> None:
        """Test _verify_signature() still creates span when enforcement=off."""
        with patch("floe_core.oci.promotion.create_span") as mock_create_span:
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

            controller._verify_signature(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"test content",
                enforcement="off",
            )

            # Should still create span even when enforcement is off
            mock_create_span.assert_called_once()
            call_args = mock_create_span.call_args
            attributes = call_args[1].get("attributes", {})
            assert attributes["enforcement_mode"] == "off"

    @pytest.mark.requirement("8C-FR-024")
    def test_verify_signature_span_has_artifact_ref_attribute(
        self, controller: MagicMock
    ) -> None:
        """Test _verify_signature() span has artifact_ref attribute."""
        from floe_core.schemas.signing import VerificationResult

        mock_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        with (
            patch("floe_core.oci.promotion.create_span") as mock_create_span,
            patch("floe_core.schemas.signing.VerificationPolicy") as mock_policy_class,
            patch("floe_core.oci.verification.VerificationClient") as mock_client_class,
        ):
            mock_span = Mock()
            mock_create_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_create_span.return_value.__exit__ = Mock(return_value=None)

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

            call_args = mock_create_span.call_args
            attributes = call_args[1].get("attributes", {})
            assert "artifact_ref" in attributes
            assert attributes["artifact_ref"] == "harbor.example.com/floe:v1.0.0"
