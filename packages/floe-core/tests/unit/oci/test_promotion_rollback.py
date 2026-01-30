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

Task: T046, T047, T048
Updated: T050 - Implementation tests now passing
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import pytest


class TestRollbackSuccessPath:
    """Unit tests for PromotionController.rollback() success path (T046).

    Tests verify the rollback method works correctly when:
    - Version was previously promoted to the environment
    - Operator has proper authorization
    - All dependencies are available
    """

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mocked OCIClient for unit testing."""
        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"

        # Mock inspect to return manifest info
        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:" + "a" * 64
        client.inspect.return_value = mock_manifest

        # Mock list to return empty (no existing rollback tags)
        client.list.return_value = []

        # Mock ORAS client operations
        mock_oras = MagicMock()
        mock_oras.get_manifest.return_value = {"schemaVersion": 2}
        client._create_oras_client.return_value = mock_oras

        return client

    @pytest.fixture
    def controller(self, mock_client: MagicMock) -> MagicMock:
        """Create a PromotionController with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(client=mock_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_returns_rollback_record(
        self, controller: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test rollback() returns a RollbackRecord on success."""
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

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_validates_version_was_promoted(
        self, controller: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test rollback() checks that version was promoted to environment."""
        # The first inspect call should be for env_tag (v1.0.0-prod)
        controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Test",
            operator="sre@example.com",
        )

        # Verify inspect was called for the environment-specific tag
        calls = mock_client.inspect.call_args_list
        assert any("v1.0.0-prod" in str(call) for call in calls)

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_creates_rollback_tag(
        self, controller: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test rollback() creates tag with FR-014 pattern."""
        controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Test",
            operator="sre@example.com",
        )

        # Verify _build_target_ref was called with rollback tag pattern
        calls = mock_client._build_target_ref.call_args_list
        rollback_tag_calls = [c for c in calls if "rollback" in str(c)]
        assert len(rollback_tag_calls) > 0, "Should create rollback tag"

    @pytest.mark.requirement("8C-FR-015")
    def test_rollback_updates_latest_tag(
        self, controller: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test rollback() updates latest-{env} tag to rollback version."""
        # Configure separate digests for env tag and latest tag
        def inspect_side_effect(tag: str) -> MagicMock:
            manifest = MagicMock()
            if tag == "latest-prod":
                manifest.digest = "sha256:" + "b" * 64  # Current version digest
            else:
                manifest.digest = "sha256:" + "a" * 64  # Target version digest
            return manifest

        mock_client.inspect.side_effect = inspect_side_effect

        controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Test",
            operator="sre@example.com",
        )

        # Verify latest tag was updated (manifest uploaded with latest-prod ref)
        oras_client = mock_client._create_oras_client.return_value
        upload_calls = oras_client.upload_manifest.call_args_list
        assert len(upload_calls) >= 1, "Should upload manifest for tag operations"

    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_record_has_audit_fields(
        self, controller: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test RollbackRecord contains all audit trail fields."""
        result = controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Audit test",
            operator="sre@example.com",
        )

        # Verify all required audit fields
        assert isinstance(result.rollback_id, UUID)
        assert result.artifact_digest.startswith("sha256:")
        assert result.previous_digest.startswith("sha256:")
        assert result.environment == "prod"
        assert result.reason == "Audit test"
        assert result.operator == "sre@example.com"
        assert isinstance(result.rolled_back_at, datetime)
        assert result.trace_id is not None

    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_stores_record_in_annotations(
        self, controller: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test rollback() stores RollbackRecord in OCI annotations."""
        controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Storage test",
            operator="sre@example.com",
        )

        # Verify _update_artifact_annotations was called
        mock_client._update_artifact_annotations.assert_called()
        call_args = mock_client._update_artifact_annotations.call_args
        annotations = call_args[0][1]
        assert "dev.floe.rollback" in annotations

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_span_created_with_attributes(
        self, mock_client: MagicMock
    ) -> None:
        """Test rollback() creates OTel span with required attributes."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        with patch("floe_core.oci.promotion.create_span") as mock_span:
            mock_span_instance = Mock()
            mock_span_instance.get_span_context.return_value = Mock(
                trace_id=0x12345678901234567890123456789012,
                is_valid=True,
            )
            mock_span.return_value.__enter__ = Mock(return_value=mock_span_instance)
            mock_span.return_value.__exit__ = Mock(return_value=None)

            promotion = PromotionConfig()
            controller = PromotionController(client=mock_client, promotion=promotion)

            controller.rollback(
                tag="v1.0.0",
                environment="prod",
                reason="Span test",
                operator="sre@example.com",
            )

            # Verify span was created with correct name
            mock_span.assert_called_once()
            assert mock_span.call_args[0][0] == "floe.oci.rollback"

            # Verify attributes
            call_kwargs = mock_span.call_args
            attributes = call_kwargs[1].get("attributes", {})
            assert attributes["environment"] == "prod"
            assert attributes["reason"] == "Span test"
            assert attributes["operator"] == "sre@example.com"


class TestRollbackVersionNotFound:
    """Unit tests for rollback when version not promoted (T047)."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mocked OCIClient."""
        from floe_core.oci.errors import ArtifactNotFoundError

        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"

        # Mock inspect to raise ArtifactNotFoundError for env tag
        def inspect_side_effect(tag: str) -> MagicMock:
            if "-prod" in tag or "-staging" in tag:
                raise ArtifactNotFoundError(tag, "oci://harbor.example.com/floe")
            manifest = MagicMock()
            manifest.digest = "sha256:" + "a" * 64
            return manifest

        client.inspect.side_effect = inspect_side_effect
        client.list.return_value = []

        return client

    @pytest.fixture
    def controller(self, mock_client: MagicMock) -> MagicMock:
        """Create controller with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(client=mock_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_raises_version_not_promoted_error(
        self, controller: MagicMock
    ) -> None:
        """Test rollback() raises VersionNotPromotedError when version not promoted."""
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError) as exc_info:
            controller.rollback(
                tag="v2.0.0",
                environment="prod",
                reason="Test error path",
                operator="sre@example.com",
            )

        assert exc_info.value.tag == "v2.0.0"
        assert exc_info.value.environment == "prod"

    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error_has_exit_code_11(
        self, controller: MagicMock
    ) -> None:
        """Test VersionNotPromotedError has exit code 11."""
        from floe_core.oci.errors import VersionNotPromotedError

        with pytest.raises(VersionNotPromotedError) as exc_info:
            controller.rollback(
                tag="v2.0.0",
                environment="prod",
                reason="Exit code test",
                operator="sre@example.com",
            )

        assert exc_info.value.exit_code == 11


class TestRollbackTagNumbering:
    """Unit tests for rollback tag sequential numbering (FR-014)."""

    @pytest.fixture
    def mock_client_with_existing_rollbacks(self) -> MagicMock:
        """Create client with existing rollback tags."""
        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:" + "a" * 64
        client.inspect.return_value = mock_manifest

        # Mock existing rollback tags
        mock_tag1 = MagicMock()
        mock_tag1.name = "v1.0.0-prod-rollback-1"
        mock_tag2 = MagicMock()
        mock_tag2.name = "v1.0.0-prod-rollback-2"
        mock_tag3 = MagicMock()
        mock_tag3.name = "v1.0.0-staging-rollback-1"  # Different env
        client.list.return_value = [mock_tag1, mock_tag2, mock_tag3]

        mock_oras = MagicMock()
        mock_oras.get_manifest.return_value = {"schemaVersion": 2}
        client._create_oras_client.return_value = mock_oras

        return client

    @pytest.fixture
    def controller(self, mock_client_with_existing_rollbacks: MagicMock) -> MagicMock:
        """Create controller with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(
            client=mock_client_with_existing_rollbacks, promotion=promotion
        )

    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_tag_increments_correctly(
        self, controller: MagicMock, mock_client_with_existing_rollbacks: MagicMock
    ) -> None:
        """Test rollback tag number increments from existing tags."""
        controller.rollback(
            tag="v1.0.0",
            environment="prod",
            reason="Sequential number test",
            operator="sre@example.com",
        )

        # Should create v1.0.0-prod-rollback-3 (1 and 2 exist)
        calls = mock_client_with_existing_rollbacks._build_target_ref.call_args_list
        rollback_calls = [str(c) for c in calls if "rollback-3" in str(c)]
        assert len(rollback_calls) > 0, "Should create rollback-3 tag"


class TestAnalyzeRollbackImpact:
    """Unit tests for analyze_rollback_impact() (T048, T051).

    Tests verify the analyze_rollback_impact() method works correctly.
    """

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mocked OCIClient."""
        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:" + "a" * 64
        client.inspect.return_value = mock_manifest
        client.list.return_value = []

        return client

    @pytest.fixture
    def controller(self, mock_client: MagicMock) -> MagicMock:
        """Create controller with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(client=mock_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_rollback_impact_exists(self, controller: MagicMock) -> None:
        """Test analyze_rollback_impact() method exists."""
        assert hasattr(controller, "analyze_rollback_impact")

    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_rollback_impact_returns_analysis(
        self, controller: MagicMock
    ) -> None:
        """Test analyze_rollback_impact() returns RollbackImpactAnalysis."""
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert isinstance(result, RollbackImpactAnalysis)

    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_rollback_impact_has_breaking_changes(
        self, controller: MagicMock
    ) -> None:
        """Test RollbackImpactAnalysis includes breaking_changes."""
        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert hasattr(result, "breaking_changes")
        assert isinstance(result.breaking_changes, list)

    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_rollback_impact_has_affected_products(
        self, controller: MagicMock
    ) -> None:
        """Test RollbackImpactAnalysis includes affected_products."""
        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert hasattr(result, "affected_products")
        assert isinstance(result.affected_products, list)

    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_rollback_impact_has_recommendations(
        self, controller: MagicMock
    ) -> None:
        """Test RollbackImpactAnalysis includes recommendations."""
        result = controller.analyze_rollback_impact(
            tag="v1.0.0",
            environment="prod",
        )

        assert hasattr(result, "recommendations")
        assert isinstance(result.recommendations, list)
