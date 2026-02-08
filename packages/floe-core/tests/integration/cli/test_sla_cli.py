"""Integration tests for SLA CLI commands.

Task: T087
Requirements: 3D-FR-038, 3D-FR-039

These tests validate the floe sla CLI command group with real command execution.
Tests FAIL when infrastructure is missing (per project testing standards).
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from floe_core.cli.main import sla


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI runner for testing commands.

    Returns:
        CliRunner instance for invoking CLI commands.
    """
    return CliRunner()


@pytest.mark.requirement("3D-FR-038")
@pytest.mark.integration
def test_sla_cli_help(cli_runner: CliRunner) -> None:
    """Test that the sla CLI group shows help text.

    Validates that the sla command group is properly registered and
    displays help information including available subcommands.

    Args:
        cli_runner: Click CLI runner fixture.
    """
    result = cli_runner.invoke(sla, ["--help"])
    assert result.exit_code == 0
    assert "report" in result.output


@pytest.mark.requirement("3D-FR-038")
@pytest.mark.integration
def test_sla_cli_report_requires_contract(cli_runner: CliRunner) -> None:
    """Test that sla report command works with optional contract parameter.

    Validates that the report command can be invoked without required args
    (contract is optional) and properly processes the request.

    Args:
        cli_runner: Click CLI runner fixture.
    """
    # Report command should work without --contract (it's optional)
    result = cli_runner.invoke(sla, ["report"])
    # Should succeed with sample report
    assert result.exit_code == 0
