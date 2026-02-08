"""Unit tests for consumer impact analysis.

Tests the resolve_affected_consumers function that extracts downstream
consumer names from contract metadata.

Task: T072 (Epic 3D)
Requirement: 3D-FR-043
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from floe_core.contracts.monitoring.config import RegisteredContract
from floe_core.contracts.monitoring.enrichment import resolve_affected_consumers


def _make_contract(
    *,
    contract_name: str = "test_contract",
    contract_version: str = "1.0.0",
    contract_data: dict[str, Any] | None = None,
    connection_config: dict[str, Any] | None = None,
) -> RegisteredContract:
    """Create a test RegisteredContract instance.

    Args:
        contract_name: Name of the contract.
        contract_version: Version of the contract.
        contract_data: Contract metadata (defaults to empty dict).
        connection_config: Connection config (defaults to empty dict).

    Returns:
        RegisteredContract instance for testing.
    """
    return RegisteredContract(
        contract_name=contract_name,
        contract_version=contract_version,
        contract_data=contract_data or {},
        connection_config=connection_config or {},
        registered_at=datetime.now(tz=timezone.utc),
    )


@pytest.mark.requirement("3D-FR-043")
def test_resolve_consumers_from_contract_data() -> None:
    """Test consumer resolution from contract_data['consumers']."""
    contract = _make_contract(
        contract_data={
            "consumers": ["analytics", "billing", "reporting"],
        }
    )

    consumers = resolve_affected_consumers(contract)

    assert consumers == ["analytics", "billing", "reporting"]


@pytest.mark.requirement("3D-FR-043")
def test_resolve_consumers_from_downstream() -> None:
    """Test consumer resolution from contract_data['downstream']['consumers']."""
    contract = _make_contract(
        contract_data={
            "downstream": {
                "consumers": ["warehouse", "ml_pipeline"],
            }
        }
    )

    consumers = resolve_affected_consumers(contract)

    assert consumers == ["ml_pipeline", "warehouse"]


@pytest.mark.requirement("3D-FR-043")
def test_resolve_consumers_empty() -> None:
    """Test consumer resolution when no consumers key exists."""
    contract = _make_contract(
        contract_data={
            "apiVersion": "v3.1.0",
            "kind": "DataContract",
        }
    )

    consumers = resolve_affected_consumers(contract)

    assert consumers == []


@pytest.mark.requirement("3D-FR-043")
def test_resolve_consumers_deduplicated() -> None:
    """Test consumer resolution removes duplicates."""
    contract = _make_contract(
        contract_data={
            "consumers": ["analytics", "billing", "analytics"],
            "downstream": {
                "consumers": ["billing", "reporting"],
            },
        }
    )

    consumers = resolve_affected_consumers(contract)

    # Should have 3 unique consumers
    assert len(consumers) == 3
    assert set(consumers) == {"analytics", "billing", "reporting"}


@pytest.mark.requirement("3D-FR-043")
def test_resolve_consumers_sorted() -> None:
    """Test consumer resolution returns sorted list."""
    contract = _make_contract(
        contract_data={
            "consumers": ["zebra", "alpha", "middle"],
        }
    )

    consumers = resolve_affected_consumers(contract)

    assert consumers == ["alpha", "middle", "zebra"]
