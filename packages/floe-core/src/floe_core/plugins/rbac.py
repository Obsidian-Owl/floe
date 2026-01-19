"""RBACPlugin ABC for Kubernetes RBAC manifest generation.

This module defines the abstract base class for RBAC plugins that generate
Kubernetes RBAC resources. RBAC plugins are responsible for:
- Generating ServiceAccount manifests
- Generating Role manifests with least-privilege permissions
- Generating RoleBinding manifests
- Generating Namespace manifests with Pod Security Standards labels
- Generating pod/container security contexts

Example:
    >>> from floe_core.plugins.rbac import RBACPlugin
    >>> class MyRBACPlugin(RBACPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "my-rbac"
    ...     # ... implement other abstract methods

Contract: See specs/7b-k8s-rbac/contracts/rbac-plugin-interface.md
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from floe_core.plugin_metadata import PluginMetadata

if TYPE_CHECKING:
    from floe_core.schemas.rbac import (
        NamespaceConfig,
        PodSecurityConfig,
        RoleBindingConfig,
        RoleConfig,
        ServiceAccountConfig,
    )


class RBACPlugin(PluginMetadata):
    """Abstract base class for RBAC operations.

    RBACPlugin extends PluginMetadata with RBAC-specific methods for generating
    Kubernetes RBAC manifests. Implementations handle the actual K8s resource
    generation for different deployment targets.

    Entry Point Group: floe.rbac

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - generate_service_account() method
        - generate_role() method
        - generate_role_binding() method
        - generate_namespace() method

    Compliance Requirements:
        - CR-001: Must satisfy PluginMetadata requirements
        - CR-002: Generated Roles must not contain wildcard permissions
        - CR-003: All generated resources must include managed-by label
        - CR-004: Namespace manifests must include all PSS labels

    Example:
        >>> class K8sRBACPlugin(RBACPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "k8s-rbac"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def generate_service_account(self, config):
        ...         return config.to_k8s_manifest()

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - specs/7b-k8s-rbac/contracts/rbac-plugin-interface.md: Full interface specification
    """

    @abstractmethod
    def generate_service_account(
        self,
        config: ServiceAccountConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes ServiceAccount manifest.

        Args:
            config: ServiceAccount configuration with name, namespace, labels.

        Returns:
            Dictionary representing a valid K8s ServiceAccount manifest.

        Contract:
            - MUST include apiVersion: v1
            - MUST include kind: ServiceAccount
            - MUST include metadata.name matching config.name
            - MUST include metadata.namespace matching config.namespace
            - MUST include metadata.labels with app.kubernetes.io/managed-by: floe
            - MUST set automountServiceAccountToken per config.automount_token

        Example:
            >>> manifest = plugin.generate_service_account(config)
            >>> manifest["kind"]
            'ServiceAccount'
            >>> manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"]
            'floe'
        """
        ...

    @abstractmethod
    def generate_role(
        self,
        config: RoleConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes Role manifest.

        Args:
            config: Role configuration with name, namespace, rules.

        Returns:
            Dictionary representing a valid K8s Role manifest.

        Contract:
            - MUST include apiVersion: rbac.authorization.k8s.io/v1
            - MUST include kind: Role
            - MUST include rules array from config.rules
            - MUST NOT include wildcard (*) in apiGroups, resources, or verbs
            - SHOULD include resourceNames when specific resources are targeted

        Example:
            >>> manifest = plugin.generate_role(config)
            >>> manifest["kind"]
            'Role'
            >>> manifest["apiVersion"]
            'rbac.authorization.k8s.io/v1'
        """
        ...

    @abstractmethod
    def generate_role_binding(
        self,
        config: RoleBindingConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes RoleBinding manifest.

        Args:
            config: RoleBinding configuration with subjects and role reference.

        Returns:
            Dictionary representing a valid K8s RoleBinding manifest.

        Contract:
            - MUST include apiVersion: rbac.authorization.k8s.io/v1
            - MUST include kind: RoleBinding
            - MUST include subjects array from config.subjects
            - MUST include roleRef pointing to config.role_name

        Example:
            >>> manifest = plugin.generate_role_binding(config)
            >>> manifest["kind"]
            'RoleBinding'
            >>> manifest["roleRef"]["kind"]
            'Role'
        """
        ...

    @abstractmethod
    def generate_namespace(
        self,
        config: NamespaceConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes Namespace manifest with PSS labels.

        Args:
            config: Namespace configuration including PSS enforcement levels.

        Returns:
            Dictionary representing a valid K8s Namespace manifest.

        Contract:
            - MUST include apiVersion: v1
            - MUST include kind: Namespace
            - MUST include pod-security.kubernetes.io/enforce label
            - MUST include pod-security.kubernetes.io/audit label
            - MUST include pod-security.kubernetes.io/warn label
            - MUST include floe.dev/layer label

        Example:
            >>> manifest = plugin.generate_namespace(config)
            >>> manifest["kind"]
            'Namespace'
            >>> manifest["metadata"]["labels"]["pod-security.kubernetes.io/enforce"]
            'restricted'
        """
        ...

    def generate_pod_security_context(
        self,
        config: PodSecurityConfig,
    ) -> dict[str, Any]:
        """Generate pod and container securityContext fragments.

        This method has a default implementation but MAY be overridden.

        Args:
            config: Pod security configuration.

        Returns:
            Dictionary with 'pod' and 'container' securityContext fragments.

        Contract:
            - MUST return dict with 'pod' key containing pod securityContext
            - MUST return dict with 'container' key containing container securityContext
            - Pod context MUST include runAsNonRoot, runAsUser, runAsGroup, fsGroup
            - Container context MUST include allowPrivilegeEscalation, readOnlyRootFilesystem
            - Container context MUST include capabilities.drop: ["ALL"]

        Example:
            >>> contexts = plugin.generate_pod_security_context(config)
            >>> contexts["pod"]["runAsNonRoot"]
            True
            >>> contexts["container"]["capabilities"]["drop"]
            ['ALL']
        """
        return {
            "pod": config.to_pod_security_context(),
            "container": config.to_container_security_context(),
        }
