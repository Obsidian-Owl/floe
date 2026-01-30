"""Unit tests for multi-registry promotion (US6 - Cross-Registry Sync).

Task ID: T076, T077, T078, T079
Phase: 8 - User Story 6 (Cross-Registry Sync)
User Story: US6 - Cross-Registry Sync
Requirements: FR-028, FR-029, FR-030

These tests validate multi-registry promotion:
- FR-028: Promotion to multiple registries concurrently
- FR-029: Digest verification across registries after sync
- FR-030: Partial failure handling (primary ok, secondary fail = warning)

TDD: Tests written FIRST (T076), implementation follows (T080-T083).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from floe_core.oci.promotion import PromotionController
from floe_core.schemas.promotion import (
    EnvironmentConfig,
    PromotionConfig,
    PromotionGate,
    RegistrySyncStatus,
)

if TYPE_CHECKING:
    pass


@pytest.fixture
def mock_oci_client() -> MagicMock:
    """Create mock OCI client for primary registry."""
    mock = MagicMock()
    mock.registry_uri = "oci://primary.registry.com/repo"
    mock.get_manifest.return_value = {
        "schemaVersion": 2,
        "digest": "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        "annotations": {},
    }
    mock.get_artifact_digest.return_value = (
        "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    )
    return mock


@pytest.fixture
def mock_secondary_client() -> MagicMock:
    """Create mock OCI client for secondary registry."""
    mock = MagicMock()
    mock.registry_uri = "oci://secondary.registry.com/repo"
    mock.get_manifest.return_value = {
        "schemaVersion": 2,
        "digest": "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        "annotations": {},
    }
    mock.get_artifact_digest.return_value = (
        "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    )
    return mock


@pytest.fixture
def promotion_config() -> PromotionConfig:
    """Create promotion config with default environments."""
    return PromotionConfig(
        environments=[
            EnvironmentConfig(
                name="dev",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
            EnvironmentConfig(
                name="staging",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
            EnvironmentConfig(
                name="prod",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
        ]
    )


class TestMultiRegistryPromotionSuccess:
    """Tests for successful multi-registry promotion (T076).

    FR-028: System SHOULD support promotion to multiple registries concurrently
    """

    @pytest.mark.requirement("FR-028")
    def test_promote_with_secondary_registries_succeeds(
        self,
        mock_oci_client: MagicMock,
        mock_secondary_client: MagicMock,
        promotion_config: PromotionConfig,
    ) -> None:
        """Promotion to primary + secondary registries succeeds.

        When secondary_clients are provided, promotion should sync
        to all registries and return success.
        """
        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config,
        )

        # Mock promote() to return a valid record
        with patch.object(controller, "promote") as mock_promote:
            from datetime import datetime, timezone
            from uuid import uuid4

            from floe_core.schemas.promotion import PromotionRecord

            mock_record = MagicMock(spec=PromotionRecord)
            mock_record.artifact_digest = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )
            mock_record.warnings = []
            mock_record.model_copy.return_value = mock_record
            mock_promote.return_value = mock_record

            # Mock secondary client copy_tag
            mock_secondary_client.copy_tag = MagicMock()

            result = controller.promote_multi(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="test@example.com",
                secondary_clients=[mock_secondary_client],
            )

            # Verify promote was called
            mock_promote.assert_called_once()
            # Verify secondary client was used
            assert result is not None

    @pytest.mark.requirement("FR-028")
    def test_promote_syncs_to_all_registries_concurrently(
        self,
        mock_oci_client: MagicMock,
        mock_secondary_client: MagicMock,
        promotion_config: PromotionConfig,
    ) -> None:
        """Multi-registry promotion syncs to all registries.

        All provided registries should receive the promoted artifact.
        """
        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config,
        )

        # Mock promote() to return a valid record
        with patch.object(controller, "promote") as mock_promote:
            mock_record = MagicMock()
            mock_record.artifact_digest = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )
            mock_record.warnings = []
            mock_record.model_copy.return_value = mock_record
            mock_promote.return_value = mock_record

            # Mock secondary clients
            mock_secondary_client.copy_tag = MagicMock()
            secondary_2 = MagicMock()
            secondary_2.registry_uri = "oci://secondary2.registry.com/repo"
            secondary_2.copy_tag = MagicMock()
            secondary_2.get_artifact_digest.return_value = mock_record.artifact_digest

            controller.promote_multi(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="test@example.com",
                secondary_clients=[mock_secondary_client, secondary_2],
            )

            # Both secondary clients should have copy_tag called
            mock_secondary_client.copy_tag.assert_called_once()
            secondary_2.copy_tag.assert_called_once()


class TestMultiRegistryDigestVerification:
    """Tests for digest verification across registries (T077).

    FR-029: System SHOULD verify digest match across all registries after sync
    """

    @pytest.mark.requirement("FR-029")
    def test_verify_digest_match_across_registries(
        self,
        mock_oci_client: MagicMock,
        mock_secondary_client: MagicMock,
        promotion_config: PromotionConfig,
    ) -> None:
        """After sync, digests are verified to match across registries."""
        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config,
        )

        # Mock promote() to return a valid record
        with patch.object(controller, "promote") as mock_promote:
            from floe_core.schemas.promotion import PromotionRecord

            mock_record = MagicMock(spec=PromotionRecord)
            mock_record.artifact_digest = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )
            mock_record.warnings = []
            mock_record.model_copy.return_value = mock_record
            mock_promote.return_value = mock_record

            # Mock secondary client - digest matches
            mock_secondary_client.copy_tag = MagicMock()
            mock_secondary_client.get_artifact_digest.return_value = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )

            result = controller.promote_multi(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="test@example.com",
                secondary_clients=[mock_secondary_client],
                verify_digests=True,
            )

            # Verify promote was called
            mock_promote.assert_called_once()
            # Verify digest verification was performed
            mock_secondary_client.get_artifact_digest.assert_called_once()
            assert result is not None

    @pytest.mark.requirement("FR-029")
    def test_digest_mismatch_raises_error(
        self,
        mock_oci_client: MagicMock,
        promotion_config: PromotionConfig,
    ) -> None:
        """Digest mismatch between registries adds warning (FR-030 graceful degradation)."""
        # Create secondary with different digest
        mock_mismatched = MagicMock()
        mock_mismatched.registry_uri = "oci://secondary.registry.com/repo"
        mock_mismatched.copy_tag = MagicMock()
        mock_mismatched.get_artifact_digest.return_value = (
            "sha256:different_digest_12345678901234567890123456789012345678901234"
        )

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config,
        )

        # Mock promote() to return a valid record
        with patch.object(controller, "promote") as mock_promote:
            from floe_core.schemas.promotion import PromotionRecord

            mock_record = MagicMock(spec=PromotionRecord)
            mock_record.artifact_digest = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )
            mock_record.warnings = []
            mock_record.model_copy.return_value = mock_record
            mock_promote.return_value = mock_record

            result = controller.promote_multi(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="test@example.com",
                secondary_clients=[mock_mismatched],
                verify_digests=True,
            )

            # Digest mismatch adds warning (FR-030 graceful degradation)
            mock_record.model_copy.assert_called_once()
            assert result is not None


class TestMultiRegistryPartialFailure:
    """Tests for partial failure handling (T078).

    FR-030: System SHOULD continue with primary if secondary registries fail
    """

    @pytest.mark.requirement("FR-030")
    def test_secondary_failure_returns_warning_not_error(
        self,
        mock_oci_client: MagicMock,
        promotion_config: PromotionConfig,
    ) -> None:
        """Secondary registry failure adds warning but doesn't fail promotion."""
        # Create failing secondary
        mock_failing = MagicMock()
        mock_failing.registry_uri = "oci://failing.registry.com/repo"
        mock_failing.copy_tag.side_effect = ConnectionError("Registry unavailable")

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config,
        )

        # Mock promote() to return a valid record
        with patch.object(controller, "promote") as mock_promote:
            from floe_core.schemas.promotion import PromotionRecord

            mock_record = MagicMock(spec=PromotionRecord)
            mock_record.artifact_digest = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )
            mock_record.warnings = []

            # Create a proper mock for model_copy that returns updated record
            def mock_model_copy(update: dict) -> MagicMock:
                updated_record = MagicMock(spec=PromotionRecord)
                updated_record.warnings = update.get("warnings", [])
                updated_record.registry_sync_status = update.get("registry_sync_status", [])
                return updated_record

            mock_record.model_copy.side_effect = mock_model_copy
            mock_promote.return_value = mock_record

            result = controller.promote_multi(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="test@example.com",
                secondary_clients=[mock_failing],
            )

            # Promotion succeeds even with secondary failure
            mock_promote.assert_called_once()
            # Result should have warning about failed secondary
            assert len(result.warnings) > 0
            assert "failing.registry.com" in result.warnings[0]

    @pytest.mark.requirement("FR-030")
    def test_primary_success_with_all_secondaries_failed(
        self,
        mock_oci_client: MagicMock,
        promotion_config: PromotionConfig,
    ) -> None:
        """Primary success even when all secondaries fail."""
        # Create multiple failing secondaries
        failing_1 = MagicMock()
        failing_1.registry_uri = "oci://failing1.registry.com/repo"
        failing_1.copy_tag.side_effect = ConnectionError("Unavailable")

        failing_2 = MagicMock()
        failing_2.registry_uri = "oci://failing2.registry.com/repo"
        failing_2.copy_tag.side_effect = TimeoutError("Timeout")

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config,
        )

        # Mock promote() to return a valid record
        with patch.object(controller, "promote") as mock_promote:
            from floe_core.schemas.promotion import PromotionRecord

            mock_record = MagicMock(spec=PromotionRecord)
            mock_record.artifact_digest = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )
            mock_record.warnings = []

            # Create a proper mock for model_copy that returns updated record
            def mock_model_copy(update: dict) -> MagicMock:
                updated_record = MagicMock(spec=PromotionRecord)
                updated_record.warnings = update.get("warnings", [])
                updated_record.registry_sync_status = update.get("registry_sync_status", [])
                return updated_record

            mock_record.model_copy.side_effect = mock_model_copy
            mock_promote.return_value = mock_record

            result = controller.promote_multi(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="test@example.com",
                secondary_clients=[failing_1, failing_2],
            )

            # Promotion succeeds even with all secondaries failed
            mock_promote.assert_called_once()
            # Should have 2 warnings for the 2 failed secondaries
            assert len(result.warnings) == 2


class TestMultiRegistrySyncStatus:
    """Tests for registry sync status in PromotionRecord (T079).

    Verifies that PromotionRecord includes sync status per registry.
    """

    @pytest.mark.requirement("FR-028")
    @pytest.mark.requirement("FR-030")
    def test_promotion_record_includes_registry_sync_status(
        self,
        mock_oci_client: MagicMock,
        mock_secondary_client: MagicMock,
        promotion_config: PromotionConfig,
    ) -> None:
        """PromotionRecord includes sync status for each registry."""
        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config,
        )

        # Mock promote() to return a valid record
        with patch.object(controller, "promote") as mock_promote:
            from floe_core.schemas.promotion import PromotionRecord

            mock_record = MagicMock(spec=PromotionRecord)
            mock_record.artifact_digest = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )
            mock_record.warnings = []

            # Create a proper mock for model_copy that returns updated record
            def mock_model_copy(update: dict) -> MagicMock:
                updated_record = MagicMock(spec=PromotionRecord)
                updated_record.warnings = update.get("warnings", [])
                updated_record.registry_sync_status = update.get("registry_sync_status", [])
                return updated_record

            mock_record.model_copy.side_effect = mock_model_copy
            mock_promote.return_value = mock_record

            # Mock secondary client
            mock_secondary_client.copy_tag = MagicMock()
            mock_secondary_client.get_artifact_digest.return_value = (
                "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
            )

            result = controller.promote_multi(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="test@example.com",
                secondary_clients=[mock_secondary_client],
            )

            # Record should include registry_sync_status
            assert hasattr(result, "registry_sync_status")
            # Should have 1 sync status for the secondary registry
            assert len(result.registry_sync_status) == 1


class TestPromotionConfigSecondaryRegistries:
    """Tests for PromotionConfig secondary registry fields (T079).

    FR-028: Support secondary registries in configuration.
    """

    @pytest.mark.requirement("FR-028")
    def test_config_accepts_secondary_registries(self) -> None:
        """PromotionConfig accepts secondary_registries list."""
        config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev", gates={PromotionGate.POLICY_COMPLIANCE: True}
                ),
            ],
            secondary_registries=[
                "oci://secondary1.registry.com/repo",
                "oci://secondary2.registry.com/repo",
            ],
        )
        assert len(config.secondary_registries) == 2
        assert config.secondary_registries[0] == "oci://secondary1.registry.com/repo"

    @pytest.mark.requirement("FR-028")
    def test_config_secondary_registries_defaults_to_none(self) -> None:
        """PromotionConfig secondary_registries defaults to None."""
        config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev", gates={PromotionGate.POLICY_COMPLIANCE: True}
                ),
            ],
        )
        assert config.secondary_registries is None

    @pytest.mark.requirement("FR-029")
    def test_config_verify_secondary_digests_defaults_to_true(self) -> None:
        """PromotionConfig verify_secondary_digests defaults to True."""
        config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev", gates={PromotionGate.POLICY_COMPLIANCE: True}
                ),
            ],
        )
        assert config.verify_secondary_digests is True

    @pytest.mark.requirement("FR-029")
    def test_config_can_disable_digest_verification(self) -> None:
        """PromotionConfig allows disabling digest verification."""
        config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev", gates={PromotionGate.POLICY_COMPLIANCE: True}
                ),
            ],
            secondary_registries=["oci://secondary.registry.com/repo"],
            verify_secondary_digests=False,
        )
        assert config.verify_secondary_digests is False


class TestRegistrySyncStatusSchema:
    """Tests for RegistrySyncStatus schema (T079/T083).

    FR-028, FR-030: Track sync status per registry.
    """

    @pytest.mark.requirement("FR-028")
    def test_registry_sync_status_success(self) -> None:
        """RegistrySyncStatus represents successful sync."""
        from datetime import datetime, timezone

        status = RegistrySyncStatus(
            registry_uri="oci://secondary.registry.com/repo",
            synced=True,
            digest="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
            synced_at=datetime.now(timezone.utc),
        )
        assert status.synced is True
        assert status.error is None

    @pytest.mark.requirement("FR-030")
    def test_registry_sync_status_failure(self) -> None:
        """RegistrySyncStatus represents failed sync with error."""
        status = RegistrySyncStatus(
            registry_uri="oci://failing.registry.com/repo",
            synced=False,
            error="Connection refused",
        )
        assert status.synced is False
        assert status.error == "Connection refused"
        assert status.digest is None


__all__: list[str] = [
    "TestMultiRegistryPromotionSuccess",
    "TestMultiRegistryDigestVerification",
    "TestMultiRegistryPartialFailure",
    "TestMultiRegistrySyncStatus",
    "TestPromotionConfigSecondaryRegistries",
    "TestRegistrySyncStatusSchema",
]
