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
import os
import ssl
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import structlog

from floe_core.lineage.events import to_openlineage_event
from floe_core.lineage.types import LineageEvent

if TYPE_CHECKING:
    from floe_core.lineage.protocols import LineageTransport

logger = logging.getLogger(__name__)

_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})
_DEFAULT_QUEUE_SIZE = 1000


def _create_ssl_context(url: str, verify_ssl: bool) -> ssl.SSLContext | None:
    """Create SSL context with environment-aware security controls.

    Production environment ALWAYS enforces SSL verification.
    Development requires FLOE_ALLOW_INSECURE_SSL=true to disable.
    """
    if not url.startswith("https://"):
        return None

    import certifi

    context = ssl.create_default_context(cafile=certifi.where())

    if os.environ.get("FLOE_ENVIRONMENT") == "production":
        return context

    if not verify_ssl:
        allow_insecure = os.environ.get("FLOE_ALLOW_INSECURE_SSL", "").lower() == "true"
        if not allow_insecure:
            logger.warning(
                "SSL verification disabled but FLOE_ALLOW_INSECURE_SSL not set - "
                "verification will remain enabled"
            )
            return context
        logger.critical(
            "SSL verification DISABLED - this should only be used in development "
            "with self-signed certificates"
        )
        _apply_insecure_settings(context)

    return context


def _apply_insecure_settings(context: ssl.SSLContext) -> None:
    """Apply insecure SSL settings. Development use only."""
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE


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

    async def close_async(self) -> None:
        """No-op async close."""


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

    async def close_async(self) -> None:
        """No-op async close."""


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

    async def close_async(self) -> None:
        """Async close all child transports."""
        for transport in self._transports:
            try:
                await transport.close_async()
            except Exception:
                logger.exception(
                    "Child transport failed to close_async",
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
        verify_ssl: Whether to verify SSL certificates (default: True).
        max_queue_size: Maximum queue size before dropping events (default: 1000).
    """

    def __init__(
        self,
        url: str,
        timeout: float = 5.0,
        api_key: str | None = None,
        verify_ssl: bool = True,
        max_queue_size: int = _DEFAULT_QUEUE_SIZE,
    ) -> None:
        """Initialize HTTP transport.

        Args:
            url: HTTP endpoint URL.
            timeout: Request timeout in seconds.
            api_key: Optional API key for authentication header.
            verify_ssl: Whether to verify SSL certificates.
            max_queue_size: Maximum queue size before dropping events.

        Raises:
            ValueError: If URL is invalid or uses unsupported scheme.
        """
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_URL_SCHEMES:
            raise ValueError(
                f"URL scheme must be one of {sorted(_ALLOWED_URL_SCHEMES)}, got: {parsed.scheme!r}"
            )
        if not parsed.netloc:
            raise ValueError(f"Invalid URL: missing host in {url!r}")

        # Strip userinfo (credentials) from URL for defense-in-depth
        if parsed.username or parsed.password:
            clean_netloc = parsed.hostname or ""
            if parsed.port:
                clean_netloc += f":{parsed.port}"
            url = f"{parsed.scheme}://{clean_netloc}{parsed.path}"
            if parsed.query:
                url += f"?{parsed.query}"
            if parsed.fragment:
                url += f"#{parsed.fragment}"

        self._url = url
        self._timeout = timeout
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._closed = False

        self._async_queue: asyncio.Queue[LineageEvent | None] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._consumer_task: asyncio.Task[None] | None = None

    def _sanitized_url(self) -> str:
        """Return URL without query string for safe logging."""
        parsed = urlparse(self._url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    async def emit(self, event: LineageEvent) -> None:
        """Enqueue event for async emission (non-blocking, <1ms).

        Args:
            event: The lineage event to emit.
        """
        if self._closed:
            return

        self._ensure_consumer()
        try:
            self._async_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Lineage queue full, dropping event",
                extra={
                    "url": self._sanitized_url(),
                    "queue_size": self._async_queue.maxsize,
                    "run_id": str(event.run.run_id),
                },
            )

    def _ensure_consumer(self) -> None:
        """Start background consumer task if not already running."""
        if self._consumer_task is not None and not self._consumer_task.done():
            return

        loop = asyncio.get_running_loop()
        self._consumer_task = loop.create_task(self._consume_async())

    async def _consume_async(self) -> None:
        """Background consumer that posts events via httpx."""
        import importlib.util

        httpx_available = importlib.util.find_spec("httpx") is not None

        while True:
            event = await self._async_queue.get()
            if event is None:
                break
            await self._post_event(event, httpx_available)

    async def _post_event(self, event: LineageEvent, httpx_available: bool) -> None:
        """Post a single event via HTTP.

        Args:
            event: Event to post.
            httpx_available: Whether httpx module is available.
        """
        payload = to_openlineage_event(event)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        ssl_context = _create_ssl_context(self._url, self._verify_ssl)

        try:
            if httpx_available:
                import httpx

                verify_setting = ssl_context if ssl_context is not None else True
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    verify=verify_setting,
                ) as client:
                    await client.post(
                        self._url,
                        json=payload,
                        headers=headers,
                    )
            else:
                import urllib.request

                req = urllib.request.Request(
                    self._url,
                    data=json.dumps(payload).encode(),
                    headers=headers,
                    method="POST",
                )
                urllib.request.urlopen(  # noqa: S310  # nosec B310
                    req, timeout=self._timeout, context=ssl_context
                )
        except ssl.SSLError:
            logger.exception(
                "SSL/TLS error posting lineage event - check certificates",
                extra={"url": self._sanitized_url()},
            )
        except Exception:
            logger.exception(
                "Failed to post lineage event",
                extra={
                    "url": self._sanitized_url(),
                    "run_id": str(event.run.run_id),
                    "job_name": event.job.name,
                },
            )

    def close(self) -> None:
        """Signal consumer to stop (non-blocking).

        For guaranteed drain completion, use close_async() instead.
        """
        self._closed = True

        try:
            self._async_queue.put_nowait(None)
        except asyncio.QueueFull:
            logger.warning("Queue full during close, some events may be lost")

    async def close_async(self) -> None:
        """Drain queue and wait for consumer task to complete.

        Use this when you need to ensure all queued events are sent
        before proceeding (e.g., in tests or graceful shutdown).
        """
        self._closed = True

        try:
            self._async_queue.put_nowait(None)
        except asyncio.QueueFull:
            logger.warning("Queue full during close, some events may be lost")

        if self._consumer_task is not None:
            await self._consumer_task
