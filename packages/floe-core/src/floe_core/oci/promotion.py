"""Promotion Controller for artifact promotion lifecycle.

This module provides the PromotionController class for promoting artifacts
through environment stages (e.g., dev -> staging -> prod) with validation gates.

The controller integrates with:
    - OCI registry operations (Epic 8A)
    - Signature verification (Epic 8B)
    - Policy enforcement (Epic 3B)
    - Audit logging

Key Features:
    - Promote artifacts between environments
    - Validate gates before promotion (policy, tests, security)
    - Rollback to previous versions
    - Environment lock/unlock for maintenance
    - Dry-run mode for validation without changes
    - OpenTelemetry tracing

Example:
    >>> from floe_core.oci.promotion import PromotionController
    >>> from floe_core.schemas.oci import RegistryConfig
    >>> from floe_core.schemas.promotion import PromotionConfig
    >>>
    >>> # Create controller
    >>> controller = PromotionController(
    ...     registry=registry_config,
    ...     promotion=promotion_config
    ... )
    >>>
    >>> # Promote artifact from dev to staging
    >>> record = controller.promote(
    ...     tag="v1.0.0",
    ...     from_env="dev",
    ...     to_env="staging",
    ...     operator="ci@github.com"
    ... )
    >>>
    >>> # Check promotion status
    >>> status = controller.status(environment="staging")

See Also:
    - specs/8c-promotion-lifecycle/spec.md: Feature specification
    - specs/8c-promotion-lifecycle/data-model.md: Data model
"""

from __future__ import annotations

import structlog

from floe_core.oci.errors import InvalidTransitionError
from floe_core.schemas.oci import RegistryConfig
from floe_core.schemas.promotion import (
    EnvironmentConfig,
    PromotionConfig,
    PromotionRecord,
    RollbackRecord,
)

logger = structlog.get_logger(__name__)


class PromotionController:
    """Controller for artifact promotion lifecycle.

    Manages the promotion of artifacts through environment stages with
    validation gates, signature verification, and audit logging.

    Attributes:
        registry: OCI registry configuration
        promotion: Promotion lifecycle configuration

    Example:
        >>> controller = PromotionController(
        ...     registry=registry_config,
        ...     promotion=PromotionConfig()  # Default [dev, staging, prod]
        ... )
        >>> record = controller.promote("v1.0.0", "dev", "staging", "operator@example.com")
    """

    def __init__(
        self,
        registry: RegistryConfig,
        promotion: PromotionConfig,
    ) -> None:
        """Initialize the PromotionController.

        Args:
            registry: OCI registry configuration for artifact operations.
            promotion: Promotion lifecycle configuration with environments and gates.
        """
        self.registry = registry
        self.promotion = promotion
        self._log = logger.bind(
            registry_uri=registry.uri,
            environments=[e.name for e in promotion.environments],
        )
        self._log.info("promotion_controller_initialized")

    def _get_environment(self, name: str) -> EnvironmentConfig | None:
        """Get environment configuration by name.

        Args:
            name: Environment name to look up.

        Returns:
            EnvironmentConfig if found, None otherwise.
        """
        for env in self.promotion.environments:
            if env.name == name:
                return env
        return None

    def _get_environment_index(self, name: str) -> int:
        """Get environment index in the promotion path.

        Args:
            name: Environment name to look up.

        Returns:
            Index of environment in promotion.environments list.

        Raises:
            ValueError: If environment not found.
        """
        for idx, env in enumerate(self.promotion.environments):
            if env.name == name:
                return idx
        raise ValueError(f"Environment '{name}' not found in promotion path")

    def _validate_transition(self, from_env: str, to_env: str) -> None:
        """Validate that a promotion transition is allowed.

        Validates that:
            1. Both environments exist in the promotion path
            2. Target environment is exactly one step after source
            3. Promotion is not backward (lower index to higher)

        Args:
            from_env: Source environment name.
            to_env: Target environment name.

        Raises:
            InvalidTransitionError: If transition is not allowed.
        """
        # Check source environment exists
        try:
            from_idx = self._get_environment_index(from_env)
        except ValueError:
            raise InvalidTransitionError(
                from_env=from_env,
                to_env=to_env,
                reason=f"Unknown source environment: '{from_env}'",
            )

        # Check target environment exists
        try:
            to_idx = self._get_environment_index(to_env)
        except ValueError:
            raise InvalidTransitionError(
                from_env=from_env,
                to_env=to_env,
                reason=f"Unknown target environment: '{to_env}'",
            )

        # Check forward direction (not backward)
        if to_idx <= from_idx:
            raise InvalidTransitionError(
                from_env=from_env,
                to_env=to_env,
                reason=f"Invalid direction: cannot promote backward from '{from_env}' to '{to_env}'",
            )

        # Check adjacent environments (no skipping)
        if to_idx != from_idx + 1:
            skipped_envs = [
                self.promotion.environments[i].name
                for i in range(from_idx + 1, to_idx)
            ]
            raise InvalidTransitionError(
                from_env=from_env,
                to_env=to_env,
                reason=f"Cannot skip environments: must promote through {skipped_envs}",
            )

    def promote(
        self,
        tag: str,
        from_env: str,
        to_env: str,
        operator: str,
        *,
        dry_run: bool = False,
    ) -> PromotionRecord:
        """Promote an artifact from one environment to the next.

        Executes validation gates, verifies signatures (if configured),
        creates environment tags, and records the promotion in the audit trail.

        Args:
            tag: Artifact tag to promote (e.g., "v1.0.0").
            from_env: Source environment name.
            to_env: Target environment name.
            operator: Identity of the operator performing the promotion.
            dry_run: If True, validate without making changes.

        Returns:
            PromotionRecord with promotion details and gate results.

        Raises:
            InvalidTransitionError: If transition path is invalid.
            GateValidationError: If any gate validation fails.
            AuthorizationError: If operator is not authorized.
            EnvironmentLockedError: If target environment is locked.

        Example:
            >>> record = controller.promote("v1.0.0", "dev", "staging", "ci@github.com")
            >>> print(f"Promoted to staging: {record.promotion_id}")
        """
        self._log.info(
            "promote_started",
            tag=tag,
            from_env=from_env,
            to_env=to_env,
            operator=operator,
            dry_run=dry_run,
        )

        # Validate transition path
        self._validate_transition(from_env, to_env)

        # TODO: T014+ - Implement full promotion logic
        # 1. Verify artifact exists with source tag
        # 2. Verify signature (if enforcement enabled)
        # 3. Check authorization
        # 4. Check environment lock
        # 5. Run validation gates
        # 6. Create immutable environment tag
        # 7. Update mutable latest tag
        # 8. Write promotion record

        raise NotImplementedError("Full promote implementation in T014+")

    def rollback(
        self,
        tag: str,
        environment: str,
        reason: str,
        operator: str,
    ) -> RollbackRecord:
        """Rollback an environment to a previous artifact version.

        Args:
            tag: Target artifact tag to rollback to.
            environment: Environment to rollback.
            reason: Operator-provided reason for rollback.
            operator: Identity of the operator performing the rollback.

        Returns:
            RollbackRecord with rollback details.

        Raises:
            VersionNotPromotedError: If target version was never promoted to this environment.
            AuthorizationError: If operator is not authorized.
            EnvironmentLockedError: If environment is locked.

        Example:
            >>> record = controller.rollback("v1.0.0", "prod", "Hotfix rollback", "sre@example.com")
        """
        self._log.info(
            "rollback_started",
            tag=tag,
            environment=environment,
            reason=reason,
            operator=operator,
        )

        # TODO: T050+ - Implement rollback logic
        raise NotImplementedError("Rollback implementation in T050+")

    def status(self, environment: str | None = None) -> dict:
        """Get promotion status for environment(s).

        Args:
            environment: Specific environment to query, or None for all.

        Returns:
            Dictionary with environment status information.

        Example:
            >>> status = controller.status("prod")
            >>> print(f"Current version: {status['current_version']}")
        """
        self._log.info("status_requested", environment=environment)

        # TODO: T060+ - Implement status logic
        raise NotImplementedError("Status implementation in T060+")

    def dry_run(
        self,
        tag: str,
        from_env: str,
        to_env: str,
        operator: str,
    ) -> PromotionRecord:
        """Perform a dry-run promotion (validate without changes).

        Equivalent to promote(..., dry_run=True).

        Args:
            tag: Artifact tag to validate.
            from_env: Source environment name.
            to_env: Target environment name.
            operator: Identity of the operator.

        Returns:
            PromotionRecord showing what would happen.

        Example:
            >>> record = controller.dry_run("v1.0.0", "dev", "staging", "ci@github.com")
            >>> print(f"Gates would pass: {all(g.status == 'passed' for g in record.gate_results)}")
        """
        return self.promote(tag, from_env, to_env, operator, dry_run=True)

    def lock_environment(
        self,
        environment: str,
        reason: str,
        operator: str,
    ) -> None:
        """Lock an environment to prevent promotions.

        Args:
            environment: Environment to lock.
            reason: Reason for locking (e.g., "Maintenance window").
            operator: Identity of the operator.

        Raises:
            ValueError: If environment does not exist.

        Example:
            >>> controller.lock_environment("prod", "Database migration", "dba@example.com")
        """
        self._log.info(
            "lock_environment",
            environment=environment,
            reason=reason,
            operator=operator,
        )

        if self._get_environment(environment) is None:
            raise ValueError(f"Environment '{environment}' not found")

        # TODO: T102+ - Implement lock logic
        raise NotImplementedError("Lock implementation in T102+")

    def unlock_environment(
        self,
        environment: str,
        reason: str,
        operator: str,
    ) -> None:
        """Unlock an environment to allow promotions.

        Args:
            environment: Environment to unlock.
            reason: Reason for unlocking.
            operator: Identity of the operator.

        Raises:
            ValueError: If environment does not exist.

        Example:
            >>> controller.unlock_environment("prod", "Migration complete", "dba@example.com")
        """
        self._log.info(
            "unlock_environment",
            environment=environment,
            reason=reason,
            operator=operator,
        )

        if self._get_environment(environment) is None:
            raise ValueError(f"Environment '{environment}' not found")

        # TODO: T103+ - Implement unlock logic
        raise NotImplementedError("Unlock implementation in T103+")


__all__ = ["PromotionController"]
