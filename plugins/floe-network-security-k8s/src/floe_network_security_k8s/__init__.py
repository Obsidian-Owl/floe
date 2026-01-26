"""floe-network-security-k8s: Kubernetes Network Security plugin for floe platform.

This plugin provides Kubernetes-native NetworkPolicy and Pod Security manifest
generation including default-deny policies, egress allowlists, Pod Security Standards
labels, and hardened container securityContext configurations.

Example:
    >>> from floe_network_security_k8s import K8sNetworkSecurityPlugin
    >>> plugin = K8sNetworkSecurityPlugin()
    >>> policies = plugin.generate_default_deny_policies("floe-jobs")
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0"
__all__ = [
    "K8sNetworkSecurityPlugin",
]


# Lazy imports to avoid circular dependencies and improve startup time
def __getattr__(name: str) -> Any:
    """Lazy import of plugin components."""
    if name == "K8sNetworkSecurityPlugin":
        from floe_network_security_k8s.plugin import K8sNetworkSecurityPlugin

        return K8sNetworkSecurityPlugin
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
