"""Unit tests for RBAC CLI helper functions.

Tests the internal helper functions used by CLI commands including
_write_manifests, _load_manifests_from_dir, _validate_resource_structure,
and _print_validation_result.

Task: T059, T060
User Story: US6 - RBAC Audit and Validation
Requirements: FR-060, FR-061
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


class TestWriteManifests:
    """Unit tests for _write_manifests helper function."""

    @pytest.mark.requirement("FR-060")
    def test_write_manifests_creates_files(self, tmp_path: Path) -> None:
        """Test _write_manifests creates expected files."""
        from floe_cli.main import _write_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "Namespace": [
                {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {"name": "test-ns"},
                },
            ],
            "ServiceAccount": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "test-sa", "namespace": "test-ns"},
                },
            ],
        }

        _write_manifests(tmp_path, manifests)

        assert (tmp_path / "namespaces.yaml").exists()
        assert (tmp_path / "serviceaccounts.yaml").exists()

    @pytest.mark.requirement("FR-060")
    def test_write_manifests_content_correct(self, tmp_path: Path) -> None:
        """Test written manifest content is correct YAML."""
        from floe_cli.main import _write_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "Role": [
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "Role",
                    "metadata": {"name": "test-role", "namespace": "default"},
                    "rules": [{"verbs": ["get"], "resources": ["secrets"]}],
                },
            ],
        }

        _write_manifests(tmp_path, manifests)

        content = (tmp_path / "roles.yaml").read_text()
        docs = list(yaml.safe_load_all(content))

        assert len(docs) == 1
        assert docs[0]["metadata"]["name"] == "test-role"
        assert docs[0]["rules"][0]["verbs"] == ["get"]

    @pytest.mark.requirement("FR-060")
    def test_write_manifests_skips_empty(self, tmp_path: Path) -> None:
        """Test _write_manifests skips empty resource types."""
        from floe_cli.main import _write_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "ServiceAccount": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "test-sa"},
                },
            ],
            "Role": [],  # Empty
        }

        _write_manifests(tmp_path, manifests)

        assert (tmp_path / "serviceaccounts.yaml").exists()
        assert not (tmp_path / "roles.yaml").exists()

    @pytest.mark.requirement("FR-060")
    def test_write_manifests_multiple_per_file(self, tmp_path: Path) -> None:
        """Test _write_manifests handles multiple resources per file."""
        from floe_cli.main import _write_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "ServiceAccount": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "sa-1"},
                },
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "sa-2"},
                },
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "sa-3"},
                },
            ],
        }

        _write_manifests(tmp_path, manifests)

        content = (tmp_path / "serviceaccounts.yaml").read_text()
        docs = list(yaml.safe_load_all(content))

        assert len(docs) == 3
        names = [d["metadata"]["name"] for d in docs]
        assert names == ["sa-1", "sa-2", "sa-3"]


class TestLoadManifestsFromDir:
    """Unit tests for _load_manifests_from_dir helper function."""

    @pytest.mark.requirement("FR-061")
    def test_load_manifests_from_dir(self, tmp_path: Path) -> None:
        """Test _load_manifests_from_dir loads YAML files."""
        from floe_cli.main import _load_manifests_from_dir

        # Create test YAML files
        (tmp_path / "serviceaccounts.yaml").write_text(
            yaml.dump_all([
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "test-sa"},
                },
            ])
        )
        (tmp_path / "roles.yaml").write_text(
            yaml.dump_all([
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "Role",
                    "metadata": {"name": "test-role"},
                },
            ])
        )

        resources = _load_manifests_from_dir(tmp_path)

        assert "ServiceAccount" in resources
        assert "Role" in resources
        assert len(resources["ServiceAccount"]) == 1
        assert len(resources["Role"]) == 1
        assert resources["ServiceAccount"][0]["metadata"]["name"] == "test-sa"

    @pytest.mark.requirement("FR-061")
    def test_load_manifests_multiple_docs(self, tmp_path: Path) -> None:
        """Test _load_manifests_from_dir handles multi-document YAML."""
        from floe_cli.main import _load_manifests_from_dir

        content = yaml.dump_all([
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa-1"},
            },
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": "sa-2"},
            },
        ])
        (tmp_path / "serviceaccounts.yaml").write_text(content)

        resources = _load_manifests_from_dir(tmp_path)

        assert len(resources["ServiceAccount"]) == 2

    @pytest.mark.requirement("FR-061")
    def test_load_manifests_empty_dir(self, tmp_path: Path) -> None:
        """Test _load_manifests_from_dir handles empty directory."""
        from floe_cli.main import _load_manifests_from_dir

        resources = _load_manifests_from_dir(tmp_path)

        assert resources == {}

    @pytest.mark.requirement("FR-061")
    def test_load_manifests_skips_non_yaml(self, tmp_path: Path) -> None:
        """Test _load_manifests_from_dir skips non-YAML files."""
        from floe_cli.main import _load_manifests_from_dir

        (tmp_path / "readme.txt").write_text("Not a YAML file")
        (tmp_path / "serviceaccounts.yaml").write_text(
            yaml.dump({"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "sa"}})
        )

        resources = _load_manifests_from_dir(tmp_path)

        assert "ServiceAccount" in resources
        # Should only find YAML files
        assert len(resources) == 1


class TestValidateResourceStructure:
    """Unit tests for _validate_resource_structure helper function."""

    @pytest.mark.requirement("FR-061")
    def test_validate_valid_resource(self) -> None:
        """Test validation of a valid resource returns no issues."""
        from floe_cli.main import _validate_resource_structure

        resource: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "test-sa", "namespace": "default"},
        }

        issues = _validate_resource_structure(resource, "ServiceAccount")

        assert issues == []

    @pytest.mark.requirement("FR-061")
    def test_validate_missing_api_version(self) -> None:
        """Test validation detects missing apiVersion."""
        from floe_cli.main import _validate_resource_structure

        resource: dict[str, Any] = {
            "kind": "ServiceAccount",
            "metadata": {"name": "test-sa"},
        }

        issues = _validate_resource_structure(resource, "ServiceAccount")

        assert len(issues) == 1
        assert "apiVersion" in issues[0].message

    @pytest.mark.requirement("FR-061")
    def test_validate_missing_metadata(self) -> None:
        """Test validation detects missing metadata."""
        from floe_cli.main import _validate_resource_structure

        resource: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
        }

        issues = _validate_resource_structure(resource, "ServiceAccount")

        assert len(issues) == 1
        assert "metadata" in issues[0].message

    @pytest.mark.requirement("FR-061")
    def test_validate_missing_metadata_name(self) -> None:
        """Test validation detects missing metadata.name."""
        from floe_cli.main import _validate_resource_structure

        resource: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"namespace": "default"},  # name is missing
        }

        issues = _validate_resource_structure(resource, "ServiceAccount")

        assert len(issues) == 1
        assert "metadata.name" in issues[0].message

    @pytest.mark.requirement("FR-061")
    def test_validate_multiple_issues(self) -> None:
        """Test validation reports multiple issues."""
        from floe_cli.main import _validate_resource_structure

        resource: dict[str, Any] = {
            "kind": "Role",  # Missing apiVersion and metadata
        }

        issues = _validate_resource_structure(resource, "Role")

        assert len(issues) == 2


class TestPrintValidationResult:
    """Unit tests for _print_validation_result helper function."""

    @pytest.mark.requirement("FR-061")
    def test_print_valid_result(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test printing valid result shows success."""
        from floe_cli.commands.rbac import RBACValidationResult, ValidationStatus
        from floe_cli.main import _print_validation_result

        result = RBACValidationResult(
            status=ValidationStatus.VALID,
            config_path="/path/to/config",
            manifest_dir="/path/to/manifests",
            service_accounts_validated=2,
            roles_validated=3,
            role_bindings_validated=2,
            namespaces_validated=1,
        )

        _print_validation_result(result)

        captured = capsys.readouterr()
        assert "PASSED" in captured.out
        assert "Service Accounts: 2" in captured.out
        assert "Roles: 3" in captured.out

    @pytest.mark.requirement("FR-061")
    def test_print_invalid_result_with_issues(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test printing invalid result shows issues."""
        from floe_cli.commands.rbac import (
            RBACValidationResult,
            ValidationIssue,
            ValidationIssueType,
            ValidationStatus,
        )
        from floe_cli.main import _print_validation_result

        issue = ValidationIssue(
            issue_type=ValidationIssueType.MISSING_ROLE,
            resource_kind="Role",
            resource_name="missing-role",
            message="Role not found in manifests",
        )

        result = RBACValidationResult(
            status=ValidationStatus.INVALID,
            config_path="/path/to/config",
            manifest_dir="/path/to/manifests",
            issues=[issue],
        )

        _print_validation_result(result)

        captured = capsys.readouterr()
        assert "FAILED" in captured.out
        assert "Issues found" in captured.out
        assert "missing-role" in captured.out
