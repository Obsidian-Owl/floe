"""Manifest schema definitions for the floe data platform.

This module provides Pydantic models for validating and working with
platform manifest files (manifest.yaml). It supports:

- 2-tier mode: Single platform configuration (scope=None)
- 3-tier mode: Enterprise/Domain hierarchy with inheritance (scope=enterprise/domain)

Models:
    PlatformManifest: Root configuration schema
    ManifestMetadata: Name, version, owner metadata
    PluginsConfig: Plugin selection for all 11 categories
    PluginSelection: Individual plugin configuration
    GovernanceConfig: Security and compliance settings
    SecretReference: Placeholder for sensitive values
    InheritanceChain: Resolved configuration lineage (3-tier)

Example:
    >>> from floe_core.schemas import PlatformManifest
    >>> import yaml
    >>> with open("manifest.yaml") as f:
    ...     data = yaml.safe_load(f)
    >>> manifest = PlatformManifest.model_validate(data)
    >>> print(f"Platform: {manifest.metadata.name}")

See Also:
    - specs/001-manifest-schema/spec.md: Feature specification
    - specs/001-manifest-schema/quickstart.md: Usage guide
"""

from __future__ import annotations

# Inheritance models (T006, T033, T034, T035)
from floe_core.schemas.inheritance import (
    CircularInheritanceError,
    FIELD_MERGE_STRATEGIES,
    InheritanceChain,
    MergeStrategy,
    detect_circular_inheritance,
    merge_manifests,
)

# Validation models (T031, T032, T036)
from floe_core.schemas.validation import (
    AUDIT_LOGGING_STRENGTH,
    InheritanceError,
    PII_ENCRYPTION_STRENGTH,
    POLICY_LEVEL_STRENGTH,
    SecurityPolicyViolationError,
    validate_security_policy_not_weakened,
)

# Metadata models (T007)
from floe_core.schemas.metadata import (
    NAME_PATTERN,
    SEMVER_PATTERN,
    ManifestMetadata,
)

# Secret models (T005, T008)
from floe_core.schemas.secrets import (
    SECRET_NAME_PATTERN,
    SecretReference,
    SecretSource,
)

# Plugin models (T016, T017, T042-T046)
from floe_core.schemas.plugins import (
    PLUGIN_REGISTRY,
    PluginSelection,
    PluginsConfig,
    PluginWhitelistError,
    get_available_plugins,
    validate_domain_plugin_whitelist,
    validate_plugin_selection,
)

# Manifest models (T018, T019)
from floe_core.schemas.manifest import (
    GovernanceConfig,
    ManifestScope,
    PlatformManifest,
)

__all__: list[str] = [
    # Inheritance (Phase 2, Phase 4)
    "MergeStrategy",
    "FIELD_MERGE_STRATEGIES",
    "InheritanceChain",
    "CircularInheritanceError",
    "detect_circular_inheritance",
    "merge_manifests",
    # Validation (Phase 4)
    "SecurityPolicyViolationError",
    "InheritanceError",
    "PII_ENCRYPTION_STRENGTH",
    "AUDIT_LOGGING_STRENGTH",
    "POLICY_LEVEL_STRENGTH",
    "validate_security_policy_not_weakened",
    # Metadata (Phase 2)
    "ManifestMetadata",
    "NAME_PATTERN",
    "SEMVER_PATTERN",
    # Secrets (Phase 2)
    "SecretSource",
    "SecretReference",
    "SECRET_NAME_PATTERN",
    # Plugins (Phase 3, Phase 5)
    "PluginSelection",
    "PluginsConfig",
    "PluginWhitelistError",
    "PLUGIN_REGISTRY",
    "get_available_plugins",
    "validate_plugin_selection",
    "validate_domain_plugin_whitelist",
    # Manifest (Phase 3)
    "ManifestScope",
    "GovernanceConfig",
    "PlatformManifest",
]
