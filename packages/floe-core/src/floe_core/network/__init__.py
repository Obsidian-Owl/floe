"""Network module for Kubernetes NetworkPolicy manifest generation.

This module provides the NetworkPolicyManifestGenerator class and related utilities
for generating Kubernetes NetworkPolicy manifests from floe configuration.

Example:
    >>> from floe_core.network import NetworkPolicyManifestGenerator
    >>> from floe_core.schemas.security import SecurityConfig
    >>> generator = NetworkPolicyManifestGenerator(plugin=k8s_network_security_plugin)
    >>> result = generator.generate(security_config)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "NetworkPolicyManifestGenerator",
    "NetworkPolicyGenerationResult",
    "PortRule",
    "EgressRule",
    "IngressRule",
    "EgressAllowRule",
    "NetworkPolicyConfig",
    "NetworkPoliciesConfig",
    "NetworkPolicyAuditEvent",
    "discover_network_security_plugins",
    "get_network_security_plugin",
    "NetworkSecurityPluginNotFoundError",
]


def __getattr__(name: str) -> Any:
    """Lazy import of network components."""
    if name in {
        "PortRule",
        "EgressRule",
        "IngressRule",
        "EgressAllowRule",
        "NetworkPolicyConfig",
        "NetworkPoliciesConfig",
    }:
        from floe_core.network import schemas

        return getattr(schemas, name)

    if name == "NetworkPolicyManifestGenerator":
        from floe_core.network.generator import NetworkPolicyManifestGenerator

        return NetworkPolicyManifestGenerator

    if name == "NetworkPolicyGenerationResult":
        from floe_core.network.result import NetworkPolicyGenerationResult

        return NetworkPolicyGenerationResult

    if name == "NetworkPolicyAuditEvent":
        from floe_core.network.audit import NetworkPolicyAuditEvent

        return NetworkPolicyAuditEvent

    if name == "discover_network_security_plugins":
        from floe_core.network.generator import discover_network_security_plugins

        return discover_network_security_plugins

    if name == "get_network_security_plugin":
        from floe_core.network.generator import get_network_security_plugin

        return get_network_security_plugin

    if name == "NetworkSecurityPluginNotFoundError":
        from floe_core.network.generator import NetworkSecurityPluginNotFoundError

        return NetworkSecurityPluginNotFoundError

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
