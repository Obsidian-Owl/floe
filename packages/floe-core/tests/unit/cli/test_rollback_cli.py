"""Unit tests for rollback CLI command (T053).

Tests for the `floe platform rollback` command:
- Table output format
- JSON output format
- Impact analysis mode
- Error handling for various error types
- Exit code verification

Task ID: T053
Phase: 3 - User Story 3 (Rollback)
Requirements: FR-013, FR-014, FR-015, FR-016, FR-017

See Also:
    - specs/8c-promotion-lifecycle/spec.md: Feature specification
    - User Story 3: Rollback to Previous Version
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli
from floe_core.schemas.promotion import RollbackImpactAnalysis, RollbackRecord


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
def mock_rollback_record() -> RollbackRecord:
    """Create a mock RollbackRecord for testing output formatting."""
    return RollbackRecord(
        rollback_id=uuid4(),
        artifact_digest="sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        environment="prod",
        previous_digest="sha256:f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2",
        reason="Performance regression in v2.0.0",
        operator="sre@example.com",
        rolled_back_at=datetime.now(timezone.utc),
        trace_id="abc123def456",
    )


@pytest.fixture
def mock_impact_analysis() -> RollbackImpactAnalysis:
    """Create a mock RollbackImpactAnalysis for testing."""
    return RollbackImpactAnalysis(
        breaking_changes=["API endpoint /users removed", "Field 'status' type changed"],
        affected_products=["dashboard", "mobile-app"],
        recommendations=["Notify API consumers", "Update mobile app config"],
        estimated_downtime="~5 minutes",
    )


class TestRollbackCliBasic:
    """Basic tests for rollback CLI command structure."""

    def test_rollback_command_exists(self) -> None:
        """Test that rollback command is registered under platform."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "rollback", "--help"])
        assert result.exit_code == 0
        assert "Rollback an environment" in result.output

    def test_rollback_requires_env(self) -> None:
        """Test that --env option is required."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["platform", "rollback", "v1.0.0", "--reason=test"],
        )
        # Should fail due to missing --env
        assert result.exit_code != 0
        assert "Missing option" in result.output or "env" in result.output.lower()

    def test_rollback_requires_reason_without_analyze(self) -> None:
        """Test that --reason is required unless --analyze is used."""
        runner = CliRunner()
        with patch(
            "floe_core.oci.client.OCIClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--registry=oci://test.io/repo",
                ],
            )

        # Should fail due to missing --reason
        assert result.exit_code == 2
        assert "reason" in result.output.lower()


class TestRollbackCliSuccess:
    """Tests for successful rollback CLI operations."""

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_table_output(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """Test rollback with table output format."""
        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.rollback.return_value = mock_rollback_record
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Performance regression",
                    "--registry=oci://test.io/repo",
                    "--output=table",
                ],
            )

        assert result.exit_code == 0
        assert "Rollback ID" in result.output
        assert "Environment" in result.output
        assert "prod" in result.output
        assert "Successfully rolled back" in result.output

    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_json_output(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """Test rollback with JSON output format."""
        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.rollback.return_value = mock_rollback_record
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Bug in production",
                    "--registry=oci://test.io/repo",
                    "--output=json",
                ],
            )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)
        assert "rollback_id" in data
        assert data["environment"] == "prod"
        assert data["reason"] == "Performance regression in v2.0.0"


class TestRollbackCliAnalyze:
    """Tests for rollback impact analysis mode."""

    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_mode_table_output(
        self, mock_impact_analysis: RollbackImpactAnalysis
    ) -> None:
        """Test --analyze flag shows impact analysis."""
        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.analyze_rollback_impact.return_value = mock_impact_analysis
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--analyze",
                    "--registry=oci://test.io/repo",
                ],
            )

        assert result.exit_code == 0
        assert "Impact Analysis" in result.output
        assert "Breaking Changes" in result.output
        assert "API endpoint /users removed" in result.output
        assert "Affected Products" in result.output
        assert "dashboard" in result.output
        assert "Recommendations" in result.output

    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_mode_json_output(
        self, mock_impact_analysis: RollbackImpactAnalysis
    ) -> None:
        """Test --analyze flag with JSON output."""
        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.analyze_rollback_impact.return_value = mock_impact_analysis
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--analyze",
                    "--registry=oci://test.io/repo",
                    "--output=json",
                ],
            )

        assert result.exit_code == 0
        data = extract_json_from_output(result.output)
        assert "breaking_changes" in data
        assert len(data["breaking_changes"]) == 2
        assert "affected_products" in data
        assert "recommendations" in data

    @pytest.mark.requirement("8C-FR-016")
    def test_analyze_mode_no_reason_required(
        self, mock_impact_analysis: RollbackImpactAnalysis
    ) -> None:
        """Test --analyze flag does not require --reason."""
        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.analyze_rollback_impact.return_value = mock_impact_analysis
            mock_controller_cls.return_value = mock_controller

            # Note: no --reason provided
            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--analyze",
                    "--registry=oci://test.io/repo",
                ],
            )

        assert result.exit_code == 0


class TestRollbackCliErrors:
    """Tests for rollback CLI error handling."""

    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error(self) -> None:
        """Test error handling for VersionNotPromotedError."""
        from floe_core.oci.errors import VersionNotPromotedError

        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.rollback.side_effect = VersionNotPromotedError(
                tag="v1.0.0",
                environment="prod",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Test",
                    "--registry=oci://test.io/repo",
                ],
            )

        assert result.exit_code == 11
        assert "v1.0.0" in result.output
        assert "prod" in result.output

    @pytest.mark.requirement("8C-FR-013")
    def test_version_not_promoted_error_json(self) -> None:
        """Test VersionNotPromotedError with JSON output."""
        from floe_core.oci.errors import VersionNotPromotedError

        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.rollback.side_effect = VersionNotPromotedError(
                tag="v2.0.0",
                environment="prod",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v2.0.0",
                    "--env=prod",
                    "--reason=Test",
                    "--registry=oci://test.io/repo",
                    "--output=json",
                ],
            )

        assert result.exit_code == 11
        data = extract_json_from_output(result.output)
        assert data["exit_code"] == 11
        assert data["tag"] == "v2.0.0"
        assert data["environment"] == "prod"

    @pytest.mark.requirement("8C-FR-013")
    def test_authorization_error(self) -> None:
        """Test error handling for AuthorizationError."""
        from floe_core.oci.errors import AuthorizationError

        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.rollback.side_effect = AuthorizationError(
                operator="user@example.com",
                required_groups=["prod-release"],
                reason="Not in prod-release group",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Test",
                    "--registry=oci://test.io/repo",
                ],
            )

        assert result.exit_code == 12
        assert "Authorization" in result.output or "authorization" in result.output

    @pytest.mark.requirement("8C-FR-013")
    def test_environment_locked_error(self) -> None:
        """Test error handling for EnvironmentLockedError."""
        from floe_core.oci.errors import EnvironmentLockedError

        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.rollback.side_effect = EnvironmentLockedError(
                environment="prod",
                locked_by="admin@example.com",
                locked_at="2026-01-30T10:00:00Z",
                reason="Release freeze",
            )
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Test",
                    "--registry=oci://test.io/repo",
                ],
            )

        assert result.exit_code == 13
        assert "locked" in result.output.lower()

    def test_missing_registry_error(self) -> None:
        """Test error when --registry is not provided."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "platform",
                "rollback",
                "v1.0.0",
                "--env=prod",
                "--reason=Test",
            ],
        )

        assert result.exit_code == 2
        assert "registry" in result.output.lower()


class TestRollbackCliOperator:
    """Tests for operator identity handling."""

    @pytest.mark.requirement("8C-FR-017")
    def test_operator_from_option(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """Test --operator option sets operator identity."""
        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.rollback.return_value = mock_rollback_record
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Test",
                    "--registry=oci://test.io/repo",
                    "--operator=custom@example.com",
                ],
            )

        assert result.exit_code == 0
        # Verify operator was passed to controller
        mock_controller.rollback.assert_called_once()
        call_kwargs = mock_controller.rollback.call_args[1]
        assert call_kwargs["operator"] == "custom@example.com"

    @pytest.mark.requirement("8C-FR-017")
    def test_operator_defaults_to_user(
        self, mock_rollback_record: RollbackRecord
    ) -> None:
        """Test operator defaults to $USER when not specified."""
        runner = CliRunner()
        with (
            patch(
                "floe_core.oci.client.OCIClient"
            ) as mock_client_cls,
            patch(
                "floe_core.oci.promotion.PromotionController"
            ) as mock_controller_cls,
            patch.dict("os.environ", {"USER": "testuser"}),
        ):
            mock_client = MagicMock()
            mock_client_cls.from_registry_config.return_value = mock_client

            mock_controller = MagicMock()
            mock_controller.rollback.return_value = mock_rollback_record
            mock_controller_cls.return_value = mock_controller

            result = runner.invoke(
                cli,
                [
                    "platform",
                    "rollback",
                    "v1.0.0",
                    "--env=prod",
                    "--reason=Test",
                    "--registry=oci://test.io/repo",
                ],
            )

        assert result.exit_code == 0
        mock_controller.rollback.assert_called_once()
        call_kwargs = mock_controller.rollback.call_args[1]
        assert call_kwargs["operator"] == "testuser"
