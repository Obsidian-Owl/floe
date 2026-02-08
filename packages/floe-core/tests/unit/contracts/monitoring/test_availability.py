"""Unit tests for AvailabilityCheck.

Tasks: T049 (Epic 3D)
Requirements: FR-019, FR-020, FR-021, FR-022
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.checks.availability import AvailabilityCheck
from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.violations import (
    CheckStatus,
    ViolationSeverity,
    ViolationType,
)


class MockComputePlugin:
    """Mock compute plugin that returns controllable ping results."""

    def __init__(
        self,
        *,
        success: bool = True,
        latency_ms: float = 10.0,
        raise_error: bool = False,
    ) -> None:
        self.success = success
        self.latency_ms = latency_ms
        self.raise_error = raise_error

    async def validate_connection(self) -> dict[str, Any]:
        """Mock validate_connection method.

        Returns:
            Dictionary with status and latency_ms.

        Raises:
            ConnectionError: If raise_error is True.
        """
        if self.raise_error:
            raise ConnectionError("Connection refused")
        return {
            "status": "ok" if self.success else "error",
            "latency_ms": self.latency_ms,
        }


def _make_contract(
    *,
    threshold_pct: float = 99.9,
    name: str = "test_contract",
    availability_present: bool = True,
) -> RegisteredContract:
    """Create a RegisteredContract with optional availability SLA.

    Args:
        threshold_pct: Availability threshold percentage.
        name: Contract name.
        availability_present: Whether to include availability SLA config.

    Returns:
        RegisteredContract instance.
    """
    now = datetime.now(tz=timezone.utc)
    contract_data: dict[str, Any] = {"apiVersion": "v3.1.0"}
    if availability_present:
        contract_data["sla"] = {"availability": {"threshold_pct": threshold_pct}}
    return RegisteredContract(
        contract_name=name,
        contract_version="1.0.0",
        contract_data=contract_data,
        connection_config={"catalog": "polaris"},
        registered_at=now - timedelta(hours=2),
    )


@pytest.mark.requirement("3D-FR-019")
def test_availability_check_type() -> None:
    """Test that AvailabilityCheck returns correct check_type."""
    check = AvailabilityCheck()
    assert check.check_type == ViolationType.AVAILABILITY


@pytest.mark.requirement("3D-FR-019")
@pytest.mark.asyncio
async def test_availability_ping_success() -> None:
    """Test availability check passes when ping succeeds."""
    contract = _make_contract(threshold_pct=99.9)
    config = MonitoringConfig()
    plugin = MockComputePlugin(success=True, latency_ms=15.5)

    check = AvailabilityCheck(compute_plugin=plugin)
    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.PASS
    assert result.check_type == ViolationType.AVAILABILITY
    assert result.contract_name == "test_contract"
    assert result.violation is None
    assert "latency_ms" in result.details
    assert result.details["latency_ms"] == pytest.approx(15.5)
    assert "availability_ratio" in result.details
    assert result.details["availability_ratio"] == pytest.approx(1.0)  # 100% on first ping


@pytest.mark.requirement("3D-FR-020")
@pytest.mark.asyncio
async def test_availability_ping_failure() -> None:
    """Test availability check fails when ping fails."""
    contract = _make_contract(threshold_pct=99.9)
    config = MonitoringConfig()
    plugin = MockComputePlugin(success=False)

    check = AvailabilityCheck(compute_plugin=plugin)
    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.FAIL
    assert result.check_type == ViolationType.AVAILABILITY
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.AVAILABILITY
    assert result.violation.severity == ViolationSeverity.WARNING  # First failure
    msg_lower = result.violation.message.lower()
    assert "unreachable" in msg_lower or "failed" in msg_lower
    assert result.violation.contract_name == "test_contract"


@pytest.mark.requirement("3D-FR-020")
@pytest.mark.asyncio
async def test_availability_timeout() -> None:
    """Test availability check handles timeout correctly."""
    contract = _make_contract(threshold_pct=99.9)
    config = MonitoringConfig()
    plugin = MockComputePlugin(raise_error=True)

    check = AvailabilityCheck(compute_plugin=plugin)
    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.severity == ViolationSeverity.WARNING  # First failure
    msg_lower = result.violation.message.lower()
    assert "connection" in msg_lower or "error" in msg_lower


@pytest.mark.requirement("3D-FR-021")
@pytest.mark.asyncio
async def test_availability_consecutive_failures() -> None:
    """Test consecutive failures increase severity."""
    contract = _make_contract(threshold_pct=99.9)
    config = MonitoringConfig()
    plugin = MockComputePlugin(success=False)

    check = AvailabilityCheck(compute_plugin=plugin)

    # First failure: WARNING
    result1 = await check.execute(contract=contract, config=config)
    assert result1.violation is not None
    assert result1.violation.severity == ViolationSeverity.WARNING

    # Second failure: still WARNING
    result2 = await check.execute(contract=contract, config=config)
    assert result2.violation is not None
    assert result2.violation.severity == ViolationSeverity.WARNING

    # Third failure: ERROR
    result3 = await check.execute(contract=contract, config=config)
    assert result3.violation is not None
    assert result3.violation.severity == ViolationSeverity.ERROR

    # Fourth failure: ERROR
    result4 = await check.execute(contract=contract, config=config)
    assert result4.violation is not None
    assert result4.violation.severity == ViolationSeverity.ERROR

    # Fifth failure: CRITICAL
    result5 = await check.execute(contract=contract, config=config)
    assert result5.violation is not None
    assert result5.violation.severity == ViolationSeverity.CRITICAL


@pytest.mark.requirement("3D-FR-021")
@pytest.mark.asyncio
async def test_availability_recovery_reset() -> None:
    """Test that success after failures resets consecutive counter."""
    contract = _make_contract(threshold_pct=99.9)
    config = MonitoringConfig()
    fail_plugin = MockComputePlugin(success=False)
    success_plugin = MockComputePlugin(success=True)

    check = AvailabilityCheck(compute_plugin=fail_plugin)

    # Three failures: escalate to ERROR
    await check.execute(contract=contract, config=config)
    await check.execute(contract=contract, config=config)
    result_fail = await check.execute(contract=contract, config=config)
    assert result_fail.violation is not None
    assert result_fail.violation.severity == ViolationSeverity.ERROR

    # Success: resets counter
    # Actually, we need to use the same instance. Let's modify approach.
    # The check maintains state across calls on the same instance.
    check_stateful = AvailabilityCheck(compute_plugin=fail_plugin)

    # Three failures
    await check_stateful.execute(contract=contract, config=config)
    await check_stateful.execute(contract=contract, config=config)
    await check_stateful.execute(contract=contract, config=config)

    # Now switch to success plugin
    check_stateful._compute_plugin = success_plugin
    result_success = await check_stateful.execute(contract=contract, config=config)
    assert result_success.status == CheckStatus.PASS

    # Next failure should be WARNING again (counter reset)
    check_stateful._compute_plugin = fail_plugin
    result_after_reset = await check_stateful.execute(contract=contract, config=config)
    assert result_after_reset.violation is not None
    assert result_after_reset.violation.severity == ViolationSeverity.WARNING


@pytest.mark.requirement("3D-FR-019")
@pytest.mark.asyncio
async def test_availability_ratio_calculation() -> None:
    """Test rolling window ratio is calculated correctly."""
    contract = _make_contract(threshold_pct=99.0)
    config = MonitoringConfig()

    check = AvailabilityCheck(compute_plugin=MockComputePlugin(success=True))

    # First ping: 100%
    result1 = await check.execute(contract=contract, config=config)
    assert result1.details["availability_ratio"] == pytest.approx(1.0)

    # Second ping (success): 100%
    result2 = await check.execute(contract=contract, config=config)
    assert result2.details["availability_ratio"] == pytest.approx(1.0)

    # Third ping (fail): 66.7%
    check._compute_plugin = MockComputePlugin(success=False)
    result3 = await check.execute(contract=contract, config=config)
    assert result3.details["availability_ratio"] == pytest.approx(0.6667, abs=0.01)

    # Fourth ping (success): 75%
    check._compute_plugin = MockComputePlugin(success=True)
    result4 = await check.execute(contract=contract, config=config)
    assert result4.details["availability_ratio"] == pytest.approx(0.75, abs=0.01)


@pytest.mark.requirement("3D-FR-021")
@pytest.mark.asyncio
async def test_availability_below_sla_threshold() -> None:
    """Test that availability ratio below SLA threshold triggers CRITICAL."""
    contract = _make_contract(threshold_pct=80.0)
    config = MonitoringConfig()

    check = AvailabilityCheck(compute_plugin=MockComputePlugin(success=True))

    # Build up history: 1 success, then 4 failures = 20% availability
    await check.execute(contract=contract, config=config)  # success: 100%

    check._compute_plugin = MockComputePlugin(success=False)
    await check.execute(contract=contract, config=config)  # fail: 50%
    await check.execute(contract=contract, config=config)  # fail: 33%
    await check.execute(contract=contract, config=config)  # fail: 25%
    result = await check.execute(contract=contract, config=config)  # fail: 20%

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    # 5 consecutive failures = CRITICAL severity
    assert result.violation.severity == ViolationSeverity.CRITICAL
    assert "availability" in result.violation.message.lower()
    assert result.details["availability_ratio"] == pytest.approx(0.2)
    assert result.violation.expected_value == "80.0%"
    assert result.violation.actual_value == "20.0%"


@pytest.mark.requirement("3D-FR-019")
@pytest.mark.asyncio
async def test_availability_no_config() -> None:
    """Test availability check returns ERROR when no SLA config present."""
    contract = _make_contract(availability_present=False)
    config = MonitoringConfig()
    plugin = MockComputePlugin(success=True)

    check = AvailabilityCheck(compute_plugin=plugin)
    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.ERROR
    assert result.violation is None
    error_lower = result.details["error"].lower()
    assert "availability" in error_lower or "sla" in error_lower


@pytest.mark.requirement("3D-FR-019")
@pytest.mark.asyncio
async def test_availability_no_compute_plugin() -> None:
    """Test availability check returns SKIPPED when no compute_plugin provided."""
    contract = _make_contract(threshold_pct=99.9)
    config = MonitoringConfig()

    check = AvailabilityCheck(compute_plugin=None)
    result = await check.execute(contract=contract, config=config)

    assert result.status == CheckStatus.SKIPPED
    assert result.violation is None
    assert "plugin" in result.details["reason"].lower()


@pytest.mark.requirement("3D-FR-019")
@pytest.mark.asyncio
async def test_availability_violation_event_fields() -> None:
    """Test that ContractViolationEvent has all required fields."""
    contract = _make_contract(threshold_pct=99.9, name="orders_v1")
    config = MonitoringConfig()
    plugin = MockComputePlugin(success=False)

    check = AvailabilityCheck(compute_plugin=plugin)
    result = await check.execute(contract=contract, config=config)

    assert result.violation is not None
    violation = result.violation

    # Required fields
    assert violation.contract_name == "orders_v1"
    assert violation.contract_version == "1.0.0"
    assert violation.violation_type == ViolationType.AVAILABILITY
    assert violation.severity in (
        ViolationSeverity.INFO,
        ViolationSeverity.WARNING,
        ViolationSeverity.ERROR,
        ViolationSeverity.CRITICAL,
    )
    assert isinstance(violation.message, str)
    assert len(violation.message) > 0
    assert isinstance(violation.timestamp, datetime)
    assert violation.check_duration_seconds > 0.0

    # Optional fields should be present for availability violations
    assert violation.expected_value is not None
    assert violation.actual_value is not None
    assert isinstance(violation.metadata, dict)
