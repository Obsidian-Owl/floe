# Contract Layer Hard Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a broad, generation-first contract layer that makes shared service, execution, runtime, and machine-output facts canonical in `floe-core`.

**Architecture:** Add bounded contract domains under `floe_core.contracts`, then migrate consumers so charts, test fixtures, shell scripts, runtime schemas, and CLI JSON outputs consume contract-owned bindings. Split validation into contract, bootstrap, platform-blackbox, and developer-workflow boundaries so red builds classify cleanly.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, Click, Bash, Helm templates, Kubernetes-native test runners.

---

## Scope Check

This plan covers one connected migration: shared operational facts move into a generation-first contract layer, and existing consumers become adapters. The runtime enum, machine-output schema, topology, execution, chart, shell, and test-boundary changes are intentionally kept together because partial migration would leave two competing sources of truth alive.

## File Structure

Create contract domains in `packages/floe-core/src/floe_core/contracts/`:

- `errors.py`: contract-specific exception types used by all domains.
- `runtime.py`: runtime enum and constant contracts, starting with OCI auth modes.
- `schemas.py`: machine-readable output contract registry for JSON payloads.
- `topology.py`: canonical platform service identity, default ports, and Helm service-name rendering.
- `execution.py`: execution context model and service env binding generation.
- `emit.py`: CLI-style emitter for shell exports, service names, and Helm test-runner env fragments.

Modify existing consumers:

- `packages/floe-core/src/floe_core/contracts/__init__.py`: export the new contract layer without breaking existing ODCS contract generator imports.
- `packages/floe-core/src/floe_core/schemas/oci.py`: use the runtime contract enum as the public `AuthType`.
- `packages/floe-core/src/floe_core/cli/rbac/audit.py`: validate JSON output against machine-output contracts.
- `packages/floe-core/src/floe_core/cli/rbac/diff.py`: validate JSON output against machine-output contracts.
- `packages/floe-core/src/floe_core/cli/network/audit.py`: validate JSON output against machine-output contracts.
- `packages/floe-core/src/floe_core/cli/network/diff.py`: validate JSON output against machine-output contracts.
- `testing/fixtures/services.py`: derive service ports and hosts from topology and execution contracts.
- `testing/ci/common.sh`: ask `floe_core.contracts.emit` for canonical defaults and service names.
- `testing/ci/test-e2e.sh`: remove locally authored service-name precomputation.
- `charts/floe-platform/templates/tests/_contract-env.generated.tpl`: generated Helm env helper.
- `charts/floe-platform/templates/tests/_test-job.tpl`: include the generated env helper instead of maintaining its own env table.
- `pyproject.toml`: add validation-boundary markers and include contract tests in top-level test flow.
- `Makefile`: wire `test-contract` into normal validation.
- `scripts/check-architecture-drift`: block newly duplicated service literals outside contract-owned files.

Add and modify tests:

- `packages/floe-core/tests/unit/contracts/test_runtime_contracts.py`
- `packages/floe-core/tests/unit/contracts/test_machine_output_contracts.py`
- `packages/floe-core/tests/unit/contracts/test_topology_contracts.py`
- `packages/floe-core/tests/unit/contracts/test_execution_contracts.py`
- `packages/floe-core/tests/unit/contracts/test_emit_contracts.py`
- `tests/unit/test_e2e_fixture_wiring.py`
- `tests/unit/test_e2e_runner_chart_contract.py`
- `tests/unit/test_validation_boundary_markers.py`
- `tests/contract/test_platform_contract_generated_bindings.py`
- `packages/floe-core/tests/integration/oci/test_lock_workflow.py`

## Tasks

### Task 1: Runtime Contract And OCI Auth Hard Reset

**Files:**

- Create: `packages/floe-core/src/floe_core/contracts/errors.py`
- Create: `packages/floe-core/src/floe_core/contracts/runtime.py`
- Modify: `packages/floe-core/src/floe_core/contracts/__init__.py`
- Modify: `packages/floe-core/src/floe_core/schemas/oci.py`
- Modify: `packages/floe-core/tests/integration/oci/test_lock_workflow.py`
- Test: `packages/floe-core/tests/unit/contracts/test_runtime_contracts.py`

- [ ] **Step 1: Write the failing runtime contract tests**

Create `packages/floe-core/tests/unit/contracts/test_runtime_contracts.py`:

```python
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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/contracts/test_runtime_contracts.py -v
```

Expected: FAIL because `floe_core.contracts.runtime` and `floe_core.contracts.errors` do not exist.

- [ ] **Step 3: Add contract-specific exceptions**

Create `packages/floe-core/src/floe_core/contracts/errors.py`:

```python
"""Contract-layer exception types.

These errors make contract, adapter, and execution-context failures distinct
from generic runtime exceptions.
"""

from __future__ import annotations


class ContractError(ValueError):
    """Base class for contract-layer failures."""


class ContractGenerationError(ContractError):
    """Raised when canonical contract facts cannot produce valid bindings."""


class ContractViolationError(ContractError):
    """Raised when a consumer violates a canonical contract."""


class ExecutionContextMismatch(ContractViolationError):
    """Raised when code runs under an execution context it was not written for."""
```

- [ ] **Step 4: Add the runtime contract domain**

Create `packages/floe-core/src/floe_core/contracts/runtime.py`:

```python
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
```

- [ ] **Step 5: Export runtime contract symbols**

Modify `packages/floe-core/src/floe_core/contracts/__init__.py` so the import section and `__all__` include the new contract types while preserving `ContractGenerator`:

```python
from floe_core.contracts.errors import (
    ContractError,
    ContractGenerationError,
    ContractViolationError,
    ExecutionContextMismatch,
)
from floe_core.contracts.generator import ContractGenerator
from floe_core.contracts.runtime import OciAuthType, enum_values, runtime_enum

__all__ = [
    "ContractError",
    "ContractGenerationError",
    "ContractGenerator",
    "ContractViolationError",
    "ExecutionContextMismatch",
    "OciAuthType",
    "enum_values",
    "runtime_enum",
]
```

- [ ] **Step 6: Make the OCI schema consume the runtime contract**

Modify `packages/floe-core/src/floe_core/schemas/oci.py`:

1. Add this import near the other `floe_core` imports:

```python
from floe_core.contracts.runtime import OciAuthType as AuthType
```

2. Delete the local `class AuthType(str, Enum):` block.

The module must still expose `AuthType` from `floe_core.schemas.oci`, but the object must be `floe_core.contracts.runtime.OciAuthType`.

- [ ] **Step 7: Hard-reset stale integration test auth usage**

Modify `packages/floe-core/tests/integration/oci/test_lock_workflow.py`:

1. Replace every `RegistryAuth(auth_type=AuthType.NONE)` call with:

```python
RegistryAuth(type=AuthType.ANONYMOUS)
```

2. Verify there are no remaining stale auth references:

```bash
rg -n "AuthType\\.NONE|auth_type=AuthType" packages/floe-core/tests/integration/oci/test_lock_workflow.py
```

Expected: no output.

- [ ] **Step 8: Run runtime and OCI schema tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/contracts/test_runtime_contracts.py packages/floe-core/tests/unit/oci/test_auth.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit runtime contract migration**

Run:

```bash
git add \
  packages/floe-core/src/floe_core/contracts/__init__.py \
  packages/floe-core/src/floe_core/contracts/errors.py \
  packages/floe-core/src/floe_core/contracts/runtime.py \
  packages/floe-core/src/floe_core/schemas/oci.py \
  packages/floe-core/tests/integration/oci/test_lock_workflow.py \
  packages/floe-core/tests/unit/contracts/test_runtime_contracts.py
git commit -m "feat: add runtime contract domain"
```

### Task 2: Machine-Output Schema Contracts

**Files:**

- Create: `packages/floe-core/src/floe_core/contracts/schemas.py`
- Modify: `packages/floe-core/src/floe_core/contracts/__init__.py`
- Modify: `packages/floe-core/src/floe_core/cli/rbac/audit.py`
- Modify: `packages/floe-core/src/floe_core/cli/rbac/diff.py`
- Modify: `packages/floe-core/src/floe_core/cli/network/audit.py`
- Modify: `packages/floe-core/src/floe_core/cli/network/diff.py`
- Test: `packages/floe-core/tests/unit/contracts/test_machine_output_contracts.py`
- Test: `packages/floe-core/tests/unit/cli/test_cli_rbac_audit.py`
- Test: `packages/floe-core/tests/unit/cli/test_rbac_diff.py`
- Test: `packages/floe-core/tests/unit/cli/network/test_audit_command.py`
- Test: `packages/floe-core/tests/unit/cli/network/test_diff.py`

- [ ] **Step 1: Write failing machine-output contract tests**

Create `packages/floe-core/tests/unit/contracts/test_machine_output_contracts.py`:

```python
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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/contracts/test_machine_output_contracts.py -v
```

Expected: FAIL because `floe_core.contracts.schemas` does not exist.

- [ ] **Step 3: Add the machine-output contract domain**

Create `packages/floe-core/src/floe_core/contracts/schemas.py`:

```python
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
        required_keys=("namespaces", "policies", "findings", "summary"),
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
```

- [ ] **Step 4: Export schema contract symbols**

Modify `packages/floe-core/src/floe_core/contracts/__init__.py`:

```python
from floe_core.contracts.schemas import (
    JsonOutputContract,
    MachineOutputName,
    contract_for_output,
    validate_machine_output,
)
```

Add these names to `__all__`:

```python
"JsonOutputContract",
"MachineOutputName",
"contract_for_output",
"validate_machine_output",
```

- [ ] **Step 5: Validate RBAC audit JSON output before printing**

Modify `packages/floe-core/src/floe_core/cli/rbac/audit.py`:

1. Add imports:

```python
import json

from floe_core.contracts.schemas import MachineOutputName, validate_machine_output
```

2. Replace the JSON branch in `_output_report` with:

```python
    if output_format == "json":
        payload = report.model_dump(mode="json")
        validate_machine_output(MachineOutputName.RBAC_AUDIT, payload)
        click.echo(json.dumps(payload, indent=2))
        return
```

- [ ] **Step 6: Validate RBAC diff JSON output before printing**

Modify `packages/floe-core/src/floe_core/cli/rbac/diff.py`:

1. Add imports:

```python
import json

from floe_core.contracts.schemas import MachineOutputName, validate_machine_output
```

2. Replace the JSON output branch with:

```python
        if output_format == "json":
            payload = diff_result.model_dump(mode="json")
            validate_machine_output(MachineOutputName.RBAC_DIFF, payload)
            click.echo(json.dumps(payload, indent=2))
        else:
            _output_diff_as_text(diff_result)
```

- [ ] **Step 7: Validate network audit JSON output before printing**

Modify `packages/floe-core/src/floe_core/cli/network/audit.py`:

1. Add import:

```python
from floe_core.contracts.schemas import MachineOutputName, validate_machine_output
```

2. Replace the JSON branch in `_output_report` with:

```python
    if output_format == "json":
        import json

        validate_machine_output(MachineOutputName.NETWORK_AUDIT, report)
        click.echo(json.dumps(report, indent=2))
        return
```

- [ ] **Step 8: Normalize network diff JSON shape and validate it**

Modify `packages/floe-core/src/floe_core/cli/network/diff.py`:

1. Add import:

```python
from floe_core.contracts.schemas import MachineOutputName, validate_machine_output
```

2. In the JSON output branch, build a stable payload:

```python
        if output_format.lower() == "json":
            import json

            payload = {
                "expected": expected_policies,
                "actual": deployed_policies,
                "diffs": diff_result.get("diffs", []),
                "summary": diff_result.get("summary", {}),
            }
            validate_machine_output(MachineOutputName.NETWORK_DIFF, payload)
            click.echo(json.dumps(payload, indent=2))
        else:
            _output_diff_as_text(diff_result)
```

- [ ] **Step 9: Run output contract tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/contracts/test_machine_output_contracts.py \
  packages/floe-core/tests/unit/cli/test_cli_rbac_audit.py \
  packages/floe-core/tests/unit/cli/test_rbac_diff.py \
  packages/floe-core/tests/unit/cli/network/test_audit_command.py \
  packages/floe-core/tests/unit/cli/network/test_diff.py \
  -v
```

Expected: PASS. Update any failing CLI JSON assertion in the listed tests so it asserts contract-owned keys from `MachineOutputName` payloads rather than locally invented keys.

- [ ] **Step 10: Commit machine-output contracts**

Run:

```bash
git add \
  packages/floe-core/src/floe_core/contracts/__init__.py \
  packages/floe-core/src/floe_core/contracts/schemas.py \
  packages/floe-core/src/floe_core/cli/rbac/audit.py \
  packages/floe-core/src/floe_core/cli/rbac/diff.py \
  packages/floe-core/src/floe_core/cli/network/audit.py \
  packages/floe-core/src/floe_core/cli/network/diff.py \
  packages/floe-core/tests/unit/contracts/test_machine_output_contracts.py \
  packages/floe-core/tests/unit/cli/test_cli_rbac_audit.py \
  packages/floe-core/tests/unit/cli/test_rbac_diff.py \
  packages/floe-core/tests/unit/cli/network/test_audit_command.py \
  packages/floe-core/tests/unit/cli/network/test_diff.py
git commit -m "feat: add machine output contracts"
```

### Task 3: Topology And Execution Contracts

**Files:**

- Create: `packages/floe-core/src/floe_core/contracts/topology.py`
- Create: `packages/floe-core/src/floe_core/contracts/execution.py`
- Modify: `packages/floe-core/src/floe_core/contracts/__init__.py`
- Test: `packages/floe-core/tests/unit/contracts/test_topology_contracts.py`
- Test: `packages/floe-core/tests/unit/contracts/test_execution_contracts.py`

- [ ] **Step 1: Write failing topology tests**

Create `packages/floe-core/tests/unit/contracts/test_topology_contracts.py`:

```python
"""Tests for platform topology contracts."""

from __future__ import annotations


def test_platform_services_include_current_e2e_dependencies() -> None:
    """The topology contract owns service identities used by E2E tests."""
    from floe_core.contracts.topology import ComponentId, service_contract, test_runner_services

    assert service_contract(ComponentId.POLARIS).default_port == 8181
    assert service_contract(ComponentId.POLARIS_MANAGEMENT).default_port == 8182
    assert service_contract(ComponentId.MINIO).default_port == 9000
    assert service_contract(ComponentId.DAGSTER_WEBSERVER).default_port == 3000
    assert service_contract(ComponentId.POSTGRESQL).default_port == 5432
    assert ComponentId.OCI_REGISTRY not in {service.component_id for service in test_runner_services()}


def test_service_names_are_rendered_from_release_name() -> None:
    """Chart and shell consumers must not hand-author service-name formulas."""
    from floe_core.contracts.topology import ComponentId, render_service_name

    assert render_service_name(ComponentId.POLARIS, release_name="floe-platform") == (
        "floe-platform-polaris"
    )
    assert render_service_name(ComponentId.DAGSTER_WEBSERVER, release_name="demo") == (
        "demo-dagster-webserver"
    )
```

- [ ] **Step 2: Write failing execution tests**

Create `packages/floe-core/tests/unit/contracts/test_execution_contracts.py`:

```python
"""Tests for execution context contracts."""

from __future__ import annotations

import pytest


def test_in_cluster_bindings_use_service_names() -> None:
    """In-cluster bindings use Kubernetes service DNS names."""
    from floe_core.contracts.execution import ExecutionContext, service_binding
    from floe_core.contracts.topology import ComponentId

    binding = service_binding(
        ComponentId.POLARIS,
        ExecutionContext.IN_CLUSTER,
        release_name="floe-platform",
        namespace="floe-test",
    )

    assert binding.host == "floe-platform-polaris"
    assert binding.port == 8181
    assert binding.env == {"POLARIS_HOST": "floe-platform-polaris", "POLARIS_PORT": "8181"}


def test_host_bindings_use_localhost_explicitly() -> None:
    """Host execution is explicit and does not rely on DNS probing."""
    from floe_core.contracts.execution import ExecutionContext, service_binding
    from floe_core.contracts.topology import ComponentId

    binding = service_binding(ComponentId.MINIO, ExecutionContext.HOST)

    assert binding.host == "localhost"
    assert binding.env == {"MINIO_HOST": "localhost", "MINIO_PORT": "9000"}


def test_unknown_execution_context_fails_as_contract_violation() -> None:
    """Invalid execution contexts fail before service helpers run."""
    from floe_core.contracts.errors import ExecutionContextMismatch
    from floe_core.contracts.execution import parse_execution_context

    with pytest.raises(ExecutionContextMismatch, match="Unknown execution context"):
        parse_execution_context("k8s")
```

- [ ] **Step 3: Run topology and execution tests and verify they fail**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/contracts/test_topology_contracts.py \
  packages/floe-core/tests/unit/contracts/test_execution_contracts.py \
  -v
```

Expected: FAIL because the topology and execution modules do not exist.

- [ ] **Step 4: Add topology contracts**

Create `packages/floe-core/src/floe_core/contracts/topology.py`:

```python
"""Canonical platform topology contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from floe_core.contracts.errors import ContractViolationError

DEFAULT_RELEASE_NAME = "floe-platform"
DEFAULT_NAMESPACE = "floe-test"


class ComponentId(str, Enum):
    """Canonical platform components shared across charts, scripts, and tests."""

    DAGSTER_WEBSERVER = "dagster-webserver"
    POLARIS = "polaris"
    POLARIS_MANAGEMENT = "polaris-management"
    MINIO = "minio"
    MINIO_CONSOLE = "minio-console"
    POSTGRESQL = "postgresql"
    JAEGER_QUERY = "jaeger-query"
    OTEL_COLLECTOR_GRPC = "otel-collector-grpc"
    OTEL_COLLECTOR_HTTP = "otel-collector-http"
    MARQUEZ = "marquez"
    OCI_REGISTRY = "oci-registry"
    OCI_REGISTRY_AUTH = "oci-registry-auth"


class ServiceContract(BaseModel):
    """Canonical identity and port contract for a platform service."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: ComponentId = Field(..., description="Canonical component identifier")
    chart_component: str = Field(..., description="Helm release suffix for service name")
    default_port: int = Field(..., ge=1, le=65535, description="Default service port")
    host_env_var: str = Field(..., description="Environment variable for service host")
    port_env_var: str = Field(..., description="Environment variable for service port")
    readiness_path: str | None = Field(default=None, description="HTTP readiness path")
    expose_to_test_runner: bool = Field(
        default=True,
        description="Whether generated Helm test-runner env should expose this service",
    )

    @property
    def short_name(self) -> str:
        """Return the canonical short service name used by Python helpers."""
        return self.component_id.value


_SERVICES: tuple[ServiceContract, ...] = (
    ServiceContract(
        component_id=ComponentId.DAGSTER_WEBSERVER,
        chart_component="dagster-webserver",
        default_port=3000,
        host_env_var="DAGSTER_WEBSERVER_HOST",
        port_env_var="DAGSTER_WEBSERVER_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.POLARIS,
        chart_component="polaris",
        default_port=8181,
        host_env_var="POLARIS_HOST",
        port_env_var="POLARIS_PORT",
        readiness_path="/api/catalog/v1/config",
    ),
    ServiceContract(
        component_id=ComponentId.POLARIS_MANAGEMENT,
        chart_component="polaris",
        default_port=8182,
        host_env_var="POLARIS_MANAGEMENT_HOST",
        port_env_var="POLARIS_MANAGEMENT_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.MINIO,
        chart_component="minio",
        default_port=9000,
        host_env_var="MINIO_HOST",
        port_env_var="MINIO_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.MINIO_CONSOLE,
        chart_component="minio",
        default_port=9001,
        host_env_var="MINIO_CONSOLE_HOST",
        port_env_var="MINIO_CONSOLE_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.POSTGRESQL,
        chart_component="postgresql",
        default_port=5432,
        host_env_var="POSTGRES_HOST",
        port_env_var="POSTGRES_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.JAEGER_QUERY,
        chart_component="jaeger-query",
        default_port=16686,
        host_env_var="JAEGER_QUERY_HOST",
        port_env_var="JAEGER_QUERY_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.OTEL_COLLECTOR_GRPC,
        chart_component="otel",
        default_port=4317,
        host_env_var="OTEL_COLLECTOR_GRPC_HOST",
        port_env_var="OTEL_COLLECTOR_GRPC_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.OTEL_COLLECTOR_HTTP,
        chart_component="otel",
        default_port=4318,
        host_env_var="OTEL_COLLECTOR_HTTP_HOST",
        port_env_var="OTEL_COLLECTOR_HTTP_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.MARQUEZ,
        chart_component="marquez",
        default_port=5000,
        host_env_var="MARQUEZ_HOST",
        port_env_var="MARQUEZ_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.OCI_REGISTRY,
        chart_component="oci-registry",
        default_port=5000,
        host_env_var="OCI_REGISTRY_HOST",
        port_env_var="OCI_REGISTRY_PORT",
        expose_to_test_runner=False,
    ),
    ServiceContract(
        component_id=ComponentId.OCI_REGISTRY_AUTH,
        chart_component="oci-registry-auth",
        default_port=5000,
        host_env_var="OCI_REGISTRY_AUTH_HOST",
        port_env_var="OCI_REGISTRY_AUTH_PORT",
        expose_to_test_runner=False,
    ),
)


def service_contracts() -> tuple[ServiceContract, ...]:
    """Return all canonical service contracts."""
    return _SERVICES


def test_runner_services() -> tuple[ServiceContract, ...]:
    """Return services exposed to the Helm test-runner environment."""
    return tuple(service for service in _SERVICES if service.expose_to_test_runner)


def service_contract(component_id: ComponentId) -> ServiceContract:
    """Return the service contract for a component."""
    for service in _SERVICES:
        if service.component_id is component_id:
            return service
    raise ContractViolationError(f"Unknown service component: {component_id.value}")


def service_contract_by_name(name: str) -> ServiceContract:
    """Return a service contract by canonical short name."""
    for service in _SERVICES:
        if service.short_name == name:
            return service
    known = ", ".join(sorted(service.short_name for service in _SERVICES))
    raise ContractViolationError(f"Unknown service {name!r}; known services: {known}")


def render_service_name(
    component_id: ComponentId,
    *,
    release_name: str = DEFAULT_RELEASE_NAME,
) -> str:
    """Render a Kubernetes service name from the canonical topology contract."""
    service = service_contract(component_id)
    return f"{release_name}-{service.chart_component}"
```

- [ ] **Step 5: Add execution contracts**

Create `packages/floe-core/src/floe_core/contracts/execution.py`:

```python
"""Execution-context contracts for platform consumers."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from floe_core.contracts.errors import ExecutionContextMismatch
from floe_core.contracts.topology import (
    DEFAULT_NAMESPACE,
    DEFAULT_RELEASE_NAME,
    ComponentId,
    render_service_name,
    service_contract,
    service_contracts,
)


class ExecutionContext(str, Enum):
    """Supported runtime contexts for generated service bindings."""

    IN_CLUSTER = "in-cluster"
    HOST = "host"
    DEVPOD = "devpod"
    DEMO = "demo"


class ServiceBinding(BaseModel):
    """Rendered service binding for one execution context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    component_id: ComponentId = Field(..., description="Canonical component")
    context: ExecutionContext = Field(..., description="Execution context")
    host: str = Field(..., description="Resolved host")
    port: int = Field(..., ge=1, le=65535, description="Resolved port")
    env: dict[str, str] = Field(..., description="Environment variables for consumers")


def parse_execution_context(raw: str | None) -> ExecutionContext:
    """Parse an execution context value.

    Args:
        raw: String value from environment or CLI input.

    Returns:
        ExecutionContext enum.

    Raises:
        ExecutionContextMismatch: If the value is missing or unknown.
    """
    if raw is None or raw.strip() == "":
        raise ExecutionContextMismatch(
            "Execution context is required; set FLOE_EXECUTION_CONTEXT to one of "
            "in-cluster, host, devpod, demo"
        )
    try:
        return ExecutionContext(raw)
    except ValueError as exc:
        allowed = ", ".join(context.value for context in ExecutionContext)
        raise ExecutionContextMismatch(
            f"Unknown execution context {raw!r}; allowed contexts: {allowed}"
        ) from exc


def service_binding(
    component_id: ComponentId,
    context: ExecutionContext,
    *,
    release_name: str = DEFAULT_RELEASE_NAME,
    namespace: str = DEFAULT_NAMESPACE,
) -> ServiceBinding:
    """Render one service binding for a specific execution context."""
    service = service_contract(component_id)
    if context is ExecutionContext.IN_CLUSTER:
        host = render_service_name(component_id, release_name=release_name)
    elif context in (ExecutionContext.HOST, ExecutionContext.DEVPOD, ExecutionContext.DEMO):
        host = "localhost"
    else:
        raise ExecutionContextMismatch(f"Unsupported execution context: {context.value}")

    env = {
        service.host_env_var: host,
        service.port_env_var: str(service.default_port),
    }
    return ServiceBinding(
        component_id=component_id,
        context=context,
        host=host,
        port=service.default_port,
        env=env,
    )


def service_bindings(
    context: ExecutionContext,
    *,
    release_name: str = DEFAULT_RELEASE_NAME,
    namespace: str = DEFAULT_NAMESPACE,
) -> tuple[ServiceBinding, ...]:
    """Render service bindings for every canonical platform service."""
    return tuple(
        service_binding(
            service.component_id,
            context,
            release_name=release_name,
            namespace=namespace,
        )
        for service in service_contracts()
    )
```

- [ ] **Step 6: Export topology and execution symbols**

Modify `packages/floe-core/src/floe_core/contracts/__init__.py`:

```python
from floe_core.contracts.execution import (
    ExecutionContext,
    ServiceBinding,
    parse_execution_context,
    service_binding,
    service_bindings,
)
from floe_core.contracts.topology import (
    DEFAULT_NAMESPACE,
    DEFAULT_RELEASE_NAME,
    ComponentId,
    ServiceContract,
    render_service_name,
    service_contract,
    service_contract_by_name,
    service_contracts,
    test_runner_services,
)
```

Add those names to `__all__`.

- [ ] **Step 7: Run topology and execution tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/contracts/test_topology_contracts.py \
  packages/floe-core/tests/unit/contracts/test_execution_contracts.py \
  -v
```

Expected: PASS.

- [ ] **Step 8: Commit topology and execution contracts**

Run:

```bash
git add \
  packages/floe-core/src/floe_core/contracts/__init__.py \
  packages/floe-core/src/floe_core/contracts/topology.py \
  packages/floe-core/src/floe_core/contracts/execution.py \
  packages/floe-core/tests/unit/contracts/test_topology_contracts.py \
  packages/floe-core/tests/unit/contracts/test_execution_contracts.py
git commit -m "feat: add topology and execution contracts"
```

### Task 4: Python Test Fixture Adapter Migration

**Files:**

- Modify: `testing/fixtures/services.py`
- Modify: `tests/unit/test_e2e_fixture_wiring.py`
- Test: `tests/unit/test_e2e_fixture_wiring.py`

- [ ] **Step 1: Add fixture tests that reject socket-based fallback**

Modify `tests/unit/test_e2e_fixture_wiring.py` and add:

```python
def test_service_default_ports_are_contract_derived() -> None:
    """E2E service defaults must be derived from topology contracts."""
    from floe_core.contracts.topology import service_contracts
    from testing.fixtures.services import SERVICE_DEFAULT_PORTS

    expected = {service.short_name: service.default_port for service in service_contracts()}

    assert SERVICE_DEFAULT_PORTS == expected


def test_service_endpoint_requires_explicit_execution_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service helpers must not silently probe DNS and fall back to localhost."""
    from floe_core.contracts.errors import ExecutionContextMismatch
    from testing.fixtures.services import ServiceEndpoint

    monkeypatch.delenv("FLOE_EXECUTION_CONTEXT", raising=False)
    monkeypatch.delenv("POLARIS_HOST", raising=False)

    endpoint = ServiceEndpoint("polaris")

    with pytest.raises(ExecutionContextMismatch, match="FLOE_EXECUTION_CONTEXT"):
        _ = endpoint.host


def test_service_endpoint_uses_contract_env_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    """ServiceEndpoint uses contract binding for in-cluster runtime."""
    from testing.fixtures.services import ServiceEndpoint

    monkeypatch.setenv("FLOE_EXECUTION_CONTEXT", "in-cluster")
    monkeypatch.setenv("FLOE_RELEASE_NAME", "floe-platform")

    endpoint = ServiceEndpoint("polaris")

    assert endpoint.host == "floe-platform-polaris"
    assert endpoint.port == 8181
    assert endpoint.url == "http://floe-platform-polaris:8181"
```

Ensure the file imports `pytest`:

```python
import pytest
```

- [ ] **Step 2: Run fixture tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_e2e_fixture_wiring.py -v
```

Expected: FAIL because `testing/fixtures/services.py` still owns `SERVICE_DEFAULT_PORTS` and still uses DNS probing.

- [ ] **Step 3: Replace fixture-owned service defaults**

Modify `testing/fixtures/services.py`:

1. Add imports:

```python
from floe_core.contracts.execution import parse_execution_context, service_binding
from floe_core.contracts.topology import (
    DEFAULT_NAMESPACE,
    DEFAULT_RELEASE_NAME,
    service_contract_by_name,
    service_contracts,
)
```

2. Replace the current hand-authored `SERVICE_DEFAULT_PORTS` dictionary with:

```python
SERVICE_DEFAULT_PORTS: dict[str, int] = {
    service.short_name: service.default_port for service in service_contracts()
}
```

- [ ] **Step 4: Replace socket-probing host resolution**

Modify `testing/fixtures/services.py`:

1. Delete the `import socket` line.

2. Replace `_get_effective_host` with:

```python
def _get_effective_host(service_name: str, namespace: str) -> str:
    """Determine the effective host for a service from execution contracts."""
    service = service_contract_by_name(service_name)
    env_key = service.host_env_var
    service_host = os.environ.get(env_key)
    if service_host:
        return service_host

    context = parse_execution_context(os.environ.get("FLOE_EXECUTION_CONTEXT"))
    release_name = os.environ.get("FLOE_RELEASE_NAME", DEFAULT_RELEASE_NAME)
    effective_namespace = namespace or os.environ.get("FLOE_NAMESPACE", DEFAULT_NAMESPACE)
    binding = service_binding(
        service.component_id,
        context,
        release_name=release_name,
        namespace=effective_namespace,
    )
    return binding.host
```

3. Delete `_can_resolve_host`.

- [ ] **Step 5: Update service fixture docstring**

Modify the environment-variable section at the top of `testing/fixtures/services.py` to read:

```python
Environment Variables:
    FLOE_EXECUTION_CONTEXT: Required execution context for generated bindings.
        Supported values: "in-cluster", "host", "devpod", "demo".
    FLOE_RELEASE_NAME: Helm release name for in-cluster service bindings.
    FLOE_NAMESPACE: Kubernetes namespace for generated bindings.
    {SERVICE}_HOST: Explicit host override for a contract-defined service.
```

- [ ] **Step 6: Run fixture adapter tests**

Run:

```bash
uv run pytest tests/unit/test_e2e_fixture_wiring.py -v
```

Expected: PASS.

- [ ] **Step 7: Run E2E conftest-focused tests**

Run:

```bash
uv run pytest tests/unit/test_e2e_runner_devpod_path.py tests/unit/test_e2e_runner_chart_contract.py -v
```

Expected: PASS. Replace any remaining `INTEGRATION_TEST_HOST` references in failing tests with `FLOE_EXECUTION_CONTEXT` and one of `in-cluster`, `host`, `devpod`, or `demo`.

- [ ] **Step 8: Commit Python fixture adapter migration**

Run:

```bash
git add testing/fixtures/services.py tests/unit/test_e2e_fixture_wiring.py
git commit -m "refactor: derive service fixtures from contracts"
```

### Task 5: Contract Emitter And Shell Adapter Migration

**Files:**

- Create: `packages/floe-core/src/floe_core/contracts/emit.py`
- Modify: `testing/ci/common.sh`
- Modify: `testing/ci/test-e2e.sh`
- Test: `packages/floe-core/tests/unit/contracts/test_emit_contracts.py`
- Test: `testing/ci/tests/test_e2e_sh_manifest_wiring.py`

- [ ] **Step 1: Write failing emitter tests**

Create `packages/floe-core/tests/unit/contracts/test_emit_contracts.py`:

```python
"""Tests for generated contract emitters."""

from __future__ import annotations


def test_shell_exports_include_canonical_defaults() -> None:
    """Shell emit output provides defaults owned by topology contracts."""
    from floe_core.contracts.emit import render_shell_defaults

    output = render_shell_defaults()

    assert "FLOE_DEFAULT_RELEASE_NAME=floe-platform" in output
    assert "FLOE_DEFAULT_NAMESPACE=floe-test" in output


def test_service_name_command_uses_topology_contract() -> None:
    """Service-name rendering comes from the topology contract."""
    from floe_core.contracts.emit import render_service_name_output

    assert render_service_name_output("polaris", "demo") == "demo-polaris\n"


def test_helm_env_fragment_contains_execution_context() -> None:
    """The Helm env fragment includes explicit execution context binding."""
    from floe_core.contracts.emit import render_helm_test_env_template

    output = render_helm_test_env_template()

    assert 'name: FLOE_EXECUTION_CONTEXT' in output
    assert 'value: "in-cluster"' in output
    assert "POLARIS_HOST" in output
```

- [ ] **Step 2: Run emitter tests and verify they fail**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/contracts/test_emit_contracts.py -v
```

Expected: FAIL because `floe_core.contracts.emit` does not exist.

- [ ] **Step 3: Add the contract emitter**

Create `packages/floe-core/src/floe_core/contracts/emit.py`:

```python
"""Emit generated contract bindings for shell and Helm consumers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from floe_core.contracts.topology import (
    DEFAULT_NAMESPACE,
    DEFAULT_RELEASE_NAME,
    ComponentId,
    render_service_name,
    service_contract_by_name,
    test_runner_services,
)


def render_shell_defaults() -> str:
    """Render shell assignments for contract-owned defaults."""
    lines = [
        f"FLOE_DEFAULT_RELEASE_NAME={DEFAULT_RELEASE_NAME}",
        f"FLOE_DEFAULT_NAMESPACE={DEFAULT_NAMESPACE}",
        "FLOE_DEFAULT_EXECUTION_CONTEXT=host",
    ]
    return "\n".join(lines) + "\n"


def render_service_name_output(component_name: str, release_name: str) -> str:
    """Render a service name and trailing newline for shell command use."""
    service = service_contract_by_name(component_name)
    return render_service_name(service.component_id, release_name=release_name) + "\n"


def _helm_host_helper(component_id: ComponentId) -> str:
    helper_by_component = {
        ComponentId.POSTGRESQL: 'include "floe-platform.postgresql.host" $context',
        ComponentId.POLARIS: 'include "floe-platform.polaris.fullname" $context',
        ComponentId.POLARIS_MANAGEMENT: 'include "floe-platform.polaris.fullname" $context',
        ComponentId.MINIO: 'include "floe-platform.minio.fullname" $context',
        ComponentId.MINIO_CONSOLE: 'include "floe-platform.minio.fullname" $context',
        ComponentId.MARQUEZ: 'include "floe-platform.marquez.fullname" $context',
        ComponentId.DAGSTER_WEBSERVER: 'include "floe-platform.dagster.webserverName" $context',
        ComponentId.JAEGER_QUERY: 'include "floe-platform.jaeger.queryName" $context',
        ComponentId.OTEL_COLLECTOR_GRPC: 'include "floe-platform.otel.fullname" $context',
        ComponentId.OTEL_COLLECTOR_HTTP: 'include "floe-platform.otel.fullname" $context',
    }
    return helper_by_component[component_id]


def render_helm_test_env_template() -> str:
    """Render the Helm template helper consumed by the test-runner Job."""
    lines = [
        '{{- define "floe-platform.testRunner.contractEnv" -}}',
        "{{- $context := . -}}",
        "- name: FLOE_EXECUTION_CONTEXT",
        '  value: "in-cluster"',
        "- name: FLOE_RELEASE_NAME",
        "  value: {{ $context.Release.Name | quote }}",
        "- name: FLOE_NAMESPACE",
        "  value: {{ $context.Release.Namespace | quote }}",
    ]
    for service in test_runner_services():
        helper = _helm_host_helper(service.component_id)
        lines.extend(
            [
                f"- name: {service.host_env_var}",
                "  value: {{ " + helper + " | quote }}",
                f"- name: {service.port_env_var}",
                f'  value: "{service.default_port}"',
            ]
        )
    lines.append("{{- end -}}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Command entry point for contract binding emission."""
    parser = argparse.ArgumentParser(prog="python -m floe_core.contracts.emit")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("shell-defaults")

    service_parser = subcommands.add_parser("service-name")
    service_parser.add_argument("component")
    service_parser.add_argument("--release-name", default=DEFAULT_RELEASE_NAME)

    subcommands.add_parser("helm-test-env")

    args = parser.parse_args(argv)
    if args.command == "shell-defaults":
        print(render_shell_defaults(), end="")
        return 0
    if args.command == "service-name":
        print(render_service_name_output(args.component, args.release_name), end="")
        return 0
    if args.command == "helm-test-env":
        print(render_helm_test_env_template(), end="")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run emitter tests**

Run:

```bash
uv run pytest packages/floe-core/tests/unit/contracts/test_emit_contracts.py -v
```

Expected: PASS.

- [ ] **Step 5: Make `testing/ci/common.sh` consume emitted defaults**

Modify `testing/ci/common.sh`:

1. Add project root calculation after `SCRIPT_DIR`:

```bash
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
```

2. Add:

```bash
floe_contract_emit() {
    PYTHONPATH="${PROJECT_ROOT}/packages/floe-core/src:${PYTHONPATH:-}" \
        python3 -m floe_core.contracts.emit "$@"
}

eval "$(floe_contract_emit shell-defaults)"
```

3. Replace:

```bash
: "${FLOE_RELEASE_NAME:=floe-platform}"
: "${FLOE_NAMESPACE:=floe-test}"
```

with:

```bash
: "${FLOE_RELEASE_NAME:=${FLOE_DEFAULT_RELEASE_NAME}}"
: "${FLOE_NAMESPACE:=${FLOE_DEFAULT_NAMESPACE}}"
```

4. Replace the `floe_service_name` body with:

```bash
floe_service_name() {
    local component="$1"
    if [[ -z "${component}" ]]; then
        echo "floe_service_name: component argument required" >&2
        return 2
    fi
    floe_contract_emit service-name --release-name "${FLOE_RELEASE_NAME}" "${component}"
}
```

- [ ] **Step 6: Remove locally authored service-name precomputation from `test-e2e.sh`**

Modify `testing/ci/test-e2e.sh`:

1. Delete this block:

```bash
# Pre-compute platform service names from the chart release name.
# No literal `floe-platform-*` strings may appear below this line.
SVC_DAGSTER_WEB="$(floe_service_name dagster-webserver)"
SVC_POLARIS="$(floe_service_name polaris)"
SVC_MINIO="$(floe_service_name minio)"
SVC_OTEL="$(floe_service_name otel)"
SVC_MARQUEZ="$(floe_service_name marquez)"
SVC_JAEGER_QUERY="$(floe_service_name jaeger-query)"
SVC_POSTGRES="$(floe_service_name postgresql)"
```

2. Replace later usages of those variables with command substitutions:

```bash
"$(floe_service_name dagster-webserver)"
"$(floe_service_name polaris)"
"$(floe_service_name minio)"
"$(floe_service_name otel-collector-grpc)"
"$(floe_service_name marquez)"
"$(floe_service_name jaeger-query)"
"$(floe_service_name postgresql)"
```

- [ ] **Step 7: Update shell wiring tests**

Modify `testing/ci/tests/test_e2e_sh_manifest_wiring.py` and add:

```python
def test_common_sh_uses_contract_emitter_for_service_names(repo_root: Path) -> None:
    """Shell service names must come from floe_core.contracts.emit."""
    common = (repo_root / "testing" / "ci" / "common.sh").read_text()

    assert "python3 -m floe_core.contracts.emit" in common
    assert 'printf \'%s-%s\\n\' "${FLOE_RELEASE_NAME}" "${component}"' not in common
```

- [ ] **Step 8: Run shell adapter tests**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/contracts/test_emit_contracts.py \
  testing/ci/tests/test_e2e_sh_manifest_wiring.py \
  -v
```

Expected: PASS.

- [ ] **Step 9: Commit shell adapter migration**

Run:

```bash
git add \
  packages/floe-core/src/floe_core/contracts/emit.py \
  packages/floe-core/tests/unit/contracts/test_emit_contracts.py \
  testing/ci/common.sh \
  testing/ci/test-e2e.sh \
  testing/ci/tests/test_e2e_sh_manifest_wiring.py
git commit -m "refactor: generate shell service bindings from contracts"
```

### Task 6: Helm Test Runner Contract Adapter

**Files:**

- Create: `charts/floe-platform/templates/tests/_contract-env.generated.tpl`
- Modify: `charts/floe-platform/templates/tests/_test-job.tpl`
- Modify: `tests/unit/test_e2e_runner_chart_contract.py`
- Test: `tests/unit/test_e2e_runner_chart_contract.py`

- [ ] **Step 1: Write chart contract tests for generated env usage**

Modify `tests/unit/test_e2e_runner_chart_contract.py` and add:

```python
def test_test_runner_uses_generated_contract_env_helper() -> None:
    """The test Job env table must come from the generated contract helper."""
    template = _TEMPLATE_PATH.read_text()

    assert 'include "floe-platform.testRunner.contractEnv" $context' in template
    assert "name: INTEGRATION_TEST_HOST" not in template
    assert "name: POLARIS_HOST" not in template


def test_generated_contract_env_helper_matches_emitter() -> None:
    """Committed Helm helper must match the contract emitter output."""
    from floe_core.contracts.emit import render_helm_test_env_template

    generated = (
        _REPO_ROOT
        / "charts"
        / "floe-platform"
        / "templates"
        / "tests"
        / "_contract-env.generated.tpl"
    )

    assert generated.read_text() == render_helm_test_env_template()
```

- [ ] **Step 2: Run chart contract tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_e2e_runner_chart_contract.py -v
```

Expected: FAIL because `_test-job.tpl` still owns the env table and the generated helper file does not exist.

- [ ] **Step 3: Generate the Helm env helper**

Run:

```bash
PYTHONPATH=packages/floe-core/src python3 -m floe_core.contracts.emit helm-test-env \
  > charts/floe-platform/templates/tests/_contract-env.generated.tpl
```

Expected: file is created and contains `FLOE_EXECUTION_CONTEXT`, `POLARIS_HOST`, and `POLARIS_PORT`.

- [ ] **Step 4: Replace the env table in `_test-job.tpl`**

Modify `charts/floe-platform/templates/tests/_test-job.tpl`:

1. Delete the local variables that only feed the env table:

```gotemplate
{{- $polaris := include "floe-platform.polaris.fullname" $context }}
{{- $minio := include "floe-platform.minio.fullname" $context }}
{{- $postgres := include "floe-platform.postgresql.host" $context }}
{{- $dagsterWeb := include "floe-platform.dagster.webserverName" $context }}
{{- $marquez := include "floe-platform.marquez.fullname" $context }}
{{- $otel := include "floe-platform.otel.fullname" $context }}
{{- $jaegerQuery := include "floe-platform.jaeger.queryName" $context }}
```

2. Replace the entire current `env:` list with:

```gotemplate
          env:
            {{- include "floe-platform.testRunner.contractEnv" $context | nindent 12 }}
            - name: POSTGRES_USER
              value: floe
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.postgresql.secretName" $context }}
                  key: postgresql-password
            - name: MINIO_ENDPOINT
              value: "http://{{ include "floe-platform.minio.fullname" $context }}:9000"
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.minio.secretName" $context }}
                  key: root-user
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.minio.secretName" $context }}
                  key: root-password
            - name: AWS_REGION
              value: us-east-1
            - name: POLARIS_URI
              value: "http://{{ include "floe-platform.polaris.fullname" $context }}:{{ $context.Values.polaris.service.port | default 8181 }}/api/catalog"
            - name: POLARIS_CREDENTIAL
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.polaris.credentialSecretName" $context }}
                  key: POLARIS_CREDENTIAL
            - name: POLARIS_WAREHOUSE
              value: {{ include "floe-platform.polaris.warehouse" $context | quote }}
            - name: POLARIS_SCOPE
              value: "PRINCIPAL_ROLE:ALL"
            - name: JAEGER_URL
              value: "http://{{ include "floe-platform.jaeger.queryName" $context }}:16686"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://{{ include "floe-platform.otel.fullname" $context }}:4317"
            - name: OTEL_SERVICE_NAME
              value: "floe-test-runner-{{ $suite }}"
            - name: PYTHONPATH
              value: "/app:/app/testing"
            - name: PYTHONUNBUFFERED
              value: "1"
```

- [ ] **Step 5: Render the standard E2E Job**

Run:

```bash
source testing/ci/common.sh && floe_render_test_job tests/job-e2e.yaml >/tmp/floe-e2e-job.yaml
```

Expected: exit code 0.

Run:

```bash
rg -n "FLOE_EXECUTION_CONTEXT|POLARIS_HOST|POLARIS_PORT|INTEGRATION_TEST_HOST" /tmp/floe-e2e-job.yaml
```

Expected: output includes `FLOE_EXECUTION_CONTEXT`, `POLARIS_HOST`, and `POLARIS_PORT`; output does not include `INTEGRATION_TEST_HOST`.

- [ ] **Step 6: Run chart contract tests**

Run:

```bash
uv run pytest tests/unit/test_e2e_runner_chart_contract.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Helm adapter migration**

Run:

```bash
git add \
  charts/floe-platform/templates/tests/_contract-env.generated.tpl \
  charts/floe-platform/templates/tests/_test-job.tpl \
  tests/unit/test_e2e_runner_chart_contract.py
git commit -m "refactor: generate test runner env bindings"
```

### Task 7: Validation Boundary Split

**Files:**

- Modify: `pyproject.toml`
- Modify: `Makefile`
- Create: `tests/bootstrap/conftest.py`
- Move: `tests/e2e/test_platform_bootstrap.py` to `tests/bootstrap/test_platform_bootstrap.py`
- Modify: `tests/e2e/conftest.py`
- Test: `tests/unit/test_validation_boundary_markers.py`

- [ ] **Step 1: Write validation-boundary marker tests**

Create `tests/unit/test_validation_boundary_markers.py`:

```python
"""Tests for validation-boundary configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_pytest_markers_include_validation_boundaries() -> None:
    """The validation stack has explicit boundary markers."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    marker_names = {entry.split(":", 1)[0] for entry in markers}

    assert {"contract", "bootstrap", "platform_blackbox", "developer_workflow"} <= marker_names


def test_make_test_runs_contract_before_integration() -> None:
    """Top-level test target runs contract tests before integration tests."""
    makefile = Path("Makefile").read_text()

    assert "test: test-unit test-contract test-integration" in makefile
    assert ".PHONY: test-contract" in makefile
```

- [ ] **Step 2: Run marker tests and verify they fail**

Run:

```bash
uv run pytest tests/unit/test_validation_boundary_markers.py -v
```

Expected: FAIL because `platform_blackbox`, `developer_workflow`, and Makefile contract wiring are missing.

- [ ] **Step 3: Add pytest validation-boundary markers**

Modify the `markers` list in `pyproject.toml`:

```toml
    "bootstrap: Marks environment bring-up and platform readiness checks",
    "platform_blackbox: Marks deployed-system behavior checks with no repo-local assumptions",
    "developer_workflow: Marks repo-aware local/developer workflow checks",
```

- [ ] **Step 4: Wire contract tests into the standard test target**

Modify `Makefile`:

1. Change:

```make
test: test-unit test-integration ## Run all tests (unit + integration)
```

to:

```make
test: test-unit test-contract test-integration ## Run all tests (unit + contract + integration)
```

2. Add after `test-unit`:

```make
.PHONY: test-contract
test-contract: ## Run cross-package contract tests
	@echo "Running contract tests..."
	@./testing/ci/test-contract.sh
```

- [ ] **Step 5: Move bootstrap test to the bootstrap boundary**

Run:

```bash
mkdir -p tests/bootstrap
git mv tests/e2e/test_platform_bootstrap.py tests/bootstrap/test_platform_bootstrap.py
```

Create `tests/bootstrap/conftest.py`:

```python
"""Bootstrap validation fixtures.

Bootstrap tests validate environment bring-up before product E2E tests run.
They may use Kubernetes and Helm readiness checks, but they should not assert
data-platform product behavior.
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark all bootstrap tests with the bootstrap boundary marker."""
    for item in items:
        item.add_marker(pytest.mark.bootstrap)
```

- [ ] **Step 6: Mark E2E tests as platform black-box by default**

Modify `tests/e2e/conftest.py` inside `pytest_collection_modifyitems` before the destructive reordering logic returns:

```python
    for item in items:
        item.add_marker(pytest.mark.platform_blackbox)
```

Keep the existing destructive reordering and TQR checks in place.

- [ ] **Step 7: Run validation-boundary tests**

Run:

```bash
uv run pytest tests/unit/test_validation_boundary_markers.py tests/bootstrap/test_platform_bootstrap.py --collect-only -q
```

Expected: PASS collection.

- [ ] **Step 8: Commit validation boundary split**

Run:

```bash
git add \
  Makefile \
  pyproject.toml \
  tests/bootstrap/conftest.py \
  tests/bootstrap/test_platform_bootstrap.py \
  tests/e2e/conftest.py \
  tests/unit/test_validation_boundary_markers.py
git commit -m "test: split validation boundaries"
```

### Task 8: Contract Drift Guard And Final Verification

**Files:**

- Modify: `scripts/check-architecture-drift`
- Create: `tests/contract/test_platform_contract_generated_bindings.py`
- Test: `tests/contract/test_platform_contract_generated_bindings.py`

- [ ] **Step 1: Write contract-generated binding tests**

Create `tests/contract/test_platform_contract_generated_bindings.py`:

```python
"""Cross-consumer contract tests for generated platform bindings."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_shell_and_python_render_same_polaris_service_name() -> None:
    """Shell bindings and Python contracts render the same service name."""
    from floe_core.contracts.topology import ComponentId, render_service_name

    expected = render_service_name(ComponentId.POLARIS, release_name="floe-platform").strip()
    result = subprocess.run(
        [
            "bash",
            "-lc",
            "source testing/ci/common.sh && floe_service_name polaris",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_chart_generated_env_helper_is_emitter_output() -> None:
    """The committed Helm helper is generated from the contract emitter."""
    from floe_core.contracts.emit import render_helm_test_env_template

    path = Path("charts/floe-platform/templates/tests/_contract-env.generated.tpl")

    assert path.read_text() == render_helm_test_env_template()


def test_service_fixture_uses_contract_owned_port_table() -> None:
    """Python service fixture defaults are generated from topology contracts."""
    from floe_core.contracts.topology import service_contracts
    from testing.fixtures.services import SERVICE_DEFAULT_PORTS

    assert SERVICE_DEFAULT_PORTS == {
        service.short_name: service.default_port for service in service_contracts()
    }
```

- [ ] **Step 2: Run contract binding tests**

Run:

```bash
uv run pytest tests/contract/test_platform_contract_generated_bindings.py -v
```

Expected: PASS.

- [ ] **Step 3: Add duplicate service-literal guard**

Modify `scripts/check-architecture-drift`:

1. Add this function before `check_file`:

```bash
check_platform_contract_literals() {
    local file="$1"

    case "$file" in
        *"packages/floe-core/src/floe_core/contracts/"*|*"charts/floe-platform/templates/tests/_contract-env.generated.tpl")
            return 0
            ;;
    esac

    if grep -qE '"(dagster|polaris|polaris-management|minio|minio-console|postgres|postgresql|jaeger-query|otel-collector-grpc|otel-collector-http|marquez|oci-registry|oci-registry-auth)"[[:space:]]*:' "$file" 2>/dev/null; then
        log_error "$file: duplicated platform service map detected - use floe_core.contracts.topology"
        ((violations++))
    fi
}
```

2. Call it from `check_file` after `check_test_organization "$file"`:

```bash
    check_platform_contract_literals "$file"
```

- [ ] **Step 4: Run architecture drift check against migrated files**

Run:

```bash
./scripts/check-architecture-drift testing/fixtures/services.py
```

Expected: exit code 0.

Run:

```bash
./scripts/check-architecture-drift packages/floe-core/src/floe_core/contracts/topology.py
```

Expected: exit code 0 because contract-domain files are allowed to author canonical service literals.

- [ ] **Step 5: Run focused contract, unit, shell, and chart verification**

Run:

```bash
uv run pytest \
  packages/floe-core/tests/unit/contracts \
  tests/unit/test_e2e_fixture_wiring.py \
  tests/unit/test_e2e_runner_chart_contract.py \
  tests/unit/test_validation_boundary_markers.py \
  tests/contract/test_platform_contract_generated_bindings.py \
  -v
```

Expected: PASS.

- [ ] **Step 6: Run type and lint checks for touched areas**

Run:

```bash
uv run ruff check packages/floe-core/src/floe_core/contracts testing/fixtures/services.py tests/unit tests/contract
uv run ruff format --check packages/floe-core/src/floe_core/contracts testing/fixtures/services.py tests/unit tests/contract
uv run mypy --strict packages/floe-core/src/floe_core/contracts testing/fixtures
```

Expected: PASS.

- [ ] **Step 7: Run top-level tests that do not require a live cluster**

Run:

```bash
make test-unit
make test-contract
```

Expected: PASS.

- [ ] **Step 8: Run cluster validation on DevPod + Hetzner**

Run:

```bash
DEVPOD_WORKSPACE=floe scripts/devpod-ensure-ready.sh
DEVPOD_WORKSPACE=floe scripts/devpod-sync-kubeconfig.sh
make test-e2e
make test-e2e-full
```

Expected: standard and destructive E2E suites pass. If bootstrap fails, record it as a bootstrap failure and do not debug product E2E behavior until bootstrap is green.

- [ ] **Step 9: Commit drift guard and verification contract tests**

Run:

```bash
git add scripts/check-architecture-drift tests/contract/test_platform_contract_generated_bindings.py
git commit -m "test: guard generated platform contracts"
```

## Acceptance Mapping

- `floe_core.contracts` exists with runtime, schemas, topology, and execution domains: Tasks 1, 2, and 3.
- Shared runtime enums are sourced from the contract layer: Task 1.
- Machine-readable output keys are contract-owned: Task 2.
- Python fixtures consume generated bindings rather than local service maps: Task 4.
- Shell scripts consume contract emitters rather than authoring service-name formulas: Task 5.
- Helm test-runner env bindings are generated from the contract emitter: Task 6.
- Validation stack is split into contract, bootstrap, platform-blackbox, and developer-workflow categories: Task 7.
- Legacy duplicate authoring paths for migrated domains are removed or guarded against: Task 8.

## Final Verification

Run the full local non-cluster validation:

```bash
make lint
make typecheck
make test-unit
make test-contract
```

Run the DevPod + Hetzner cluster validation:

```bash
DEVPOD_WORKSPACE=floe scripts/devpod-ensure-ready.sh
DEVPOD_WORKSPACE=floe scripts/devpod-sync-kubeconfig.sh
make test-e2e
make test-e2e-full
```

The implementation is complete when all focused tests, unit tests, contract tests, and DevPod + Hetzner E2E suites pass.
