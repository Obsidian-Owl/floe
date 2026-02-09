"""Unit tests for root cause context enrichment.

Tests the build_root_cause_context function that populates metadata
for root cause analysis and debugging.

Task: T074 (Epic 3D)
Requirement: 3D-FR-044
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.config import RegisteredContract
from floe_core.contracts.monitoring.enrichment import build_root_cause_context


def _make_contract(
    *,
    contract_name: str = "test_contract",
    contract_version: str = "1.0.0",
    contract_data: dict[str, Any] | None = None,
    connection_config: dict[str, Any] | None = None,
    last_check_times: dict[str, datetime] | None = None,
    registered_at: datetime | None = None,
) -> RegisteredContract:
    """Create a test RegisteredContract instance."""
    contract = RegisteredContract(
        contract_name=contract_name,
        contract_version=contract_version,
        contract_data=contract_data or {},
        connection_config=connection_config or {},
        registered_at=registered_at or datetime.now(tz=timezone.utc),
    )
    if last_check_times:
        contract.last_check_times = last_check_times
    return contract


@pytest.mark.requirement("3D-FR-044")
def test_build_context_basic() -> None:
    """Test basic context fields are present."""
    registered_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    contract = _make_contract(
        contract_name="orders_v1",
        contract_version="2.0.0",
        registered_at=registered_at,
    )

    context = build_root_cause_context(contract)

    assert context["contract_name"] == "orders_v1"
    assert context["contract_version"] == "2.0.0"
    assert context["registered_at"] == "2024-01-01T12:00:00+00:00"


@pytest.mark.requirement("3D-FR-044")
def test_build_context_with_history() -> None:
    """Test context includes history stats when provided."""
    contract = _make_contract()
    history = [
        {"status": "fail", "timestamp": "2024-01-01T10:00:00Z"},
        {"status": "pass", "timestamp": "2024-01-01T09:45:00Z"},
        {"status": "fail", "timestamp": "2024-01-01T09:30:00Z"},
    ]

    context = build_root_cause_context(contract, check_results_history=history)

    assert context["recent_check_count"] == "3"
    assert context["recent_failure_count"] == "2"
    assert context["last_check_status"] == "fail"


@pytest.mark.requirement("3D-FR-044")
def test_build_context_no_history() -> None:
    """Test context when history is None."""
    contract = _make_contract()

    context = build_root_cause_context(contract, check_results_history=None)

    assert "recent_check_count" not in context
    assert "recent_failure_count" not in context
    assert "last_check_status" not in context


@pytest.mark.requirement("3D-FR-044")
def test_build_context_all_values_are_strings() -> None:
    """Test all metadata values are strings."""
    contract = _make_contract(
        connection_config={"catalog": "polaris"},
    )
    history = [
        {"status": "pass", "timestamp": "2024-01-01T10:00:00Z"},
    ]

    context = build_root_cause_context(contract, check_results_history=history)

    # All values must be str (ContractViolationEvent.metadata is dict[str, str])
    for key, value in context.items():
        assert isinstance(value, str), f"Value for {key} is not a string: {type(value)}"


@pytest.mark.requirement("3D-FR-044")
def test_build_context_with_last_check_times() -> None:
    """Test last_check_times are serialized as JSON string."""
    check_time_1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    check_time_2 = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    contract = _make_contract(
        last_check_times={
            "freshness": check_time_1,
            "schema_drift": check_time_2,
        }
    )

    context = build_root_cause_context(contract)

    # Should be JSON string
    last_check_times_str = context["last_check_times"]
    assert isinstance(last_check_times_str, str)

    # Parse and verify
    parsed = json.loads(last_check_times_str)
    assert parsed["freshness"] == "2024-01-01T10:00:00+00:00"
    assert parsed["schema_drift"] == "2024-01-01T11:00:00+00:00"


@pytest.mark.requirement("3D-FR-044")
def test_build_context_connection_catalog() -> None:
    """Test connection catalog is included in metadata."""
    contract = _make_contract(
        connection_config={
            "catalog": "polaris",
            "warehouse": "warehouse",
        }
    )

    context = build_root_cause_context(contract)

    assert context["connection_catalog"] == "polaris"


@pytest.mark.requirement("3D-FR-044")
def test_build_context_connection_catalog_missing() -> None:
    """Test connection catalog defaults to 'unknown' when missing."""
    contract = _make_contract(connection_config={"warehouse": "warehouse"})

    context = build_root_cause_context(contract)

    assert context["connection_catalog"] == "unknown"
