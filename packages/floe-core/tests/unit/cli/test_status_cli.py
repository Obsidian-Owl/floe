"""Unit tests for status CLI command output formatting (T060).

Tests for the `floe platform status` command output formats:
- Table output format
- JSON output format
- YAML output format
- Environment filtering (--env)
- History limiting (--history=N)

Task ID: T060
Phase: 6 - User Story 4 (Status)
Requirements: FR-023, FR-024, FR-027

TDD Note: These tests are written FIRST per TDD methodology.
The status command is currently a stub - tests SHOULD FAIL until T063-T066 implement.

See Also:
    - specs/8c-promotion-lifecycle/spec.md: Feature specification
    - User Story 4: Query Promotion Status
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import uuid4

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
def mock_status_response() -> MagicMock:
    """Create a mock PromotionStatusResponse for testing output formatting."""
    from floe_core.schemas.promotion import (
        EnvironmentStatus,
        PromotionHistoryEntry,
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
        history=[
            PromotionHistoryEntry(
                promotion_id=str(uuid4()),
                artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                source_environment="dev",
                target_environment="staging",
                operator="release@example.com",
                promoted_at=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            ),
            PromotionHistoryEntry(
                promotion_id=str(uuid4()),
                artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                source_environment="build",
                target_environment="dev",
                operator="ci@example.com",
                promoted_at=datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc),
            ),
        ],
        queried_at=datetime.now(timezone.utc),
    )


class TestStatusCliBasic:
    """Basic tests for status CLI command structure."""

    @pytest.mark.requirement("8C-FR-023")
    def test_status_command_exists(self) -> None:
        """Test that status command is registered under platform."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "status", "--help"])
        # Note: Currently a stub, but --help should work
        assert result.exit_code == 0
        assert "status" in result.output.lower()

    @pytest.mark.requirement("8C-FR-023")
    def test_status_requires_tag_argument(self) -> None:
        """Test that status command requires a tag argument."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["platform", "status", "--registry=oci://test.io/repo"],
        )
        # Should fail due to missing TAG argument
        assert result.exit_code != 0


class TestStatusCliTableOutput:
    """Tests for status CLI table output format."""

    @pytest.mark.requirement("8C-FR-023")
    def test_status_table_output_default(self, mock_status_response: MagicMock) -> None:
        """Test status with default table output format."""
        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://test.io/repo",
                ],
            )

        assert result.exit_code == 0
        # Table should show tag, digest, and environment states
        assert "v1.0.0" in result.output
        assert "sha256:" in result.output
        assert "dev" in result.output
        assert "staging" in result.output
        assert "prod" in result.output

    @pytest.mark.requirement("8C-FR-023")
    def test_status_table_shows_promoted_status(
        self, mock_status_response: MagicMock
    ) -> None:
        """Test table output shows promoted/not promoted status."""
        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://test.io/repo",
                    "--format=table",
                ],
            )

        assert result.exit_code == 0
        # Should indicate promoted environments
        output_lower = result.output.lower()
        # Dev and staging are promoted, prod is not
        assert (
            "promoted" in output_lower or "✓" in result.output or "yes" in output_lower
        )

    @pytest.mark.requirement("8C-FR-023")
    def test_status_table_shows_latest_marker(
        self, mock_status_response: MagicMock
    ) -> None:
        """Test table output shows latest marker for current environment."""
        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://test.io/repo",
                    "--format=table",
                ],
            )

        assert result.exit_code == 0
        # Staging is marked as latest
        output_lower = result.output.lower()
        assert "latest" in output_lower or "*" in result.output


class TestStatusCliJsonOutput:
    """Tests for status CLI JSON output format."""

    @pytest.mark.requirement("8C-FR-023")
    def test_status_json_output(self, mock_status_response: MagicMock) -> None:
        """Test status with JSON output format."""
        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://test.io/repo",
                    "--format=json",
                ],
            )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)
        assert data["tag"] == "v1.0.0"
        assert "digest" in data
        assert "environments" in data
        assert "dev" in data["environments"]
        assert "staging" in data["environments"]
        assert "prod" in data["environments"]

    @pytest.mark.requirement("8C-FR-023")
    def test_status_json_includes_environment_details(
        self, mock_status_response: MagicMock
    ) -> None:
        """Test JSON output includes environment promotion details."""
        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://test.io/repo",
                    "--format=json",
                ],
            )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)

        # Check dev environment details
        dev = data["environments"]["dev"]
        assert dev["promoted"] is True
        assert "promoted_at" in dev
        assert dev["operator"] == "ci@example.com"

        # Check prod environment (not promoted)
        prod = data["environments"]["prod"]
        assert prod["promoted"] is False

    @pytest.mark.requirement("8C-FR-027")
    def test_status_json_includes_history(
        self, mock_status_response: MagicMock
    ) -> None:
        """Test JSON output includes promotion history."""
        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://test.io/repo",
                    "--format=json",
                ],
            )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)

        assert "history" in data
        assert len(data["history"]) == 2

        # Check history entry has FR-027 required fields
        entry = data["history"][0]
        assert "promotion_id" in entry
        assert "artifact_digest" in entry
        assert "source_environment" in entry
        assert "target_environment" in entry
        assert "operator" in entry
        assert "promoted_at" in entry


class TestStatusCliYamlOutput:
    """Tests for status CLI YAML output format."""

    @pytest.mark.requirement("8C-FR-023")
    def test_status_yaml_output(self, mock_status_response: MagicMock) -> None:
        """Test status with YAML output format."""
        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://test.io/repo",
                    "--format=yaml",
                ],
            )

        assert result.exit_code == 0
        # YAML should have key-value format
        assert "tag:" in result.output
        assert "v1.0.0" in result.output
        assert "digest:" in result.output
        assert "environments:" in result.output

    @pytest.mark.requirement("8C-FR-023")
    def test_status_yaml_is_valid(self, mock_status_response: MagicMock) -> None:
        """Test YAML output is parseable."""
        import yaml

        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = mock_status_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--registry=oci://test.io/repo",
                    "--format=yaml",
                ],
            )

        assert result.exit_code == 0

        # Remove any non-YAML prefix (log lines)
        yaml_start = result.output.find("tag:")
        if yaml_start == -1:
            yaml_start = 0
        yaml_content = result.output[yaml_start:]

        data = yaml.safe_load(yaml_content)
        assert data["tag"] == "v1.0.0"
        assert "environments" in data


class TestStatusCliEnvFilter:
    """Tests for status CLI --env filter option."""

    @pytest.mark.requirement("8C-FR-023")
    def test_status_with_env_filter(self, mock_status_response: MagicMock) -> None:
        """Test --env filter returns single environment status."""
        from floe_core.schemas.promotion import (
            EnvironmentStatus,
            PromotionStatusResponse,
        )

        # Create filtered response with single environment
        filtered_response = PromotionStatusResponse(
            tag="v1.0.0",
            digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            environments={
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

        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = filtered_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--env=prod",
                    "--registry=oci://test.io/repo",
                    "--format=json",
                ],
            )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)
        assert len(data["environments"]) == 1
        assert "prod" in data["environments"]

        # Verify get_status was called with env parameter
        mock_controller.get_status.assert_called_once()
        call_kwargs = mock_controller.get_status.call_args[1]
        assert call_kwargs.get("env") == "prod"


class TestStatusCliHistoryLimit:
    """Tests for status CLI --history=N option."""

    @pytest.mark.requirement("8C-FR-027")
    def test_status_with_history_limit(self, mock_status_response: MagicMock) -> None:
        """Test --history=N limits history entries."""
        from floe_core.schemas.promotion import (
            EnvironmentStatus,
            PromotionHistoryEntry,
            PromotionStatusResponse,
        )

        # Create response with limited history
        limited_response = PromotionStatusResponse(
            tag="v1.0.0",
            digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            environments={
                "dev": EnvironmentStatus(promoted=True),
            },
            history=[
                PromotionHistoryEntry(
                    promotion_id=str(uuid4()),
                    artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                    source_environment="build",
                    target_environment="dev",
                    operator="ci@example.com",
                    promoted_at=datetime.now(timezone.utc),
                ),
            ],
            queried_at=datetime.now(timezone.utc),
        )

        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.return_value = limited_response
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v1.0.0",
                    "--history=1",
                    "--registry=oci://test.io/repo",
                    "--format=json",
                ],
            )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)
        assert len(data["history"]) == 1

        # Verify get_status was called with history parameter
        mock_controller.get_status.assert_called_once()
        call_kwargs = mock_controller.get_status.call_args[1]
        assert call_kwargs.get("history") == 1


class TestStatusCliErrors:
    """Tests for status CLI error handling."""

    @pytest.mark.requirement("8C-FR-023")
    def test_artifact_not_found_error(self) -> None:
        """Test error handling for ArtifactNotFoundError."""
        from floe_core.oci.errors import ArtifactNotFoundError

        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.side_effect = ArtifactNotFoundError(
                tag="v999.0.0",
                registry="oci://test.io/repo",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v999.0.0",
                    "--registry=oci://test.io/repo",
                ],
            )

        # Should return non-zero exit code
        assert result.exit_code != 0
        assert "v999.0.0" in result.output or "not found" in result.output.lower()

    @pytest.mark.requirement("8C-FR-023")
    def test_artifact_not_found_json_output(self) -> None:
        """Test ArtifactNotFoundError with JSON output."""
        from floe_core.oci.errors import ArtifactNotFoundError

        runner = CliRunner()
        with (
            patch("floe_core.oci.client.OCIClient") as mock_client_cls,
            patch("floe_core.oci.promotion.PromotionController") as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.get_status.side_effect = ArtifactNotFoundError(
                tag="v999.0.0",
                registry="oci://test.io/repo",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "status",
                    "v999.0.0",
                    "--registry=oci://test.io/repo",
                    "--format=json",
                ],
            )

        assert result.exit_code != 0
        data = extract_json_from_output(result.output)
        assert "error" in data
        assert "tag" in data
        assert data["tag"] == "v999.0.0"

    @pytest.mark.requirement("8C-FR-023")
    def test_missing_registry_error(self) -> None:
        """Test error when --registry is not provided."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "platform",
                "status",
                "v1.0.0",
            ],
        )

        # Should fail due to missing registry
        assert result.exit_code != 0


class TestStatusCliOutputFormat:
    """Tests for status CLI --format option."""

    @pytest.mark.requirement("8C-FR-023")
    def test_format_option_choices(self) -> None:
        """Test --format accepts table, json, yaml choices."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "status", "--help"])

        assert result.exit_code == 0
        # Help should show format options
        assert "format" in result.output.lower()

    @pytest.mark.requirement("8C-FR-023")
    def test_invalid_format_rejected(self, mock_status_response: MagicMock) -> None:
        """Test invalid --format value is rejected."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "platform",
                "status",
                "v1.0.0",
                "--registry=oci://test.io/repo",
                "--format=invalid",
            ],
        )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "choice" in result.output.lower()
