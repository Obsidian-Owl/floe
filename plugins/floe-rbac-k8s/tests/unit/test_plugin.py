"""Unit tests for K8sRBACPlugin.

Tests the K8sRBACPlugin class which implements the RBACPlugin ABC
from floe-core, generating Kubernetes RBAC manifests.

Task: T011
User Story: US2 - Plugin System
Requirements: FR-002, FR-003
"""

from __future__ import annotations

import pytest


class TestK8sRBACPluginMetadata:
    """Unit tests for K8sRBACPlugin metadata properties."""

    @pytest.mark.requirement("FR-002")
    def test_plugin_name(self) -> None:
        """Test plugin name property."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()

        assert plugin.name == "k8s-rbac"

    @pytest.mark.requirement("FR-002")
    def test_plugin_version(self) -> None:
        """Test plugin version property."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()

        assert plugin.version == "0.1.0"

    @pytest.mark.requirement("FR-002")
    def test_plugin_floe_api_version(self) -> None:
        """Test plugin floe_api_version property."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()

        assert plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("FR-002")
    def test_plugin_inherits_from_rbac_plugin(self) -> None:
        """Test K8sRBACPlugin inherits from RBACPlugin ABC."""
        from floe_core.plugins.rbac import RBACPlugin

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()

        assert isinstance(plugin, RBACPlugin)


class TestGenerateServiceAccount:
    """Unit tests for generate_service_account method."""

    @pytest.mark.requirement("FR-003")
    def test_generate_service_account_basic(self) -> None:
        """Test generating basic ServiceAccount manifest."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = ServiceAccountConfig(
            name="floe-job-runner",
            namespace="floe-jobs",
        )

        manifest = plugin.generate_service_account(config)

        assert manifest["kind"] == "ServiceAccount"
        assert manifest["apiVersion"] == "v1"
        assert manifest["metadata"]["name"] == "floe-job-runner"
        assert manifest["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-003")
    def test_generate_service_account_automount_token_false(self) -> None:
        """Test ServiceAccount has automountServiceAccountToken: false by default."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = ServiceAccountConfig(
            name="floe-test-sa",
            namespace="default",
        )

        manifest = plugin.generate_service_account(config)

        assert manifest["automountServiceAccountToken"] is False

    @pytest.mark.requirement("FR-003")
    def test_generate_service_account_with_labels(self) -> None:
        """Test ServiceAccount with custom labels."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = ServiceAccountConfig(
            name="floe-custom-sa",
            namespace="floe-jobs",
            labels={"custom": "label"},
        )

        manifest = plugin.generate_service_account(config)

        assert manifest["metadata"]["labels"]["custom"] == "label"


class TestGenerateRole:
    """Unit tests for generate_role method."""

    @pytest.mark.requirement("FR-003")
    def test_generate_role_basic(self) -> None:
        """Test generating basic Role manifest."""
        from floe_core.schemas.rbac import RoleConfig, RoleRule

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        rule = RoleRule(resources=["secrets"], verbs=["get"])
        config = RoleConfig(
            name="floe-reader-role",
            namespace="floe-jobs",
            rules=[rule],
        )

        manifest = plugin.generate_role(config)

        assert manifest["kind"] == "Role"
        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"
        assert manifest["metadata"]["name"] == "floe-reader-role"
        assert len(manifest["rules"]) == 1

    @pytest.mark.requirement("FR-003")
    def test_generate_role_with_resource_names(self) -> None:
        """Test Role with resourceNames constraint."""
        from floe_core.schemas.rbac import RoleConfig, RoleRule

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        rule = RoleRule(
            resources=["secrets"],
            verbs=["get"],
            resource_names=["snowflake-creds", "catalog-creds"],
        )
        config = RoleConfig(
            name="floe-secret-reader-role",
            namespace="floe-jobs",
            rules=[rule],
        )

        manifest = plugin.generate_role(config)

        assert manifest["rules"][0]["resourceNames"] == [
            "snowflake-creds",
            "catalog-creds",
        ]


class TestGenerateRoleBinding:
    """Unit tests for generate_role_binding method."""

    @pytest.mark.requirement("FR-003")
    def test_generate_role_binding_basic(self) -> None:
        """Test generating basic RoleBinding manifest."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        subject = RoleBindingSubject(
            name="floe-job-runner",
            namespace="floe-jobs",
        )
        config = RoleBindingConfig(
            name="floe-reader-binding",
            namespace="floe-jobs",
            subjects=[subject],
            role_name="floe-reader-role",
        )

        manifest = plugin.generate_role_binding(config)

        assert manifest["kind"] == "RoleBinding"
        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"
        assert manifest["roleRef"]["name"] == "floe-reader-role"

    @pytest.mark.requirement("FR-003")
    def test_generate_role_binding_multiple_subjects(self) -> None:
        """Test RoleBinding with multiple subjects."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        subjects = [
            RoleBindingSubject(name="floe-sa-1", namespace="ns-1"),
            RoleBindingSubject(name="floe-sa-2", namespace="ns-2"),
        ]
        config = RoleBindingConfig(
            name="floe-multi-binding",
            namespace="floe-jobs",
            subjects=subjects,
            role_name="floe-shared-role",
        )

        manifest = plugin.generate_role_binding(config)

        assert len(manifest["subjects"]) == 2


class TestGenerateNamespace:
    """Unit tests for generate_namespace method."""

    @pytest.mark.requirement("FR-003")
    def test_generate_namespace_basic(self) -> None:
        """Test generating basic Namespace manifest."""
        from floe_core.schemas.rbac import NamespaceConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = NamespaceConfig(
            name="floe-jobs",
            layer="4",
        )

        manifest = plugin.generate_namespace(config)

        assert manifest["kind"] == "Namespace"
        assert manifest["apiVersion"] == "v1"
        assert manifest["metadata"]["name"] == "floe-jobs"

    @pytest.mark.requirement("FR-003")
    def test_generate_namespace_with_pss_enforce(self) -> None:
        """Test Namespace with PSS enforce label."""
        from floe_core.schemas.rbac import NamespaceConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = NamespaceConfig(
            name="floe-jobs",
            layer="4",
            pss_enforce="restricted",
        )

        manifest = plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

    @pytest.mark.requirement("FR-003")
    def test_generate_namespace_pss_all_levels(self) -> None:
        """Test Namespace with all PSS levels set."""
        from floe_core.schemas.rbac import NamespaceConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = NamespaceConfig(
            name="floe-jobs",
            layer="4",
            pss_enforce="restricted",
            pss_audit="restricted",
            pss_warn="restricted",
        )

        manifest = plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"
        assert labels["pod-security.kubernetes.io/audit"] == "restricted"
        assert labels["pod-security.kubernetes.io/warn"] == "restricted"


class TestGeneratePodSecurityContext:
    """Unit tests for generate_pod_security_context method."""

    @pytest.mark.requirement("FR-043")
    def test_generate_pod_security_context_default(self) -> None:
        """Test generating default pod security context."""
        from floe_core.schemas.rbac import PodSecurityConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = PodSecurityConfig()

        contexts = plugin.generate_pod_security_context(config)

        assert "pod" in contexts
        assert "container" in contexts
        assert "volumes" in contexts
        assert "volumeMounts" in contexts

    @pytest.mark.requirement("FR-043")
    def test_generate_pod_security_context_values(self) -> None:
        """Test pod security context has PSS-restricted values."""
        from floe_core.schemas.rbac import PodSecurityConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = PodSecurityConfig()

        contexts = plugin.generate_pod_security_context(config)

        # Pod level
        assert contexts["pod"]["runAsNonRoot"] is True

        # Container level
        assert contexts["container"]["allowPrivilegeEscalation"] is False
        assert contexts["container"]["readOnlyRootFilesystem"] is True

    @pytest.mark.requirement("FR-043")
    def test_generate_pod_security_context_volumes(self) -> None:
        """Test default volumes include /tmp."""
        from floe_core.schemas.rbac import PodSecurityConfig

        from floe_rbac_k8s.plugin import K8sRBACPlugin

        plugin = K8sRBACPlugin()
        config = PodSecurityConfig()

        contexts = plugin.generate_pod_security_context(config)

        # Should have at least /tmp volume
        assert len(contexts["volumes"]) >= 1
        assert len(contexts["volumeMounts"]) >= 1

        # Check /tmp is included
        mount_paths = {m["mountPath"] for m in contexts["volumeMounts"]}
        assert "/tmp" in mount_paths


class TestPluginModuleExports:
    """Unit tests for plugin module exports."""

    @pytest.mark.requirement("FR-002")
    def test_plugin_importable_from_package(self) -> None:
        """Test K8sRBACPlugin can be imported from package."""
        from floe_rbac_k8s import K8sRBACPlugin

        assert K8sRBACPlugin is not None

    @pytest.mark.requirement("FR-002")
    def test_plugin_in_module_all(self) -> None:
        """Test K8sRBACPlugin is in __all__."""
        import floe_rbac_k8s

        assert "K8sRBACPlugin" in floe_rbac_k8s.__all__

    @pytest.mark.requirement("FR-002")
    def test_invalid_attribute_raises_error(self) -> None:
        """Test accessing invalid attribute raises AttributeError."""
        import floe_rbac_k8s

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = floe_rbac_k8s.NonExistentAttribute  # type: ignore[attr-defined]

    @pytest.mark.requirement("FR-002")
    def test_module_version(self) -> None:
        """Test module has version attribute."""
        import floe_rbac_k8s

        assert hasattr(floe_rbac_k8s, "__version__")
        assert floe_rbac_k8s.__version__ == "0.1.0"
