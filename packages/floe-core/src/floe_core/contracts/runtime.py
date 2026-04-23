"""Runtime contracts shared across packages and test boundaries."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from floe_core.contracts.errors import ContractViolationError

EnumT = TypeVar("EnumT", bound=Enum)


class OciAuthType(str, Enum):
    """Authentication modes supported by floe OCI registry integrations."""

    ANONYMOUS = "anonymous"
    BASIC = "basic"
    TOKEN = "token"
    AWS_IRSA = "aws-irsa"
    AZURE_MANAGED_IDENTITY = "azure-managed-identity"
    GCP_WORKLOAD_IDENTITY = "gcp-workload-identity"


_RUNTIME_ENUMS: dict[str, type[Enum]] = {
    "oci.auth_type": OciAuthType,
}


def enum_values(enum_type: type[EnumT]) -> tuple[str, ...]:
    """Return stable string values for a runtime enum."""
    return tuple(str(member.value) for member in enum_type)


def runtime_enum(name: str) -> type[Enum]:
    """Look up a runtime enum by canonical contract name.

    Args:
        name: Canonical runtime enum name, such as ``"oci.auth_type"``.

    Returns:
        Enum class registered for the name.

    Raises:
        ContractViolationError: If the enum name is not registered.
    """
    try:
        return _RUNTIME_ENUMS[name]
    except KeyError as exc:
        available = ", ".join(sorted(_RUNTIME_ENUMS))
        raise ContractViolationError(
            f"Unknown runtime enum {name!r}; available enums: {available}"
        ) from exc
