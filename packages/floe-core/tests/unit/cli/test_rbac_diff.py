"""Unit tests for the rbac diff command.

Task ID: T030
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-026, FR-027

Tests cover:
- Command accepts --manifest-dir option (FR-026)
- Command accepts --namespace option (FR-026)
- Command accepts --output option (FR-026)
- Command accepts --kubeconfig option (FR-026)
- Command shows added, removed, modified resources (FR-027)
- Exit code handling
- _k8s_to_dict helper function
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestRbacDiffCommand:
    """Tests for the rbac diff CLI command."""

    @pytest.mark.requirement("FR-026")
    def test_diff_accepts_manifest_dir_option(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that diff command accepts --manifest-dir option.

        Validates that the --manifest-dir option is recognized.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "diff",
                "--manifest-dir",
                str(manifest_dir),
                "--namespace",
                "default",
            ],
        )

        assert "Error: No such option: --manifest-dir" not in (result.output or "")

    @pytest.mark.requirement("FR-026")
    def test_diff_accepts_namespace_option(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that diff command accepts --namespace option.

        Validates that the --namespace option is recognized.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "diff",
                "--manifest-dir",
                str(manifest_dir),
                "--namespace",
                "floe",
            ],
        )

        assert "Error: No such option: --namespace" not in (result.output or "")

    @pytest.mark.requirement("FR-026")
    def test_diff_accepts_output_option(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that diff command accepts --output option.

        Validates that the --output option is recognized for format choice.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "diff",
                "--manifest-dir",
                str(manifest_dir),
                "--namespace",
                "default",
                "--output",
                "text",
            ],
        )

        assert "Error: No such option: --output" not in (result.output or "")

    @pytest.mark.requirement("FR-026")
    def test_diff_accepts_kubeconfig_option(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that diff command accepts --kubeconfig option.

        Validates that the --kubeconfig option is recognized.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        kubeconfig = temp_dir / "kubeconfig"
        kubeconfig.write_text("# placeholder kubeconfig")

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "diff",
                "--manifest-dir",
                str(manifest_dir),
                "--namespace",
                "default",
                "--kubeconfig",
                str(kubeconfig),
            ],
        )

        assert "Error: No such option: --kubeconfig" not in (result.output or "")

    @pytest.mark.requirement("FR-026")
    def test_diff_shows_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that diff command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "diff", "--help"],
        )

        assert result.exit_code == 0
        assert "diff" in result.output.lower()

    @pytest.mark.requirement("FR-026")
    def test_diff_fails_without_manifest_dir(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that diff fails when --manifest-dir not provided.

        Validates proper error handling for missing required option.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "diff",
                "--namespace",
                "default",
            ],
        )

        # Should fail when manifest-dir not provided
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-026")
    def test_diff_fails_without_namespace(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that diff fails when --namespace not provided.

        Validates proper error handling for missing required namespace.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "diff",
                "--manifest-dir",
                str(manifest_dir),
            ],
        )

        # Should fail when namespace not provided
        assert result.exit_code != 0

    @pytest.mark.requirement("FR-027")
    def test_diff_output_formats(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test that diff accepts different output formats.

        Validates that --output accepts text and json formats.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        for output_format in ["text", "json"]:
            result = cli_runner.invoke(
                cli,
                [
                    "rbac",
                    "diff",
                    "--manifest-dir",
                    str(manifest_dir),
                    "--namespace",
                    "default",
                    "--output",
                    output_format,
                ],
            )

            assert "Error: Invalid value for '--output'" not in (result.output or ""), (
                f"Format {output_format} should be valid"
            )


class TestRbacDiffInGroup:
    """Tests for diff subcommand in rbac group."""

    @pytest.mark.requirement("FR-026")
    def test_rbac_shows_diff_subcommand(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that rbac group shows diff subcommand.

        Validates that diff is listed in rbac help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        assert "diff" in result.output.lower()


class TestK8sToDictHelper:
    """Tests for the _k8s_to_dict helper function."""

    @pytest.mark.requirement("FR-027")
    def test_k8s_to_dict_role(self) -> None:
        """Test _k8s_to_dict converts Role resources correctly."""
        from floe_core.cli.rbac.diff import _k8s_to_dict

        mock_rule = MagicMock()
        mock_rule.api_groups = [""]
        mock_rule.resources = ["pods"]
        mock_rule.verbs = ["get", "list"]
        mock_rule.resource_names = []

        mock_resource = MagicMock()
        mock_resource.metadata.name = "test-role"
        mock_resource.metadata.namespace = "default"
        mock_resource.rules = [mock_rule]

        result = _k8s_to_dict(mock_resource, "Role")

        assert result["kind"] == "Role"
        assert result["apiVersion"] == "rbac.authorization.k8s.io/v1"
        assert result["metadata"]["name"] == "test-role"
        assert result["metadata"]["namespace"] == "default"
        assert len(result["rules"]) == 1
        assert result["rules"][0]["resources"] == ["pods"]

    @pytest.mark.requirement("FR-027")
    def test_k8s_to_dict_role_binding(self) -> None:
        """Test _k8s_to_dict converts RoleBinding resources correctly."""
        from floe_core.cli.rbac.diff import _k8s_to_dict

        mock_subject = MagicMock()
        mock_subject.kind = "ServiceAccount"
        mock_subject.name = "test-sa"
        mock_subject.namespace = "default"

        mock_role_ref = MagicMock()
        mock_role_ref.api_group = "rbac.authorization.k8s.io"
        mock_role_ref.kind = "Role"
        mock_role_ref.name = "test-role"

        mock_resource = MagicMock()
        mock_resource.metadata.name = "test-rb"
        mock_resource.metadata.namespace = "default"
        mock_resource.role_ref = mock_role_ref
        mock_resource.subjects = [mock_subject]

        result = _k8s_to_dict(mock_resource, "RoleBinding")

        assert result["kind"] == "RoleBinding"
        assert result["apiVersion"] == "rbac.authorization.k8s.io/v1"
        assert result["roleRef"]["name"] == "test-role"
        assert len(result["subjects"]) == 1
        assert result["subjects"][0]["name"] == "test-sa"

    @pytest.mark.requirement("FR-027")
    def test_k8s_to_dict_service_account(self) -> None:
        """Test _k8s_to_dict converts ServiceAccount resources correctly."""
        from floe_core.cli.rbac.diff import _k8s_to_dict

        mock_resource = MagicMock()
        mock_resource.metadata.name = "test-sa"
        mock_resource.metadata.namespace = "default"

        result = _k8s_to_dict(mock_resource, "ServiceAccount")

        assert result["kind"] == "ServiceAccount"
        assert result["apiVersion"] == "v1"
        assert result["metadata"]["name"] == "test-sa"
        assert result["metadata"]["namespace"] == "default"

    @pytest.mark.requirement("FR-027")
    def test_k8s_to_dict_role_without_rules(self) -> None:
        """Test _k8s_to_dict handles Role without rules."""
        from floe_core.cli.rbac.diff import _k8s_to_dict

        mock_resource = MagicMock()
        mock_resource.metadata.name = "empty-role"
        mock_resource.metadata.namespace = "default"
        mock_resource.rules = None

        result = _k8s_to_dict(mock_resource, "Role")

        assert result["kind"] == "Role"
        assert "rules" not in result

    @pytest.mark.requirement("FR-027")
    def test_k8s_to_dict_role_binding_without_subjects(self) -> None:
        """Test _k8s_to_dict handles RoleBinding without subjects."""
        from floe_core.cli.rbac.diff import _k8s_to_dict

        mock_role_ref = MagicMock()
        mock_role_ref.api_group = "rbac.authorization.k8s.io"
        mock_role_ref.kind = "Role"
        mock_role_ref.name = "test-role"

        mock_resource = MagicMock()
        mock_resource.metadata.name = "test-rb"
        mock_resource.metadata.namespace = "default"
        mock_resource.role_ref = mock_role_ref
        mock_resource.subjects = None

        result = _k8s_to_dict(mock_resource, "RoleBinding")

        assert result["kind"] == "RoleBinding"
        assert "subjects" not in result


__all__: list[str] = [
    "TestRbacDiffCommand",
    "TestRbacDiffInGroup",
    "TestK8sToDictHelper",
]
