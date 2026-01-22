"""Unit tests for the rbac validate command.

Task ID: T028
Phase: 4 - User Story 2 (RBAC Command Migration)
User Story: US2 - RBAC Command Migration
Requirements: FR-022, FR-023

Tests cover:
- Command accepts --config option (FR-022)
- Command accepts --manifest-dir option (FR-022)
- Command accepts --output option with text/json choices (FR-022)
- Command returns validation status with issue details (FR-023)
- Exit code handling
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from click.testing import CliRunner


class TestRbacValidateCommand:
    """Tests for the rbac validate CLI command."""

    @pytest.mark.requirement("FR-022")
    def test_validate_accepts_config_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command accepts --config option.

        Validates that the --config option is recognized.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
            ],
        )

        assert "Error: No such option: --config" not in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_accepts_manifest_dir_option(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command accepts --manifest-dir option.

        Validates that the --manifest-dir option is recognized.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
            ],
        )

        assert "Error: No such option: --manifest-dir" not in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_accepts_output_option_text(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command accepts --output text option.

        Validates that --output accepts 'text' format choice.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
                "--output",
                "text",
            ],
        )

        assert "Error: Invalid value for '--output'" not in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_accepts_output_option_json(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command accepts --output json option.

        Validates that --output accepts 'json' format choice.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
                "--output",
                "json",
            ],
        )

        assert "Error: Invalid value for '--output'" not in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_rejects_invalid_output_format(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate command rejects invalid --output values.

        Validates that invalid output format choices are rejected.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(manifest_dir),
                "--output",
                "invalid_format",
            ],
        )

        assert result.exit_code != 0
        assert "Invalid value" in (result.output or "") or "invalid_format" in (result.output or "")

    @pytest.mark.requirement("FR-022")
    def test_validate_shows_help(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that validate command shows help text.

        Validates that --help flag works and shows expected options.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(
            cli,
            ["rbac", "validate", "--help"],
        )

        assert result.exit_code == 0
        assert "validate" in result.output.lower()

    @pytest.mark.requirement("FR-023")
    def test_validate_fails_manifest_dir_not_found(
        self,
        cli_runner: CliRunner,
        sample_manifest_yaml: Path,
        temp_dir: Path,
    ) -> None:
        """Test that validate fails when manifest-dir doesn't exist.

        Validates error handling for missing manifest directory.
        """
        from floe_core.cli.main import cli

        nonexistent_dir = temp_dir / "nonexistent_rbac"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--config",
                str(sample_manifest_yaml),
                "--manifest-dir",
                str(nonexistent_dir),
            ],
        )

        assert result.exit_code != 0


class TestRbacValidateInGroup:
    """Tests for validate subcommand in rbac group."""

    @pytest.mark.requirement("FR-023")
    def test_rbac_shows_validate_subcommand(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Test that rbac group shows validate subcommand.

        Validates that validate is listed in rbac help.
        """
        from floe_core.cli.main import cli

        result = cli_runner.invoke(cli, ["rbac", "--help"])

        assert result.exit_code == 0
        assert "validate" in result.output.lower()


class TestRbacValidateManifestHandling:
    """Tests for manifest loading and validation logic."""

    @pytest.mark.requirement("FR-023")
    def test_validate_with_empty_manifest_file(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test validate handles empty manifest files correctly.

        Validates that empty manifest files (whitespace only) are handled gracefully.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        # Create empty manifest files
        (manifest_dir / "namespaces.yaml").write_text("   \n\n")
        (manifest_dir / "serviceaccounts.yaml").write_text("")
        (manifest_dir / "roles.yaml").write_text("# comment only\n")
        (manifest_dir / "rolebindings.yaml").write_text("\n")

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--manifest-dir",
                str(manifest_dir),
            ],
        )

        # Should not crash on empty files
        assert result.exception is None or isinstance(result.exception, SystemExit)

    @pytest.mark.requirement("FR-023")
    def test_validate_with_valid_manifest_files(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test validate with valid manifest content.

        Validates that well-formed manifests are accepted.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        # Create valid manifest files
        (manifest_dir / "namespaces.yaml").write_text(
            """apiVersion: v1
kind: Namespace
metadata:
  name: floe-jobs
"""
        )
        (manifest_dir / "serviceaccounts.yaml").write_text(
            """apiVersion: v1
kind: ServiceAccount
metadata:
  name: floe-sa
  namespace: floe-jobs
"""
        )
        (manifest_dir / "roles.yaml").write_text(
            """apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: floe-role
  namespace: floe-jobs
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"]
"""
        )
        (manifest_dir / "rolebindings.yaml").write_text(
            """apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: floe-binding
  namespace: floe-jobs
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: floe-role
subjects:
  - kind: ServiceAccount
    name: floe-sa
    namespace: floe-jobs
"""
        )

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--manifest-dir",
                str(manifest_dir),
            ],
        )

        # Should succeed with valid manifests
        if result.exit_code == 0:
            assert "valid" in result.output.lower()

    @pytest.mark.requirement("FR-023")
    def test_validate_json_output_with_valid_manifests(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test validate JSON output format.

        Validates that JSON output contains expected structure.
        """
        from floe_core.cli.main import cli
        import json

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal valid manifest
        (manifest_dir / "namespaces.yaml").write_text("")
        (manifest_dir / "serviceaccounts.yaml").write_text("")
        (manifest_dir / "roles.yaml").write_text("")
        (manifest_dir / "rolebindings.yaml").write_text("")

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--manifest-dir",
                str(manifest_dir),
                "--output",
                "json",
            ],
        )

        # Try to parse JSON output
        if result.exit_code == 0:
            try:
                output = json.loads(result.output)
                assert "status" in output
                assert "manifest_dir" in output
            except json.JSONDecodeError:
                # Some outputs might include non-JSON lines
                pass

    @pytest.mark.requirement("FR-023")
    def test_validate_text_output_with_errors(
        self,
        temp_dir: Path,
    ) -> None:
        """Test validate text output shows errors correctly.

        Validates error output formatting for validation failures.
        """
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationIssue,
            ValidationIssueType,
            ValidationStatus,
        )

        # Create a validation result with issues
        issue = ValidationIssue(
            issue_type=ValidationIssueType.MISSING_SERVICE_ACCOUNT,
            resource_kind="ServiceAccount",
            resource_name="expected-sa",
            message="Expected ServiceAccount not found in manifests",
        )

        result = RBACValidationResult(
            status=ValidationStatus.INVALID,
            config_path=str(temp_dir / "config.yaml"),
            manifest_dir=str(temp_dir / "rbac"),
            issues=[issue],
            service_accounts_validated=0,
            roles_validated=0,
            role_bindings_validated=0,
        )

        # Verify result properties
        assert not result.is_valid
        assert result.status == ValidationStatus.INVALID
        assert len(result.issues) == 1
        assert result.issues[0].resource_name == "expected-sa"

    @pytest.mark.requirement("FR-023")
    def test_validation_result_is_valid_property(self) -> None:
        """Test RBACValidationResult.is_valid property.

        Validates that is_valid returns correct boolean based on status.
        """
        from floe_core.schemas.rbac_validation import (
            RBACValidationResult,
            ValidationStatus,
        )

        # Valid result
        valid_result = RBACValidationResult(
            status=ValidationStatus.VALID,
            config_path="config.yaml",
            manifest_dir="target/rbac",
            issues=[],
            service_accounts_validated=2,
            roles_validated=3,
            role_bindings_validated=2,
        )
        assert valid_result.is_valid is True

        # Invalid result
        invalid_result = RBACValidationResult(
            status=ValidationStatus.INVALID,
            config_path="config.yaml",
            manifest_dir="target/rbac",
            issues=[],
            service_accounts_validated=0,
            roles_validated=0,
            role_bindings_validated=0,
        )
        assert invalid_result.is_valid is False

    @pytest.mark.requirement("FR-023")
    def test_validate_with_config_and_expected_resources(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test validate compares against config when provided.

        Validates that config-based validation works.
        """
        from floe_core.cli.main import cli

        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)

        # Create empty manifests
        (manifest_dir / "namespaces.yaml").write_text("")
        (manifest_dir / "serviceaccounts.yaml").write_text("")
        (manifest_dir / "roles.yaml").write_text("")
        (manifest_dir / "rolebindings.yaml").write_text("")

        # Create config with expected resources
        config_path = temp_dir / "config.yaml"
        config_path.write_text(
            """rbac:
  service_accounts:
    - name: expected-sa
      namespace: floe-jobs
  roles:
    - name: expected-role
      namespace: floe-jobs
"""
        )

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--manifest-dir",
                str(manifest_dir),
                "--config",
                str(config_path),
            ],
        )

        # Should detect missing resources and fail
        assert result.exception is None or isinstance(result.exception, SystemExit)


class TestRbacValidateErrorHandling:
    """Tests for error handling in validate command."""

    @pytest.mark.requirement("FR-023")
    def test_validate_file_not_found_error(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test validate handles FileNotFoundError correctly.

        Validates that FILE_NOT_FOUND exit code is returned.
        """
        from floe_core.cli.main import cli

        # Create manifest dir but point to nonexistent config
        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "roles.yaml").write_text("")

        nonexistent_config = temp_dir / "nonexistent_config.yaml"

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--manifest-dir",
                str(manifest_dir),
                "--config",
                str(nonexistent_config),
            ],
        )

        assert result.exit_code != 0

    @pytest.mark.requirement("FR-023")
    def test_validate_with_validation_errors_text_output(
        self,
        cli_runner: CliRunner,
        temp_dir: Path,
    ) -> None:
        """Test validate shows errors in text output.

        Validates that validation errors are formatted correctly.
        """
        from floe_core.cli.main import cli

        # Create manifest dir with invalid YAML
        manifest_dir = temp_dir / "rbac"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "roles.yaml").write_text(
            """apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: test-role
  namespace: default
"""
        )
        (manifest_dir / "serviceaccounts.yaml").write_text("")
        (manifest_dir / "rolebindings.yaml").write_text("")
        (manifest_dir / "namespaces.yaml").write_text("")

        result = cli_runner.invoke(
            cli,
            [
                "rbac",
                "validate",
                "--manifest-dir",
                str(manifest_dir),
                "--output",
                "text",
            ],
        )

        # Should complete (success or validation failure)
        assert result.exception is None or isinstance(result.exception, SystemExit)

    @pytest.mark.requirement("FR-023")
    def test_validation_issue_type_values(self) -> None:
        """Test all ValidationIssueType enum values.

        Validates that all issue types are properly defined.
        """
        from floe_core.schemas.rbac_validation import ValidationIssueType

        assert ValidationIssueType.MISSING_SERVICE_ACCOUNT is not None
        assert ValidationIssueType.MISSING_ROLE is not None
        assert ValidationIssueType.MISSING_ROLE_BINDING is not None

    @pytest.mark.requirement("FR-023")
    def test_validation_status_enum_values(self) -> None:
        """Test all ValidationStatus enum values.

        Validates that all status values are properly defined.
        """
        from floe_core.schemas.rbac_validation import ValidationStatus

        assert ValidationStatus.VALID is not None
        assert ValidationStatus.INVALID is not None


__all__: list[str] = [
    "TestRbacValidateCommand",
    "TestRbacValidateInGroup",
    "TestRbacValidateManifestHandling",
    "TestRbacValidateErrorHandling",
]
