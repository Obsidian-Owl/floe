"""Lineage event transport implementations.

Provides pluggable transports for emitting OpenLineage events to backends
(Marquez, Atlan, console, etc.). All transports implement the LineageTransport
protocol.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import structlog

from floe_core.lineage.events import to_openlineage_event
from floe_core.lineage.types import LineageEvent

if TYPE_CHECKING:
    from floe_core.lineage.protocols import LineageTransport

logger = logging.getLogger(__name__)


class NoOpLineageTransport:
    """Transport that discards all events.

    Useful for testing and environments where lineage collection
    is disabled.
    """

    async def emit(self, event: LineageEvent) -> None:
        """Discard the event.

        Args:
            event: The lineage event (ignored).
        """

    def close(self) -> None:
        """No-op close."""


class ConsoleLineageTransport:
    """Transport that logs events as JSON via structlog.

    Useful for local development and debugging.
    """

    def __init__(self) -> None:
        """Initialize with structlog logger."""
        self._log: structlog.stdlib.BoundLogger = structlog.get_logger("floe.lineage.console")

    async def emit(self, event: LineageEvent) -> None:
        """Log the event as JSON via structlog.

        Args:
            event: The lineage event to log.
        """
        self._log.info(
            "lineage_event",
            event_type=event.event_type.value,
            job_namespace=event.job.namespace,
            job_name=event.job.name,
            run_id=str(event.run.run_id),
            producer=event.producer,
            inputs_count=len(event.inputs),
            outputs_count=len(event.outputs),
        )

    def close(self) -> None:
        """No-op close."""


class CompositeLineageTransport:
    """Transport that fans out events to multiple child transports.

    Individual transport failures are caught and logged, never propagated.

    Args:
        transports: List of child transports to fan out to.
    """

    def __init__(self, transports: list[LineageTransport]) -> None:
        """Initialize with child transports.

        Args:
            transports: Child transports to fan out to.
        """
        self._transports = list(transports)

    async def emit(self, event: LineageEvent) -> None:
        """Fan out event to all child transports.

        Individual failures are caught and logged.

        Args:
            event: The lineage event to emit.
        """
        for transport in self._transports:
            try:
                await transport.emit(event)
            except Exception:
                logger.exception(
                    "Child transport failed to emit event",
                    extra={"transport": type(transport).__name__},
                )

    def close(self) -> None:
        """Close all child transports."""
        for transport in self._transports:
            try:
                transport.close()
            except Exception:
                logger.exception(
                    "Child transport failed to close",
                    extra={"transport": type(transport).__name__},
                )


class HttpLineageTransport:
    """Non-blocking HTTP transport for lineage events.

    Uses an asyncio.Queue with a background consumer task for fire-and-forget
    emission. The emit() method enqueues events and returns immediately.

    Args:
        url: HTTP endpoint URL for lineage events.
        timeout: HTTP request timeout in seconds.
        api_key: Optional API key for authentication.
    """

    def __init__(
        self,
        url: str,
        timeout: float = 5.0,
        api_key: str | None = None,
    ) -> None:
        """Initialize HTTP transport.

        Args:
            url: HTTP endpoint URL.
            timeout: Request timeout in seconds.
            api_key: Optional API key for authentication header.
        """
        self._url = url
        self._timeout = timeout
        self._api_key = api_key
        self._closed = False

        self._async_queue: asyncio.Queue[LineageEvent | None] = asyncio.Queue()
        self._consumer_task: asyncio.Task[None] | None = None

    async def emit(self, event: LineageEvent) -> None:
        """Enqueue event for async emission (non-blocking, <1ms).

        Args:
            event: The lineage event to emit.
        """
        if self._closed:
            return

        # Ensure background consumer is running
        self._ensure_consumer()
        await self._async_queue.put(event)

    def _ensure_consumer(self) -> None:
        """Start background consumer task if not already running."""
        if self._consumer_task is not None and not self._consumer_task.done():
            return

        loop = asyncio.get_running_loop()
        self._consumer_task = loop.create_task(self._consume_async())

    async def _consume_async(self) -> None:
        """Background consumer that posts events via httpx."""
        try:
            import httpx
        except ImportError:
            httpx = None  # type: ignore[assignment]

        while True:
            event = await self._async_queue.get()
            if event is None:
                break
            await self._post_event(event, httpx)

    async def _post_event(self, event: LineageEvent, httpx_mod: object | None) -> None:
        """Post a single event via HTTP.

        Args:
            event: Event to post.
            httpx_mod: The httpx module if available, else None.
        """
        payload = to_openlineage_event(event)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            if httpx_mod is not None:
                import httpx

                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    await client.post(
                        self._url,
                        json=payload,
                        headers=headers,
                    )
            else:
                # Fallback to urllib
                import urllib.request

                req = urllib.request.Request(
                    self._url,
                    data=json.dumps(payload).encode(),
                    headers=headers,
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=self._timeout)  # noqa: S310  # nosec B310
        except Exception:
            logger.exception(
                "Failed to post lineage event",
                extra={"url": self._url},
            )

    def close(self) -> None:
        """Signal consumer to stop (non-blocking).

        For guaranteed drain completion, use close_async() instead.
        """
        self._closed = True

        try:
            self._async_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    async def close_async(self) -> None:
        """Drain queue and wait for consumer task to complete.

        Use this when you need to ensure all queued events are sent
        before proceeding (e.g., in tests or graceful shutdown).
        """
        self._closed = True

        try:
            self._async_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

        if self._consumer_task is not None:
            await self._consumer_task
