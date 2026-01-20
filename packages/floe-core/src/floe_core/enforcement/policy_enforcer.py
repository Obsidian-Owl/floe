"""PolicyEnforcer core class for compile-time governance validation.

PolicyEnforcer is the main orchestrator that coordinates all policy validators
(naming, coverage, documentation) and aggregates their results into a single
EnforcementResult.

Task: T029, T030, T031, T032, T033
Requirements: FR-001 (PolicyEnforcer core module), FR-002 (Pipeline integration)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

import structlog

from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)
from floe_core.enforcement.validators.coverage import CoverageValidator
from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
from floe_core.enforcement.validators.documentation import DocumentationValidator
from floe_core.enforcement.validators.naming import NamingValidator
from floe_core.enforcement.validators.semantic import SemanticValidator

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
    ) -> EnforcementResult:
        """Run all policy validators against the dbt manifest.

        This is the main entry point for policy enforcement. It coordinates
        all validators (naming, coverage, documentation) and aggregates
        their results into a single EnforcementResult.

        Args:
            manifest: The compiled dbt manifest.json as a dictionary.
            dry_run: If True, violations are reported as warnings and
                the result always passes. Useful for previewing impact.

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

        # Collect violations from all validators
        violations: list[Violation] = []

        # Run naming validation if configured
        if self.governance_config.naming is not None:
            naming_violations = self._validate_naming(models)
            violations.extend(naming_violations)

        # Run coverage validation if configured
        if self.governance_config.quality_gates is not None:
            tests = self._extract_tests(manifest)
            coverage_violations = self._validate_coverage(models, tests)
            violations.extend(coverage_violations)

            # Run documentation validation if configured
            if self.governance_config.quality_gates.require_descriptions:
                doc_violations = self._validate_documentation(models)
                violations.extend(doc_violations)

        # Run semantic validation (always enabled - validates model relationships)
        semantic_violations = self._validate_semantic(manifest)
        violations.extend(semantic_violations)

        # Run custom rule validation if configured (T032)
        if self.governance_config.custom_rules:
            custom_violations = self._validate_custom_rules(manifest)
            violations.extend(custom_violations)

        # Adjust severity for dry-run mode
        if dry_run:
            violations = self._downgrade_to_warnings(violations)

        # Determine pass/fail based on enforcement level and violations
        passed = self._determine_passed(violations, dry_run)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Build summary
        summary = self._build_summary(models, violations, duration_ms)

        # Determine effective enforcement level
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
