"""Unit tests for the rbac validate command.

Task ID: T028
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-022, FR-023

Tests cover:
- Command accepts --config option (FR-022)
- Command accepts --manifest-dir option (FR-022)
- Command accepts --output option with text/json choices (FR-022)
- Command returns validation status with issue details (FR-023)
- Exit code handling
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestRbacValidateCommand:
    """Tests for the rbac validate CLI command."""

    @pytest.mark.requirement("FR-022")
    def test_validate_accepts_config_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command accepts --config option.

        Validates that the --config option is recognized.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
            ],
        )

        assert "Error: No such option: --config" not in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_accepts_manifest_dir_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command accepts --manifest-dir option.

        Validates that the --manifest-dir option is recognized.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
            ],
        )

        assert "Error: No such option: --manifest-dir" not in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_accepts_output_option_text(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command accepts --output text option.

        Validates that --output accepts 'text' format choice.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
                "--output",
                "text",
            ],
        )

        assert "Error: Invalid value for '--output'" not in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_accepts_output_option_json(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command accepts --output json option.

        Validates that --output accepts 'json' format choice.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
                "--output",
                "json",
            ],
        )

        assert "Error: Invalid value for '--output'" not in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_rejects_invalid_output_format(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command rejects invalid --output values.

        Validates that invalid output format choices are rejected.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
                "--output",
                "invalid_format",
            ],
        )

        assert result.exit_code != 0
        assert "Invalid value" in (result.output or "") or "invalid_format" in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_shows_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that validate command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "validate", "--help"],
        )

        assert result.exit_code == 0
        assert "validate" in result.output.lower()

    @pytest.mark.requirement("FR-023")
    def test_validate_fails_manifest_dir_not_found(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate fails when manifest-dir doesn't exist.

        Validates error handling for missing manifest directory.
        """
        from floe_core.cli.main import cli

        nonexistent_dir = temp_dir / "nonexistent_rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(nonexistent_dir),
            ],
        )

        assert result.exit_code != 0


class TestRbacValidateInGroup:
    """Tests for validate subcommand in rbac group."""

    @pytest.mark.requirement("FR-023")
    def test_rbac_shows_validate_subcommand(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that rbac group shows validate subcommand.

        Validates that validate is listed in rbac help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        assert "validate" in result.output.lower()


__all__: list[str] = ["TestRbacValidateCommand", "TestRbacValidateInGroup"]
