"""LineageResource and NoOpLineageResource for Dagster lineage integration.

Provides synchronous wrappers around an async LineageEmitter, dispatching
coroutines to a dedicated daemon thread running its own asyncio event loop.
This lets Dagster assets emit OpenLineage events without blocking the
orchestrator's sync execution path.

Example:
    >>> from floe_orchestrator_dagster.resources.lineage import LineageResource
    >>>
    >>> @asset
    >>> def my_asset(lineage: LineageResource) -> None:
    ...     run_id = lineage.emit_start("my_asset")
    ...     # ... do work ...
    ...     lineage.emit_complete(run_id, "my_asset")
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from floe_core.lineage.emitter import LineageEmitter

_EMIT_TIMEOUT = 5.0

logger = logging.getLogger(__name__)


class LineageResource:
    """Synchronous Dagster resource wrapping an async LineageEmitter.

    Runs a dedicated daemon thread with its own asyncio event loop so that
    coroutines from the emitter can be submitted from any synchronous thread
    via ``asyncio.run_coroutine_threadsafe``.

    Args:
        emitter: An async LineageEmitter instance whose methods are dispatched
            to the background loop.
    """

    def __init__(self, emitter: LineageEmitter) -> None:
        """Initialise the resource and start the background event loop thread.

        Args:
            emitter: The async LineageEmitter to delegate to.
        """
        self._emitter = emitter
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_coroutine(self, coro: Any, *, default: Any = None) -> Any:
        """Submit *coro* to the background loop and block until it completes.

        Returns the coroutine's result, or *default* on timeout/exception.

        Args:
            coro: Awaitable coroutine to submit.
            default: Value to return when the coroutine fails or times out.

        Returns:
            The coroutine result, or *default* on failure.
        """
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=_EMIT_TIMEOUT)
        except TimeoutError:
            logger.warning(
                "lineage_emit_timeout",
                extra={"timeout": _EMIT_TIMEOUT},
            )
            return default
        except Exception as exc:
            logger.warning(
                "lineage_emit_error",
                extra={"error": str(exc)},
            )
            return default

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def namespace(self) -> str:
        """Return the emitter's default namespace.

        Returns:
            The default namespace string from the underlying emitter.
        """
        return str(self._emitter.default_namespace)

    def emit_start(
        self,
        job_name: str,
        *,
        inputs: list[Any] | None = None,
        outputs: list[Any] | None = None,
        run_facets: dict[str, Any] | None = None,
        job_facets: dict[str, Any] | None = None,
    ) -> UUID:
        """Emit a START event for a lineage run.

        Args:
            job_name: Name of the job/asset being started.
            inputs: Optional list of input datasets.
            outputs: Optional list of output datasets.
            run_facets: Optional run-level facets.
            job_facets: Optional job-level facets.

        Returns:
            The UUID identifying this lineage run.  On failure a fresh UUID is
            returned so callers always receive a valid handle.
        """
        if self._closed:
            logger.warning("lineage_resource_closed: emit_start called after close")
            return uuid4()

        fallback = uuid4()
        result = self._run_coroutine(
            self._emitter.emit_start(
                job_name,
                inputs=inputs,
                outputs=outputs,
                run_facets=run_facets,
                job_facets=job_facets,
            ),
            default=fallback,
        )
        if isinstance(result, UUID):
            return result
        return fallback

    def emit_complete(
        self,
        run_id: UUID,
        job_name: str,
        *,
        outputs: list[Any] | None = None,
        run_facets: dict[str, Any] | None = None,
        job_facets: dict[str, Any] | None = None,
    ) -> None:
        """Emit a COMPLETE event for a lineage run.

        Args:
            run_id: UUID returned by a prior ``emit_start`` call.
            job_name: Name of the job/asset that completed.
            outputs: Optional list of output datasets.
            run_facets: Optional run-level facets.
            job_facets: Optional job-level facets.
        """
        if self._closed:
            logger.warning("lineage_resource_closed: emit_complete called after close")
            return

        self._run_coroutine(
            self._emitter.emit_complete(
                run_id,
                job_name,
                outputs=outputs,
                run_facets=run_facets,
                job_facets=job_facets,
            ),
        )

    def emit_fail(
        self,
        run_id: UUID,
        job_name: str,
        *,
        error_message: str | None = None,
        run_facets: dict[str, Any] | None = None,
    ) -> None:
        """Emit a FAIL event for a lineage run.

        Args:
            run_id: UUID returned by a prior ``emit_start`` call.
            job_name: Name of the job/asset that failed.
            error_message: Optional human-readable error description.
            run_facets: Optional run-level facets.
        """
        if self._closed:
            logger.warning("lineage_resource_closed: emit_fail called after close")
            return

        self._run_coroutine(
            self._emitter.emit_fail(
                run_id,
                job_name,
                error_message=error_message,
                run_facets=run_facets,
            ),
        )

    def emit_event(self, event: Any) -> None:
        """Forward a pre-built LineageEvent directly to the transport.

        Unlike ``emit_start``/``emit_complete``/``emit_fail``, this method
        bypasses the emitter's high-level methods and calls
        ``transport.emit`` directly.

        Args:
            event: A fully-constructed LineageEvent object.
        """
        if self._closed:
            logger.warning("lineage_resource_closed: emit_event called after close")
            return

        transport_emit = self._emitter.transport.emit
        result = transport_emit(event)
        # If transport.emit is async (production), dispatch the coroutine
        if asyncio.iscoroutine(result):
            self._run_coroutine(result)

    def close(self) -> None:
        """Drain the emitter, stop the background loop, and join the thread.

        Safe to call multiple times (idempotent).
        """
        if self._closed:
            return
        self._closed = True

        self._emitter.close()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=_EMIT_TIMEOUT)


class NoOpLineageResource:
    """A no-op LineageResource that discards all emissions.

    Intended for use when lineage tracking is disabled or not configured.
    All methods accept the same signatures as ``LineageResource`` but perform
    no work.
    """

    @property
    def namespace(self) -> str:
        """Return the default namespace string.

        Returns:
            Always ``"default"``.
        """
        return "default"

    def emit_start(self, job_name: str, **kwargs: Any) -> UUID:
        """Return a fresh UUID without emitting anything.

        Args:
            job_name: Ignored.
            **kwargs: Ignored.

        Returns:
            A new unique UUID.
        """
        return uuid4()

    def emit_complete(self, run_id: UUID, job_name: str, **kwargs: Any) -> None:
        """No-op.

        Args:
            run_id: Ignored.
            job_name: Ignored.
            **kwargs: Ignored.
        """

    def emit_fail(self, run_id: UUID, job_name: str, **kwargs: Any) -> None:
        """No-op.

        Args:
            run_id: Ignored.
            job_name: Ignored.
            **kwargs: Ignored.
        """

    def emit_event(self, event: Any) -> None:
        """No-op.

        Args:
            event: Ignored.
        """

    def close(self) -> None:
        """No-op. Safe to call multiple times."""
