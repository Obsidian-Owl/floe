"""Unit tests for CLI entry point verification.

Task ID: T062
Phase: 8 - Deprecation
Requirements: FR-050, FR-051

These tests verify that the unified floe CLI entry point works correctly
and that there is only one entry point for the CLI.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli, main


class TestEntryPoint:
    """Tests for the floe CLI entry point.

    Task: T062
    Requirement: FR-050, FR-051
    """

    @pytest.mark.requirement("FR-050")
    def test_cli_function_exists(self) -> None:
        """Test that the CLI function exists and is callable."""
        assert callable(cli)

    @pytest.mark.requirement("FR-050")
    def test_main_function_exists(self) -> None:
        """Test that the main function exists and is callable."""
        assert callable(main)

    @pytest.mark.requirement("FR-050")
    def test_cli_responds_to_help(self) -> None:
        """Test that CLI responds to --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "floe" in result.output

    @pytest.mark.requirement("FR-050")
    def test_cli_responds_to_version(self) -> None:
        """Test that CLI responds to --version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        # Should show version number
        assert "floe" in result.output.lower()

    @pytest.mark.requirement("FR-051")
    def test_cli_has_all_command_groups(self) -> None:
        """Test that CLI has all expected command groups."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        # All command groups should be present
        assert "platform" in result.output
        assert "rbac" in result.output
        assert "artifact" in result.output
        # Data team stubs at root level
        assert "compile" in result.output
        assert "validate" in result.output
        assert "run" in result.output
        assert "test" in result.output


class TestEntryPointModule:
    """Tests for entry point module import.

    Task: T062
    Requirement: FR-050
    """

    @pytest.mark.requirement("FR-050")
    def test_cli_module_importable(self) -> None:
        """Test that CLI module can be imported."""
        from floe_core.cli import main as cli_main

        assert cli_main is not None

    @pytest.mark.requirement("FR-050")
    def test_entry_point_function_importable(self) -> None:
        """Test that entry point function can be imported directly."""
        from floe_core.cli.main import cli, main

        assert cli is not None
        assert main is not None


__all__: list[str] = [
    "TestEntryPoint",
    "TestEntryPointModule",
]
