"""Schema definitions for the floe data platform.

This module provides Pydantic models for validating and working with:

- Platform manifest files (manifest.yaml) - input configuration
- CompiledArtifacts - output from floe compile

Manifest Configuration:
    - 2-tier mode: Single platform configuration (scope=None)
    - 3-tier mode: Enterprise/Domain hierarchy with inheritance (scope=enterprise/domain)

Manifest Models:
    PlatformManifest: Root configuration schema
    ManifestMetadata: Name, version, owner metadata
    PluginsConfig: Plugin selection for all 12 categories (per ADR-0035)
    PluginSelection: Individual plugin configuration
    GovernanceConfig: Security and compliance settings
    SecretReference: Placeholder for sensitive values
    InheritanceChain: Resolved configuration lineage (3-tier)

CompiledArtifacts Models:
    CompiledArtifacts: Output of floe compile with resolved configuration
    CompilationMetadata: Compilation information and source hash
    ProductIdentity: Product identity from catalog registration
    ManifestRef: Reference to manifest in inheritance chain
    ObservabilityConfig: Observability settings with TelemetryConfig

Example:
    >>> from floe_core.schemas import PlatformManifest
    >>> import yaml
    >>> with open("manifest.yaml") as f:
    ...     data = yaml.safe_load(f)
    >>> manifest = PlatformManifest.model_validate(data)
    >>> print(f"Platform: {manifest.metadata.name}")

See Also:
    - specs/001-manifest-schema/spec.md: Feature specification
    - docs/contracts/compiled-artifacts.md: CompiledArtifacts contract
"""

from __future__ import annotations

# Audit models (T078)
from floe_core.schemas.audit import (
    AuditEvent,
    AuditOperation,
    AuditResult,
)

# CompiledArtifacts models (T076)
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    DeploymentMode,
    ManifestRef,
    ObservabilityConfig,
    ProductIdentity,
)

# Inheritance models (T006, T033, T034, T035)
from floe_core.schemas.inheritance import (
    FIELD_MERGE_STRATEGIES,
    CircularInheritanceError,
    InheritanceChain,
    MergeStrategy,
    detect_circular_inheritance,
    merge_manifests,
)

# JSON Schema export (T047, T048, T049)
from floe_core.schemas.json_schema import (
    JSON_SCHEMA_DRAFT,
    MANIFEST_SCHEMA_ID,
    JsonSchemaValidationError,
    export_json_schema,
    export_json_schema_to_file,
    validate_against_schema,
)

# Manifest models (T018, T019)
from floe_core.schemas.manifest import (
    FORBIDDEN_ENVIRONMENT_FIELDS,
    GovernanceConfig,
    ManifestScope,
    PlatformManifest,
)

# Metadata models (T007)
from floe_core.schemas.metadata import (
    NAME_PATTERN,
    SEMVER_PATTERN,
    ManifestMetadata,
)

# Plugin models (T016, T017, T042-T046)
from floe_core.schemas.plugins import (
    PLUGIN_REGISTRY,
    PluginsConfig,
    PluginSelection,
    PluginWhitelistError,
    get_available_plugins,
    validate_domain_plugin_whitelist,
    validate_plugin_selection,
)

# Secret models (T005, T008, T039, T040)
from floe_core.schemas.secrets import (
    SECRET_NAME_PATTERN,
    SECRET_VALUE_PATTERNS,
    SecretReference,
    SecretSource,
    resolve_secret_references,
    validate_no_secrets_in_artifacts,
)

# Validation models (T031, T032, T036)
from floe_core.schemas.validation import (
    AUDIT_LOGGING_STRENGTH,
    PII_ENCRYPTION_STRENGTH,
    POLICY_LEVEL_STRENGTH,
    InheritanceError,
    SecurityPolicyViolationError,
    validate_security_policy_not_weakened,
)

__all__: list[str] = [
    # Audit (Phase 7, Epic 7A)
    "AuditEvent",
    "AuditOperation",
    "AuditResult",
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
    # Secrets (Phase 2, 7A)
    "SecretSource",
    "SecretReference",
    "SECRET_NAME_PATTERN",
    "SECRET_VALUE_PATTERNS",
    "resolve_secret_references",
    "validate_no_secrets_in_artifacts",
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
    "FORBIDDEN_ENVIRONMENT_FIELDS",
    # JSON Schema (Phase 6)
    "JSON_SCHEMA_DRAFT",
    "MANIFEST_SCHEMA_ID",
    "JsonSchemaValidationError",
    "export_json_schema",
    "export_json_schema_to_file",
    "validate_against_schema",
    # CompiledArtifacts (T076)
    "CompiledArtifacts",
    "CompilationMetadata",
    "DeploymentMode",
    "ManifestRef",
    "ObservabilityConfig",
    "ProductIdentity",
]
