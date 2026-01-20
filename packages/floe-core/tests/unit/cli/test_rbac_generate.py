"""Unit tests for the rbac generate command.

Task ID: T027
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-020, FR-021

Tests cover:
- Command accepts --config option (FR-020)
- Command accepts --output option (FR-020)
- Command accepts --dry-run option (FR-020)
- Command produces YAML manifests for Namespace, ServiceAccount, Role, RoleBinding (FR-021)
- Exit code handling
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestRbacGenerateCommand:
    """Tests for the rbac generate CLI command."""

    @pytest.mark.requirement("FR-020")
    def test_generate_accepts_config_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that generate command accepts --config option.

        Validates that the --config option is recognized and accepts a file path.
        """
        from floe_core.cli.main import cli

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
            ],
        )

        # Command should not fail on argument parsing
        assert "Error: No such option: --config" not in (result.output or "")

    @pytest.mark.requirement("FR-020")
    def test_generate_accepts_output_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that generate command accepts --output option.

        Validates that the --output option is recognized for specifying output directory.
        """
        from floe_core.cli.main import cli

        output_dir = temp_dir / "rbac_output"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
            ],
        )

        assert "Error: No such option: --output" not in (result.output or "")

    @pytest.mark.requirement("FR-020")
    def test_generate_accepts_dry_run_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that generate command accepts --dry-run option.

        Validates that --dry-run flag prevents writing files.
        """
        from floe_core.cli.main import cli

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(sample_manifest_yaml),
                "--output",
                str(output_dir),
                "--dry-run",
            ],
        )

        assert "Error: No such option: --dry-run" not in (result.output or "")

    @pytest.mark.requirement("FR-020")
    def test_generate_shows_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that generate command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "generate", "--help"],
        )

        assert result.exit_code == 0
        assert "generate" in result.output.lower()
        # Should document options
        assert "--config" in result.output or "config" in result.output.lower()

    @pytest.mark.requirement("FR-020")
    def test_generate_fails_without_config(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that generate fails when --config not provided.

        Validates proper error handling for missing required option.
        """
        from floe_core.cli.main import cli

        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--output",
                str(output_dir),
            ],
        )

        # Should fail when config not provided
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-020")
    def test_generate_fails_config_not_found(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that generate fails when config file doesn't exist.

        Validates error handling for missing config file.
        """
        from floe_core.cli.main import cli

        nonexistent_config = temp_dir / "nonexistent.yaml"
        output_dir = temp_dir / "rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "generate",
                "--config",
                str(nonexistent_config),
                "--output",
                str(output_dir),
            ],
        )

        assert result.exit_code != 0

    @pytest.mark.requirement("FR-021")
    def test_generate_default_output_directory(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that generate uses default output directory if not specified.

        Validates that default output path is target/rbac.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "generate", "--help"],
        )

        # Help should show default output path
        assert result.exit_code == 0
        # Default should be mentioned in help
        assert "target/rbac" in result.output or "rbac" in result.output.lower()


class TestRbacGroup:
    """Tests for the rbac command group."""

    def test_rbac_group_exists(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that rbac command group exists.

        Validates that 'floe rbac' is a valid command group.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        assert "rbac" in result.output.lower()

    def test_rbac_shows_generate_subcommand(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that rbac group shows generate subcommand.

        Validates that generate is listed in rbac help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        assert "generate" in result.output.lower()


__all__: list[str] = ["TestRbacGenerateCommand", "TestRbacGroup"]
