"""Platform manifest model for manifest schema.

This module provides the root PlatformManifest model and related
governance configuration for platform manifests.

Implements:
    - FR-001: Platform Configuration Definition
    - FR-016: Manifest Immutability
    - FR-017: Governance Configuration
"""

from __future__ import annotations

import warnings
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from floe_core.schemas.metadata import ManifestMetadata
from floe_core.schemas.plugins import PluginsConfig


# Manifest scope literals
ManifestScope = Literal["enterprise", "domain"]
"""Valid scope values for 3-tier configuration mode."""


class GovernanceConfig(BaseModel):
    """Security and compliance settings for platform governance.

    Defines security policies that are immutable in inheritance chains.
    Child manifests can only strengthen (not weaken) security policies.

    Attributes:
        pii_encryption: PII encryption policy (required > optional)
        audit_logging: Audit logging policy (enabled > disabled)
        policy_enforcement_level: Enforcement level (strict > warn > off)
        data_retention_days: Data retention period in days

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
        plugins: Plugin selections for all 11 categories
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
        json_schema_extra={
            "examples": [
                {
                    "api_version": "floe.dev/v1",
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
        description="Plugin selections for all 11 categories",
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
                f"approved_plugins is only valid for scope='enterprise', "
                f"not scope={self.scope!r}."
            )
            raise ValueError(msg)

        # C005: approved_products only for domain scope
        if self.approved_products is not None and self.scope != "domain":
            msg = (
                f"approved_products is only valid for scope='domain', "
                f"not scope={self.scope!r}."
            )
            raise ValueError(msg)

        return self

    @model_validator(mode="after")
    def warn_on_extra_fields(self) -> PlatformManifest:
        """Emit warning for unknown fields (forward compatibility)."""
        if self.model_extra:
            unknown_fields = list(self.model_extra.keys())
            warnings.warn(
                f"Unknown fields in manifest will be ignored: {unknown_fields}. "
                "This may indicate a newer manifest version or typos.",
                UserWarning,
                stacklevel=2,
            )
        return self


__all__ = [
    "ManifestScope",
    "GovernanceConfig",
    "PlatformManifest",
]
