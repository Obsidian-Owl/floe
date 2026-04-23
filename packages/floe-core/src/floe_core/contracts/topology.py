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
    local_port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description="Local forwarded port for host-style execution contexts",
    )
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

    @property
    def host_port(self) -> int:
        """Return the local forwarded port, falling back to the service port."""
        return self.local_port if self.local_port is not None else self.default_port


_SERVICES: tuple[ServiceContract, ...] = (
    ServiceContract(
        component_id=ComponentId.DAGSTER_WEBSERVER,
        chart_component="dagster-webserver",
        default_port=3000,
        local_port=3100,
        host_env_var="DAGSTER_WEBSERVER_HOST",
        port_env_var="DAGSTER_WEBSERVER_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.POLARIS,
        chart_component="polaris",
        default_port=8181,
        local_port=8181,
        host_env_var="POLARIS_HOST",
        port_env_var="POLARIS_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.POLARIS_MANAGEMENT,
        chart_component="polaris",
        default_port=8182,
        host_env_var="POLARIS_MANAGEMENT_HOST",
        port_env_var="POLARIS_MANAGEMENT_PORT",
        readiness_path="/q/health/ready",
    ),
    ServiceContract(
        component_id=ComponentId.MINIO,
        chart_component="minio",
        default_port=9000,
        local_port=9000,
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
        local_port=5432,
        host_env_var="POSTGRES_HOST",
        port_env_var="POSTGRES_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.JAEGER_QUERY,
        chart_component="jaeger-query",
        default_port=16686,
        local_port=16686,
        host_env_var="JAEGER_QUERY_HOST",
        port_env_var="JAEGER_QUERY_PORT",
    ),
    ServiceContract(
        component_id=ComponentId.OTEL_COLLECTOR_GRPC,
        chart_component="otel",
        default_port=4317,
        local_port=4317,
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
        local_port=5100,
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
