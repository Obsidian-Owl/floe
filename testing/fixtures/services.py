"""Service health utilities for K8s-native integration tests.

This module provides utilities for checking the health status of K8s services
before running integration tests. Tests use these utilities to ensure required
services are available.

Functions:
    check_service_health: Check if a K8s service is responding
    check_infrastructure: Verify multiple services are healthy

Environment Variables:
    INTEGRATION_TEST_HOST: Override host for all services (default: auto-detect)
        - "k8s": Use K8s DNS names (for in-cluster testing)
        - "localhost": Use localhost (for host-based testing with NodePort)
        - Not set: Auto-detect based on DNS resolution
    {SERVICE}_HOST: Override host for specific service (e.g., POLARIS_HOST=localhost)

Example:
    from testing.fixtures.services import check_service_health

    if check_service_health("polaris", 8181):
        print("Polaris is ready")
"""

from __future__ import annotations

import os
import socket
from collections.abc import Sequence
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Port resolution constants and utilities
# ---------------------------------------------------------------------------

SERVICE_DEFAULT_PORTS: dict[str, int] = {
    "dagster-webserver": 3000,
    "dagster": 3000,
    "polaris": 8181,
    "polaris-management": 8182,
    "minio": 9000,
    "minio-console": 9001,
    "postgres": 5432,
    "jaeger-query": 16686,
    "otel-collector-grpc": 4317,
    "otel-collector-http": 4318,
    "marquez": 5100,
    "oci-registry": 5000,
    "registry": 5000,
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
    env_key = f"{service_name.upper().replace('-', '_')}_PORT"
    env_val = os.environ.get(env_key)
    if env_val is not None and env_val != "":
        try:
            return int(env_val)
        except ValueError:
            raise ValueError(
                f"Invalid port value for {env_key}={env_val!r}: must be an integer"
            ) from None
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
    """Determine the effective host for a service.

    Checks environment variables and auto-detects whether to use K8s DNS
    or localhost based on network reachability.

    Args:
        service_name: Name of the service (e.g., "polaris").
        namespace: K8s namespace.

    Returns:
        Effective hostname to use for connections.
    """
    # Check service-specific override (e.g., POLARIS_HOST=localhost)
    env_key = f"{service_name.upper().replace('-', '_')}_HOST"
    service_host = os.environ.get(env_key)
    if service_host:
        return service_host

    # Check global override
    global_host = os.environ.get("INTEGRATION_TEST_HOST")
    if global_host == "k8s":
        return f"{service_name}.{namespace}.svc.cluster.local"
    if global_host == "localhost":
        return "localhost"
    if global_host:
        return global_host

    # Auto-detect: try K8s DNS first, fall back to localhost
    k8s_dns = f"{service_name}.{namespace}.svc.cluster.local"
    if _can_resolve_host(k8s_dns):
        return k8s_dns

    # Fallback to localhost for Kind cluster NodePort access
    return "localhost"


def _can_resolve_host(hostname: str) -> bool:
    """Check if a hostname can be resolved.

    Args:
        hostname: The hostname to resolve.

    Returns:
        True if hostname resolves, False otherwise.
    """
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False


@dataclass(frozen=True)
class ServiceEndpoint:
    """Represents a K8s service endpoint.

    When ``port`` is omitted (or set to the sentinel ``_PORT_UNSET``), it is
    resolved automatically via :func:`_get_effective_port` using the standard
    precedence chain (env var → dict default).

    Attributes:
        name: Service name (e.g., "polaris", "postgres")
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
        if check_service_health("postgres", 5432):
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
        health = check_infrastructure(["polaris", "minio", "postgres"])

        # Legacy tuple format still works
        health = check_infrastructure([("polaris", 8181)])

        # Mixed list
        health = check_infrastructure([("dagster", 3100), "polaris"])
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
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_effective_host(
    service_name: str,
    namespace: str = "floe-test",
) -> str:
    """Get the effective hostname for a service.

    Determines whether to use K8s DNS or localhost based on environment
    variables and network reachability. This is useful for tests that
    need to construct URIs for services.

    Args:
        service_name: Name of the service (e.g., "polaris").
        namespace: K8s namespace. Defaults to "floe-test".

    Returns:
        Effective hostname (e.g., "localhost" or "polaris.floe-test.svc.cluster.local").

    Environment Variables:
        {SERVICE}_HOST: Override host for specific service (e.g., POLARIS_HOST=localhost)
        INTEGRATION_TEST_HOST: Global override ("k8s", "localhost", or custom host)

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
