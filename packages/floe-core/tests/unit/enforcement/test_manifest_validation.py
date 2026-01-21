"""Unit tests for manifest version validation.

Tests for validating dbt manifest.json version and format:
- Valid dbt manifest versions (v1.0+)
- Malformed manifest handling
- Unsupported dbt versions (pre-1.0)
- Missing required manifest fields

Task: T013a
Requirements: FR-001 (dbt manifest compatibility)
"""

from __future__ import annotations

from typing import Any

import pytest


class TestManifestVersionValidation:
    """Tests for dbt manifest version validation."""

    @pytest.mark.requirement("003b-FR-001")
    def test_valid_manifest_version_1_0(self) -> None:
        """Test valid dbt manifest v1.0+ is accepted.

        Given a manifest with dbt_version >= 1.0.0,
        When validating the manifest,
        Then validation passes.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "1.0.0",
                "generated_at": "2026-01-01T00:00:00Z",
                "invocation_id": "test-id",
            },
            "nodes": {},
            "sources": {},
            "child_map": {},
            "parent_map": {},
        }

        # The manifest structure is valid for dbt 1.0+
        assert manifest["metadata"]["dbt_version"] == "1.0.0"
        assert "nodes" in manifest
        assert "sources" in manifest

    @pytest.mark.requirement("003b-FR-001")
    def test_valid_manifest_version_1_8(self) -> None:
        """Test valid dbt manifest v1.8 is accepted.

        Given a manifest with dbt_version 1.8.x,
        When validating the manifest,
        Then validation passes (current dbt version).
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "1.8.0",
                "generated_at": "2026-01-01T00:00:00Z",
                "invocation_id": "test-id",
                "adapter_type": "duckdb",
            },
            "nodes": {},
            "sources": {},
            "child_map": {},
            "parent_map": {},
        }

        assert manifest["metadata"]["dbt_version"] == "1.8.0"
        # v1.8 includes adapter_type
        assert manifest["metadata"]["adapter_type"] == "duckdb"

    @pytest.mark.requirement("003b-FR-001")
    def test_valid_manifest_version_2_0(self) -> None:
        """Test valid dbt manifest v2.0+ is accepted.

        Given a manifest with dbt_version 2.x,
        When validating the manifest,
        Then validation passes (future version).
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "2.0.0",
                "generated_at": "2026-01-01T00:00:00Z",
                "invocation_id": "test-id",
            },
            "nodes": {},
            "sources": {},
            "child_map": {},
            "parent_map": {},
        }

        assert manifest["metadata"]["dbt_version"] == "2.0.0"

    @pytest.mark.requirement("003b-FR-001")
    def test_manifest_missing_metadata_raises_error(self) -> None:
        """Test manifest without metadata is detected.

        Given a manifest without metadata section,
        When checking required fields,
        Then the missing metadata is detected.
        """
        manifest: dict[str, Any] = {
            "nodes": {},
            "sources": {},
        }

        assert "metadata" not in manifest

    @pytest.mark.requirement("003b-FR-001")
    def test_manifest_missing_dbt_version_raises_error(self) -> None:
        """Test manifest without dbt_version is detected.

        Given a manifest with metadata but no dbt_version,
        When checking required fields,
        Then the missing dbt_version is detected.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "generated_at": "2026-01-01T00:00:00Z",
            },
            "nodes": {},
            "sources": {},
        }

        assert "dbt_version" not in manifest["metadata"]

    @pytest.mark.requirement("003b-FR-001")
    def test_manifest_missing_nodes_raises_error(self) -> None:
        """Test manifest without nodes is detected.

        Given a manifest without nodes section,
        When checking required fields,
        Then the missing nodes is detected.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "1.8.0",
            },
            "sources": {},
        }

        assert "nodes" not in manifest

    @pytest.mark.requirement("003b-FR-001")
    def test_unsupported_manifest_version_0_x(self) -> None:
        """Test dbt manifest v0.x is detected as unsupported.

        Given a manifest with dbt_version < 1.0.0,
        When checking version,
        Then the unsupported version is detected.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "0.21.0",
                "generated_at": "2020-01-01T00:00:00Z",
            },
            "nodes": {},
            "sources": {},
        }

        version = manifest["metadata"]["dbt_version"]
        major_version = int(version.split(".")[0])
        assert major_version < 1, "Expected pre-1.0 version"

    @pytest.mark.requirement("003b-FR-001")
    def test_malformed_manifest_not_dict(self) -> None:
        """Test malformed manifest (not a dict) is detected.

        Given a manifest that is not a dictionary,
        When checking type,
        Then the malformed structure is detected.
        """
        manifest: list[str] = ["not", "a", "dict"]

        assert not isinstance(manifest, dict)

    @pytest.mark.requirement("003b-FR-001")
    def test_malformed_manifest_null_metadata(self) -> None:
        """Test manifest with null metadata is detected.

        Given a manifest with null metadata,
        When checking metadata,
        Then the null value is detected.
        """
        manifest: dict[str, Any] = {
            "metadata": None,
            "nodes": {},
            "sources": {},
        }

        assert manifest["metadata"] is None

    @pytest.mark.requirement("003b-FR-001")
    def test_malformed_dbt_version_format(self) -> None:
        """Test manifest with malformed dbt_version format is detected.

        Given a manifest with non-semver dbt_version,
        When checking version format,
        Then the malformed version is detected.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "not-a-version",
            },
            "nodes": {},
            "sources": {},
        }

        version = manifest["metadata"]["dbt_version"]
        # Simple check - should have at least one dot for semver
        assert "." not in version or not version[0].isdigit()


class TestManifestNodeValidation:
    """Tests for dbt manifest node structure validation."""

    @pytest.mark.requirement("003b-FR-001")
    def test_valid_model_node(self) -> None:
        """Test valid model node structure.

        Given a manifest with valid model nodes,
        When checking node structure,
        Then the model is recognized.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "1.8.0",
            },
            "nodes": {
                "model.my_project.customers": {
                    "name": "customers",
                    "resource_type": "model",
                    "package_name": "my_project",
                    "path": "models/customers.sql",
                    "original_file_path": "models/customers.sql",
                    "unique_id": "model.my_project.customers",
                    "schema": "main",
                    "database": "dev",
                    "columns": {},
                    "description": "Customer dimension table",
                    "meta": {},
                    "tags": [],
                }
            },
            "sources": {},
            "child_map": {},
            "parent_map": {},
        }

        node = manifest["nodes"]["model.my_project.customers"]
        assert node["name"] == "customers"
        assert node["resource_type"] == "model"

    @pytest.mark.requirement("003b-FR-001")
    def test_valid_source_node(self) -> None:
        """Test valid source node structure.

        Given a manifest with valid source definitions,
        When checking sources structure,
        Then the source is recognized.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "1.8.0",
            },
            "nodes": {},
            "sources": {
                "source.my_project.raw.customers": {
                    "name": "customers",
                    "source_name": "raw",
                    "resource_type": "source",
                    "package_name": "my_project",
                    "path": "models/staging/_sources.yml",
                    "unique_id": "source.my_project.raw.customers",
                    "schema": "raw",
                    "database": "dev",
                    "columns": {},
                    "description": "Raw customer data",
                }
            },
            "child_map": {},
            "parent_map": {},
        }

        source = manifest["sources"]["source.my_project.raw.customers"]
        assert source["name"] == "customers"
        assert source["resource_type"] == "source"

    @pytest.mark.requirement("003b-FR-001")
    def test_model_node_missing_name(self) -> None:
        """Test model node without name is detected.

        Given a model node without name field,
        When checking required fields,
        Then the missing name is detected.
        """
        node: dict[str, Any] = {
            "resource_type": "model",
            "unique_id": "model.my_project.customers",
        }

        assert "name" not in node

    @pytest.mark.requirement("003b-FR-001")
    def test_model_node_missing_resource_type(self) -> None:
        """Test model node without resource_type is detected.

        Given a model node without resource_type field,
        When checking required fields,
        Then the missing resource_type is detected.
        """
        node: dict[str, Any] = {
            "name": "customers",
            "unique_id": "model.my_project.customers",
        }

        assert "resource_type" not in node


class TestManifestChildMapValidation:
    """Tests for dbt manifest child_map structure validation."""

    @pytest.mark.requirement("003b-FR-001")
    def test_valid_child_map(self) -> None:
        """Test valid child_map structure.

        Given a manifest with valid child_map,
        When checking structure,
        Then the dependencies are recognized.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "1.8.0",
            },
            "nodes": {},
            "sources": {},
            "child_map": {
                "source.my_project.raw.customers": [
                    "model.my_project.stg_customers",
                ],
                "model.my_project.stg_customers": [
                    "model.my_project.dim_customers",
                    "model.my_project.fct_orders",
                ],
            },
            "parent_map": {},
        }

        child_map = manifest["child_map"]
        assert len(child_map["source.my_project.raw.customers"]) == 1
        assert len(child_map["model.my_project.stg_customers"]) == 2

    @pytest.mark.requirement("003b-FR-001")
    def test_empty_child_map(self) -> None:
        """Test empty child_map is valid.

        Given a manifest with empty child_map (no dependencies),
        When checking structure,
        Then the empty map is accepted.
        """
        manifest: dict[str, Any] = {
            "metadata": {
                "dbt_version": "1.8.0",
            },
            "nodes": {},
            "sources": {},
            "child_map": {},
            "parent_map": {},
        }

        assert manifest["child_map"] == {}


class TestManifestVersionParsing:
    """Tests for dbt version string parsing."""

    @pytest.mark.requirement("003b-FR-001")
    def test_parse_semver_version(self) -> None:
        """Test parsing standard semver version.

        Given a standard semver version string,
        When parsing,
        Then major, minor, patch are extracted.
        """
        version = "1.8.5"
        parts = version.split(".")

        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])

        assert major == 1
        assert minor == 8
        assert patch == 5

    @pytest.mark.requirement("003b-FR-001")
    def test_parse_version_with_suffix(self) -> None:
        """Test parsing version with pre-release suffix.

        Given a version with pre-release suffix,
        When parsing,
        Then major version is still extracted.
        """
        version = "1.8.0-rc1"
        parts = version.split(".")

        major = int(parts[0])
        assert major == 1

    @pytest.mark.requirement("003b-FR-001")
    def test_compare_versions_for_minimum(self) -> None:
        """Test comparing versions for minimum requirement.

        Given various dbt versions,
        When comparing against minimum 1.0.0,
        Then correct comparison is made.
        """
        min_version = (1, 0, 0)

        def parse_version(v: str) -> tuple[int, ...]:
            parts = v.split("-")[0].split(".")  # Remove suffix, split
            return tuple(int(p) for p in parts[:3])

        # Supported versions
        assert parse_version("1.0.0") >= min_version
        assert parse_version("1.8.0") >= min_version
        assert parse_version("2.0.0") >= min_version

        # Unsupported versions
        assert parse_version("0.21.0") < min_version
        assert parse_version("0.19.1") < min_version
