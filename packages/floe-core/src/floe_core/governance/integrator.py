"""Governance integrator coordinating RBAC, secret scanning, and policy enforcement.

Task: T026
Requirements: FR-001, FR-004, FR-005, FR-006, FR-007, FR-031

The GovernanceIntegrator orchestrates all governance checks (RBAC, secret scanning,
policy enforcement) and returns a unified EnforcementResult.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from opentelemetry import trace

if TYPE_CHECKING:
    from floe_core.plugins.identity import IdentityPlugin

from floe_core.enforcement.policy_enforcer import PolicyEnforcer
from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)
from floe_core.governance.policy_evaluator import PolicyDefinition, PolicyEvaluator
from floe_core.governance.rbac_checker import RBACChecker
from floe_core.governance.secrets import BuiltinSecretScanner as SecretScanner
from floe_core.governance.types import SecretFinding, SecretPattern
from floe_core.network.generator import get_network_security_plugin
from floe_core.schemas.manifest import GovernanceConfig


class GovernanceIntegrator:
    """Orchestrate RBAC, secret scanning, and policy enforcement.

    Coordinates all governance checks and returns a unified result with
    violations from all sources. Supports enforcement levels (off/warn/strict)
    and dry-run mode.
    """

    def __init__(
        self,
        governance_config: GovernanceConfig,
        identity_plugin: IdentityPlugin | None,
    ) -> None:
        """Initialize integrator with governance configuration.

        Args:
            governance_config: Governance configuration with RBAC, secret scanning, policy settings
            identity_plugin: Identity plugin for RBAC token validation, or None
                when OIDC is unavailable (principal fallback only).
        """
        self.governance_config = governance_config
        self.identity_plugin = identity_plugin

    def run_checks(
        self,
        project_dir: Path,
        token: str | None,
        principal: str | None,
        dry_run: bool,
        enforcement_level: Literal["off", "warn", "strict"],
        dbt_manifest: dict[str, Any] | None = None,
    ) -> EnforcementResult:
        """Run all governance checks and return unified result.

        Args:
            project_dir: Project directory to scan
            token: Authentication token for RBAC
            principal: Principal identifier for RBAC
            dry_run: If True, return passed=True regardless of violations
            enforcement_level: "off" (skip all), "warn" (downgrade errors),
                "strict" (fail on errors)
            dbt_manifest: dbt manifest.json for policy enforcement (optional)

        Returns:
            EnforcementResult with merged violations from all checks
        """
        # Short-circuit if enforcement is off
        if enforcement_level == "off":
            return EnforcementResult(
                passed=True,
                violations=[],
                summary=self._empty_summary(),
                enforcement_level="off",
                manifest_version="",
                timestamp=datetime.now(timezone.utc),
            )

        all_violations: list[Violation] = []

        # 1. Run RBAC checks
        if self.governance_config.rbac is not None and self.governance_config.rbac.enabled:
            rbac_violations = self._run_rbac_check(token, principal)
            all_violations.extend(rbac_violations)

        # 2. Run secret scanning
        if (
            self.governance_config.secret_scanning is not None
            and self.governance_config.secret_scanning.enabled
        ):
            secret_violations = self._run_secret_scan(project_dir)
            all_violations.extend(secret_violations)

        # 3. Run policy enforcement
        policy_result = self._run_policy_enforcement(dbt_manifest)
        all_violations.extend(policy_result.violations)

        # 3.5. Run policy-as-code evaluation (FR-015)
        if self.governance_config.policies:
            policy_eval_violations = self._run_policy_evaluation(dbt_manifest)
            all_violations.extend(policy_eval_violations)

        # 4. Run network policy check
        if (
            self.governance_config.network_policies is not None
            and self.governance_config.network_policies.enabled
        ):
            network_violations = self._run_network_policy_check()
            all_violations.extend(network_violations)

        # Apply enforcement level transformations
        if enforcement_level == "warn":
            # Downgrade all errors to warnings
            all_violations = [
                (v.model_copy(update={"severity": "warning"}) if v.severity == "error" else v)
                for v in all_violations
            ]

        # Determine if checks passed
        has_errors = any(v.severity == "error" for v in all_violations)
        passed = (
            dry_run  # Dry run always passes
            or not has_errors  # No errors means pass
            or enforcement_level == "warn"  # Warn mode always passes
        )

        # Build final result using policy enforcer's summary
        return EnforcementResult(
            passed=passed,
            violations=all_violations,
            summary=policy_result.summary,
            enforcement_level=enforcement_level,
            manifest_version=policy_result.manifest_version,
            timestamp=datetime.now(timezone.utc),
        )

    def _run_rbac_check(self, token: str | None, principal: str | None) -> list[Violation]:
        """Run RBAC checks with OpenTelemetry tracing.

        Args:
            token: Authentication token
            principal: Principal identifier

        Returns:
            List of RBAC violations
        """
        tracer = trace.get_tracer("floe.governance")
        with tracer.start_as_current_span("governance.rbac") as span:
            start = time.monotonic()

            # Narrowing: guarded by `rbac is not None and rbac.enabled` above
            rbac_config = self.governance_config.rbac
            assert rbac_config is not None

            try:
                assert (
                    self.identity_plugin is not None
                ), "identity_plugin must not be None when RBAC is enabled"
                checker = RBACChecker(
                    rbac_config=rbac_config,
                    identity_plugin=self.identity_plugin,
                )
                violations = checker.check(token=token, principal=principal)
            except Exception as e:
                violations = [
                    Violation(
                        error_code="FLOE-E500",
                        severity="error",
                        policy_type="rbac",
                        model_name="__rbac__",
                        message=f"RBAC check failed: {e}",
                        expected="RBAC check to succeed",
                        actual=str(e),
                        suggestion="Verify identity plugin configuration and availability",
                        documentation_url="https://floe.dev/docs/governance/rbac",
                    )
                ]

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("governance.check_type", "rbac")
            span.set_attribute("governance.violations_count", len(violations))
            span.set_attribute("governance.duration_ms", duration_ms)

            if violations:
                span.set_status(
                    trace.Status(trace.StatusCode.ERROR, f"{len(violations)} violations found")
                )

            return violations

    def _run_secret_scan(self, project_dir: Path) -> list[Violation]:
        """Run secret scanning with OpenTelemetry tracing.

        Args:
            project_dir: Project directory to scan for secrets.

        Returns:
            List of secret scanning violations
        """
        tracer = trace.get_tracer("floe.governance")
        with tracer.start_as_current_span("governance.secrets") as span:
            start = time.monotonic()

            try:
                # Convert config SecretPatternConfig → internal SecretPattern (C-02 fix)
                config = self.governance_config.secret_scanning
                custom_patterns: list[SecretPattern] | None = None
                if config is not None and config.custom_patterns:
                    custom_patterns = [
                        SecretPattern(
                            name=p.name,
                            regex=p.pattern,
                            description=p.name,
                            error_code="E699",
                        )
                        for p in config.custom_patterns
                    ]

                # Determine allow_secrets from severity config
                allow_secrets = config is not None and config.severity == "warning"

                scanner = SecretScanner(
                    custom_patterns=custom_patterns,
                    allow_secrets=allow_secrets,
                )

                # Get exclude patterns from config
                exclude_patterns: list[str] | None = None
                if config is not None and config.exclude_patterns:
                    exclude_patterns = config.exclude_patterns

                # Call scan_directory (C-01 fix: was calling non-existent scan())
                findings: list[SecretFinding] = scanner.scan_directory(
                    project_dir, exclude_patterns=exclude_patterns
                )

                # Convert SecretFinding → Violation
                violations = [self._finding_to_violation(f) for f in findings]
            except Exception as e:
                violations = [
                    Violation(
                        error_code="FLOE-E600",
                        severity="error",
                        policy_type="secret_scanning",
                        model_name="secret_scanning",
                        message=f"Secret scan failed: {e}",
                        expected="Secret scan to succeed",
                        actual=str(e),
                        suggestion="Verify secret scanner configuration",
                        documentation_url="https://floe.dev/docs/governance/secret-scanning",
                    )
                ]

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("governance.check_type", "secrets")
            span.set_attribute("governance.violations_count", len(violations))
            span.set_attribute("governance.duration_ms", duration_ms)

            if violations:
                span.set_status(
                    trace.Status(trace.StatusCode.ERROR, f"{len(violations)} violations found")
                )

            return violations

    @staticmethod
    def _finding_to_violation(finding: SecretFinding) -> Violation:
        """Convert a SecretFinding to a Violation.

        Args:
            finding: Secret detection finding from the scanner.

        Returns:
            Violation instance for the enforcement result.
        """
        return Violation(
            error_code=f"FLOE-{finding.error_code}",
            severity=finding.severity,
            policy_type="secret_scanning",
            model_name=finding.file_path,
            message=(
                f"Secret detected: {finding.pattern_name} "
                f"at {finding.file_path}:{finding.line_number}"
            ),
            expected="No hardcoded secrets in source files",
            actual=f"Pattern '{finding.pattern_name}' matched",
            suggestion="Remove the secret and use environment variables or a secrets manager",
            documentation_url="https://floe.dev/docs/governance/secret-scanning",
            column_name=None,
        )

    def _run_policy_enforcement(
        self, dbt_manifest: dict[str, Any] | None = None
    ) -> EnforcementResult:
        """Run policy enforcement with OpenTelemetry tracing.

        Args:
            dbt_manifest: dbt manifest.json for policy enforcement

        Returns:
            EnforcementResult from policy enforcer
        """
        tracer = trace.get_tracer("floe.governance")
        with tracer.start_as_current_span("governance.policies") as span:
            start = time.monotonic()

            try:
                enforcer = PolicyEnforcer(governance_config=self.governance_config)
                result = enforcer.enforce(dbt_manifest or {})
            except Exception as e:
                result = EnforcementResult(
                    passed=False,
                    violations=[
                        Violation(
                            error_code="FLOE-E400",
                            severity="error",
                            policy_type="custom",
                            model_name="policy_enforcement",
                            message=f"Policy enforcement failed: {e}",
                            expected="Policy enforcement to succeed",
                            actual=str(e),
                            suggestion="Verify policy configuration and manifest format",
                            documentation_url="https://floe.dev/docs/governance/policies",
                        )
                    ],
                    summary=self._empty_summary(),
                    enforcement_level="strict",
                    manifest_version="",
                    timestamp=datetime.now(timezone.utc),
                )

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("governance.check_type", "policies")
            span.set_attribute("governance.violations_count", len(result.violations))
            span.set_attribute("governance.duration_ms", duration_ms)

            if result.violations:
                span.set_status(
                    trace.Status(
                        trace.StatusCode.ERROR,
                        f"{len(result.violations)} violations found",
                    )
                )

            return result

    def _run_network_policy_check(self) -> list[Violation]:
        """Run network policy checks with OpenTelemetry tracing.

        Returns:
            List of network policy violations
        """
        tracer = trace.get_tracer("floe.governance")
        with tracer.start_as_current_span("governance.network_policies") as span:
            start = time.monotonic()

            try:
                plugin = get_network_security_plugin()

                # Generate default deny policies if configured
                if (
                    self.governance_config.network_policies is not None
                    and self.governance_config.network_policies.default_deny
                ):
                    plugin.generate_default_deny_policies("floe")

                # Generate custom policies if egress rules are present
                if (
                    self.governance_config.network_policies is not None
                    and self.governance_config.network_policies.custom_egress_rules
                ):
                    # TODO: Convert NetworkPoliciesConfig → NetworkPolicyConfig
                    # The plugin expects NetworkPolicyConfig (detailed K8s policy),
                    # but we have NetworkPoliciesConfig (high-level governance config).
                    # Currently works because tests mock the plugin. Needs proper
                    # conversion when network policy generation is wired end-to-end.
                    plugin.generate_network_policy(
                        self.governance_config.network_policies  # type: ignore[arg-type]
                    )

                violations: list[Violation] = []

            except Exception as e:
                violations = [
                    Violation(
                        error_code="FLOE-E700",
                        severity="error",
                        policy_type="network_policy",
                        model_name="network_policy",
                        message=f"network policy check failed: {e}",
                        expected="network policy check to succeed",
                        actual=str(e),
                        suggestion="Verify network security plugin configuration and availability",
                        documentation_url="https://floe.dev/docs/governance/network-policies",
                    )
                ]

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("governance.check_type", "network_policies")
            span.set_attribute("governance.violations_count", len(violations))
            span.set_attribute("governance.duration_ms", duration_ms)

            if violations:
                span.set_status(
                    trace.Status(trace.StatusCode.ERROR, f"{len(violations)} violations found")
                )

            return violations

    def _run_policy_evaluation(self, dbt_manifest: dict[str, Any] | None) -> list[Violation]:
        """Run policy-as-code evaluation with OpenTelemetry tracing (FR-015).

        Converts PolicyDefinitionConfig from governance config into PolicyDefinition
        domain objects and evaluates them against the dbt manifest.

        Args:
            dbt_manifest: dbt manifest.json for policy evaluation.

        Returns:
            List of policy evaluation violations.
        """
        tracer = trace.get_tracer("floe.governance")
        with tracer.start_as_current_span("governance.policy_evaluation") as span:
            start = time.monotonic()

            try:
                # Convert config models → domain models
                policy_configs = self.governance_config.policies or []
                policies = [
                    PolicyDefinition(
                        name=p.name,
                        type=p.type,
                        action=p.action,
                        message=p.message,
                        config=p.config,
                    )
                    for p in policy_configs
                ]

                evaluator = PolicyEvaluator(policies=policies)
                violations = evaluator.evaluate(manifest=dbt_manifest or {})

            except Exception as e:
                violations = [
                    Violation(
                        error_code="FLOE-E450",
                        severity="error",
                        policy_type="custom",
                        model_name="policy_evaluation",
                        message=f"Policy evaluation failed: {e}",
                        expected="Policy evaluation to succeed",
                        actual=str(e),
                        suggestion="Verify policy definitions in manifest.yaml",
                        documentation_url="https://floe.dev/docs/governance/policies",
                    )
                ]

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("governance.check_type", "policy_evaluation")
            span.set_attribute("governance.violations_count", len(violations))
            span.set_attribute("governance.duration_ms", duration_ms)
            span.set_attribute("governance.policies_evaluated", len(policy_configs))

            if violations:
                span.set_status(
                    trace.Status(
                        trace.StatusCode.ERROR,
                        f"{len(violations)} violations found",
                    )
                )

            return violations

    def _empty_summary(self) -> EnforcementSummary:
        """Create empty enforcement summary for enforcement_level=off.

        Returns:
            EnforcementSummary with zero counts
        """
        return EnforcementSummary(
            total_models=0,
            models_validated=0,
        )
