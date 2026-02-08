"""Freshness check implementation for contract monitoring.

Compares actual data age against the contract's freshness SLA threshold,
accounting for configurable clock skew tolerance.

Tasks: T025 (Epic 3D)
Requirements: FR-007, FR-008, FR-009, FR-010
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from floe_core.contracts.monitoring.checks.base import BaseCheck
from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.violations import (
    CheckResult,
    CheckStatus,
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)


class FreshnessCheck(BaseCheck):
    """Check that data freshness meets the contract SLA threshold.

    Reads ``contract_data.sla.freshness.threshold_minutes`` and compares
    against ``contract_data.dataset.last_updated``.  Clock skew tolerance
    from ``config.clock_skew_tolerance_seconds`` is subtracted from the
    effective data age before comparison.

    Returns:
        CheckResult with status PASS if data is fresh, FAIL with a
        ContractViolationEvent if stale, or ERROR if required contract
        fields are missing or malformed.
    """

    @property
    def check_type(self) -> ViolationType:
        """The type of violation this check detects."""
        return ViolationType.FRESHNESS

    async def execute(
        self,
        contract: RegisteredContract,
        config: MonitoringConfig,
    ) -> CheckResult:
        """Execute freshness check against a registered contract.

        Args:
            contract: The registered contract to check.
            config: Global monitoring configuration.

        Returns:
            CheckResult recording the check outcome.
        """
        now = datetime.now(tz=timezone.utc)
        start = time.monotonic()

        # --- Extract freshness SLA config ---
        sla = contract.contract_data.get("sla", {})
        freshness_cfg = sla.get("freshness")
        if not freshness_cfg:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.FRESHNESS,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": "No freshness SLA configuration in contract_data"},
            )

        threshold_minutes: int = freshness_cfg.get("threshold_minutes", 0)

        # --- Extract dataset timestamp ---
        dataset = contract.contract_data.get("dataset", {})
        last_updated_str = dataset.get("last_updated")
        if not last_updated_str:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.FRESHNESS,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": "No last_updated timestamp in contract_data.dataset"},
            )

        # --- Parse timestamp ---
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.FRESHNESS,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={
                    "error": f"Cannot parse timestamp: {last_updated_str!r}",
                },
            )

        # --- Calculate data age ---
        data_age_seconds = (now - last_updated).total_seconds()
        threshold_seconds = threshold_minutes * 60.0
        tolerance_seconds = float(config.clock_skew_tolerance_seconds)

        # Data is stale if age exceeds threshold + tolerance
        is_stale = data_age_seconds > (threshold_seconds + tolerance_seconds)

        duration = time.monotonic() - start

        if not is_stale:
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.FRESHNESS,
                status=CheckStatus.PASS,
                duration_seconds=duration,
                timestamp=now,
                details={
                    "data_age_minutes": round(data_age_seconds / 60.0, 2),
                    "threshold_minutes": threshold_minutes,
                },
            )

        # --- Build violation event ---
        data_age_minutes = round(data_age_seconds / 60.0, 1)
        violation = ContractViolationEvent(
            contract_name=contract.contract_name,
            contract_version=contract.contract_version,
            violation_type=ViolationType.FRESHNESS,
            severity=ViolationSeverity.ERROR,
            message=(
                f"Data is {data_age_minutes} minutes old, "
                f"SLA threshold is {threshold_minutes} minutes"
            ),
            expected_value=f"<= {threshold_minutes} minutes",
            actual_value=f"{data_age_minutes} minutes",
            timestamp=now,
            check_duration_seconds=duration,
            metadata={
                "data_age_minutes": str(data_age_minutes),
                "threshold_minutes": str(threshold_minutes),
                "tolerance_seconds": str(config.clock_skew_tolerance_seconds),
            },
        )

        return CheckResult(
            contract_name=contract.contract_name,
            check_type=ViolationType.FRESHNESS,
            status=CheckStatus.FAIL,
            duration_seconds=duration,
            timestamp=now,
            details={
                "data_age_minutes": round(data_age_seconds / 60.0, 2),
                "threshold_minutes": threshold_minutes,
            },
            violation=violation,
        )
