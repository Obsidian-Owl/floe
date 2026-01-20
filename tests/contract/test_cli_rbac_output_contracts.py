"""Contract tests for RBAC CLI command output equivalence.

Task ID: T031
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: SC-003, FR-052

These tests compare migrated RBAC command output against golden files
captured in T011. The golden files represent the expected behavior
before migration, ensuring output equivalence after migration.

Success Criteria SC-003: All 4 RBAC commands (generate, validate, audit, diff)
produce identical output before and after migration, verified via golden
file comparison.

Requirement FR-052: System MUST preserve all existing RBAC command functionality
during migration.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    pass


# Path to golden files captured in T011
GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "cli" / "golden"


def normalize_help_output(output: str) -> str:
    """Normalize help output for comparison.

    Removes trailing whitespace, normalizes line endings,
    and ignores minor formatting differences.

    Args:
        output: Raw command output string.

    Returns:
        Normalized string for comparison.
    """
    lines = output.strip().split("\n")
    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in lines]
    # Join with consistent line endings
    return "\n".join(lines)


class TestRbacGenerateOutputContract:
    """Contract tests for rbac generate command output.

    Task: T031
    Requirement: SC-003, FR-052
    """

    @pytest.mark.requirement("SC-003")
    @pytest.mark.requirement("FR-052")
    def test_generate_help_matches_golden(self) -> None:
        """Test that rbac generate --help matches golden file.

        The help output MUST match the pre-migration golden file
        to ensure command interface stability.
        """
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "generate", "--help"])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        golden_path = GOLDEN_DIR / "rbac_generate_help.txt"
        assert golden_path.exists(), f"Golden file not found: {golden_path}"

        golden_output = normalize_help_output(golden_path.read_text())
        actual_output = normalize_help_output(result.output)

        assert actual_output == golden_output, (
            f"Help output does not match golden file.\n"
            f"Expected:\n{golden_output}\n\n"
            f"Actual:\n{actual_output}"
        )


class TestRbacValidateOutputContract:
    """Contract tests for rbac validate command output.

    Task: T031
    Requirement: SC-003, FR-052
    """

    @pytest.mark.requirement("SC-003")
    @pytest.mark.requirement("FR-052")
    def test_validate_help_matches_golden(self) -> None:
        """Test that rbac validate --help matches golden file.

        The help output MUST match the pre-migration golden file
        to ensure command interface stability.
        """
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "validate", "--help"])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        golden_path = GOLDEN_DIR / "rbac_validate_help.txt"
        assert golden_path.exists(), f"Golden file not found: {golden_path}"

        golden_output = normalize_help_output(golden_path.read_text())
        actual_output = normalize_help_output(result.output)

        assert actual_output == golden_output, (
            f"Help output does not match golden file.\n"
            f"Expected:\n{golden_output}\n\n"
            f"Actual:\n{actual_output}"
        )


class TestRbacAuditOutputContract:
    """Contract tests for rbac audit command output.

    Task: T031
    Requirement: SC-003, FR-052
    """

    @pytest.mark.requirement("SC-003")
    @pytest.mark.requirement("FR-052")
    def test_audit_help_matches_golden(self) -> None:
        """Test that rbac audit --help matches golden file.

        The help output MUST match the pre-migration golden file
        to ensure command interface stability.
        """
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "audit", "--help"])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        golden_path = GOLDEN_DIR / "rbac_audit_help.txt"
        assert golden_path.exists(), f"Golden file not found: {golden_path}"

        golden_output = normalize_help_output(golden_path.read_text())
        actual_output = normalize_help_output(result.output)

        assert actual_output == golden_output, (
            f"Help output does not match golden file.\n"
            f"Expected:\n{golden_output}\n\n"
            f"Actual:\n{actual_output}"
        )


class TestRbacDiffOutputContract:
    """Contract tests for rbac diff command output.

    Task: T031
    Requirement: SC-003, FR-052
    """

    @pytest.mark.requirement("SC-003")
    @pytest.mark.requirement("FR-052")
    def test_diff_help_matches_golden(self) -> None:
        """Test that rbac diff --help matches golden file.

        The help output MUST match the pre-migration golden file
        to ensure command interface stability.
        """
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "diff", "--help"])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        golden_path = GOLDEN_DIR / "rbac_diff_help.txt"
        assert golden_path.exists(), f"Golden file not found: {golden_path}"

        golden_output = normalize_help_output(golden_path.read_text())
        actual_output = normalize_help_output(result.output)

        assert actual_output == golden_output, (
            f"Help output does not match golden file.\n"
            f"Expected:\n{golden_output}\n\n"
            f"Actual:\n{actual_output}"
        )


class TestRbacCommandExistence:
    """Tests that all RBAC commands exist in the CLI.

    Task: T031
    Requirement: FR-052
    """

    @pytest.mark.requirement("FR-052")
    def test_all_rbac_commands_listed_in_help(self) -> None:
        """Test that all 4 RBAC commands are listed in rbac --help.

        The rbac group MUST list generate, validate, audit, and diff
        subcommands to maintain API compatibility.
        """
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0, f"Command failed: {result.output}"

        output_lower = result.output.lower()
        assert "generate" in output_lower, "rbac generate command not listed"
        assert "validate" in output_lower, "rbac validate command not listed"
        assert "audit" in output_lower, "rbac audit command not listed"
        assert "diff" in output_lower, "rbac diff command not listed"

    @pytest.mark.requirement("FR-052")
    def test_generate_command_accessible(self) -> None:
        """Test that rbac generate command is accessible."""
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "generate", "--help"])

        # Should succeed (exit 0) or fail gracefully (not exit 2 = command not found)
        assert result.exit_code != 2, "rbac generate command not found"

    @pytest.mark.requirement("FR-052")
    def test_validate_command_accessible(self) -> None:
        """Test that rbac validate command is accessible."""
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "validate", "--help"])

        assert result.exit_code != 2, "rbac validate command not found"

    @pytest.mark.requirement("FR-052")
    def test_audit_command_accessible(self) -> None:
        """Test that rbac audit command is accessible."""
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "audit", "--help"])

        assert result.exit_code != 2, "rbac audit command not found"

    @pytest.mark.requirement("FR-052")
    def test_diff_command_accessible(self) -> None:
        """Test that rbac diff command is accessible."""
        from floe_core.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["rbac", "diff", "--help"])

        assert result.exit_code != 2, "rbac diff command not found"


__all__: list[str] = [
    "TestRbacGenerateOutputContract",
    "TestRbacValidateOutputContract",
    "TestRbacAuditOutputContract",
    "TestRbacDiffOutputContract",
    "TestRbacCommandExistence",
]
