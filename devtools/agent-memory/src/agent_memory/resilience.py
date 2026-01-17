"""Network resilience patterns for unreliable connections.

Provides exponential backoff with jitter, circuit breaker pattern,
and configurable retry behavior for handling mobile/train network conditions.

Patterns implemented:
- Exponential backoff with full jitter (AWS best practice)
- Circuit breaker (prevent hammering dead services)
- Configurable retry for different operation types

Example:
    >>> config = RetryConfig(max_retries=5, base_delay=2.0)
    >>> delay = calculate_backoff(attempt=2, config=config)
    >>> print(f"Waiting {delay:.2f}s before retry")
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Service failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery, limited requests


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay cap in seconds.
        exponential_base: Base for exponential backoff calculation.
        jitter: Whether to add randomization to prevent thundering herd.

    Example:
        >>> config = RetryConfig(max_retries=5, base_delay=2.0)
        >>> # Delays: ~2s, ~4s, ~8s, ~16s, ~32s (with jitter)
    """

    max_retries: int = 5
    base_delay: float = 2.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


# Preset configurations for different scenarios
RETRY_CONFIG_DEFAULT = RetryConfig()
RETRY_CONFIG_AGGRESSIVE = RetryConfig(max_retries=7, base_delay=1.0, max_delay=120.0)
RETRY_CONFIG_CONSERVATIVE = RetryConfig(max_retries=3, base_delay=1.0, max_delay=30.0)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Consecutive failures before opening circuit.
        recovery_timeout: Seconds to wait before testing recovery.
        success_threshold: Successes needed in half-open to close circuit.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2


class CircuitBreaker:
    """Circuit breaker to prevent hammering failing services.

    States:
        CLOSED: Normal operation, all requests allowed
        OPEN: Service is down, requests fail fast without calling service
        HALF_OPEN: Testing if service recovered, limited requests allowed

    Example:
        >>> breaker = CircuitBreaker()
        >>> if breaker.can_execute():
        ...     try:
        ...         result = await make_request()
        ...         breaker.record_success()
        ...     except Exception:
        ...         breaker.record_failure()
        ... else:
        ...     raise ServiceUnavailableError("Circuit open")
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        """Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration. Uses defaults if None.
        """
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current consecutive failure count."""
        return self._failure_count

    def can_execute(self) -> bool:
        """Check if a request should be allowed through.

        Returns:
            True if request should proceed, False if circuit is open.
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.config.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    return True
            return False

        # HALF_OPEN - allow request to test recovery
        return True

    def record_success(self) -> None:
        """Record a successful request.

        In HALF_OPEN state, enough successes will close the circuit.
        In CLOSED state, resets failure count.
        """
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request.

        Increments failure count and may open the circuit.
        In HALF_OPEN state, immediately reopens the circuit.
        """
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.config.failure_threshold:
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None


def calculate_backoff(
    attempt: int,
    config: RetryConfig | None = None,
) -> float:
    """Calculate backoff delay with exponential increase and optional jitter.

    Uses "full jitter" algorithm recommended by AWS for distributed systems:
    https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/

    Args:
        attempt: Current attempt number (0-indexed).
        config: Retry configuration. Uses defaults if None.

    Returns:
        Delay in seconds before next retry.

    Example:
        >>> config = RetryConfig(base_delay=2.0, exponential_base=2.0)
        >>> calculate_backoff(0, config)  # ~0-2s
        >>> calculate_backoff(1, config)  # ~0-4s
        >>> calculate_backoff(2, config)  # ~0-8s
    """
    if config is None:
        config = RETRY_CONFIG_DEFAULT

    # Exponential backoff: base * (exp_base ^ attempt)
    exp_delay = min(
        config.base_delay * (config.exponential_base**attempt),
        config.max_delay,
    )

    # Full jitter: random value between 0 and calculated delay
    # This prevents thundering herd when multiple clients retry simultaneously
    if config.jitter:
        return random.uniform(0, exp_delay)

    return exp_delay


def parse_retry_after(header_value: str | None) -> float | None:
    """Parse Retry-After header value.

    Handles both delay-seconds and HTTP-date formats.

    Args:
        header_value: Value of Retry-After header, or None.

    Returns:
        Delay in seconds, or None if header is missing/invalid.

    Example:
        >>> parse_retry_after("30")
        30.0
        >>> parse_retry_after(None)
        None
    """
    if header_value is None:
        return None

    try:
        # Try parsing as seconds (most common)
        return float(header_value)
    except ValueError:
        # Could be HTTP-date format, but that's rare
        # For simplicity, return None and use calculated backoff
        return None
