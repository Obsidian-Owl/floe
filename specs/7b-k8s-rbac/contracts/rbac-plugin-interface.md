# Contract: RBACPlugin Interface

**Feature**: Epic 7B - K8s RBAC Plugin System
**Version**: 1.0.0
**Date**: 2026-01-19

## Overview

This contract defines the `RBACPlugin` abstract base class interface that all RBAC plugin implementations must satisfy.

## Entry Point Registration

```toml
# pyproject.toml
[project.entry-points."floe.rbac"]
k8s = "floe_rbac_k8s:K8sRBACPlugin"
```

## Interface Definition

```python
from abc import abstractmethod
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


class RBACPlugin(PluginMetadata):
    """Abstract base class for RBAC operations.

    All RBAC plugin implementations MUST inherit from this class and
    implement all abstract methods. The plugin is responsible for
    generating Kubernetes RBAC manifests from floe configuration.

    Entry Point Group: floe.rbac
    """

    @abstractmethod
    def generate_service_account(
        self,
        config: "ServiceAccountConfig"
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
        """
        ...

    @abstractmethod
    def generate_role(
        self,
        config: "RoleConfig"
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
        """
        ...

    @abstractmethod
    def generate_role_binding(
        self,
        config: "RoleBindingConfig"
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
        """
        ...

    @abstractmethod
    def generate_namespace(
        self,
        config: "NamespaceConfig"
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
        """
        ...

    def generate_pod_security_context(
        self,
        config: "PodSecurityConfig"
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
        """
        return {
            "pod": config.to_pod_security_context(),
            "container": config.to_container_security_context(),
        }
```

## Compliance Requirements

### CR-001: PluginMetadata Inheritance

All RBACPlugin implementations MUST satisfy PluginMetadata requirements:

```python
class K8sRBACPlugin(RBACPlugin):
    @property
    def name(self) -> str:
        return "k8s-rbac"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"
```

### CR-002: No Wildcard Permissions

Generated Role manifests MUST NOT contain wildcard permissions:

```yaml
# FORBIDDEN
rules:
  - apiGroups: ["*"]  # NOT ALLOWED
    resources: ["*"]   # NOT ALLOWED
    verbs: ["*"]       # NOT ALLOWED

# REQUIRED
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get"]
    resourceNames: ["specific-secret"]
```

### CR-003: Managed-By Label

All generated resources MUST include the managed-by label:

```yaml
metadata:
  labels:
    app.kubernetes.io/managed-by: floe
```

### CR-004: PSS Label Requirements

Namespace manifests MUST include all three PSS labels:

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

## Test Compliance

Plugin implementations are validated via `BaseRBACPluginTests`:

```python
from testing.base_classes.base_rbac_plugin_tests import BaseRBACPluginTests

class TestK8sRBACPlugin(BaseRBACPluginTests):
    """Compliance tests for K8sRBACPlugin."""

    @pytest.fixture
    def plugin(self) -> RBACPlugin:
        return K8sRBACPlugin()
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-19 | Initial contract definition |
