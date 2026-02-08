"""Authorization module for promotion lifecycle (T125-T127).

Task IDs: T125, T126, T127
Phase: 12 - Authorization (US10)
User Story: US10 - Authorization and Access Control
Requirements: FR-045, FR-046, FR-047, FR-048

This module implements authorization checking for promotion operations:
- FR-045: Verify operator identity via registry authentication
- FR-046: Support environment-specific authorization rules
- FR-047: Support group-based access control
- FR-048: Record authorization decisions for audit trail

Example:
    >>> from floe_core.oci.authorization import AuthorizationChecker
    >>> from floe_core.schemas.promotion import AuthorizationConfig
    >>> config = AuthorizationConfig(
    ...     allowed_groups=["platform-admins"],
    ...     separation_of_duties=True,
    ... )
    >>> checker = AuthorizationChecker(config=config)
    >>> result = checker.check_authorization(
    ...     operator="alice@example.com",
    ...     groups=["platform-admins"],
    ... )
    >>> result.authorized
    True
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from floe_core.schemas.promotion import AuthorizationConfig

logger = structlog.get_logger(__name__)


class AuthorizationResult(BaseModel):
    """Result of an authorization check.

    Records the authorization decision for audit trail compliance (FR-048).

    Attributes:
        authorized: Whether access was granted.
        operator: Identity of the operator being checked.
        authorized_via: How authorization was granted (group:name, operator:email, etc.).
        reason: Explanation if access was denied.
        groups_checked: Groups that were checked during authorization.
        checked_at: Timestamp when the check was performed.

    Examples:
        >>> result = AuthorizationResult(
        ...     authorized=True,
        ...     operator="alice@example.com",
        ...     authorized_via="group:platform-admins",
        ... )
        >>> result.authorized
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    authorized: bool = Field(
        ...,
        description="Whether access was granted",
    )
    operator: str = Field(
        ...,
        description="Identity of the operator being checked",
    )
    authorized_via: str | None = Field(
        default=None,
        description="How authorization was granted (group:name, operator:email, etc.)",
    )
    reason: str | None = Field(
        default=None,
        description="Explanation if access was denied",
    )
    groups_checked: list[str] = Field(
        default_factory=list,
        description="Groups that were checked during authorization",
    )
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the check was performed",
    )


class AuthorizationChecker:
    """Authorization checker for promotion operations.

    Implements authorization checking based on AuthorizationConfig rules.
    Supports group-based access (FR-047) and operator-specific access (FR-046).

    Attributes:
        config: AuthorizationConfig with allowed_groups and allowed_operators.

    Examples:
        >>> config = AuthorizationConfig(
        ...     allowed_groups=["platform-admins"],
        ... )
        >>> checker = AuthorizationChecker(config=config)
        >>> result = checker.check_authorization("alice@example.com", ["platform-admins"])
        >>> result.authorized
        True
    """

    def __init__(self, config: AuthorizationConfig | None) -> None:
        """Initialize AuthorizationChecker with configuration.

        Args:
            config: AuthorizationConfig with access rules. If None, all access is allowed.
        """
        self.config = config

    def check_authorization(
        self,
        operator: str,
        groups: list[str],
    ) -> AuthorizationResult:
        """Check if operator is authorized based on configuration.

        Implements FR-046 (environment-specific rules) and FR-047 (group-based access).
        Authorization uses OR semantics: operator is authorized if they match
        ANY allowed_groups OR ANY allowed_operators.

        Args:
            operator: Identity of the operator (email or username).
            groups: List of groups the operator belongs to.

        Returns:
            AuthorizationResult with decision and audit information.
        """
        log = logger.bind(operator=operator, groups=groups)

        # No config means allow all
        if self.config is None:
            log.debug("authorization_allowed_no_config")
            return AuthorizationResult(
                authorized=True,
                operator=operator,
                authorized_via="no_config",
                groups_checked=groups,
            )

        allowed_groups = self.config.allowed_groups
        allowed_operators = self.config.allowed_operators

        # If no restrictions configured, allow all
        if (allowed_groups is None or len(allowed_groups) == 0) and (
            allowed_operators is None or len(allowed_operators) == 0
        ):
            log.debug("authorization_allowed_no_restrictions")
            return AuthorizationResult(
                authorized=True,
                operator=operator,
                authorized_via="no_restrictions",
                groups_checked=groups,
            )

        # Check if operator is in allowed_operators
        if allowed_operators and operator in allowed_operators:
            log.info("authorization_allowed_by_operator", operator=operator)
            return AuthorizationResult(
                authorized=True,
                operator=operator,
                authorized_via=f"operator:{operator}",
                groups_checked=groups,
            )

        # Check if operator is in any allowed_groups
        if allowed_groups:
            for group in groups:
                if group in allowed_groups:
                    log.info("authorization_allowed_by_group", group=group)
                    return AuthorizationResult(
                        authorized=True,
                        operator=operator,
                        authorized_via=f"group:{group}",
                        groups_checked=groups,
                    )

        # Authorization denied
        reason_parts = []
        if allowed_groups:
            reason_parts.append(f"not in allowed groups: {sorted(allowed_groups)}")
        if allowed_operators:
            reason_parts.append(
                f"not in allowed operators: {sorted(allowed_operators)}"
            )

        reason = f"Operator '{operator}' " + " and ".join(reason_parts)

        log.warning(
            "authorization_denied",
            reason=reason,
            allowed_groups=allowed_groups,
            allowed_operators=allowed_operators,
        )
        return AuthorizationResult(
            authorized=False,
            operator=operator,
            reason=reason,
            groups_checked=groups,
        )

    def get_operator_identity(
        self,
        credentials: dict[str, Any] | None,
    ) -> str:
        """Get operator identity from registry credentials (FR-045).

        Attempts to extract operator identity from:
        1. Registry credentials (username field)
        2. FLOE_OPERATOR environment variable
        3. Falls back to "unknown" if neither available

        Args:
            credentials: Registry authentication credentials dict.

        Returns:
            Operator identity string (email or username).
        """
        # Try to get from credentials
        if credentials:
            username = credentials.get("username")
            if username:
                logger.debug("operator_identity_from_credentials", identity=username)
                return str(username)

        # Fall back to environment variable
        env_operator = os.environ.get("FLOE_OPERATOR")
        if env_operator:
            logger.debug("operator_identity_from_env", identity=env_operator)
            return env_operator

        logger.warning("operator_identity_unknown")
        return "unknown"

    def get_operator_groups(
        self,
        metadata: dict[str, Any] | None,
    ) -> list[str]:
        """Get operator groups from registry metadata (FR-045).

        Extracts group membership from registry metadata for authorization.

        Args:
            metadata: Registry metadata containing group information.

        Returns:
            List of group names the operator belongs to.
        """
        if metadata is None:
            return []

        groups = metadata.get("groups", [])
        if isinstance(groups, list):
            logger.debug("operator_groups_from_metadata", groups=groups)
            return groups

        return []

    def check_separation_of_duties(
        self,
        operator: str,
        previous_operator: str | None,
    ) -> SeparationOfDutiesResult:
        """Check if promotion violates separation of duties (T135).

        Implements FR-049 (separation rule), FR-050 (enable/disable), FR-052 (case-insensitive).
        Prevents the same operator from promoting through consecutive environments
        when separation_of_duties is enabled.

        Args:
            operator: Identity of the operator attempting this promotion.
            previous_operator: Identity of operator who promoted to the previous
                environment. None if this is the first promotion in the chain.

        Returns:
            SeparationOfDutiesResult with allowed status and reason if denied.
        """
        log = logger.bind(operator=operator, previous_operator=previous_operator)

        # If separation of duties is not enabled, always allow
        if self.config is None or not self.config.separation_of_duties:
            log.debug("separation_of_duties_disabled")
            return SeparationOfDutiesResult(
                allowed=True,
                operator=operator,
                previous_operator=previous_operator,
            )

        # If no previous operator, this is first promotion - allow
        if previous_operator is None:
            log.debug("separation_of_duties_no_previous_operator")
            return SeparationOfDutiesResult(
                allowed=True,
                operator=operator,
                previous_operator=None,
            )

        # Case-insensitive comparison (FR-052)
        current_normalized = operator.lower().strip()
        previous_normalized = previous_operator.lower().strip()

        if current_normalized == previous_normalized:
            reason = (
                f"Separation of duties violation: operator '{operator}' cannot "
                f"promote to consecutive environments. Previous promotion was also "
                f"performed by '{previous_operator}'."
            )
            log.warning(
                "separation_of_duties_violation",
                reason=reason,
            )
            return SeparationOfDutiesResult(
                allowed=False,
                operator=operator,
                previous_operator=previous_operator,
                reason=reason,
            )

        log.debug("separation_of_duties_passed")
        return SeparationOfDutiesResult(
            allowed=True,
            operator=operator,
            previous_operator=previous_operator,
        )


class SeparationOfDutiesResult(BaseModel):
    """Result of a separation of duties check (T135).

    Records whether a promotion is allowed based on separation of duties rules.
    Implements FR-051 (result schema), FR-052 (immutability).

    Attributes:
        allowed: Whether the promotion is allowed.
        operator: Identity of the operator attempting promotion.
        previous_operator: Identity of operator who promoted to previous env.
        reason: Explanation if denied.

    Examples:
        >>> result = SeparationOfDutiesResult(
        ...     allowed=True,
        ...     operator="bob@example.com",
        ...     previous_operator="alice@example.com",
        ... )
        >>> result.allowed
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool = Field(
        ...,
        description="Whether the promotion is allowed",
    )
    operator: str = Field(
        ...,
        description="Identity of the operator attempting promotion",
    )
    previous_operator: str | None = Field(
        default=None,
        description="Identity of operator who promoted to previous environment",
    )
    reason: str | None = Field(
        default=None,
        description="Explanation if denied",
    )


__all__: list[str] = [
    "AuthorizationResult",
    "AuthorizationChecker",
    "SeparationOfDutiesResult",
]
