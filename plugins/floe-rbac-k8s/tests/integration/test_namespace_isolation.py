"""Integration tests for namespace isolation.

Tests that K8sRBACPlugin generates Namespace manifests with proper PSS labels
for namespace isolation.

Task: T033
User Story: US2 - Namespace Isolation
Requirements: FR-030, FR-031, FR-032, FR-033, FR-034, FR-040, FR-044
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_rbac_k8s.plugin import K8sRBACPlugin as K8sRBACPluginType


class TestNamespaceIsolation:
    """Integration tests for namespace isolation via PSS labels."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-030")
    def test_jobs_namespace_created_with_pss(self, plugin: K8sRBACPluginType) -> None:
        """Test jobs namespace has PSS labels for isolation."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]

        # PSS enforcement labels for isolation
        assert "pod-security.kubernetes.io/enforce" in labels
        assert "pod-security.kubernetes.io/audit" in labels
        assert "pod-security.kubernetes.io/warn" in labels

    @pytest.mark.requirement("FR-031")
    def test_jobs_namespace_restricted_pss(self, plugin: K8sRBACPluginType) -> None:
        """Test jobs namespace defaults to restricted PSS level."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]

        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"
        assert labels["pod-security.kubernetes.io/audit"] == "restricted"
        assert labels["pod-security.kubernetes.io/warn"] == "restricted"

    @pytest.mark.requirement("FR-033")
    def test_platform_namespace_baseline_pss(self, plugin: K8sRBACPluginType) -> None:
        """Test platform namespace can use baseline PSS level."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(
            name="floe-platform",
            layer="3",
            pss_enforce="baseline",
            pss_audit="baseline",
            pss_warn="baseline",
        )
        manifest = plugin.generate_namespace(config)

        labels = manifest["metadata"]["labels"]

        assert labels["pod-security.kubernetes.io/enforce"] == "baseline"
        assert labels["pod-security.kubernetes.io/audit"] == "baseline"
        assert labels["pod-security.kubernetes.io/warn"] == "baseline"

    @pytest.mark.requirement("FR-034")
    def test_namespaces_have_layer_labels(self, plugin: K8sRBACPluginType) -> None:
        """Test namespaces have layer labels for architecture visibility."""
        from floe_core.schemas.rbac import NamespaceConfig

        # Layer 3 - platform
        platform_config = NamespaceConfig(name="floe-platform", layer="3")
        platform_manifest = plugin.generate_namespace(platform_config)

        assert platform_manifest["metadata"]["labels"]["floe.dev/layer"] == "3"

        # Layer 4 - jobs
        jobs_config = NamespaceConfig(name="floe-jobs", layer="4")
        jobs_manifest = plugin.generate_namespace(jobs_config)

        assert jobs_manifest["metadata"]["labels"]["floe.dev/layer"] == "4"

    @pytest.mark.requirement("FR-034")
    def test_namespaces_have_managed_by_label(self, plugin: K8sRBACPluginType) -> None:
        """Test namespaces have managed-by label for ownership tracking."""
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-test", layer="4")
        manifest = plugin.generate_namespace(config)

        assert manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"


class TestPodSecurityContextIsolation:
    """Integration tests for pod security context isolation."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-040")
    def test_pod_security_context_non_root(self, plugin: K8sRBACPluginType) -> None:
        """Test pod security context enforces non-root execution."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = plugin.generate_pod_security_context(config)

        assert contexts["pod"]["runAsNonRoot"] is True

    @pytest.mark.requirement("FR-041")
    def test_container_context_no_privilege_escalation(self, plugin: K8sRBACPluginType) -> None:
        """Test container context prevents privilege escalation."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = plugin.generate_pod_security_context(config)

        assert contexts["container"]["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("FR-041")
    def test_container_context_drops_all_capabilities(self, plugin: K8sRBACPluginType) -> None:
        """Test container context drops all Linux capabilities."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = plugin.generate_pod_security_context(config)

        assert contexts["container"]["capabilities"]["drop"] == ["ALL"]

    @pytest.mark.requirement("FR-042")
    def test_pod_security_context_seccomp(self, plugin: K8sRBACPluginType) -> None:
        """Test pod security context has seccomp profile."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = plugin.generate_pod_security_context(config)

        assert contexts["pod"]["seccompProfile"]["type"] == "RuntimeDefault"

    @pytest.mark.requirement("FR-043")
    def test_container_context_read_only_filesystem(self, plugin: K8sRBACPluginType) -> None:
        """Test container context uses read-only root filesystem."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = plugin.generate_pod_security_context(config)

        assert contexts["container"]["readOnlyRootFilesystem"] is True

    @pytest.mark.requirement("FR-044")
    def test_pod_security_context_user_group(self, plugin: K8sRBACPluginType) -> None:
        """Test pod security context has user and group settings."""
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig(run_as_user=1000, run_as_group=1000, fs_group=1000)
        contexts = plugin.generate_pod_security_context(config)

        assert contexts["pod"]["runAsUser"] == 1000
        assert contexts["pod"]["runAsGroup"] == 1000
        assert contexts["pod"]["fsGroup"] == 1000


class TestNamespaceIsolationYAMLOutput:
    """Integration tests for YAML output of namespace isolation manifests."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-030")
    def test_namespace_manifest_valid_yaml(self, plugin: K8sRBACPluginType) -> None:
        """Test namespace manifest produces valid YAML."""
        import yaml
        from floe_core.schemas.rbac import NamespaceConfig

        config = NamespaceConfig(name="floe-jobs", layer="4")
        manifest = plugin.generate_namespace(config)

        yaml_str = yaml.dump(manifest, default_flow_style=False)

        # Validate structure
        assert "apiVersion: v1" in yaml_str
        assert "kind: Namespace" in yaml_str
        assert "name: floe-jobs" in yaml_str
        assert "pod-security.kubernetes.io/enforce" in yaml_str

    @pytest.mark.requirement("FR-040")
    def test_security_context_valid_yaml(self, plugin: K8sRBACPluginType) -> None:
        """Test security context produces valid YAML."""
        import yaml
        from floe_core.schemas.rbac import PodSecurityConfig

        config = PodSecurityConfig()
        contexts = plugin.generate_pod_security_context(config)

        pod_yaml = yaml.dump(contexts["pod"], default_flow_style=False)
        container_yaml = yaml.dump(contexts["container"], default_flow_style=False)

        # Pod context structure
        assert "runAsNonRoot: true" in pod_yaml
        assert "runAsUser: 1000" in pod_yaml
        assert "seccompProfile:" in pod_yaml

        # Container context structure
        assert "allowPrivilegeEscalation: false" in container_yaml
        assert "readOnlyRootFilesystem: true" in container_yaml
        assert "capabilities:" in container_yaml


class TestMultipleNamespaceIsolation:
    """Integration tests for multiple namespace isolation scenarios."""

    @pytest.fixture
    def plugin(self) -> K8sRBACPluginType:
        """Return a K8sRBACPlugin instance for testing."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin()

    @pytest.mark.requirement("FR-030")
    def test_multiple_namespaces_different_pss_levels(self, plugin: K8sRBACPluginType) -> None:
        """Test multiple namespaces can have different PSS levels."""
        from floe_core.schemas.rbac import NamespaceConfig

        # Jobs namespace - restricted
        jobs_config = NamespaceConfig(
            name="floe-jobs",
            layer="4",
            pss_enforce="restricted",
        )
        jobs_manifest = plugin.generate_namespace(jobs_config)

        # Platform namespace - baseline
        platform_config = NamespaceConfig(
            name="floe-platform",
            layer="3",
            pss_enforce="baseline",
        )
        platform_manifest = plugin.generate_namespace(platform_config)

        # Verify different enforcement levels
        jobs_labels = jobs_manifest["metadata"]["labels"]
        platform_labels = platform_manifest["metadata"]["labels"]

        assert jobs_labels["pod-security.kubernetes.io/enforce"] == "restricted"
        assert platform_labels["pod-security.kubernetes.io/enforce"] == "baseline"

    @pytest.mark.requirement("FR-032")
    def test_jobs_namespace_isolation_complete(self, plugin: K8sRBACPluginType) -> None:
        """Test jobs namespace has complete isolation configuration."""
        from floe_core.schemas.rbac import NamespaceConfig, PodSecurityConfig

        # Create jobs namespace
        ns_config = NamespaceConfig(name="floe-jobs", layer="4")
        ns_manifest = plugin.generate_namespace(ns_config)

        # Create security context for pods in this namespace
        sec_config = PodSecurityConfig()
        sec_contexts = plugin.generate_pod_security_context(sec_config)

        # Namespace has PSS labels
        labels = ns_manifest["metadata"]["labels"]
        assert labels["pod-security.kubernetes.io/enforce"] == "restricted"

        # Pod security context complies with restricted PSS
        assert sec_contexts["pod"]["runAsNonRoot"] is True
        assert sec_contexts["container"]["allowPrivilegeEscalation"] is False
        assert sec_contexts["container"]["capabilities"]["drop"] == ["ALL"]
        assert sec_contexts["pod"]["seccompProfile"]["type"] == "RuntimeDefault"
