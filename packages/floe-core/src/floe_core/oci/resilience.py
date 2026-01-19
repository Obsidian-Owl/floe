"""Resilience patterns for OCI registry operations.

This module implements retry policy and circuit breaker patterns for handling
transient failures and registry unavailability in OCI operations.

Key Components:
    RetryPolicy: Exponential backoff with jitter for transient failures
    CircuitBreaker: Three-state pattern (CLOSED/OPEN/HALF_OPEN) for availability

Design Principles:
- Non-blocking: All delays use asyncio.sleep or time.sleep
- Observable: OpenTelemetry metrics emitted for retry/circuit events
- Configurable: Uses RetryConfig and CircuitBreakerConfig from schemas

Example:
    >>> from floe_core.oci.resilience import RetryPolicy, CircuitBreaker
    >>> from floe_core.schemas.oci import RetryConfig, CircuitBreakerConfig
    >>>
    >>> # Create retry policy
    >>> retry_policy = RetryPolicy(RetryConfig(max_attempts=3))
    >>>
    >>> @retry_policy.wrap
    >>> def fetch_artifact():
    ...     return client.pull(tag="v1.0.0")
    >>>
    >>> # Create circuit breaker
    >>> circuit = CircuitBreaker("harbor.example.com", CircuitBreakerConfig())
    >>> with circuit.protect():
    ...     result = fetch_artifact()

See Also:
    - specs/08a-oci-client/research.md: Resilience research (Section 4)
    - Martin Fowler's Circuit Breaker pattern
"""

from __future__ import annotations

import functools
import random
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

import structlog

from floe_core.oci.errors import CircuitBreakerOpenError, RegistryUnavailableError
from floe_core.schemas.oci import CircuitBreakerConfig, RetryConfig

if TYPE_CHECKING:
    from floe_core.oci.metrics import OCIMetrics

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class RetryPolicy:
    """Retry policy with exponential backoff and jitter.

    Implements exponential backoff with optional jitter to prevent thundering herd.
    Can be used as a decorator or context manager.

    Retry Timeline (default config):
    - Attempt 1: Immediate
    - Attempt 2: ~1s delay (with jitter)
    - Attempt 3: ~2s delay (with jitter)
    - Total max time: ~7s

    Example:
        >>> config = RetryConfig(max_attempts=3, initial_delay_ms=1000)
        >>> policy = RetryPolicy(config)
        >>>
        >>> # As decorator
        >>> @policy.wrap
        >>> def fetch_data():
        ...     return external_api.get()
        >>>
        >>> # As context manager
        >>> for attempt in policy.attempts():
        ...     try:
        ...         result = external_api.get()
        ...         break
        ...     except TransientError:
        ...         attempt.record_failure()

    Attributes:
        config: RetryConfig with max_attempts, delays, and jitter settings.
    """

    def __init__(
        self,
        config: RetryConfig | None = None,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> None:
        """Initialize RetryPolicy.

        Args:
            config: Retry configuration. Uses defaults if None.
            retryable_exceptions: Exception types to retry on.
                Defaults to (RegistryUnavailableError, ConnectionError, TimeoutError).
        """
        self._config = config or RetryConfig()
        self._retryable_exceptions = retryable_exceptions or (
            RegistryUnavailableError,
            ConnectionError,
            TimeoutError,
        )

    @property
    def config(self) -> RetryConfig:
        """Return the retry configuration."""
        return self._config

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay before next retry attempt.

        Uses exponential backoff: delay = initial * (multiplier ^ attempt)
        Optionally adds jitter (±25%) to prevent thundering herd.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds.
        """
        base_delay_ms = min(
            self._config.initial_delay_ms * (self._config.backoff_multiplier**attempt),
            self._config.max_delay_ms,
        )

        if self._config.jitter:
            # Add ±25% jitter
            jitter_range = base_delay_ms * 0.25
            base_delay_ms += random.uniform(-jitter_range, jitter_range)

        return base_delay_ms / 1000.0  # Convert to seconds

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception is retryable.

        Args:
            exception: The exception that was raised.

        Returns:
            True if the exception is in the retryable list.
        """
        return isinstance(exception, self._retryable_exceptions)

    def wrap(self, func: Callable[P, T]) -> Callable[P, T]:
        """Decorator to wrap a function with retry logic.

        Args:
            func: Function to wrap.

        Returns:
            Wrapped function that retries on transient failures.

        Example:
            >>> @policy.wrap
            >>> def fetch_artifact():
            ...     return client.pull(tag="v1.0.0")
        """

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(self._config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not self.should_retry(e):
                        raise

                    last_exception = e
                    remaining = self._config.max_attempts - attempt - 1

                    if remaining > 0:
                        delay = self.calculate_delay(attempt)
                        logger.debug(
                            "retry_attempt",
                            attempt=attempt + 1,
                            max_attempts=self._config.max_attempts,
                            delay_seconds=delay,
                            error=str(e),
                        )
                        time.sleep(delay)
                    else:
                        logger.warning(
                            "retry_exhausted",
                            attempts=self._config.max_attempts,
                            error=str(e),
                        )

            # Should not reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry exhausted without exception")

        return wrapper

    def attempts(self) -> RetryAttemptIterator:
        """Return an iterator for manual retry control.

        Useful when you need more control over retry logic.

        Yields:
            RetryAttempt objects for each attempt.

        Example:
            >>> for attempt in policy.attempts():
            ...     try:
            ...         result = risky_operation()
            ...         break
            ...     except TransientError as e:
            ...         if not attempt.should_retry(e):
            ...             raise
            ...         attempt.wait()
        """
        return RetryAttemptIterator(self)


class RetryAttemptIterator:
    """Iterator for manual retry control.

    Used by RetryPolicy.attempts() for fine-grained retry control.
    """

    def __init__(self, policy: RetryPolicy) -> None:
        """Initialize iterator with retry policy."""
        self._policy = policy
        self._attempt = 0

    def __iter__(self) -> RetryAttemptIterator:
        """Return self as iterator."""
        return self

    def __next__(self) -> RetryAttempt:
        """Return next retry attempt."""
        if self._attempt >= self._policy.config.max_attempts:
            raise StopIteration

        attempt = RetryAttempt(self._policy, self._attempt)
        self._attempt += 1
        return attempt


class RetryAttempt:
    """Single retry attempt with delay and tracking."""

    def __init__(self, policy: RetryPolicy, attempt_number: int) -> None:
        """Initialize retry attempt."""
        self._policy = policy
        self._attempt_number = attempt_number

    @property
    def attempt_number(self) -> int:
        """Return current attempt number (0-indexed)."""
        return self._attempt_number

    @property
    def is_last_attempt(self) -> bool:
        """Check if this is the last attempt."""
        return self._attempt_number >= self._policy.config.max_attempts - 1

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception is retryable and attempts remain."""
        return not self.is_last_attempt and self._policy.should_retry(exception)

    def wait(self) -> None:
        """Wait before the next retry attempt."""
        if not self.is_last_attempt:
            delay = self._policy.calculate_delay(self._attempt_number)
            logger.debug(
                "retry_wait",
                attempt=self._attempt_number + 1,
                delay_seconds=delay,
            )
            time.sleep(delay)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failures exceeded threshold, requests rejected
    HALF_OPEN = "half_open"  # Testing recovery, limited requests allowed


class CircuitBreaker:
    """Circuit breaker pattern for registry availability.

    Implements the three-state circuit breaker pattern:
    - CLOSED: Normal operation, all requests allowed
    - OPEN: Too many failures, requests fail fast without network call
    - HALF_OPEN: Testing recovery, limited probe requests allowed

    State Transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After recovery_timeout_ms elapses
    - HALF_OPEN -> CLOSED: On successful probe
    - HALF_OPEN -> OPEN: On failed probe

    Thread Safety:
        All state mutations are protected by a threading lock for
        safe concurrent access.

    Example:
        >>> circuit = CircuitBreaker("harbor.example.com")
        >>>
        >>> with circuit.protect():
        ...     result = fetch_from_registry()
        >>>
        >>> # Check state
        >>> if circuit.is_open:
        ...     print(f"Registry unavailable until {circuit.recovery_time}")

    Attributes:
        registry_uri: Registry identifier for logging/metrics.
        config: CircuitBreakerConfig with thresholds and timeouts.
        state: Current circuit state.
    """

    def __init__(
        self,
        registry_uri: str,
        config: CircuitBreakerConfig | None = None,
        *,
        metrics: OCIMetrics | None = None,
    ) -> None:
        """Initialize CircuitBreaker.

        Args:
            registry_uri: Registry URI for identification.
            config: Circuit breaker configuration. Uses defaults if None.
            metrics: Optional OCIMetrics instance for emitting metrics.
        """
        self._registry_uri = registry_uri
        self._config = config or CircuitBreakerConfig()
        self._metrics = metrics
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_requests = 0
        self._lock = threading.Lock()

        # Emit initial state metric
        self._emit_state_metric()

    @property
    def state(self) -> CircuitState:
        """Return current circuit state."""
        with self._lock:
            self._update_state()
            return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def failure_count(self) -> int:
        """Return current consecutive failure count."""
        return self._failure_count

    @property
    def recovery_time(self) -> datetime | None:
        """Return timestamp when circuit will transition to HALF_OPEN.

        Returns:
            Datetime when HALF_OPEN probing begins, or None if not OPEN.
        """
        with self._lock:
            if self._state != CircuitState.OPEN or self._last_failure_time is None:
                return None
            recovery_ms = self._config.recovery_timeout_ms
            return self._last_failure_time + timedelta(milliseconds=recovery_ms)

    def _emit_state_metric(self) -> None:
        """Emit circuit breaker state metric.

        Converts CircuitState to CircuitBreakerStateValue and emits via OCIMetrics.
        """
        if self._metrics is None:
            return

        from floe_core.oci.metrics import CircuitBreakerStateValue

        state_value_map = {
            CircuitState.CLOSED: CircuitBreakerStateValue.CLOSED,
            CircuitState.OPEN: CircuitBreakerStateValue.OPEN,
            CircuitState.HALF_OPEN: CircuitBreakerStateValue.HALF_OPEN,
        }

        state_value = state_value_map[self._state]
        self._metrics.set_circuit_breaker_state(
            registry=self._registry_uri,
            state=state_value,
            failure_count=self._failure_count,
        )

    def allow_request(self) -> bool:
        """Check if a request should be allowed.

        Updates state based on time elapsed since last failure.

        Returns:
            True if request is allowed, False if should fail fast.
        """
        if not self._config.enabled:
            return True

        with self._lock:
            self._update_state()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                return False

            # HALF_OPEN: allow limited probe requests
            if self._half_open_requests < self._config.half_open_requests:
                self._half_open_requests += 1
                logger.debug(
                    "circuit_half_open_probe",
                    registry=self._registry_uri,
                    probe_number=self._half_open_requests,
                )
                return True

            return False

    def record_success(self) -> None:
        """Record a successful request.

        Resets failure count and closes circuit if in HALF_OPEN state.
        """
        if not self._config.enabled:
            return

        with self._lock:
            state_changed = False
            if self._state == CircuitState.HALF_OPEN:
                # Probe succeeded, close circuit
                logger.info(
                    "circuit_closed",
                    registry=self._registry_uri,
                    previous_failures=self._failure_count,
                )
                self._state = CircuitState.CLOSED
                state_changed = True

            self._failure_count = 0
            self._success_count += 1

            if state_changed:
                self._emit_state_metric()

    def record_failure(self) -> None:
        """Record a failed request.

        Increments failure count and opens circuit if threshold exceeded.
        """
        if not self._config.enabled:
            return

        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)
            state_changed = False

            if self._state == CircuitState.HALF_OPEN:
                # Probe failed, reopen circuit
                logger.warning(
                    "circuit_reopened",
                    registry=self._registry_uri,
                    failure_count=self._failure_count,
                )
                self._state = CircuitState.OPEN
                self._half_open_requests = 0
                state_changed = True

            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self._config.failure_threshold
            ):
                # Too many failures, open circuit
                logger.warning(
                    "circuit_opened",
                    registry=self._registry_uri,
                    failure_count=self._failure_count,
                    recovery_timeout_ms=self._config.recovery_timeout_ms,
                )
                self._state = CircuitState.OPEN
                state_changed = True

            if state_changed:
                self._emit_state_metric()

    def _update_state(self) -> None:
        """Update state based on time elapsed.

        Transitions from OPEN to HALF_OPEN after recovery timeout.
        Must be called with lock held.
        """
        if self._state != CircuitState.OPEN:
            return

        if self._last_failure_time is None:
            return

        elapsed_ms = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds() * 1000

        if elapsed_ms >= self._config.recovery_timeout_ms:
            logger.info(
                "circuit_half_open",
                registry=self._registry_uri,
                elapsed_ms=elapsed_ms,
            )
            self._state = CircuitState.HALF_OPEN
            self._half_open_requests = 0
            self._emit_state_metric()

    @contextmanager
    def protect(self) -> Any:
        """Context manager for circuit breaker protection.

        Raises CircuitBreakerOpenError if circuit is open.
        Records success/failure based on whether exception is raised.

        Yields:
            None

        Raises:
            CircuitBreakerOpenError: If circuit is open and request not allowed.

        Example:
            >>> with circuit.protect():
            ...     result = risky_operation()
        """
        if not self.allow_request():
            recovery_at = self.recovery_time
            raise CircuitBreakerOpenError(
                registry=self._registry_uri,
                failure_count=self._failure_count,
                recovery_at=recovery_at.isoformat() if recovery_at else None,
            )

        try:
            yield
            self.record_success()
        except Exception:
            self.record_failure()
            raise

    def reset(self) -> None:
        """Reset circuit breaker to initial state.

        Useful for testing or manual recovery.
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_requests = 0
            logger.info(
                "circuit_reset",
                registry=self._registry_uri,
            )
            self._emit_state_metric()


def with_resilience(
    retry_config: RetryConfig | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator factory combining retry and circuit breaker.

    Creates a decorator that applies both retry policy and circuit breaker
    protection to a function.

    Args:
        retry_config: Retry configuration. Uses defaults if None.
        circuit_breaker: Circuit breaker instance. No circuit breaking if None.

    Returns:
        Decorator that applies resilience patterns.

    Example:
        >>> circuit = CircuitBreaker("harbor.example.com")
        >>>
        >>> @with_resilience(RetryConfig(max_attempts=3), circuit)
        >>> def fetch_artifact():
        ...     return client.pull(tag="v1.0.0")
    """
    retry_policy = RetryPolicy(retry_config)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if circuit_breaker is not None:
                with circuit_breaker.protect():
                    return retry_policy.wrap(func)(*args, **kwargs)
            return retry_policy.wrap(func)(*args, **kwargs)

        return wrapper

    return decorator
