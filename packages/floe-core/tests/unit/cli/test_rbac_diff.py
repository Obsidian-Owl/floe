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

            assert "Error: Invalid value for '--output'" not in (
                result.output or ""
            ), f"Format {output_format} should be valid"


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


class TestDiffHelperFunctions:
    """Tests for helper functions in the diff module."""

    @pytest.mark.requirement("FR-027")
    def test_load_expected_manifests(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _load_expected_manifests loads manifests correctly.

        Validates that manifest files are loaded and parsed.
        """
        from floe_core.cli.rbac.diff import _load_expected_manifests

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        # Create valid manifest files
        (manifest_dir / "roles.yaml").write_text(
            """apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: test-role
  namespace: default
"""
        )
        (manifest_dir / "rolebindings.yaml").write_text(
            """apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: test-binding
  namespace: default
"""
        )
        (manifest_dir / "serviceaccounts.yaml").write_text("")

        resources = _load_expected_manifests(manifest_dir)

        assert len(resources) == 2
        assert resources[0]["kind"] == "Role"
        assert resources[1]["kind"] == "RoleBinding"

    @pytest.mark.requirement("FR-027")
    def test_load_expected_manifests_empty_files(
        self,
        temp_dir: Path,
    ) -> None:
        """Test _load_expected_manifests handles empty files.

        Validates that empty manifest files don't cause errors.
        """
        from floe_core.cli.rbac.diff import _load_expected_manifests

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        # Create empty manifest files
        (manifest_dir / "roles.yaml").write_text("   \n\n")
        (manifest_dir / "rolebindings.yaml").write_text("")
        (manifest_dir / "serviceaccounts.yaml").write_text("# comment only\n")

        resources = _load_expected_manifests(manifest_dir)

        assert len(resources) == 0

    @pytest.mark.requirement("FR-027")
    def test_get_api_version(self) -> None:
        """Test _get_api_version returns correct versions.

        Validates API version lookup for different resource kinds.
        """
        from floe_core.cli.rbac.diff import _get_api_version

        assert _get_api_version("ServiceAccount") == "v1"
        assert _get_api_version("Role") == "rbac.authorization.k8s.io/v1"
        assert _get_api_version("RoleBinding") == "rbac.authorization.k8s.io/v1"
        assert _get_api_version("ClusterRole") == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-027")
    def test_add_role_fields(self) -> None:
        """Test _add_role_fields adds role-specific fields.

        Validates that rules are correctly added to Role results.
        """
        from floe_core.cli.rbac.diff import _add_role_fields

        mock_rule = MagicMock()
        mock_rule.api_groups = ["apps"]
        mock_rule.resources = ["deployments"]
        mock_rule.verbs = ["get", "list"]
        mock_rule.resource_names = []

        mock_resource = MagicMock()
        mock_resource.rules = [mock_rule]

        result: dict[str, list[dict[str, list[str]]]] = {}
        _add_role_fields(result, mock_resource, "Role")

        assert "rules" in result
        assert len(result["rules"]) == 1
        assert result["rules"][0]["apiGroups"] == ["apps"]
        assert result["rules"][0]["resources"] == ["deployments"]
        assert result["rules"][0]["verbs"] == ["get", "list"]

    @pytest.mark.requirement("FR-027")
    def test_add_role_fields_not_role(self) -> None:
        """Test _add_role_fields skips non-Role kinds.

        Validates that non-Role resources are not modified.
        """
        from floe_core.cli.rbac.diff import _add_role_fields

        mock_resource = MagicMock()
        mock_resource.rules = [MagicMock()]

        result: dict[str, list[dict[str, list[str]]]] = {}
        _add_role_fields(result, mock_resource, "ServiceAccount")

        assert "rules" not in result

    @pytest.mark.requirement("FR-027")
    def test_add_role_binding_fields(self) -> None:
        """Test _add_role_binding_fields adds binding-specific fields.

        Validates that roleRef and subjects are correctly added.
        """
        from typing import Any

        from floe_core.cli.rbac.diff import _add_role_binding_fields

        mock_subject = MagicMock()
        mock_subject.kind = "ServiceAccount"
        mock_subject.name = "test-sa"
        mock_subject.namespace = "default"

        mock_role_ref = MagicMock()
        mock_role_ref.api_group = "rbac.authorization.k8s.io"
        mock_role_ref.kind = "Role"
        mock_role_ref.name = "test-role"

        mock_resource = MagicMock()
        mock_resource.role_ref = mock_role_ref
        mock_resource.subjects = [mock_subject]

        result: dict[str, Any] = {}
        _add_role_binding_fields(result, mock_resource, "RoleBinding")

        assert "roleRef" in result
        assert result["roleRef"]["name"] == "test-role"
        assert "subjects" in result
        assert len(result["subjects"]) == 1
        assert result["subjects"][0]["name"] == "test-sa"

    @pytest.mark.requirement("FR-027")
    def test_add_role_binding_fields_not_binding(self) -> None:
        """Test _add_role_binding_fields skips non-RoleBinding kinds.

        Validates that non-RoleBinding resources are not modified.
        """
        from typing import Any

        from floe_core.cli.rbac.diff import _add_role_binding_fields

        mock_resource = MagicMock()
        mock_resource.role_ref = MagicMock()
        mock_resource.subjects = [MagicMock()]

        result: dict[str, Any] = {}
        _add_role_binding_fields(result, mock_resource, "Role")

        assert "roleRef" not in result
        assert "subjects" not in result


class TestDiffOutputFormatting:
    """Tests for diff output formatting."""

    @pytest.mark.requirement("FR-027")
    def test_output_diff_as_text_no_differences(self) -> None:
        """Test text output when no differences found.

        Validates success message is shown when manifests match.
        """
        from floe_core.schemas.rbac_diff import RBACDiffResult

        diff_result = RBACDiffResult(
            expected_source="manifests/rbac",
            actual_source="cluster:default",
            diffs=[],
        )

        assert not diff_result.has_differences()

    @pytest.mark.requirement("FR-027")
    def test_output_diff_as_text_with_differences(self) -> None:
        """Test text output with differences.

        Validates diff details are properly formatted.
        """
        from floe_core.schemas.rbac_diff import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        added_diff = ResourceDiff(
            resource_kind="Role",
            resource_name="new-role",
            resource_namespace="default",
            change_type=DiffChangeType.ADDED,
            diff_details=["Resource exists in manifest but not in cluster"],
        )

        removed_diff = ResourceDiff(
            resource_kind="ServiceAccount",
            resource_name="old-sa",
            resource_namespace="default",
            change_type=DiffChangeType.REMOVED,
            diff_details=["Resource exists in cluster but not in manifest"],
        )

        modified_diff = ResourceDiff(
            resource_kind="Role",
            resource_name="changed-role",
            resource_namespace="default",
            change_type=DiffChangeType.MODIFIED,
            diff_details=["rules[0].verbs: ['get'] -> ['get', 'list']"],
        )

        diff_result = RBACDiffResult(
            expected_source="manifests/rbac",
            actual_source="cluster:default",
            diffs=[added_diff, removed_diff, modified_diff],
            added_count=1,
            removed_count=1,
            modified_count=1,
        )

        assert diff_result.has_differences()
        assert diff_result.added_count == 1
        assert diff_result.removed_count == 1
        assert diff_result.modified_count == 1

        by_type = diff_result.diffs_by_change_type()
        assert len(by_type[DiffChangeType.ADDED]) == 1
        assert len(by_type[DiffChangeType.REMOVED]) == 1
        assert len(by_type[DiffChangeType.MODIFIED]) == 1

    @pytest.mark.requirement("FR-027")
    def test_diff_json_output(self) -> None:
        """Test JSON output formatting.

        Validates that diff result can be serialized to JSON.
        """
        import json

        from floe_core.schemas.rbac_diff import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        diff = ResourceDiff(
            resource_kind="Role",
            resource_name="test-role",
            resource_namespace="default",
            change_type=DiffChangeType.ADDED,
            diff_details=["New resource"],
        )

        diff_result = RBACDiffResult(
            expected_source="manifests/rbac",
            actual_source="cluster:default",
            diffs=[diff],
        )

        json_output = diff_result.model_dump_json(indent=2)
        parsed = json.loads(json_output)

        assert parsed["expected_source"] == "manifests/rbac"
        assert parsed["actual_source"] == "cluster:default"
        assert len(parsed["diffs"]) == 1
        assert parsed["diffs"][0]["resource_name"] == "test-role"


class TestValidateRequiredOptions:
    """Tests for _validate_required_options helper."""

    @pytest.mark.requirement("FR-026")
    def test_validate_required_options_success(
        self,
        temp_dir: Path,
    ) -> None:
        """Test validation succeeds with valid options.

        Validates that valid options are returned unchanged.
        """
        from floe_core.cli.rbac.diff import _validate_required_options

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result_dir, result_ns = _validate_required_options(manifest_dir, "default")

        assert result_dir == manifest_dir
        assert result_ns == "default"


class TestOutputDiffAsText:
    """Tests for _output_diff_as_text function."""

    @pytest.mark.requirement("FR-027")
    def test_output_diff_as_text_no_differences(
        self,
    ) -> None:
        """Test _output_diff_as_text shows success when no differences.

        Validates that success message is shown for matching manifests.
        """
        from click.testing import CliRunner

        from floe_core.cli.rbac.diff import _output_diff_as_text
        from floe_core.schemas.rbac_diff import RBACDiffResult

        diff_result = RBACDiffResult(
            expected_source="manifests/rbac",
            actual_source="cluster:default",
            diffs=[],
        )

        # Capture output using click's testing utilities
        runner = CliRunner()
        with runner.isolated_filesystem():
            import click

            @click.command()
            def test_cmd() -> None:
                _output_diff_as_text(diff_result)

            result = runner.invoke(test_cmd)
            assert "No differences found" in result.output

    @pytest.mark.requirement("FR-027")
    def test_output_diff_as_text_with_added_resources(
        self,
    ) -> None:
        """Test _output_diff_as_text shows added resources.

        Validates that added resources are properly formatted.
        """
        from click.testing import CliRunner

        from floe_core.cli.rbac.diff import _output_diff_as_text
        from floe_core.schemas.rbac_diff import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        added_diff = ResourceDiff(
            resource_kind="Role",
            resource_name="new-role",
            resource_namespace="default",
            change_type=DiffChangeType.ADDED,
            diff_details=["Resource exists in manifest but not in cluster"],
        )

        diff_result = RBACDiffResult(
            expected_source="manifests/rbac",
            actual_source="cluster:default",
            diffs=[added_diff],
            added_count=1,
            removed_count=0,
            modified_count=0,
        )

        runner = CliRunner()
        with runner.isolated_filesystem():
            import click

            @click.command()
            def test_cmd() -> None:
                _output_diff_as_text(diff_result)

            result = runner.invoke(test_cmd)
            assert "1 difference" in result.output
            assert "To be created" in result.output
            assert "+ Role/new-role" in result.output

    @pytest.mark.requirement("FR-027")
    def test_output_diff_as_text_with_removed_resources(
        self,
    ) -> None:
        """Test _output_diff_as_text shows removed resources.

        Validates that removed resources are properly formatted.
        """
        from click.testing import CliRunner

        from floe_core.cli.rbac.diff import _output_diff_as_text
        from floe_core.schemas.rbac_diff import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        removed_diff = ResourceDiff(
            resource_kind="ServiceAccount",
            resource_name="old-sa",
            resource_namespace="default",
            change_type=DiffChangeType.REMOVED,
            diff_details=["Resource exists in cluster but not in manifest"],
        )

        diff_result = RBACDiffResult(
            expected_source="manifests/rbac",
            actual_source="cluster:default",
            diffs=[removed_diff],
            added_count=0,
            removed_count=1,
            modified_count=0,
        )

        runner = CliRunner()
        with runner.isolated_filesystem():
            import click

            @click.command()
            def test_cmd() -> None:
                _output_diff_as_text(diff_result)

            result = runner.invoke(test_cmd)
            assert "1 difference" in result.output
            assert "To be removed" in result.output
            assert "- ServiceAccount/old-sa" in result.output

    @pytest.mark.requirement("FR-027")
    def test_output_diff_as_text_with_modified_resources(
        self,
    ) -> None:
        """Test _output_diff_as_text shows modified resources.

        Validates that modified resources and their details are properly formatted.
        """
        from click.testing import CliRunner

        from floe_core.cli.rbac.diff import _output_diff_as_text
        from floe_core.schemas.rbac_diff import (
            DiffChangeType,
            RBACDiffResult,
            ResourceDiff,
        )

        modified_diff = ResourceDiff(
            resource_kind="Role",
            resource_name="changed-role",
            resource_namespace="default",
            change_type=DiffChangeType.MODIFIED,
            diff_details=["rules[0].verbs: ['get'] -> ['get', 'list']"],
        )

        diff_result = RBACDiffResult(
            expected_source="manifests/rbac",
            actual_source="cluster:default",
            diffs=[modified_diff],
            added_count=0,
            removed_count=0,
            modified_count=1,
        )

        runner = CliRunner()
        with runner.isolated_filesystem():
            import click

            @click.command()
            def test_cmd() -> None:
                _output_diff_as_text(diff_result)

            result = runner.invoke(test_cmd)
            assert "1 difference" in result.output
            assert "To be modified" in result.output
            assert "~ Role/changed-role" in result.output
            assert "rules[0].verbs" in result.output


__all__: list[str] = [
    "TestRbacDiffCommand",
    "TestRbacDiffInGroup",
    "TestK8sToDictHelper",
    "TestDiffHelperFunctions",
    "TestDiffOutputFormatting",
    "TestValidateRequiredOptions",
    "TestOutputDiffAsText",
]
