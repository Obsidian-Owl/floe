"""Availability check implementation for contract monitoring.

Validates data source availability by pinging the compute plugin and tracking
success/failure rates over a rolling time window. Escalates severity based on
consecutive failures.

Tasks: T050 (Epic 3D)
Requirements: FR-019, FR-020, FR-021, FR-022
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

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


class AvailabilityCheck(BaseCheck):
    """Check that data source availability meets the contract SLA threshold.

    Validates connection to the data source via compute plugin and tracks
    availability ratio over a rolling 24-hour window. Consecutive failures
    escalate severity:
    - 1-2 failures: WARNING
    - 3-4 failures: ERROR
    - 5+ failures: CRITICAL

    The check maintains state across executions to track:
    - Ping history: list of (timestamp, success) tuples per contract
    - Consecutive failure count per contract

    Attributes:
        check_type: Returns ViolationType.AVAILABILITY

    Args:
        compute_plugin: Optional compute plugin with validate_connection() method.
            If None, check returns SKIPPED status.
    """

    def __init__(self, compute_plugin: Any = None) -> None:
        """Initialize the availability check.

        Args:
            compute_plugin: Optional compute plugin with validate_connection() method.
                Must return dict with 'status' and 'latency_ms' keys.
        """
        self._compute_plugin = compute_plugin
        self._ping_history: dict[str, list[tuple[float, bool]]] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._log = logger.bind(check_type="availability")

    @property
    def check_type(self) -> ViolationType:
        """The type of violation this check detects."""
        return ViolationType.AVAILABILITY

    async def execute(
        self,
        contract: RegisteredContract,
        config: MonitoringConfig,
    ) -> CheckResult:
        """Execute availability check against a registered contract.

        Pings the data source via compute plugin, records result in rolling window,
        calculates availability ratio, and compares against threshold.

        Args:
            contract: The registered contract to check.
            config: Global monitoring configuration.

        Returns:
            CheckResult with status PASS if available, FAIL with violation if
            below threshold, SKIPPED if no compute plugin, or ERROR if config missing.
        """
        now = datetime.now(tz=timezone.utc)
        start = time.monotonic()

        # --- Extract availability SLA config ---
        sla = contract.contract_data.get("sla", {})
        availability_cfg = sla.get("availability")
        if not availability_cfg:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.AVAILABILITY,
                status=CheckStatus.ERROR,
                duration_seconds=duration,
                timestamp=now,
                details={"error": "No availability SLA configuration in contract_data"},
            )

        threshold_pct: float = availability_cfg.get("threshold_pct", 99.9)

        # --- Check for compute plugin ---
        if self._compute_plugin is None:
            duration = time.monotonic() - start
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.AVAILABILITY,
                status=CheckStatus.SKIPPED,
                duration_seconds=duration,
                timestamp=now,
                details={"reason": "No compute plugin available for availability check"},
            )

        # --- Ping the data source ---
        ping_success = False
        latency_ms = 0.0
        error_msg = ""

        try:
            result = await self._compute_plugin.validate_connection()
            ping_success = result.get("status") == "ok"
            latency_ms = result.get("latency_ms", 0.0)
        except Exception as e:
            ping_success = False
            error_msg = str(e)
            self._log.warning(
                "availability_ping_error",
                contract_name=contract.contract_name,
                error=error_msg,
            )

        # --- Record ping result in history ---
        if contract.contract_name not in self._ping_history:
            self._ping_history[contract.contract_name] = []

        current_time = time.monotonic()
        self._ping_history[contract.contract_name].append((current_time, ping_success))

        # --- Prune history older than 24 hours ---
        window_seconds = 24 * 60 * 60
        cutoff_time = current_time - window_seconds
        self._ping_history[contract.contract_name] = [
            (t, success)
            for t, success in self._ping_history[contract.contract_name]
            if t >= cutoff_time
        ]

        # --- Update consecutive failures counter ---
        if contract.contract_name not in self._consecutive_failures:
            self._consecutive_failures[contract.contract_name] = 0

        if ping_success:
            self._consecutive_failures[contract.contract_name] = 0
        else:
            self._consecutive_failures[contract.contract_name] += 1

        # --- Calculate availability ratio ---
        history = self._ping_history[contract.contract_name]
        total_pings = len(history)
        successful_pings = sum(1 for _, success in history if success)
        availability_ratio = successful_pings / total_pings if total_pings > 0 else 0.0

        duration = time.monotonic() - start
        threshold_ratio = threshold_pct / 100.0
        availability_pct = availability_ratio * 100.0

        # --- Determine severity based on consecutive failures ---
        consecutive = self._consecutive_failures[contract.contract_name]
        if consecutive >= 5:
            severity = ViolationSeverity.CRITICAL
        elif consecutive >= 3:
            severity = ViolationSeverity.ERROR
        elif consecutive >= 1:
            severity = ViolationSeverity.WARNING
        else:
            severity = ViolationSeverity.INFO

        # --- PASS conditions ---
        # PASS if current ping succeeded AND ratio meets threshold
        if ping_success and availability_ratio >= threshold_ratio:
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.AVAILABILITY,
                status=CheckStatus.PASS,
                duration_seconds=duration,
                timestamp=now,
                details={
                    "latency_ms": latency_ms,
                    "availability_ratio": availability_ratio,
                    "threshold_pct": threshold_pct,
                },
            )

        # PASS if current ping succeeded and consecutive failures reset
        # (recovery from transient failures, ratio will recover over time)
        if ping_success and consecutive == 0:
            return CheckResult(
                contract_name=contract.contract_name,
                check_type=ViolationType.AVAILABILITY,
                status=CheckStatus.PASS,
                duration_seconds=duration,
                timestamp=now,
                details={
                    "latency_ms": latency_ms,
                    "availability_ratio": availability_ratio,
                    "threshold_pct": threshold_pct,
                },
            )

        # --- Build violation event ---
        # If ratio below threshold AND we have substantial history AND
        # we're in a sustained failure state (not just recovered), escalate to CRITICAL
        # This overrides consecutive-based severity when SLA is breached
        #
        # Check if we've had recent success (suggesting transient failures, not sustained outage)
        recent_history = history[-3:] if len(history) >= 3 else history
        has_recent_success = any(success for _, success in recent_history)

        ratio_breach = (
            availability_ratio < threshold_ratio
            and total_pings >= 5
            and not ping_success  # Only apply ratio escalation during active failures
            and not has_recent_success  # Don't apply if we just recovered
        )

        # Determine final severity: MAX(consecutive-based, ratio-based)
        if ratio_breach:
            severity = ViolationSeverity.CRITICAL

        # Build message based on failure mode
        if ratio_breach:
            # Sustained SLA violation (many failures over time)
            message = (
                f"Availability is {availability_pct:.1f}%, "
                f"SLA threshold is {threshold_pct:.1f}%"
            )
        elif not ping_success:
            # Active ping failure (connection issue)
            message = (
                f"Data source unreachable or failed validation "
                f"(consecutive failures: {consecutive})"
            )
            if error_msg:
                message += f": {error_msg}"
        else:
            # Ping succeeded but ratio below threshold (recovering)
            message = (
                f"Availability is {availability_pct:.1f}%, "
                f"SLA threshold is {threshold_pct:.1f}% (recovering)"
            )

        violation = ContractViolationEvent(
            contract_name=contract.contract_name,
            contract_version=contract.contract_version,
            violation_type=ViolationType.AVAILABILITY,
            severity=severity,
            message=message,
            expected_value=f"{threshold_pct:.1f}%",
            actual_value=f"{availability_pct:.1f}%",
            timestamp=now,
            check_duration_seconds=duration,
            metadata={
                "availability_ratio": f"{availability_ratio:.4f}",
                "threshold_pct": str(threshold_pct),
                "consecutive_failures": str(consecutive),
                "total_pings": str(total_pings),
                "successful_pings": str(successful_pings),
            },
        )

        return CheckResult(
            contract_name=contract.contract_name,
            check_type=ViolationType.AVAILABILITY,
            status=CheckStatus.FAIL,
            duration_seconds=duration,
            timestamp=now,
            details={
                "latency_ms": latency_ms,
                "availability_ratio": availability_ratio,
                "threshold_pct": threshold_pct,
                "consecutive_failures": consecutive,
            },
            violation=violation,
        )
