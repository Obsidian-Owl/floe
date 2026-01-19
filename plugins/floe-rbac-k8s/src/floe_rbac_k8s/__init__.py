"""floe-rbac-k8s: Kubernetes RBAC plugin for floe platform.

This plugin provides Kubernetes-native RBAC manifest generation including
ServiceAccounts, Roles, RoleBindings, and Namespaces with Pod Security Standards.

Example:
    >>> from floe_rbac_k8s import K8sRBACPlugin
    >>> from floe_core.schemas.rbac import ServiceAccountConfig
    >>> plugin = K8sRBACPlugin()
    >>> config = ServiceAccountConfig(
    ...     name="floe-job-runner",
    ...     namespace="floe-jobs"
    ... )
    >>> manifest = plugin.generate_service_account(config)
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"
__all__ = [
    "K8sRBACPlugin",
]


# Lazy imports to avoid circular dependencies and improve startup time
def __getattr__(name: str) -> Any:
    """Lazy import of plugin components."""
    if name == "K8sRBACPlugin":
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        return K8sRBACPlugin
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
