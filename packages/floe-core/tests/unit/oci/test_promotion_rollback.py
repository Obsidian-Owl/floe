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


class TestRollbackVersionNotFound:
    """Unit tests for rollback() version-not-found error path (T047).

    TDD: These tests document the expected error behavior when attempting
    to rollback to a version that was never promoted to the environment.
    Currently xfail until T050 implements the validation logic.
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

    @pytest.mark.xfail(reason="T050: Implement VersionNotPromotedError handling")
    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_raises_version_not_promoted_error(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: rollback() raises VersionNotPromotedError for unknown version.

        When the target version was never promoted to the specified environment,
        rollback() should raise VersionNotPromotedError with helpful context.
        """
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError):
            controller.rollback(
                tag="v99.0.0",  # Version that was never promoted
                environment="prod",
                reason="Rollback to unknown version",
                operator="sre@example.com",
            )

    @pytest.mark.xfail(reason="T050: Implement VersionNotPromotedError with tag")
    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error_contains_tag(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: VersionNotPromotedError includes the requested tag."""
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError) as exc_info:
            controller.rollback(
                tag="v99.0.0",
                environment="prod",
                reason="Check error tag",
                operator="sre@example.com",
            )

        assert exc_info.value.tag == "v99.0.0"

    @pytest.mark.xfail(reason="T050: Implement VersionNotPromotedError with environment")
    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error_contains_environment(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: VersionNotPromotedError includes the target environment."""
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError) as exc_info:
            controller.rollback(
                tag="v99.0.0",
                environment="prod",
                reason="Check error environment",
                operator="sre@example.com",
            )

        assert exc_info.value.environment == "prod"

    @pytest.mark.xfail(reason="T050: Implement VersionNotPromotedError with available_versions")
    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error_contains_available_versions(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: VersionNotPromotedError includes list of available versions.

        To help operators, the error should list what versions ARE available
        in the environment for rollback.
        """
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError) as exc_info:
            controller.rollback(
                tag="v99.0.0",
                environment="prod",
                reason="Check available versions",
                operator="sre@example.com",
            )

        # available_versions should be populated with actual env versions
        assert exc_info.value.available_versions is not None
        assert isinstance(exc_info.value.available_versions, list)

    @pytest.mark.xfail(reason="T050: Implement exit code for VersionNotPromotedError")
    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error_has_correct_exit_code(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: VersionNotPromotedError uses exit code 11."""
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError) as exc_info:
            controller.rollback(
                tag="v99.0.0",
                environment="prod",
                reason="Check exit code",
                operator="sre@example.com",
            )

        assert exc_info.value.exit_code == 11

    @pytest.mark.xfail(reason="T050: Implement error message format")
    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error_message_is_helpful(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: Error message includes both tag and environment for context."""
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError) as exc_info:
            controller.rollback(
                tag="v99.0.0",
                environment="prod",
                reason="Check message",
                operator="sre@example.com",
            )

        error_message = str(exc_info.value)
        assert "v99.0.0" in error_message
        assert "prod" in error_message


class TestRollbackAuthorizationError:
    """Unit tests for rollback() authorization error path (T047 extension).

    TDD: Tests for when operator is not authorized to rollback in the environment.
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

    @pytest.mark.xfail(reason="T050: Implement AuthorizationError handling")
    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_raises_authorization_error_for_unauthorized_operator(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: rollback() raises AuthorizationError for unauthorized operator."""
        from floe_core.oci.errors import AuthorizationError

        with pytest.raises(AuthorizationError):
            controller.rollback(
                tag="v1.0.0",
                environment="prod",
                reason="Unauthorized rollback attempt",
                operator="unauthorized@example.com",
            )

    @pytest.mark.xfail(reason="T050: Implement AuthorizationError with operator")
    @pytest.mark.requirement("8C-FR-013")
    def test_authorization_error_contains_operator(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: AuthorizationError includes the operator identity."""
        from floe_core.oci.errors import AuthorizationError

        with pytest.raises(AuthorizationError) as exc_info:
            controller.rollback(
                tag="v1.0.0",
                environment="prod",
                reason="Check operator in error",
                operator="unauthorized@example.com",
            )

        assert exc_info.value.operator == "unauthorized@example.com"


class TestRollbackEnvironmentLocked:
    """Unit tests for rollback() environment-locked error path (T047 extension).

    TDD: Tests for when the target environment is locked.
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

    @pytest.mark.xfail(reason="T050: Implement EnvironmentLockedError handling")
    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_raises_environment_locked_error(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: rollback() raises EnvironmentLockedError for locked environment."""
        from floe_core.oci.errors import EnvironmentLockedError

        with pytest.raises(EnvironmentLockedError):
            controller.rollback(
                tag="v1.0.0",
                environment="prod",  # Assume prod is locked
                reason="Rollback to locked environment",
                operator="sre@example.com",
            )

    @pytest.mark.xfail(reason="T050: Implement EnvironmentLockedError with reason")
    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_error_contains_lock_reason(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: EnvironmentLockedError includes why the environment is locked."""
        from floe_core.oci.errors import EnvironmentLockedError

        with pytest.raises(EnvironmentLockedError) as exc_info:
            controller.rollback(
                tag="v1.0.0",
                environment="prod",
                reason="Check lock reason",
                operator="sre@example.com",
            )

        assert exc_info.value.reason is not None
        assert len(exc_info.value.reason) > 0


class TestAnalyzeRollbackImpact:
    """Unit tests for PromotionController.analyze_rollback_impact() (T048).

    TDD: Tests document expected behavior for the impact analysis method
    that will be implemented in T051. analyze_rollback_impact() provides
    pre-rollback analysis per FR-016.
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

    @pytest.mark.xfail(reason="T051: analyze_rollback_impact() method not yet implemented")
    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_rollback_impact_method_exists(self, controller: MagicMock) -> None:
        """Test that analyze_rollback_impact() method exists on controller.

        TDD baseline: Method should exist after T051 implementation.
        """
        assert hasattr(controller, "analyze_rollback_impact"), (
            "PromotionController should have analyze_rollback_impact method"
        )

    @pytest.mark.xfail(reason="T051: Implement analyze_rollback_impact()")
    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_rollback_impact_returns_impact_analysis(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: analyze_rollback_impact() returns RollbackImpactAnalysis.

        Implementation in T051 should return analysis with:
        - breaking_changes: List of schema/API changes
        - affected_products: Data products using this artifact
        - recommendations: Operator guidance
        - estimated_downtime: Impact duration estimate
        """
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert isinstance(result, RollbackImpactAnalysis)

    @pytest.mark.xfail(reason="T051: Implement breaking_changes detection")
    @pytest.mark.requirement("8C-FR-016")
    def test_impact_analysis_contains_breaking_changes(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: Analysis includes list of breaking changes."""
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert isinstance(result, RollbackImpactAnalysis)
        assert isinstance(result.breaking_changes, list)

    @pytest.mark.xfail(reason="T051: Implement affected_products detection")
    @pytest.mark.requirement("8C-FR-016")
    def test_impact_analysis_contains_affected_products(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: Analysis includes list of affected data products."""
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert isinstance(result, RollbackImpactAnalysis)
        assert isinstance(result.affected_products, list)

    @pytest.mark.xfail(reason="T051: Implement recommendations generation")
    @pytest.mark.requirement("8C-FR-016")
    def test_impact_analysis_contains_recommendations(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: Analysis includes operator recommendations."""
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert isinstance(result, RollbackImpactAnalysis)
        assert isinstance(result.recommendations, list)

    @pytest.mark.xfail(reason="T051: Implement estimated_downtime calculation")
    @pytest.mark.requirement("8C-FR-016")
    def test_impact_analysis_may_contain_estimated_downtime(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: Analysis may include estimated_downtime (optional)."""
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert isinstance(result, RollbackImpactAnalysis)
        # estimated_downtime is optional (can be None or string)
        if result.estimated_downtime is not None:
            assert isinstance(result.estimated_downtime, str)

    @pytest.mark.xfail(reason="T051: Implement version validation in analyze")
    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_raises_version_not_promoted_for_unknown_version(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: analyze_rollback_impact() raises error for unknown version."""
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError):
            controller.analyze_rollback_impact(
                tag="v99.0.0",
                environment="prod",
            )

    @pytest.mark.xfail(reason="T051: Implement OpenTelemetry span for analyze")
    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_rollback_impact_creates_span(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: analyze_rollback_impact() creates OpenTelemetry span."""
        with patch("floe_core.oci.promotion.create_span") as mock_span:
            mock_span_instance = Mock()
            mock_span_instance.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                is_valid=True,
            )
            mock_span.return_value.__enter__ = Mock(return_value=mock_span_instance)
            mock_span.return_value.__exit__ = Mock(return_value=None)

            controller.analyze_rollback_impact(
                tag="v1.0.0",
                environment="prod",
            )

            mock_span.assert_called_once()
            # Span name should indicate analysis operation
            span_name = mock_span.call_args[0][0]
            assert "analyze" in span_name.lower() or "impact" in span_name.lower()

    @pytest.mark.xfail(reason="T051: Implement dry-run integration")
    @pytest.mark.requirement("8C-FR-016")
    def test_rollback_with_analyze_flag_includes_impact_analysis(
        self, controller: MagicMock
    ) -> None:
        """EXPECTED: rollback() with analyze=True includes impact analysis.

        When analyze=True is passed to rollback(), the RollbackRecord
        should include the impact_analysis field populated.
        """
        from floe_core.schemas.promotion import RollbackImpactAnalysis, RollbackRecord

        result = controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Rollback with impact analysis",
            operator="sre@example.com",
            analyze=True,  # Request impact analysis
        )

        assert isinstance(result, RollbackRecord)
        assert result.impact_analysis is not None
        assert isinstance(result.impact_analysis, RollbackImpactAnalysis)
