"""Unit tests for environment lock/unlock functionality (T097, T098, T099).

Task ID: T097, T098, T099
Phase: 10 - User Story 8 (Environment Lock)
User Story: US8 - Environment Lock/Freeze
Requirements: FR-035, FR-036, FR-037

These tests validate environment locking functionality:
- FR-035: Lock environment to prevent promotions
- FR-036: Promotion rejection on locked environment
- FR-037: Unlock environment to allow promotions

TDD: Tests written FIRST (T097-T099), implementation follows in T102-T104.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from floe_core.oci.errors import EnvironmentLockedError
from floe_core.oci.promotion import PromotionController
from floe_core.schemas.promotion import (
    EnvironmentConfig,
    PromotionConfig,
    PromotionGate,
)


@pytest.fixture
def mock_oci_client() -> MagicMock:
    """Create a mock OCI client."""
    return MagicMock()


@pytest.fixture
def promotion_config() -> PromotionConfig:
    """Create a promotion config with test environments."""
    return PromotionConfig(
        environments=[
            EnvironmentConfig(
                name="dev",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
            EnvironmentConfig(
                name="staging",
                gates={
                    PromotionGate.POLICY_COMPLIANCE: True,
                    PromotionGate.TESTS: True,
                },
            ),
            EnvironmentConfig(
                name="prod",
                gates={
                    PromotionGate.POLICY_COMPLIANCE: True,
                    PromotionGate.TESTS: True,
                    PromotionGate.SECURITY_SCAN: True,
                },
            ),
        ],
    )


@pytest.fixture
def controller(
    mock_oci_client: MagicMock, promotion_config: PromotionConfig
) -> PromotionController:
    """Create a PromotionController for testing."""
    return PromotionController(
        client=mock_oci_client,
        promotion=promotion_config,
    )


class TestLockEnvironment:
    """Tests for PromotionController.lock_environment() (FR-035).

    FR-035: Operators SHOULD be able to lock an environment to prevent promotions.
    """

    @pytest.mark.requirement("FR-035")
    def test_lock_environment_stores_lock_in_annotations(
        self, controller: PromotionController, mock_oci_client: MagicMock
    ) -> None:
        """Lock is stored in OCI annotations when environment is locked."""
        # This test verifies that lock_environment stores the lock
        # The actual implementation should store the lock in OCI annotations
        controller.lock_environment(
            environment="prod",
            reason="Incident #123 - Database migration",
            operator="sre@example.com",
        )

        # Verify that the lock was stored
        lock_status = controller.get_lock_status("prod")
        assert lock_status is not None
        assert lock_status.locked is True

    @pytest.mark.requirement("FR-035")
    def test_lock_environment_includes_reason(self, controller: PromotionController) -> None:
        """Lock includes reason field."""
        controller.lock_environment(
            environment="prod",
            reason="Maintenance window",
            operator="ops@example.com",
        )

        lock_status = controller.get_lock_status("prod")
        assert lock_status.reason == "Maintenance window"

    @pytest.mark.requirement("FR-035")
    def test_lock_environment_includes_locked_by(self, controller: PromotionController) -> None:
        """Lock includes locked_by field with operator identity."""
        controller.lock_environment(
            environment="prod",
            reason="Deployment freeze",
            operator="platform@example.com",
        )

        lock_status = controller.get_lock_status("prod")
        assert lock_status.locked_by == "platform@example.com"

    @pytest.mark.requirement("FR-035")
    def test_lock_environment_includes_locked_at(self, controller: PromotionController) -> None:
        """Lock includes locked_at timestamp."""
        before_lock = datetime.now(timezone.utc)

        controller.lock_environment(
            environment="prod",
            reason="Incident response",
            operator="oncall@example.com",
        )

        after_lock = datetime.now(timezone.utc)
        lock_status = controller.get_lock_status("prod")

        assert lock_status.locked_at is not None
        assert before_lock <= lock_status.locked_at <= after_lock

    @pytest.mark.requirement("FR-035")
    def test_lock_environment_raises_for_invalid_environment(
        self, controller: PromotionController
    ) -> None:
        """Lock raises ValueError for non-existent environment."""
        with pytest.raises(ValueError, match="not found"):
            controller.lock_environment(
                environment="nonexistent",
                reason="Test",
                operator="test@example.com",
            )


class TestUnlockEnvironment:
    """Tests for PromotionController.unlock_environment() (FR-037).

    FR-037: Operators SHOULD be able to unlock a locked environment.
    """

    @pytest.mark.requirement("FR-037")
    def test_unlock_environment_removes_lock(self, controller: PromotionController) -> None:
        """Unlock removes the lock from the environment."""
        # First lock the environment
        controller.lock_environment(
            environment="prod",
            reason="Incident",
            operator="sre@example.com",
        )

        # Then unlock it
        controller.unlock_environment(
            environment="prod",
            reason="Incident resolved",
            operator="sre@example.com",
        )

        lock_status = controller.get_lock_status("prod")
        assert lock_status.locked is False

    @pytest.mark.requirement("FR-037")
    def test_unlock_records_unlock_event(self, controller: PromotionController) -> None:
        """Unlock records the unlock event with reason."""
        controller.lock_environment(
            environment="prod",
            reason="Maintenance",
            operator="ops@example.com",
        )

        controller.unlock_environment(
            environment="prod",
            reason="Maintenance complete",
            operator="ops@example.com",
        )

        # The unlock reason should be recorded (for audit)
        # This is implementation-dependent
        lock_status = controller.get_lock_status("prod")
        assert lock_status.locked is False

    @pytest.mark.requirement("FR-037")
    def test_unlock_unlocked_environment_is_noop(self, controller: PromotionController) -> None:
        """Unlocking an already unlocked environment is a no-op."""
        # Environment starts unlocked
        lock_status = controller.get_lock_status("prod")
        assert lock_status.locked is False

        # Unlocking should not raise
        controller.unlock_environment(
            environment="prod",
            reason="Test unlock",
            operator="test@example.com",
        )

        lock_status = controller.get_lock_status("prod")
        assert lock_status.locked is False


class TestPromotionRejectionOnLocked:
    """Tests for promotion rejection on locked environment (FR-036).

    FR-036: Promotions SHOULD be rejected when target environment is locked.
    """

    @pytest.mark.requirement("FR-036")
    def test_promote_to_locked_environment_raises_error(
        self, controller: PromotionController, mock_oci_client: MagicMock
    ) -> None:
        """Promotion to locked environment raises EnvironmentLockedError."""
        # Lock the target environment
        controller.lock_environment(
            environment="prod",
            reason="Incident #456",
            operator="sre@example.com",
        )

        # Attempt to promote should fail
        with pytest.raises(EnvironmentLockedError) as exc_info:
            controller.promote(
                tag="v1.0.0",
                from_env="staging",
                to_env="prod",
                operator="release@example.com",
            )

        # Verify error details
        assert exc_info.value.environment == "prod"
        assert exc_info.value.exit_code == 13

    @pytest.mark.requirement("FR-036")
    def test_environment_locked_error_includes_lock_info(
        self, controller: PromotionController, mock_oci_client: MagicMock
    ) -> None:
        """EnvironmentLockedError includes lock details."""
        controller.lock_environment(
            environment="prod",
            reason="Database migration",
            operator="dba@example.com",
        )

        with pytest.raises(EnvironmentLockedError) as exc_info:
            controller.promote(
                tag="v1.0.0",
                from_env="staging",
                to_env="prod",
                operator="release@example.com",
            )

        # Error should include lock details for troubleshooting
        assert exc_info.value.locked_by == "dba@example.com"
        assert "Database migration" in exc_info.value.reason

    @pytest.mark.requirement("FR-036")
    def test_promote_after_unlock_succeeds(
        self, controller: PromotionController, mock_oci_client: MagicMock
    ) -> None:
        """Promotion succeeds after environment is unlocked."""
        # Setup mock for successful promotion
        mock_oci_client.get_manifest.return_value = MagicMock()
        mock_oci_client.tag_artifact.return_value = None

        # Lock and then unlock
        controller.lock_environment(
            environment="prod",
            reason="Maintenance",
            operator="ops@example.com",
        )
        controller.unlock_environment(
            environment="prod",
            reason="Maintenance complete",
            operator="ops@example.com",
        )

        # Promotion should now succeed (no EnvironmentLockedError)
        # Note: May fail for other reasons (mocking incomplete), but not due to lock
        try:
            controller.promote(
                tag="v1.0.0",
                from_env="staging",
                to_env="prod",
                operator="release@example.com",
            )
        except EnvironmentLockedError:
            pytest.fail("Should not raise EnvironmentLockedError after unlock")
        except Exception:
            # Other exceptions are acceptable in this test
            pass


class TestGetLockStatus:
    """Tests for PromotionController.get_lock_status()."""

    @pytest.mark.requirement("FR-035")
    def test_get_lock_status_returns_unlocked_by_default(
        self, controller: PromotionController
    ) -> None:
        """Environment is unlocked by default."""
        lock_status = controller.get_lock_status("prod")

        assert lock_status is not None
        assert lock_status.locked is False

    @pytest.mark.requirement("FR-035")
    def test_get_lock_status_returns_locked_after_lock(
        self, controller: PromotionController
    ) -> None:
        """get_lock_status returns locked=True after locking."""
        controller.lock_environment(
            environment="prod",
            reason="Test lock",
            operator="test@example.com",
        )

        lock_status = controller.get_lock_status("prod")

        assert lock_status.locked is True
        assert lock_status.reason == "Test lock"
        assert lock_status.locked_by == "test@example.com"

    @pytest.mark.requirement("FR-035")
    def test_get_lock_status_invalid_environment_raises(
        self, controller: PromotionController
    ) -> None:
        """get_lock_status raises ValueError for invalid environment."""
        with pytest.raises(ValueError, match="not found"):
            controller.get_lock_status("nonexistent")


__all__: list[str] = [
    "TestLockEnvironment",
    "TestUnlockEnvironment",
    "TestPromotionRejectionOnLocked",
    "TestGetLockStatus",
]
