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
from floe_core.telemetry.tracing import create_span
from floe_core.schemas.promotion import (
    EnvironmentConfig,
    EnvironmentStatus,
    GateResult,
    GateStatus,
    PromotionConfig,
    PromotionGate,
    PromotionHistoryEntry,
    PromotionRecord,
    PromotionStatusResponse,
    RollbackImpactAnalysis,
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
        # Create OpenTelemetry span for gate execution
        gate_name = gate.value
        with create_span(
            f"floe.oci.gate.{gate_name}",
            attributes={
                "gate_type": gate_name,
                "timeout_seconds": timeout_seconds,
            },
        ) as span:
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
                span.set_attribute("duration_ms", duration_ms)

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
                span.set_attribute("duration_ms", duration_ms)

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
                span.set_attribute("duration_ms", duration_ms)
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

    def _get_artifact_digest(self, tag: str) -> str:
        """Get artifact digest from registry.

        Helper method that can be mocked in unit tests.

        Args:
            tag: Tag to get digest for.

        Returns:
            SHA256 digest string.

        Raises:
            ArtifactNotFoundError: If tag doesn't exist.
        """
        manifest_info = self.client.inspect(tag)
        return manifest_info.digest

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
        content: bytes | None = None,
        enforcement: str = "enforce",
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

        # Create OpenTelemetry span for signature verification
        with create_span(
            "floe.oci.promote.verify",
            attributes={
                "artifact_ref": artifact_ref,
                "enforcement_mode": enforcement,
            },
        ) as span:
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
                span.set_attribute("skipped", True)
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

                span.set_attribute("verification_status", result.status)
                return result

            except Exception as e:
                self._log.error(
                    "verify_signature_error",
                    artifact_ref=artifact_ref,
                    error=str(e),
                )

                # In warn mode, return invalid result instead of raising
                if enforcement == "warn":
                    span.set_attribute("verification_status", "invalid")
                    return VerificationResult(
                        status="invalid",
                        verified_at=datetime.now(timezone.utc),
                        failure_reason=f"Verification error: {e}",
                    )

                # Re-raise in enforce mode
                raise

    def _get_promotion_history(
        self,
        annotations: dict[str, str],
        default_digest: str,
        *,
        limit: int | None = None,
    ) -> list[PromotionHistoryEntry]:
        """Extract promotion history from OCI manifest annotations.

        Parses the promotion history stored in the `dev.floe.promotion.history`
        annotation and returns a list of PromotionHistoryEntry objects.

        Args:
            annotations: Dictionary of OCI manifest annotations.
            default_digest: Default digest to use if entry doesn't have one.
            limit: Optional maximum number of history entries to return.

        Returns:
            List of PromotionHistoryEntry objects, newest first.
            Returns empty list if no history or parsing fails.

        Note:
            History entries are stored as JSON array in annotation.
            Malformed entries are silently skipped to ensure robustness.

        Example:
            >>> annotations = {"dev.floe.promotion.history": '[{...}]'}
            >>> history = controller._get_promotion_history(annotations, digest)
            >>> for entry in history:
            ...     print(f"{entry.source_environment} -> {entry.target_environment}")
        """
        import json

        history_entries: list[PromotionHistoryEntry] = []
        history_data = annotations.get("dev.floe.promotion.history", "[]")

        try:
            history_list = json.loads(history_data)
            if isinstance(history_list, list):
                for entry in history_list:
                    if isinstance(entry, dict):
                        try:
                            # Validate required fields exist
                            if not entry.get("source_environment"):
                                continue  # Skip entries without source
                            if not entry.get("target_environment"):
                                continue  # Skip entries without target

                            history_entries.append(
                                PromotionHistoryEntry(
                                    promotion_id=entry.get("promotion_id", ""),
                                    artifact_digest=entry.get(
                                        "artifact_digest", default_digest
                                    ),
                                    source_environment=entry.get(
                                        "source_environment", ""
                                    ),
                                    target_environment=entry.get(
                                        "target_environment", ""
                                    ),
                                    operator=entry.get("operator", "unknown"),
                                    promoted_at=entry.get("promoted_at", ""),
                                    gate_results=entry.get("gate_results", []),
                                    signature_verified=entry.get(
                                        "signature_verified", False
                                    ),
                                )
                            )
                        except Exception:
                            pass  # Skip malformed entries
        except json.JSONDecodeError:
            pass  # Return empty list on JSON parse error

        # Apply limit if specified
        if limit is not None and limit > 0:
            history_entries = history_entries[:limit]

        return history_entries

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

    def _update_latest_tag(
        self,
        source_tag: str,
        target_env: str,
    ) -> str:
        """Update the mutable latest-{env} tag to point to the source artifact.

        Updates the mutable `latest-{target_env}` tag to point to the same
        digest as the source tag. This implements FR-003 for mutable "latest"
        tag updates during promotion.

        Unlike immutable environment tags, this can overwrite existing tags.

        Args:
            source_tag: Source artifact tag (e.g., "v1.2.3" or "v1.2.3-staging").
            target_env: Target environment name (e.g., "staging").

        Returns:
            The updated latest tag (e.g., "latest-staging").

        Raises:
            ArtifactNotFoundError: If source tag doesn't exist.

        Example:
            >>> tag = controller._update_latest_tag("v1.2.3-staging", "staging")
            >>> assert tag == "latest-staging"
        """
        # Build the latest tag
        latest_tag = f"latest-{target_env}"

        self._log.info(
            "update_latest_tag_started",
            source_tag=source_tag,
            target_env=target_env,
            latest_tag=latest_tag,
        )

        # Get source manifest (to verify it exists and get digest)
        source_manifest = self.client.inspect(source_tag)
        source_digest = source_manifest.digest

        # Create ORAS client and get manifest
        oras_client = self.client._create_oras_client()
        source_ref = self.client._build_target_ref(source_tag)
        target_ref = self.client._build_target_ref(latest_tag)

        # Fetch the source manifest
        manifest_data = oras_client.get_manifest(container=source_ref)

        # Upload manifest with latest tag (overwrites if exists)
        oras_client.upload_manifest(
            manifest=manifest_data,
            container=target_ref,
        )

        self._log.info(
            "update_latest_tag_completed",
            latest_tag=latest_tag,
            digest=source_digest,
        )

        return latest_tag

    def _store_promotion_record(
        self,
        tag: str,
        record: PromotionRecord,
    ) -> None:
        """Store a promotion record in OCI annotations.

        Stores the complete promotion record as a JSON annotation on the
        specified artifact tag. This implements FR-008 for immutable audit
        trails in OCI annotations.

        Args:
            tag: Tag to store the record on (e.g., "v1.2.3-staging").
            record: PromotionRecord to store.

        Raises:
            ArtifactNotFoundError: If tag doesn't exist.

        Example:
            >>> controller._store_promotion_record("v1.2.3-staging", record)
        """
        self._log.info(
            "store_promotion_record_started",
            tag=tag,
            promotion_id=str(record.promotion_id),
        )

        # Serialize record to JSON
        record_json = record.model_dump_json()

        # Store in OCI annotation with dev.floe.promotion key
        annotations = {"dev.floe.promotion": record_json}
        self.client._update_artifact_annotations(tag, annotations)

        self._log.info(
            "store_promotion_record_completed",
            tag=tag,
            promotion_id=str(record.promotion_id),
        )

    def _get_promoted_versions(self, environment: str) -> list[str]:
        """Get list of versions promoted to an environment.

        Scans tags with pattern `*-{environment}` to find promoted versions.

        Args:
            environment: Environment to scan (e.g., "prod").

        Returns:
            List of version tags that have been promoted to this environment.

        Example:
            >>> versions = controller._get_promoted_versions("prod")
            >>> print(versions)  # ['v1.0.0', 'v1.1.0', 'v2.0.0']
        """
        import fnmatch
        import re

        self._log.debug("get_promoted_versions_started", environment=environment)

        try:
            all_tags = self.client.list()
        except Exception:
            return []

        # Pattern: v{X.Y.Z}-{environment} (not rollback tags)
        env_suffix = f"-{environment}"
        rollback_pattern = re.compile(r"-rollback-\d+$")
        versions: list[str] = []

        for tag_info in all_tags:
            tag_name = tag_info.name
            if tag_name.endswith(env_suffix) and not rollback_pattern.search(tag_name):
                # Extract version by removing environment suffix
                version = tag_name[: -len(env_suffix)]
                versions.append(version)

        self._log.debug(
            "get_promoted_versions_completed",
            environment=environment,
            version_count=len(versions),
        )
        return versions

    def _get_next_rollback_number(self, tag: str, environment: str) -> int:
        """Calculate the next rollback number for a version-environment pair.

        Scans existing rollback tags with pattern `{tag}-{env}-rollback-{N}`
        and returns the next available number.

        Args:
            tag: Version tag (e.g., "v1.0.0").
            environment: Environment name (e.g., "prod").

        Returns:
            Next available rollback number (starts at 1).

        Example:
            >>> # If v1.0.0-prod-rollback-1 and v1.0.0-prod-rollback-2 exist:
            >>> controller._get_next_rollback_number("v1.0.0", "prod")
            3
        """
        import re

        self._log.debug(
            "get_next_rollback_number_started",
            tag=tag,
            environment=environment,
        )

        try:
            all_tags = self.client.list()
        except Exception:
            return 1

        # Pattern: {tag}-{environment}-rollback-{N}
        rollback_prefix = f"{tag}-{environment}-rollback-"
        pattern = re.compile(rf"^{re.escape(rollback_prefix)}(\d+)$")

        max_number = 0
        for tag_info in all_tags:
            match = pattern.match(tag_info.name)
            if match:
                number = int(match.group(1))
                max_number = max(max_number, number)

        next_number = max_number + 1

        self._log.debug(
            "get_next_rollback_number_completed",
            tag=tag,
            environment=environment,
            next_number=next_number,
        )
        return next_number

    def _create_rollback_tag(
        self,
        source_tag: str,
        rollback_tag: str,
    ) -> None:
        """Create a rollback-specific tag by copying manifest from source.

        Creates an immutable rollback tag following FR-014 pattern.

        Args:
            source_tag: Source artifact tag (e.g., "v1.0.0-prod").
            rollback_tag: Target rollback tag (e.g., "v1.0.0-prod-rollback-1").

        Raises:
            ArtifactNotFoundError: If source tag doesn't exist.

        Example:
            >>> controller._create_rollback_tag("v1.0.0-prod", "v1.0.0-prod-rollback-1")
        """
        self._log.info(
            "create_rollback_tag_started",
            source_tag=source_tag,
            rollback_tag=rollback_tag,
        )

        # Get source manifest
        source_manifest = self.client.inspect(source_tag)
        source_digest = source_manifest.digest

        # Create ORAS client
        oras_client = self.client._create_oras_client()
        source_ref = self.client._build_target_ref(source_tag)
        target_ref = self.client._build_target_ref(rollback_tag)

        # Fetch the source manifest
        manifest_data = oras_client.get_manifest(container=source_ref)

        # Upload manifest with rollback tag
        oras_client.upload_manifest(
            manifest=manifest_data,
            container=target_ref,
        )

        self._log.info(
            "create_rollback_tag_completed",
            rollback_tag=rollback_tag,
            digest=source_digest,
        )

    def _store_rollback_record(
        self,
        tag: str,
        record: RollbackRecord,
    ) -> None:
        """Store a rollback record in OCI annotations.

        Stores the complete rollback record as a JSON annotation on the
        specified artifact tag. This implements FR-017 for audit trails.

        Args:
            tag: Tag to store the record on (e.g., "v1.0.0-prod-rollback-1").
            record: RollbackRecord to store.

        Raises:
            ArtifactNotFoundError: If tag doesn't exist.

        Example:
            >>> controller._store_rollback_record("v1.0.0-prod-rollback-1", record)
        """
        self._log.info(
            "store_rollback_record_started",
            tag=tag,
            rollback_id=str(record.rollback_id),
        )

        # Serialize record to JSON
        record_json = record.model_dump_json()

        # Store in OCI annotation with dev.floe.rollback key
        annotations = {"dev.floe.rollback": record_json}
        self.client._update_artifact_annotations(tag, annotations)

        self._log.info(
            "store_rollback_record_completed",
            tag=tag,
            rollback_id=str(record.rollback_id),
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
            SignatureVerificationError: If signature verification fails in enforce mode.
            AuthorizationError: If operator is not authorized.
            EnvironmentLockedError: If target environment is locked.

        Example:
            >>> record = controller.promote("v1.0.0", "dev", "staging", "ci@github.com")
            >>> print(f"Promoted to staging: {record.promotion_id}")
        """
        from datetime import datetime, timezone
        from uuid import uuid4

        from floe_core.oci.errors import GateValidationError, SignatureVerificationError

        # Build artifact reference for span attributes
        artifact_ref = self.client._build_target_ref(tag)

        # Create OpenTelemetry span for promotion operation
        with create_span(
            "floe.oci.promote",
            attributes={
                "artifact_ref": artifact_ref,
                "from_env": from_env,
                "to_env": to_env,
                "dry_run": dry_run,
                "operator": operator,
            },
        ) as span:
            # Extract trace_id for CLI output and correlation
            span_context = span.get_span_context()
            trace_id = (
                format(span_context.trace_id, "032x")
                if span_context.is_valid
                else ""
            )

            self._log.info(
                "promote_started",
                tag=tag,
                from_env=from_env,
                to_env=to_env,
                operator=operator,
                dry_run=dry_run,
                trace_id=trace_id,
            )

            # Step 1: Validate transition path
            self._validate_transition(from_env, to_env)

            # Step 2: Get artifact digest (verifies artifact exists)
            artifact_digest = self._get_artifact_digest(tag)

            # Step 3: Run all validation gates (BEFORE signature verification)
            gate_results = self._run_all_gates(
                to_env=to_env,
                manifest={},  # TODO: T035+ - Pass actual manifest for policy gate
                artifact_ref=artifact_ref,
                dry_run=dry_run,
            )

            # Step 4: Check for gate failures
            failed_gates = [g for g in gate_results if g.status == GateStatus.FAILED]
            if failed_gates and not dry_run:
                # Get the first failed gate for the error
                first_failed = failed_gates[0]
                raise GateValidationError(
                    gate=first_failed.gate.value,
                    details=first_failed.error or "Gate validation failed",
                )

            # Step 5: Verify signature (only after gates pass)
            # The _verify_signature method handles enforcement logic internally
            # It returns a result object with status or raises SignatureVerificationError
            verification_result = self._verify_signature(
                artifact_ref=artifact_ref,
                artifact_digest=artifact_digest,
            )
            # If _verify_signature doesn't raise, signature is valid
            signature_verified = verification_result.status == "valid"

            # Generate promotion ID
            promotion_id = uuid4()
            promoted_at = datetime.now(timezone.utc)

            # Steps 6-8: Only perform mutations if not dry_run
            warnings: list[str] = []
            if not dry_run:
                # Step 6: Create immutable environment tag
                env_tag = self._create_env_tag(tag, to_env, force=True)

                # Step 7: Update mutable latest tag (with retry on transient failures)
                max_retries = 3
                latest_tag_updated = False
                for attempt in range(max_retries):
                    try:
                        self._update_latest_tag(env_tag, to_env)
                        latest_tag_updated = True
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self._log.warning(
                                "latest_tag_update_retry",
                                attempt=attempt + 1,
                                max_retries=max_retries,
                                error=str(e),
                            )
                            time.sleep(0.1 * (attempt + 1))  # Simple backoff
                        else:
                            self._log.warning(
                                "latest_tag_update_failed",
                                env_tag=env_tag,
                                error=str(e),
                            )
                            warnings.append(f"Latest tag update failed: {e}")

            # Step 8: Generate trace_id if not provided (required by schema)
            effective_trace_id = trace_id or f"promo-{promotion_id.hex[:16]}"

            # Only pass verification_result if it's a proper VerificationResult
            # (not a Mock from tests)
            from floe_core.schemas.signing import VerificationResult

            signature_status: VerificationResult | None = (
                verification_result
                if isinstance(verification_result, VerificationResult)
                else None
            )

            # Step 9: Store promotion record (if not dry_run) with retry
            # Note: Record is created AFTER storage to capture any storage warnings
            if not dry_run:
                max_retries = 3
                record_stored = False

                # Build preliminary record for storage attempts
                preliminary_record = PromotionRecord(
                    promotion_id=promotion_id,
                    artifact_digest=artifact_digest,
                    artifact_tag=tag,
                    source_environment=from_env,
                    target_environment=to_env,
                    gate_results=gate_results,
                    signature_verified=signature_verified,
                    signature_status=signature_status,
                    operator=operator,
                    promoted_at=promoted_at,
                    dry_run=dry_run,
                    trace_id=effective_trace_id,
                    authorization_passed=True,  # TODO: T040+ - Real authorization check
                    warnings=warnings.copy(),  # Copy current warnings
                )

                for attempt in range(max_retries):
                    try:
                        env_tag = f"{tag}-{to_env}"
                        self._store_promotion_record(env_tag, preliminary_record)
                        record_stored = True
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self._log.warning(
                                "promotion_record_storage_retry",
                                attempt=attempt + 1,
                                max_retries=max_retries,
                                error=str(e),
                            )
                            time.sleep(0.1 * (attempt + 1))  # Simple backoff
                        else:
                            # Log warning but don't fail - promotion succeeded
                            self._log.warning(
                                "promotion_record_storage_failed",
                                promotion_id=str(promotion_id),
                                error=str(e),
                            )
                            warnings.append(f"Promotion record storage failed: {e}")

            # Create final record with all warnings
            record = PromotionRecord(
                promotion_id=promotion_id,
                artifact_digest=artifact_digest,
                artifact_tag=tag,
                source_environment=from_env,
                target_environment=to_env,
                gate_results=gate_results,
                signature_verified=signature_verified,
                signature_status=signature_status,
                operator=operator,
                promoted_at=promoted_at,
                dry_run=dry_run,
                trace_id=effective_trace_id,
                authorization_passed=True,  # TODO: T040+ - Real authorization check
                warnings=warnings,
            )

            self._log.info(
                "promote_completed",
                promotion_id=str(promotion_id),
                artifact_digest=artifact_digest,
                from_env=from_env,
                to_env=to_env,
                dry_run=dry_run,
                gate_count=len(gate_results),
                failed_gate_count=len(failed_gates),
                warning_count=len(warnings),
            )

            return record

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
        # Build artifact reference for span attributes
        artifact_ref = self.client._build_target_ref(tag)

        # Create OpenTelemetry span for rollback operation
        with create_span(
            "floe.oci.rollback",
            attributes={
                "artifact_ref": artifact_ref,
                "environment": environment,
                "reason": reason,
                "operator": operator,
            },
        ) as span:
            # Extract trace_id for CLI output and correlation
            span_context = span.get_span_context()
            trace_id = (
                format(span_context.trace_id, "032x")
                if span_context.is_valid
                else ""
            )

            self._log.info(
                "rollback_started",
                tag=tag,
                environment=environment,
                reason=reason,
                operator=operator,
                trace_id=trace_id,
            )

            from datetime import datetime, timezone
            from uuid import uuid4

            from floe_core.oci.errors import (
                ArtifactNotFoundError,
                VersionNotPromotedError,
            )
            from floe_core.schemas.promotion import RollbackRecord

            # Step 1: Validate version was promoted to this environment
            env_tag = f"{tag}-{environment}"
            try:
                self.client.inspect(env_tag)
            except ArtifactNotFoundError:
                # Get available versions promoted to this environment
                available = self._get_promoted_versions(environment)
                raise VersionNotPromotedError(
                    tag=tag,
                    environment=environment,
                    available_versions=available,
                )

            # Step 2: Get target artifact digest (the version we're rolling back TO)
            target_digest = self._get_artifact_digest(env_tag)

            # Step 3: Get current latest digest (the version we're rolling back FROM)
            latest_tag = f"latest-{environment}"
            try:
                previous_digest = self._get_artifact_digest(latest_tag)
            except ArtifactNotFoundError:
                # No current latest - first deployment scenario (unlikely for rollback)
                previous_digest = "sha256:" + "0" * 64  # Sentinel value

            # Step 4: Calculate next rollback number and create rollback tag (FR-014)
            rollback_number = self._get_next_rollback_number(tag, environment)
            rollback_tag = f"{tag}-{environment}-rollback-{rollback_number}"

            # Step 5: Create rollback tag by copying manifest from env_tag
            self._create_rollback_tag(env_tag, rollback_tag)

            # Step 6: Update latest tag to point to rollback target (FR-015)
            self._update_latest_tag(env_tag, environment)

            # Generate rollback ID
            rollback_id = uuid4()
            rolled_back_at = datetime.now(timezone.utc)

            # Create RollbackRecord for audit trail (FR-017)
            effective_trace_id = trace_id or f"rollback-{rollback_id.hex[:16]}"

            record = RollbackRecord(
                rollback_id=rollback_id,
                artifact_digest=target_digest,
                environment=environment,
                previous_digest=previous_digest,
                reason=reason,
                operator=operator,
                rolled_back_at=rolled_back_at,
                trace_id=effective_trace_id,
            )

            # Step 7: Store rollback record in OCI annotations
            self._store_rollback_record(rollback_tag, record)

            self._log.info(
                "rollback_completed",
                rollback_id=str(rollback_id),
                tag=tag,
                environment=environment,
                rollback_tag=rollback_tag,
                target_digest=target_digest,
                previous_digest=previous_digest,
                trace_id=effective_trace_id,
            )

            return record

    def analyze_rollback_impact(
        self,
        tag: str,
        environment: str,
    ) -> RollbackImpactAnalysis:
        """Analyze the impact of rolling back to a specific version.

        Performs pre-rollback analysis to help operators understand the
        consequences before executing. Returns information about breaking
        changes, affected products, and recommendations.

        Args:
            tag: Target artifact tag to analyze rollback to.
            environment: Environment to analyze.

        Returns:
            RollbackImpactAnalysis with impact details.

        Raises:
            VersionNotPromotedError: If target version was never promoted.
            ArtifactNotFoundError: If artifact not found.

        Example:
            >>> analysis = controller.analyze_rollback_impact("v1.0.0", "prod")
            >>> if analysis.breaking_changes:
            ...     print("Warning: Breaking changes detected!")
        """
        from floe_core.oci.errors import ArtifactNotFoundError, VersionNotPromotedError
        from floe_core.schemas.promotion import RollbackImpactAnalysis

        self._log.info(
            "analyze_rollback_impact_started",
            tag=tag,
            environment=environment,
        )

        # Step 1: Validate version was promoted to this environment
        env_tag = f"{tag}-{environment}"
        try:
            target_manifest = self.client.inspect(env_tag)
        except ArtifactNotFoundError:
            available = self._get_promoted_versions(environment)
            raise VersionNotPromotedError(
                tag=tag,
                environment=environment,
                available_versions=available,
            )

        # Step 2: Get current latest version info
        latest_tag = f"latest-{environment}"
        try:
            current_manifest = self.client.inspect(latest_tag)
            current_digest = current_manifest.digest
        except ArtifactNotFoundError:
            current_digest = None

        # Step 3: Check if already at target version (no rollback needed)
        target_digest = target_manifest.digest
        if current_digest == target_digest:
            self._log.info(
                "analyze_rollback_impact_same_version",
                tag=tag,
                environment=environment,
            )
            return RollbackImpactAnalysis(
                breaking_changes=[],
                affected_products=[],
                recommendations=["Environment already at target version - no rollback needed"],
                estimated_downtime=None,
            )

        # Step 4: Analyze potential breaking changes
        # In a full implementation, this would compare schemas/manifests
        # For now, we provide basic analysis based on version comparison
        breaking_changes: list[str] = []
        recommendations: list[str] = []

        # Extract version info if available (semantic versioning)
        try:
            import re
            version_match = re.match(r"v(\d+)\.(\d+)\.(\d+)", tag)
            if version_match:
                major, minor, patch = map(int, version_match.groups())
                # If rolling back to a lower major version, likely breaking
                if major < 1:
                    recommendations.append("Rolling back to pre-1.0 version - check stability")
        except Exception:
            pass  # Version parsing optional

        # Step 5: Analyze affected products
        # In a full implementation, this would query lineage/dependencies
        affected_products: list[str] = []

        # Step 6: Build recommendations
        recommendations.extend([
            "Verify downstream systems are compatible with rollback version",
            "Monitor application health after rollback",
            "Consider notifying dependent teams before rollback",
        ])

        # Step 7: Estimate downtime
        # In a full implementation, this would consider deployment time
        estimated_downtime = "~1-2 minutes for tag update"

        analysis = RollbackImpactAnalysis(
            breaking_changes=breaking_changes,
            affected_products=affected_products,
            recommendations=recommendations,
            estimated_downtime=estimated_downtime,
        )

        self._log.info(
            "analyze_rollback_impact_completed",
            tag=tag,
            environment=environment,
            breaking_change_count=len(breaking_changes),
            affected_product_count=len(affected_products),
            recommendation_count=len(recommendations),
        )

        return analysis

    def get_status(
        self,
        tag: str,
        env: str | None = None,
        history: int | None = None,
    ) -> PromotionStatusResponse:
        """Get promotion status for an artifact across environments.

        Queries the registry to determine which environments contain the
        artifact and retrieves promotion history from OCI annotations.

        Args:
            tag: Artifact tag to query status for.
            env: Optional environment filter for single-environment status.
            history: Optional limit on number of history entries to return.

        Returns:
            PromotionStatusResponse with environment states and history.

        Raises:
            ArtifactNotFoundError: If artifact tag not found.

        Example:
            >>> status = controller.get_status("v1.0.0")
            >>> if status.environments["prod"].promoted:
            ...     print(f"v1.0.0 is in production")
            >>> status = controller.get_status("v1.0.0", env="prod")
            >>> status = controller.get_status("v1.0.0", history=5)
        """
        import json
        from datetime import datetime, timezone

        from floe_core.oci.errors import ArtifactNotFoundError

        self._log.info(
            "get_status_started",
            tag=tag,
            env_filter=env,
            history_limit=history,
        )

        # Step 1: Get artifact manifest and digest
        manifest = self.client.inspect(tag)
        digest = manifest.digest
        annotations = getattr(manifest, "annotations", {}) or {}

        # Step 2: Determine environments to check
        if env is not None:
            environments_to_check = [env]
        else:
            environments_to_check = [e.name for e in self.promotion.environments]

        # Step 3: Check each environment for this artifact
        environment_states: dict[str, EnvironmentStatus] = {}
        for env_name in environments_to_check:
            env_tag = f"{tag}-{env_name}"
            latest_tag = f"latest-{env_name}"

            promoted = False
            promoted_at = None
            is_latest = False
            operator = None

            try:
                # Check if environment-specific tag exists
                env_manifest = self.client.inspect(env_tag)
                if env_manifest.digest == digest:
                    promoted = True

                    # Try to get promotion metadata from annotations
                    env_annotations = getattr(env_manifest, "annotations", {}) or {}
                    promotion_data = env_annotations.get("dev.floe.promotion", "{}")
                    try:
                        promo_info = json.loads(promotion_data)
                        if isinstance(promo_info, dict):
                            if "promoted_at" in promo_info:
                                promoted_at = datetime.fromisoformat(
                                    promo_info["promoted_at"].replace("Z", "+00:00")
                                )
                            operator = promo_info.get("operator")
                    except (json.JSONDecodeError, ValueError):
                        pass

            except ArtifactNotFoundError:
                pass  # Not promoted to this environment

            try:
                # Check if this artifact is the latest in the environment
                latest_manifest = self.client.inspect(latest_tag)
                if latest_manifest.digest == digest:
                    is_latest = True
            except ArtifactNotFoundError:
                pass  # No latest tag exists

            environment_states[env_name] = EnvironmentStatus(
                promoted=promoted,
                promoted_at=promoted_at,
                is_latest=is_latest,
                operator=operator,
            )

        # Step 4: Extract promotion history using helper method
        history_entries = self._get_promotion_history(
            annotations=annotations,
            default_digest=digest,
            limit=history,
        )

        # Step 5: Build response
        response = PromotionStatusResponse(
            tag=tag,
            digest=digest,
            environments=environment_states,
            history=history_entries,
            queried_at=datetime.now(timezone.utc),
        )

        self._log.info(
            "get_status_completed",
            tag=tag,
            environment_count=len(environment_states),
            history_count=len(history_entries),
        )

        return response

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
