"""Platform manifest model for manifest schema.

This module provides the root PlatformManifest model and related
governance configuration for platform manifests.

Implements:
    - FR-001: Platform Configuration Definition
    - FR-011: Environment-Agnostic Configuration
    - FR-012: Forward Compatibility (unknown fields warning)
    - FR-013: Required Fields Enforcement
    - FR-015: Runtime Environment Resolution
    - FR-016: Manifest Immutability
    - FR-017: Governance Configuration
"""

from __future__ import annotations

import warnings
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from floe_core.schemas.governance import (
    CustomRule,
    DataContractsConfig,
    NamingConfig,
    PolicyOverride,
    QualityGatesConfig,
)
from floe_core.schemas.metadata import ManifestMetadata
from floe_core.schemas.oci import RegistryConfig
from floe_core.schemas.plugins import PluginsConfig
from floe_core.schemas.promotion import PromotionConfig

# Manifest scope literals
ManifestScope = Literal["enterprise", "domain"]
"""Valid scope values for 3-tier configuration mode."""

# Environment-specific field names that are forbidden in manifests
# Manifests are environment-agnostic; FLOE_ENV determines runtime behavior
FORBIDDEN_ENVIRONMENT_FIELDS = frozenset(
    {
        "env_overrides",
        "environments",
        "environment",
        "env",
        "dev",
        "staging",
        "prod",
        "production",
        "target_env",
        "floe_env",
    }
)
"""Fields forbidden in manifests to enforce environment-agnostic design.

Manifests MUST NOT contain environment-specific configuration.
Runtime behavior is determined by FLOE_ENV environment variable.
"""


class ArtifactsConfig(BaseModel):
    """Configuration for OCI artifact storage and promotion lifecycle.

    Defines how compiled artifacts are stored in OCI registries and
    how they are promoted through environment stages.

    Attributes:
        registry: OCI registry configuration for artifact storage.
        promotion: Optional promotion lifecycle configuration.
            If None, promotion features are disabled.

    Example:
        >>> from floe_core.schemas.oci import RegistryConfig
        >>> from floe_core.schemas.promotion import PromotionConfig
        >>> config = ArtifactsConfig(
        ...     registry=RegistryConfig(uri="oci://harbor.example.com/floe"),
        ...     promotion=PromotionConfig()  # Default [dev, staging, prod]
        ... )

    See Also:
        - Epic 8C: Promotion Lifecycle specification
        - FR-009a: ArtifactsConfig schema integration with manifest
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "registry": {"uri": "oci://harbor.example.com/floe"},
                    "promotion": {
                        "environments": [
                            {"name": "dev"},
                            {"name": "staging"},
                            {"name": "prod"},
                        ]
                    },
                }
            ]
        },
    )

    registry: RegistryConfig = Field(
        description="OCI registry configuration for artifact storage",
    )
    promotion: PromotionConfig | None = Field(
        default=None,
        description="Promotion lifecycle configuration (None disables promotion)",
    )


class GovernanceConfig(BaseModel):
    """Security and compliance settings for platform governance.

    Defines security policies that are immutable in inheritance chains.
    Child manifests can only strengthen (not weaken) security policies.

    Attributes:
        pii_encryption: PII encryption policy (required > optional)
        audit_logging: Audit logging policy (enabled > disabled)
        policy_enforcement_level: Enforcement level (strict > warn > off)
        data_retention_days: Data retention period in days
        naming: Naming convention configuration (NEW in Epic 3A)
        quality_gates: Quality gate thresholds (NEW in Epic 3A)
        custom_rules: Custom validation rules (NEW in Epic 3B)
        policy_overrides: Override rules for legacy/migration (NEW in Epic 3B)
        data_contracts: Data contract validation settings (NEW in Epic 3C)

    Example:
        >>> governance = GovernanceConfig(
        ...     pii_encryption="required",
        ...     audit_logging="enabled",
        ...     policy_enforcement_level="strict",
        ...     data_retention_days=90
        ... )

    Strength Ordering (for inheritance validation):
        - pii_encryption: required > optional
        - audit_logging: enabled > disabled
        - policy_enforcement_level: strict > warn > off
        - data_retention_days: higher is stricter
        - naming.enforcement: strict > warn > off
        - quality_gates.minimum_test_coverage: higher is stricter
        - quality_gates.require_descriptions: True > False

    See Also:
        - data-model.md: GovernanceConfig entity specification
        - FR-017: Governance immutability in inheritance
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "pii_encryption": "required",
                    "audit_logging": "enabled",
                    "policy_enforcement_level": "strict",
                    "data_retention_days": 90,
                }
            ]
        },
    )

    pii_encryption: Literal["required", "optional"] | None = Field(
        default=None,
        description="PII encryption policy (required > optional)",
    )
    audit_logging: Literal["enabled", "disabled"] | None = Field(
        default=None,
        description="Audit logging policy (enabled > disabled)",
    )
    policy_enforcement_level: Literal["off", "warn", "strict"] | None = Field(
        default=None,
        description="Policy enforcement level (strict > warn > off)",
    )
    data_retention_days: Annotated[
        int | None,
        Field(
            default=None,
            ge=1,
            description="Data retention period in days (higher is stricter)",
        ),
    ]

    # NEW in Epic 3A: Policy Enforcer configuration
    naming: NamingConfig | None = Field(
        default=None,
        description="Naming convention configuration (NEW in Epic 3A)",
    )
    quality_gates: QualityGatesConfig | None = Field(
        default=None,
        description="Quality gate thresholds (NEW in Epic 3A)",
    )

    # NEW in Epic 3B: Custom rules and policy overrides
    custom_rules: list[CustomRule] = Field(
        default_factory=list,
        description="Custom validation rules (NEW in Epic 3B)",
    )
    policy_overrides: list[PolicyOverride] = Field(
        default_factory=list,
        description="Override rules for legacy/migration support (NEW in Epic 3B)",
    )

    # NEW in Epic 3C: Data contract configuration
    data_contracts: DataContractsConfig | None = Field(
        default=None,
        description="Data contract validation settings (NEW in Epic 3C)",
    )


class PlatformManifest(BaseModel):
    """Root configuration entity for platform manifests.

    Represents an organization's platform settings including plugin
    selections, governance policies, and inheritance configuration.

    Supports two configuration modes:
    - 2-tier mode (scope=None): Single platform configuration
    - 3-tier mode (scope=enterprise/domain): Enterprise → Domain hierarchy

    Attributes:
        api_version: API version (must be "floe.dev/v1")
        kind: Resource kind (must be "Manifest")
        metadata: Manifest metadata (name, version, owner)
        scope: Configuration scope (None=2-tier, enterprise/domain=3-tier)
        parent_manifest: OCI URI of parent manifest (required for domain scope)
        plugins: Plugin selections for all 12 categories
        governance: Security and compliance settings
        approved_plugins: Enterprise whitelist of approved plugins per category
        approved_products: Domain list of approved data products

    Example:
        >>> manifest = PlatformManifest(
        ...     api_version="floe.dev/v1",
        ...     kind="Manifest",
        ...     metadata=ManifestMetadata(
        ...         name="acme-platform",
        ...         version="1.0.0",
        ...         owner="platform-team@acme.com"
        ...     ),
        ...     plugins=PluginsConfig(
        ...         compute=PluginSelection(type="duckdb"),
        ...         orchestrator=PluginSelection(type="dagster")
        ...     )
        ... )

    Validation Rules:
        - C001: scope=enterprise → parent_manifest=None
        - C002: scope=domain → parent_manifest required
        - C003: scope=None → parent_manifest=None
        - C004: approved_plugins only for scope=enterprise
        - C005: approved_products only for scope=domain

    See Also:
        - data-model.md: PlatformManifest entity specification
        - spec.md: Manifest schema specification
    """

    model_config = ConfigDict(
        frozen=True,
        extra="allow",  # Forward compatibility - allow unknown fields with warning
        populate_by_name=True,  # Accept both alias (apiVersion) and field name (api_version)
        json_schema_extra={
            "examples": [
                {
                    "apiVersion": "floe.dev/v1",
                    "kind": "Manifest",
                    "metadata": {
                        "name": "acme-platform",
                        "version": "1.0.0",
                        "owner": "platform-team@acme.com",
                    },
                    "plugins": {
                        "compute": {"type": "duckdb"},
                        "orchestrator": {"type": "dagster"},
                    },
                }
            ]
        },
    )

    api_version: Literal["floe.dev/v1"] = Field(
        alias="apiVersion",
        description="API version (must be 'floe.dev/v1')",
    )
    kind: Literal["Manifest"] = Field(
        description="Resource kind (must be 'Manifest')",
    )
    metadata: ManifestMetadata = Field(
        description="Manifest metadata (name, version, owner)",
    )
    scope: ManifestScope | None = Field(
        default=None,
        description="Configuration scope (None=2-tier, enterprise/domain=3-tier)",
    )
    parent_manifest: str | None = Field(
        default=None,
        description="OCI URI of parent manifest (required for domain scope)",
    )
    plugins: PluginsConfig = Field(
        description="Plugin selections for all 12 categories",
    )
    governance: GovernanceConfig | None = Field(
        default=None,
        description="Security and compliance settings",
    )
    approved_plugins: dict[str, list[str]] | None = Field(
        default=None,
        description="Enterprise whitelist of approved plugins per category",
    )
    approved_products: list[str] | None = Field(
        default=None,
        description="Domain list of approved data products",
    )
    defaults: dict[str, str] | None = Field(
        default=None,
        description="Default settings (e.g., compute: duckdb)",
    )
    artifacts: ArtifactsConfig | None = Field(
        default=None,
        description="OCI artifact storage and promotion lifecycle configuration (Epic 8C)",
    )

    @model_validator(mode="after")
    def validate_scope_constraints(self) -> PlatformManifest:
        """Validate scope-related constraints.

        Rules:
            - C001: scope=enterprise → parent_manifest must be None
            - C002: scope=domain → parent_manifest is required
            - C003: scope=None → parent_manifest must be None
            - C004: approved_plugins only valid for scope=enterprise
            - C005: approved_products only valid for scope=domain
        """
        # C001, C003: enterprise and None scopes cannot have parent_manifest
        if self.scope in (None, "enterprise") and self.parent_manifest is not None:
            msg = (
                f"parent_manifest must be None for scope={self.scope!r}. "
                "Only domain-scoped manifests can have a parent."
            )
            raise ValueError(msg)

        # C002: domain scope requires parent_manifest
        if self.scope == "domain" and self.parent_manifest is None:
            msg = (
                "parent_manifest is required for scope='domain'. "
                "Domain manifests must inherit from an enterprise manifest."
            )
            raise ValueError(msg)

        # C004: approved_plugins only for enterprise scope
        if self.approved_plugins is not None and self.scope != "enterprise":
            msg = (
                f"approved_plugins is only valid for scope='enterprise', not scope={self.scope!r}."
            )
            raise ValueError(msg)

        # C005: approved_products only for domain scope
        if self.approved_products is not None and self.scope != "domain":
            msg = f"approved_products is only valid for scope='domain', not scope={self.scope!r}."
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def reject_environment_specific_fields(self) -> PlatformManifest:
        """Reject environment-specific fields to enforce environment-agnostic design.

        Manifests MUST NOT contain environment-specific configuration.
        Runtime behavior is determined by FLOE_ENV environment variable.

        Raises:
            ValueError: If any forbidden environment field is present.
        """
        if self.model_extra:
            forbidden_found = set(self.model_extra.keys()) & FORBIDDEN_ENVIRONMENT_FIELDS
            if forbidden_found:
                forbidden_str = ", ".join(sorted(forbidden_found))
                msg = (
                    f"Environment-specific fields are not allowed in manifests: "
                    f"[{forbidden_str}]. "
                    "Manifests are environment-agnostic by design. "
                    "Use FLOE_ENV environment variable at runtime to select environment. "
                    "See quickstart.md for environment resolution patterns."
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def warn_on_extra_fields(self) -> PlatformManifest:
        """Emit warning for unknown fields (forward compatibility).

        Note: This runs after reject_environment_specific_fields, so
        environment-specific fields will have already been rejected.
        """
        if self.model_extra:
            # Filter out fields already handled by reject_environment_specific_fields
            unknown_fields = [
                f for f in self.model_extra.keys() if f not in FORBIDDEN_ENVIRONMENT_FIELDS
            ]
            if unknown_fields:
                warnings.warn(
                    f"Unknown fields in manifest will be ignored: {unknown_fields}. "
                    "This may indicate a newer manifest version or typos.",
                    UserWarning,
                    stacklevel=2,
                )
        return self


__all__ = [
    "ArtifactsConfig",
    "FORBIDDEN_ENVIRONMENT_FIELDS",
    "GovernanceConfig",
    "ManifestScope",
    "PlatformManifest",
]
