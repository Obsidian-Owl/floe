"""Unit tests for Data Team stub commands.

Task ID: T053
Phase: 7 - User Story 5 (Data Team Stubs)
User Story: US5 - Data Team Compile Stub
Requirements: FR-040, FR-041, FR-042, FR-043

These tests verify the data team stub commands:
- floe compile: Data team spec compilation (stub)
- floe validate: Data team floe.yaml validation (stub)
- floe run: Pipeline execution (stub)
- floe test: dbt test execution (stub)

All stubs should:
- Show appropriate help text
- Output "not yet implemented" message to stderr when invoked
- Exit with code 0 (stubs are informational, not errors)
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from floe_core.cli.main import cli


class TestCompileStub:
    """Tests for floe compile stub command.

    Task: T053, T054
    Requirement: FR-040
    """

    @pytest.mark.requirement("FR-040")
    def test_compile_appears_in_root_help(self) -> None:
        """Test that compile command is listed in root help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "compile" in result.output

    @pytest.mark.requirement("FR-040")
    def test_compile_help_shows_description(self) -> None:
        """Test that compile help shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["compile", "--help"])

        assert result.exit_code == 0
        # Should describe data team usage
        assert "data" in result.output.lower() or "spec" in result.output.lower()

    @pytest.mark.requirement("FR-040")
    def test_compile_stub_outputs_not_implemented_message(self) -> None:
        """Test that compile stub outputs not implemented message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["compile"])

        # Should exit with 0 (stub is informational)
        assert result.exit_code == 0
        # Message in output (stderr captured in output by default)
        assert "not yet implemented" in result.output.lower()

    @pytest.mark.requirement("FR-040")
    def test_compile_stub_suggests_platform_compile(self) -> None:
        """Test that compile stub suggests platform compile for Platform Team."""
        runner = CliRunner()
        result = runner.invoke(cli, ["compile"])

        assert result.exit_code == 0
        assert "platform compile" in result.output.lower()


class TestValidateStub:
    """Tests for floe validate stub command.

    Task: T053, T055
    Requirement: FR-041
    """

    @pytest.mark.requirement("FR-041")
    def test_validate_appears_in_root_help(self) -> None:
        """Test that validate command is listed in root help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "validate" in result.output

    @pytest.mark.requirement("FR-041")
    def test_validate_help_shows_description(self) -> None:
        """Test that validate help shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])

        assert result.exit_code == 0
        # Should describe validation
        assert "validate" in result.output.lower() or "yaml" in result.output.lower()

    @pytest.mark.requirement("FR-041")
    def test_validate_stub_outputs_not_implemented_message(self) -> None:
        """Test that validate stub outputs not implemented message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["validate"])

        assert result.exit_code == 0
        assert "not yet implemented" in result.output.lower()


class TestRunStub:
    """Tests for floe run stub command.

    Task: T053, T056
    Requirement: FR-042
    """

    @pytest.mark.requirement("FR-042")
    def test_run_appears_in_root_help(self) -> None:
        """Test that run command is listed in root help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "run" in result.output

    @pytest.mark.requirement("FR-042")
    def test_run_help_shows_description(self) -> None:
        """Test that run help shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])

        assert result.exit_code == 0
        # Should describe pipeline execution
        assert "run" in result.output.lower() or "pipeline" in result.output.lower()

    @pytest.mark.requirement("FR-042")
    def test_run_stub_outputs_not_implemented_message(self) -> None:
        """Test that run stub outputs not implemented message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["run"])

        assert result.exit_code == 0
        assert "not yet implemented" in result.output.lower()


class TestTestStub:
    """Tests for floe test stub command.

    Task: T053, T057
    Requirement: FR-043
    """

    @pytest.mark.requirement("FR-043")
    def test_test_appears_in_root_help(self) -> None:
        """Test that test command is listed in root help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "test" in result.output

    @pytest.mark.requirement("FR-043")
    def test_test_help_shows_description(self) -> None:
        """Test that test help shows description."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "--help"])

        assert result.exit_code == 0
        # Should describe testing
        assert "test" in result.output.lower() or "dbt" in result.output.lower()

    @pytest.mark.requirement("FR-043")
    def test_test_stub_outputs_not_implemented_message(self) -> None:
        """Test that test stub outputs not implemented message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test"])

        assert result.exit_code == 0
        assert "not yet implemented" in result.output.lower()


class TestStubConsistency:
    """Tests for consistency across all stub commands.

    Task: T053
    Requirements: FR-040, FR-041, FR-042, FR-043
    """

    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("FR-042")
    @pytest.mark.requirement("FR-043")
    def test_all_stubs_support_short_help_flag(self) -> None:
        """Test that all stub commands support -h for help."""
        runner = CliRunner()
        commands = ["compile", "validate", "run", "test"]

        for cmd in commands:
            result = runner.invoke(cli, [cmd, "-h"])
            assert result.exit_code == 0, f"{cmd} -h failed"
            assert "Usage:" in result.output, f"{cmd} -h missing Usage"

    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("FR-042")
    @pytest.mark.requirement("FR-043")
    def test_all_stubs_exit_with_zero(self) -> None:
        """Test that all stub commands exit with code 0."""
        runner = CliRunner()
        commands = ["compile", "validate", "run", "test"]

        for cmd in commands:
            result = runner.invoke(cli, [cmd])
            assert result.exit_code == 0, f"{cmd} exited with {result.exit_code}"


__all__: list[str] = [
    "TestCompileStub",
    "TestValidateStub",
    "TestRunStub",
    "TestTestStub",
    "TestStubConsistency",
]
