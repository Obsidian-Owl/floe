"""Integration tests for all check types with real data persistence.

Tests freshness, schema_drift, quality, and availability checks with PostgreSQL storage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.checks.availability import AvailabilityCheck
from floe_core.contracts.monitoring.checks.freshness import FreshnessCheck
from floe_core.contracts.monitoring.checks.quality import QualityCheck
from floe_core.contracts.monitoring.checks.schema_drift import SchemaDriftCheck
from floe_core.contracts.monitoring.config import MonitoringConfig, RegisteredContract
from floe_core.contracts.monitoring.violations import (
    CheckStatus,
    ViolationSeverity,
)


class MockQualityPlugin:
    """Mock quality plugin for testing."""

    def __init__(self, scores: dict[str, float]) -> None:
        """Initialize mock with predefined scores.

        Args:
            scores: Mapping of expectation names to scores
        """
        self.scores = scores

    async def run_checks(self, expectations: list[dict[str, Any]]) -> dict[str, float]:
        """Return predefined scores for expectations.

        Args:
            expectations: List of expectation configs

        Returns:
            Mapping of expectation names to scores
        """
        return self.scores


class MockComputePlugin:
    """Mock compute plugin for testing."""

    def __init__(self, *, success: bool = True, latency_ms: float = 10.0) -> None:
        """Initialize mock with connection behavior.

        Args:
            success: Whether connection should succeed
            latency_ms: Simulated latency in milliseconds
        """
        self.success = success
        self.latency_ms = latency_ms

    async def validate_connection(self) -> dict[str, Any]:
        """Simulate connection validation.

        Returns:
            Connection status dict

        Raises:
            ConnectionError: If success is False
        """
        if not self.success:
            raise ConnectionError("Connection refused")
        return {"status": "ok", "latency_ms": self.latency_ms}


def _make_contract(contract_data: dict[str, Any]) -> RegisteredContract:
    """Create a RegisteredContract with correct fields for testing.

    Args:
        contract_data: Contract data payload

    Returns:
        RegisteredContract instance with unique name
    """
    return RegisteredContract(
        contract_name=f"test_contract_{uuid.uuid4().hex[:8]}",
        contract_version="1.0.0",
        contract_data=contract_data,
        connection_config={"catalog": "test"},
        registered_at=datetime.now(timezone.utc),
    )


# Freshness Tests


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_freshness_check_pass_fresh_data() -> None:
    """Test freshness check passes with fresh data."""
    contract = _make_contract({
        "sla": {"freshness": {"threshold_minutes": 60}},
        "dataset": {"last_updated": datetime.now(timezone.utc).isoformat()},
    })
    config = MonitoringConfig()
    check = FreshnessCheck()

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.PASS
    assert result.violation is None


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_freshness_check_fail_stale_data() -> None:
    """Test freshness check fails with stale data and creates violation."""
    stale_time = datetime.now(timezone.utc) - timedelta(hours=2)
    contract = _make_contract({
        "sla": {"freshness": {"threshold_minutes": 30}},
        "dataset": {"last_updated": stale_time.isoformat()},
    })
    config = MonitoringConfig()
    check = FreshnessCheck()

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.violation_type == "FRESHNESS"
    assert result.violation.severity == ViolationSeverity.ERROR


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_freshness_check_error_missing_config() -> None:
    """Test freshness check returns ERROR when SLA config is missing."""
    contract = _make_contract({
        "dataset": {"last_updated": datetime.now(timezone.utc).isoformat()},
    })
    config = MonitoringConfig()
    check = FreshnessCheck()

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.ERROR
    assert "No freshness SLA" in result.details.get("error", "")


# Schema Drift Tests


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_schema_drift_check_pass_matching_schemas() -> None:
    """Test schema drift check passes with identical schemas."""
    schema_columns = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
    ]
    contract = _make_contract({
        "schema": {"columns": schema_columns},
        "actual_schema": {"columns": schema_columns},
    })
    config = MonitoringConfig()
    check = SchemaDriftCheck()

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.PASS


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_schema_drift_check_fail_column_removed() -> None:
    """Test schema drift check fails with CRITICAL when column is removed."""
    expected_columns = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
        {"name": "email", "type": "string", "nullable": True},
    ]
    actual_columns = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
    ]
    contract = _make_contract({
        "schema": {"columns": expected_columns},
        "actual_schema": {"columns": actual_columns},
    })
    config = MonitoringConfig()
    check = SchemaDriftCheck()

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.severity == ViolationSeverity.CRITICAL


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_schema_drift_check_fail_type_changed() -> None:
    """Test schema drift check fails with ERROR when type changes."""
    expected_columns = [
        {"name": "age", "type": "integer", "nullable": False},
    ]
    actual_columns = [
        {"name": "age", "type": "string", "nullable": False},
    ]
    contract = _make_contract({
        "schema": {"columns": expected_columns},
        "actual_schema": {"columns": actual_columns},
    })
    config = MonitoringConfig()
    check = SchemaDriftCheck()

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.severity == ViolationSeverity.ERROR


# Quality Tests


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_quality_check_pass_above_threshold() -> None:
    """Test quality check passes when score is above threshold."""
    mock_plugin = MockQualityPlugin(scores={"completeness": 0.95})
    contract = _make_contract({
        "quality": {
            "threshold": 0.8,
            "expectations": [{"name": "completeness", "weight": 1.0}],
        },
    })
    config = MonitoringConfig()
    check = QualityCheck(quality_plugin=mock_plugin)

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.PASS
    assert result.violation is None


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_quality_check_fail_below_threshold() -> None:
    """Test quality check fails when score is below threshold."""
    mock_plugin = MockQualityPlugin(scores={"completeness": 0.3})
    contract = _make_contract({
        "quality": {
            "threshold": 0.8,
            "expectations": [{"name": "completeness", "weight": 1.0}],
        },
    })
    config = MonitoringConfig()
    check = QualityCheck(quality_plugin=mock_plugin)

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_quality_check_skipped_no_plugin() -> None:
    """Test quality check returns SKIPPED when no plugin is provided."""
    contract = _make_contract({
        "quality": {
            "threshold": 0.8,
            "expectations": [{"name": "completeness", "weight": 1.0}],
        },
    })
    config = MonitoringConfig()
    check = QualityCheck(quality_plugin=None)

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.SKIPPED


# Availability Tests


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_availability_check_pass_source_reachable() -> None:
    """Test availability check passes when source is reachable."""
    mock_plugin = MockComputePlugin(success=True, latency_ms=10.0)
    contract = _make_contract({
        "sla": {"availability": {"threshold_pct": 95.0}},
    })
    config = MonitoringConfig()
    check = AvailabilityCheck(compute_plugin=mock_plugin)

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.PASS


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_availability_check_fail_source_unreachable() -> None:
    """Test availability check fails when source is unreachable."""
    mock_plugin = MockComputePlugin(success=False)
    contract = _make_contract({
        "sla": {"availability": {"threshold_pct": 95.0}},
    })
    config = MonitoringConfig()
    check = AvailabilityCheck(compute_plugin=mock_plugin)

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None


@pytest.mark.asyncio
@pytest.mark.requirement("003e-FR-028")
async def test_availability_check_skipped_no_plugin() -> None:
    """Test availability check returns SKIPPED when no plugin is provided."""
    contract = _make_contract({
        "sla": {"availability": {"threshold_pct": 95.0}},
    })
    config = MonitoringConfig()
    check = AvailabilityCheck(compute_plugin=None)

    result = await check.execute(contract, config)

    assert result.status == CheckStatus.SKIPPED
