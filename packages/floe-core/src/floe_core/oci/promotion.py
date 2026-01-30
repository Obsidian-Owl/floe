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

import subprocess
import time
from typing import TYPE_CHECKING

import structlog

from floe_core.oci.errors import InvalidTransitionError
from floe_core.schemas.promotion import (
    EnvironmentConfig,
    GateResult,
    GateStatus,
    PromotionConfig,
    PromotionGate,
    PromotionRecord,
    RollbackRecord,
)

if TYPE_CHECKING:
    from floe_core.enforcement import PolicyEnforcer
    from floe_core.oci.client import OCIClient
    from floe_core.schemas.oci import RegistryConfig
    from floe_core.schemas.signing import VerificationResult

logger = structlog.get_logger(__name__)


class PromotionController:
    """Controller for artifact promotion lifecycle.

    Manages the promotion of artifacts through environment stages with
    validation gates, signature verification, and audit logging.

    Attributes:
        client: OCI client for registry operations
        promotion: Promotion lifecycle configuration
        policy_enforcer: Optional policy enforcer for compliance gates

    Example:
        >>> from floe_core.oci import OCIClient
        >>> client = OCIClient.from_registry_config(registry_config)
        >>> controller = PromotionController(
        ...     client=client,
        ...     promotion=PromotionConfig()  # Default [dev, staging, prod]
        ... )
        >>> record = controller.promote("v1.0.0", "dev", "staging", "operator@example.com")
    """

    def __init__(
        self,
        promotion: PromotionConfig,
        *,
        client: OCIClient | None = None,
        registry: RegistryConfig | None = None,
        policy_enforcer: PolicyEnforcer | None = None,
    ) -> None:
        """Initialize the PromotionController.

        Can be initialized with either an OCIClient (preferred) or a RegistryConfig
        (legacy, will create client internally).

        Args:
            promotion: Promotion lifecycle configuration with environments and gates.
            client: OCIClient instance for registry operations. Preferred.
            registry: Legacy: RegistryConfig to create OCIClient from.
                Deprecated - use client parameter instead.
            policy_enforcer: Optional PolicyEnforcer for policy_compliance gate.
                If None, policy_compliance gate will be skipped.

        Raises:
            ValueError: If neither client nor registry is provided.
        """
        # Handle both new (client=) and legacy (registry=) initialization
        if client is not None:
            self.client = client
        elif registry is not None:
            # Legacy path: create OCIClient from RegistryConfig
            from floe_core.oci.client import OCIClient

            self.client = OCIClient.from_registry_config(registry)
        else:
            raise ValueError("Either client or registry must be provided")

        self.promotion = promotion
        self.policy_enforcer = policy_enforcer

        self._log = logger.bind(
            registry_uri=self.client.registry_uri,
            environments=[e.name for e in promotion.environments],
            has_policy_enforcer=policy_enforcer is not None,
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

    def _run_gate(
        self,
        gate: PromotionGate,
        command: str,
        timeout_seconds: int,
    ) -> GateResult:
        """Execute a single validation gate with timeout handling.

        Runs the gate command as a subprocess with timeout enforcement.
        If the command exceeds the timeout, SIGTERM is sent first,
        then SIGKILL after a 5-second grace period.

        Args:
            gate: The gate type being executed.
            command: Shell command to run for the gate.
            timeout_seconds: Maximum execution time in seconds.

        Returns:
            GateResult with status, duration, and any error message.

        Note:
            Duration is recorded even for timed-out gates.
        """
        start_time = time.monotonic()
        grace_period = 5  # Seconds to wait after SIGTERM before SIGKILL

        self._log.info(
            "gate_execution_started",
            gate=gate.value,
            command=command,
            timeout_seconds=timeout_seconds,
        )

        try:
            # Try simple subprocess.run first (covers most cases)
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            duration_ms = int((time.monotonic() - start_time) * 1000)

            if result.returncode == 0:
                self._log.info(
                    "gate_execution_passed",
                    gate=gate.value,
                    duration_ms=duration_ms,
                )
                return GateResult(
                    gate=gate,
                    status=GateStatus.PASSED,
                    duration_ms=duration_ms,
                    details={"stdout": result.stdout, "stderr": result.stderr},
                )
            else:
                error_msg = f"Gate failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg = f"{error_msg}: {result.stderr.strip()}"

                self._log.warning(
                    "gate_execution_failed",
                    gate=gate.value,
                    duration_ms=duration_ms,
                    exit_code=result.returncode,
                    error=error_msg,
                )
                return GateResult(
                    gate=gate,
                    status=GateStatus.FAILED,
                    duration_ms=duration_ms,
                    error=error_msg,
                    details={"stdout": result.stdout, "stderr": result.stderr},
                )

        except subprocess.TimeoutExpired:
            # Timeout handling with SIGTERM -> SIGKILL escalation
            duration_ms = int((time.monotonic() - start_time) * 1000)

            # For proper SIGTERM/SIGKILL handling, use Popen
            try:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                proc.terminate()  # Send SIGTERM

                try:
                    proc.wait(timeout=grace_period)
                except subprocess.TimeoutExpired:
                    proc.kill()  # Send SIGKILL after grace period
                    proc.wait()

            except Exception:
                # If Popen fails, we've already recorded the timeout
                pass

            error_msg = f"Gate execution timed out after {timeout_seconds} seconds"
            self._log.warning(
                "gate_execution_timeout",
                gate=gate.value,
                duration_ms=duration_ms,
                timeout_seconds=timeout_seconds,
            )
            return GateResult(
                gate=gate,
                status=GateStatus.FAILED,
                duration_ms=duration_ms,
                error=error_msg,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            error_msg = f"Gate execution error: {e}"

            self._log.error(
                "gate_execution_error",
                gate=gate.value,
                duration_ms=duration_ms,
                error=str(e),
            )
            return GateResult(
                gate=gate,
                status=GateStatus.FAILED,
                duration_ms=duration_ms,
                error=error_msg,
            )

    def _run_policy_compliance_gate(
        self,
        manifest: dict,
        *,
        dry_run: bool = False,
    ) -> GateResult:
        """Execute the policy compliance gate using PolicyEnforcer.

        Integrates with Epic 3B's PolicyEnforcer to validate artifacts against
        governance policies before promotion.

        Args:
            manifest: The dbt manifest dictionary to validate.
            dry_run: If True, violations are reported as warnings.

        Returns:
            GateResult with status based on enforcement result.

        Note:
            If no PolicyEnforcer is configured, returns SKIPPED status.
        """
        start_time = time.monotonic()

        # If no PolicyEnforcer configured, skip this gate
        if self.policy_enforcer is None:
            self._log.info(
                "policy_compliance_gate_skipped",
                reason="no_policy_enforcer_configured",
            )
            return GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.SKIPPED,
                duration_ms=0,
            )

        self._log.info(
            "policy_compliance_gate_started",
            dry_run=dry_run,
        )

        try:
            # Call PolicyEnforcer.enforce()
            result = self.policy_enforcer.enforce(
                manifest=manifest,
                dry_run=dry_run,
            )

            duration_ms = int((time.monotonic() - start_time) * 1000)

            if result.passed:
                self._log.info(
                    "policy_compliance_gate_passed",
                    duration_ms=duration_ms,
                    violation_count=len(result.violations),
                )
                return GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=duration_ms,
                    details={
                        "enforcement_level": result.enforcement_level,
                        "warning_count": result.warning_count,
                    },
                )
            else:
                # Enforcement failed - extract violation summary
                violation_summary = (
                    f"{result.error_count} error(s), {result.warning_count} warning(s)"
                )
                error_msg = f"Policy compliance failed: {violation_summary}"

                self._log.warning(
                    "policy_compliance_gate_failed",
                    duration_ms=duration_ms,
                    error_count=result.error_count,
                    warning_count=result.warning_count,
                )
                return GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.FAILED,
                    duration_ms=duration_ms,
                    error=error_msg,
                    details={
                        "enforcement_level": result.enforcement_level,
                        "error_count": result.error_count,
                        "warning_count": result.warning_count,
                        "violations": [
                            {
                                "error_code": v.error_code,
                                "model_name": v.model_name,
                                "message": v.message,
                            }
                            for v in result.violations[:5]  # Limit to first 5
                        ],
                    },
                )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            error_msg = f"Policy compliance gate error: {e}"

            self._log.error(
                "policy_compliance_gate_error",
                duration_ms=duration_ms,
                error=str(e),
            )
            return GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.FAILED,
                duration_ms=duration_ms,
                error=error_msg,
            )

    def _run_all_gates(
        self,
        to_env: str,
        manifest: dict,
        artifact_ref: str,
        *,
        dry_run: bool = False,
    ) -> list[GateResult]:
        """Run all enabled gates for an environment.

        Orchestrates execution of all gates configured for the target environment.
        Policy compliance gate always runs first. If a gate fails and dry_run is False,
        execution stops immediately (fail-fast).

        Args:
            to_env: Target environment name.
            manifest: The dbt manifest for policy compliance gate.
            artifact_ref: Full artifact reference for security scan.
            dry_run: If True, continue all gates even if one fails.

        Returns:
            List of GateResult for all executed gates.

        Raises:
            ValueError: If target environment is not found.
        """
        # Get environment configuration
        env_config = self._get_environment(to_env)
        if env_config is None:
            raise ValueError(f"Environment '{to_env}' not found in promotion path")

        self._log.info(
            "run_all_gates_started",
            environment=to_env,
            gates=[g.value for g in env_config.gates.keys()],
            dry_run=dry_run,
        )

        results: list[GateResult] = []
        timeout_seconds = env_config.gate_timeout_seconds

        # Always run policy_compliance gate first (mandatory)
        policy_result = self._run_policy_compliance_gate(
            manifest=manifest,
            dry_run=dry_run,
        )
        results.append(policy_result)

        # Check for failure (stop unless dry_run)
        if policy_result.status == GateStatus.FAILED and not dry_run:
            self._log.warning(
                "run_all_gates_stopped",
                reason="policy_compliance_failed",
                results_count=len(results),
            )
            return results

        # Run other enabled gates
        for gate, gate_config in env_config.gates.items():
            # Skip policy_compliance (already run)
            if gate == PromotionGate.POLICY_COMPLIANCE:
                continue

            # Skip disabled gates
            if gate_config is False:
                continue

            # Get command for the gate
            command = self._get_gate_command(gate, artifact_ref)
            if command is None:
                # No command configured, skip
                self._log.debug(
                    "gate_skipped",
                    gate=gate.value,
                    reason="no_command_configured",
                )
                results.append(
                    GateResult(
                        gate=gate,
                        status=GateStatus.SKIPPED,
                        duration_ms=0,
                    )
                )
                continue

            # Run the gate
            gate_result = self._run_gate(
                gate=gate,
                command=command,
                timeout_seconds=timeout_seconds,
            )
            results.append(gate_result)

            # Check for failure (stop unless dry_run)
            if gate_result.status == GateStatus.FAILED and not dry_run:
                self._log.warning(
                    "run_all_gates_stopped",
                    reason=f"{gate.value}_failed",
                    results_count=len(results),
                )
                return results

        self._log.info(
            "run_all_gates_completed",
            environment=to_env,
            results_count=len(results),
            all_passed=all(r.status in (GateStatus.PASSED, GateStatus.SKIPPED) for r in results),
        )

        return results

    def _get_gate_command(self, gate: PromotionGate, artifact_ref: str) -> str | None:
        """Get the command to execute for a gate.

        Looks up the command in promotion.gate_commands configuration.
        Substitutes ${ARTIFACT_REF} placeholder with actual reference.

        Args:
            gate: The gate type.
            artifact_ref: Full artifact reference for substitution.

        Returns:
            Command string or None if not configured.
        """
        if self.promotion.gate_commands is None:
            return None

        gate_key = gate.value  # e.g., "tests", "security_scan"
        command_config = self.promotion.gate_commands.get(gate_key)

        if command_config is None:
            return None

        # Handle string command or SecurityGateConfig
        if isinstance(command_config, str):
            command = command_config
        else:
            # SecurityGateConfig has .command attribute
            command = command_config.command

        # Substitute artifact reference
        return command.replace("${ARTIFACT_REF}", artifact_ref)

    def _verify_signature(
        self,
        artifact_ref: str,
        artifact_digest: str,
        content: bytes,
        enforcement: str,
    ) -> "VerificationResult":
        """Verify artifact signature using existing verification infrastructure.

        Integrates with Epic 8B's VerificationClient for signature verification
        during promotion. Supports enforce/warn/off enforcement modes.

        Args:
            artifact_ref: Full OCI artifact reference.
            artifact_digest: SHA256 digest of the artifact.
            content: Raw artifact bytes to verify.
            enforcement: Enforcement mode ("enforce", "warn", "off").

        Returns:
            VerificationResult with verification status and signer info.

        Note:
            When enforcement="off", returns a skipped result without verification.
            When enforcement="warn", verification errors return invalid but don't raise.
            When enforcement="enforce", verification errors propagate as exceptions.
        """
        from datetime import datetime, timezone

        from floe_core.oci.verification import VerificationClient
        from floe_core.schemas.signing import VerificationPolicy, VerificationResult

        self._log.info(
            "verify_signature_started",
            artifact_ref=artifact_ref,
            enforcement=enforcement,
        )

        # If enforcement is off, skip verification
        if enforcement == "off":
            self._log.info(
                "verify_signature_skipped",
                reason="enforcement=off",
            )
            return VerificationResult(
                status="unsigned",
                verified_at=datetime.now(timezone.utc),
                failure_reason="Verification skipped (enforcement=off)",
            )

        # Create verification policy with the specified enforcement
        policy = VerificationPolicy(
            enabled=True,
            enforcement=enforcement,
        )

        try:
            # Create client and verify
            client = VerificationClient(policy)

            # Get signature metadata from annotations if available
            # For now, pass None and let client handle unsigned artifacts
            result = client.verify(
                content=content,
                metadata=None,  # TODO: T020+ - Extract metadata from OCI annotations
                artifact_ref=artifact_ref,
                artifact_digest=artifact_digest,
            )

            self._log.info(
                "verify_signature_completed",
                artifact_ref=artifact_ref,
                status=result.status,
                is_valid=result.is_valid,
            )

            return result

        except Exception as e:
            self._log.error(
                "verify_signature_error",
                artifact_ref=artifact_ref,
                error=str(e),
            )

            # In warn mode, return invalid result instead of raising
            if enforcement == "warn":
                return VerificationResult(
                    status="invalid",
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=f"Verification error: {e}",
                )

            # Re-raise in enforce mode
            raise

    def _create_env_tag(
        self,
        source_tag: str,
        target_env: str,
        *,
        force: bool = False,
    ) -> str:
        """Create an immutable environment-specific tag.

        Creates a new tag in the format `{source_tag}-{target_env}` by copying
        the manifest from the source tag. This implements FR-002 for immutable
        environment-specific tags.

        Args:
            source_tag: Source artifact tag (e.g., "v1.2.3").
            target_env: Target environment name (e.g., "staging").
            force: If True, allow idempotent re-creation when digests match.

        Returns:
            The created environment tag (e.g., "v1.2.3-staging").

        Raises:
            ImmutabilityViolationError: If tag already exists with different digest.
            ArtifactNotFoundError: If source tag doesn't exist.

        Example:
            >>> tag = controller._create_env_tag("v1.2.3", "staging")
            >>> assert tag == "v1.2.3-staging"
        """
        from floe_core.oci.errors import ImmutabilityViolationError

        # Build the new environment tag
        env_tag = f"{source_tag}-{target_env}"

        self._log.info(
            "create_env_tag_started",
            source_tag=source_tag,
            target_env=target_env,
            env_tag=env_tag,
        )

        # Get source manifest and digest
        source_manifest = self.client.inspect(source_tag)
        source_digest = source_manifest.digest

        # Check if tag already exists
        if self.client.tag_exists(env_tag):
            existing_manifest = self.client.inspect(env_tag)
            existing_digest = existing_manifest.digest

            # If digests match and force=True, this is idempotent - no action needed
            if existing_digest == source_digest and force:
                self._log.info(
                    "create_env_tag_idempotent",
                    env_tag=env_tag,
                    digest=source_digest,
                )
                return env_tag

            # Tag exists with different digest or force=False
            raise ImmutabilityViolationError(
                tag=env_tag,
                registry=self.client._config.uri,
                digest=existing_digest,
            )

        # Create the new tag by copying the manifest
        oras_client = self.client._create_oras_client()
        source_ref = self.client._build_target_ref(source_tag)
        target_ref = self.client._build_target_ref(env_tag)

        # Fetch the source manifest
        manifest_data = oras_client.get_manifest(container=source_ref)

        # Upload manifest with new tag
        oras_client.upload_manifest(
            manifest=manifest_data,
            container=target_ref,
        )

        self._log.info(
            "create_env_tag_completed",
            env_tag=env_tag,
            digest=source_digest,
        )

        return env_tag

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
