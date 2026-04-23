"""Tests for runtime contract enums."""

from __future__ import annotations

import pytest


def test_oci_auth_type_values_are_canonical() -> None:
    """OCI auth modes are contract-owned and have no stale NONE alias."""
    from floe_core.contracts.runtime import OciAuthType, enum_values

    assert enum_values(OciAuthType) == (
        "anonymous",
        "basic",
        "token",
        "aws-irsa",
        "azure-managed-identity",
        "gcp-workload-identity",
    )
    assert not hasattr(OciAuthType, "NONE")


def test_oci_schema_reuses_runtime_contract_enum() -> None:
    """The legacy schema import path exposes the contract-owned enum."""
    from floe_core.contracts.runtime import OciAuthType
    from floe_core.schemas.oci import AuthType

    assert AuthType is OciAuthType
    assert AuthType.ANONYMOUS.value == "anonymous"


def test_invalid_contract_enum_name_has_clear_error() -> None:
    """Runtime contract lookup fails with a contract-specific error."""
    from floe_core.contracts.errors import ContractViolationError
    from floe_core.contracts.runtime import runtime_enum

    with pytest.raises(ContractViolationError, match="Unknown runtime enum"):
        runtime_enum("missing.enum")
