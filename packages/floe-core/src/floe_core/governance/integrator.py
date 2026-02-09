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
from typing import Any

from opentelemetry import trace

from floe_core.enforcement.policy_enforcer import PolicyEnforcer
from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)
from floe_core.governance.rbac_checker import RBACChecker
from floe_core.governance.secrets import BuiltinSecretScanner as SecretScanner
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
        identity_plugin: Any,
    ) -> None:
        """Initialize integrator with governance configuration.

        Args:
            governance_config: Governance configuration with RBAC, secret scanning, policy settings
            identity_plugin: Identity plugin for RBAC checks (typed loosely for test mocking)
        """
        self.governance_config = governance_config
        self.identity_plugin = identity_plugin

    def run_checks(
        self,
        project_dir: Path,
        token: str | None,
        principal: str | None,
        dry_run: bool,
        enforcement_level: str,
    ) -> EnforcementResult:
        """Run all governance checks and return unified result.

        Args:
            project_dir: Project directory to scan
            token: Authentication token for RBAC
            principal: Principal identifier for RBAC
            dry_run: If True, return passed=True regardless of violations
            enforcement_level: "off" (skip all), "warn" (downgrade errors),
                "strict" (fail on errors)

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
        if (
            self.governance_config.rbac is not None
            and self.governance_config.rbac.enabled
        ):
            rbac_violations = self._run_rbac_check(token, principal)
            all_violations.extend(rbac_violations)

        # 2. Run secret scanning
        if (
            self.governance_config.secret_scanning is not None
            and self.governance_config.secret_scanning.enabled
        ):
            secret_violations = self._run_secret_scan()
            all_violations.extend(secret_violations)

        # 3. Run policy enforcement
        policy_result = self._run_policy_enforcement()
        all_violations.extend(policy_result.violations)

        # Apply enforcement level transformations
        if enforcement_level == "warn":
            # Downgrade all errors to warnings
            all_violations = [
                (
                    v.model_copy(update={"severity": "warning"})
                    if v.severity == "error"
                    else v
                )
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

    def _run_rbac_check(
        self, token: str | None, principal: str | None
    ) -> list[Violation]:
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

            checker = RBACChecker(
                rbac_config=self.governance_config.rbac,  # type: ignore[arg-type]
                identity_plugin=self.identity_plugin,
            )
            violations = checker.check(token=token, principal=principal)

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("governance.check_type", "rbac")
            span.set_attribute("governance.violations_count", len(violations))
            span.set_attribute("governance.duration_ms", duration_ms)

            if violations:
                span.set_status(
                    trace.Status(
                        trace.StatusCode.ERROR, f"{len(violations)} violations found"
                    )
                )

            return violations

    def _run_secret_scan(self) -> list[Violation]:
        """Run secret scanning with OpenTelemetry tracing.

        Returns:
            List of secret scanning violations
        """
        tracer = trace.get_tracer("floe.governance")
        with tracer.start_as_current_span("governance.secrets") as span:
            start = time.monotonic()

            scanner = SecretScanner()
            violations = scanner.scan()

            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("governance.check_type", "secrets")
            span.set_attribute("governance.violations_count", len(violations))
            span.set_attribute("governance.duration_ms", duration_ms)

            if violations:
                span.set_status(
                    trace.Status(
                        trace.StatusCode.ERROR, f"{len(violations)} violations found"
                    )
                )

            return violations

    def _run_policy_enforcement(self) -> EnforcementResult:
        """Run policy enforcement with OpenTelemetry tracing.

        Returns:
            EnforcementResult from policy enforcer
        """
        tracer = trace.get_tracer("floe.governance")
        with tracer.start_as_current_span("governance.policies") as span:
            start = time.monotonic()

            enforcer = PolicyEnforcer()
            result = enforcer.enforce()

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

    def _empty_summary(self) -> EnforcementSummary:
        """Create empty enforcement summary for enforcement_level=off.

        Returns:
            EnforcementSummary with zero counts
        """
        return EnforcementSummary(
            total_models=0,
            models_validated=0,
        )
