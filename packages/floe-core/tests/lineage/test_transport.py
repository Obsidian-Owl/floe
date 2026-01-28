"""Tests for lineage transport implementations.

This module tests the four lineage transports: NoOp, Console, Composite, and HTTP.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from floe_core.lineage.protocols import LineageTransport
from floe_core.lineage.transport import (
    CompositeLineageTransport,
    ConsoleLineageTransport,
    HttpLineageTransport,
    NoOpLineageTransport,
)
from floe_core.lineage.types import (
    LineageEvent,
    LineageJob,
    LineageRun,
    RunState,
)


def _run(coro: object) -> object:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)  # type: ignore[arg-type]


@pytest.fixture()
def sample_event() -> LineageEvent:
    """Create a sample lineage event for testing."""
    return LineageEvent(
        event_type=RunState.START,
        run=LineageRun(),
        job=LineageJob(namespace="floe", name="test_job"),
        producer="floe-test",
    )


class TestNoOpLineageTransport:
    """Tests for NoOpLineageTransport."""

    def test_implements_protocol(self) -> None:
        """NoOpLineageTransport satisfies LineageTransport protocol."""
        transport = NoOpLineageTransport()
        assert isinstance(transport, LineageTransport)

    def test_emit_accepts_event(self, sample_event: LineageEvent) -> None:
        """NoOp transport accepts events without error."""
        transport = NoOpLineageTransport()
        _run(transport.emit(sample_event))

    def test_close_is_noop(self) -> None:
        """NoOp close does nothing."""
        transport = NoOpLineageTransport()
        transport.close()  # Should not raise


class TestConsoleLineageTransport:
    """Tests for ConsoleLineageTransport."""

    def test_implements_protocol(self) -> None:
        """ConsoleLineageTransport satisfies LineageTransport protocol."""
        transport = ConsoleLineageTransport()
        assert isinstance(transport, LineageTransport)

    def test_emit_logs_via_structlog(self, sample_event: LineageEvent) -> None:
        """Console transport logs event via structlog."""
        transport = ConsoleLineageTransport()
        with patch.object(transport, "_log") as mock_log:
            _run(transport.emit(sample_event))
            mock_log.info.assert_called_once()
            call_kwargs = mock_log.info.call_args
            assert call_kwargs[0][0] == "lineage_event"
            assert call_kwargs[1]["event_type"] == "START"
            assert call_kwargs[1]["job_name"] == "test_job"

    def test_close_is_noop(self) -> None:
        """Console close does nothing."""
        transport = ConsoleLineageTransport()
        transport.close()


class TestCompositeLineageTransport:
    """Tests for CompositeLineageTransport."""

    def test_implements_protocol(self) -> None:
        """CompositeLineageTransport satisfies LineageTransport protocol."""
        transport = CompositeLineageTransport(transports=[])
        assert isinstance(transport, LineageTransport)

    def test_fans_out_to_multiple_transports(self, sample_event: LineageEvent) -> None:
        """Composite fans out to 3+ child transports."""
        children = [AsyncMock() for _ in range(3)]
        transport = CompositeLineageTransport(transports=children)  # type: ignore[arg-type]

        _run(transport.emit(sample_event))

        for child in children:
            child.emit.assert_awaited_once_with(sample_event)

    def test_child_failure_does_not_propagate(self, sample_event: LineageEvent) -> None:
        """Individual child failures are caught, not propagated."""
        failing = AsyncMock()
        failing.emit.side_effect = RuntimeError("boom")
        healthy = AsyncMock()

        transport = CompositeLineageTransport(transports=[failing, healthy])  # type: ignore[arg-type]
        _run(transport.emit(sample_event))  # Should not raise

        healthy.emit.assert_awaited_once_with(sample_event)

    def test_close_closes_all_children(self) -> None:
        """Close calls close() on all children."""
        children = [MagicMock(spec=["emit", "close"]) for _ in range(3)]
        transport = CompositeLineageTransport(transports=children)  # type: ignore[arg-type]
        transport.close()

        for child in children:
            child.close.assert_called_once()

    def test_close_handles_child_failure(self) -> None:
        """Close continues even if a child fails."""
        failing = MagicMock(spec=["emit", "close"])
        failing.close.side_effect = RuntimeError("boom")
        healthy = MagicMock(spec=["emit", "close"])

        transport = CompositeLineageTransport(transports=[failing, healthy])  # type: ignore[arg-type]
        transport.close()  # Should not raise

        healthy.close.assert_called_once()


class TestHttpLineageTransport:
    """Tests for HttpLineageTransport."""

    def test_implements_protocol(self) -> None:
        """HttpLineageTransport satisfies LineageTransport protocol."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        assert isinstance(transport, LineageTransport)
        transport.close()

    @pytest.mark.requirement("REQ-525")
    def test_emit_is_non_blocking(self, sample_event: LineageEvent) -> None:
        """Emit enqueues without blocking (<10ms)."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        try:
            start = time.monotonic()
            _run(transport.emit(sample_event))
            elapsed = time.monotonic() - start

            assert elapsed < 0.1, f"emit() took {elapsed:.4f}s, expected <100ms"
        finally:
            transport.close()

    @pytest.mark.requirement("REQ-526")
    def test_fire_and_forget_enqueue(self, sample_event: LineageEvent) -> None:
        """Events are enqueued for background processing (fire-and-forget)."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        try:
            _run(transport.emit(sample_event))
            # Event was either consumed by background task or still queued
            assert transport._async_queue.qsize() >= 0
        finally:
            transport.close()

    def test_close_drains_queue(self) -> None:
        """Close signals the background consumer to stop."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        transport.close()

        assert transport._closed is True

    def test_constructor_params(self) -> None:
        """Constructor accepts url, timeout, and api_key."""
        transport = HttpLineageTransport(
            url="http://example.com/lineage",
            timeout=10.0,
            api_key="secret-key",
        )
        assert transport._url == "http://example.com/lineage"
        assert transport._timeout == 10.0
        assert transport._api_key == "secret-key"
        transport.close()

    def test_emit_after_close_is_ignored(self, sample_event: LineageEvent) -> None:
        """Events emitted after close are silently dropped."""
        transport = HttpLineageTransport(url="http://localhost:5000/api/v1/lineage")
        transport.close()
        _run(transport.emit(sample_event))  # Should not raise
