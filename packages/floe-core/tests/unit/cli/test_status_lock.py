"""Unit tests for lock status display in status command (T100).

Task ID: T100
Phase: 10 - User Story 8 (Environment Lock)
User Story: US8 - Environment Lock/Freeze
Requirements: FR-039

These tests validate lock status display in the status command:
- FR-039: Locked environments shown with lock indicator
- Lock reason and operator displayed in output

TDD: Tests written FIRST (T100), implementation follows in T108.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli

if TYPE_CHECKING:
    pass


def extract_json_from_output(output: str) -> dict:
    """Extract JSON object from CLI output that may contain log messages.

    Args:
        output: Raw CLI output that may contain log messages and JSON.

    Returns:
        Parsed JSON dictionary.
    """
    start = output.find("{")
    if start == -1:
        return json.loads(output)

    depth = 0
    for i, char in enumerate(output[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(output[start : i + 1])

    return json.loads(output[start:])


@pytest.fixture
def mock_status_with_locked_env() -> MagicMock:
    """Create a mock PromotionStatusResponse with a locked environment.

    Note: This uses MagicMock because PromotionStatusResponse doesn't have
    environment_locks field yet. The field will be added as part of US8 implementation.
    """
    from floe_core.schemas.promotion import (
        EnvironmentLock,
        EnvironmentStatus,
    )

    # Create mock response with environment_locks field (to be added to schema)
    mock_response = MagicMock()
    mock_response.tag = "v1.0.0"
    mock_response.digest = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    mock_response.environments = {
        "dev": EnvironmentStatus(
            promoted=True,
            promoted_at=datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc),
            is_latest=False,
            operator="ci@example.com",
        ),
        "staging": EnvironmentStatus(
            promoted=True,
            promoted_at=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            is_latest=True,
            operator="release@example.com",
        ),
        "prod": EnvironmentStatus(
            promoted=False,
            promoted_at=None,
            is_latest=False,
            operator=None,
        ),
    }
    mock_response.history = []
    mock_response.queried_at = datetime.now(timezone.utc)
    # Lock status for the prod environment (to be added to schema)
    mock_response.environment_locks = {
        "prod": EnvironmentLock(
            locked=True,
            reason="Incident #456 - Database migration in progress",
            locked_by="sre@example.com",
            locked_at=datetime(2026, 1, 30, 8, 0, 0, tzinfo=timezone.utc),
        ),
    }
    # Mock model_dump for JSON serialization
    mock_response.model_dump.return_value = {
        "tag": mock_response.tag,
        "digest": mock_response.digest,
        "environments": {
            name: {
                "promoted": env.promoted,
                "promoted_at": env.promoted_at.isoformat() if env.promoted_at else None,
                "is_latest": env.is_latest,
                "operator": env.operator,
            }
            for name, env in mock_response.environments.items()
        },
        "history": [],
        "queried_at": mock_response.queried_at.isoformat(),
        "environment_locks": {
            "prod": {
                "locked": True,
                "reason": "Incident #456 - Database migration in progress",
                "locked_by": "sre@example.com",
                "locked_at": "2026-01-30T08:00:00+00:00",
            }
        },
    }
    return mock_response


@pytest.fixture
def mock_status_all_unlocked() -> MagicMock:
    """Create a mock PromotionStatusResponse with all environments unlocked."""
    from floe_core.schemas.promotion import (
        EnvironmentStatus,
        PromotionStatusResponse,
    )

    return PromotionStatusResponse(
        tag="v1.0.0",
        digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        environments={
            "dev": EnvironmentStatus(
                promoted=True,
                promoted_at=datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc),
                is_latest=False,
                operator="ci@example.com",
            ),
            "staging": EnvironmentStatus(
                promoted=True,
                promoted_at=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
                is_latest=True,
                operator="release@example.com",
            ),
            "prod": EnvironmentStatus(
                promoted=False,
                promoted_at=None,
                is_latest=False,
                operator=None,
            ),
        },
        history=[],
        queried_at=datetime.now(timezone.utc),
    )


class TestStatusLockTableOutput:
    """Tests for lock status in table output format (FR-039)."""

    @pytest.mark.requirement("FR-039")
    def test_locked_environment_shows_lock_indicator(
        self, mock_status_with_locked_env: MagicMock
    ) -> None:
        """Locked environment shows lock indicator in table output."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_with_locked_env
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 0
            # Look for lock indicator (could be 🔒, [LOCKED], or similar)
            assert "🔒" in result.output or "[LOCKED]" in result.output or "LOCKED" in result.output

    @pytest.mark.requirement("FR-039")
    def test_locked_environment_shows_lock_reason(
        self, mock_status_with_locked_env: MagicMock
    ) -> None:
        """Locked environment shows lock reason in table output."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_with_locked_env
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 0
            # Lock reason should be visible
            assert "Incident #456" in result.output or "Database migration" in result.output

    @pytest.mark.requirement("FR-039")
    def test_locked_environment_shows_locked_by(
        self, mock_status_with_locked_env: MagicMock
    ) -> None:
        """Locked environment shows who locked it in table output."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_with_locked_env
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 0
            # Locked by should be visible
            assert "sre@example.com" in result.output

    @pytest.mark.requirement("FR-039")
    def test_unlocked_environment_no_lock_indicator(
        self, mock_status_all_unlocked: MagicMock
    ) -> None:
        """Unlocked environments do not show lock indicator."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_all_unlocked
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 0
            # No lock indicators for unlocked environments
            assert "🔒" not in result.output
            assert "[LOCKED]" not in result.output


class TestStatusLockJsonOutput:
    """Tests for lock status in JSON output format (FR-039)."""

    @pytest.mark.requirement("FR-039")
    def test_json_output_includes_lock_status(self, mock_status_with_locked_env: MagicMock) -> None:
        """JSON output includes lock status for environments."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_with_locked_env
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)

            # JSON should include environment_locks or lock info per environment
            assert "environment_locks" in data or any(
                "lock" in str(env).lower() for env in data.get("environments", {}).values()
            )

    @pytest.mark.requirement("FR-039")
    def test_json_output_includes_lock_details(
        self, mock_status_with_locked_env: MagicMock
    ) -> None:
        """JSON output includes lock details (locked_by, reason, locked_at)."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_with_locked_env
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)

            # Check for lock details in the output
            output_str = json.dumps(data)
            assert "sre@example.com" in output_str  # locked_by
            assert "Incident" in output_str or "migration" in output_str  # reason

    @pytest.mark.requirement("FR-039")
    def test_json_output_unlocked_shows_false(self, mock_status_all_unlocked: MagicMock) -> None:
        """JSON output shows locked=false for unlocked environments."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_all_unlocked
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--format=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)

            # No environment_locks key or all locks are false
            if "environment_locks" in data:
                for lock in data["environment_locks"].values():
                    if isinstance(lock, dict):
                        assert lock.get("locked") is False


class TestStatusLockWithEnvFilter:
    """Tests for lock status with environment filtering."""

    @pytest.mark.requirement("FR-039")
    def test_env_filter_shows_lock_for_locked_env(
        self, mock_status_with_locked_env: MagicMock
    ) -> None:
        """Environment filter shows lock when filtering to locked environment."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_with_locked_env
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://example.com/repo",
                    "--env=prod",
                ],
            )

            assert result.exit_code == 0
            # Lock should be visible when filtering to locked environment
            assert "🔒" in result.output or "[LOCKED]" in result.output or "LOCKED" in result.output


__all__: list[str] = [
    "TestStatusLockTableOutput",
    "TestStatusLockJsonOutput",
    "TestStatusLockWithEnvFilter",
]
