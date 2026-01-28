"""Quality configuration inheritance resolver.

This module implements three-tier inheritance resolution for quality configuration:
Enterprise → Domain → Product

Each level can define quality settings (gates, thresholds, weights).
Higher levels can lock settings with overridable: false to prevent
lower levels from modifying them.

T074: Three-tier inheritance resolution
T075: Locked setting enforcement (FLOE-DQ107)
"""

from __future__ import annotations

from typing import Any

from floe_core.quality_errors import QualityOverrideError
from floe_core.schemas.quality_config import (
    CalculationParameters,
    DimensionWeights,
    GateTier,
    QualityConfig,
    QualityGates,
    QualityThresholds,
)

INHERITANCE_LEVELS = ["enterprise", "domain", "product"]


def resolve_quality_inheritance(
    enterprise_config: QualityConfig | None,
    domain_config: QualityConfig | None,
    product_config: QualityConfig | None,
) -> QualityConfig:
    """Resolve quality configuration through three-tier inheritance.

    Configuration flows: Enterprise → Domain → Product
    Each level inherits from the previous and can override settings
    unless they are locked (overridable: false).

    Args:
        enterprise_config: Enterprise-level quality configuration (base).
        domain_config: Domain-level quality configuration (inherits from enterprise).
        product_config: Product-level quality configuration (inherits from domain).

    Returns:
        Fully resolved QualityConfig with merged settings.

    Raises:
        QualityOverrideError: If a lower level attempts to override a locked setting.
    """
    configs = [
        ("enterprise", enterprise_config),
        ("domain", domain_config),
        ("product", product_config),
    ]

    result: dict[str, Any] = {}
    locked_settings: dict[str, str] = {}

    for level, config in configs:
        if config is None:
            continue

        _merge_config_level(result, config, level, locked_settings)

    if not result:
        return QualityConfig(provider="great_expectations")

    return QualityConfig(**result)


def _merge_config_level(
    result: dict[str, Any],
    config: QualityConfig,
    level: str,
    locked_settings: dict[str, str],
) -> None:
    """Merge a single configuration level into the result.

    Args:
        result: Current merged result (mutated in place).
        config: Configuration at this level.
        level: Level name (enterprise, domain, product).
        locked_settings: Dict mapping setting name to level that locked it.

    Raises:
        QualityOverrideError: If attempting to override a locked setting.
    """
    config_dict = config.model_dump()

    for key, value in config_dict.items():
        if key in locked_settings:
            if key in result and result[key] != value:
                raise QualityOverrideError(
                    setting_name=key,
                    locked_by=locked_settings[key],
                    attempted_by=level,
                )
        result[key] = value

    _check_gate_tier_locks(result, config, level, locked_settings)


def _check_gate_tier_locks(
    result: dict[str, Any],
    config: QualityConfig,
    level: str,
    locked_settings: dict[str, str],
) -> None:
    """Check and track locked settings in quality gates.

    Gate tiers (bronze, silver, gold) can have overridable: false
    which prevents lower levels from modifying those tier requirements.

    Args:
        result: Current merged result.
        config: Configuration at this level.
        level: Level name.
        locked_settings: Dict to track locked settings (mutated).
    """
    for tier_name in ["bronze", "silver", "gold"]:
        tier = getattr(config.quality_gates, tier_name, None)
        if tier is None:
            continue

        if not tier.overridable:
            lock_key = f"quality_gates.{tier_name}"
            if lock_key not in locked_settings:
                locked_settings[lock_key] = level


def merge_gate_tiers(
    parent_gates: QualityGates,
    child_gates: QualityGates | None,
    parent_level: str,
    child_level: str,
) -> QualityGates:
    """Merge quality gate tiers with inheritance and lock checking.

    Args:
        parent_gates: Parent level quality gates.
        child_gates: Child level quality gates (may be None).
        parent_level: Name of parent level.
        child_level: Name of child level.

    Returns:
        Merged QualityGates.

    Raises:
        QualityOverrideError: If child attempts to override locked tier.
    """
    if child_gates is None:
        return parent_gates

    merged_tiers: dict[str, GateTier] = {}

    for tier_name in ["bronze", "silver", "gold"]:
        parent_tier = getattr(parent_gates, tier_name)
        child_tier = getattr(child_gates, tier_name)

        if not parent_tier.overridable and _tier_differs(parent_tier, child_tier):
            raise QualityOverrideError(
                setting_name=f"quality_gates.{tier_name}",
                locked_by=parent_level,
                attempted_by=child_level,
            )

        merged_tiers[tier_name] = child_tier if child_tier else parent_tier

    return QualityGates(**merged_tiers)


def _tier_differs(parent: GateTier, child: GateTier) -> bool:
    """Check if child tier differs from parent (ignoring overridable flag)."""
    return (
        parent.min_test_coverage != child.min_test_coverage
        or set(parent.required_tests) != set(child.required_tests)
        or parent.min_score != child.min_score
    )


def merge_thresholds(
    parent: QualityThresholds,
    child: QualityThresholds | None,
) -> QualityThresholds:
    """Merge quality thresholds with child overriding parent."""
    if child is None:
        return parent
    return child


def merge_dimension_weights(
    parent: DimensionWeights,
    child: DimensionWeights | None,
) -> DimensionWeights:
    """Merge dimension weights with child overriding parent."""
    if child is None:
        return parent
    return child


def merge_calculation_params(
    parent: CalculationParameters,
    child: CalculationParameters | None,
) -> CalculationParameters:
    """Merge calculation parameters with child overriding parent."""
    if child is None:
        return parent
    return child


__all__ = [
    "merge_calculation_params",
    "merge_dimension_weights",
    "merge_gate_tiers",
    "merge_thresholds",
    "resolve_quality_inheritance",
]
