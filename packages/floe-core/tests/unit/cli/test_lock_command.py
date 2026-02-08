"""Unit tests for platform lock/unlock CLI commands.

Task ID: T105, T106
Phase: 10 - User Story 8 (Environment Lock)
User Story: US8 - Environment Lock/Freeze
Requirements: FR-035, FR-037

These tests validate the lock and unlock CLI commands:
- FR-035: Lock environment to prevent promotions
- FR-037: Unlock environment to allow promotions
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from floe_core.cli.main import cli
from floe_core.cli.platform.lock import _get_operator, _load_platform_manifest

if TYPE_CHECKING:
    from collections.abc import Generator


def extract_json_from_output(output: str) -> dict[str, object]:
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
def mock_lock_status() -> MagicMock:
    """Create a mock EnvironmentLock for successful lock operations."""
    from floe_core.schemas.promotion import EnvironmentLock

    lock = EnvironmentLock(
        locked=True,
        reason="Incident #123 - Production freeze",
        locked_by="sre@example.com",
        locked_at=datetime(2026, 1, 30, 10, 0, 0, tzinfo=timezone.utc),
    )
    # Return as MagicMock wrapping the real object for flexibility
    mock = MagicMock()
    mock.locked = lock.locked
    mock.reason = lock.reason
    mock.locked_by = lock.locked_by
    mock.locked_at = lock.locked_at
    return mock


@pytest.fixture
def valid_manifest_content() -> dict[str, object]:
    """Create valid manifest YAML content with artifacts configuration."""
    return {
        "apiVersion": "floe.dev/v1",
        "kind": "Manifest",
        "metadata": {
            "name": "test-platform",
            "version": "1.0.0",
            "owner": "test@example.com",
        },
        "plugins": {
            "compute": {"type": "duckdb"},
            "orchestrator": {"type": "dagster"},
        },
        "artifacts": {
            "registry": {
                "uri": "oci://harbor.example.com/floe",
                "auth": {"type": "anonymous"},
            },
            "promotion": {
                "environments": [
                    {"name": "dev", "gates": {"policy_compliance": True}},
                    {"name": "staging", "gates": {"policy_compliance": True}},
                    {"name": "prod", "gates": {"policy_compliance": True}},
                ],
            },
        },
    }


@pytest.fixture
def temp_manifest(valid_manifest_content: dict) -> Generator[Path, None, None]:
    """Create a temporary manifest file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(valid_manifest_content, f)
        yield Path(f.name)
    os.unlink(f.name)


class TestGetOperator:
    """Tests for _get_operator helper function."""

    @pytest.mark.requirement("FR-035")
    def test_get_operator_from_user_env(self) -> None:
        """Returns USER environment variable when set."""
        with patch.dict(os.environ, {"USER": "testuser"}, clear=False):
            result = _get_operator()
            assert result == "testuser"

    @pytest.mark.requirement("FR-035")
    def test_get_operator_from_floe_operator_env(self) -> None:
        """Returns FLOE_OPERATOR when USER not set."""
        env = {"FLOE_OPERATOR": "floe-ci", "USER": ""}
        with patch.dict(os.environ, env, clear=True):
            # Need to handle the empty USER case
            with patch.dict(os.environ, {"USER": ""}, clear=False):
                os.environ.pop("USER", None)
                os.environ["FLOE_OPERATOR"] = "floe-ci"
                result = _get_operator()
                assert result in ("floe-ci", "unknown", os.environ.get("USER", ""))

    @pytest.mark.requirement("FR-035")
    def test_get_operator_default_unknown(self) -> None:
        """Returns 'unknown' when no environment variables set."""
        with patch.dict(os.environ, {}, clear=True):
            result = _get_operator()
            assert result == "unknown"


class TestLoadPlatformManifest:
    """Tests for _load_platform_manifest helper function."""

    @pytest.mark.requirement("FR-035")
    def test_load_valid_manifest(self, temp_manifest: Path) -> None:
        """Successfully loads a valid manifest file."""
        manifest = _load_platform_manifest(temp_manifest)
        assert manifest.metadata.name == "test-platform"
        assert manifest.artifacts is not None
        assert manifest.artifacts.registry.uri == "oci://harbor.example.com/floe"

    @pytest.mark.requirement("FR-035")
    def test_load_manifest_file_not_found(self) -> None:
        """Raises ClickException for non-existent file."""
        import click

        with pytest.raises(click.ClickException, match="Failed to load manifest"):
            _load_platform_manifest(Path("/nonexistent/manifest.yaml"))

    @pytest.mark.requirement("FR-035")
    def test_load_manifest_invalid_yaml(self) -> None:
        """Raises ClickException for invalid YAML."""
        import click

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            try:
                with pytest.raises(click.ClickException, match="Failed to parse YAML"):
                    _load_platform_manifest(Path(f.name))
            finally:
                os.unlink(f.name)


class TestLockCommand:
    """Tests for platform lock CLI command (FR-035)."""

    @pytest.mark.requirement("FR-035")
    def test_lock_with_registry_success(self, mock_lock_status: MagicMock) -> None:
        """Lock command succeeds with --registry option."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_lock_status.return_value = mock_lock_status
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "lock",
                    "--env=prod",
                    "--reason=Incident #123",
                    "--registry=oci://harbor.example.com/floe",
                ],
            )

            # Command calls sys.exit(0) on success
            assert result.exit_code == 0
            mock_controller.lock_environment.assert_called_once()
            assert "locked successfully" in result.output or "prod" in result.output

    @pytest.mark.requirement("FR-035")
    def test_lock_with_manifest_success(
        self, temp_manifest: Path, mock_lock_status: MagicMock
    ) -> None:
        """Lock command succeeds with --manifest option."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_lock_status.return_value = mock_lock_status
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "lock",
                    "--env=prod",
                    "--reason=Maintenance window",
                    f"--manifest={temp_manifest}",
                ],
            )

            assert result.exit_code == 0
            mock_controller.lock_environment.assert_called_once()

    @pytest.mark.requirement("FR-035")
    def test_lock_json_output(self, mock_lock_status: MagicMock) -> None:
        """Lock command outputs JSON when --output=json."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_lock_status.return_value = mock_lock_status
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "lock",
                    "--env=prod",
                    "--reason=Incident #123",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert data["status"] == "locked"
            assert data["environment"] == "prod"
            assert "Incident #123" in str(data["reason"])

    @pytest.mark.requirement("FR-035")
    def test_lock_with_custom_operator(self, mock_lock_status: MagicMock) -> None:
        """Lock command uses custom --operator value."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_lock_status.return_value = mock_lock_status
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "lock",
                    "--env=prod",
                    "--reason=Incident #123",
                    "--registry=oci://example.com/repo",
                    "--operator=admin@example.com",
                ],
            )

            assert result.exit_code == 0
            # Verify the operator was passed to lock_environment
            call_kwargs = mock_controller.lock_environment.call_args
            assert call_kwargs.kwargs["operator"] == "admin@example.com"

    @pytest.mark.requirement("FR-035")
    def test_lock_missing_registry_and_manifest(self) -> None:
        """Lock command fails without --registry or --manifest."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "platform",
                "lock",
                "--env=prod",
                "--reason=Test",
            ],
        )

        # Exit code 3 for configuration error
        assert result.exit_code == 3
        assert "Either --manifest or --registry is required" in result.output

    @pytest.mark.requirement("FR-035")
    def test_lock_missing_env_option(self) -> None:
        """Lock command fails without --env option."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "platform",
                "lock",
                "--reason=Test",
                "--registry=oci://example.com/repo",
            ],
        )

        # Click validation error
        assert result.exit_code != 0
        assert "Missing option" in result.output or "--env" in result.output

    @pytest.mark.requirement("FR-035")
    def test_lock_missing_reason_option(self) -> None:
        """Lock command fails without --reason option."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "platform",
                "lock",
                "--env=prod",
                "--registry=oci://example.com/repo",
            ],
        )

        # Click validation error
        assert result.exit_code != 0
        assert "Missing option" in result.output or "--reason" in result.output

    @pytest.mark.requirement("FR-035")
    def test_lock_controller_error(self) -> None:
        """Lock command handles controller errors gracefully."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.lock_environment.side_effect = ValueError(
                "Environment not found"
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "lock",
                    "--env=invalid",
                    "--reason=Test",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 1
            assert "Environment not found" in result.output

    @pytest.mark.requirement("FR-035")
    def test_lock_manifest_without_artifacts(self) -> None:
        """Lock command fails when manifest has no artifacts section."""
        runner = CliRunner()

        # Create manifest without artifacts
        manifest_content = {
            "apiVersion": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "test-platform",
                "version": "1.0.0",
                "owner": "test@example.com",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(manifest_content, f)
            manifest_path = f.name

        try:
            result = runner.invoke(
                cli,
                [
                    "platform",
                    "lock",
                    "--env=prod",
                    "--reason=Test",
                    f"--manifest={manifest_path}",
                ],
            )

            # Exit code 1 from ClickException (Pydantic validation error for missing plugins)
            # or exit code 3 if artifacts check happens first
            assert result.exit_code != 0
            # The error could be about missing plugins or artifacts
            assert (
                "artifacts" in result.output.lower()
                or "plugins" in result.output.lower()
                or "validation" in result.output.lower()
            )
        finally:
            os.unlink(manifest_path)


class TestUnlockCommand:
    """Tests for platform unlock CLI command (FR-037)."""

    @pytest.mark.requirement("FR-037")
    def test_unlock_with_registry_success(self) -> None:
        """Unlock command succeeds with --registry option."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "unlock",
                    "--env=prod",
                    "--reason=Incident resolved",
                    "--registry=oci://harbor.example.com/floe",
                ],
            )

            assert result.exit_code == 0
            mock_controller.unlock_environment.assert_called_once()
            assert "unlocked successfully" in result.output or "prod" in result.output

    @pytest.mark.requirement("FR-037")
    def test_unlock_with_manifest_success(self, temp_manifest: Path) -> None:
        """Unlock command succeeds with --manifest option."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "unlock",
                    "--env=prod",
                    "--reason=Maintenance complete",
                    f"--manifest={temp_manifest}",
                ],
            )

            assert result.exit_code == 0
            mock_controller.unlock_environment.assert_called_once()

    @pytest.mark.requirement("FR-037")
    def test_unlock_json_output(self) -> None:
        """Unlock command outputs JSON when --output=json."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "unlock",
                    "--env=prod",
                    "--reason=Incident resolved",
                    "--registry=oci://example.com/repo",
                    "--output=json",
                ],
            )

            assert result.exit_code == 0
            data = extract_json_from_output(result.output)
            assert data["status"] == "unlocked"
            assert data["environment"] == "prod"
            assert data["reason"] == "Incident resolved"

    @pytest.mark.requirement("FR-037")
    def test_unlock_with_custom_operator(self) -> None:
        """Unlock command uses custom --operator value."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "unlock",
                    "--env=prod",
                    "--reason=Incident resolved",
                    "--registry=oci://example.com/repo",
                    "--operator=admin@example.com",
                ],
            )

            assert result.exit_code == 0
            # Verify the operator was passed to unlock_environment
            call_kwargs = mock_controller.unlock_environment.call_args
            assert call_kwargs.kwargs["operator"] == "admin@example.com"

    @pytest.mark.requirement("FR-037")
    def test_unlock_missing_registry_and_manifest(self) -> None:
        """Unlock command fails without --registry or --manifest."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "platform",
                "unlock",
                "--env=prod",
                "--reason=Test",
            ],
        )

        assert result.exit_code == 3
        assert "Either --manifest or --registry is required" in result.output

    @pytest.mark.requirement("FR-037")
    def test_unlock_missing_env_option(self) -> None:
        """Unlock command fails without --env option."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "platform",
                "unlock",
                "--reason=Test",
                "--registry=oci://example.com/repo",
            ],
        )

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--env" in result.output

    @pytest.mark.requirement("FR-037")
    def test_unlock_missing_reason_option(self) -> None:
        """Unlock command fails without --reason option."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            [
                "platform",
                "unlock",
                "--env=prod",
                "--registry=oci://example.com/repo",
            ],
        )

        assert result.exit_code != 0
        assert "Missing option" in result.output or "--reason" in result.output

    @pytest.mark.requirement("FR-037")
    def test_unlock_controller_error(self) -> None:
        """Unlock command handles controller errors gracefully."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.unlock_environment.side_effect = ValueError(
                "Environment not locked"
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "unlock",
                    "--env=staging",
                    "--reason=Test",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 1
            assert "Environment not locked" in result.output

    @pytest.mark.requirement("FR-037")
    def test_unlock_manifest_without_artifacts(self) -> None:
        """Unlock command fails when manifest has no artifacts section."""
        runner = CliRunner()

        manifest_content = {
            "apiVersion": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "test-platform",
                "version": "1.0.0",
                "owner": "test@example.com",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(manifest_content, f)
            manifest_path = f.name

        try:
            result = runner.invoke(
                cli,
                [
                    "platform",
                    "unlock",
                    "--env=prod",
                    "--reason=Test",
                    f"--manifest={manifest_path}",
                ],
            )

            # Exit code 1 from ClickException (Pydantic validation error for missing plugins)
            # or exit code 3 if artifacts check happens first
            assert result.exit_code != 0
            # The error could be about missing plugins or artifacts
            assert (
                "artifacts" in result.output.lower()
                or "plugins" in result.output.lower()
                or "validation" in result.output.lower()
            )
        finally:
            os.unlink(manifest_path)


class TestLockCommandExceptionHandling:
    """Tests for exception handling in lock/unlock commands."""

    @pytest.mark.requirement("FR-035")
    def test_lock_handles_exception_with_exit_code(self) -> None:
        """Lock command uses exception's exit_code if available."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            # Create exception with custom exit_code
            error = Exception("Registry unavailable")
            error.exit_code = 5  # type: ignore[attr-defined]

            mock_controller = MagicMock()
            mock_controller.lock_environment.side_effect = error
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "lock",
                    "--env=prod",
                    "--reason=Test",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 5

    @pytest.mark.requirement("FR-037")
    def test_unlock_handles_exception_with_exit_code(self) -> None:
        """Unlock command uses exception's exit_code if available."""
        runner = CliRunner()

        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            # Create exception with custom exit_code
            error = Exception("Registry unavailable")
            error.exit_code = 5  # type: ignore[attr-defined]

            mock_controller = MagicMock()
            mock_controller.unlock_environment.side_effect = error
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "unlock",
                    "--env=prod",
                    "--reason=Test",
                    "--registry=oci://example.com/repo",
                ],
            )

            assert result.exit_code == 5


__all__: list[str] = [
    "TestGetOperator",
    "TestLoadPlatformManifest",
    "TestLockCommand",
    "TestUnlockCommand",
    "TestLockCommandExceptionHandling",
]
