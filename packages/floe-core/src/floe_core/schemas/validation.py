"""Security policy validation for manifest schema.

This module provides validation functions for security policy enforcement
during configuration inheritance.

Implements:
    - FR-017: Security Policy Immutability
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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


__all__ = [
    "SecurityPolicyViolationError",
    "InheritanceError",
    "PII_ENCRYPTION_STRENGTH",
    "AUDIT_LOGGING_STRENGTH",
    "POLICY_LEVEL_STRENGTH",
    "validate_security_policy_not_weakened",
]
