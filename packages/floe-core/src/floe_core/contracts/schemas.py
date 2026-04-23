"""Machine-readable output contracts for CLI and adapter payloads."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from floe_core.contracts.errors import ContractViolationError


class MachineOutputName(str, Enum):
    """Registered machine-readable output payloads."""

    RBAC_AUDIT = "rbac.audit"
    RBAC_DIFF = "rbac.diff"
    NETWORK_AUDIT = "network.audit"
    NETWORK_DIFF = "network.diff"


class JsonOutputContract(BaseModel):
    """Stable contract for a JSON payload emitted by a CLI or adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: MachineOutputName = Field(..., description="Canonical output contract name")
    required_keys: tuple[str, ...] = Field(..., description="Keys that must be present")
    stable_keys: tuple[str, ...] = Field(..., description="Keys consumers may rely on")

    def validate_payload(self, payload: dict[str, Any]) -> None:
        """Validate a payload against the contract.

        Args:
            payload: JSON-ready dictionary to validate.

        Raises:
            ContractViolationError: If a required key is absent.
        """
        missing = [key for key in self.required_keys if key not in payload]
        if missing:
            missing_text = ", ".join(missing)
            raise ContractViolationError(
                f"{self.name.value} output missing required keys: {missing_text}"
            )


_CONTRACTS: dict[MachineOutputName, JsonOutputContract] = {
    MachineOutputName.RBAC_AUDIT: JsonOutputContract(
        name=MachineOutputName.RBAC_AUDIT,
        required_keys=(
            "generated_at",
            "cluster_name",
            "namespaces",
            "service_accounts",
            "findings",
            "total_service_accounts",
            "total_roles",
            "total_role_bindings",
            "floe_managed_count",
        ),
        stable_keys=("generated_at", "cluster_name", "findings"),
    ),
    MachineOutputName.RBAC_DIFF: JsonOutputContract(
        name=MachineOutputName.RBAC_DIFF,
        required_keys=(
            "generated_at",
            "expected_source",
            "actual_source",
            "diffs",
            "added_count",
            "removed_count",
            "modified_count",
        ),
        stable_keys=("generated_at", "expected_source", "actual_source", "diffs"),
    ),
    MachineOutputName.NETWORK_AUDIT: JsonOutputContract(
        name=MachineOutputName.NETWORK_AUDIT,
        required_keys=("findings", "namespaces", "policies", "summary"),
        stable_keys=("namespaces", "policies", "findings", "summary"),
    ),
    MachineOutputName.NETWORK_DIFF: JsonOutputContract(
        name=MachineOutputName.NETWORK_DIFF,
        required_keys=("expected", "actual", "diffs", "summary"),
        stable_keys=("diffs", "summary"),
    ),
}


def contract_for_output(name: MachineOutputName) -> JsonOutputContract:
    """Return the machine-output contract for a registered payload."""
    return _CONTRACTS[name]


def validate_machine_output(name: MachineOutputName, payload: dict[str, Any]) -> None:
    """Validate a JSON-ready output payload against its contract."""
    contract_for_output(name).validate_payload(payload)
