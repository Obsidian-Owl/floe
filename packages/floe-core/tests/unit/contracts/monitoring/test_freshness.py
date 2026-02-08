"""Unit tests for FreshnessCheck contract monitoring.

TDD-style tests — written FIRST, will FAIL until FreshnessCheck is implemented.

Tasks: T020 (Epic 3D)
Requirements: 3D-FR-007, 3D-FR-008, 3D-FR-009, 3D-FR-010
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.checks.freshness import FreshnessCheck
from floe_core.contracts.monitoring.config import (
    MonitoringConfig,
    RegisteredContract,
)
from floe_core.contracts.monitoring.violations import (
    CheckStatus,
    ViolationSeverity,
    ViolationType,
)


def _make_contract(
    *,
    threshold_minutes: int = 120,
    data_age_minutes: float | None = 60,
    name: str = "test_contract",
    sla_present: bool = True,
    dataset_present: bool = True,
    timestamp_value: str | None = None,
) -> RegisteredContract:
    """Helper to build a RegisteredContract with configurable freshness data."""
    now = datetime.now(tz=timezone.utc)
    contract_data: dict[str, Any] = {"apiVersion": "v3.1.0"}

    if sla_present:
        contract_data["sla"] = {
            "freshness": {
                "threshold_minutes": threshold_minutes,
                "timestamp_field": "updated_at",
            }
        }
    else:
        contract_data["sla"] = {}

    if dataset_present and (data_age_minutes is not None or timestamp_value is not None):
        ts = timestamp_value or (now - timedelta(minutes=data_age_minutes)).isoformat()  # type: ignore[arg-type]
        contract_data["dataset"] = {"last_updated": ts}
    elif dataset_present:
        contract_data["dataset"] = {}
    # else: no dataset key at all

    return RegisteredContract(
        contract_name=name,
        contract_version="1.0.0",
        contract_data=contract_data,
        connection_config={"catalog": "polaris"},
        registered_at=now - timedelta(hours=2),
    )


# ================================
# FreshnessCheck Type Tests
# ================================


@pytest.mark.requirement("3D-FR-007")
def test_freshness_check_type() -> None:
    """Test that FreshnessCheck.check_type returns FRESHNESS."""
    check = FreshnessCheck()
    assert check.check_type == ViolationType.FRESHNESS


# ================================
# FreshnessCheck Pass Tests
# ================================


@pytest.mark.requirement("3D-FR-008")
@pytest.mark.asyncio
async def test_freshness_check_pass_data_fresh() -> None:
    """Test freshness check passes when data is within threshold.

    Data is 60 minutes old, threshold is 120 minutes -> PASS.
    """
    contract = _make_contract(threshold_minutes=120, data_age_minutes=60)
    config = MonitoringConfig()

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.PASS
    assert result.contract_name == "test_contract"
    assert result.check_type == ViolationType.FRESHNESS
    assert result.violation is None
    assert result.duration_seconds >= 0


@pytest.mark.requirement("3D-FR-010")
@pytest.mark.asyncio
async def test_freshness_check_clock_skew_tolerance() -> None:
    """Test clock skew tolerance allows data slightly over threshold.

    Data is 120 min + 30 sec old, threshold is 120 min, tolerance is 60 sec.
    30 seconds over threshold is within 60-second tolerance -> PASS.
    """
    now = datetime.now(tz=timezone.utc)
    data_time = now - timedelta(minutes=120, seconds=30)
    contract = _make_contract(
        threshold_minutes=120,
        data_age_minutes=None,
        timestamp_value=data_time.isoformat(),
    )
    config = MonitoringConfig(clock_skew_tolerance_seconds=60)

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.PASS
    assert result.violation is None


@pytest.mark.requirement("3D-FR-008")
@pytest.mark.asyncio
async def test_freshness_check_pass_exactly_at_threshold() -> None:
    """Test freshness check at exact threshold boundary.

    Data is exactly 120 minutes old, threshold is 120 minutes.
    At-or-equal should PASS (not yet stale). Uses 1-second tolerance
    to account for microsecond execution gap between test and check.
    """
    now = datetime.now(tz=timezone.utc)
    data_time = now - timedelta(minutes=120)
    contract = _make_contract(
        threshold_minutes=120,
        data_age_minutes=None,
        timestamp_value=data_time.isoformat(),
    )
    config = MonitoringConfig(clock_skew_tolerance_seconds=1)

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    # Exactly at threshold should PASS (data age <= threshold)
    assert result.status == CheckStatus.PASS


# ================================
# FreshnessCheck Fail Tests
# ================================


@pytest.mark.requirement("3D-FR-009")
@pytest.mark.asyncio
async def test_freshness_check_fail_data_stale() -> None:
    """Test freshness check fails when data exceeds threshold.

    Data is 180 minutes old, threshold is 120 minutes -> FAIL with violation.
    """
    contract = _make_contract(threshold_minutes=120, data_age_minutes=180)
    config = MonitoringConfig()

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.FRESHNESS
    assert result.violation.contract_name == "test_contract"
    assert result.violation.contract_version == "1.0.0"
    assert result.violation.check_duration_seconds >= 0


@pytest.mark.requirement("3D-FR-010")
@pytest.mark.asyncio
async def test_freshness_check_fail_beyond_clock_skew() -> None:
    """Test data over threshold AND beyond clock skew tolerance -> FAIL.

    Data is 125 min old, threshold is 120 min, tolerance is 60 sec.
    5 minutes over > 60 seconds tolerance -> FAIL.
    """
    now = datetime.now(tz=timezone.utc)
    data_time = now - timedelta(minutes=125)
    contract = _make_contract(
        threshold_minutes=120,
        data_age_minutes=None,
        timestamp_value=data_time.isoformat(),
    )
    config = MonitoringConfig(clock_skew_tolerance_seconds=60)

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None


# ================================
# FreshnessCheck Error Tests
# ================================


@pytest.mark.requirement("3D-FR-009")
@pytest.mark.asyncio
async def test_freshness_check_error_missing_sla_config() -> None:
    """Test freshness check returns ERROR when freshness SLA config is missing."""
    contract = _make_contract(sla_present=False)
    config = MonitoringConfig()

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.ERROR
    assert result.violation is None
    assert "freshness" in result.details.get("error", "").lower()


@pytest.mark.requirement("3D-FR-009")
@pytest.mark.asyncio
async def test_freshness_check_error_missing_dataset_timestamp() -> None:
    """Test freshness check returns ERROR when dataset timestamp is missing."""
    contract = _make_contract(data_age_minutes=None, dataset_present=True)
    config = MonitoringConfig()

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.ERROR
    assert result.violation is None


@pytest.mark.requirement("3D-FR-009")
@pytest.mark.asyncio
async def test_freshness_check_error_invalid_timestamp() -> None:
    """Test freshness check returns ERROR when timestamp is unparseable."""
    contract = _make_contract(
        data_age_minutes=None,
        timestamp_value="not-a-valid-timestamp",
    )
    config = MonitoringConfig()

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.ERROR
    assert result.violation is None


# ================================
# Violation Event Field Tests
# ================================


@pytest.mark.requirement("3D-FR-009")
@pytest.mark.asyncio
async def test_freshness_check_violation_event_fields() -> None:
    """Test that ContractViolationEvent has all correct fields on violation."""
    contract = _make_contract(
        threshold_minutes=120,
        data_age_minutes=180,
        name="orders_v1",
    )
    config = MonitoringConfig()

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None

    violation = result.violation
    assert violation.contract_name == "orders_v1"
    assert violation.contract_version == "1.0.0"
    assert violation.violation_type == ViolationType.FRESHNESS
    assert violation.severity in list(ViolationSeverity)
    assert len(violation.message) > 0
    assert violation.timestamp is not None
    assert violation.check_duration_seconds >= 0
    # Expected/actual should describe the freshness situation
    assert violation.expected_value is not None
    assert violation.actual_value is not None


@pytest.mark.requirement("3D-FR-008")
@pytest.mark.asyncio
async def test_freshness_check_duration_recorded() -> None:
    """Test that duration_seconds is recorded in the CheckResult."""
    contract = _make_contract(threshold_minutes=120, data_age_minutes=60)
    config = MonitoringConfig()

    check = FreshnessCheck()
    result = await check.execute(contract, config)

    assert result.duration_seconds >= 0
    # Duration should be reasonable (< timeout)
    assert result.duration_seconds < config.check_timeout_seconds
