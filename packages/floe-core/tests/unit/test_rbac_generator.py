"""Unit tests for RBAC generator validation functions.

Tests the validate_manifest, validate_all_manifests functions and
GenerationResult class.

Task: T042
User Story: US4 - RBAC Manifest Generation
Requirements: FR-051, FR-053
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


class TestValidateManifest:
    """Unit tests for validate_manifest function."""

    @pytest.mark.requirement("FR-051")
    def test_validate_valid_manifest(self) -> None:
        """Test valid manifest returns no errors."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "test-sa", "namespace": "default"},
        }

        errors = validate_manifest(manifest)

        assert errors == []

    @pytest.mark.requirement("FR-051")
    def test_validate_missing_api_version(self) -> None:
        """Test manifest missing apiVersion reports error."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {
            "kind": "ServiceAccount",
            "metadata": {"name": "test-sa"},
        }

        errors = validate_manifest(manifest)

        assert any("apiVersion" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_missing_kind(self) -> None:
        """Test manifest missing kind reports error."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "metadata": {"name": "test-sa"},
        }

        errors = validate_manifest(manifest)

        assert any("kind" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_missing_metadata(self) -> None:
        """Test manifest missing metadata reports error."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
        }

        errors = validate_manifest(manifest)

        assert any("metadata" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_unknown_kind(self) -> None:
        """Test manifest with unknown kind reports error."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "UnknownKind",
            "metadata": {"name": "test"},
        }

        errors = validate_manifest(manifest)

        assert any("Unknown kind" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_metadata_missing_name(self) -> None:
        """Test manifest with metadata missing name reports error."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"namespace": "default"},
        }

        errors = validate_manifest(manifest)

        assert any("metadata.name" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_metadata_not_dict(self) -> None:
        """Test manifest with non-dict metadata reports error."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": "invalid-metadata",
        }

        errors = validate_manifest(manifest)

        assert any("metadata must be a dictionary" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_api_version_not_string(self) -> None:
        """Test manifest with non-string apiVersion reports error."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {
            "apiVersion": 123,
            "kind": "ServiceAccount",
            "metadata": {"name": "test"},
        }

        errors = validate_manifest(manifest)

        assert any("apiVersion must be a string" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_all_valid_rbac_kinds(self) -> None:
        """Test all valid RBAC kinds pass validation."""
        from floe_core.rbac.generator import VALID_RBAC_KINDS, validate_manifest

        for kind in VALID_RBAC_KINDS:
            core_kinds = ("ServiceAccount", "Namespace")
            api_version = "v1" if kind in core_kinds else "rbac.authorization.k8s.io/v1"
            manifest: dict[str, Any] = {
                "apiVersion": api_version,
                "kind": kind,
                "metadata": {"name": f"test-{kind.lower()}"},
            }

            errors = validate_manifest(manifest)
            kind_errors = [e for e in errors if "kind" in e.lower()]
            assert kind_errors == [], f"Kind {kind} should be valid but got: {kind_errors}"

    @pytest.mark.requirement("FR-051")
    def test_validate_multiple_errors(self) -> None:
        """Test manifest with multiple issues reports all errors."""
        from floe_core.rbac.generator import validate_manifest

        manifest: dict[str, Any] = {}

        errors = validate_manifest(manifest)

        # Should have errors for all required fields
        assert len(errors) >= 3  # apiVersion, kind, metadata


class TestValidateAllManifests:
    """Unit tests for validate_all_manifests function."""

    @pytest.mark.requirement("FR-051")
    def test_validate_all_valid_manifests(self) -> None:
        """Test all valid manifests returns True."""
        from floe_core.rbac.generator import validate_all_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "test-sa"},
                },
            ],
            "roles.yaml": [
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "Role",
                    "metadata": {"name": "test-role"},
                },
            ],
        }

        is_valid, errors = validate_all_manifests(manifests)

        assert is_valid is True
        assert errors == []

    @pytest.mark.requirement("FR-051")
    def test_validate_all_with_invalid_manifest(self) -> None:
        """Test invalid manifest returns False with errors."""
        from floe_core.rbac.generator import validate_all_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "test-sa"},
                },
            ],
            "roles.yaml": [
                {
                    "kind": "Role",  # Missing apiVersion
                    "metadata": {"name": "test-role"},
                },
            ],
        }

        is_valid, errors = validate_all_manifests(manifests)

        assert is_valid is False
        assert len(errors) > 0

    @pytest.mark.requirement("FR-051")
    def test_validate_all_error_includes_file_context(self) -> None:
        """Test error messages include file name context."""
        from floe_core.rbac.generator import validate_all_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "roles.yaml": [
                {
                    "kind": "Role",  # Missing apiVersion
                    "metadata": {"name": "test-role"},
                },
            ],
        }

        is_valid, errors = validate_all_manifests(manifests)

        assert is_valid is False
        assert any("roles.yaml" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_all_error_includes_index(self) -> None:
        """Test error messages include document index."""
        from floe_core.rbac.generator import validate_all_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "roles.yaml": [
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "Role",
                    "metadata": {"name": "good-role"},
                },
                {
                    "kind": "Role",  # Missing apiVersion (index 1)
                    "metadata": {"name": "bad-role"},
                },
            ],
        }

        is_valid, errors = validate_all_manifests(manifests)

        assert is_valid is False
        assert any("[1]" in e for e in errors)

    @pytest.mark.requirement("FR-051")
    def test_validate_all_empty_manifests(self) -> None:
        """Test empty manifests dict is valid."""
        from floe_core.rbac.generator import validate_all_manifests

        manifests: dict[str, list[dict[str, Any]]] = {}

        is_valid, errors = validate_all_manifests(manifests)

        assert is_valid is True
        assert errors == []

    @pytest.mark.requirement("FR-051")
    def test_validate_all_empty_file_lists(self) -> None:
        """Test empty file lists are valid."""
        from floe_core.rbac.generator import validate_all_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [],
            "roles.yaml": [],
        }

        is_valid, errors = validate_all_manifests(manifests)

        assert is_valid is True
        assert errors == []


class TestGenerationResult:
    """Unit tests for GenerationResult class."""

    @pytest.mark.requirement("FR-053")
    def test_generation_result_str_success(self) -> None:
        """Test __str__ shows SUCCESS for successful result."""
        from floe_core.rbac.result import GenerationResult

        result = GenerationResult(
            success=True,
            service_accounts=2,
            roles=1,
            role_bindings=1,
            namespaces=1,
        )

        output = str(result)

        assert "SUCCESS" in output
        assert "ServiceAccounts: 2" in output
        assert "Roles: 1" in output
        assert "RoleBindings: 1" in output
        assert "Namespaces: 1" in output

    @pytest.mark.requirement("FR-053")
    def test_generation_result_str_failed(self) -> None:
        """Test __str__ shows FAILED for failed result."""
        from floe_core.rbac.result import GenerationResult

        result = GenerationResult(
            success=False,
            errors=["Error 1", "Error 2"],
        )

        output = str(result)

        assert "FAILED" in output
        assert "Errors: 2" in output

    @pytest.mark.requirement("FR-053")
    def test_generation_result_str_with_warnings(self) -> None:
        """Test __str__ includes warnings count."""
        from floe_core.rbac.result import GenerationResult

        result = GenerationResult(
            success=True,
            warnings=["Warning 1", "Warning 2", "Warning 3"],
        )

        output = str(result)

        assert "Warnings: 3" in output

    @pytest.mark.requirement("FR-053")
    def test_generation_result_str_files_count(self) -> None:
        """Test __str__ shows files count."""
        from floe_core.rbac.result import GenerationResult

        result = GenerationResult(
            success=True,
            files_generated=[
                Path("serviceaccounts.yaml"),
                Path("roles.yaml"),
                Path("rolebindings.yaml"),
            ],
        )

        output = str(result)

        assert "Files: 3" in output

    @pytest.mark.requirement("FR-053")
    def test_generation_result_default_values(self) -> None:
        """Test GenerationResult has correct default values."""
        from floe_core.rbac.result import GenerationResult

        result = GenerationResult(success=True)

        assert result.files_generated == []
        assert result.service_accounts == 0
        assert result.roles == 0
        assert result.role_bindings == 0
        assert result.namespaces == 0
        assert result.warnings == []
        assert result.errors == []

    @pytest.mark.requirement("FR-053")
    def test_generation_result_str_no_warnings_or_errors(self) -> None:
        """Test __str__ omits warnings/errors sections when empty."""
        from floe_core.rbac.result import GenerationResult

        result = GenerationResult(success=True)

        output = str(result)

        assert "Warnings" not in output
        assert "Errors" not in output
