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
from dataclasses import dataclass


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

    Attributes:
        name: Service name (e.g., "polaris", "postgres")
        port: Service port number
        namespace: K8s namespace. Defaults to "floe-test"
    """

    name: str
    port: int
    namespace: str = "floe-test"

    @property
    def host(self) -> str:
        """Get the effective hostname for the service.

        Uses K8s DNS when running inside the cluster, localhost when running
        on host (e.g., with Kind NodePort mappings).
        """
        return _get_effective_host(self.name, self.namespace)

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
    services: list[tuple[str, int]],
    namespace: str = "floe-test",
    timeout: float = 5.0,
    *,
    raise_on_failure: bool = True,
) -> dict[str, bool]:
    """Verify multiple services are healthy.

    Checks all specified services and returns their health status.
    Optionally raises an exception if any service is unavailable.

    Args:
        services: List of (service_name, port) tuples to check.
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
        # Check multiple services
        health = check_infrastructure([
            ("polaris", 8181),
            ("minio", 9000),
            ("postgres", 5432),
        ])

        # With exception on failure
        try:
            check_infrastructure([("polaris", 8181)])
        except ServiceUnavailableError as e:
            print(f"Required service unavailable: {e}")
    """
    results: dict[str, bool] = {}

    for service_name, port in services:
        endpoint = ServiceEndpoint(service_name, port, namespace)
        is_healthy = _tcp_health_check(endpoint.host, port, timeout)
        results[service_name] = is_healthy

        if raise_on_failure and not is_healthy:
            raise ServiceUnavailableError(
                endpoint,
                f"TCP connection to {endpoint.host}:{port} failed",
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
    "ServiceEndpoint",
    "ServiceUnavailableError",
    "check_infrastructure",
    "check_service_health",
    "get_effective_host",
]
