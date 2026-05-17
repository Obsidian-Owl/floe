"""K8s RBAC Plugin implementation.

This module provides the K8sRBACPlugin class which implements the RBACPlugin ABC
from floe-core, generating Kubernetes RBAC manifests.

Example:
    >>> from floe_rbac_k8s.plugin import K8sRBACPlugin
    >>> from floe_core.schemas.rbac import ServiceAccountConfig
    >>> plugin = K8sRBACPlugin()
    >>> config = ServiceAccountConfig(name="floe-job-runner", namespace="floe-jobs")
    >>> manifest = plugin.generate_service_account(config)
    >>> manifest["kind"]
    'ServiceAccount'
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from floe_core.plugins.rbac import RBACPlugin
from floe_core.schemas.rbac import (
    NamespaceConfig,
    PodSecurityConfig,
    RoleBindingConfig,
    RoleConfig,
    ServiceAccountConfig,
)

from floe_rbac_k8s.tracing import get_tracer, security_span


class _ErrorType:
    ACCESS_DENIED = "access_denied"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


def _classify_generation_error(error: Exception) -> str:
    if isinstance(error, PermissionError):
        return _ErrorType.ACCESS_DENIED
    if isinstance(error, FileNotFoundError):
        return _ErrorType.NOT_FOUND
    if isinstance(error, ValueError):
        return _ErrorType.VALIDATION
    if isinstance(error, ConnectionError | TimeoutError):
        return _ErrorType.UNAVAILABLE
    return _ErrorType.UNKNOWN


class K8sRBACPlugin(RBACPlugin):
    """Kubernetes RBAC plugin for generating RBAC manifests.

    This plugin implements the RBACPlugin ABC from floe-core and provides
    Kubernetes-native RBAC manifest generation. Each method delegates to
    the corresponding schema's to_k8s_manifest() method.

    Attributes:
        name: Plugin name for identification.
        version: Plugin version following semver.
        floe_api_version: Minimum floe API version required.

    Example:
        >>> plugin = K8sRBACPlugin()
        >>> plugin.name
        'k8s-rbac'
        >>> plugin.version
        '0.1.0'
    """

    @property
    def name(self) -> str:
        """Plugin name."""
        return "k8s-rbac"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Minimum floe API version required."""
        return "1.0"

    @property
    def tracer_name(self) -> str | None:
        """OpenTelemetry tracer name for this plugin.

        Returns:
            The RBAC security tracer name for instrumentation auditing.
        """
        return "floe.security.rbac"

    def _record_generation(
        self,
        *,
        operation: str,
        policy_type: str,
        resource_kind: str,
        namespace: str | None,
        action: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Run a manifest generator and record secret-free lifecycle metadata."""
        tracer = get_tracer()
        with security_span(
            tracer,
            operation,
            policy_type=policy_type,
            extra_attributes={
                "security.resource_kind": resource_kind,
                **({"security.namespace": namespace} if namespace is not None else {}),
            },
        ) as span:
            started_at = time.perf_counter()
            try:
                manifest = action()
                span.set_attribute("security.status", "success")
                span.set_attribute(
                    "security.duration_ms", (time.perf_counter() - started_at) * 1000
                )
                return manifest
            except Exception as exc:
                span.set_attribute("security.status", "failure")
                span.set_attribute(
                    "security.duration_ms", (time.perf_counter() - started_at) * 1000
                )
                span.set_attribute("security.error_type", _classify_generation_error(exc))
                raise

    def generate_service_account(
        self,
        config: ServiceAccountConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes ServiceAccount manifest.

        Delegates to ServiceAccountConfig.to_k8s_manifest() to produce a valid
        K8s ServiceAccount manifest with automountServiceAccountToken defaulting
        to False for least-privilege (FR-011, FR-014).

        Args:
            config: ServiceAccount configuration with name, namespace, labels.

        Returns:
            Dictionary representing a valid K8s ServiceAccount manifest.

        Example:
            >>> from floe_core.schemas.rbac import ServiceAccountConfig
            >>> plugin = K8sRBACPlugin()
            >>> config = ServiceAccountConfig(
            ...     name="floe-job-runner",
            ...     namespace="floe-jobs"
            ... )
            >>> manifest = plugin.generate_service_account(config)
            >>> manifest["kind"]
            'ServiceAccount'
            >>> manifest["automountServiceAccountToken"]
            False
        """
        return self._record_generation(
            operation="generate_service_account",
            policy_type="ServiceAccount",
            resource_kind="ServiceAccount",
            namespace=config.namespace,
            action=config.to_k8s_manifest,
        )

    def generate_role(
        self,
        config: RoleConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes Role manifest.

        Delegates to RoleConfig.to_k8s_manifest() to produce a valid K8s Role
        manifest. Wildcard permissions (*) are forbidden per FR-070 and
        validated at the RoleRule schema level.

        Args:
            config: Role configuration with name, namespace, rules.

        Returns:
            Dictionary representing a valid K8s Role manifest.

        Example:
            >>> from floe_core.schemas.rbac import RoleConfig, RoleRule
            >>> plugin = K8sRBACPlugin()
            >>> rule = RoleRule(resources=["secrets"], verbs=["get"])
            >>> config = RoleConfig(
            ...     name="floe-reader-role",
            ...     namespace="floe-jobs",
            ...     rules=[rule]
            ... )
            >>> manifest = plugin.generate_role(config)
            >>> manifest["kind"]
            'Role'
        """
        return self._record_generation(
            operation="generate_role",
            policy_type="Role",
            resource_kind="Role",
            namespace=config.namespace,
            action=config.to_k8s_manifest,
        )

    def generate_role_binding(
        self,
        config: RoleBindingConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes RoleBinding manifest.

        Delegates to RoleBindingConfig.to_k8s_manifest() to produce a valid K8s
        RoleBinding manifest linking subjects to a Role.

        Args:
            config: RoleBinding configuration with subjects and role reference.

        Returns:
            Dictionary representing a valid K8s RoleBinding manifest.

        Example:
            >>> from floe_core.schemas.rbac import (
            ...     RoleBindingConfig,
            ...     RoleBindingSubject
            ... )
            >>> plugin = K8sRBACPlugin()
            >>> subject = RoleBindingSubject(
            ...     name="floe-job-runner",
            ...     namespace="floe-jobs"
            ... )
            >>> config = RoleBindingConfig(
            ...     name="floe-reader-binding",
            ...     namespace="floe-jobs",
            ...     subjects=[subject],
            ...     role_name="floe-reader-role"
            ... )
            >>> manifest = plugin.generate_role_binding(config)
            >>> manifest["kind"]
            'RoleBinding'
        """
        return self._record_generation(
            operation="generate_role_binding",
            policy_type="RoleBinding",
            resource_kind="RoleBinding",
            namespace=config.namespace,
            action=config.to_k8s_manifest,
        )

    def generate_namespace(
        self,
        config: NamespaceConfig,
    ) -> dict[str, Any]:
        """Generate a Kubernetes Namespace manifest with PSS labels.

        Delegates to NamespaceConfig.to_k8s_manifest() to produce a valid K8s
        Namespace manifest with Pod Security Standards labels.

        Args:
            config: Namespace configuration including PSS enforcement levels.

        Returns:
            Dictionary representing a valid K8s Namespace manifest.

        Example:
            >>> from floe_core.schemas.rbac import NamespaceConfig
            >>> plugin = K8sRBACPlugin()
            >>> config = NamespaceConfig(
            ...     name="floe-jobs",
            ...     layer="4",
            ...     pss_enforce="restricted"
            ... )
            >>> manifest = plugin.generate_namespace(config)
            >>> manifest["kind"]
            'Namespace'
        """
        return self._record_generation(
            operation="generate_namespace",
            policy_type="Namespace",
            resource_kind="Namespace",
            namespace=config.name,
            action=config.to_k8s_manifest,
        )

    def generate_pod_security_context(
        self,
        config: PodSecurityConfig,
    ) -> dict[str, Any]:
        """Generate pod and container securityContext fragments.

        Produces both pod-level and container-level securityContext dictionaries
        that comply with Pod Security Standards at the 'restricted' level.
        Also includes volumes and volumeMounts for writable directories when
        using readOnlyRootFilesystem: true (FR-043).

        Args:
            config: Pod security configuration.

        Returns:
            Dictionary with 'pod' and 'container' securityContext fragments,
            plus 'volumes' (for pod spec) and 'volumeMounts' (for container spec)
            for writable directories.

        Example:
            >>> from floe_core.schemas.rbac import PodSecurityConfig
            >>> plugin = K8sRBACPlugin()
            >>> config = PodSecurityConfig()
            >>> contexts = plugin.generate_pod_security_context(config)
            >>> contexts["pod"]["runAsNonRoot"]
            True
            >>> contexts["container"]["allowPrivilegeEscalation"]
            False
            >>> len(contexts["volumes"]) > 0  # Default includes /tmp
            True
        """
        return self._record_generation(
            operation="generate_pod_security_context",
            policy_type="PodSecurityContext",
            resource_kind="PodSecurityContext",
            namespace=None,
            action=lambda: {
                "pod": config.to_pod_security_context(),
                "container": config.to_container_security_context(),
                "volumes": config.to_volumes(),
                "volumeMounts": config.to_volume_mounts(),
            },
        )
