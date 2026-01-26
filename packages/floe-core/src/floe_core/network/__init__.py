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
    # Core generator (T050)
    "NetworkPolicyManifestGenerator",
    # Result types (T017)
    "NetworkPolicyGenerationResult",
    # Schemas (T008-T012)
    "PortRule",
    "EgressRule",
    "IngressRule",
    "EgressAllowRule",
    "NetworkPolicyConfig",
    "NetworkPoliciesConfig",
    # Audit (T018)
    "NetworkPolicyAuditEvent",
]


def __getattr__(name: str) -> Any:
    """Lazy import of network components."""
    # Schemas - T008-T012
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
    # Generator - T050
    if name == "NetworkPolicyManifestGenerator":
        from floe_core.network.generator import NetworkPolicyManifestGenerator

        return NetworkPolicyManifestGenerator
    # Result - T017
    if name == "NetworkPolicyGenerationResult":
        from floe_core.network.result import NetworkPolicyGenerationResult

        return NetworkPolicyGenerationResult
    # Audit - T018
    if name == "NetworkPolicyAuditEvent":
        from floe_core.network.audit import NetworkPolicyAuditEvent

        return NetworkPolicyAuditEvent
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
