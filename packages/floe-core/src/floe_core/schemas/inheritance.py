"""Configuration inheritance models for manifest schema.

This module provides models for 3-tier configuration inheritance
(enterprise → domain → product) with merge strategies.

Implements:
    - FR-003: Configuration Inheritance
    - FR-004: Merge Strategies
    - FR-014: Inheritance Chain Resolution
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from floe_core.schemas.manifest import PlatformManifest


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
    enterprise: "PlatformManifest | None" = Field(
        default=None,
        description="Enterprise-level manifest (scope=enterprise)",
    )
    domain: "PlatformManifest | None" = Field(
        default=None,
        description="Domain-level manifest (scope=domain)",
    )
    product: "PlatformManifest" = Field(
        description="Product manifest being resolved",
    )
    resolved: "PlatformManifest" = Field(
        description="Final merged configuration",
    )
    field_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Maps field paths to source tier (enterprise/domain/product)",
    )


__all__ = [
    "MergeStrategy",
    "FIELD_MERGE_STRATEGIES",
    "InheritanceChain",
]
