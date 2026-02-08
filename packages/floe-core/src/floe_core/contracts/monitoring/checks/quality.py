"""Quality check implementation for contract monitoring.

Evaluates data quality against configurable expectations (completeness,
uniqueness, validity, etc.) via a pluggable quality plugin. Calculates
weighted score and compares against threshold.

Tasks: T047 (Epic 3D)
Requirements: FR-015, FR-016, FR-017, FR-018
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Protocol

import structlog

from floe_core.contracts.monitoring.checks.base import BaseCheck
from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.violations import (
    CheckResult,
    CheckStatus,
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)

logger = structlog.get_logger(__name__)


class QualityPlugin(Protocol):
    """Protocol for quality check plugins.

    Quality plugins analyze data against expectations and return scores.
    This is a duck-typed protocol — any object with run_checks() method works.
    """

    async def run_checks(self, expectations: list[dict[str, Any]]) -> dict[str, float]:
        """Run quality checks against expectations.

        Args:
            expectations: List of expectation dicts with keys:
                - name: Expectation identifier
                - type: Expectation type (completeness, uniqueness, etc.)
                - threshold: Minimum acceptable score (0.0-1.0)
                - weight: Relative importance (default 1.0)

        Returns:
            Map of expectation name to score (0.0-1.0).
        """
        ...


class QualityCheck(BaseCheck):
    """Check that data quality meets contract expectations.

    Reads ``contract_data.quality.expectations`` (list of quality expectations)
    and ``contract_data.quality.threshold`` (minimum overall score).

    Delegates expectation evaluation to an optional quality_plugin. If no
    plugin is provided, the check is SKIPPED (graceful degradation).

    Quality score calculation:
        weighted_score = sum(score_i * weight_i) / sum(weight_i)

    Severity assignment based on distance from threshold:
        - score >= threshold → PASS
        - score >= 0.9 * threshold → WARNING
        - score >= 0.5 * threshold → ERROR
        - score < 0.5 * threshold → CRITICAL

    Returns:
        CheckResult with status PASS if score meets threshold, FAIL with a
        ContractViolationEvent if below threshold, SKIPPED if no plugin,
        or ERROR if required contract fields are missing.
    """

    def __init__(self, quality_plugin: QualityPlugin | None = None) -> None:
        """Initialize quality check with optional quality plugin.

        Args:
            quality_plugin: Optional plugin implementing QualityPlugin protocol.
                If None, check will return SKIPPED status.
        """
        self._quality_plugin = quality_plugin

    @property
    def check_type(self) -> ViolationType:
        """The type of violation this check detects."""
        return ViolationType.QUALITY

    async def execute(
        self,
        contract: RegisteredContract,
        config: MonitoringConfig,
    ) -> CheckResult:
        """Execute quality check against a registered contract.

        Args:
            contract: The registered contract to check.
            config: Global monitoring configuration.

        Returns:
            CheckResult recording the check outcome.
        """
        now = datetime.now(tz=timezone.utc)
        start = time.monotonic()

        # --- Extract quality config ---
        quality_cfg = contract.contract_data.get("quality")
        if not quality_cfg:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.QUALITY,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": "No quality configuration in contract_data"},
            )

        threshold: float = quality_cfg.get("threshold", 0.8)
        expectations: list[dict[str, Any]] = quality_cfg.get("expectations", [])

        # --- Check if quality plugin is available ---
        if self._quality_plugin is None:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.QUALITY,
                status=CheckStatus.SKIPPED,
                duration_seconds=duration,
                timestamp=now,
                details={"message": "Quality plugin not available — check skipped"},
            )

        # --- Validate expectations present ---
        if not expectations:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.QUALITY,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": "No quality expectations defined in contract"},
            )

        # --- Run quality checks via plugin ---
        try:
            results = await self._quality_plugin.run_checks(expectations)
        except Exception as e:
            duration = time.monotonic() - start
            logger.exception(
                "quality_plugin_error",
                contract_name=contract.contract_name,
                error=str(e),
            )
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.QUALITY,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": f"Quality plugin execution failed: {e!s}"},
            )

        # --- Calculate weighted score ---
        total_weighted_score = 0.0
        total_weight = 0.0

        for exp in expectations:
            exp_name = exp.get("name", "")
            exp_weight = float(exp.get("weight", 1.0))
            exp_score = results.get(exp_name, 1.0)  # Default to 1.0 if missing

            total_weighted_score += exp_score * exp_weight
            total_weight += exp_weight

        # Avoid division by zero
        if total_weight == 0.0:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.QUALITY,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": "Total expectation weight is zero"},
            )

        overall_score = total_weighted_score / total_weight

        duration = time.monotonic() - start

        # --- Check if score meets threshold ---
        if overall_score >= threshold:
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.QUALITY,
                status=CheckStatus.PASS,
                duration_seconds=duration,
                timestamp=now,
                details={
                    "overall_score": round(overall_score, 3),
                    "threshold": threshold,
                    "expectations_evaluated": len(expectations),
                },
            )

        # --- Calculate severity based on distance from threshold ---
        if overall_score >= 0.9 * threshold:
            severity = ViolationSeverity.WARNING
        elif overall_score >= 0.5 * threshold:
            severity = ViolationSeverity.ERROR
        else:
            severity = ViolationSeverity.CRITICAL

        # --- Build violation event ---
        message = f"Quality score {overall_score:.2f} is below threshold {threshold:.2f}"

        violation = ContractViolationEvent(
            contract_name=contract.contract_name,
            contract_version=contract.contract_version,
            violation_type=ViolationType.QUALITY,
            severity=severity,
            message=message,
            expected_value=f">= {threshold:.2f}",
            actual_value=f"{overall_score:.2f}",
            timestamp=now,
            check_duration_seconds=duration,
            metadata={
                "overall_score": f"{overall_score:.3f}",
                "threshold": f"{threshold:.2f}",
                "expectations_evaluated": str(len(expectations)),
                "severity_reason": (
                    "critical"
                    if overall_score < 0.5 * threshold
                    else "error"
                    if overall_score < 0.9 * threshold
                    else "warning"
                ),
            },
        )

        return CheckResult(
            contract_name=contract.contract_name,
            check_type=ViolationType.QUALITY,
            status=CheckStatus.FAIL,
            duration_seconds=duration,
            timestamp=now,
            details={
                "overall_score": round(overall_score, 3),
                "threshold": threshold,
                "expectations_evaluated": len(expectations),
                "individual_results": {
                    exp["name"]: results.get(exp["name"], 1.0) for exp in expectations
                },
            },
            violation=violation,
        )
