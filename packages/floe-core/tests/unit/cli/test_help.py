"""Unit tests for CLI help output completeness.

Task ID: T040
Phase: 5 - User Story 3 (Help Discovery)
User Story: US3 - Discoverable Command Help
Requirements: FR-051, FR-052

These tests verify that all CLI commands have complete, discoverable help text.
"""

from __future__ import annotations

import time

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli


class TestRootHelp:
    """Tests for root command help output.

    Task: T040
    Requirement: FR-051
    """

    @pytest.mark.requirement("FR-051")
    def test_root_help_shows_version_option(self) -> None:
        """Test that root help displays version option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "--version" in result.output

    @pytest.mark.requirement("FR-051")
    def test_root_help_shows_all_command_groups(self) -> None:
        """Test that root help lists all command groups."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        # All command groups must be listed
        assert "platform" in result.output
        assert "rbac" in result.output
        assert "artifact" in result.output

    @pytest.mark.requirement("FR-051")
    def test_root_help_shows_description(self) -> None:
        """Test that root help shows a description of floe."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        # Should have meaningful description
        assert "platform" in result.output.lower() or "data" in result.output.lower()

    @pytest.mark.requirement("FR-051")
    def test_root_help_shows_usage(self) -> None:
        """Test that root help shows usage pattern."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    @pytest.mark.requirement("FR-051")
    def test_root_help_shows_epilog(self) -> None:
        """Test that root help shows epilog with additional guidance."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        # Epilog should guide users to get more help
        assert "--help" in result.output


class TestPlatformGroupHelp:
    """Tests for platform command group help.

    Task: T040
    Requirement: FR-051
    """

    @pytest.mark.requirement("FR-051")
    def test_platform_help_shows_all_subcommands(self) -> None:
        """Test that platform group lists all subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0
        # All platform subcommands must be listed
        assert "compile" in result.output
        assert "test" in result.output
        assert "publish" in result.output
        assert "deploy" in result.output
        assert "status" in result.output

    @pytest.mark.requirement("FR-051")
    def test_platform_help_shows_description(self) -> None:
        """Test that platform help shows a description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0
        # Should describe platform team purpose
        assert "platform" in result.output.lower()

    @pytest.mark.requirement("FR-051")
    def test_platform_compile_help_shows_options(self) -> None:
        """Test that platform compile help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "compile", "--help"])

        assert result.exit_code == 0
        # Core options must be documented
        assert "--spec" in result.output or "-s" in result.output
        assert "--manifest" in result.output or "-m" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "--enforcement-report" in result.output
        assert "--enforcement-format" in result.output


class TestRbacGroupHelp:
    """Tests for RBAC command group help.

    Task: T040
    Requirement: FR-051
    """

    @pytest.mark.requirement("FR-051")
    def test_rbac_help_shows_all_subcommands(self) -> None:
        """Test that rbac group lists all subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        # All RBAC subcommands must be listed
        assert "generate" in result.output
        assert "validate" in result.output
        assert "audit" in result.output
        assert "diff" in result.output

    @pytest.mark.requirement("FR-051")
    def test_rbac_help_shows_description(self) -> None:
        """Test that rbac help shows a description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        # Should describe RBAC purpose
        assert "rbac" in result.output.lower() or "kubernetes" in result.output.lower()

    @pytest.mark.requirement("FR-051")
    def test_rbac_generate_help_shows_options(self) -> None:
        """Test that rbac generate help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "generate", "--help"])

        assert result.exit_code == 0
        assert "--config" in result.output or "-c" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "--dry-run" in result.output

    @pytest.mark.requirement("FR-051")
    def test_rbac_validate_help_shows_options(self) -> None:
        """Test that rbac validate help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "validate", "--help"])

        assert result.exit_code == 0
        assert "--config" in result.output or "-c" in result.output
        assert "--manifest-dir" in result.output or "-m" in result.output
        assert "--output" in result.output or "-o" in result.output

    @pytest.mark.requirement("FR-051")
    def test_rbac_audit_help_shows_options(self) -> None:
        """Test that rbac audit help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "audit", "--help"])

        assert result.exit_code == 0
        assert "--namespace" in result.output or "-n" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "--kubeconfig" in result.output

    @pytest.mark.requirement("FR-051")
    def test_rbac_diff_help_shows_options(self) -> None:
        """Test that rbac diff help shows all options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "diff", "--help"])

        assert result.exit_code == 0
        assert "--manifest-dir" in result.output or "-m" in result.output
        assert "--namespace" in result.output or "-n" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "--kubeconfig" in result.output


class TestArtifactGroupHelp:
    """Tests for artifact command group help.

    Task: T040
    Requirement: FR-051
    """

    @pytest.mark.requirement("FR-051")
    def test_artifact_help_shows_description(self) -> None:
        """Test that artifact help shows a description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["artifact", "--help"])

        assert result.exit_code == 0
        # Should describe artifact/OCI purpose
        assert "artifact" in result.output.lower() or "oci" in result.output.lower()


class TestHelpConsistency:
    """Tests for consistent help formatting across commands.

    Task: T040
    Requirement: FR-052
    """

    @pytest.mark.requirement("FR-052")
    def test_all_commands_support_short_help_flag(self) -> None:
        """Test that all commands support -h for help."""
        runner = CliRunner()

        # Root
        result = runner.invoke(cli, ["-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

        # Groups
        result = runner.invoke(cli, ["platform", "-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

        result = runner.invoke(cli, ["rbac", "-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

        result = runner.invoke(cli, ["artifact", "-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    @pytest.mark.requirement("FR-052")
    def test_help_includes_command_name_in_usage(self) -> None:
        """Test that help output includes proper command names in Usage."""
        runner = CliRunner()

        result = runner.invoke(cli, ["--help"])
        assert "floe" in result.output

        result = runner.invoke(cli, ["platform", "--help"])
        assert "platform" in result.output

        result = runner.invoke(cli, ["rbac", "--help"])
        assert "rbac" in result.output


class TestHelpPerformance:
    """Tests for help response time.

    Task: T047
    Requirement: FR-053
    """

    @pytest.mark.requirement("FR-053")
    def test_root_help_responds_under_one_second(self) -> None:
        """Test that root help responds in under 1 second.

        Performance requirement ensures CLI feels responsive to users.
        """
        runner = CliRunner()

        start = time.perf_counter()
        result = runner.invoke(cli, ["--help"])
        elapsed = time.perf_counter() - start

        assert result.exit_code == 0
        assert elapsed < 1.0, f"Help took {elapsed:.2f}s, should be < 1s"

    @pytest.mark.requirement("FR-053")
    def test_platform_help_responds_under_one_second(self) -> None:
        """Test that platform help responds in under 1 second."""
        runner = CliRunner()

        start = time.perf_counter()
        result = runner.invoke(cli, ["platform", "--help"])
        elapsed = time.perf_counter() - start

        assert result.exit_code == 0
        assert elapsed < 1.0, f"Help took {elapsed:.2f}s, should be < 1s"

    @pytest.mark.requirement("FR-053")
    def test_rbac_help_responds_under_one_second(self) -> None:
        """Test that rbac help responds in under 1 second."""
        runner = CliRunner()

        start = time.perf_counter()
        result = runner.invoke(cli, ["rbac", "--help"])
        elapsed = time.perf_counter() - start

        assert result.exit_code == 0
        assert elapsed < 1.0, f"Help took {elapsed:.2f}s, should be < 1s"

    @pytest.mark.requirement("FR-053")
    def test_all_subcommand_help_responds_under_one_second(self) -> None:
        """Test that all subcommand help responds in under 1 second."""
        runner = CliRunner()

        subcommands = [
            ["platform", "compile", "--help"],
            ["platform", "test", "--help"],
            ["platform", "publish", "--help"],
            ["platform", "deploy", "--help"],
            ["platform", "status", "--help"],
            ["rbac", "generate", "--help"],
            ["rbac", "validate", "--help"],
            ["rbac", "audit", "--help"],
            ["rbac", "diff", "--help"],
        ]

        for cmd in subcommands:
            start = time.perf_counter()
            result = runner.invoke(cli, cmd)
            elapsed = time.perf_counter() - start

            assert result.exit_code == 0, f"{' '.join(cmd)} failed"
            assert elapsed < 1.0, f"{' '.join(cmd)} took {elapsed:.2f}s, should be < 1s"


__all__: list[str] = [
    "TestRootHelp",
    "TestPlatformGroupHelp",
    "TestRbacGroupHelp",
    "TestArtifactGroupHelp",
    "TestHelpConsistency",
    "TestHelpPerformance",
]
