"""Service health utilities for K8s-native integration tests.

This module provides utilities for checking the health status of K8s services
before running integration tests. Tests use these utilities to ensure required
services are available.

Functions:
    check_service_health: Check if a K8s service is responding
    check_infrastructure: Verify multiple services are healthy

Environment Variables:
    FLOE_EXECUTION_CONTEXT: Required execution context for generated bindings.
        Supported values: "in-cluster", "host", "devpod", "demo".
    FLOE_RELEASE_NAME: Helm release name for in-cluster service bindings.
    FLOE_NAMESPACE: Kubernetes namespace for generated bindings.
    {SERVICE}_HOST: Explicit host override for a contract-defined service.

Example:
    from testing.fixtures.services import check_service_health

    if check_service_health("polaris", 8181):
        print("Polaris is ready")
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from socket import create_connection

from floe_core.contracts.errors import ContractViolationError
from floe_core.contracts.execution import parse_execution_context, service_binding
from floe_core.contracts.topology import (
    DEFAULT_NAMESPACE,
    DEFAULT_RELEASE_NAME,
    service_contract_by_name,
    service_contracts,
)

# ---------------------------------------------------------------------------
# Port resolution constants and utilities
# ---------------------------------------------------------------------------

SERVICE_DEFAULT_PORTS: dict[str, int] = {
    service.short_name: service.default_port for service in service_contracts()
}
"""Default ports for well-known floe platform services."""

_PORT_UNSET: int = -1
"""Sentinel value indicating a port has not been set."""


def _get_effective_port(service_name: str, default: int | None = None) -> int:
    """Determine the effective port for a service.

    Resolves port using the following precedence:
      1. Environment variable ``{SERVICE_NAME}_PORT`` (hyphens → underscores, uppercase)
      2. Explicit ``default`` parameter (if not None)
      3. ``SERVICE_DEFAULT_PORTS`` lookup
      4. ``ValueError`` if none of the above applies

    Args:
        service_name: Name of the service (e.g., ``"polaris"``).
        default: Optional caller-supplied default port.

    Returns:
        Resolved port as an integer.

    Raises:
        ValueError: If the env var contains a non-integer value, or if no
            port can be determined.
    """
    fallback_env_key = f"{service_name.upper().replace('-', '_')}_PORT"
    try:
        service = service_contract_by_name(service_name)
        env_key = service.port_env_var
    except ContractViolationError:
        env_key = fallback_env_key
    env_val = os.environ.get(env_key)
    if env_val is not None and env_val.strip() != "":
        try:
            port = int(env_val)
        except ValueError:
            raise ValueError(
                f"Invalid port value for {env_key}={env_val!r}: must be an integer"
            ) from None
        if not (1 <= port <= 65535):
            raise ValueError(f"Invalid port value for {env_key}={port}: must be 1-65535")
        return port
    if default is not None:
        return default
    if service_name in SERVICE_DEFAULT_PORTS:
        return SERVICE_DEFAULT_PORTS[service_name]
    known = ", ".join(sorted(SERVICE_DEFAULT_PORTS.keys()))
    raise ValueError(
        f"No port for service {service_name!r}: "
        f"set {env_key} env var or use a known service ({known})"
    )


def get_effective_port(service_name: str, default: int | None = None) -> int:
    """Get the effective port for a service.

    Public wrapper around :func:`_get_effective_port`.  Resolves port using
    the following precedence:
      1. Environment variable ``{SERVICE_NAME}_PORT``
      2. Explicit ``default`` parameter
      3. ``SERVICE_DEFAULT_PORTS`` lookup
      4. ``ValueError`` if none of the above applies

    Args:
        service_name: Name of the service (e.g., ``"polaris"``).
        default: Optional caller-supplied default port.

    Returns:
        Resolved port as an integer.

    Raises:
        ValueError: If the env var contains a non-integer value, or if no
            port can be determined.

    Example:
        port = get_effective_port("polaris")
        uri = f"http://localhost:{port}/api/catalog"
    """
    return _get_effective_port(service_name, default)


def _get_effective_host(service_name: str, namespace: str) -> str:
    """Determine the effective host for a service from execution contracts."""
    service = service_contract_by_name(service_name)
    env_key = service.host_env_var
    service_host = os.environ.get(env_key)
    if service_host:
        return service_host

    context = parse_execution_context(os.environ.get("FLOE_EXECUTION_CONTEXT"))
    release_name = os.environ.get("FLOE_RELEASE_NAME", DEFAULT_RELEASE_NAME)
    effective_namespace = (
        os.environ.get("FLOE_NAMESPACE", DEFAULT_NAMESPACE)
        if namespace == DEFAULT_NAMESPACE
        else namespace
    )
    binding = service_binding(
        service.component_id,
        context,
        release_name=release_name,
        namespace=effective_namespace,
    )
    return binding.host


@dataclass(frozen=True)
class ServiceEndpoint:
    """Represents a K8s service endpoint.

    When ``port`` is omitted (or set to the sentinel ``_PORT_UNSET``), it is
    resolved automatically via :func:`_get_effective_port` using the standard
    precedence chain (env var → dict default).

    Attributes:
        name: Service name (e.g., "polaris", "postgresql")
        port: Service port number.  Defaults to automatic resolution.
        namespace: K8s namespace. Defaults to "floe-test"
    """

    name: str
    port: int = _PORT_UNSET
    namespace: str = "floe-test"

    def __post_init__(self) -> None:
        """Resolve port from env/defaults when the sentinel is used."""
        if self.port == _PORT_UNSET:
            object.__setattr__(self, "port", _get_effective_port(self.name))

    @property
    def host(self) -> str:
        """Get the effective hostname for the service.

        Uses K8s DNS when running inside the cluster, localhost when running
        on host (e.g., with Kind NodePort mappings).
        """
        return _get_effective_host(self.name, self.namespace)

    @property
    def url(self) -> str:
        """Construct ``http://{host}:{port}`` URL."""
        return f"http://{self.host}:{self.port}"

    @property
    def k8s_host(self) -> str:
        """Get the fully qualified K8s DNS name (for documentation/logging)."""
        return f"{self.name}.{self.namespace}.svc.cluster.local"

    def __str__(self) -> str:
        return f"{self.name}:{self.port} ({self.namespace})"


class ServiceUnavailableError(Exception):
    """Raised when a required service is not available.

    Attributes:
        service: The service endpoint that was checked
        reason: Why the service is unavailable
    """

    def __init__(self, service: ServiceEndpoint, reason: str) -> None:
        self.service = service
        self.reason = reason
        super().__init__(
            f"Service {service} is unavailable: {reason}\n"
            f"Ensure the Kind cluster is running: make kind-up"
        )


def check_service_health(
    service_name: str,
    port: int,
    namespace: str = "floe-test",
    timeout: float = 5.0,
) -> bool:
    """Check if a K8s service is healthy.

    Attempts to establish a TCP connection to the service. Returns True
    if the connection succeeds, False otherwise. Does not raise exceptions
    for unhealthy services.

    Args:
        service_name: Name of the K8s service.
        port: Port to check.
        namespace: K8s namespace. Defaults to "floe-test".
        timeout: Connection timeout in seconds. Defaults to 5.0.

    Returns:
        True if service responds, False otherwise.

    Example:
        if check_service_health("postgresql", 5432):
            print("PostgreSQL is ready")
        else:
            print("PostgreSQL is not available")
    """
    endpoint = ServiceEndpoint(service_name, port, namespace)
    return _tcp_health_check(endpoint.host, port, timeout)


def check_infrastructure(
    services: Sequence[tuple[str, int] | str],
    namespace: str = "floe-test",
    timeout: float = 5.0,
    *,
    raise_on_failure: bool = True,
) -> dict[str, bool]:
    """Verify multiple services are healthy.

    Checks all specified services and returns their health status.
    Optionally raises an exception if any service is unavailable.

    Each entry in *services* may be either:
    - ``("service_name", port)`` — explicit port (legacy format)
    - ``"service_name"`` — port resolved via env var / defaults

    Args:
        services: List of service specs to check.
        namespace: K8s namespace. Defaults to "floe-test".
        timeout: Connection timeout per service in seconds. Defaults to 5.0.
        raise_on_failure: If True, raise ServiceUnavailableError for the
            first unhealthy service. Defaults to True.

    Returns:
        Dictionary mapping service names to their health status.

    Raises:
        ServiceUnavailableError: If raise_on_failure=True and any service
            is unavailable.

    Example:
        # New string format (port resolved from env/defaults)
        health = check_infrastructure(["polaris", "minio", "postgresql"])

        # Legacy tuple format still works
        health = check_infrastructure([("polaris", 8181)])

        # Mixed list
        health = check_infrastructure([("dagster-webserver", 3100), "polaris"])
    """
    results: dict[str, bool] = {}

    for spec in services:
        if isinstance(spec, str):
            endpoint = ServiceEndpoint(spec, namespace=namespace)
        else:
            name, port = spec
            endpoint = ServiceEndpoint(name, port, namespace)
        is_healthy = _tcp_health_check(endpoint.host, endpoint.port, timeout)
        results[endpoint.name] = is_healthy

        if raise_on_failure and not is_healthy:
            raise ServiceUnavailableError(
                endpoint,
                f"TCP connection to {endpoint.host}:{endpoint.port} failed",
            )

    return results


def _tcp_health_check(host: str, port: int, timeout: float) -> bool:
    """Perform a TCP health check.

    Args:
        host: Hostname or IP address.
        port: Port number.
        timeout: Connection timeout in seconds.

    Returns:
        True if connection successful, False otherwise.
    """
    try:
        with create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_effective_host(
    service_name: str,
    namespace: str = "floe-test",
) -> str:
    """Get the effective hostname for a service.

    Resolves the host from contract-defined execution context bindings.

    Args:
        service_name: Name of the service (e.g., "polaris").
        namespace: K8s namespace. Defaults to "floe-test".

    Returns:
        Effective hostname from the configured execution context.

    Environment Variables:
        FLOE_EXECUTION_CONTEXT: Required execution context for generated bindings.
        FLOE_RELEASE_NAME: Helm release name for in-cluster service bindings.
        FLOE_NAMESPACE: Kubernetes namespace for generated bindings.
        {SERVICE}_HOST: Explicit host override for a contract-defined service.

    Example:
        host = get_effective_host("polaris")
        uri = f"http://{host}:8181/api/catalog"
    """
    return _get_effective_host(service_name, namespace)


# Module exports
__all__ = [
    "SERVICE_DEFAULT_PORTS",
    "ServiceEndpoint",
    "ServiceUnavailableError",
    "check_infrastructure",
    "check_service_health",
    "get_effective_host",
    "get_effective_port",
]
