"""Unit tests for artifact pull CLI command.

Task ID: T059
Phase: 6 - User Story 4 (Verification Policy Configuration)
User Story: US4 - Verification Policy Configuration
Requirements: FR-009, FR-043

These tests verify the artifact pull command:
- Parses --registry, --tag, and --environment options correctly
- Supports FLOE_ENVIRONMENT env var
- Handles verification policy configuration
- Provides meaningful error messages
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli


class TestArtifactPullHelp:
    """Tests for artifact pull help output.

    Task: T059
    Requirement: FR-043
    """

    @pytest.mark.requirement("FR-043")
    def test_pull_appears_in_artifact_help(self) -> None:
        """Test that pull command is listed in artifact group."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "--help"])

        assert result.exit_code == 0
        assert "pull" in result.output

    @pytest.mark.requirement("FR-043")
    def test_pull_help_shows_options(self) -> None:
        """Test that pull help shows required options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "pull", "--help"])

        assert result.exit_code == 0
        assert "--registry" in result.output or "-r" in result.output
        assert "--tag" in result.output or "-t" in result.output
        assert "--environment" in result.output or "-e" in result.output

    @pytest.mark.requirement("FR-043")
    def test_pull_help_shows_environment_description(self) -> None:
        """Test that pull help explains --environment flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "pull", "--help"])

        assert result.exit_code == 0
        assert "environment" in result.output.lower()
        assert (
            "verification" in result.output.lower() or "policy" in result.output.lower()
        )


class TestArtifactPullValidation:
    """Tests for artifact pull input validation.

    Task: T059
    Requirement: FR-043
    """

    @pytest.mark.requirement("FR-043")
    def test_pull_requires_registry_option(self) -> None:
        """Test that pull fails without --registry."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "pull", "--tag", "v1.0.0"])

        assert result.exit_code != 0

    @pytest.mark.requirement("FR-043")
    def test_pull_requires_tag_option(self) -> None:
        """Test that pull fails without --tag."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["artifact", "pull", "--registry", "oci://example.com/repo"]
        )

        assert result.exit_code != 0


class TestArtifactPullEnvironmentFlag:
    """Tests for --environment flag.

    Task: T059
    Requirement: FR-009
    """

    @pytest.mark.requirement("FR-009")
    @patch("floe_core.oci.OCIClient")
    def test_pull_passes_environment_to_client(
        self, mock_client_class: MagicMock
    ) -> None:
        """Test that --environment flag is passed to OCIClient.pull()."""
        mock_client = MagicMock()
        mock_client.pull.return_value = MagicMock(
            model_dump_json=MagicMock(return_value="{}")
        )
        mock_client_class.from_registry_config.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "pull",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
                "--environment",
                "production",
            ],
        )

        assert result.exit_code == 0
        mock_client.pull.assert_called_once_with(tag="v1.0.0", environment="production")

    @pytest.mark.requirement("FR-009")
    @patch("floe_core.oci.OCIClient")
    def test_pull_environment_from_env_var(self, mock_client_class: MagicMock) -> None:
        """Test that FLOE_ENVIRONMENT env var is used."""
        mock_client = MagicMock()
        mock_client.pull.return_value = MagicMock(
            model_dump_json=MagicMock(return_value="{}")
        )
        mock_client_class.from_registry_config.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "pull",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
            ],
            env={"FLOE_ENVIRONMENT": "staging"},
        )

        assert result.exit_code == 0
        mock_client.pull.assert_called_once_with(tag="v1.0.0", environment="staging")

    @pytest.mark.requirement("FR-009")
    @patch("floe_core.oci.OCIClient")
    def test_pull_flag_overrides_env_var(self, mock_client_class: MagicMock) -> None:
        """Test that --environment flag takes precedence over env var."""
        mock_client = MagicMock()
        mock_client.pull.return_value = MagicMock(
            model_dump_json=MagicMock(return_value="{}")
        )
        mock_client_class.from_registry_config.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "pull",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
                "--environment",
                "production",
            ],
            env={"FLOE_ENVIRONMENT": "staging"},
        )

        assert result.exit_code == 0
        mock_client.pull.assert_called_once_with(tag="v1.0.0", environment="production")

    @pytest.mark.requirement("FR-009")
    @patch("floe_core.oci.OCIClient")
    def test_pull_without_environment(self, mock_client_class: MagicMock) -> None:
        """Test that pull works without environment (None)."""
        mock_client = MagicMock()
        mock_client.pull.return_value = MagicMock(
            model_dump_json=MagicMock(return_value="{}")
        )
        mock_client_class.from_registry_config.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "pull",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
            ],
        )

        assert result.exit_code == 0
        mock_client.pull.assert_called_once_with(tag="v1.0.0", environment=None)


class TestArtifactPullOutput:
    """Tests for artifact pull output handling.

    Task: T059
    Requirement: FR-043
    """

    @pytest.mark.requirement("FR-043")
    @patch("floe_core.oci.OCIClient")
    def test_pull_outputs_to_stdout_by_default(
        self, mock_client_class: MagicMock
    ) -> None:
        """Test that pull outputs JSON to stdout without --output."""
        mock_artifacts = MagicMock()
        mock_artifacts.model_dump_json.return_value = '{"test": "artifact"}'
        mock_client = MagicMock()
        mock_client.pull.return_value = mock_artifacts
        mock_client_class.from_registry_config.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "artifact",
                "pull",
                "--registry",
                "oci://example.com/repo",
                "--tag",
                "v1.0.0",
            ],
        )

        assert result.exit_code == 0
        assert '{"test": "artifact"}' in result.output

    @pytest.mark.requirement("FR-043")
    @patch("floe_core.oci.OCIClient")
    def test_pull_outputs_to_file_with_option(
        self, mock_client_class: MagicMock
    ) -> None:
        """Test that pull writes to file with --output."""
        mock_artifacts = MagicMock()
        mock_artifacts.model_dump_json.return_value = '{"test": "artifact"}'
        mock_client = MagicMock()
        mock_client.pull.return_value = mock_artifacts
        mock_client_class.from_registry_config.return_value = mock_client

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                [
                    "artifact",
                    "pull",
                    "--registry",
                    "oci://example.com/repo",
                    "--tag",
                    "v1.0.0",
                    "--output",
                    "pulled.json",
                ],
            )

            assert result.exit_code == 0
            assert Path("pulled.json").exists()
            content = Path("pulled.json").read_text()
            assert '{"test": "artifact"}' in content
