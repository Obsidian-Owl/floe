"""Service health utilities for K8s-native integration tests.

This module provides utilities for checking the health status of K8s services
before running integration tests. Tests use these utilities to ensure required
services are available.

Functions:
    check_service_health: Check if a K8s service is responding
    check_infrastructure: Verify multiple services are healthy

Example:
    from testing.fixtures.services import check_service_health

    if check_service_health("polaris", 8181):
        print("Polaris is ready")
"""

from __future__ import annotations

import socket
from dataclasses import dataclass


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
        """Get the fully qualified K8s DNS name."""
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
    except (OSError, socket.error):
        return False


# Module exports
__all__ = [
    "ServiceEndpoint",
    "ServiceUnavailableError",
    "check_infrastructure",
    "check_service_health",
]
