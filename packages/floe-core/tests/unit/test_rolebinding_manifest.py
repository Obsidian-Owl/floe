"""Unit tests for RoleBindingConfig.to_k8s_manifest() method.

Tests the K8s RoleBinding manifest generation including subjects structure,
roleRef handling, and label handling.

Task: T020
User Story: US1 - Service Account Generation
Requirements: FR-022
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject


class TestRoleBindingManifestBasicStructure:
    """Unit tests for basic manifest structure."""

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_api_version(self) -> None:
        """Test manifest includes apiVersion: rbac.authorization.k8s.io/v1."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert "apiVersion" in manifest
        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_kind(self) -> None:
        """Test manifest includes kind: RoleBinding."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert "kind" in manifest
        assert manifest["kind"] == "RoleBinding"

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_metadata(self) -> None:
        """Test manifest includes metadata section."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert "metadata" in manifest
        assert isinstance(manifest["metadata"], dict)

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_subjects(self) -> None:
        """Test manifest includes subjects section."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert "subjects" in manifest
        assert isinstance(manifest["subjects"], list)

    @pytest.mark.requirement("FR-022")
    def test_manifest_has_role_ref(self) -> None:
        """Test manifest includes roleRef section."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert "roleRef" in manifest
        assert isinstance(manifest["roleRef"], dict)


class TestRoleBindingManifestMetadata:
    """Unit tests for manifest metadata section."""

    @pytest.mark.requirement("FR-022")
    def test_metadata_has_name(self) -> None:
        """Test metadata includes name matching config."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-reader-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-reader-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["name"] == "floe-reader-binding"

    @pytest.mark.requirement("FR-022")
    def test_metadata_has_namespace(self) -> None:
        """Test metadata includes namespace matching config."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="floe-jobs",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-022")
    def test_metadata_has_managed_by_label(self) -> None:
        """Test metadata labels include managed-by: floe."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert "app.kubernetes.io/managed-by" in labels
        assert labels["app.kubernetes.io/managed-by"] == "floe"


class TestRoleBindingManifestSubjects:
    """Unit tests for manifest subjects section."""

    @pytest.mark.requirement("FR-022")
    def test_subject_has_kind(self) -> None:
        """Test subject includes kind: ServiceAccount."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["subjects"][0]["kind"] == "ServiceAccount"

    @pytest.mark.requirement("FR-022")
    def test_subject_has_name(self) -> None:
        """Test subject includes name."""
        subject = RoleBindingSubject(name="floe-pipeline-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["subjects"][0]["name"] == "floe-pipeline-runner"

    @pytest.mark.requirement("FR-022")
    def test_subject_has_namespace(self) -> None:
        """Test subject includes namespace."""
        subject = RoleBindingSubject(name="floe-runner", namespace="floe-jobs")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["subjects"][0]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-022")
    def test_multiple_subjects(self) -> None:
        """Test manifest with multiple subjects."""
        subjects = [
            RoleBindingSubject(name="floe-runner-1", namespace="floe-jobs"),
            RoleBindingSubject(name="floe-runner-2", namespace="floe-jobs"),
            RoleBindingSubject(name="floe-admin", namespace="floe-platform"),
        ]
        config = RoleBindingConfig(
            name="floe-multi-binding",
            namespace="default",
            subjects=subjects,
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert len(manifest["subjects"]) == 3
        assert manifest["subjects"][0]["name"] == "floe-runner-1"
        assert manifest["subjects"][1]["name"] == "floe-runner-2"
        assert manifest["subjects"][2]["namespace"] == "floe-platform"


class TestRoleBindingManifestRoleRef:
    """Unit tests for manifest roleRef section."""

    @pytest.mark.requirement("FR-022")
    def test_role_ref_has_kind(self) -> None:
        """Test roleRef includes kind: Role."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["roleRef"]["kind"] == "Role"

    @pytest.mark.requirement("FR-022")
    def test_role_ref_has_name(self) -> None:
        """Test roleRef includes name matching role_name."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-reader-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["roleRef"]["name"] == "floe-reader-role"

    @pytest.mark.requirement("FR-022")
    def test_role_ref_has_api_group(self) -> None:
        """Test roleRef includes apiGroup: rbac.authorization.k8s.io."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["roleRef"]["apiGroup"] == "rbac.authorization.k8s.io"


class TestRoleBindingManifestFieldTypes:
    """Unit tests for manifest field types."""

    @pytest.mark.requirement("FR-022")
    def test_api_version_is_string(self) -> None:
        """Test apiVersion is a string."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["apiVersion"], str)

    @pytest.mark.requirement("FR-022")
    def test_kind_is_string(self) -> None:
        """Test kind is a string."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["kind"], str)

    @pytest.mark.requirement("FR-022")
    def test_subjects_is_list(self) -> None:
        """Test subjects is a list."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["subjects"], list)

    @pytest.mark.requirement("FR-022")
    def test_role_ref_is_dict(self) -> None:
        """Test roleRef is a dictionary."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        assert isinstance(manifest["roleRef"], dict)


class TestRoleBindingManifestVariousConfigs:
    """Unit tests for manifest generation with various configurations."""

    @pytest.mark.requirement("FR-022")
    def test_minimal_config(self) -> None:
        """Test manifest generation with minimal config."""
        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-minimal-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-minimal-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"
        assert manifest["kind"] == "RoleBinding"
        assert manifest["metadata"]["name"] == "floe-minimal-binding"
        assert len(manifest["subjects"]) == 1
        assert manifest["roleRef"]["name"] == "floe-minimal-role"

    @pytest.mark.requirement("FR-022")
    def test_cross_namespace_subjects(self) -> None:
        """Test manifest with subjects from different namespaces."""
        subjects = [
            RoleBindingSubject(name="floe-runner", namespace="floe-jobs"),
            RoleBindingSubject(name="floe-admin", namespace="floe-platform"),
        ]
        config = RoleBindingConfig(
            name="floe-cross-ns-binding",
            namespace="target-namespace",
            subjects=subjects,
            role_name="floe-shared-role",
        )
        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["namespace"] == "target-namespace"
        assert manifest["subjects"][0]["namespace"] == "floe-jobs"
        assert manifest["subjects"][1]["namespace"] == "floe-platform"


class TestRoleBindingManifestYamlCompatibility:
    """Unit tests ensuring manifest is YAML-serializable."""

    @pytest.mark.requirement("FR-022")
    def test_manifest_can_be_yaml_serialized(self) -> None:
        """Test manifest can be serialized to YAML."""
        import yaml

        subject = RoleBindingSubject(name="floe-runner", namespace="default")
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=[subject],
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        # Should not raise
        yaml_str = yaml.dump(manifest, default_flow_style=False)
        assert "apiVersion: rbac.authorization.k8s.io/v1" in yaml_str
        assert "kind: RoleBinding" in yaml_str

    @pytest.mark.requirement("FR-022")
    def test_manifest_yaml_roundtrip(self) -> None:
        """Test manifest survives YAML roundtrip."""
        import yaml

        subjects = [
            RoleBindingSubject(name="floe-runner", namespace="floe-jobs"),
        ]
        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="default",
            subjects=subjects,
            role_name="floe-test-role",
        )
        manifest = config.to_k8s_manifest()

        yaml_str = yaml.dump(manifest)
        restored: dict[str, Any] = yaml.safe_load(yaml_str)

        assert restored["apiVersion"] == manifest["apiVersion"]
        assert restored["kind"] == manifest["kind"]
        assert restored["subjects"][0]["name"] == manifest["subjects"][0]["name"]
        assert restored["roleRef"]["name"] == manifest["roleRef"]["name"]
