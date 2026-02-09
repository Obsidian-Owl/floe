"""RBAC enforcement logic for floe-core.

Task: T025
Requirements: FR-002, FR-003

This module implements role-based access control checking by validating
tokens and principal fallbacks against configured RBAC policies.
"""

from __future__ import annotations

from floe_core.enforcement.result import Violation
from floe_core.plugins.identity import IdentityPlugin
from floe_core.schemas.governance import RBACConfig


class RBACChecker:
    """Checks RBAC policies against token credentials.

    This checker validates that tokens or principals meet the configured
    RBAC requirements, including token validation and role membership.

    Args:
        rbac_config: RBAC configuration settings
        identity_plugin: Plugin for token validation
    """

    def __init__(
        self,
        rbac_config: RBACConfig,
        identity_plugin: IdentityPlugin,
    ) -> None:
        """Initialize the RBAC checker.

        Args:
            rbac_config: RBAC configuration settings
            identity_plugin: Plugin for token validation
        """
        self.rbac_config = rbac_config
        self.identity_plugin = identity_plugin

    def check(
        self,
        token: str | None,
        principal: str | None,
    ) -> list[Violation]:
        """Check RBAC policy against provided credentials.

        Args:
            token: OIDC token for authentication
            principal: Principal fallback identifier

        Returns:
            List of violations (empty if valid)
        """
        # RBAC disabled - allow all
        if not self.rbac_config.enabled:
            return []

        # No token provided
        if token is None:
            # Principal fallback allowed
            if principal is not None and self.rbac_config.allow_principal_fallback:
                return []

            # Principal provided but fallback disabled
            if principal is not None:
                return [
                    Violation(
                        error_code="FLOE-E501",
                        severity="error",
                        message="RBAC check failed: principal fallback disabled",
                        policy_type="rbac",
                        model_name="__rbac__",
                        expected="OIDC token (principal fallback disabled)",
                        actual="Principal provided but fallback disabled",
                        suggestion="Provide FLOE_TOKEN environment variable",
                        documentation_url="https://floe.dev/docs/governance/rbac#principal-fallback-disabled",
                    )
                ]

            # No token or principal
            return [
                Violation(
                    error_code="FLOE-E501",
                    severity="error",
                    message="RBAC check failed: token required",
                    policy_type="rbac",
                    model_name="__rbac__",
                    expected="OIDC token or principal fallback",
                    actual="No token or principal provided",
                    suggestion="Set FLOE_TOKEN or provide --principal",
                    documentation_url="https://floe.dev/docs/governance/rbac#missing-token",
                )
            ]

        # Token provided - validate it
        result = self.identity_plugin.validate_token(token)

        if not result.valid:
            return [
                Violation(
                    error_code="FLOE-E502",
                    severity="error",
                    message="OIDC token expired or invalid",
                    policy_type="rbac",
                    model_name="__rbac__",
                    expected="Valid OIDC token",
                    actual=result.error,
                    suggestion="Obtain a fresh token",
                    documentation_url="https://floe.dev/docs/governance/rbac#token-expired",
                )
            ]

        # Token valid, no role required
        if self.rbac_config.required_role is None:
            return []

        # user_info must be present if token is valid
        if result.user_info is None:
            return [
                Violation(
                    error_code="FLOE-E502",
                    severity="error",
                    message="OIDC token valid but user_info missing",
                    policy_type="rbac",
                    model_name="__rbac__",
                    expected="Valid user_info from identity plugin",
                    actual="user_info is None",
                    suggestion="Check identity plugin implementation",
                    documentation_url="https://floe.dev/docs/governance/rbac#token-expired",
                )
            ]

        # Check role membership
        if self.rbac_config.required_role not in result.user_info.roles:
            return [
                Violation(
                    error_code="FLOE-E503",
                    severity="error",
                    message="RBAC check failed: insufficient role",
                    policy_type="rbac",
                    model_name="__rbac__",
                    expected=f"Role: {self.rbac_config.required_role}",
                    actual=f"User roles: {result.user_info.roles}",
                    suggestion="Request role assignment",
                    documentation_url="https://floe.dev/docs/governance/rbac#insufficient-role",
                )
            ]

        # All checks passed
        return []
