"""Tests for machine-readable output contracts."""

from __future__ import annotations

import pytest


def test_rbac_audit_contract_requires_findings_key() -> None:
    """RBAC audit JSON must keep the stable findings key."""
    from floe_core.contracts.schemas import MachineOutputName, contract_for_output

    contract = contract_for_output(MachineOutputName.RBAC_AUDIT)

    assert "findings" in contract.required_keys
    assert "cluster_name" in contract.required_keys


def test_rbac_diff_contract_requires_diffs_key() -> None:
    """RBAC diff JSON must keep the stable diffs key."""
    from floe_core.contracts.schemas import MachineOutputName, contract_for_output

    contract = contract_for_output(MachineOutputName.RBAC_DIFF)

    assert "diffs" in contract.required_keys
    assert "expected_source" in contract.required_keys


def test_contract_validation_reports_missing_keys() -> None:
    """Machine-output validation reports the exact missing keys."""
    from floe_core.contracts.errors import ContractViolationError
    from floe_core.contracts.schemas import MachineOutputName, validate_machine_output

    with pytest.raises(ContractViolationError, match="missing required keys: findings"):
        validate_machine_output(MachineOutputName.NETWORK_AUDIT, {"summary": {}})
