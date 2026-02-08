"""Unit tests for ServiceAccountConfig.to_k8s_manifest() method.

Tests the K8s ServiceAccount manifest generation including all required fields,
labels, annotations, and automountServiceAccountToken handling.

Task: T018
User Story: US1 - Service Account Generation
Requirements: FR-010, FR-011, FR-012, FR-013, FR-014
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core.schemas.rbac import ServiceAccountConfig


class TestServiceAccountManifestBasicStructure:
    """Unit tests for basic manifest structure."""

    @pytest.mark.requirement("FR-012")
    def test_manifest_has_api_version(self) -> None:
        """Test manifest includes apiVersion: v1."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert "apiVersion" in manifest
        assert manifest["apiVersion"] == "v1"

    @pytest.mark.requirement("FR-012")
    def test_manifest_has_kind(self) -> None:
        """Test manifest includes kind: ServiceAccount."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert "kind" in manifest
        assert manifest["kind"] == "ServiceAccount"

    @pytest.mark.requirement("FR-012")
    def test_manifest_has_metadata(self) -> None:
        """Test manifest includes metadata section."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert "metadata" in manifest
        assert isinstance(manifest["metadata"], dict)

    @pytest.mark.requirement("FR-012")
    def test_manifest_returns_dict(self) -> None:
        """Test to_k8s_manifest returns a dictionary."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest, dict)


class TestServiceAccountManifestMetadata:
    """Unit tests for manifest metadata section."""

    @pytest.mark.requirement("FR-010")
    def test_metadata_has_name(self) -> None:
        """Test metadata includes name matching config."""
        config = ServiceAccountConfig(name="floe-runner", namespace="default")
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["name"] == "floe-runner"

    @pytest.mark.requirement("FR-010")
    def test_metadata_has_namespace(self) -> None:
        """Test metadata includes namespace matching config."""
        config = ServiceAccountConfig(name="floe-test", namespace="floe-jobs")
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-013")
    def test_metadata_has_labels(self) -> None:
        """Test metadata includes labels section."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert "labels" in manifest["metadata"]
        assert isinstance(manifest["metadata"]["labels"], dict)

    @pytest.mark.requirement("FR-013")
    def test_metadata_has_managed_by_label(self) -> None:
        """Test metadata labels include managed-by: floe."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert "app.kubernetes.io/managed-by" in labels
        assert labels["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-010")
    def test_metadata_includes_custom_labels(self) -> None:
        """Test metadata includes custom labels from config."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            labels={
                "app.kubernetes.io/managed-by": "floe",
                "custom-label": "custom-value",
                "team": "data-platform",
            },
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert labels["custom-label"] == "custom-value"
        assert labels["team"] == "data-platform"

    @pytest.mark.requirement("FR-010")
    def test_metadata_has_annotations(self) -> None:
        """Test metadata includes annotations section."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            annotations={"description": "Test SA"},
        )
        manifest = config.to_k8s_manifest()

        assert "annotations" in manifest["metadata"]
        assert manifest["metadata"]["annotations"]["description"] == "Test SA"

    @pytest.mark.requirement("FR-010")
    def test_metadata_empty_annotations(self) -> None:
        """Test metadata handles empty annotations dict."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
        )
        manifest = config.to_k8s_manifest()

        # Empty annotations dict should still be present
        assert "annotations" in manifest["metadata"]
        assert manifest["metadata"]["annotations"] == {}


class TestServiceAccountManifestAutomountToken:
    """Unit tests for automountServiceAccountToken field."""

    @pytest.mark.requirement("FR-014")
    def test_manifest_has_automount_token_field(self) -> None:
        """Test manifest includes automountServiceAccountToken field."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert "automountServiceAccountToken" in manifest

    @pytest.mark.requirement("FR-011")
    def test_automount_token_default_is_false(self) -> None:
        """Test automountServiceAccountToken defaults to False."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert manifest["automountServiceAccountToken"] is False

    @pytest.mark.requirement("FR-014")
    def test_automount_token_true(self) -> None:
        """Test automountServiceAccountToken can be set to True."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            automount_token=True,
        )
        manifest = config.to_k8s_manifest()

        assert manifest["automountServiceAccountToken"] is True

    @pytest.mark.requirement("FR-014")
    def test_automount_token_explicit_false(self) -> None:
        """Test automountServiceAccountToken can be explicitly set to False."""
        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            automount_token=False,
        )
        manifest = config.to_k8s_manifest()

        assert manifest["automountServiceAccountToken"] is False


class TestServiceAccountManifestFieldTypes:
    """Unit tests for manifest field types."""

    @pytest.mark.requirement("FR-012")
    def test_api_version_is_string(self) -> None:
        """Test apiVersion is a string."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["apiVersion"], str)

    @pytest.mark.requirement("FR-012")
    def test_kind_is_string(self) -> None:
        """Test kind is a string."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["kind"], str)

    @pytest.mark.requirement("FR-010")
    def test_name_is_string(self) -> None:
        """Test name is a string."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["metadata"]["name"], str)

    @pytest.mark.requirement("FR-010")
    def test_namespace_is_string(self) -> None:
        """Test namespace is a string."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["metadata"]["namespace"], str)

    @pytest.mark.requirement("FR-013")
    def test_labels_is_dict(self) -> None:
        """Test labels is a dictionary."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["metadata"]["labels"], dict)

    @pytest.mark.requirement("FR-014")
    def test_automount_token_is_bool(self) -> None:
        """Test automountServiceAccountToken is a boolean."""
        config = ServiceAccountConfig(name="floe-test", namespace="default")
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["automountServiceAccountToken"], bool)


class TestServiceAccountManifestVariousConfigs:
    """Unit tests for manifest generation with various configurations."""

    @pytest.mark.requirement("FR-010")
    def test_minimal_config(self) -> None:
        """Test manifest generation with minimal config."""
        config = ServiceAccountConfig(name="floe-minimal", namespace="default")
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "v1"
        assert manifest["kind"] == "ServiceAccount"
        assert manifest["metadata"]["name"] == "floe-minimal"
        assert manifest["metadata"]["namespace"] == "default"
        assert manifest["automountServiceAccountToken"] is False

    @pytest.mark.requirement("FR-010")
    def test_full_config(self) -> None:
        """Test manifest generation with all fields populated."""
        config = ServiceAccountConfig(
            name="floe-full",
            namespace="floe-platform",
            automount_token=True,
            labels={
                "app.kubernetes.io/managed-by": "floe",
                "app.kubernetes.io/component": "rbac",
                "environment": "production",
            },
            annotations={
                "description": "Full service account",
                "owner": "platform-team",
            },
        )
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["name"] == "floe-full"
        assert manifest["metadata"]["namespace"] == "floe-platform"
        assert manifest["automountServiceAccountToken"] is True
        assert manifest["metadata"]["labels"]["environment"] == "production"
        assert manifest["metadata"]["annotations"]["owner"] == "platform-team"

    @pytest.mark.requirement("FR-010")
    def test_different_namespaces(self) -> None:
        """Test manifest generation for different namespaces."""
        namespaces = ["default", "floe-jobs", "floe-platform", "kube-system"]

        for ns in namespaces:
            config = ServiceAccountConfig(name="floe-test", namespace=ns)
            manifest = config.to_k8s_manifest()
            assert manifest["metadata"]["namespace"] == ns

    @pytest.mark.requirement("FR-010")
    def test_different_names(self) -> None:
        """Test manifest generation with different valid names."""
        names = [
            "floe-a",
            "floe-job-runner",
            "floe-pipeline-executor",
            "floe-dbt-runner-v2",
        ]

        for name in names:
            config = ServiceAccountConfig(name=name, namespace="default")
            manifest = config.to_k8s_manifest()
            assert manifest["metadata"]["name"] == name


class TestServiceAccountManifestYamlCompatibility:
    """Unit tests ensuring manifest is YAML-serializable."""

    @pytest.mark.requirement("FR-012")
    def test_manifest_can_be_yaml_serialized(self) -> None:
        """Test manifest can be serialized to YAML."""
        import yaml

        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            labels={"app.kubernetes.io/managed-by": "floe"},
        )
        manifest = config.to_k8s_manifest()

        # Should not raise
        yaml_str = yaml.dump(manifest, default_flow_style=False)
        assert "apiVersion: v1" in yaml_str
        assert "kind: ServiceAccount" in yaml_str

    @pytest.mark.requirement("FR-012")
    def test_manifest_yaml_roundtrip(self) -> None:
        """Test manifest survives YAML roundtrip."""
        import yaml

        config = ServiceAccountConfig(
            name="floe-test",
            namespace="default",
            automount_token=True,
        )
        manifest = config.to_k8s_manifest()

        yaml_str = yaml.dump(manifest)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        assert restored["apiVersion"] == manifest["apiVersion"]
        assert restored["kind"] == manifest["kind"]
        assert restored["metadata"]["name"] == manifest["metadata"]["name"]
        assert restored["automountServiceAccountToken"] == manifest["automountServiceAccountToken"]
