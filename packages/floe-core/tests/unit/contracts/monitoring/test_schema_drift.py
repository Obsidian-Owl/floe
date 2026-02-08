"""Unit tests for SchemaDriftCheck contract monitoring.

TDD-style tests — written FIRST, will FAIL until SchemaDriftCheck is implemented.

Tasks: T021 (Epic 3D)
Requirements: 3D-FR-011, 3D-FR-012, 3D-FR-013
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.checks.schema_drift import SchemaDriftCheck
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
    expected_schema: list[dict[str, Any]] | None = None,
    actual_schema: list[dict[str, Any]] | None = None,
    name: str = "test_contract",
    schema_present: bool = True,
    actual_schema_present: bool = True,
) -> RegisteredContract:
    """Helper to build a RegisteredContract with configurable schema data.

    Args:
        expected_schema: Expected schema columns (from contract definition).
        actual_schema: Actual schema columns (from data source).
        name: Contract name.
        schema_present: Whether to include "schema" key in contract_data.
        actual_schema_present: Whether to include "actual_schema" key in contract_data.

    Returns:
        RegisteredContract configured for schema drift testing.
    """
    now = datetime.now(tz=timezone.utc)
    contract_data: dict[str, Any] = {"apiVersion": "v3.1.0"}

    if schema_present:
        if expected_schema is not None:
            contract_data["schema"] = {"columns": expected_schema}
        else:
            contract_data["schema"] = {}

    if actual_schema_present:
        if actual_schema is not None:
            contract_data["actual_schema"] = {"columns": actual_schema}
        else:
            contract_data["actual_schema"] = {}

    return RegisteredContract(
        contract_name=name,
        contract_version="1.0.0",
        contract_data=contract_data,
        connection_config={"catalog": "polaris"},
        registered_at=now - timedelta(hours=2),
    )


# ================================
# SchemaDriftCheck Type Tests
# ================================


@pytest.mark.requirement("3D-FR-011")
def test_schema_drift_check_type() -> None:
    """Test that SchemaDriftCheck.check_type returns SCHEMA_DRIFT."""
    check = SchemaDriftCheck()
    assert check.check_type == ViolationType.SCHEMA_DRIFT


# ================================
# SchemaDriftCheck Pass Tests
# ================================


@pytest.mark.requirement("3D-FR-011")
@pytest.mark.asyncio
async def test_schema_drift_no_drift() -> None:
    """Test schema drift check passes when schemas match exactly.

    Both expected and actual schemas have same columns with same types
    and nullability -> PASS.
    """
    schema = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
        {"name": "created_at", "type": "timestamp", "nullable": False},
    ]
    contract = _make_contract(expected_schema=schema, actual_schema=schema)
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.PASS
    assert result.contract_name == "test_contract"
    assert result.check_type == ViolationType.SCHEMA_DRIFT
    assert result.violation is None
    assert result.duration_seconds >= 0


@pytest.mark.requirement("3D-FR-011")
@pytest.mark.asyncio
async def test_schema_drift_empty_schemas() -> None:
    """Test schema drift check passes when both schemas are empty.

    Empty expected and empty actual -> PASS (trivial match).
    """
    contract = _make_contract(expected_schema=[], actual_schema=[])
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.PASS
    assert result.violation is None


# ================================
# SchemaDriftCheck Fail Tests
# ================================


@pytest.mark.requirement("3D-FR-012")
@pytest.mark.asyncio
async def test_schema_drift_column_added() -> None:
    """Test schema drift check fails when actual schema has extra column.

    Actual has a column not in expected -> FAIL with WARNING severity
    (additive change, backward compatible).
    """
    expected = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
    ]
    actual = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
        {"name": "email", "type": "string", "nullable": True},  # Added column
    ]
    contract = _make_contract(expected_schema=expected, actual_schema=actual)
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.SCHEMA_DRIFT
    assert result.violation.severity == ViolationSeverity.WARNING
    # Verify drift details contain the added column
    drifts = result.details.get("drifts", [])
    assert len(drifts) == 1
    assert drifts[0]["column"] == "email"
    assert drifts[0]["drift_type"] == "column_added"


@pytest.mark.requirement("3D-FR-012")
@pytest.mark.asyncio
async def test_schema_drift_column_removed() -> None:
    """Test schema drift check fails when actual schema is missing a column.

    Expected has a column not in actual -> FAIL with CRITICAL severity
    (breaking change, data consumers may fail).
    """
    expected = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
        {"name": "email", "type": "string", "nullable": True},
    ]
    actual = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
        # email removed
    ]
    contract = _make_contract(expected_schema=expected, actual_schema=actual)
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.SCHEMA_DRIFT
    assert result.violation.severity == ViolationSeverity.CRITICAL
    drifts = result.details.get("drifts", [])
    assert len(drifts) == 1
    assert drifts[0]["column"] == "email"
    assert drifts[0]["drift_type"] == "column_removed"


@pytest.mark.requirement("3D-FR-013")
@pytest.mark.asyncio
async def test_schema_drift_type_changed() -> None:
    """Test schema drift check fails when column type changes.

    Column exists in both but type differs -> FAIL with ERROR severity
    (breaking change, type incompatible).
    """
    expected = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "amount", "type": "decimal", "nullable": False},
    ]
    actual = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "amount", "type": "string", "nullable": False},  # Type changed
    ]
    contract = _make_contract(expected_schema=expected, actual_schema=actual)
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.SCHEMA_DRIFT
    assert result.violation.severity == ViolationSeverity.ERROR
    drifts = result.details.get("drifts", [])
    assert len(drifts) == 1
    assert drifts[0]["column"] == "amount"
    assert drifts[0]["drift_type"] == "type_changed"
    assert drifts[0]["expected"] == "decimal"
    assert drifts[0]["actual"] == "string"


@pytest.mark.requirement("3D-FR-013")
@pytest.mark.asyncio
async def test_schema_drift_nullability_changed() -> None:
    """Test schema drift check fails when column nullability changes.

    Column type matches but nullable differs -> FAIL with WARNING severity
    (potentially breaking, depending on direction).
    """
    expected = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
    ]
    actual = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": False},  # Nullability changed
    ]
    contract = _make_contract(expected_schema=expected, actual_schema=actual)
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.SCHEMA_DRIFT
    assert result.violation.severity == ViolationSeverity.WARNING
    drifts = result.details.get("drifts", [])
    assert len(drifts) == 1
    assert drifts[0]["column"] == "name"
    assert drifts[0]["drift_type"] == "nullability_changed"


@pytest.mark.requirement("3D-FR-012")
@pytest.mark.asyncio
async def test_schema_drift_multiple_drifts() -> None:
    """Test schema drift check reports all drifts when multiple exist.

    Multiple changes (added, removed, type changed) -> FAIL with details
    listing all drifts. Severity should be CRITICAL (worst of all drifts).
    """
    expected = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
        {"name": "email", "type": "string", "nullable": True},
    ]
    actual = [
        {"name": "id", "type": "string", "nullable": False},  # Type changed
        {"name": "name", "type": "string", "nullable": True},
        {"name": "phone", "type": "string", "nullable": True},  # Added column
        # email removed
    ]
    contract = _make_contract(expected_schema=expected, actual_schema=actual)
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None
    assert result.violation.violation_type == ViolationType.SCHEMA_DRIFT
    # Worst severity should be CRITICAL (column removed)
    assert result.violation.severity == ViolationSeverity.CRITICAL
    # Should report all drifts
    drifts = result.details.get("drifts", [])
    assert len(drifts) == 3  # type_changed(id), column_removed(email), column_added(phone)
    drift_columns = {d["column"] for d in drifts}
    assert drift_columns == {"id", "email", "phone"}
    drift_types = {d["drift_type"] for d in drifts}
    assert "type_changed" in drift_types
    assert "column_removed" in drift_types
    assert "column_added" in drift_types


# ================================
# SchemaDriftCheck Error Tests
# ================================


@pytest.mark.requirement("3D-FR-011")
@pytest.mark.asyncio
async def test_schema_drift_missing_schema_config() -> None:
    """Test schema drift check returns ERROR when schema config is missing."""
    contract = _make_contract(schema_present=False, actual_schema_present=True)
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.ERROR
    assert result.violation is None
    assert "schema" in result.details.get("error", "").lower()


@pytest.mark.requirement("3D-FR-011")
@pytest.mark.asyncio
async def test_schema_drift_missing_actual_schema() -> None:
    """Test schema drift check returns ERROR when actual_schema is missing."""
    expected = [{"name": "id", "type": "integer", "nullable": False}]
    contract = _make_contract(
        expected_schema=expected,
        actual_schema_present=False,
    )
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.ERROR
    assert result.violation is None
    assert "actual_schema" in result.details.get("error", "").lower()


# ================================
# Violation Event Field Tests
# ================================


@pytest.mark.requirement("3D-FR-012")
@pytest.mark.asyncio
async def test_schema_drift_violation_event_fields() -> None:
    """Test that ContractViolationEvent has all correct fields on violation."""
    expected = [
        {"name": "id", "type": "integer", "nullable": False},
        {"name": "name", "type": "string", "nullable": True},
    ]
    actual = [
        {"name": "id", "type": "string", "nullable": False},  # Type changed
        {"name": "name", "type": "string", "nullable": True},
    ]
    contract = _make_contract(
        expected_schema=expected,
        actual_schema=actual,
        name="orders_v1",
    )
    config = MonitoringConfig()

    check = SchemaDriftCheck()
    result = await check.execute(contract, config)

    assert result.status == CheckStatus.FAIL
    assert result.violation is not None

    violation = result.violation
    assert violation.contract_name == "orders_v1"
    assert violation.contract_version == "1.0.0"
    assert violation.violation_type == ViolationType.SCHEMA_DRIFT
    assert violation.severity in list(ViolationSeverity)
    assert len(violation.message) > 0
    assert violation.timestamp is not None
    assert violation.check_duration_seconds >= 0
    # Expected/actual should describe the schema drift
    # (either in violation or details)
    assert violation.expected_value is not None or "expected" in result.details
    assert violation.actual_value is not None or "actual" in result.details
