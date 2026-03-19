"""Thread-safe tracer factory with ProxyTracer auto-upgrade support.

This module provides a centralized, thread-safe tracer cache that handles:
- Lazy initialization with double-checked locking
- Graceful fallback to NoOpTracer on initialization failure
- Test isolation via reset_tracer()

The cache stores ProxyTracer instances obtained from the OTel API via
``trace.get_tracer()``.  These proxies auto-upgrade to real SDK tracers
when ``set_tracer_provider()`` is called (e.g. by
``ensure_telemetry_initialized()``).  ``reset_tracer()`` clears the cache
to force fresh tracer acquisition after a provider reset.

All floe packages should import get_tracer and reset_tracer from this module
to ensure consistent behavior and proper thread-safety.

Contract Version: 1.0.0
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from opentelemetry import trace

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

# Module-level state for thread-safe tracer management
_tracers: dict[str, Tracer] = {}
_tracer_init_failed: bool = False
_lock = threading.Lock()


def get_tracer(name: str = "floe") -> Tracer:
    """Get or create a thread-safe tracer instance.

    Returns a cached tracer for the given name, creating it if necessary.
    Uses double-checked locking for thread-safe lazy initialization.

    Returns a NoOpTracer if OpenTelemetry initialization fails (e.g., due to
    corrupted global state from test fixtures or missing configuration).

    Args:
        name: The tracer name (instrumenting module name). Defaults to "floe".
              Each unique name gets its own tracer instance.

    Returns:
        OpenTelemetry Tracer instance for the given name.

    Example:
        >>> tracer = get_tracer("floe_core.telemetry")
        >>> with tracer.start_as_current_span("my_operation"):
        ...     pass
    """
    global _tracer_init_failed

    # Fast path: return cached tracer without lock
    if name in _tracers:
        return _tracers[name]

    # If initialization already failed, return NoOp without trying again
    if _tracer_init_failed:
        return trace.NoOpTracer()

    # Slow path: acquire lock and initialize
    with _lock:
        # Double-check after acquiring lock
        if name in _tracers:
            return _tracers[name]

        if _tracer_init_failed:
            return trace.NoOpTracer()

        try:
            tracer = trace.get_tracer(name)
            _tracers[name] = tracer
            return tracer
        except RecursionError:
            # OTel global state corrupted (common in test environments)
            _tracer_init_failed = True
            return trace.NoOpTracer()
        except Exception as exc:
            # Log type only — never str(exc) to avoid credential leak (S-VI).
            import structlog

            structlog.get_logger(__name__).warning(
                "tracer_init_failed",
                exc_type=type(exc).__name__,
            )
            _tracer_init_failed = True
            return trace.NoOpTracer()


def set_tracer(name: str, tracer: Tracer | None) -> None:
    """Set or clear a tracer for a specific name (for testing).

    Allows tests to inject mock tracers for specific tracer names.
    Pass None to remove a cached tracer.

    Args:
        name: The tracer name to set.
        tracer: The tracer instance to use, or None to clear.

    Example:
        >>> from unittest.mock import MagicMock
        >>> mock_tracer = MagicMock(spec=Tracer)
        >>> set_tracer("floe_core.telemetry", mock_tracer)
    """
    with _lock:
        if tracer is None:
            _tracers.pop(name, None)
        else:
            _tracers[name] = tracer


def reset_tracer() -> None:
    """Reset tracer state for test isolation.

    Clears all cached tracers and resets the initialization failure flag.
    Call this in test fixtures to ensure clean tracer state between tests.

    Example:
        >>> @pytest.fixture(autouse=True)
        ... def reset_otel():
        ...     reset_tracer()
        ...     yield
        ...     reset_tracer()
    """
    global _tracer_init_failed
    with _lock:
        _tracers.clear()
        _tracer_init_failed = False


__all__ = ["get_tracer", "set_tracer", "reset_tracer"]
