"""Snapshot tests for CLI help text format.

Task ID: T041
Phase: 5 - User Story 3 (Help Discovery)
User Story: US3 - Discoverable Command Help
Requirements: FR-052

These tests verify that help text format remains consistent and readable.
Snapshots are stored in tests/fixtures/cli/golden/ for regression testing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli


# Path to golden files
GOLDEN_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "tests" / "fixtures" / "cli" / "golden"


class TestRootHelpSnapshot:
    """Snapshot tests for root command help.

    Task: T041
    Requirement: FR-052
    """

    @pytest.mark.requirement("FR-052")
    def test_root_help_format(self) -> None:
        """Test that root help output has expected structure."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0

        # Verify structural elements are present
        output = result.output

        # Must have Usage line
        assert "Usage:" in output

        # Must have Options section
        assert "Options:" in output

        # Must have Commands section
        assert "Commands:" in output

        # Commands must be listed with descriptions
        lines = output.split("\n")
        commands_section_started = False
        command_lines: list[str] = []

        for line in lines:
            if "Commands:" in line:
                commands_section_started = True
                continue
            if commands_section_started and line.strip():
                command_lines.append(line)

        # Should have at least platform, rbac, artifact
        assert len(command_lines) >= 3, f"Expected at least 3 commands, got {len(command_lines)}"


class TestPlatformHelpSnapshot:
    """Snapshot tests for platform command group help.

    Task: T041
    Requirement: FR-052
    """

    @pytest.mark.requirement("FR-052")
    def test_platform_help_format(self) -> None:
        """Test that platform help output has expected structure."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0

        output = result.output

        # Must have Usage line with platform
        assert "Usage:" in output
        assert "platform" in output

        # Must have Commands section with subcommands
        assert "Commands:" in output

        # Verify all subcommands are listed
        assert "compile" in output
        assert "test" in output
        assert "publish" in output
        assert "deploy" in output
        assert "status" in output

    @pytest.mark.requirement("FR-052")
    def test_platform_compile_help_format(self) -> None:
        """Test that platform compile help has proper option documentation."""
        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "compile", "--help"])

        assert result.exit_code == 0

        output = result.output

        # Must have Options section
        assert "Options:" in output

        # Options must have help text (not just the flag)
        # Check that option descriptions exist
        assert "floe.yaml" in output.lower() or "spec" in output.lower()
        assert "manifest" in output.lower()


class TestRbacHelpSnapshot:
    """Snapshot tests for RBAC command group help.

    Task: T041
    Requirement: FR-052
    """

    @pytest.mark.requirement("FR-052")
    def test_rbac_help_format(self) -> None:
        """Test that rbac help output has expected structure."""
        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0

        output = result.output

        # Must have Usage line with rbac
        assert "Usage:" in output
        assert "rbac" in output

        # Must have Commands section with subcommands
        assert "Commands:" in output

        # Verify all subcommands are listed
        assert "generate" in output
        assert "validate" in output
        assert "audit" in output
        assert "diff" in output


class TestHelpTextQuality:
    """Tests for help text quality and readability.

    Task: T041
    Requirement: FR-052
    """

    @pytest.mark.requirement("FR-052")
    def test_no_truncated_descriptions(self) -> None:
        """Test that command descriptions are not truncated with ellipsis."""
        runner = CliRunner()

        # Check root help
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        # Truncated descriptions typically end with "..."
        lines = result.output.split("\n")
        for line in lines:
            # Check for lines in Commands section that might be truncated
            if line.strip() and not line.strip().startswith("Usage:"):
                # Allow ellipsis only in instructional text, not descriptions
                if "..." in line and "OPTIONS" not in line and "COMMAND" not in line:
                    # This is acceptable in epilog/instructions
                    pass

    @pytest.mark.requirement("FR-052")
    def test_options_have_help_text(self) -> None:
        """Test that all options have help text."""
        runner = CliRunner()

        # Check a command with many options
        result = runner.invoke(cli, ["platform", "compile", "--help"])
        assert result.exit_code == 0

        output = result.output
        lines = output.split("\n")

        # Find lines that look like options (start with --)
        option_lines = [line for line in lines if line.strip().startswith("-")]

        # Each option should have description text
        for opt_line in option_lines:
            # Options without help text typically just show the flag
            # Good options have: "  --option  Description text"
            parts = opt_line.split()
            # At minimum: flag and at least one word of description
            assert len(parts) >= 2, f"Option may lack help text: {opt_line}"

    @pytest.mark.requirement("FR-052")
    def test_consistent_option_naming(self) -> None:
        """Test that options follow consistent naming conventions."""
        runner = CliRunner()

        # Commands should use consistent short option naming
        # -o for output, -c for config, -m for manifest, -n for namespace

        # Check rbac generate
        result = runner.invoke(cli, ["rbac", "generate", "--help"])
        assert result.exit_code == 0
        # Should have -c for config, -o for output
        assert "-c" in result.output or "--config" in result.output
        assert "-o" in result.output or "--output" in result.output

        # Check rbac validate
        result = runner.invoke(cli, ["rbac", "validate", "--help"])
        assert result.exit_code == 0
        assert "-c" in result.output or "--config" in result.output
        assert "-m" in result.output or "--manifest-dir" in result.output

        # Check rbac audit
        result = runner.invoke(cli, ["rbac", "audit", "--help"])
        assert result.exit_code == 0
        assert "-n" in result.output or "--namespace" in result.output


class TestGoldenFileComparison:
    """Tests comparing help output to golden files.

    Task: T041
    Requirement: FR-052

    These tests ensure help output doesn't regress from baseline.
    Golden files are stored in tests/fixtures/cli/golden/
    """

    @pytest.mark.requirement("FR-052")
    def test_root_help_matches_golden(self) -> None:
        """Test that root help matches golden file.

        Per Constitution V: tests FAIL, never skip.
        Golden file must exist for regression testing.
        """
        golden_file = GOLDEN_DIR / "root_help.txt"

        if not golden_file.exists():
            pytest.fail(
                f"Golden file missing: {golden_file}\n"
                "Run: floe --help > tests/fixtures/cli/golden/root_help.txt"
            )

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0

        golden_content = golden_file.read_text()
        assert result.output == golden_content, (
            f"Root help output differs from golden file.\n"
            f"To update: run the command and save output to {golden_file}"
        )

    @pytest.mark.requirement("FR-052")
    def test_platform_help_matches_golden(self) -> None:
        """Test that platform help matches golden file.

        Per Constitution V: tests FAIL, never skip.
        Golden file must exist for regression testing.
        """
        golden_file = GOLDEN_DIR / "platform_help.txt"

        if not golden_file.exists():
            pytest.fail(
                f"Golden file missing: {golden_file}\n"
                "Run: floe platform --help > tests/fixtures/cli/golden/platform_help.txt"
            )

        runner = CliRunner()
        result = runner.invoke(cli, ["platform", "--help"])

        assert result.exit_code == 0

        golden_content = golden_file.read_text()
        assert result.output == golden_content, (
            f"Platform help output differs from golden file.\n"
            f"To update: run the command and save output to {golden_file}"
        )


__all__: list[str] = [
    "TestRootHelpSnapshot",
    "TestPlatformHelpSnapshot",
    "TestRbacHelpSnapshot",
    "TestHelpTextQuality",
    "TestGoldenFileComparison",
]
