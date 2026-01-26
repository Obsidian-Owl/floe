"""Unit tests for pod and container securityContext generation.

Task: T042
Phase: 6 - Secure Container Runtime Configuration (US4)
User Story: US4 - Secure Container Runtime Configuration
Requirement: FR-060, FR-061, FR-062, FR-063, FR-064
"""

from __future__ import annotations

import pytest


class TestPodSecurityContext:
    """Unit tests for pod-level securityContext generation (T044).

    Pod securityContext defines security settings at the pod level:
    - runAsNonRoot: Enforce non-root execution
    - runAsUser/runAsGroup: Specific UID/GID
    - fsGroup: Filesystem group for volumes
    - seccompProfile: Seccomp profile for syscall filtering
    """

    @pytest.mark.requirement("FR-060")
    def test_generate_pod_security_context_returns_dict(self) -> None:
        """Test that pod securityContext generation returns a dictionary."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_pod_security_context(config=None)

        assert isinstance(ctx, dict)

    @pytest.mark.requirement("FR-060")
    def test_pod_security_context_run_as_non_root(self) -> None:
        """Test that runAsNonRoot is set to True."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_pod_security_context(config=None)

        assert ctx["runAsNonRoot"] is True

    @pytest.mark.requirement("FR-060")
    def test_pod_security_context_run_as_user(self) -> None:
        """Test that runAsUser is set to non-root UID."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_pod_security_context(config=None)

        assert ctx["runAsUser"] >= 1000  # Non-root UID

    @pytest.mark.requirement("FR-060")
    def test_pod_security_context_run_as_group(self) -> None:
        """Test that runAsGroup is set to non-root GID."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_pod_security_context(config=None)

        assert ctx["runAsGroup"] >= 1000  # Non-root GID

    @pytest.mark.requirement("FR-060")
    def test_pod_security_context_fs_group(self) -> None:
        """Test that fsGroup is set for volume access."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_pod_security_context(config=None)

        assert "fsGroup" in ctx
        assert ctx["fsGroup"] >= 1000  # Non-root GID

    @pytest.mark.requirement("FR-064")
    def test_pod_security_context_seccomp_profile(self) -> None:
        """Test that seccompProfile is set to RuntimeDefault."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_pod_security_context(config=None)

        assert "seccompProfile" in ctx
        assert ctx["seccompProfile"]["type"] == "RuntimeDefault"


class TestContainerSecurityContext:
    """Unit tests for container-level securityContext generation (T045).

    Container securityContext defines security settings at the container level:
    - allowPrivilegeEscalation: Prevent privilege escalation
    - capabilities: Drop dangerous capabilities
    - readOnlyRootFilesystem: Prevent writes to root filesystem
    """

    @pytest.mark.requirement("FR-061")
    def test_generate_container_security_context_returns_dict(self) -> None:
        """Test that container securityContext generation returns a dictionary."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_container_security_context(config=None)

        assert isinstance(ctx, dict)

    @pytest.mark.requirement("FR-061")
    def test_container_no_privilege_escalation(self) -> None:
        """Test that allowPrivilegeEscalation is False."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_container_security_context(config=None)

        assert ctx["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("FR-062")
    def test_container_read_only_root_filesystem(self) -> None:
        """Test that readOnlyRootFilesystem is True."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_container_security_context(config=None)

        assert ctx["readOnlyRootFilesystem"] is True

    @pytest.mark.requirement("FR-061")
    def test_container_drops_all_capabilities(self) -> None:
        """Test that all capabilities are dropped."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_container_security_context(config=None)

        assert "capabilities" in ctx
        assert "drop" in ctx["capabilities"]
        assert "ALL" in ctx["capabilities"]["drop"]

    @pytest.mark.requirement("FR-061")
    def test_container_no_capabilities_added(self) -> None:
        """Test that no capabilities are added."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        ctx = plugin.generate_container_security_context(config=None)

        # Should not have 'add' key or it should be empty
        assert "add" not in ctx.get("capabilities", {})


class TestSecurityContextIntegration:
    """Integration tests for security context with pod specs."""

    @pytest.mark.requirement("FR-060")
    def test_pod_and_container_context_compatible(self) -> None:
        """Test that pod and container security contexts can be combined."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        pod_ctx = plugin.generate_pod_security_context(config=None)
        container_ctx = plugin.generate_container_security_context(config=None)

        # Both should be dictionaries
        assert isinstance(pod_ctx, dict)
        assert isinstance(container_ctx, dict)

        # Simulate a pod spec structure
        pod_spec = {
            "securityContext": pod_ctx,
            "containers": [
                {
                    "name": "main",
                    "securityContext": container_ctx,
                }
            ],
        }

        # Verify structure is valid
        assert pod_spec["securityContext"]["runAsNonRoot"] is True
        assert pod_spec["containers"][0]["securityContext"]["allowPrivilegeEscalation"] is False

    @pytest.mark.requirement("FR-060")
    def test_security_context_complies_with_pss_restricted(self) -> None:
        """Test that generated contexts comply with PSS restricted level.

        PSS restricted requires:
        - runAsNonRoot: true
        - allowPrivilegeEscalation: false
        - capabilities.drop: [ALL]
        - seccompProfile.type: RuntimeDefault or Localhost
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        pod_ctx = plugin.generate_pod_security_context(config=None)
        container_ctx = plugin.generate_container_security_context(config=None)

        # PSS restricted requirements at pod level
        assert pod_ctx.get("runAsNonRoot") is True
        assert pod_ctx.get("seccompProfile", {}).get("type") in ["RuntimeDefault", "Localhost"]

        # PSS restricted requirements at container level
        assert container_ctx.get("allowPrivilegeEscalation") is False
        assert "ALL" in container_ctx.get("capabilities", {}).get("drop", [])
