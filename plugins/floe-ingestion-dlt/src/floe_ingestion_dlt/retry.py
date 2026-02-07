"""Retry logic with error categorization for the dlt ingestion plugin.

This module provides error categorization and retry decorator creation
using tenacity for exponential backoff on transient errors.

The categorization maps dlt and Python standard library exceptions to
one of four categories (TRANSIENT, PERMANENT, PARTIAL, CONFIGURATION)
which determines retry behavior.

Example:
    >>> from floe_ingestion_dlt.retry import categorize_error, create_retry_decorator
    >>> from floe_ingestion_dlt.config import RetryConfig
    >>> retry = create_retry_decorator(RetryConfig())
    >>> @retry
    ... def load_data():
    ...     pass

Requirements Covered:
    - FR-051: Error categorization with concrete criteria
    - FR-052: TRANSIENT errors retried with exponential backoff
    - FR-053: PERMANENT errors fail immediately
    - FR-054: Configurable max_retries and initial_delay_seconds
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import structlog
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from floe_ingestion_dlt.errors import ErrorCategory, IngestionError

if TYPE_CHECKING:
    from collections.abc import Callable

    from floe_ingestion_dlt.config import RetryConfig

logger = structlog.get_logger(__name__)

# HTTP status codes that indicate transient errors (retryable)
TRANSIENT_HTTP_CODES = frozenset({408, 429, 500, 502, 503, 504})

# HTTP status codes that indicate permanent errors (not retryable)
PERMANENT_HTTP_CODES = frozenset({400, 401, 403, 404, 405, 422})

__all__ = [
    "categorize_error",
    "create_retry_decorator",
    "is_retryable",
]


def categorize_error(error: BaseException) -> ErrorCategory:
    """Categorize an exception for retry decisions.

    Maps dlt exceptions and standard Python exceptions to an ErrorCategory
    based on concrete criteria defined in FR-051.

    Categorization rules:
        - TRANSIENT: HTTP 429/503, network timeout, connection reset,
          OSError, ConnectionError, TimeoutError
        - PERMANENT: HTTP 401/403, PermissionError, KeyError (missing resource),
          authentication failures
        - PARTIAL: Errors from IngestionError with PARTIAL category
        - CONFIGURATION: HTTP 400/404, ValueError, ImportError,
          ModuleNotFoundError, invalid config

    Args:
        error: The exception to categorize.

    Returns:
        The ErrorCategory for the given exception.

    Example:
        >>> categorize_error(TimeoutError("connection timed out"))
        <ErrorCategory.TRANSIENT: 'transient'>
        >>> categorize_error(PermissionError("access denied"))
        <ErrorCategory.PERMANENT: 'permanent'>
    """
    # If it's already an IngestionError, use its category
    if isinstance(error, IngestionError):
        return error.category

    # Check for HTTP status code in the error (common in dlt/httpx errors)
    http_code = _extract_http_status(error)
    if http_code is not None:
        if http_code in TRANSIENT_HTTP_CODES:
            return ErrorCategory.TRANSIENT
        if http_code in PERMANENT_HTTP_CODES:
            return ErrorCategory.PERMANENT

    # Permission errors are permanent (check before OSError, since it's a subclass)
    if isinstance(error, PermissionError):
        return ErrorCategory.PERMANENT

    # Network/connection errors are transient
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return ErrorCategory.TRANSIENT

    # Import errors are configuration issues
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return ErrorCategory.CONFIGURATION

    # Validation errors are configuration issues
    if isinstance(error, (ValueError, TypeError)):
        return ErrorCategory.CONFIGURATION

    # Key/attribute errors are usually permanent (missing resource)
    if isinstance(error, (KeyError, AttributeError)):
        return ErrorCategory.PERMANENT

    # Default: treat unknown errors as permanent (fail-fast is safer)
    return ErrorCategory.PERMANENT


def is_retryable(error: BaseException) -> bool:
    """Check if an error should be retried.

    Only TRANSIENT and PARTIAL errors are retried. PERMANENT and
    CONFIGURATION errors fail immediately.

    Args:
        error: The exception to check.

    Returns:
        True if the error should be retried.

    Example:
        >>> is_retryable(TimeoutError("timed out"))
        True
        >>> is_retryable(PermissionError("denied"))
        False
    """
    category = categorize_error(error)
    return category in (ErrorCategory.TRANSIENT, ErrorCategory.PARTIAL)


def create_retry_decorator(
    retry_config: RetryConfig,
) -> Callable[..., Any]:
    """Create a tenacity retry decorator from RetryConfig.

    Configures exponential backoff retry that only retries TRANSIENT
    and PARTIAL errors. PERMANENT and CONFIGURATION errors fail immediately.

    Args:
        retry_config: Configuration with max_retries and initial_delay_seconds.

    Returns:
        A tenacity retry decorator.

    Example:
        >>> from floe_ingestion_dlt.config import RetryConfig
        >>> retry_decorator = create_retry_decorator(RetryConfig(max_retries=5))
        >>> @retry_decorator
        ... def load_data():
        ...     pass
    """
    return retry(
        retry=retry_if_exception(is_retryable),
        stop=stop_after_attempt(retry_config.max_retries + 1),
        wait=wait_exponential(
            multiplier=retry_config.initial_delay_seconds,
            min=retry_config.initial_delay_seconds,
            max=60.0,
        ),
        before_sleep=_log_retry_attempt,
        reraise=True,
    )


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempts with structured logging.

    Args:
        retry_state: Tenacity retry state with attempt information.
    """
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    attempt = retry_state.attempt_number
    next_wait = retry_state.next_action.sleep if retry_state.next_action else 0

    logger.warning(
        "retrying_after_error",
        attempt=attempt,
        next_wait_seconds=round(next_wait, 2),
        error_type=type(exception).__name__ if exception else "unknown",
        error_category=categorize_error(exception).value if exception else "unknown",
    )


def _extract_http_status(error: BaseException) -> int | None:
    """Extract HTTP status code from an exception if available.

    Handles common HTTP exception patterns from httpx, requests,
    and dlt's internal error types.

    Args:
        error: The exception to inspect.

    Returns:
        HTTP status code if found, None otherwise.
    """
    # Check for status_code attribute (httpx, requests)
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    # Check for response.status_code (httpx, requests)
    response = getattr(error, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code

    # Check for errno/code attribute
    code_attr = getattr(error, "code", None)
    if isinstance(code_attr, int) and 100 <= code_attr <= 599:
        return code_attr

    return None
