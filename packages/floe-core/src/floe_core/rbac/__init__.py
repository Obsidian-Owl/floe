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
    "MANIFEST_FILES",
    "ManifestValidationError",
    "validate_manifest",
    "validate_all_manifests",
    "aggregate_permissions",
    "write_manifests",
    # Secret reference validation (FR-073)
    "validate_secret_references",
    # Audit logging (FR-072)
    "RBACGenerationAuditEvent",
    "RBACGenerationResult",
    "log_rbac_event",
    # Security audit functions (FR-070)
    "detect_wildcard_permissions",
    "check_missing_resource_names",
    # Validation functions (FR-061, FR-062)
    "validate_manifest_against_config",
    # Diff functions (FR-063)
    "compute_resource_diff",
    "compute_rbac_diff",
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
    if name == "MANIFEST_FILES":
        from floe_core.rbac.generator import MANIFEST_FILES

        return MANIFEST_FILES
    if name == "ManifestValidationError":
        from floe_core.rbac.generator import ManifestValidationError

        return ManifestValidationError
    if name == "validate_manifest":
        from floe_core.rbac.generator import validate_manifest

        return validate_manifest
    if name == "validate_all_manifests":
        from floe_core.rbac.generator import validate_all_manifests

        return validate_all_manifests
    if name == "aggregate_permissions":
        from floe_core.rbac.generator import aggregate_permissions

        return aggregate_permissions
    if name == "write_manifests":
        from floe_core.rbac.generator import write_manifests

        return write_manifests
    if name == "validate_secret_references":
        from floe_core.rbac.generator import validate_secret_references

        return validate_secret_references
    if name == "RBACGenerationAuditEvent":
        from floe_core.rbac.audit import RBACGenerationAuditEvent

        return RBACGenerationAuditEvent
    if name == "RBACGenerationResult":
        from floe_core.rbac.audit import RBACGenerationResult

        return RBACGenerationResult
    if name == "log_rbac_event":
        from floe_core.rbac.audit import log_rbac_event

        return log_rbac_event
    # Security audit functions (FR-070)
    if name == "detect_wildcard_permissions":
        from floe_core.rbac.audit import detect_wildcard_permissions

        return detect_wildcard_permissions
    if name == "check_missing_resource_names":
        from floe_core.rbac.audit import check_missing_resource_names

        return check_missing_resource_names
    # Validation functions (FR-061, FR-062)
    if name == "validate_manifest_against_config":
        from floe_core.rbac.validate import validate_manifest_against_config

        return validate_manifest_against_config
    # Diff functions (FR-063)
    if name == "compute_resource_diff":
        from floe_core.rbac.diff import compute_resource_diff

        return compute_resource_diff
    if name == "compute_rbac_diff":
        from floe_core.rbac.diff import compute_rbac_diff

        return compute_rbac_diff
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
