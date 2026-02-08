"""Retry utilities for Polaris catalog operations.

This module provides retry decorators and utilities with exponential backoff
for handling transient failures when communicating with Polaris.

Example:
    >>> from floe_catalog_polaris.retry import create_retry_decorator
    >>> retry = create_retry_decorator(max_retries=5)
    >>> @retry
    ... def connect():
    ...     # Connect to Polaris
    ...     pass

Requirements Covered:
    - FR-033: System MUST support retry logic with configurable backoff
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

import structlog
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from tenacity import WrappedFn

logger = structlog.get_logger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Exceptions that should trigger retry (transient failures)
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempt details for observability.

    Args:
        retry_state: Tenacity retry state containing attempt info.
    """
    attempt = retry_state.attempt_number
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    error_type = type(exception).__name__ if exception else "unknown"
    error_msg = str(exception) if exception else "unknown"

    logger.warning(
        "catalog_operation_retry",
        attempt=attempt,
        error_type=error_type,
        error_message=error_msg,
        next_wait_seconds=(retry_state.next_action.sleep if retry_state.next_action else 0),
    )


def create_retry_decorator(
    max_retries: int = 5,
    min_wait_seconds: float = 1.0,
    max_wait_seconds: float = 30.0,
    multiplier: float = 2.0,
) -> Callable[[F], F]:
    """Create a retry decorator with exponential backoff.

    Creates a tenacity retry decorator configured with exponential backoff
    for handling transient failures. Only retries on specific exception types
    that indicate recoverable errors (connection issues, timeouts).

    Args:
        max_retries: Maximum number of retry attempts (0 disables retry).
        min_wait_seconds: Minimum wait time between retries.
        max_wait_seconds: Maximum wait time between retries.
        multiplier: Exponential backoff multiplier.

    Returns:
        A retry decorator function that can be applied to callables.

    Example:
        >>> retry = create_retry_decorator(max_retries=3, min_wait_seconds=0.5)
        >>> @retry
        ... def connect_to_catalog():
        ...     # May raise ConnectionError on transient failure
        ...     pass
    """
    if max_retries == 0:
        # No retries - return identity decorator
        def no_retry(func: F) -> F:
            return func

        return no_retry

    return retry(
        # stop_after_attempt counts total attempts, not retries.
        # If max_retries=3, we want: 1 initial attempt + 3 retries = 4 total attempts.
        stop=stop_after_attempt(max_retries + 1),
        wait=wait_exponential(
            multiplier=multiplier,
            min=min_wait_seconds,
            max=max_wait_seconds,
        ),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=_log_retry_attempt,
        reraise=True,
    )


def with_retry(
    func: WrappedFn,
    max_retries: int = 5,
    min_wait_seconds: float = 1.0,
    max_wait_seconds: float = 30.0,
) -> WrappedFn:
    """Apply retry logic to a function.

    Convenience function for applying retry logic without decorator syntax.
    Useful when retry parameters need to be determined at runtime.

    Args:
        func: The function to wrap with retry logic.
        max_retries: Maximum number of retry attempts.
        min_wait_seconds: Minimum wait time between retries.
        max_wait_seconds: Maximum wait time between retries.

    Returns:
        The wrapped function with retry logic applied.

    Example:
        >>> def connect():
        ...     # Connect to catalog
        ...     pass
        >>> connect_with_retry = with_retry(connect, max_retries=3)
        >>> connect_with_retry()
    """
    decorator = create_retry_decorator(
        max_retries=max_retries,
        min_wait_seconds=min_wait_seconds,
        max_wait_seconds=max_wait_seconds,
    )
    return decorator(func)
