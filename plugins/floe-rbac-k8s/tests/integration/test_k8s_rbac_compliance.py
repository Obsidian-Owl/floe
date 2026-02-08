"""Integration tests for K8sRBACPlugin compliance with BaseRBACPluginTests.

This module validates that K8sRBACPlugin passes all compliance tests defined
in the BaseRBACPluginTests base class.

Task: T026
User Story: US1 - Service Account Generation
Requirements: FR-001, FR-003, FR-010-014, FR-020-024, FR-030-034, FR-040-044, FR-070
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from testing.base_classes.base_rbac_plugin_tests import BaseRBACPluginTests

if TYPE_CHECKING:
    from floe_rbac_k8s.plugin import K8sRBACPlugin as K8sRBACPluginType


class TestK8sRBACPluginCompliance(BaseRBACPluginTests):
    """Integration tests validating K8sRBACPlugin meets all interface requirements.

    Inherits all test methods from BaseRBACPluginTests and provides
    a concrete K8sRBACPlugin instance via the rbac_plugin fixture.

    This test class validates:
    - Plugin metadata (name, version, floe_api_version)
    - ServiceAccount generation
    - Role generation with resourceNames support
    - RoleBinding generation with cross-namespace subjects
    - Namespace generation with PSS labels
    - Pod security context generation
    - Wildcard permission rejection (FR-070)
    """

    @pytest.fixture
    def rbac_plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing.

        Returns:
            A configured K8sRBACPlugin instance.
        """
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()


class TestK8sRBACPluginSpecific:
    """K8s-specific tests beyond base compliance.

    These tests validate K8s-specific behavior not covered by the
    generic BaseRBACPluginTests.
    """

    @pytest.fixture
    def plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-001")
    def test_plugin_name_is_k8s_rbac(self, plugin: K8sRBACPluginType) -> None:
        """Verify plugin name is 'k8s-rbac'."""
        assert plugin.name == "k8s-rbac"

    @pytest.mark.requirement("FR-003")
    def test_plugin_version_is_semver(self, plugin: K8sRBACPluginType) -> None:
        """Verify plugin version follows semantic versioning."""
        version = plugin.version
        parts = version.split(".")
        assert len(parts) >= 2, "Version should have at least major.minor"
        assert all(
            part.isdigit() for part in parts[:2]
        ), "Major and minor should be numeric"

    @pytest.mark.requirement("FR-010")
    def test_service_account_manifest_is_valid_k8s(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Verify ServiceAccount manifest has all required K8s fields."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        config = ServiceAccountConfig(name="floe-test-runner", namespace="floe-jobs")
        manifest = plugin.generate_service_account(config)

        # Required top-level fields for K8s
        assert "apiVersion" in manifest
        assert "kind" in manifest
        assert "metadata" in manifest

        # Required metadata fields
        assert "name" in manifest["metadata"]
        assert "namespace" in manifest["metadata"]

    @pytest.mark.requirement("FR-020")
    def test_role_manifest_is_valid_k8s(self, plugin: K8sRBACPluginType) -> None:
        """Verify Role manifest has all required K8s fields."""
        from floe_core.schemas.rbac import RoleConfig, RoleRule

        config = RoleConfig(
            name="floe-test-role",
            namespace="floe-jobs",
            rules=[RoleRule(resources=["pods"], verbs=["get", "list"])],
        )
        manifest = plugin.generate_role(config)

        # Required top-level fields for K8s
        assert "apiVersion" in manifest
        assert "kind" in manifest
        assert "metadata" in manifest
        assert "rules" in manifest

        # Required rule fields
        assert len(manifest["rules"]) > 0
        assert "apiGroups" in manifest["rules"][0]
        assert "resources" in manifest["rules"][0]
        assert "verbs" in manifest["rules"][0]

    @pytest.mark.requirement("FR-022")
    def test_role_binding_manifest_is_valid_k8s(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Verify RoleBinding manifest has all required K8s fields."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="floe-jobs",
            subjects=[RoleBindingSubject(name="floe-test", namespace="floe-jobs")],
            role_name="floe-test-role",
        )
        manifest = plugin.generate_role_binding(config)

        # Required top-level fields for K8s
        assert "apiVersion" in manifest
        assert "kind" in manifest
        assert "metadata" in manifest
        assert "subjects" in manifest
        assert "roleRef" in manifest

        # Required roleRef fields
        assert "kind" in manifest["roleRef"]
        assert "name" in manifest["roleRef"]
        assert "apiGroup" in manifest["roleRef"]

    @pytest.mark.requirement("FR-030")
    def test_namespace_manifest_is_valid_k8s(self, plugin: K8sRBACPluginType) -> None:
        """Verify Namespace manifest has all required K8s fields."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-test-ns", layer="4")
        manifest = plugin.generate_namespace(config)

        # Required top-level fields for K8s
        assert "apiVersion" in manifest
        assert "kind" in manifest
        assert "metadata" in manifest

        # Required metadata fields
        assert "name" in manifest["metadata"]
        assert "labels" in manifest["metadata"]

    @pytest.mark.requirement("FR-040")
    def test_pod_security_context_returns_both_contexts(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Verify generate_pod_security_context returns pod and container contexts."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = plugin.generate_pod_security_context(config)

        assert "pod" in contexts
        assert "container" in contexts
        assert isinstance(contexts["pod"], dict)
        assert isinstance(contexts["container"], dict)

    @pytest.mark.requirement("FR-011")
    def test_service_account_automount_default_false(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Verify ServiceAccount automountServiceAccountToken defaults to False."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        # Default config
        config = ServiceAccountConfig(name="floe-test-runner", namespace="floe-jobs")
        manifest = plugin.generate_service_account(config)

        assert manifest["automountServiceAccountToken"] is False

    @pytest.mark.requirement("FR-013")
    def test_all_manifests_have_managed_by_label(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Verify all generated manifests have the managed-by label."""
        from floe_core.schemas.rbac import (
            NamespaceConfig,
            RoleBindingConfig,
            RoleBindingSubject,
            RoleConfig,
            RoleRule,
            ServiceAccountConfig,
        )

        # ServiceAccount
        sa_manifest = plugin.generate_service_account(
            ServiceAccountConfig(name="floe-test", namespace="floe-jobs")
        )
        assert (
            sa_manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"
        )

        # Role
        role_manifest = plugin.generate_role(
            RoleConfig(
                name="floe-test-role",
                namespace="floe-jobs",
                rules=[RoleRule(resources=["pods"], verbs=["get"])],
            )
        )
        assert (
            role_manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"]
            == "floe"
        )

        # RoleBinding
        rb_manifest = plugin.generate_role_binding(
            RoleBindingConfig(
                name="floe-test-binding",
                namespace="floe-jobs",
                subjects=[RoleBindingSubject(name="floe-test", namespace="floe-jobs")],
                role_name="floe-test-role",
            )
        )
        assert (
            rb_manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"
        )

        # Namespace
        ns_manifest = plugin.generate_namespace(
            NamespaceConfig(name="floe-test-ns", layer="4")
        )
        assert (
            ns_manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"
        )


class TestK8sRBACPluginYAMLCompatibility:
    """Tests for YAML serialization compatibility."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-012")
    def test_service_account_manifest_yaml_compatible(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Verify ServiceAccount manifest can be serialized to YAML."""
        import yaml
        from floe_core.schemas.rbac import ServiceAccountConfig

        config = ServiceAccountConfig(name="floe-test", namespace="floe-jobs")
        manifest = plugin.generate_service_account(config)

        # Should not raise
        yaml_str = yaml.dump(manifest, default_flow_style=False)
        assert "apiVersion: v1" in yaml_str
        assert "kind: ServiceAccount" in yaml_str

    @pytest.mark.requirement("FR-020")
    def test_role_manifest_yaml_compatible(self, plugin: K8sRBACPluginType) -> None:
        """Verify Role manifest can be serialized to YAML."""
        import yaml
        from floe_core.schemas.rbac import RoleConfig, RoleRule

        config = RoleConfig(
            name="floe-test-role",
            namespace="floe-jobs",
            rules=[RoleRule(resources=["secrets"], verbs=["get"])],
        )
        manifest = plugin.generate_role(config)

        yaml_str = yaml.dump(manifest, default_flow_style=False)
        assert "apiVersion: rbac.authorization.k8s.io/v1" in yaml_str
        assert "kind: Role" in yaml_str

    @pytest.mark.requirement("FR-022")
    def test_role_binding_manifest_yaml_compatible(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Verify RoleBinding manifest can be serialized to YAML."""
        import yaml
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-test-binding",
            namespace="floe-jobs",
            subjects=[RoleBindingSubject(name="floe-test", namespace="floe-jobs")],
            role_name="floe-test-role",
        )
        manifest = plugin.generate_role_binding(config)

        yaml_str = yaml.dump(manifest, default_flow_style=False)
        assert "apiVersion: rbac.authorization.k8s.io/v1" in yaml_str
        assert "kind: RoleBinding" in yaml_str

    @pytest.mark.requirement("FR-030")
    def test_namespace_manifest_yaml_compatible(
        self, plugin: K8sRBACPluginType
    ) -> None:
        """Verify Namespace manifest can be serialized to YAML."""
        import yaml
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-test-ns", layer="4")
        manifest = plugin.generate_namespace(config)

        yaml_str = yaml.dump(manifest, default_flow_style=False)
        assert "apiVersion: v1" in yaml_str
        assert "kind: Namespace" in yaml_str
