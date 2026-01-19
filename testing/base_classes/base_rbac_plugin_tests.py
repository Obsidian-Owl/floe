"""Base test class for RBACPlugin compliance testing.

This module provides BaseRBACPluginTests, an abstract test class that
validates RBACPlugin implementations meet all interface requirements.

Plugin implementations MUST pass all tests in this class to be considered
compliant with the RBACPlugin ABC.

Usage:
    1. Create a test class that inherits from BaseRBACPluginTests
    2. Implement the rbac_plugin fixture to return your plugin instance
    3. Run pytest - all base tests will be executed automatically

Example:
    >>> import pytest
    >>> from testing.base_classes import BaseRBACPluginTests
    >>> from floe_rbac_k8s import K8sRBACPlugin
    >>>
    >>> class TestK8sRBACPlugin(BaseRBACPluginTests):
    ...     @pytest.fixture
    ...     def rbac_plugin(self) -> K8sRBACPlugin:
    ...         return K8sRBACPlugin()

Requirements Covered:
    - FR-001: RBACPlugin ABC implementation
    - FR-003: PluginMetadata inheritance
    - FR-010-014: ServiceAccount generation
    - FR-020-024: Role generation
    - FR-022-023: RoleBinding generation
    - FR-030-034: Namespace generation
    - FR-040-044: Pod security context generation
    - FR-070: No wildcard permissions
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.plugins.rbac import RBACPlugin


class BaseRBACPluginTests(ABC):
    """Abstract base test class for RBACPlugin implementations.

    Subclasses must implement the rbac_plugin fixture to provide
    an instance of their RBACPlugin implementation.

    All tests use @pytest.mark.requirement() for traceability.

    Attributes:
        rbac_plugin: Fixture that returns the plugin under test.

    Example:
        >>> class TestK8sRBACPlugin(BaseRBACPluginTests):
        ...     @pytest.fixture
        ...     def rbac_plugin(self):
        ...         return K8sRBACPlugin()
    """

    @pytest.fixture
    @abstractmethod
    def rbac_plugin(self) -> RBACPlugin:
        """Return an instance of the RBACPlugin to test.

        Subclasses MUST implement this fixture to provide their
        concrete plugin implementation.

        Returns:
            A configured RBACPlugin instance ready for testing.
        """
        ...

    # =========================================================================
    # Plugin Metadata Tests (FR-001, FR-003)
    # =========================================================================

    @pytest.mark.requirement("FR-001")
    def test_has_name_property(self, rbac_plugin: RBACPlugin) -> None:
        """Verify plugin has a name property.

        All plugins must have a unique name identifier.
        """
        assert hasattr(rbac_plugin, "name")
        assert isinstance(rbac_plugin.name, str)
        assert len(rbac_plugin.name) > 0

    @pytest.mark.requirement("FR-003")
    def test_has_version_property(self, rbac_plugin: RBACPlugin) -> None:
        """Verify plugin has a version property.

        Plugin version should follow semantic versioning.
        """
        assert hasattr(rbac_plugin, "version")
        assert isinstance(rbac_plugin.version, str)
        assert len(rbac_plugin.version) > 0

    @pytest.mark.requirement("FR-003")
    def test_has_floe_api_version_property(self, rbac_plugin: RBACPlugin) -> None:
        """Verify plugin declares compatible floe API version.

        This is used to check plugin compatibility with the platform.
        """
        assert hasattr(rbac_plugin, "floe_api_version")
        assert isinstance(rbac_plugin.floe_api_version, str)
        assert len(rbac_plugin.floe_api_version) > 0

    # =========================================================================
    # Core Method Tests (FR-001)
    # =========================================================================

    @pytest.mark.requirement("FR-001")
    def test_has_generate_service_account_method(self, rbac_plugin: RBACPlugin) -> None:
        """Verify plugin has generate_service_account() method."""
        assert hasattr(rbac_plugin, "generate_service_account")
        assert callable(rbac_plugin.generate_service_account)

    @pytest.mark.requirement("FR-001")
    def test_has_generate_role_method(self, rbac_plugin: RBACPlugin) -> None:
        """Verify plugin has generate_role() method."""
        assert hasattr(rbac_plugin, "generate_role")
        assert callable(rbac_plugin.generate_role)

    @pytest.mark.requirement("FR-001")
    def test_has_generate_role_binding_method(self, rbac_plugin: RBACPlugin) -> None:
        """Verify plugin has generate_role_binding() method."""
        assert hasattr(rbac_plugin, "generate_role_binding")
        assert callable(rbac_plugin.generate_role_binding)

    @pytest.mark.requirement("FR-001")
    def test_has_generate_namespace_method(self, rbac_plugin: RBACPlugin) -> None:
        """Verify plugin has generate_namespace() method."""
        assert hasattr(rbac_plugin, "generate_namespace")
        assert callable(rbac_plugin.generate_namespace)

    @pytest.mark.requirement("FR-001")
    def test_has_generate_pod_security_context_method(self, rbac_plugin: RBACPlugin) -> None:
        """Verify plugin has generate_pod_security_context() method."""
        assert hasattr(rbac_plugin, "generate_pod_security_context")
        assert callable(rbac_plugin.generate_pod_security_context)

    # =========================================================================
    # ServiceAccount Generation Tests (FR-010, FR-011, FR-013)
    # =========================================================================

    @pytest.mark.requirement("FR-010")
    def test_generate_service_account_has_correct_api_version(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify generated ServiceAccount has correct apiVersion."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        config = ServiceAccountConfig(name="floe-test-runner", namespace="floe-jobs")
        manifest = rbac_plugin.generate_service_account(config)

        assert manifest["apiVersion"] == "v1"

    @pytest.mark.requirement("FR-010")
    def test_generate_service_account_has_correct_kind(self, rbac_plugin: RBACPlugin) -> None:
        """Verify generated ServiceAccount has correct kind."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        config = ServiceAccountConfig(name="floe-test-runner", namespace="floe-jobs")
        manifest = rbac_plugin.generate_service_account(config)

        assert manifest["kind"] == "ServiceAccount"

    @pytest.mark.requirement("FR-013")
    def test_generate_service_account_has_managed_by_label(self, rbac_plugin: RBACPlugin) -> None:
        """Verify generated ServiceAccount has floe managed-by label."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        config = ServiceAccountConfig(name="floe-test-runner", namespace="floe-jobs")
        manifest = rbac_plugin.generate_service_account(config)

        assert "labels" in manifest["metadata"]
        assert manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-011")
    def test_generate_service_account_respects_automount_setting(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify automountServiceAccountToken matches config."""
        from floe_core.schemas.rbac import ServiceAccountConfig

        # Default: False (least privilege)
        config_no_mount = ServiceAccountConfig(
            name="floe-test-runner", namespace="floe-jobs", automount_token=False
        )
        manifest = rbac_plugin.generate_service_account(config_no_mount)
        assert manifest["automountServiceAccountToken"] is False

        # Explicit: True for K8s API access
        config_mount = ServiceAccountConfig(
            name="floe-k8s-runner", namespace="floe-jobs", automount_token=True
        )
        manifest = rbac_plugin.generate_service_account(config_mount)
        assert manifest["automountServiceAccountToken"] is True

    # =========================================================================
    # Role Generation Tests (FR-020, FR-021, FR-024, FR-070)
    # =========================================================================

    @pytest.mark.requirement("FR-020")
    def test_generate_role_has_correct_api_version(self, rbac_plugin: RBACPlugin) -> None:
        """Verify generated Role has correct apiVersion."""
        from floe_core.schemas.rbac import RoleConfig, RoleRule

        config = RoleConfig(
            name="floe-test-runner-role",
            namespace="floe-jobs",
            rules=[RoleRule(resources=["secrets"], verbs=["get"])],
        )
        manifest = rbac_plugin.generate_role(config)

        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-020")
    def test_generate_role_has_correct_kind(self, rbac_plugin: RBACPlugin) -> None:
        """Verify generated Role has correct kind."""
        from floe_core.schemas.rbac import RoleConfig, RoleRule

        config = RoleConfig(
            name="floe-test-runner-role",
            namespace="floe-jobs",
            rules=[RoleRule(resources=["secrets"], verbs=["get"])],
        )
        manifest = rbac_plugin.generate_role(config)

        assert manifest["kind"] == "Role"

    @pytest.mark.requirement("FR-021")
    def test_generate_role_includes_resource_names_when_specified(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify Role includes resourceNames for specific secret access."""
        from floe_core.schemas.rbac import RoleConfig, RoleRule

        config = RoleConfig(
            name="floe-test-runner-role",
            namespace="floe-jobs",
            rules=[
                RoleRule(
                    resources=["secrets"],
                    verbs=["get"],
                    resource_names=["my-secret", "other-secret"],
                )
            ],
        )
        manifest = rbac_plugin.generate_role(config)

        assert "resourceNames" in manifest["rules"][0]
        assert manifest["rules"][0]["resourceNames"] == ["my-secret", "other-secret"]

    @pytest.mark.requirement("FR-024")
    def test_generate_role_allows_only_get_for_secrets(self, rbac_plugin: RBACPlugin) -> None:
        """Verify Role can be generated with only get verb for secrets."""
        from floe_core.schemas.rbac import RoleConfig, RoleRule

        config = RoleConfig(
            name="floe-test-runner-role",
            namespace="floe-jobs",
            rules=[RoleRule(resources=["secrets"], verbs=["get"])],
        )
        manifest = rbac_plugin.generate_role(config)

        # Should only have get verb
        assert manifest["rules"][0]["verbs"] == ["get"]

    @pytest.mark.requirement("FR-070")
    def test_role_rule_rejects_wildcard_resources(self, rbac_plugin: RBACPlugin) -> None:
        """Verify RoleRule rejects wildcard (*) in resources."""
        from floe_core.schemas.rbac import RoleRule
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Wildcard permissions"):
            RoleRule(resources=["*"], verbs=["get"])

    @pytest.mark.requirement("FR-070")
    def test_role_rule_rejects_wildcard_verbs(self, rbac_plugin: RBACPlugin) -> None:
        """Verify RoleRule rejects wildcard (*) in verbs."""
        from floe_core.schemas.rbac import RoleRule
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Wildcard permissions"):
            RoleRule(resources=["secrets"], verbs=["*"])

    @pytest.mark.requirement("FR-070")
    def test_role_rule_rejects_wildcard_api_groups(self, rbac_plugin: RBACPlugin) -> None:
        """Verify RoleRule rejects wildcard (*) in apiGroups."""
        from floe_core.schemas.rbac import RoleRule
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Wildcard permissions"):
            RoleRule(api_groups=["*"], resources=["secrets"], verbs=["get"])

    # =========================================================================
    # RoleBinding Generation Tests (FR-022, FR-023)
    # =========================================================================

    @pytest.mark.requirement("FR-022")
    def test_generate_role_binding_has_correct_api_version(self, rbac_plugin: RBACPlugin) -> None:
        """Verify generated RoleBinding has correct apiVersion."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-test-runner-binding",
            namespace="floe-jobs",
            subjects=[RoleBindingSubject(name="floe-test-runner", namespace="floe-jobs")],
            role_name="floe-test-runner-role",
        )
        manifest = rbac_plugin.generate_role_binding(config)

        assert manifest["apiVersion"] == "rbac.authorization.k8s.io/v1"

    @pytest.mark.requirement("FR-022")
    def test_generate_role_binding_has_correct_kind(self, rbac_plugin: RBACPlugin) -> None:
        """Verify generated RoleBinding has correct kind."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-test-runner-binding",
            namespace="floe-jobs",
            subjects=[RoleBindingSubject(name="floe-test-runner", namespace="floe-jobs")],
            role_name="floe-test-runner-role",
        )
        manifest = rbac_plugin.generate_role_binding(config)

        assert manifest["kind"] == "RoleBinding"

    @pytest.mark.requirement("FR-022")
    def test_generate_role_binding_has_correct_role_ref(self, rbac_plugin: RBACPlugin) -> None:
        """Verify RoleBinding references the correct Role."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-test-runner-binding",
            namespace="floe-jobs",
            subjects=[RoleBindingSubject(name="floe-test-runner", namespace="floe-jobs")],
            role_name="floe-test-runner-role",
        )
        manifest = rbac_plugin.generate_role_binding(config)

        assert manifest["roleRef"]["kind"] == "Role"
        assert manifest["roleRef"]["name"] == "floe-test-runner-role"
        assert manifest["roleRef"]["apiGroup"] == "rbac.authorization.k8s.io"

    @pytest.mark.requirement("FR-023")
    def test_generate_role_binding_supports_cross_namespace_subjects(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify RoleBinding supports subjects from different namespaces."""
        from floe_core.schemas.rbac import RoleBindingConfig, RoleBindingSubject

        config = RoleBindingConfig(
            name="floe-dagster-binding",
            namespace="floe-jobs",
            subjects=[RoleBindingSubject(name="floe-dagster", namespace="floe-platform")],
            role_name="floe-job-creator-role",
        )
        manifest = rbac_plugin.generate_role_binding(config)

        # Subject should have different namespace than binding
        assert manifest["metadata"]["namespace"] == "floe-jobs"
        assert manifest["subjects"][0]["namespace"] == "floe-platform"

    # =========================================================================
    # Namespace Generation Tests (FR-030, FR-031, FR-032, FR-034)
    # =========================================================================

    @pytest.mark.requirement("FR-030")
    def test_generate_namespace_has_correct_api_version(self, rbac_plugin: RBACPlugin) -> None:
        """Verify generated Namespace has correct apiVersion."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-test", layer="4")
        manifest = rbac_plugin.generate_namespace(config)

        assert manifest["apiVersion"] == "v1"

    @pytest.mark.requirement("FR-030")
    def test_generate_namespace_has_correct_kind(self, rbac_plugin: RBACPlugin) -> None:
        """Verify generated Namespace has correct kind."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-test", layer="4")
        manifest = rbac_plugin.generate_namespace(config)

        assert manifest["kind"] == "Namespace"

    @pytest.mark.requirement("FR-031")
    def test_generate_namespace_has_pss_enforce_label(self, rbac_plugin: RBACPlugin) -> None:
        """Verify Namespace has PSS enforce label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4", pss_enforce="restricted")
        manifest = rbac_plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]
        assert "pod-security.kubernetes.io/enforce" in labels
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

    @pytest.mark.requirement("FR-031")
    def test_generate_namespace_has_pss_audit_label(self, rbac_plugin: RBACPlugin) -> None:
        """Verify Namespace has PSS audit label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = rbac_plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]
        assert "pod-security.kubernetes.io/audit" in labels

    @pytest.mark.requirement("FR-031")
    def test_generate_namespace_has_pss_warn_label(self, rbac_plugin: RBACPlugin) -> None:
        """Verify Namespace has PSS warn label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = rbac_plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]
        assert "pod-security.kubernetes.io/warn" in labels

    @pytest.mark.requirement("FR-034")
    def test_generate_namespace_has_layer_label(self, rbac_plugin: RBACPlugin) -> None:
        """Verify Namespace has floe.dev/layer label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = rbac_plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]
        assert "floe.dev/layer" in labels
        assert labels["floe.dev/layer"] == "4"

    @pytest.mark.requirement("FR-034")
    def test_generate_namespace_has_managed_by_label(self, rbac_plugin: RBACPlugin) -> None:
        """Verify Namespace has managed-by label."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = rbac_plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]
        assert labels["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-032")
    def test_generate_namespace_platform_defaults_to_baseline(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify platform namespace defaults to baseline PSS level."""
        from floe_core.schemas.rbac import NamespaceConfig

        # Platform namespace (layer 3) should default to baseline
        config = NamespaceConfig(name="floe-platform", layer="3", pss_enforce="baseline")
        manifest = rbac_plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/enforce"] == "baseline"

    # =========================================================================
    # Pod Security Context Tests (FR-040, FR-041, FR-042, FR-043, FR-044)
    # =========================================================================

    @pytest.mark.requirement("FR-040")
    def test_generate_pod_security_context_has_run_as_non_root(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify pod security context includes runAsNonRoot."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = rbac_plugin.generate_pod_security_context(config)

        assert contexts["pod"]["runAsNonRoot"] is True

    @pytest.mark.requirement("FR-044")
    def test_generate_pod_security_context_has_run_as_user(self, rbac_plugin: RBACPlugin) -> None:
        """Verify pod security context includes runAsUser."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(run_as_user=1000)
        contexts = rbac_plugin.generate_pod_security_context(config)

        assert contexts["pod"]["runAsUser"] == 1000

    @pytest.mark.requirement("FR-041")
    def test_generate_container_security_context_has_no_privilege_escalation(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify container context has allowPrivilegeEscalation: false."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = rbac_plugin.generate_pod_security_context(config)

        assert contexts["container"]["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("FR-041")
    def test_generate_container_security_context_drops_all_capabilities(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify container context drops all capabilities."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = rbac_plugin.generate_pod_security_context(config)

        assert contexts["container"]["capabilities"]["drop"] == ["ALL"]

    @pytest.mark.requirement("FR-042")
    def test_generate_pod_security_context_has_seccomp_profile(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify pod security context includes seccompProfile."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = rbac_plugin.generate_pod_security_context(config)

        assert "seccompProfile" in contexts["pod"]
        assert contexts["pod"]["seccompProfile"]["type"] == "RuntimeDefault"

    @pytest.mark.requirement("FR-043")
    def test_generate_container_security_context_has_read_only_filesystem(
        self, rbac_plugin: RBACPlugin
    ) -> None:
        """Verify container context has readOnlyRootFilesystem."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = rbac_plugin.generate_pod_security_context(config)

        assert contexts["container"]["readOnlyRootFilesystem"] is True


# Module exports
__all__ = ["BaseRBACPluginTests"]
