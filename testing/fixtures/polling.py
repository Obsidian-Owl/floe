"""Polling utilities for K8s-native integration tests.

This module provides polling helpers to replace hardcoded time.sleep() calls
in test code, ensuring reliable and efficient waiting for async operations.

Functions:
    wait_for_condition: Poll until a condition is true or timeout
    wait_for_service: Wait for a K8s service to become ready

Example:
    from testing.fixtures.polling import wait_for_condition, wait_for_service

    # Wait for async operation
    assert wait_for_condition(
        lambda: job_status(job_id) == "complete",
        timeout=30.0,
        description="job completion"
    )

    # Wait for service
    wait_for_service("polaris", 8181, timeout=60.0)
"""

from __future__ import annotations

import socket
import time
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field


class PollingConfig(BaseModel):
    """Configuration for polling utilities.

    Attributes:
        timeout: Maximum wait time in seconds. Defaults to 30.0.
        interval: Poll interval in seconds. Defaults to 0.5.
        description: Description for error messages. Defaults to "condition".

    Example:
        config = PollingConfig(timeout=60.0, interval=1.0)
        wait_for_service("polaris", 8181, config=config)
    """

    model_config = ConfigDict(frozen=True)

    timeout: float = Field(
        default=30.0,
        ge=0.0,
        description="Maximum wait time in seconds",
    )
    interval: float = Field(
        default=0.5,
        ge=0.1,
        description="Poll interval in seconds",
    )
    description: str = Field(
        default="condition",
        min_length=1,
        description="Description for error messages",
    )


class PollingTimeoutError(TimeoutError):
    """Raised when a polling operation times out.

    Attributes:
        description: What was being waited for
        timeout: How long we waited
        last_error: Last exception encountered during polling (if any)
    """

    def __init__(
        self,
        description: str,
        timeout: float,
        last_error: Exception | None = None,
    ) -> None:
        self.description = description
        self.timeout = timeout
        self.last_error = last_error
        message = f"Timeout waiting for {description} after {timeout:.1f}s"
        if last_error:
            message += f" (last error: {last_error})"
        super().__init__(message)


def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 30.0,
    interval: float = 0.5,
    description: str = "condition",
    *,
    raise_on_timeout: bool = True,
) -> bool:
    """Poll until condition is True or timeout.

    This function polls the given condition at regular intervals until it
    returns True or the timeout is reached. Use this instead of time.sleep()
    for reliable async waiting.

    Args:
        condition: Callable returning True when the condition is met.
        timeout: Maximum wait time in seconds. Defaults to 30.0.
        interval: Poll interval in seconds. Defaults to 0.5.
        description: Description for error messages. Defaults to "condition".
        raise_on_timeout: If True, raise PollingTimeoutError on timeout.
            If False, return False on timeout. Defaults to True.

    Returns:
        True if condition was met within timeout.
        False if raise_on_timeout=False and timeout occurred.

    Raises:
        PollingTimeoutError: If condition not met within timeout and
            raise_on_timeout=True.

    Example:
        # Wait for job completion
        wait_for_condition(
            lambda: job_status(job_id) == "complete",
            timeout=30.0,
            description="job completion"
        )

        # Non-raising variant
        if wait_for_condition(
            lambda: service.is_ready(),
            raise_on_timeout=False
        ):
            print("Service ready")
    """
    start_time = time.monotonic()
    last_error: Exception | None = None

    while True:
        try:
            if condition():
                return True
        except Exception as e:  # noqa: BLE001
            last_error = e

        elapsed = time.monotonic() - start_time
        if elapsed >= timeout:
            if raise_on_timeout:
                raise PollingTimeoutError(description, timeout, last_error)
            return False

        # Sleep for interval, but don't exceed remaining time
        remaining = timeout - elapsed
        sleep_time = min(interval, remaining)
        if sleep_time > 0:
            time.sleep(sleep_time)


def wait_for_service(
    service_name: str,
    port: int,
    namespace: str = "floe-test",
    timeout: float = 60.0,
    config: PollingConfig | None = None,
    *,
    raise_on_timeout: bool = True,
) -> bool:
    """Wait for a K8s service to become ready.

    Polls the service endpoint until it accepts TCP connections or the
    timeout is reached.

    Args:
        service_name: Name of the K8s service.
        port: Port to check.
        namespace: K8s namespace. Defaults to "floe-test".
        timeout: Maximum wait time in seconds. Defaults to 60.0.
        config: Optional PollingConfig to override timeout/interval.
        raise_on_timeout: If True, raise on timeout. Defaults to True.

    Returns:
        True if service became ready within timeout.
        False if raise_on_timeout=False and timeout occurred.

    Raises:
        PollingTimeoutError: If service not ready within timeout and
            raise_on_timeout=True.

    Example:
        # Wait for Polaris to be ready
        wait_for_service("polaris", 8181)

        # With custom config
        config = PollingConfig(timeout=120.0, interval=2.0)
        wait_for_service("postgres", 5432, config=config)
    """
    effective_timeout = config.timeout if config else timeout
    effective_interval = config.interval if config else 0.5
    service_host = f"{service_name}.{namespace}.svc.cluster.local"
    description = f"service {service_name}:{port} in {namespace}"

    def check_connection() -> bool:
        return _tcp_check(service_host, port)

    return wait_for_condition(
        check_connection,
        timeout=effective_timeout,
        interval=effective_interval,
        description=description,
        raise_on_timeout=raise_on_timeout,
    )


def _tcp_check(host: str, port: int, timeout: float = 5.0) -> bool:
    """Check if a TCP connection can be established.

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
    "PollingConfig",
    "PollingTimeoutError",
    "wait_for_condition",
    "wait_for_service",
]
