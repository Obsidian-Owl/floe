"""Unit tests for network validate CLI command.

Task ID: T070
Phase: 4 - Network and Pod Security
User Story: US7 - Network Policy Management
Requirements: FR-081

This module tests the `floe network validate` command which validates
NetworkPolicy manifests against schema and checks for required labels.

Test Coverage:
- Command option parsing (--manifest-dir, --config, --strict, --debug)
- YAML manifest loading (single/multi-doc, empty, invalid)
- NetworkPolicy schema validation (apiVersion, kind, metadata, spec)
- Required label validation (app.kubernetes.io/managed-by: floe)
- Directory manifest loading (.yaml and .yml extensions)
- Command execution with various scenarios (valid, invalid, strict mode)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml
from click.testing import CliRunner

from floe_core.cli.network.validate import (
    _load_all_manifests,
    _load_manifest_file,
    _validate_network_policy_schema,
    _validate_required_labels,
    validate_command,
)
from floe_core.cli.utils import ExitCode

if TYPE_CHECKING:
    pass


# =============================================================================
# TestLoadManifestFile - Test YAML manifest loading
# =============================================================================


class TestLoadManifestFile:
    """Test _load_manifest_file function."""

    @pytest.mark.requirement("FR-081")
    def test_loads_valid_yaml(
        self,
        tmp_path: Path,
        valid_network_policy_yaml: str,
    ) -> None:
        """Test loading a valid NetworkPolicy YAML file."""
        yaml_file = tmp_path / "policy.yaml"
        yaml_file.write_text(valid_network_policy_yaml)

        result = _load_manifest_file(yaml_file)

        assert len(result) == 1
        assert result[0]["kind"] == "NetworkPolicy"
        assert result[0]["apiVersion"] == "networking.k8s.io/v1"
        assert result[0]["metadata"]["name"] == "default-deny-all"

    @pytest.mark.requirement("FR-081")
    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        """Test that empty file returns empty list."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        result = _load_manifest_file(yaml_file)

        assert result == []

    @pytest.mark.requirement("FR-081")
    def test_file_not_found_returns_empty_list(self, tmp_path: Path) -> None:
        """Test that non-existent file returns empty list."""
        yaml_file = tmp_path / "nonexistent.yaml"

        result = _load_manifest_file(yaml_file)

        assert result == []

    @pytest.mark.requirement("FR-081")
    def test_multi_document_yaml(
        self,
        tmp_path: Path,
        multi_doc_network_policy_yaml: str,
    ) -> None:
        """Test loading multi-document YAML file."""
        yaml_file = tmp_path / "multi.yaml"
        yaml_file.write_text(multi_doc_network_policy_yaml)

        result = _load_manifest_file(yaml_file)

        assert len(result) == 2
        assert result[0]["metadata"]["name"] == "default-deny-all"
        assert result[1]["metadata"]["name"] == "allow-dns-egress"

    @pytest.mark.requirement("FR-081")
    def test_null_documents_filtered(self, tmp_path: Path, null_doc_yaml: str) -> None:
        """Test that null documents are filtered out."""
        yaml_file = tmp_path / "null.yaml"
        yaml_file.write_text(null_doc_yaml)

        result = _load_manifest_file(yaml_file)

        assert result == []

    @pytest.mark.requirement("FR-081")
    def test_invalid_structure_raises_valueerror(self, tmp_path: Path) -> None:
        """Test that non-dict manifest raises ValueError."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("- item1\n- item2\n")

        with pytest.raises(ValueError, match="expected dict, got list"):
            _load_manifest_file(yaml_file)

    @pytest.mark.requirement("FR-081")
    def test_missing_apiversion_raises_valueerror(self, tmp_path: Path) -> None:
        """Test that manifest missing apiVersion raises ValueError."""
        yaml_file = tmp_path / "no-apiversion.yaml"
        content = """kind: NetworkPolicy
metadata:
  name: test
spec:
  podSelector: {}
"""
        yaml_file.write_text(content)

        with pytest.raises(ValueError, match="Missing apiVersion"):
            _load_manifest_file(yaml_file)

    @pytest.mark.requirement("FR-081")
    def test_missing_kind_raises_valueerror(self, tmp_path: Path) -> None:
        """Test that manifest missing kind raises ValueError."""
        yaml_file = tmp_path / "no-kind.yaml"
        content = """apiVersion: networking.k8s.io/v1
metadata:
  name: test
spec:
  podSelector: {}
"""
        yaml_file.write_text(content)

        with pytest.raises(ValueError, match="Missing kind"):
            _load_manifest_file(yaml_file)


# =============================================================================
# TestValidateNetworkPolicySchema - Test schema validation
# =============================================================================


class TestValidateNetworkPolicySchema:
    """Test _validate_network_policy_schema function."""

    @pytest.mark.requirement("FR-081")
    def test_valid_policy_passes(self, valid_network_policy_yaml: str) -> None:
        """Test that valid NetworkPolicy passes validation."""
        manifest = yaml.safe_load(valid_network_policy_yaml)

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is True
        assert errors == []

    @pytest.mark.requirement("FR-081")
    def test_missing_apiversion_fails(self) -> None:
        """Test that missing apiVersion fails validation."""
        manifest: dict[str, Any] = {
            "kind": "NetworkPolicy",
            "metadata": {"name": "test", "namespace": "default"},
            "spec": {"podSelector": {}},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("apiVersion" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_wrong_apiversion_fails(self) -> None:
        """Test that wrong apiVersion fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "test", "namespace": "default"},
            "spec": {"podSelector": {}},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("Invalid apiVersion" in error for error in errors)
        assert any("networking.k8s.io/v1" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_missing_kind_fails(self) -> None:
        """Test that missing kind fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "metadata": {"name": "test", "namespace": "default"},
            "spec": {"podSelector": {}},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("kind" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_wrong_kind_fails(self) -> None:
        """Test that wrong kind fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "ConfigMap",
            "metadata": {"name": "test", "namespace": "default"},
            "spec": {"podSelector": {}},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("Invalid kind" in error for error in errors)
        assert any("NetworkPolicy" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_missing_metadata_fails(self) -> None:
        """Test that missing metadata fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "spec": {"podSelector": {}},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("metadata" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_missing_metadata_name_fails(self) -> None:
        """Test that missing metadata.name fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"namespace": "default"},
            "spec": {"podSelector": {}},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("metadata.name" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_missing_metadata_namespace_fails(self) -> None:
        """Test that missing metadata.namespace fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "test"},
            "spec": {"podSelector": {}},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("metadata.namespace" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_missing_spec_fails(self) -> None:
        """Test that missing spec fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "test", "namespace": "default"},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("spec" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_missing_podselector_fails(self) -> None:
        """Test that missing spec.podSelector fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "test", "namespace": "default"},
            "spec": {"policyTypes": ["Ingress"]},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("podSelector" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_non_dict_manifest_fails(self) -> None:
        """Test that non-dict manifest fails validation."""
        manifest = ["not", "a", "dict"]  # type: ignore[assignment]

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("must be a dictionary" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_non_dict_metadata_fails(self) -> None:
        """Test that non-dict metadata fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": "not-a-dict",  # type: ignore[dict-item]
            "spec": {"podSelector": {}},
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("metadata must be a dictionary" in error for error in errors)

    @pytest.mark.requirement("FR-081")
    def test_non_dict_spec_fails(self) -> None:
        """Test that non-dict spec fails validation."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "test", "namespace": "default"},
            "spec": "not-a-dict",  # type: ignore[dict-item]
        }

        is_valid, errors = _validate_network_policy_schema(manifest)

        assert is_valid is False
        assert any("spec must be a dictionary" in error for error in errors)


# =============================================================================
# TestValidateRequiredLabels - Test label validation
# =============================================================================


class TestValidateRequiredLabels:
    """Test _validate_required_labels function."""

    @pytest.mark.requirement("FR-081")
    def test_managed_by_floe_passes(self, valid_network_policy_yaml: str) -> None:
        """Test that policy with managed-by: floe label passes."""
        manifest = yaml.safe_load(valid_network_policy_yaml)

        is_valid, warnings = _validate_required_labels(manifest)

        assert is_valid is True
        assert warnings == []

    @pytest.mark.requirement("FR-081")
    def test_missing_managed_by_warns(
        self,
        network_policy_missing_managed_by_label_yaml: str,
    ) -> None:
        """Test that missing managed-by label generates warning."""
        manifest = yaml.safe_load(network_policy_missing_managed_by_label_yaml)

        is_valid, warnings = _validate_required_labels(manifest)

        assert is_valid is False
        assert len(warnings) == 1
        assert "Missing recommended label" in warnings[0]
        assert "app.kubernetes.io/managed-by" in warnings[0]

    @pytest.mark.requirement("FR-081")
    def test_wrong_managed_by_value_warns(
        self,
        network_policy_wrong_managed_by_label_yaml: str,
    ) -> None:
        """Test that wrong managed-by label value generates warning."""
        manifest = yaml.safe_load(network_policy_wrong_managed_by_label_yaml)

        is_valid, warnings = _validate_required_labels(manifest)

        assert is_valid is False
        assert len(warnings) == 1
        assert "should be 'floe'" in warnings[0]
        assert "helm" in warnings[0]


# =============================================================================
# TestLoadAllManifests - Test directory manifest loading
# =============================================================================


class TestLoadAllManifests:
    """Test _load_all_manifests function."""

    @pytest.mark.requirement("FR-081")
    def test_loads_yaml_files(self, manifest_dir_with_policies: Path) -> None:
        """Test loading .yaml files from directory."""
        manifests = _load_all_manifests(manifest_dir_with_policies)

        assert len(manifests) == 2
        names = {m["metadata"]["name"] for m in manifests}
        assert "default-deny-all" in names
        assert "allow-platform-egress" in names

    @pytest.mark.requirement("FR-081")
    def test_loads_yml_files(self, manifest_dir_with_yml_extension: Path) -> None:
        """Test loading .yml files from directory."""
        manifests = _load_all_manifests(manifest_dir_with_yml_extension)

        assert len(manifests) == 1
        assert manifests[0]["metadata"]["name"] == "default-deny-all"

    @pytest.mark.requirement("FR-081")
    def test_empty_directory_returns_empty(self, manifest_dir_empty: Path) -> None:
        """Test that empty directory returns empty list."""
        manifests = _load_all_manifests(manifest_dir_empty)

        assert manifests == []

    @pytest.mark.requirement("FR-081")
    def test_directory_not_found_returns_empty(self, tmp_path: Path) -> None:
        """Test that non-existent directory returns empty list."""
        nonexistent_dir = tmp_path / "nonexistent"

        manifests = _load_all_manifests(nonexistent_dir)

        assert manifests == []

    @pytest.mark.requirement("FR-081")
    def test_loads_both_yaml_and_yml(
        self,
        tmp_path: Path,
        valid_network_policy_yaml: str,
    ) -> None:
        """Test loading both .yaml and .yml files from same directory."""
        manifest_dir = tmp_path / "mixed"
        manifest_dir.mkdir()

        (manifest_dir / "policy1.yaml").write_text(valid_network_policy_yaml)
        (manifest_dir / "policy2.yml").write_text(
            valid_network_policy_yaml.replace("default-deny-all", "policy2")
        )

        manifests = _load_all_manifests(manifest_dir)

        assert len(manifests) == 2
        names = {m["metadata"]["name"] for m in manifests}
        assert "default-deny-all" in names
        assert "policy2" in names


# =============================================================================
# TestValidateCommandOptions - Test CLI option parsing
# =============================================================================


class TestValidateCommandOptions:
    """Test validate_command CLI option parsing."""

    @pytest.mark.requirement("FR-081")
    def test_accepts_manifest_dir_option(
        self,
        cli_runner: CliRunner,
        manifest_dir_with_policies: Path,
    ) -> None:
        """Test that --manifest-dir option is accepted."""
        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir_with_policies)],
        )

        # Should succeed (exit code 0)
        assert result.exit_code == ExitCode.SUCCESS

    @pytest.mark.requirement("FR-081")
    def test_manifest_dir_is_required(self, cli_runner: CliRunner) -> None:
        """Test that --manifest-dir is required."""
        result = cli_runner.invoke(validate_command, [])

        # Should fail with usage error
        assert result.exit_code == ExitCode.USAGE_ERROR
        assert (
            "manifest-dir" in result.output.lower()
            or "missing" in result.output.lower()
        )

    @pytest.mark.requirement("FR-081")
    def test_accepts_config_option(
        self,
        cli_runner: CliRunner,
        manifest_dir_with_policies: Path,
        sample_manifest_yaml_with_network: Path,
    ) -> None:
        """Test that --config option is accepted."""
        result = cli_runner.invoke(
            validate_command,
            [
                "--manifest-dir",
                str(manifest_dir_with_policies),
                "--config",
                str(sample_manifest_yaml_with_network),
            ],
        )

        # Should succeed
        assert result.exit_code == ExitCode.SUCCESS
        assert "Against configuration" in result.output

    @pytest.mark.requirement("FR-081")
    def test_accepts_strict_flag(
        self,
        cli_runner: CliRunner,
        manifest_dir_with_policies: Path,
    ) -> None:
        """Test that --strict flag is accepted."""
        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir_with_policies), "--strict"],
        )

        # Should succeed (no warnings in valid manifests)
        assert result.exit_code == ExitCode.SUCCESS

    @pytest.mark.requirement("FR-081")
    def test_shows_help(self, cli_runner: CliRunner) -> None:
        """Test that --help shows command help."""
        result = cli_runner.invoke(validate_command, ["--help"])

        assert result.exit_code == ExitCode.SUCCESS
        assert "validate" in result.output.lower()
        assert "NetworkPolicy" in result.output
        assert "--manifest-dir" in result.output


# =============================================================================
# TestValidateCommandExecution - Test command execution scenarios
# =============================================================================


class TestValidateCommandExecution:
    """Test validate_command execution with various scenarios."""

    @pytest.mark.requirement("FR-081")
    def test_valid_manifests_success(
        self,
        cli_runner: CliRunner,
        manifest_dir_with_policies: Path,
    ) -> None:
        """Test validation succeeds with valid manifests."""
        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir_with_policies)],
        )

        assert result.exit_code == ExitCode.SUCCESS
        assert "Validation complete" in result.output
        assert "2/2" in result.output or "2 manifest" in result.output

    @pytest.mark.requirement("FR-081")
    def test_invalid_manifests_fail(
        self,
        cli_runner: CliRunner,
        manifest_dir_with_invalid_policies: Path,
    ) -> None:
        """Test validation fails with invalid manifests.

        Note: ValueError from _load_manifest_file is caught by general
        exception handler, so exit code is GENERAL_ERROR not VALIDATION_ERROR.
        """
        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir_with_invalid_policies)],
        )

        assert result.exit_code == ExitCode.GENERAL_ERROR
        assert "Error:" in result.output
        assert "Validation failed" in result.output

    @pytest.mark.requirement("FR-081")
    def test_strict_mode_fails_on_warnings(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
        network_policy_missing_managed_by_label_yaml: str,
    ) -> None:
        """Test that strict mode fails on warnings."""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        (manifest_dir / "policy.yaml").write_text(
            network_policy_missing_managed_by_label_yaml
        )

        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir), "--strict"],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "Warning:" in result.output
        assert "Validation failed" in result.output

    @pytest.mark.requirement("FR-081")
    def test_non_strict_mode_passes_with_warnings(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
        network_policy_missing_managed_by_label_yaml: str,
    ) -> None:
        """Test that non-strict mode passes with warnings."""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        (manifest_dir / "policy.yaml").write_text(
            network_policy_missing_managed_by_label_yaml
        )

        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir)],
        )

        assert result.exit_code == ExitCode.SUCCESS
        assert "Warning:" in result.output
        assert "Validation complete" in result.output
        assert "1 warning" in result.output

    @pytest.mark.requirement("FR-081")
    def test_no_manifests_found_success(
        self,
        cli_runner: CliRunner,
        manifest_dir_empty: Path,
    ) -> None:
        """Test that empty directory succeeds with informational message."""
        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir_empty)],
        )

        assert result.exit_code == ExitCode.SUCCESS
        assert "No NetworkPolicy manifests found" in result.output
        assert "0 manifests validated" in result.output

    @pytest.mark.requirement("FR-081")
    def test_validation_with_schema_errors_only(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test validation with schema errors (no label validation)."""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()

        # Create manifest with schema errors (missing namespace)
        invalid_yaml = """apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: test-policy
  labels:
    app.kubernetes.io/managed-by: floe
spec:
  podSelector: {}
"""
        (manifest_dir / "invalid.yaml").write_text(invalid_yaml)

        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir)],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "Error:" in result.output
        assert "metadata.namespace" in result.output

    @pytest.mark.requirement("FR-081")
    def test_validation_with_mixed_valid_invalid(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
        valid_network_policy_yaml: str,
    ) -> None:
        """Test validation with mix of valid and invalid manifests."""
        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()

        # One valid
        (manifest_dir / "valid.yaml").write_text(valid_network_policy_yaml)

        # One invalid (missing namespace)
        invalid_yaml = """apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: invalid-policy
  labels:
    app.kubernetes.io/managed-by: floe
spec:
  podSelector: {}
"""
        (manifest_dir / "invalid.yaml").write_text(invalid_yaml)

        result = cli_runner.invoke(
            validate_command,
            ["--manifest-dir", str(manifest_dir)],
        )

        assert result.exit_code == ExitCode.VALIDATION_ERROR
        assert "Error:" in result.output
        assert "1 issue(s)" in result.output or "1 error(s)" in result.output


__all__: list[str] = [
    "TestLoadManifestFile",
    "TestValidateNetworkPolicySchema",
    "TestValidateRequiredLabels",
    "TestLoadAllManifests",
    "TestValidateCommandOptions",
    "TestValidateCommandExecution",
]
