"""NetworkSecurityPlugin ABC for Kubernetes NetworkPolicy and Pod Security generation.

This module defines the abstract base class for Network Security plugins that generate
Kubernetes NetworkPolicy resources and Pod Security contexts. Network Security plugins
are responsible for:
- Generating NetworkPolicy manifests with default-deny and allow rules
- Generating DNS egress rules for pod connectivity
- Generating pod and container security contexts for PSS compliance
- Generating writable volume mounts for read-only root filesystems

Example:
    >>> from floe_core.plugins.network_security import NetworkSecurityPlugin
    >>> class MyNetworkSecurityPlugin(NetworkSecurityPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "my-network-security"
    ...     # ... implement other abstract methods

Contract: See specs/7c-network-pod-security/contracts/network-security-plugin-interface.md
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from floe_core.plugin_metadata import PluginMetadata

if TYPE_CHECKING:
    from floe_core.network.schemas import NetworkPolicyConfig


class NetworkSecurityPlugin(PluginMetadata):
    """Abstract base class for Network Security operations.

    NetworkSecurityPlugin extends PluginMetadata with network security-specific methods
    for generating Kubernetes NetworkPolicy manifests and Pod Security contexts.
    Implementations handle the actual K8s resource generation for different deployment
    targets.

    Entry Point Group: floe.network_security

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - generate_network_policy() method
        - generate_default_deny_policies() method
        - generate_dns_egress_rule() method
        - generate_pod_security_context() method
        - generate_container_security_context() method
        - generate_writable_volumes() method

    Compliance Requirements:
        - CR-001: Must satisfy PluginMetadata requirements
        - CR-002: Generated NetworkPolicies must be valid K8s networking.k8s.io/v1
        - CR-003: All generated resources must include managed-by label
        - CR-004: Default-deny policies must deny all ingress and egress by default
        - CR-005: Pod security contexts must enforce runAsNonRoot
        - CR-006: Container security contexts must drop ALL capabilities

    Example:
        >>> class K8sNetworkSecurityPlugin(NetworkSecurityPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "k8s-network-security"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "0.1.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def generate_network_policy(self, config):
        ...         return config.to_k8s_manifest()

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - specs/7c-network-pod-security/contracts/network-security-plugin-interface.md
    """

    # =========================================================================
    # NetworkPolicy Generation Methods (T015)
    # =========================================================================

    @abstractmethod
    def generate_network_policy(
        self,
        config: NetworkPolicyConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes NetworkPolicy manifest from configuration.

        Args:
            config: NetworkPolicy configuration with ingress/egress rules.

        Returns:
            Dictionary representing a valid K8s NetworkPolicy manifest.

        Contract:
            - MUST include apiVersion: networking.k8s.io/v1
            - MUST include kind: NetworkPolicy
            - MUST include metadata.name matching config.name
            - MUST include metadata.namespace matching config.namespace
            - MUST include metadata.labels with app.kubernetes.io/managed-by: floe
            - MUST include spec.podSelector matching config.pod_selector
            - MUST include spec.policyTypes based on rules present

        Example:
            >>> manifest = plugin.generate_network_policy(config)
            >>> manifest["kind"]
            'NetworkPolicy'
            >>> manifest["apiVersion"]
            'networking.k8s.io/v1'
        """
        ...

    @abstractmethod
    def generate_default_deny_policies(
        self,
        namespace: str,
    ) -> list[dict[str, Any]]:
        """Generate default-deny NetworkPolicy manifests for a namespace.

        Creates policies that deny all ingress and egress traffic by default,
        following zero-trust networking principles.

        Args:
            namespace: Target namespace for the policies.

        Returns:
            List of dictionaries representing K8s NetworkPolicy manifests.

        Contract:
            - MUST return at least one NetworkPolicy
            - MUST include apiVersion: networking.k8s.io/v1
            - MUST include kind: NetworkPolicy
            - MUST include metadata.namespace matching namespace parameter
            - MUST include policyTypes: ["Ingress", "Egress"]
            - MUST have empty ingress and egress arrays (default deny)

        Example:
            >>> policies = plugin.generate_default_deny_policies("floe-jobs")
            >>> len(policies) >= 1
            True
            >>> policies[0]["metadata"]["namespace"]
            'floe-jobs'
        """
        ...

    @abstractmethod
    def generate_dns_egress_rule(self) -> dict[str, Any]:
        """Generate an egress rule allowing DNS lookups.

        Creates an egress rule that allows pods to perform DNS queries to
        the cluster DNS service (typically CoreDNS in kube-system).

        Returns:
            Dictionary representing a K8s NetworkPolicy egress rule structure.

        Contract:
            - MUST include "to" array with namespace selector
            - MUST include "ports" array with DNS port configuration
            - MUST allow port 53 for UDP protocol
            - SHOULD allow port 53 for TCP protocol (for large responses)
            - SHOULD target kube-system namespace

        Example:
            >>> rule = plugin.generate_dns_egress_rule()
            >>> "to" in rule
            True
            >>> any(p.get("port") == 53 for p in rule["ports"])
            True
        """
        ...

    # =========================================================================
    # SecurityContext Generation Methods (T016)
    # =========================================================================

    @abstractmethod
    def generate_pod_security_context(
        self,
        config: Any,
    ) -> dict[str, Any]:
        """Generate a Kubernetes pod securityContext.

        Creates a pod-level securityContext that enforces Pod Security Standards
        at the restricted level.

        Args:
            config: Pod security configuration (may be None for defaults).

        Returns:
            Dictionary representing a K8s pod securityContext.

        Contract:
            - MUST include runAsNonRoot: true
            - MUST include runAsUser with non-root UID (e.g., 1000)
            - MUST include runAsGroup with non-root GID (e.g., 1000)
            - MUST include fsGroup with non-root GID (e.g., 1000)
            - MUST include seccompProfile.type: RuntimeDefault

        Example:
            >>> context = plugin.generate_pod_security_context(None)
            >>> context["runAsNonRoot"]
            True
            >>> context["runAsUser"]
            1000
        """
        ...

    @abstractmethod
    def generate_container_security_context(
        self,
        config: Any,
    ) -> dict[str, Any]:
        """Generate a Kubernetes container securityContext.

        Creates a container-level securityContext that enforces Pod Security
        Standards at the restricted level with hardened settings.

        Args:
            config: Container security configuration (may be None for defaults).

        Returns:
            Dictionary representing a K8s container securityContext.

        Contract:
            - MUST include allowPrivilegeEscalation: false
            - MUST include readOnlyRootFilesystem: true
            - MUST include capabilities.drop: ["ALL"]
            - SHOULD NOT include any capabilities.add entries

        Example:
            >>> context = plugin.generate_container_security_context(None)
            >>> context["allowPrivilegeEscalation"]
            False
            >>> context["readOnlyRootFilesystem"]
            True
            >>> "ALL" in context["capabilities"]["drop"]
            True
        """
        ...

    @abstractmethod
    def generate_writable_volumes(
        self,
        paths: list[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Generate emptyDir volumes and mounts for writable paths.

        When using readOnlyRootFilesystem, certain paths may need to be
        writable. This method generates emptyDir volumes and corresponding
        volumeMounts for the specified paths.

        Args:
            paths: List of container paths that need to be writable.

        Returns:
            Tuple of (volumes, volumeMounts) where:
            - volumes: List of K8s volume definitions with emptyDir
            - volumeMounts: List of K8s volumeMount definitions

        Contract:
            - MUST return equal-length lists of volumes and volumeMounts
            - Each volume MUST have a unique name
            - Each volume MUST use emptyDir: {}
            - Each volumeMount MUST reference the corresponding volume name
            - Each volumeMount MUST have mountPath matching the input path

        Example:
            >>> volumes, mounts = plugin.generate_writable_volumes(["/tmp", "/home/floe"])
            >>> len(volumes) == len(mounts) == 2
            True
            >>> all("emptyDir" in v for v in volumes)
            True
        """
        ...
