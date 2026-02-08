"""Unit tests for promotion failure recovery (T031a).

Tests for promotion recovery scenarios:
- Idempotent retry when tag exists with matching digest
- Failure when tag exists with different digest
- Latest tag update retry behavior

Requirements tested:
    NFR-004: Promotion idempotency and recovery
    FR-004: Tag exists error handling

⚠️ TDD: Tests WILL FAIL until T032/T032a implement full promote() logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

# Test constants
TEST_DIGEST = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


class TestPromotionIdempotency:
    """Unit tests for promotion idempotency (T031a)."""

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

    @pytest.mark.requirement("8C-NFR-004")
    def test_promote_is_idempotent_when_tag_exists_with_matching_digest(
        self, controller: MagicMock
    ) -> None:
        """Test promote() succeeds when env tag already exists with matching digest.

        ⚠️ TDD: This test WILL FAIL until T032a implements recovery logic.

        This is the idempotent case: if a promotion was interrupted after creating
        the env tag but before completing, retrying should succeed as a no-op
        if the digest matches.
        """
        from floe_core.schemas.promotion import PromotionRecord

        # Test constants

        expected_digest = TEST_DIGEST

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = expected_digest

            # Tag creation says "tag exists with same digest" - should be treated as success
            mock_create_tag.return_value = expected_digest  # Same digest = idempotent

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Should succeed (idempotent)
            assert isinstance(result, PromotionRecord)
            assert result.artifact_digest == expected_digest

    @pytest.mark.requirement("8C-FR-004")
    def test_promote_raises_tag_exists_error_when_different_digest(
        self, controller: MagicMock
    ) -> None:
        """Test promote() raises TagExistsError when env tag exists with different digest.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        This is an error case: if the env tag exists but points to a different
        artifact, this is a conflict that must be resolved manually.
        """
        from floe_core.oci.errors import TagExistsError

        source_digest = TEST_DIGEST
        existing_digest = (
            "sha256:1111111111111111111111111111111111111111111111111111111111111111"
        )

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = source_digest

            # Tag creation fails because tag exists with different digest
            mock_create_tag.side_effect = TagExistsError(
                tag="v1.0.0-staging",
                existing_digest=existing_digest,
            )

            with pytest.raises(TagExistsError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            assert exc_info.value.tag == "v1.0.0-staging"
            assert exc_info.value.existing_digest == existing_digest

    @pytest.mark.requirement("8C-FR-004")
    def test_tag_exists_error_has_exit_code_10(self, controller: MagicMock) -> None:
        """Test TagExistsError has correct exit code (10).

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import TagExistsError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            mock_create_tag.side_effect = TagExistsError(
                tag="v1.0.0-staging",
                existing_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            )

            with pytest.raises(TagExistsError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Exit code 10 for tag exists
            assert exc_info.value.exit_code == 10


class TestLatestTagRecovery:
    """Unit tests for latest tag update recovery (T031a)."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        # Test constants

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-NFR-004")
    def test_promote_retries_latest_tag_update_on_transient_failure(
        self, controller: MagicMock
    ) -> None:
        """Test promote() retries latest tag update on transient failures.

        If the env tag was created but latest tag update fails transiently,
        retry should eventually succeed.
        """
        from floe_core.schemas.promotion import PromotionRecord

        # Test constants

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag") as mock_update_latest,
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            # First call fails, second succeeds (simulating retry)
            mock_update_latest.side_effect = [
                ConnectionError("Transient failure"),
                None,  # Success on retry
            ]

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Should succeed after retry
            assert isinstance(result, PromotionRecord)
            # Verify retry happened
            assert mock_update_latest.call_count == 2

    @pytest.mark.requirement("8C-NFR-004")
    def test_promote_gives_up_after_max_retries(self, controller: MagicMock) -> None:
        """Test promote() records warning after max retry attempts.

        If latest tag update keeps failing, promotion should succeed
        with warnings instead of raising an exception.
        """
        from floe_core.schemas.promotion import PromotionRecord

        # Test constants

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag") as mock_update_latest,
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = "v1.0.0-staging"
            mock_get_digest.return_value = TEST_DIGEST

            # All calls fail
            mock_update_latest.side_effect = ConnectionError("Persistent failure")

            # Should succeed with warnings instead of raising
            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            assert isinstance(result, PromotionRecord)
            assert len(result.warnings) > 0
            assert "Latest tag update failed" in result.warnings[0]
            # Verify 3 retry attempts were made
            assert mock_update_latest.call_count == 3


class TestPromotionRecordRecovery:
    """Unit tests for promotion record storage recovery (T031a)."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        # Test constants

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-NFR-004")
    def test_promote_continues_if_record_storage_fails(
        self, controller: MagicMock
    ) -> None:
        """Test promote() continues even if promotion record storage fails.

        ⚠️ TDD: This test WILL FAIL until T032a implements recovery logic.

        Promotion record storage is for audit/traceability. If it fails,
        the promotion itself should still succeed (tags are created).
        The record storage failure should be logged but not block promotion.
        """
        from floe_core.schemas.promotion import PromotionRecord

        # Test constants

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            # Record storage fails
            mock_store.side_effect = Exception("Storage failed")

            # Should still succeed (warn but don't fail)
            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            assert isinstance(result, PromotionRecord)
            # Verify retry happened (3 attempts)
            assert mock_store.call_count == 3

    @pytest.mark.requirement("8C-NFR-004")
    def test_promote_records_partial_failure_in_result(
        self, controller: MagicMock
    ) -> None:
        """Test promote() records partial failures in the result.

        If record storage fails, the PromotionRecord should indicate
        that there were warnings during promotion.
        """
        from floe_core.schemas.promotion import PromotionRecord

        # Test constants

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = "v1.0.0-staging"
            mock_get_digest.return_value = TEST_DIGEST

            # Record storage fails
            mock_store.side_effect = Exception("Storage failed")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Result should indicate partial failure
            assert isinstance(result, PromotionRecord)
            assert hasattr(result, "warnings")
            assert len(result.warnings) > 0
            assert "Promotion record storage failed" in result.warnings[0]
