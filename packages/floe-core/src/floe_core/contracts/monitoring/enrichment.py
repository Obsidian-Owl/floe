"""Violation enrichment — consumer impact and root cause context.

This module provides enrichment functions to populate ContractViolationEvent
with consumer impact analysis and root cause context for debugging.

Functions:
- resolve_affected_consumers: Extract downstream consumers from contract metadata
- build_root_cause_context: Build metadata dict for root cause analysis

Tasks: T073, T075 (Epic 3D)
Requirements: FR-043, FR-044
"""

from __future__ import annotations

import json
from typing import Any

from floe_core.contracts.monitoring.config import RegisteredContract


def resolve_affected_consumers(contract: RegisteredContract) -> list[str]:
    """Resolve affected downstream consumers from contract metadata.

    Extracts consumer names from contract_data to populate the
    ContractViolationEvent.affected_consumers field. Checks multiple
    possible locations for consumer metadata:
    - contract_data["consumers"]
    - contract_data["downstream"]["consumers"]

    Args:
        contract: The registered contract to analyze.

    Returns:
        Deduplicated, sorted list of consumer names. Empty list if no
        consumers found.

    Example:
        >>> contract = RegisteredContract(
        ...     contract_name="orders_v1",
        ...     contract_version="1.0.0",
        ...     contract_data={"consumers": ["analytics", "billing"]},
        ...     connection_config={},
        ...     registered_at=datetime.now(tz=timezone.utc),
        ... )
        >>> resolve_affected_consumers(contract)
        ['analytics', 'billing']
    """
    consumers: set[str] = set()

    # Check direct consumers key
    direct_consumers = contract.contract_data.get("consumers", [])
    if isinstance(direct_consumers, list):
        consumers.update(str(c) for c in direct_consumers)

    # Check downstream.consumers alternative location
    downstream = contract.contract_data.get("downstream", {})
    if isinstance(downstream, dict):
        downstream_consumers = downstream.get("consumers", [])
        if isinstance(downstream_consumers, list):
            consumers.update(str(c) for c in downstream_consumers)

    return sorted(consumers)


def build_root_cause_context(
    contract: RegisteredContract,
    check_results_history: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Build metadata dictionary for root cause analysis context.

    Populates ContractViolationEvent.metadata with contextual information
    to aid in root cause analysis and debugging:
    - Contract identification (name, version, registered_at)
    - Last check execution times
    - Recent check history stats (if provided)
    - Connection configuration details

    All values are converted to strings to match the dict[str, str] type
    of ContractViolationEvent.metadata.

    Args:
        contract: The registered contract to extract context from.
        check_results_history: Optional list of recent check results with
            "status" and "timestamp" fields. Used to calculate recent failure
            rates and patterns.

    Returns:
        Dictionary of metadata key-value pairs (all strings).

    Example:
        >>> contract = RegisteredContract(...)
        >>> history = [
        ...     {"status": "fail", "timestamp": "2024-01-01T10:00:00Z"},
        ...     {"status": "pass", "timestamp": "2024-01-01T09:45:00Z"},
        ... ]
        >>> context = build_root_cause_context(contract, history)
        >>> context["contract_name"]
        'orders_v1'
        >>> context["recent_check_count"]
        '2'
    """
    metadata: dict[str, str] = {}

    # Basic contract identification
    metadata["contract_name"] = contract.contract_name
    metadata["contract_version"] = contract.contract_version
    metadata["registered_at"] = contract.registered_at.isoformat()

    # Serialize last check times
    last_check_times_serialized: dict[str, str] = {}
    for check_type, timestamp in contract.last_check_times.items():
        last_check_times_serialized[check_type] = timestamp.isoformat()
    metadata["last_check_times"] = json.dumps(last_check_times_serialized)

    # Recent check history stats
    if check_results_history:
        metadata["recent_check_count"] = str(len(check_results_history))

        failure_count = sum(1 for result in check_results_history if result.get("status") == "fail")
        metadata["recent_failure_count"] = str(failure_count)

        # Most recent check status (first in list assumed to be most recent)
        if check_results_history:
            metadata["last_check_status"] = str(check_results_history[0].get("status", "unknown"))

    # Connection configuration details
    catalog = contract.connection_config.get("catalog", "unknown")
    metadata["connection_catalog"] = str(catalog)

    return metadata
