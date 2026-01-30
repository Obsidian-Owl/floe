"""Unit tests for PromotionController.rollback() method (T046-T048).

Tests for the rollback() method covering:
- T046: Success path (version exists, operator authorized)
- T047: Version-not-found path
- T048: Impact analysis

Requirements tested:
    FR-013: Rollback to any previously promoted version
    FR-014: Rollback-specific tag pattern
    FR-015: Update mutable "latest" tag
    FR-016: Impact analysis in dry-run mode
    FR-017: Record rollback in audit trail

TDD Note:
    These tests are written FIRST per TDD methodology.
    They currently FAIL with NotImplementedError since rollback()
    is not yet implemented (implementation in T050+).
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestRollbackSuccessPath:
    """Unit tests for PromotionController.rollback() success path (T046).

    TDD: These tests document expected behavior and will pass after T050 implements
    the full rollback() logic. Currently they fail with NotImplementedError.
    """

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

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_raises_not_implemented(self, controller: MagicMock) -> None:
        """Test rollback() currently raises NotImplementedError.

        TDD baseline: This test passes now and will need to be removed/updated
        when T050 implements the full rollback() logic.
        """
        with pytest.raises(NotImplementedError, match="Rollback implementation"):
            controller.rollback(
                tag="v1.0.0",
                environment="prod",
                reason="Performance regression",
                operator="sre@example.com",
            )

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_calls_are_logged(self, controller: MagicMock) -> None:
        """Test rollback() logs the operation start.

        Validates that logging happens before NotImplementedError.
        """
        with patch("floe_core.oci.promotion.create_span") as mock_span:
            mock_span_instance = Mock()
            mock_span_instance.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                is_valid=True,
            )
            mock_span.return_value.__enter__ = Mock(return_value=mock_span_instance)
            mock_span.return_value.__exit__ = Mock(return_value=None)

            # Should raise NotImplementedError but after logging
            with pytest.raises(NotImplementedError):
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Logging test",
                    operator="sre@example.com",
                )

            # Verify span was created with correct name
            mock_span.assert_called_once()
            assert mock_span.call_args[0][0] == "floe.oci.rollback"

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_span_has_environment_attribute(
        self, controller: MagicMock
    ) -> None:
        """Test rollback() span includes environment attribute."""
        with patch("floe_core.oci.promotion.create_span") as mock_span:
            mock_span_instance = Mock()
            mock_span_instance.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                is_valid=True,
            )
            mock_span.return_value.__enter__ = Mock(return_value=mock_span_instance)
            mock_span.return_value.__exit__ = Mock(return_value=None)

            with pytest.raises(NotImplementedError):
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Attribute test",
                    operator="sre@example.com",
                )

            call_kwargs = mock_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert attributes["environment"] == "prod"

    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_span_has_reason_attribute(self, controller: MagicMock) -> None:
        """Test rollback() span includes reason attribute for audit."""
        with patch("floe_core.oci.promotion.create_span") as mock_span:
            mock_span_instance = Mock()
            mock_span_instance.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                is_valid=True,
            )
            mock_span.return_value.__enter__ = Mock(return_value=mock_span_instance)
            mock_span.return_value.__exit__ = Mock(return_value=None)

            with pytest.raises(NotImplementedError):
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Critical bug found",
                    operator="sre@example.com",
                )

            call_kwargs = mock_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert attributes["reason"] == "Critical bug found"

    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_span_has_operator_attribute(self, controller: MagicMock) -> None:
        """Test rollback() span includes operator attribute for audit."""
        with patch("floe_core.oci.promotion.create_span") as mock_span:
            mock_span_instance = Mock()
            mock_span_instance.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                is_valid=True,
            )
            mock_span.return_value.__enter__ = Mock(return_value=mock_span_instance)
            mock_span.return_value.__exit__ = Mock(return_value=None)

            with pytest.raises(NotImplementedError):
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Operator test",
                    operator="sre@example.com",
                )

            call_kwargs = mock_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert attributes["operator"] == "sre@example.com"

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_span_has_artifact_ref_attribute(
        self, controller: MagicMock
    ) -> None:
        """Test rollback() span includes artifact_ref attribute."""
        with patch("floe_core.oci.promotion.create_span") as mock_span:
            mock_span_instance = Mock()
            mock_span_instance.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                is_valid=True,
            )
            mock_span.return_value.__enter__ = Mock(return_value=mock_span_instance)
            mock_span.return_value.__exit__ = Mock(return_value=None)

            with pytest.raises(NotImplementedError):
                controller.rollback(
                    tag="v1.0.0",
                    environment="prod",
                    reason="Artifact ref test",
                    operator="sre@example.com",
                )

            call_kwargs = mock_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert "artifact_ref" in attributes
            assert "v1.0.0" in attributes["artifact_ref"]


class TestRollbackExpectedBehavior:
    """Tests documenting expected rollback behavior for T050 implementation.

    TDD: These tests are marked xfail and document what rollback() SHOULD do.
    They will be converted to passing tests when T050 implements the logic.
    """

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

    @pytest.mark.xfail(reason="T050: Implement rollback() return RollbackRecord")
    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_returns_rollback_record(self, controller: MagicMock) -> None:
        """EXPECTED: rollback() returns a valid RollbackRecord on success.

        Implementation in T050 should:
        1. Validate version was promoted to environment
        2. Check operator authorization
        3. Check environment is not locked
        4. Get target and current digests
        5. Create rollback tag (FR-014)
        6. Update latest tag (FR-015)
        7. Store RollbackRecord (FR-017)
        8. Return RollbackRecord
        """
        from floe_core.schemas.promotion import RollbackRecord

        result = controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Performance regression",
            operator="sre@example.com",
        )

        assert isinstance(result, RollbackRecord)
        assert result.environment == "prod"
        assert result.reason == "Performance regression"
        assert result.operator == "sre@example.com"

    @pytest.mark.xfail(reason="T050: Implement rollback() with trace_id")
    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_record_contains_trace_id(self, controller: MagicMock) -> None:
        """EXPECTED: RollbackRecord includes trace_id for observability."""
        from floe_core.schemas.promotion import RollbackRecord

        result = controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Trace ID test",
            operator="sre@example.com",
        )

        assert isinstance(result, RollbackRecord)
        assert result.trace_id is not None
        assert len(result.trace_id) > 0

    @pytest.mark.xfail(reason="T050: Implement rollback() with previous_digest")
    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_record_contains_previous_digest(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: RollbackRecord includes previous_digest for audit."""
        from floe_core.schemas.promotion import RollbackRecord

        result = controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Previous digest test",
            operator="sre@example.com",
        )

        assert isinstance(result, RollbackRecord)
        assert result.previous_digest is not None
        assert result.previous_digest.startswith("sha256:")

    @pytest.mark.xfail(reason="T050: Implement rollback() with artifact_digest")
    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_record_contains_artifact_digest(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: RollbackRecord includes target artifact_digest."""
        from floe_core.schemas.promotion import RollbackRecord

        result = controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Artifact digest test",
            operator="sre@example.com",
        )

        assert isinstance(result, RollbackRecord)
        assert result.artifact_digest is not None
        assert result.artifact_digest.startswith("sha256:")
