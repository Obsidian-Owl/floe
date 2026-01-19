"""Unit tests for RBAC manifest file writing.

Tests the write_manifests function that writes generated RBAC manifests
to separate YAML files in the target/rbac/ directory.

Task: T042
User Story: US4 - RBAC Manifest Generation
Requirements: FR-053
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


class TestManifestWritingBasics:
    """Unit tests for basic manifest file writing behavior."""

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_creates_output_directory(self, tmp_path: Path) -> None:
        """Test write_manifests creates output directory if not exists."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "target" / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        assert output_dir.exists()
        assert output_dir.is_dir()

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_creates_all_files(self, tmp_path: Path) -> None:
        """Test write_manifests creates all expected files."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        assert (output_dir / "serviceaccounts.yaml").exists()
        assert (output_dir / "roles.yaml").exists()
        assert (output_dir / "rolebindings.yaml").exists()
        assert (output_dir / "namespaces.yaml").exists()

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_returns_list_of_paths(self, tmp_path: Path) -> None:
        """Test write_manifests returns list of written file paths."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        paths = write_manifests(manifests, output_dir)

        assert isinstance(paths, list)
        assert len(paths) == 4
        assert all(isinstance(p, Path) for p in paths)


class TestManifestWritingContent:
    """Unit tests for manifest file content writing."""

    @pytest.mark.requirement("FR-053")
    def test_write_single_serviceaccount_manifest(self, tmp_path: Path) -> None:
        """Test writing a single ServiceAccount manifest."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        sa_manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": "floe-job-runner",
                "namespace": "floe-jobs",
                "labels": {"app.kubernetes.io/managed-by": "floe"},
            },
            "automountServiceAccountToken": False,
        }

        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [sa_manifest],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        # Read back and verify
        content = (output_dir / "serviceaccounts.yaml").read_text()
        parsed = list(yaml.safe_load_all(content))

        assert len(parsed) == 1
        assert parsed[0]["kind"] == "ServiceAccount"
        assert parsed[0]["metadata"]["name"] == "floe-job-runner"

    @pytest.mark.requirement("FR-053")
    def test_write_multiple_manifests_per_file(self, tmp_path: Path) -> None:
        """Test writing multiple manifests to single file with YAML document separator."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "floe-sa-1", "namespace": "default"},
                },
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "floe-sa-2", "namespace": "default"},
                },
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {"name": "floe-sa-3", "namespace": "default"},
                },
            ],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        # Read back and verify all documents
        content = (output_dir / "serviceaccounts.yaml").read_text()
        parsed = list(yaml.safe_load_all(content))

        assert len(parsed) == 3
        names = [doc["metadata"]["name"] for doc in parsed]
        assert names == ["floe-sa-1", "floe-sa-2", "floe-sa-3"]

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_uses_yaml_document_separator(self, tmp_path: Path) -> None:
        """Test that multiple manifests are separated by YAML document separator."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "floe-a", "namespace": "default"}},
                {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "floe-b", "namespace": "default"}},
            ],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        content = (output_dir / "serviceaccounts.yaml").read_text()

        # Should contain document separator
        assert "---" in content


class TestManifestWritingEmptyLists:
    """Unit tests for handling empty manifest lists."""

    @pytest.mark.requirement("FR-053")
    def test_empty_manifest_list_creates_empty_file(self, tmp_path: Path) -> None:
        """Test empty manifest list creates file with no documents."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        # File should exist but contain no valid documents
        content = (output_dir / "serviceaccounts.yaml").read_text()
        parsed = list(yaml.safe_load_all(content))

        # Empty or contains only None (from empty YAML)
        valid_docs = [doc for doc in parsed if doc is not None]
        assert len(valid_docs) == 0

    @pytest.mark.requirement("FR-053")
    def test_mixed_empty_and_filled_lists(self, tmp_path: Path) -> None:
        """Test mix of empty and non-empty manifest lists."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "floe-test", "namespace": "default"}},
            ],
            "roles.yaml": [],  # Empty
            "rolebindings.yaml": [],  # Empty
            "namespaces.yaml": [
                {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "floe-jobs"}},
            ],
        }

        write_manifests(manifests, output_dir)

        # ServiceAccounts should have content
        sa_content = (output_dir / "serviceaccounts.yaml").read_text()
        sa_docs = [d for d in yaml.safe_load_all(sa_content) if d]
        assert len(sa_docs) == 1

        # Namespaces should have content
        ns_content = (output_dir / "namespaces.yaml").read_text()
        ns_docs = [d for d in yaml.safe_load_all(ns_content) if d]
        assert len(ns_docs) == 1


class TestManifestWritingYAMLFormat:
    """Unit tests for YAML formatting in manifest writing."""

    @pytest.mark.requirement("FR-053")
    def test_written_yaml_is_valid(self, tmp_path: Path) -> None:
        """Test written files contain valid YAML."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {
                        "name": "floe-test",
                        "namespace": "floe-jobs",
                        "labels": {"app.kubernetes.io/managed-by": "floe"},
                    },
                },
            ],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        # Should parse without errors
        content = (output_dir / "serviceaccounts.yaml").read_text()
        parsed = list(yaml.safe_load_all(content))
        assert len(parsed) >= 1

    @pytest.mark.requirement("FR-053")
    def test_written_yaml_roundtrips_correctly(self, tmp_path: Path) -> None:
        """Test written YAML can be read back with identical content."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        original_manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": "floe-test",
                "namespace": "default",
                "labels": {"app.kubernetes.io/managed-by": "floe"},
                "annotations": {},
            },
            "automountServiceAccountToken": False,
        }

        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [original_manifest],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        # Read back and compare
        content = (output_dir / "serviceaccounts.yaml").read_text()
        parsed = list(yaml.safe_load_all(content))[0]

        assert parsed["apiVersion"] == original_manifest["apiVersion"]
        assert parsed["kind"] == original_manifest["kind"]
        assert parsed["metadata"]["name"] == original_manifest["metadata"]["name"]


class TestManifestWritingFileOverwrite:
    """Unit tests for file overwrite behavior."""

    @pytest.mark.requirement("FR-053")
    def test_write_manifests_overwrites_existing_files(self, tmp_path: Path) -> None:
        """Test write_manifests overwrites existing files."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        output_dir.mkdir(parents=True)

        # Create existing file
        existing_file = output_dir / "serviceaccounts.yaml"
        existing_file.write_text("# Old content\napiVersion: v1\nkind: ServiceAccount")

        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "floe-new", "namespace": "default"}},
            ],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        # Should have new content
        content = existing_file.read_text()
        assert "floe-new" in content
        assert "# Old content" not in content


class TestManifestWritingEdgeCases:
    """Unit tests for edge cases in manifest writing."""

    @pytest.mark.requirement("FR-053")
    def test_manifest_with_nested_structures(self, tmp_path: Path) -> None:
        """Test writing manifest with deeply nested structures."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [],
            "roles.yaml": [
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "Role",
                    "metadata": {
                        "name": "floe-test-role",
                        "namespace": "floe-jobs",
                        "labels": {"app.kubernetes.io/managed-by": "floe"},
                    },
                    "rules": [
                        {
                            "apiGroups": [""],
                            "resources": ["secrets"],
                            "verbs": ["get"],
                            "resourceNames": ["secret-a", "secret-b"],
                        },
                        {
                            "apiGroups": ["batch"],
                            "resources": ["jobs"],
                            "verbs": ["get", "list", "create", "delete"],
                        },
                    ],
                },
            ],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        # Should parse nested structures correctly
        content = (output_dir / "roles.yaml").read_text()
        parsed = list(yaml.safe_load_all(content))[0]

        assert len(parsed["rules"]) == 2
        assert parsed["rules"][0]["resourceNames"] == ["secret-a", "secret-b"]

    @pytest.mark.requirement("FR-053")
    def test_manifest_with_special_characters(self, tmp_path: Path) -> None:
        """Test writing manifest with special characters in values."""
        from floe_core.rbac.generator import write_manifests

        output_dir = tmp_path / "rbac"
        manifests: dict[str, list[dict[str, Any]]] = {
            "serviceaccounts.yaml": [
                {
                    "apiVersion": "v1",
                    "kind": "ServiceAccount",
                    "metadata": {
                        "name": "floe-test",
                        "namespace": "default",
                        "annotations": {
                            "description": "Service account for: jobs & tasks",
                            "quote-test": "Value with 'single' and \"double\" quotes",
                        },
                    },
                },
            ],
            "roles.yaml": [],
            "rolebindings.yaml": [],
            "namespaces.yaml": [],
        }

        write_manifests(manifests, output_dir)

        # Should handle special characters
        content = (output_dir / "serviceaccounts.yaml").read_text()
        parsed = list(yaml.safe_load_all(content))[0]

        assert "jobs & tasks" in parsed["metadata"]["annotations"]["description"]
