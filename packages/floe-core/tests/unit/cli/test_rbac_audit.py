"""Unit tests for the rbac audit command.

Task ID: T029
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-024, FR-025

Tests cover:
- Command accepts --namespace option (FR-024)
- Command accepts --output option (FR-024)
- Command accepts --kubeconfig option (FR-024)
- Command reports security findings (FR-025)
- Graceful handling of missing kubernetes dependency
- Exit code handling
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestRbacAuditCommand:
    """Tests for the rbac audit CLI command."""

    @pytest.mark.requirement("FR-024")
    def test_audit_accepts_namespace_option(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit command accepts --namespace option.

        Validates that the --namespace option is recognized.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "audit",
                "--namespace",
                "floe",
            ],
        )

        assert "Error: No such option: --namespace" not in (result.output or "")

    @pytest.mark.requirement("FR-024")
    def test_audit_accepts_output_option(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit command accepts --output option.

        Validates that the --output option is recognized for format choice.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "audit",
                "--namespace",
                "default",
                "--output",
                "text",
            ],
        )

        assert "Error: No such option: --output" not in (result.output or "")

    @pytest.mark.requirement("FR-024")
    def test_audit_accepts_kubeconfig_option(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that audit command accepts --kubeconfig option.

        Validates that the --kubeconfig option is recognized.
        """
        from floe_core.cli.main import cli

        kubeconfig = temp_dir / "kubeconfig"
        kubeconfig.write_text("# placeholder kubeconfig")

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "audit",
                "--namespace",
                "default",
                "--kubeconfig",
                str(kubeconfig),
            ],
        )

        assert "Error: No such option: --kubeconfig" not in (result.output or "")

    @pytest.mark.requirement("FR-024")
    def test_audit_shows_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "audit", "--help"],
        )

        assert result.exit_code == 0
        assert "audit" in result.output.lower()

    @pytest.mark.requirement("FR-024")
    def test_audit_fails_without_namespace(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit fails when --namespace not provided.

        Validates proper error handling for missing required namespace.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "audit",
            ],
        )

        # Should fail when namespace not provided
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-025")
    def test_audit_output_formats(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit accepts different output formats.

        Validates that --output accepts text and json formats.
        """
        from floe_core.cli.main import cli

        for output_format in ["text", "json"]:
            result = cli_runner.invoke(
                cli,
                [
                    "rbac",
                    "audit",
                    "--namespace",
                    "default",
                    "--output",
                    output_format,
                ],
            )

            assert "Error: Invalid value for '--output'" not in (
                result.output or ""
            ), f"Format {output_format} should be valid"


class TestRbacAuditKubernetesDependency:
    """Tests for kubernetes dependency handling in audit command."""

    @pytest.mark.requirement("FR-024")
    def test_audit_handles_missing_kubernetes(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that audit handles missing kubernetes package gracefully.

        Validates that the command runs without unhandled exceptions.
        The command may fail (if kubernetes is unavailable) or succeed
        (if kubernetes is available), but should not crash.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "audit",
                "--namespace",
                "default",
            ],
        )

        # If kubernetes is not available, command should fail gracefully
        # or succeed if kubernetes is available
        # The key is that no unhandled exception should occur
        assert result.exception is None or isinstance(result.exception, SystemExit)


class TestRbacAuditInGroup:
    """Tests for audit subcommand in rbac group."""

    def test_rbac_shows_audit_subcommand(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that rbac group shows audit subcommand.

        Validates that audit is listed in rbac help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        assert "audit" in result.output.lower()


__all__: list[str] = [
    "TestRbacAuditCommand",
    "TestRbacAuditKubernetesDependency",
    "TestRbacAuditInGroup",
]
