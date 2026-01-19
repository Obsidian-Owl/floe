"""Security policy validation for manifest schema.

This module provides validation functions for security policy enforcement
during configuration inheritance.

Implements:
    - FR-017: Security Policy Immutability

Task: T015-T017 (Epic 3A extension)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from floe_core.schemas.governance import (
        LayerThresholds,
        NamingConfig,
        QualityGatesConfig,
    )
    from floe_core.schemas.manifest import GovernanceConfig


class SecurityPolicyViolationError(Exception):
    """Raised when a child manifest attempts to weaken parent security policies.

    Security policies in 3-tier mode (enterprise → domain) are immutable.
    Child manifests can only maintain or strengthen parent policies.

    Example:
        >>> raise SecurityPolicyViolationError(
        ...     field="pii_encryption",
        ...     parent_value="required",
        ...     child_value="optional",
        ...     message="Cannot weaken pii_encryption from 'required' to 'optional'"
        ... )
    """

    def __init__(
        self,
        field: str,
        parent_value: str | int | None,
        child_value: str | int | None,
        message: str | None = None,
    ) -> None:
        """Initialize SecurityPolicyViolationError.

        Args:
            field: The security policy field that was weakened
            parent_value: The parent's policy value
            child_value: The child's attempted policy value
            message: Optional custom error message
        """
        self.field = field
        self.parent_value = parent_value
        self.child_value = child_value
        if message is None:
            message = (
                f"Cannot weaken security policy '{field}' from "
                f"'{parent_value}' to '{child_value}'. "
                "Child manifests can only maintain or strengthen parent policies."
            )
        super().__init__(message)


class InheritanceError(Exception):
    """Raised when there is an error in inheritance resolution.

    Example:
        >>> raise InheritanceError("Failed to resolve parent manifest")
    """

    pass


# Policy strength ordering constants (T031)
# Higher values indicate stricter policies
PII_ENCRYPTION_STRENGTH: dict[str, int] = {
    "optional": 1,
    "required": 2,
}
"""PII encryption strength ordering: required (2) > optional (1)."""

AUDIT_LOGGING_STRENGTH: dict[str, int] = {
    "disabled": 1,
    "enabled": 2,
}
"""Audit logging strength ordering: enabled (2) > disabled (1)."""

POLICY_LEVEL_STRENGTH: dict[str, int] = {
    "off": 1,
    "warn": 2,
    "strict": 3,
}
"""Policy enforcement level strength ordering: strict (3) > warn (2) > off (1)."""

# T015: Naming enforcement strength constants (Epic 3A)
NAMING_ENFORCEMENT_STRENGTH: dict[str, int] = {
    "off": 1,
    "warn": 2,
    "strict": 3,
}
"""Naming enforcement level strength ordering: strict (3) > warn (2) > off (1)."""


def validate_security_policy_not_weakened(
    parent: GovernanceConfig,
    child: GovernanceConfig,
) -> None:
    """Validate that child does not weaken parent security policies.

    Security policies in 3-tier mode are immutable. Child manifests can only
    maintain or strengthen parent policies, never weaken them.

    Args:
        parent: Parent manifest's governance configuration
        child: Child manifest's governance configuration

    Raises:
        SecurityPolicyViolationError: If child attempts to weaken any policy

    Example:
        >>> from floe_core.schemas import GovernanceConfig
        >>> parent = GovernanceConfig(pii_encryption="required")
        >>> child = GovernanceConfig(pii_encryption="optional")
        >>> validate_security_policy_not_weakened(parent, child)
        Traceback (most recent call last):
            ...
        SecurityPolicyViolationError: Cannot weaken security policy 'pii_encryption'...

    Strength Ordering:
        - pii_encryption: required > optional
        - audit_logging: enabled > disabled
        - policy_enforcement_level: strict > warn > off
        - data_retention_days: higher is stricter
    """
    # Check pii_encryption
    if parent.pii_encryption is not None and child.pii_encryption is not None:
        parent_strength = PII_ENCRYPTION_STRENGTH.get(parent.pii_encryption, 0)
        child_strength = PII_ENCRYPTION_STRENGTH.get(child.pii_encryption, 0)
        if child_strength < parent_strength:
            raise SecurityPolicyViolationError(
                field="pii_encryption",
                parent_value=parent.pii_encryption,
                child_value=child.pii_encryption,
            )

    # Check audit_logging
    if parent.audit_logging is not None and child.audit_logging is not None:
        parent_strength = AUDIT_LOGGING_STRENGTH.get(parent.audit_logging, 0)
        child_strength = AUDIT_LOGGING_STRENGTH.get(child.audit_logging, 0)
        if child_strength < parent_strength:
            raise SecurityPolicyViolationError(
                field="audit_logging",
                parent_value=parent.audit_logging,
                child_value=child.audit_logging,
            )

    # Check policy_enforcement_level
    if parent.policy_enforcement_level is not None and child.policy_enforcement_level is not None:
        parent_strength = POLICY_LEVEL_STRENGTH.get(parent.policy_enforcement_level, 0)
        child_strength = POLICY_LEVEL_STRENGTH.get(child.policy_enforcement_level, 0)
        if child_strength < parent_strength:
            raise SecurityPolicyViolationError(
                field="policy_enforcement_level",
                parent_value=parent.policy_enforcement_level,
                child_value=child.policy_enforcement_level,
            )

    # Check data_retention_days (higher is stricter)
    if parent.data_retention_days is not None and child.data_retention_days is not None:
        if child.data_retention_days < parent.data_retention_days:
            raise SecurityPolicyViolationError(
                field="data_retention_days",
                parent_value=parent.data_retention_days,
                child_value=child.data_retention_days,
                message=(
                    f"Cannot weaken data_retention_days from "
                    f"{parent.data_retention_days} to {child.data_retention_days}. "
                    "Child manifests must maintain or increase retention period."
                ),
            )

    # T016: Check naming configuration (Epic 3A)
    if parent.naming is not None and child.naming is not None:
        _validate_naming_config_not_weakened(parent.naming, child.naming)

    # T017: Check quality_gates configuration (Epic 3A)
    if parent.quality_gates is not None and child.quality_gates is not None:
        _validate_quality_gates_not_weakened(parent.quality_gates, child.quality_gates)


def _validate_naming_config_not_weakened(
    parent: NamingConfig,
    child: NamingConfig,
) -> None:
    """Validate that child does not weaken parent naming configuration.

    Args:
        parent: Parent's naming configuration
        child: Child's naming configuration

    Raises:
        SecurityPolicyViolationError: If child attempts to weaken naming config
    """
    # Check naming.enforcement
    parent_strength = NAMING_ENFORCEMENT_STRENGTH.get(parent.enforcement, 0)
    child_strength = NAMING_ENFORCEMENT_STRENGTH.get(child.enforcement, 0)
    if child_strength < parent_strength:
        raise SecurityPolicyViolationError(
            field="naming.enforcement",
            parent_value=parent.enforcement,
            child_value=child.enforcement,
        )


def _validate_quality_gates_not_weakened(
    parent: QualityGatesConfig,
    child: QualityGatesConfig,
) -> None:
    """Validate that child does not weaken parent quality gates configuration.

    Args:
        parent: Parent's quality gates configuration
        child: Child's quality gates configuration

    Raises:
        SecurityPolicyViolationError: If child attempts to weaken quality gates
    """
    # Check minimum_test_coverage (higher is stricter)
    if child.minimum_test_coverage < parent.minimum_test_coverage:
        raise SecurityPolicyViolationError(
            field="quality_gates.minimum_test_coverage",
            parent_value=parent.minimum_test_coverage,
            child_value=child.minimum_test_coverage,
        )

    # Check require_descriptions (True > False)
    if parent.require_descriptions and not child.require_descriptions:
        raise SecurityPolicyViolationError(
            field="quality_gates.require_descriptions",
            parent_value=parent.require_descriptions,
            child_value=child.require_descriptions,
        )

    # Check require_column_descriptions (True > False)
    if parent.require_column_descriptions and not child.require_column_descriptions:
        raise SecurityPolicyViolationError(
            field="quality_gates.require_column_descriptions",
            parent_value=parent.require_column_descriptions,
            child_value=child.require_column_descriptions,
        )

    # Check block_on_failure (True > False - cannot relax)
    if parent.block_on_failure and not child.block_on_failure:
        raise SecurityPolicyViolationError(
            field="quality_gates.block_on_failure",
            parent_value=parent.block_on_failure,
            child_value=child.block_on_failure,
        )

    # Check layer_thresholds (each layer threshold must not decrease)
    if parent.layer_thresholds is not None and child.layer_thresholds is not None:
        _validate_layer_thresholds_not_weakened(parent.layer_thresholds, child.layer_thresholds)


def _validate_layer_thresholds_not_weakened(
    parent: LayerThresholds,
    child: LayerThresholds,
) -> None:
    """Validate that child does not weaken parent layer thresholds.

    Args:
        parent: Parent's layer thresholds
        child: Child's layer thresholds

    Raises:
        SecurityPolicyViolationError: If child attempts to weaken any threshold
    """
    # Check bronze threshold
    if child.bronze < parent.bronze:
        raise SecurityPolicyViolationError(
            field="quality_gates.layer_thresholds.bronze",
            parent_value=parent.bronze,
            child_value=child.bronze,
        )

    # Check silver threshold
    if child.silver < parent.silver:
        raise SecurityPolicyViolationError(
            field="quality_gates.layer_thresholds.silver",
            parent_value=parent.silver,
            child_value=child.silver,
        )

    # Check gold threshold
    if child.gold < parent.gold:
        raise SecurityPolicyViolationError(
            field="quality_gates.layer_thresholds.gold",
            parent_value=parent.gold,
            child_value=child.gold,
        )


__all__ = [
    "SecurityPolicyViolationError",
    "InheritanceError",
    "PII_ENCRYPTION_STRENGTH",
    "AUDIT_LOGGING_STRENGTH",
    "POLICY_LEVEL_STRENGTH",
    "NAMING_ENFORCEMENT_STRENGTH",
    "validate_security_policy_not_weakened",
]
