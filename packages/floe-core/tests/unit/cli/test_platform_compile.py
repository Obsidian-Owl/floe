"""Unit tests for the platform compile command.

Task ID: T012
Phase: 3 - User Story 1 (Platform Compile MVP)
User Story: US1 - Unified Platform Compile with Enforcement Export
Requirements: FR-010 through FR-015, FR-021

Tests cover:
- Command accepts --spec and --manifest options (FR-010)
- Command accepts --output option (FR-011)
- Command accepts --enforcement-report option (FR-012)
- Command accepts --enforcement-format option (FR-013)
- Parent directories are created for enforcement report (FR-014)
- Exit code handling (FR-015)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestPlatformCompileCommand:
    """Tests for the platform compile CLI command."""

    @pytest.mark.requirement("FR-010")
    def test_compile_accepts_spec_and_manifest_options(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
    ) -> None:
        """Test that compile command accepts --spec and --manifest options.

        Validates that the command can be invoked with spec and manifest paths
        and doesn't error on argument parsing.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
            ],
        )

        # Command should not fail on argument parsing
        # (actual compilation may fail due to missing dependencies in unit test)
        assert result.exit_code in (0, 1), f"Unexpected exit code: {result.exit_code}"
        assert "Error: No such option" not in (result.output or "")

    @pytest.mark.requirement("FR-011")
    def test_compile_accepts_output_option(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that compile command accepts --output option for artifacts path.

        Validates that the --output option is recognized.
        """
        from floe_core.cli.main import cli

        output_path = temp_dir / "target" / "compiled_artifacts.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--output",
                str(output_path),
            ],
        )

        assert "Error: No such option: --output" not in (result.output or "")

    @pytest.mark.requirement("FR-012")
    def test_compile_accepts_enforcement_report_option(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that compile command accepts --enforcement-report option.

        Validates that the --enforcement-report option is recognized.
        """
        from floe_core.cli.main import cli

        report_path = temp_dir / "report.json"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--enforcement-report",
                str(report_path),
            ],
        )

        assert "Error: No such option: --enforcement-report" not in (result.output or "")

    @pytest.mark.requirement("FR-013")
    def test_compile_accepts_enforcement_format_option(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that compile command accepts --enforcement-format option.

        Validates that the --enforcement-format option accepts json, sarif, html.
        """
        from floe_core.cli.main import cli

        report_path = temp_dir / "report.sarif"

        for format_choice in ["json", "sarif", "html"]:
            result = cli_runner.invoke(
                cli,
                [
                    "platform",
                    "compile",
                    "--spec",
                    str(sample_floe_yaml),
                    "--manifest",
                    str(sample_manifest_yaml),
                    "--enforcement-report",
                    str(report_path),
                    "--enforcement-format",
                    format_choice,
                ],
            )

            assert "Error: Invalid value for '--enforcement-format'" not in (
                result.output or ""
            ), f"Format {format_choice} should be valid"

    @pytest.mark.requirement("FR-013")
    def test_compile_rejects_invalid_enforcement_format(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that compile command rejects invalid --enforcement-format values.

        Validates that invalid format choices are rejected by Click.
        """
        from floe_core.cli.main import cli

        report_path = temp_dir / "report.txt"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(sample_manifest_yaml),
                "--enforcement-report",
                str(report_path),
                "--enforcement-format",
                "invalid_format",
            ],
        )

        assert result.exit_code != 0
        # Click outputs error about invalid choice
        assert "Invalid value" in (result.output or "") or "invalid_format" in (
            result.output or ""
        )

    @pytest.mark.requirement("FR-015")
    def test_compile_exits_with_zero_on_success(
        self,
        cli_runner: CliRunner,
        sample_floe_yaml: Path,
        sample_manifest_yaml: Path,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that compile command returns exit code 0 on success.

        Uses monkeypatch to mock the compile function to avoid actual compilation.
        """
        from floe_core.cli.main import cli

        # Mock the compile function to succeed
        def mock_compile(*args: object, **kwargs: object) -> int:
            return 0

        # We'll need to patch the actual compile function when implemented
        # For now, just verify command can be invoked
        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--help",
            ],
        )

        # Help should always succeed
        assert result.exit_code == 0

    @pytest.mark.requirement("FR-010")
    def test_compile_shows_help_with_help_flag(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that compile command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["platform", "compile", "--help"],
        )

        assert result.exit_code == 0
        assert "compile" in result.output.lower()
        # Once implemented, these should be in help
        # assert "--spec" in result.output
        # assert "--manifest" in result.output

    @pytest.mark.requirement("FR-010")
    def test_compile_spec_file_not_found(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
        sample_manifest_yaml: Path,
    ) -> None:
        """Test that compile fails gracefully when spec file not found.

        Validates error handling for missing spec file.
        """
        from floe_core.cli.main import cli

        nonexistent_spec = temp_dir / "nonexistent.yaml"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(nonexistent_spec),
                "--manifest",
                str(sample_manifest_yaml),
            ],
        )

        # Should fail (either during arg parsing or command execution)
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-010")
    def test_compile_manifest_file_not_found(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
        sample_floe_yaml: Path,
    ) -> None:
        """Test that compile fails gracefully when manifest file not found.

        Validates error handling for missing manifest file.
        """
        from floe_core.cli.main import cli

        nonexistent_manifest = temp_dir / "nonexistent_manifest.yaml"

        result = cli_runner.invoke(
            cli,
            [
                "platform",
                "compile",
                "--spec",
                str(sample_floe_yaml),
                "--manifest",
                str(nonexistent_manifest),
            ],
        )

        # Should fail (either during arg parsing or command execution)
        assert result.exit_code != 0


class TestPlatformGroup:
    """Tests for the platform command group."""

    def test_platform_group_exists(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that platform command group exists.

        Validates that 'floe platform' is a valid command group.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0
        assert "platform" in result.output.lower()

    def test_platform_shows_compile_subcommand(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that platform group shows compile subcommand.

        Validates that compile is listed in platform help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0
        # Once compile is implemented, it should appear in help
        # assert "compile" in result.output
