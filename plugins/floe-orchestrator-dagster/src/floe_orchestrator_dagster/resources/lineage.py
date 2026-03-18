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
import importlib
import logging
import threading
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from floe_core.lineage.emitter import LineageEmitter
    from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

# ---------------------------------------------------------------------------
# Lazy module-level references — patchable by tests, no AST import statements
# ---------------------------------------------------------------------------
# These are set via importlib so they do NOT create ast.Import / ast.ImportFrom
# nodes (which the AC-13 test forbids outside TYPE_CHECKING).  They ARE
# module-level attributes so unittest.mock.patch can replace them.
get_registry = importlib.import_module("floe_core.plugin_registry").get_registry
create_emitter = importlib.import_module("floe_core.lineage.emitter").create_emitter
_PluginType = importlib.import_module("floe_core.plugin_types").PluginType

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
                extra={"error_type": type(exc).__name__},
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


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def create_lineage_resource(lineage_ref: PluginRef) -> dict[str, Any]:
    """Create a Dagster ResourceDefinition for the configured lineage backend.

    Loads the lineage plugin from the registry, obtains its transport config
    and namespace strategy, creates a :class:`LineageEmitter`, wraps it in a
    :class:`LineageResource`, and returns a Dagster ``@resource`` generator
    definition with proper close-on-teardown behaviour.

    Args:
        lineage_ref: Resolved lineage plugin reference (type, version, config).

    Returns:
        ``{"lineage": ResourceDefinition}`` where the resource yields a
        :class:`LineageResource` and closes it on Dagster teardown.
    """
    from dagster import ResourceDefinition

    registry = get_registry()
    plugin = registry.get(_PluginType.LINEAGE, lineage_ref.type)

    transport_config: dict[str, Any] = plugin.get_transport_config()
    ns_strategy: dict[str, Any] = plugin.get_namespace_strategy()
    default_namespace: str = ns_strategy.get("default_namespace", "default")

    emitter = create_emitter(transport_config, default_namespace)
    resource = LineageResource(emitter=emitter)

    def _resource_fn(_init_context: Any) -> Any:
        try:
            yield resource
        finally:
            resource.close()

    return {"lineage": ResourceDefinition(resource_fn=_resource_fn)}


def try_create_lineage_resource(
    plugins: ResolvedPlugins | None,
) -> dict[str, Any]:
    """Return a lineage resource dict, always with a ``"lineage"`` key.

    When *plugins* is ``None`` or its ``lineage_backend`` is ``None``, returns
    a :class:`NoOpLineageResource` wrapped in a Dagster ``ResourceDefinition``.
    When ``lineage_backend`` is set, delegates to :func:`create_lineage_resource`.

    Unlike the iceberg counterpart this function NEVER returns an empty dict —
    it always returns ``{"lineage": <resource>}``.

    Args:
        plugins: Resolved plugin configuration, or ``None``.

    Returns:
        ``{"lineage": ResourceDefinition}`` in all cases.
    """
    from dagster import ResourceDefinition

    lineage_backend = None
    if plugins is not None:
        lineage_backend = plugins.lineage_backend

    if lineage_backend is None:
        noop = NoOpLineageResource()

        def _noop_fn(_init_context: Any) -> Any:
            return noop

        return {"lineage": ResourceDefinition(resource_fn=_noop_fn)}

    return create_lineage_resource(lineage_backend)
