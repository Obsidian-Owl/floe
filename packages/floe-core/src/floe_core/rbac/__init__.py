"""RBAC module for Kubernetes RBAC manifest generation.

This module provides the RBACManifestGenerator class and related utilities
for generating Kubernetes RBAC manifests from floe configuration.

Example:
    >>> from floe_core.rbac import RBACManifestGenerator
    >>> from floe_core.schemas.security import SecurityConfig
    >>> generator = RBACManifestGenerator(plugin=k8s_rbac_plugin)
    >>> result = generator.generate(security_config, secret_refs)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "RBACManifestGenerator",
    "GenerationResult",
]


# Lazy imports to avoid circular dependencies
def __getattr__(name: str) -> Any:
    """Lazy import of RBAC components."""
    if name == "RBACManifestGenerator":
        from floe_core.rbac.generator import RBACManifestGenerator

        return RBACManifestGenerator
    if name == "GenerationResult":
        from floe_core.rbac.result import GenerationResult

        return GenerationResult
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
