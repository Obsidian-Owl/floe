"""Configuration inheritance models for manifest schema.

This module provides models for 3-tier configuration inheritance
(enterprise → domain → product) with merge strategies.

Implements:
    - FR-003: Configuration Inheritance
    - FR-004: Merge Strategies
    - FR-005: Circular Dependency Detection
    - FR-014: Inheritance Chain Resolution
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from floe_core.schemas.manifest import GovernanceConfig, PlatformManifest


class CircularInheritanceError(Exception):
    """Raised when a circular dependency is detected in the inheritance chain.

    Circular dependencies occur when manifest A inherits from B, which inherits
    from A (directly or indirectly).

    Example:
        >>> raise CircularInheritanceError(
        ...     "Circular inheritance detected: A → B → A",
        ...     chain=["A", "B", "A"]
        ... )
    """

    def __init__(self, message: str, chain: list[str] | None = None) -> None:
        """Initialize CircularInheritanceError.

        Args:
            message: Error message describing the circular dependency
            chain: List of manifest URIs showing the circular path
        """
        self.chain = chain or []
        super().__init__(message)


class MergeStrategy(str, Enum):
    """Strategy for merging configuration fields during inheritance.

    Defines how child manifest fields combine with parent manifest fields
    in 3-tier mode (enterprise → domain → product).

    Attributes:
        OVERRIDE: Child completely replaces parent value (default for most fields)
        EXTEND: Child adds to parent value (for lists/dicts)
        FORBID: Parent value is immutable, child cannot change it (security policies)

    Example:
        >>> strategy = MergeStrategy.OVERRIDE
        >>> strategy.value
        'override'

    See Also:
        - data-model.md: MergeStrategy enum specification
        - FIELD_MERGE_STRATEGIES: Default strategies per field
    """

    OVERRIDE = "override"
    EXTEND = "extend"
    FORBID = "forbid"


# Default merge strategies per field (US2: Configuration Inheritance)
# These define how child manifests combine with parent manifests
FIELD_MERGE_STRATEGIES: dict[str, MergeStrategy] = {
    # Plugin selections can be overridden by child
    "plugins": MergeStrategy.OVERRIDE,
    # Governance policies are immutable (cannot weaken)
    "governance": MergeStrategy.FORBID,
    # Approved plugins list is immutable (set by enterprise)
    "approved_plugins": MergeStrategy.FORBID,
    # Approved products list is immutable (set by domain)
    "approved_products": MergeStrategy.FORBID,
    # Metadata always overridden
    "metadata": MergeStrategy.OVERRIDE,
}


class InheritanceChain(BaseModel):
    """Resolved lineage of configurations for 3-tier mode.

    Tracks the full inheritance chain from enterprise through domain to product,
    including the final resolved configuration and field source tracking.

    This model is only used in 3-tier mode (scope=enterprise/domain).
    In 2-tier mode (scope=None), there is no inheritance chain.

    Attributes:
        enterprise: Enterprise-level manifest (scope=enterprise), or None
        domain: Domain-level manifest (scope=domain), or None
        product: Product manifest (the current manifest being resolved)
        resolved: Final merged configuration after applying inheritance
        field_sources: Tracks which tier provided each field value

    Example:
        >>> chain = InheritanceChain(
        ...     enterprise=enterprise_manifest,
        ...     domain=domain_manifest,
        ...     product=product_manifest,
        ...     resolved=merged_manifest,
        ...     field_sources={"plugins.compute": "domain", "governance": "enterprise"}
        ... )

    See Also:
        - data-model.md: InheritanceChain entity specification
        - merge_manifests(): Function that creates resolved chain
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    # Using Any type here to avoid circular import - actual type is PlatformManifest
    # The type checking is done at runtime via model_validator
    enterprise: PlatformManifest | None = Field(
        default=None,
        description="Enterprise-level manifest (scope=enterprise)",
    )
    domain: PlatformManifest | None = Field(
        default=None,
        description="Domain-level manifest (scope=domain)",
    )
    product: PlatformManifest = Field(
        description="Product manifest being resolved",
    )
    resolved: PlatformManifest = Field(
        description="Final merged configuration",
    )
    field_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Maps field paths to source tier (enterprise/domain/product)",
    )


def detect_circular_inheritance(
    manifest_uri: str,
    manifests: dict[str, dict[str, Any]],
    visited: set[str] | None = None,
    chain: list[str] | None = None,
) -> None:
    """Detect circular dependencies in manifest inheritance.

    Traverses the inheritance chain and raises an error if a cycle is detected.

    Args:
        manifest_uri: URI of the manifest to check
        manifests: Dictionary mapping URIs to manifest data (must have parent_manifest key)
        visited: Set of already visited manifest URIs (for recursion)
        chain: List tracking the current inheritance path

    Raises:
        CircularInheritanceError: If a circular dependency is detected

    Example:
        >>> manifests = {
        ...     "oci://A:v1": {"name": "A", "parent_manifest": "oci://B:v1"},
        ...     "oci://B:v1": {"name": "B", "parent_manifest": None},
        ... }
        >>> detect_circular_inheritance("oci://A:v1", manifests)  # No error
    """
    if visited is None:
        visited = set()
    if chain is None:
        chain = []

    if manifest_uri in visited:
        chain.append(manifest_uri)
        cycle_str = " → ".join(chain)
        raise CircularInheritanceError(
            f"Circular inheritance detected: {cycle_str}",
            chain=chain,
        )

    visited.add(manifest_uri)
    chain.append(manifest_uri)

    manifest_data = manifests.get(manifest_uri)
    if manifest_data is None:
        return

    parent_uri = manifest_data.get("parent_manifest")
    if parent_uri is not None:
        detect_circular_inheritance(parent_uri, manifests, visited, chain)


def merge_manifests(
    parent: PlatformManifest,
    child: PlatformManifest,
) -> PlatformManifest:
    """Merge parent and child manifests according to merge strategies.

    Applies the merge strategies defined in FIELD_MERGE_STRATEGIES to combine
    parent and child configurations. Child values take precedence for OVERRIDE
    strategy fields.

    Args:
        parent: Parent manifest (enterprise or domain scope)
        child: Child manifest (domain or product)

    Returns:
        New PlatformManifest with merged values

    Raises:
        ValueError: If merge strategy is FORBID and child attempts to change value

    Example:
        >>> resolved = merge_manifests(enterprise_manifest, domain_manifest)
        >>> resolved.plugins.compute.type
        'duckdb'  # From domain manifest (OVERRIDE strategy)
    """
    # Import here to avoid circular imports
    from floe_core.schemas.manifest import PlatformManifest
    from floe_core.schemas.plugins import PluginsConfig, PluginSelection
    from floe_core.schemas.quality_config import QualityConfig

    # Start with parent's values, override with child's non-None values
    # For plugins, merge at the category level (child overrides parent categories)
    merged_plugins_data: dict[str, PluginSelection | QualityConfig | None] = {}

    # Copy parent plugin selections
    if parent.plugins is not None:
        for category in [
            "compute",
            "orchestrator",
            "catalog",
            "storage",
            "semantic_layer",
            "ingestion",
            "secrets",
            "telemetry_backend",
            "lineage_backend",
            "identity",
            "dbt",
            "quality",
        ]:
            parent_selection = getattr(parent.plugins, category, None)
            if parent_selection is not None:
                merged_plugins_data[category] = parent_selection

    # Override with child plugin selections
    if child.plugins is not None:
        for category in [
            "compute",
            "orchestrator",
            "catalog",
            "storage",
            "semantic_layer",
            "ingestion",
            "secrets",
            "telemetry_backend",
            "lineage_backend",
            "identity",
            "dbt",
            "quality",
        ]:
            child_selection = getattr(child.plugins, category, None)
            if child_selection is not None:
                merged_plugins_data[category] = child_selection

    # Filter out None values before creating PluginsConfig
    merged_plugins_filtered = {
        k: v for k, v in merged_plugins_data.items() if v is not None
    }
    merged_plugins = PluginsConfig(**cast(dict[str, Any], merged_plugins_filtered))

    # For governance, FORBID strategy means child cannot WEAKEN parent's policies.
    # If parent has governance, it's preserved (child can't override).
    # If parent has None, child can ADD governance policies.
    # Note: validate_security_policy_not_weakened() should be called separately
    # before merge to enforce FR-017 (security policy immutability).
    merged_governance: GovernanceConfig | None
    if parent.governance is not None:
        merged_governance = parent.governance
    else:
        merged_governance = child.governance

    # approved_plugins/approved_products are scope-restricted and not propagated during merge:
    # - approved_plugins: only valid for scope='enterprise'
    # - approved_products: only valid for scope='domain'
    #
    # Whitelist validation must happen BEFORE merge via validate_domain_plugin_whitelist().
    # The merged manifest takes child's scope, so these fields are not copied.
    # Enterprise whitelists are enforced but not stored on domain/product manifests.
    merged_approved_plugins = None
    merged_approved_products = None

    # Create merged manifest with child's metadata (OVERRIDE strategy)
    # Note: Using apiVersion (alias) because mypy expects the alias parameter name
    return PlatformManifest(
        apiVersion=child.api_version,  # alias for api_version
        kind=child.kind,
        metadata=child.metadata,  # Child's metadata takes precedence
        scope=child.scope,
        parent_manifest=child.parent_manifest,
        plugins=merged_plugins,
        governance=merged_governance,
        approved_plugins=merged_approved_plugins,
        approved_products=merged_approved_products,
    )


__all__ = [
    "CircularInheritanceError",
    "MergeStrategy",
    "FIELD_MERGE_STRATEGIES",
    "InheritanceChain",
    "detect_circular_inheritance",
    "merge_manifests",
]
