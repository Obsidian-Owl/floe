"""PolicyEnforcer core class for compile-time governance validation.

PolicyEnforcer is the main orchestrator that coordinates all policy validators
(naming, coverage, documentation) and aggregates their results into a single
EnforcementResult.

Task: T029, T030, T031, T032, T033, T038-T044
Requirements: FR-001 (PolicyEnforcer core module), FR-002 (Pipeline integration)
             FR-011 through FR-015 (US3 - Severity Overrides)
"""

from __future__ import annotations

import fnmatch
import time
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

import structlog

from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
    compute_downstream_impact,
)
from floe_core.enforcement.validators.coverage import CoverageValidator
from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
from floe_core.enforcement.validators.documentation import DocumentationValidator
from floe_core.enforcement.validators.naming import NamingValidator
from floe_core.enforcement.validators.semantic import SemanticValidator
from floe_core.schemas.governance import PolicyOverride

if TYPE_CHECKING:
    from floe_core.schemas.manifest import GovernanceConfig

logger = structlog.get_logger(__name__)


class PolicyEnforcer:
    """Orchestrates policy enforcement for dbt manifests.

    PolicyEnforcer coordinates all policy validators (naming, coverage,
    documentation) and aggregates their results. It is stateless - each
    invocation processes input and returns a result.

    Attributes:
        governance_config: The governance configuration to enforce.

    Example:
        >>> from floe_core.enforcement import PolicyEnforcer
        >>> from floe_core.schemas.manifest import GovernanceConfig
        >>>
        >>> config = GovernanceConfig(policy_enforcement_level="strict")
        >>> enforcer = PolicyEnforcer(governance_config=config)
        >>> result = enforcer.enforce(dbt_manifest)
        >>> if not result.passed:
        ...     for v in result.violations:
        ...         print(f"{v.error_code}: {v.message}")
    """

    def __init__(self, governance_config: GovernanceConfig) -> None:
        """Initialize PolicyEnforcer with governance configuration.

        Args:
            governance_config: The governance configuration containing
                naming conventions, quality gates, and enforcement level.
        """
        self.governance_config = governance_config
        self._log = logger.bind(
            component="PolicyEnforcer",
            enforcement_level=governance_config.policy_enforcement_level,
        )

    def enforce(
        self,
        manifest: dict[str, Any],
        *,
        dry_run: bool = False,
        include_context: bool = False,
        max_violations: int | None = None,
    ) -> EnforcementResult:
        """Run all policy validators against the dbt manifest.

        This is the main entry point for policy enforcement. It coordinates
        all validators (naming, coverage, documentation) and aggregates
        their results into a single EnforcementResult.

        Args:
            manifest: The compiled dbt manifest.json as a dictionary.
            dry_run: If True, violations are reported as warnings and
                the result always passes. Useful for previewing impact.
            include_context: If True, populates downstream_impact field on
                violations using manifest child_map. Default: False (lazy).
            max_violations: Optional maximum violations to collect before
                early exit. Useful for fail-fast scenarios where only the
                first few violations are needed. If None, collects all.

        Returns:
            EnforcementResult containing pass/fail status, all violations,
            and summary statistics.
        """
        start_time = time.perf_counter()

        # Extract manifest metadata
        manifest_version = self._get_manifest_version(manifest)
        models = self._extract_models(manifest)

        self._log.info(
            "enforcement_started",
            manifest_version=manifest_version,
            model_count=len(models),
            dry_run=dry_run,
        )

        # Run all validators and collect violations
        violations = self._run_all_validators(manifest, models, max_violations)

        # Post-process violations
        violations = self._post_process_violations(violations, manifest, dry_run, include_context)

        # Build result
        return self._build_enforcement_result(
            violations, models, manifest_version, dry_run, start_time
        )

    def _run_all_validators(
        self,
        manifest: dict[str, Any],
        models: list[dict[str, Any]],
        max_violations: int | None,
    ) -> list[Violation]:
        """Run all configured validators and collect violations.

        Args:
            manifest: The dbt manifest dictionary.
            models: Extracted model nodes.
            max_violations: Optional limit for early exit.

        Returns:
            List of violations from all validators.
        """
        violations: list[Violation] = []

        # Run naming validation if configured
        if self.governance_config.naming is not None:
            violations.extend(self._validate_naming(models))
            if self._limit_reached(violations, max_violations):
                return violations[:max_violations]

        # Run quality gate validators
        violations = self._run_quality_gate_validators(manifest, models, violations, max_violations)
        if self._limit_reached(violations, max_violations):
            return violations[:max_violations]

        # Run semantic validation (always enabled)
        violations.extend(self._validate_semantic(manifest))
        if self._limit_reached(violations, max_violations):
            return violations[:max_violations]

        # Run custom rule validation if configured
        if self.governance_config.custom_rules:
            violations.extend(self._validate_custom_rules(manifest))
            if self._limit_reached(violations, max_violations):
                return violations[:max_violations]

        return violations

    def _run_quality_gate_validators(
        self,
        manifest: dict[str, Any],
        models: list[dict[str, Any]],
        violations: list[Violation],
        max_violations: int | None,
    ) -> list[Violation]:
        """Run quality gate validators (coverage, documentation).

        Args:
            manifest: The dbt manifest dictionary.
            models: Extracted model nodes.
            violations: Current list of violations.
            max_violations: Optional limit for early exit.

        Returns:
            Updated list of violations.
        """
        quality_gates = self.governance_config.quality_gates
        if quality_gates is None:
            return violations

        # Run coverage validation
        tests = self._extract_tests(manifest)
        violations.extend(self._validate_coverage(models, tests))
        if self._limit_reached(violations, max_violations):
            return violations

        # Run documentation validation if configured
        if quality_gates.require_descriptions:
            violations.extend(self._validate_documentation(models))

        return violations

    def _limit_reached(
        self,
        violations: list[Violation],
        max_violations: int | None,
    ) -> bool:
        """Check if max_violations limit reached (early exit).

        Args:
            violations: Current violations list.
            max_violations: Optional limit.

        Returns:
            True if limit reached, False otherwise.
        """
        return max_violations is not None and len(violations) >= max_violations

    def _post_process_violations(
        self,
        violations: list[Violation],
        manifest: dict[str, Any],
        dry_run: bool,
        include_context: bool,
    ) -> list[Violation]:
        """Post-process violations (downstream impact, dry-run downgrade).

        Args:
            violations: Raw violations from validators.
            manifest: The dbt manifest dictionary.
            dry_run: Whether this is a dry-run.
            include_context: Whether to include downstream impact.

        Returns:
            Post-processed violations.
        """
        # Populate downstream_impact if requested (T048-T049)
        if include_context:
            child_map = manifest.get("child_map", {})
            violations = self._populate_downstream_impact(violations, child_map)

        # Adjust severity for dry-run mode
        if dry_run:
            violations = self._downgrade_to_warnings(violations)

        return violations

    def _build_enforcement_result(
        self,
        violations: list[Violation],
        models: list[dict[str, Any]],
        manifest_version: str,
        dry_run: bool,
        start_time: float,
    ) -> EnforcementResult:
        """Build the final EnforcementResult.

        Args:
            violations: Processed violations.
            models: Model nodes from manifest.
            manifest_version: dbt version string.
            dry_run: Whether this is a dry-run.
            start_time: Start time from perf_counter().

        Returns:
            Complete EnforcementResult.
        """
        passed = self._determine_passed(violations, dry_run)
        duration_ms = (time.perf_counter() - start_time) * 1000
        summary = self._build_summary(models, violations, duration_ms)
        enforcement_level = self._get_effective_enforcement_level()

        result = EnforcementResult(
            passed=passed,
            violations=violations,
            summary=summary,
            enforcement_level=enforcement_level,
            manifest_version=manifest_version,
            timestamp=datetime.now(timezone.utc),
        )

        self._log.info(
            "enforcement_completed",
            passed=passed,
            violation_count=len(violations),
            error_count=result.error_count,
            warning_count=result.warning_count,
            duration_ms=duration_ms,
        )

        return result

    def _get_manifest_version(self, manifest: dict[str, Any]) -> str:
        """Extract dbt version from manifest metadata.

        Args:
            manifest: The dbt manifest dictionary.

        Returns:
            The dbt version string (e.g., "1.8.0").
        """
        metadata = manifest.get("metadata", {})
        return str(metadata.get("dbt_version", "unknown"))

    def _extract_models(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract model nodes from the manifest.

        Args:
            manifest: The dbt manifest dictionary.

        Returns:
            List of model node dictionaries.
        """
        nodes = manifest.get("nodes", {})
        models = [node for node in nodes.values() if node.get("resource_type") == "model"]
        return models

    def _extract_tests(self, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract test nodes from the manifest.

        Args:
            manifest: The dbt manifest dictionary.

        Returns:
            List of test node dictionaries.
        """
        nodes = manifest.get("nodes", {})
        tests = [node for node in nodes.values() if node.get("resource_type") == "test"]
        return tests

    def _validate_naming(
        self,
        models: list[dict[str, Any]],
    ) -> list[Violation]:
        """Validate model names against naming conventions.

        Uses NamingValidator to check model names against configured patterns
        (medallion, kimball, or custom).

        Args:
            models: List of model nodes from the manifest.

        Returns:
            List of naming violations found.
        """
        naming_config = self.governance_config.naming
        if naming_config is None:
            return []

        # Delegate to NamingValidator (T046)
        validator = NamingValidator(naming_config)
        return validator.validate(models)

    def _validate_coverage(
        self,
        models: list[dict[str, Any]],
        tests: list[dict[str, Any]],
    ) -> list[Violation]:
        """Validate test coverage against quality gates.

        Args:
            models: List of model nodes from the manifest.
            tests: List of test nodes from the manifest.

        Returns:
            List of coverage violations found.
        """
        quality_gates = self.governance_config.quality_gates
        if quality_gates is None:
            return []

        # Delegate to CoverageValidator (T060)
        validator = CoverageValidator(quality_gates)
        return validator.validate(models, tests)

    def _validate_documentation(
        self,
        models: list[dict[str, Any]],
    ) -> list[Violation]:
        """Validate documentation requirements.

        Args:
            models: List of model nodes from the manifest.

        Returns:
            List of documentation violations found.
        """
        quality_gates = self.governance_config.quality_gates
        if quality_gates is None:
            return []

        # Delegate to DocumentationValidator (T070)
        validator = DocumentationValidator(quality_gates)
        return validator.validate(models)

    def _validate_semantic(
        self,
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Validate semantic relationships (refs, sources, dependencies).

        Validates model references, source references, and detects
        circular dependencies using the full manifest.

        Args:
            manifest: The full dbt manifest dictionary.

        Returns:
            List of semantic violations found (FLOE-E301, E302, E303).
        """
        # Delegate to SemanticValidator (T017-T020)
        validator = SemanticValidator()
        return validator.validate(manifest)

    def _validate_custom_rules(
        self,
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Validate models against user-defined custom rules.

        Applies custom rules from governance config:
        - require_tags_for_prefix (FLOE-E400)
        - require_meta_field (FLOE-E401)
        - require_tests_of_type (FLOE-E402)

        Args:
            manifest: The full dbt manifest dictionary.

        Returns:
            List of custom rule violations found (FLOE-E4xx).
        """
        custom_rules = self.governance_config.custom_rules
        if not custom_rules:
            return []

        # Delegate to CustomRuleValidator (T027-T033)
        validator = CustomRuleValidator(custom_rules)
        return validator.validate(manifest)

    def _populate_downstream_impact(
        self,
        violations: list[Violation],
        child_map: dict[str, list[str]],
    ) -> list[Violation]:
        """Populate downstream_impact field on violations.

        Uses compute_downstream_impact to find affected downstream models
        for each violation.

        Args:
            violations: List of violations to enrich.
            child_map: dbt manifest child_map for dependency lookup.

        Returns:
            New list of violations with downstream_impact populated.
        """
        if not child_map:
            return violations

        result: list[Violation] = []
        for violation in violations:
            impact = compute_downstream_impact(
                model_name=violation.model_name,
                child_map=child_map,
                recursive=True,  # Include transitive dependencies
            )
            # Create new Violation with downstream_impact populated
            enriched = Violation(
                error_code=violation.error_code,
                severity=violation.severity,
                policy_type=violation.policy_type,
                model_name=violation.model_name,
                column_name=violation.column_name,
                message=violation.message,
                expected=violation.expected,
                actual=violation.actual,
                suggestion=violation.suggestion,
                documentation_url=violation.documentation_url,
                downstream_impact=impact if impact else None,
                first_detected=violation.first_detected,
                occurrences=violation.occurrences,
                override_applied=violation.override_applied,
            )
            result.append(enriched)

        return result

    def _downgrade_to_warnings(
        self,
        violations: list[Violation],
    ) -> list[Violation]:
        """Downgrade all violations to warning severity for dry-run mode.

        Args:
            violations: List of violations to downgrade.

        Returns:
            New list with all violations as warnings.
        """
        return [
            Violation(
                error_code=v.error_code,
                severity="warning",
                policy_type=v.policy_type,
                model_name=v.model_name,
                column_name=v.column_name,
                message=v.message,
                expected=v.expected,
                actual=v.actual,
                suggestion=v.suggestion,
                documentation_url=v.documentation_url,
            )
            for v in violations
        ]

    def _determine_passed(
        self,
        violations: list[Violation],
        dry_run: bool,
    ) -> bool:
        """Determine if enforcement passed based on violations and mode.

        Args:
            violations: List of violations found.
            dry_run: Whether this is a dry-run.

        Returns:
            True if enforcement passed, False otherwise.
        """
        # Dry-run always passes
        if dry_run:
            return True

        # No violations = pass
        if not violations:
            return True

        # Check for error-severity violations
        has_errors = any(v.severity == "error" for v in violations)
        return not has_errors

    def _build_summary(
        self,
        models: list[dict[str, Any]],
        violations: list[Violation],
        duration_ms: float,
    ) -> EnforcementSummary:
        """Build enforcement summary statistics.

        Args:
            models: List of model nodes validated.
            violations: List of violations found.
            duration_ms: Enforcement duration in milliseconds.

        Returns:
            EnforcementSummary with statistics.
        """
        naming_count = sum(1 for v in violations if v.policy_type == "naming")
        coverage_count = sum(1 for v in violations if v.policy_type == "coverage")
        doc_count = sum(1 for v in violations if v.policy_type == "documentation")
        semantic_count = sum(1 for v in violations if v.policy_type == "semantic")
        custom_count = sum(1 for v in violations if v.policy_type == "custom")

        return EnforcementSummary(
            total_models=len(models),
            models_validated=len(models),
            naming_violations=naming_count,
            coverage_violations=coverage_count,
            documentation_violations=doc_count,
            semantic_violations=semantic_count,
            custom_rule_violations=custom_count,
            duration_ms=duration_ms,
        )

    def _get_effective_enforcement_level(self) -> Literal["off", "warn", "strict"]:
        """Get the effective enforcement level.

        Returns:
            The enforcement level ('off', 'warn', or 'strict').
        """
        level = self.governance_config.policy_enforcement_level
        if level is None:
            return "warn"  # Default to warn if not specified
        return level

    # ==========================================================================
    # US3: Policy Override Support (T038-T044)
    # ==========================================================================

    @staticmethod
    def apply_overrides(
        violations: list[Violation],
        overrides: list[PolicyOverride],
    ) -> list[Violation]:
        """Apply policy overrides to modify or exclude violations.

        Processes violations through the override rules, applying the first
        matching override for each violation. Supports:
        - downgrade: Convert error severity to warning (FR-012)
        - exclude: Remove violation entirely (FR-013)
        - expires: Ignore override after expiration date (FR-014)
        - policy_types: Limit override to specific policy types (FR-011)

        The first matching override wins (no stacking).

        Args:
            violations: List of violations to process.
            overrides: List of policy overrides to apply.

        Returns:
            List of violations after applying overrides. May be shorter
            than input if exclude actions removed violations.

        Example:
            >>> violations = [Violation(model_name="legacy_orders", ...)]
            >>> overrides = [PolicyOverride(pattern="legacy_*", action="downgrade", ...)]
            >>> result = PolicyEnforcer.apply_overrides(violations, overrides)
            >>> result[0].severity
            'warning'
        """
        if not overrides:
            return violations

        log = logger.bind(component="PolicyEnforcer.apply_overrides")

        # Filter out expired overrides and log warnings
        active_overrides = PolicyEnforcer._filter_expired_overrides(overrides, log)

        if not active_overrides:
            log.debug("all_overrides_expired", total_overrides=len(overrides))
            return violations

        result: list[Violation] = []
        overrides_applied_count = 0

        for violation in violations:
            # Find first matching override
            matched_override = PolicyEnforcer._find_matching_override(violation, active_overrides)

            if matched_override is None:
                # No match - keep violation unchanged
                result.append(violation)
            elif matched_override.action == "exclude":
                # Exclude action - skip this violation entirely (FR-013)
                log.warning(
                    "override_exclude_applied",
                    pattern=matched_override.pattern,
                    model_name=violation.model_name,
                    reason=matched_override.reason,
                )
                overrides_applied_count += 1
                # Don't add to result - violation is excluded
            else:
                # Downgrade action - convert error to warning (FR-012)
                downgraded = PolicyEnforcer._apply_downgrade(violation, matched_override.pattern)
                log.warning(
                    "override_downgrade_applied",
                    pattern=matched_override.pattern,
                    model_name=violation.model_name,
                    reason=matched_override.reason,
                    original_severity=violation.severity,
                    new_severity=downgraded.severity,
                )
                overrides_applied_count += 1
                result.append(downgraded)

        # Log warning if any override matched zero models (T044)
        PolicyEnforcer._log_unused_overrides(active_overrides, violations, log)

        if overrides_applied_count > 0:
            log.info(
                "overrides_summary",
                overrides_applied=overrides_applied_count,
                violations_before=len(violations),
                violations_after=len(result),
            )

        return result

    @staticmethod
    def _filter_expired_overrides(
        overrides: list[PolicyOverride],
        log: structlog.BoundLogger,
    ) -> list[PolicyOverride]:
        """Filter out expired overrides and log warnings.

        Args:
            overrides: List of overrides to filter.
            log: Bound logger for warnings.

        Returns:
            List of non-expired overrides.
        """
        today = date.today()
        active: list[PolicyOverride] = []

        for override in overrides:
            if override.expires is not None and override.expires < today:
                # Override has expired (FR-014)
                log.warning(
                    "override_expired",
                    pattern=override.pattern,
                    action=override.action,
                    expired_on=override.expires.isoformat(),
                    reason=override.reason,
                )
            else:
                active.append(override)

        return active

    @staticmethod
    def _find_matching_override(
        violation: Violation,
        overrides: list[PolicyOverride],
    ) -> PolicyOverride | None:
        """Find the first override matching a violation.

        Matching criteria:
        1. Pattern matches model_name using fnmatch (glob patterns) (T039)
        2. If policy_types specified, violation policy_type must be in list (T043)

        First match wins - no stacking of overrides.

        Args:
            violation: Violation to match against.
            overrides: List of active (non-expired) overrides.

        Returns:
            First matching override, or None if no match.
        """
        for override in overrides:
            # Check pattern match (T039)
            if not fnmatch.fnmatch(violation.model_name, override.pattern):
                continue

            # Check policy_types filter if specified (T043)
            if override.policy_types is not None:
                if violation.policy_type not in override.policy_types:
                    continue

            # Match found
            return override

        return None

    @staticmethod
    def _apply_downgrade(
        violation: Violation,
        pattern: str,
    ) -> Violation:
        """Apply downgrade action to a violation.

        Creates a new Violation with severity changed to "warning" and
        override_applied field set to the matching pattern.

        Args:
            violation: Original violation.
            pattern: The override pattern that matched.

        Returns:
            New Violation with downgraded severity.
        """
        return Violation(
            error_code=violation.error_code,
            severity="warning",
            policy_type=violation.policy_type,
            model_name=violation.model_name,
            column_name=violation.column_name,
            message=violation.message,
            expected=violation.expected,
            actual=violation.actual,
            suggestion=violation.suggestion,
            documentation_url=violation.documentation_url,
            downstream_impact=violation.downstream_impact,
            first_detected=violation.first_detected,
            occurrences=violation.occurrences,
            override_applied=pattern,
        )

    @staticmethod
    def _log_unused_overrides(
        overrides: list[PolicyOverride],
        violations: list[Violation],
        log: structlog.BoundLogger,
    ) -> None:
        """Log warning for overrides that matched zero violations.

        Helps identify stale overrides that may need cleanup.

        Args:
            overrides: List of active overrides.
            violations: Original violations list.
            log: Bound logger for warnings.
        """
        model_names = {v.model_name for v in violations}

        for override in overrides:
            # Check if pattern matches any model
            matched_any = any(fnmatch.fnmatch(name, override.pattern) for name in model_names)
            if not matched_any:
                log.warning(
                    "override_matched_zero_models",
                    pattern=override.pattern,
                    action=override.action,
                    reason=override.reason,
                )
