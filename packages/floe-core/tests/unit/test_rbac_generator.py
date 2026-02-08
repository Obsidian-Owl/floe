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


class TestGetTracer:
    """Unit tests for _get_tracer helper function in generator module."""

    @pytest.mark.requirement("FR-050")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test _get_tracer returns a valid tracer for tracing generation."""
        from floe_core.rbac.generator import _get_tracer

        tracer = _get_tracer()

        assert tracer is not None
        # Verify it has the start_as_current_span method
        assert hasattr(tracer, "start_as_current_span")

    @pytest.mark.requirement("FR-050")
    def test_get_tracer_can_start_span(self) -> None:
        """Test _get_tracer returns a tracer that can create spans."""
        from floe_core.rbac.generator import _get_tracer

        tracer = _get_tracer()

        # Should be able to create a span without error
        with tracer.start_as_current_span("test_span") as span:
            assert span is not None


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
            assert (
                kind_errors == []
            ), f"Kind {kind} should be valid but got: {kind_errors}"

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


class TestAggregatePermissions:
    """Unit tests for aggregate_permissions function."""

    @pytest.mark.requirement("FR-052")
    def test_aggregate_permissions_empty_list(self) -> None:
        """Test aggregate_permissions returns empty list for empty input."""
        from floe_core.rbac.generator import aggregate_permissions

        rules = aggregate_permissions([])

        assert rules == []

    @pytest.mark.requirement("FR-052")
    def test_aggregate_permissions_single_secret(self) -> None:
        """Test aggregate_permissions with single secret reference."""
        from floe_core.rbac.generator import aggregate_permissions

        rules = aggregate_permissions(["snowflake-creds"])

        assert len(rules) == 1
        assert rules[0].verbs == ["get"]
        assert rules[0].resources == ["secrets"]
        assert rules[0].resource_names == ["snowflake-creds"]

    @pytest.mark.requirement("FR-052")
    def test_aggregate_permissions_multiple_secrets(self) -> None:
        """Test aggregate_permissions combines multiple secrets into one rule."""
        from floe_core.rbac.generator import aggregate_permissions

        rules = aggregate_permissions(["secret-a", "secret-b", "secret-c"])

        assert len(rules) == 1
        assert rules[0].resource_names == ["secret-a", "secret-b", "secret-c"]

    @pytest.mark.requirement("FR-052")
    def test_aggregate_permissions_deduplicates(self) -> None:
        """Test aggregate_permissions removes duplicate secret references."""
        from floe_core.rbac.generator import aggregate_permissions

        rules = aggregate_permissions(["secret-a", "secret-b", "secret-a", "secret-b"])

        assert len(rules) == 1
        assert rules[0].resource_names == ["secret-a", "secret-b"]

    @pytest.mark.requirement("FR-052")
    def test_aggregate_permissions_strips_whitespace(self) -> None:
        """Test aggregate_permissions strips whitespace from secret names."""
        from floe_core.rbac.generator import aggregate_permissions

        rules = aggregate_permissions(["  secret-a  ", "secret-b\t"])

        assert len(rules) == 1
        assert rules[0].resource_names == ["secret-a", "secret-b"]


class TestValidateSecretReferences:
    """Unit tests for validate_secret_references function."""

    @pytest.mark.requirement("FR-073")
    def test_validate_secret_references_empty(self) -> None:
        """Test validate_secret_references with empty references."""
        from floe_core.rbac.generator import validate_secret_references

        is_valid, errors = validate_secret_references([], {"secret-a"})

        assert is_valid is True
        assert errors == []

    @pytest.mark.requirement("FR-073")
    def test_validate_secret_references_all_permitted(self) -> None:
        """Test validate_secret_references with all secrets permitted."""
        from floe_core.rbac.generator import validate_secret_references

        is_valid, errors = validate_secret_references(
            ["secret-a", "secret-b"],
            {"secret-a", "secret-b", "secret-c"},
        )

        assert is_valid is True
        assert errors == []

    @pytest.mark.requirement("FR-073")
    def test_validate_secret_references_missing(self) -> None:
        """Test validate_secret_references detects missing permissions."""
        from floe_core.rbac.generator import validate_secret_references

        is_valid, errors = validate_secret_references(
            ["secret-a", "secret-b"],
            {"secret-a"},
        )

        assert is_valid is False
        assert len(errors) == 1
        assert "secret-b" in errors[0]

    @pytest.mark.requirement("FR-073")
    def test_validate_secret_references_multiple_missing(self) -> None:
        """Test validate_secret_references reports all missing secrets."""
        from floe_core.rbac.generator import validate_secret_references

        is_valid, errors = validate_secret_references(
            ["secret-a", "secret-b", "secret-c"],
            {"secret-a"},
        )

        assert is_valid is False
        assert len(errors) == 2  # secret-b and secret-c missing

    @pytest.mark.requirement("FR-073")
    def test_validate_secret_references_strips_whitespace(self) -> None:
        """Test validate_secret_references strips whitespace from names."""
        from floe_core.rbac.generator import validate_secret_references

        is_valid, errors = validate_secret_references(
            ["  secret-a  ", "secret-b"],
            {"secret-a", "secret-b"},
        )

        assert is_valid is True
        assert errors == []


class TestWriteManifests:
    """Unit tests for write_manifests function."""

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_creates_directory(self, tmp_path: Path) -> None:
        """Test write_manifests creates output directory."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac" / "nested"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [{"apiVersion": "v1", "kind": "ServiceAccount"}],
        }

        paths = write_manifests(manifests, output_dir)

        assert output_dir.exists()
        assert len(paths) == 1

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_writes_yaml(self, tmp_path: Path) -> None:
        """Test write_manifests writes valid YAML content."""
        import yaml

        from floe_core.rbac.generator import write_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "roles.yaml": [
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "Role",
                    "metadata": {"name": "test-role"},
                },
            ],
        }

        write_manifests(manifests, tmp_path)

        content = (tmp_path / "roles.yaml").read_text()
        docs = list(yaml.safe_load_all(content))
        assert len(docs) == 1
        assert docs[0]["kind"] == "Role"

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_empty_list(self, tmp_path: Path) -> None:
        """Test write_manifests creates empty file for empty list."""
        from floe_core.rbac.generator import write_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [],
        }

        paths = write_manifests(manifests, tmp_path)

        assert (tmp_path / "serviceaccounts.yaml").exists()
        assert (tmp_path / "serviceaccounts.yaml").read_text() == ""
        assert len(paths) == 1

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_multiple_documents(self, tmp_path: Path) -> None:
        """Test write_manifests handles multiple documents per file."""
        import yaml

        from floe_core.rbac.generator import write_manifests

        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
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
            ],
        }

        write_manifests(manifests, tmp_path)

        content = (tmp_path / "serviceaccounts.yaml").read_text()
        docs = list(yaml.safe_load_all(content))
        assert len(docs) == 2
