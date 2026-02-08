"""OpenLineage event emission for contract violations.

Epic 3D (Contract Monitoring) - Task T028
Requirements: FR-030, FR-031, FR-035

This module creates OpenLineage RunEvents when contract violations occur,
enabling lineage tracking and integration with OpenLineage-compatible systems.

The contract violation facet follows the schema defined in:
specs/3d-contract-monitoring/contracts/contract-violation-facet.json
"""

from __future__ import annotations

import uuid
from typing import Any

from floe_core.contracts.monitoring.violations import ContractViolationEvent


def create_violation_run_event(violation: ContractViolationEvent) -> dict[str, Any]:
    """Create an OpenLineage RunEvent for a contract violation.

    Args:
        violation: The contract violation event to emit

    Returns:
        OpenLineage RunEvent dictionary with FAIL event type and contract
        violation facet

    Examples:
        >>> violation = ContractViolationEvent(
        ...     contract_name="customers_v2",
        ...     contract_version="2.1.0",
        ...     violation_type=ViolationType.COLUMN_REMOVED,
        ...     severity=Severity.CRITICAL,
        ...     message="Column 'email' removed",
        ...     check_duration_seconds=0.123,
        ...     affected_consumers=["analytics_team"]
        ... )
        >>> event = create_violation_run_event(violation)
        >>> event["eventType"]
        'FAIL'
        >>> event["job"]["namespace"]
        'floe.contract_monitor'
    """
    # Format timestamp as ISO 8601 with Z suffix (not +00:00)
    event_time = violation.timestamp.isoformat().replace("+00:00", "Z")

    return {
        "eventType": "FAIL",
        "eventTime": event_time,
        "run": {
            "runId": str(uuid.uuid4()),
            "facets": {"contractViolation": build_contract_violation_facet(violation)},
        },
        "job": {
            "namespace": "floe.contract_monitor",
            "name": f"{violation.contract_name}.{violation.violation_type.value}",
        },
        "producer": "https://github.com/obsidian-owl/floe",
        "inputs": [],
        "outputs": [],
    }


def build_contract_violation_facet(
    violation: ContractViolationEvent,
) -> dict[str, Any]:
    """Build the contractViolation facet for an OpenLineage RunEvent.

    The facet uses camelCase field names to comply with OpenLineage conventions.

    Args:
        violation: The contract violation event

    Returns:
        Dictionary containing the contract violation facet with camelCase keys

    Examples:
        >>> violation = ContractViolationEvent(
        ...     contract_name="customers_v2",
        ...     contract_version="2.1.0",
        ...     violation_type=ViolationType.COLUMN_REMOVED,
        ...     severity=Severity.CRITICAL,
        ...     message="Column 'email' removed",
        ...     check_duration_seconds=0.123,
        ...     affected_consumers=["analytics_team"],
        ...     element="email"
        ... )
        >>> facet = build_contract_violation_facet(violation)
        >>> facet["contractName"]
        'customers_v2'
        >>> facet["violationType"]
        'column_removed'
    """
    facet: dict[str, Any] = {
        "_producer": "https://github.com/obsidian-owl/floe",
        "_schemaURL": "https://raw.githubusercontent.com/obsidian-owl/floe/main/specs/3d-contract-monitoring/contracts/contract-violation-facet.json",
        "contractName": violation.contract_name,
        "contractVersion": violation.contract_version,
        "violationType": violation.violation_type.value,
        "severity": violation.severity.value,
        "message": violation.message,
        "checkDurationSeconds": violation.check_duration_seconds,
        "affectedConsumers": violation.affected_consumers,
    }

    # Include optional fields even if None
    facet["element"] = violation.element
    facet["expectedValue"] = violation.expected_value
    facet["actualValue"] = violation.actual_value

    return facet
