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
