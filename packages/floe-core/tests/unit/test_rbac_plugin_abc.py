"""Unit tests for RBACPlugin abstract base class.

Tests the RBACPlugin ABC contract and default implementations.

Task: T016
Requirements: CR-001, CR-002, CR-003, CR-004
Contract: specs/7b-k8s-rbac/contracts/rbac-plugin-interface.md
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugins.rbac import RBACPlugin
from floe_core.schemas.rbac import (
    NamespaceConfig,
    PodSecurityConfig,
    RoleBindingConfig,
    RoleBindingSubject,
    RoleConfig,
    RoleRule,
    ServiceAccountConfig,
)


class ConcreteRBACPlugin(RBACPlugin):
    """Concrete implementation of RBACPlugin for testing.

    This minimal implementation satisfies all abstract methods to allow
    instantiation for testing purposes.
    """

    @property
    def name(self) -> str:
        """Return plugin name."""
        return "test-rbac"

    @property
    def version(self) -> str:
        """Return plugin version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Return floe API version."""
        return "1.0"

    def generate_service_account(
        self,
        config: ServiceAccountConfig,
    ) -> dict[str, Any]:
        """Generate ServiceAccount manifest from config."""
        return config.to_k8s_manifest()

    def generate_role(
        self,
        config: RoleConfig,
    ) -> dict[str, Any]:
        """Generate Role manifest from config."""
        return config.to_k8s_manifest()

    def generate_role_binding(
        self,
        config: RoleBindingConfig,
    ) -> dict[str, Any]:
        """Generate RoleBinding manifest from config."""
        return config.to_k8s_manifest()

    def generate_namespace(
        self,
        config: NamespaceConfig,
    ) -> dict[str, Any]:
        """Generate Namespace manifest from config."""
        return config.to_k8s_manifest()


@pytest.fixture
def rbac_plugin() -> ConcreteRBACPlugin:
    """Create a concrete RBAC plugin instance for testing."""
    return ConcreteRBACPlugin()


@pytest.fixture
def service_account_config() -> ServiceAccountConfig:
    """Create a sample ServiceAccountConfig for testing."""
    return ServiceAccountConfig(
        name="floe-test-sa",
        namespace="floe-jobs",
    )


@pytest.fixture
def role_config() -> RoleConfig:
    """Create a sample RoleConfig for testing."""
    return RoleConfig(
        name="floe-test-role",
        namespace="floe-jobs",
        rules=[
            RoleRule(
                api_groups=[""],
                resources=["pods"],
                verbs=["get", "list"],
            ),
        ],
    )


@pytest.fixture
def role_binding_config() -> RoleBindingConfig:
    """Create a sample RoleBindingConfig for testing."""
    return RoleBindingConfig(
        name="floe-test-binding",
        namespace="floe-jobs",
        subjects=[
            RoleBindingSubject(
                name="floe-test-sa",
                namespace="floe-jobs",
            ),
        ],
        role_name="floe-test-role",
    )


@pytest.fixture
def namespace_config() -> NamespaceConfig:
    """Create a sample NamespaceConfig for testing."""
    return NamespaceConfig(
        name="floe-jobs",
        layer="4",
    )


@pytest.fixture
def pod_security_config() -> PodSecurityConfig:
    """Create a sample PodSecurityConfig for testing."""
    return PodSecurityConfig()


class TestRBACPluginInheritance:
    """Unit tests for RBACPlugin inheritance."""

    @pytest.mark.requirement("CR-001")
    def test_rbac_plugin_extends_plugin_metadata(self) -> None:
        """Test RBACPlugin inherits from PluginMetadata."""
        assert issubclass(RBACPlugin, PluginMetadata)

    @pytest.mark.requirement("CR-001")
    def test_concrete_plugin_is_instance_of_rbac_plugin(
        self,
        rbac_plugin: ConcreteRBACPlugin,
    ) -> None:
        """Test concrete implementation is instance of RBACPlugin."""
        assert isinstance(rbac_plugin, RBACPlugin)

    @pytest.mark.requirement("CR-001")
    def test_concrete_plugin_is_instance_of_plugin_metadata(
        self,
        rbac_plugin: ConcreteRBACPlugin,
    ) -> None:
        """Test concrete implementation is instance of PluginMetadata."""
        assert isinstance(rbac_plugin, PluginMetadata)


class TestRBACPluginMetadataProperties:
    """Unit tests for RBACPlugin metadata properties."""

    @pytest.mark.requirement("CR-001")
    def test_plugin_has_name_property(
        self,
        rbac_plugin: ConcreteRBACPlugin,
    ) -> None:
        """Test plugin exposes name property."""
        assert rbac_plugin.name == "test-rbac"

    @pytest.mark.requirement("CR-001")
    def test_plugin_has_version_property(
        self,
        rbac_plugin: ConcreteRBACPlugin,
    ) -> None:
        """Test plugin exposes version property."""
        assert rbac_plugin.version == "1.0.0"

    @pytest.mark.requirement("CR-001")
    def test_plugin_has_floe_api_version_property(
        self,
        rbac_plugin: ConcreteRBACPlugin,
    ) -> None:
        """Test plugin exposes floe_api_version property."""
        assert rbac_plugin.floe_api_version == "1.0"


class TestRBACPluginAbstractMethods:
    """Unit tests for RBACPlugin abstract method signatures."""

    @pytest.mark.requirement("CR-001")
    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test RBACPlugin cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            RBACPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("CR-001")
    def test_generate_service_account_is_abstract(self) -> None:
        """Test generate_service_account is an abstract method."""
        # Check that RBACPlugin defines generate_service_account
        assert hasattr(RBACPlugin, "generate_service_account")

    @pytest.mark.requirement("CR-001")
    def test_generate_role_is_abstract(self) -> None:
        """Test generate_role is an abstract method."""
        assert hasattr(RBACPlugin, "generate_role")

    @pytest.mark.requirement("CR-001")
    def test_generate_role_binding_is_abstract(self) -> None:
        """Test generate_role_binding is an abstract method."""
        assert hasattr(RBACPlugin, "generate_role_binding")

    @pytest.mark.requirement("CR-001")
    def test_generate_namespace_is_abstract(self) -> None:
        """Test generate_namespace is an abstract method."""
        assert hasattr(RBACPlugin, "generate_namespace")


class TestRBACPluginGenerateServiceAccount:
    """Unit tests for generate_service_account method."""

    @pytest.mark.requirement("CR-001")
    def test_returns_dict(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        service_account_config: ServiceAccountConfig,
    ) -> None:
        """Test generate_service_account returns a dict."""
        result = rbac_plugin.generate_service_account(service_account_config)
        assert isinstance(result, dict)

    @pytest.mark.requirement("CR-001")
    def test_result_has_api_version(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        service_account_config: ServiceAccountConfig,
    ) -> None:
        """Test result includes apiVersion."""
        result = rbac_plugin.generate_service_account(service_account_config)
        assert result["apiVersion"] == "v1"

    @pytest.mark.requirement("CR-001")
    def test_result_has_kind(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        service_account_config: ServiceAccountConfig,
    ) -> None:
        """Test result includes kind: ServiceAccount."""
        result = rbac_plugin.generate_service_account(service_account_config)
        assert result["kind"] == "ServiceAccount"

    @pytest.mark.requirement("CR-003")
    def test_result_has_managed_by_label(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        service_account_config: ServiceAccountConfig,
    ) -> None:
        """Test result includes managed-by label (CR-003)."""
        result = rbac_plugin.generate_service_account(service_account_config)
        labels = result["metadata"]["labels"]
        assert labels["app.kubernetes.io/managed-by"] == "floe"


class TestRBACPluginGenerateRole:
    """Unit tests for generate_role method."""

    @pytest.mark.requirement("CR-001")
    def test_returns_dict(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_config: RoleConfig,
    ) -> None:
        """Test generate_role returns a dict."""
        result = rbac_plugin.generate_role(role_config)
        assert isinstance(result, dict)

    @pytest.mark.requirement("CR-001")
    def test_result_has_api_version(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_config: RoleConfig,
    ) -> None:
        """Test result includes apiVersion."""
        result = rbac_plugin.generate_role(role_config)
        assert result["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("CR-001")
    def test_result_has_kind(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_config: RoleConfig,
    ) -> None:
        """Test result includes kind: Role."""
        result = rbac_plugin.generate_role(role_config)
        assert result["kind"] == "Role"

    @pytest.mark.requirement("CR-002")
    def test_result_rules_have_no_wildcards(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_config: RoleConfig,
    ) -> None:
        """Test result rules do not contain wildcards (CR-002)."""
        result = rbac_plugin.generate_role(role_config)

        for rule in result["rules"]:
            assert "*" not in rule["apiGroups"]
            assert "*" not in rule["resources"]
            assert "*" not in rule["verbs"]


class TestRBACPluginGenerateRoleBinding:
    """Unit tests for generate_role_binding method."""

    @pytest.mark.requirement("CR-001")
    def test_returns_dict(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_binding_config: RoleBindingConfig,
    ) -> None:
        """Test generate_role_binding returns a dict."""
        result = rbac_plugin.generate_role_binding(role_binding_config)
        assert isinstance(result, dict)

    @pytest.mark.requirement("CR-001")
    def test_result_has_api_version(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_binding_config: RoleBindingConfig,
    ) -> None:
        """Test result includes apiVersion."""
        result = rbac_plugin.generate_role_binding(role_binding_config)
        assert result["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("CR-001")
    def test_result_has_kind(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_binding_config: RoleBindingConfig,
    ) -> None:
        """Test result includes kind: RoleBinding."""
        result = rbac_plugin.generate_role_binding(role_binding_config)
        assert result["kind"] == "RoleBinding"

    @pytest.mark.requirement("CR-001")
    def test_result_has_subjects(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_binding_config: RoleBindingConfig,
    ) -> None:
        """Test result includes subjects array."""
        result = rbac_plugin.generate_role_binding(role_binding_config)
        assert "subjects" in result
        assert len(result["subjects"]) >= 1

    @pytest.mark.requirement("CR-001")
    def test_result_has_role_ref(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        role_binding_config: RoleBindingConfig,
    ) -> None:
        """Test result includes roleRef."""
        result = rbac_plugin.generate_role_binding(role_binding_config)
        assert "roleRef" in result
        assert result["roleRef"]["kind"] == "Role"


class TestRBACPluginGenerateNamespace:
    """Unit tests for generate_namespace method."""

    @pytest.mark.requirement("CR-001")
    def test_returns_dict(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        namespace_config: NamespaceConfig,
    ) -> None:
        """Test generate_namespace returns a dict."""
        result = rbac_plugin.generate_namespace(namespace_config)
        assert isinstance(result, dict)

    @pytest.mark.requirement("CR-001")
    def test_result_has_api_version(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        namespace_config: NamespaceConfig,
    ) -> None:
        """Test result includes apiVersion: v1."""
        result = rbac_plugin.generate_namespace(namespace_config)
        assert result["apiVersion"] == "v1"

    @pytest.mark.requirement("CR-001")
    def test_result_has_kind(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        namespace_config: NamespaceConfig,
    ) -> None:
        """Test result includes kind: Namespace."""
        result = rbac_plugin.generate_namespace(namespace_config)
        assert result["kind"] == "Namespace"

    @pytest.mark.requirement("CR-004")
    def test_result_has_pss_enforce_label(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        namespace_config: NamespaceConfig,
    ) -> None:
        """Test result includes PSS enforce label (CR-004)."""
        result = rbac_plugin.generate_namespace(namespace_config)
        labels = result["metadata"]["labels"]
        assert "pod-security.kubernetes.io/enforce" in labels

    @pytest.mark.requirement("CR-004")
    def test_result_has_pss_audit_label(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        namespace_config: NamespaceConfig,
    ) -> None:
        """Test result includes PSS audit label (CR-004)."""
        result = rbac_plugin.generate_namespace(namespace_config)
        labels = result["metadata"]["labels"]
        assert "pod-security.kubernetes.io/audit" in labels

    @pytest.mark.requirement("CR-004")
    def test_result_has_pss_warn_label(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        namespace_config: NamespaceConfig,
    ) -> None:
        """Test result includes PSS warn label (CR-004)."""
        result = rbac_plugin.generate_namespace(namespace_config)
        labels = result["metadata"]["labels"]
        assert "pod-security.kubernetes.io/warn" in labels

    @pytest.mark.requirement("CR-004")
    def test_result_has_layer_label(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        namespace_config: NamespaceConfig,
    ) -> None:
        """Test result includes floe.dev/layer label (CR-004)."""
        result = rbac_plugin.generate_namespace(namespace_config)
        labels = result["metadata"]["labels"]
        assert "floe.dev/layer" in labels


class TestRBACPluginGeneratePodSecurityContext:
    """Unit tests for generate_pod_security_context default implementation."""

    @pytest.mark.requirement("CR-001")
    def test_method_exists(self, rbac_plugin: ConcreteRBACPlugin) -> None:
        """Test generate_pod_security_context method exists."""
        assert hasattr(rbac_plugin, "generate_pod_security_context")

    @pytest.mark.requirement("CR-001")
    def test_returns_dict(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test method returns a dict."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert isinstance(result, dict)

    @pytest.mark.requirement("CR-001")
    def test_result_has_pod_key(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test result has 'pod' key."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert "pod" in result

    @pytest.mark.requirement("CR-001")
    def test_result_has_container_key(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test result has 'container' key."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert "container" in result

    @pytest.mark.requirement("CR-001")
    def test_pod_context_has_run_as_non_root(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test pod context includes runAsNonRoot."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert result["pod"]["runAsNonRoot"] is True

    @pytest.mark.requirement("CR-001")
    def test_pod_context_has_run_as_user(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test pod context includes runAsUser."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert "runAsUser" in result["pod"]

    @pytest.mark.requirement("CR-001")
    def test_pod_context_has_run_as_group(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test pod context includes runAsGroup."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert "runAsGroup" in result["pod"]

    @pytest.mark.requirement("CR-001")
    def test_pod_context_has_fs_group(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test pod context includes fsGroup."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert "fsGroup" in result["pod"]

    @pytest.mark.requirement("CR-001")
    def test_container_context_has_allow_privilege_escalation(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test container context includes allowPrivilegeEscalation."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert result["container"]["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("CR-001")
    def test_container_context_has_read_only_root_filesystem(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test container context includes readOnlyRootFilesystem."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert result["container"]["readOnlyRootFilesystem"] is True

    @pytest.mark.requirement("CR-001")
    def test_container_context_drops_all_capabilities(
        self,
        rbac_plugin: ConcreteRBACPlugin,
        pod_security_config: PodSecurityConfig,
    ) -> None:
        """Test container context drops ALL capabilities."""
        result = rbac_plugin.generate_pod_security_context(pod_security_config)
        assert result["container"]["capabilities"]["drop"] == ["ALL"]


class TestRBACPluginDefaultImplementationCanBeOverridden:
    """Unit tests for verifying default implementation can be overridden."""

    @pytest.mark.requirement("CR-001")
    def test_generate_pod_security_context_can_be_overridden(self) -> None:
        """Test that generate_pod_security_context can be overridden."""

        class CustomRBACPlugin(RBACPlugin):
            """Custom plugin with overridden security context."""

            @property
            def name(self) -> str:
                return "custom"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def generate_service_account(
                self,
                config: ServiceAccountConfig,
            ) -> dict[str, Any]:
                return config.to_k8s_manifest()

            def generate_role(
                self,
                config: RoleConfig,
            ) -> dict[str, Any]:
                return config.to_k8s_manifest()

            def generate_role_binding(
                self,
                config: RoleBindingConfig,
            ) -> dict[str, Any]:
                return config.to_k8s_manifest()

            def generate_namespace(
                self,
                config: NamespaceConfig,
            ) -> dict[str, Any]:
                return config.to_k8s_manifest()

            def generate_pod_security_context(
                self,
                config: PodSecurityConfig,
            ) -> dict[str, Any]:
                """Custom implementation with additional fields."""
                base = super().generate_pod_security_context(config)
                base["custom_field"] = "custom_value"
                return base

        plugin = CustomRBACPlugin()
        config = PodSecurityConfig()
        result = plugin.generate_pod_security_context(config)

        # Verify custom field was added
        assert result["custom_field"] == "custom_value"
        # Verify base implementation still works
        assert result["pod"]["runAsNonRoot"] is True
        assert result["container"]["capabilities"]["drop"] == ["ALL"]
