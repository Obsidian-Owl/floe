"""Unit tests for LineageResource and NoOpLineageResource.

Tests the Dagster ConfigurableResource wrappers that bridge async
LineageEmitter methods to synchronous Dagster resource calls via
a dedicated daemon thread running an asyncio event loop.

Requirements Covered:
    - AC-1: emit_start submits via run_coroutine_threadsafe, blocks 5s, returns UUID
    - AC-2: emit_complete/emit_fail same pattern with 5s timeout
    - AC-3: emit_event forwards pre-built events to transport
    - AC-4: Background loop runs in daemon thread
    - AC-5: close() drains, stops, joins; idempotent; post-close warns
    - AC-6: TimeoutError/exceptions caught, logged, never crash
    - AC-7: NoOp returns unique UUIDs, namespace "default", all no-op
    - AC-12: Thread-safe concurrent emission
    - AC-13: floe-core imports guarded by TYPE_CHECKING
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Constants to avoid duplicate literals
# ---------------------------------------------------------------------------
JOB_NAME = "test_job"
ERROR_MESSAGE = "something went wrong"
AC_1 = "AC-1"
AC_2 = "AC-2"
AC_3 = "AC-3"
AC_4 = "AC-4"
AC_5 = "AC-5"
AC_6 = "AC-6"
AC_7 = "AC-7"
AC_12 = "AC-12"
AC_13 = "AC-13"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_emitter() -> MagicMock:
    """Create a mock LineageEmitter with async methods.

    The mock emitter has AsyncMock coroutines for emit_start,
    emit_complete, and emit_fail. emit_start returns a UUID.
    transport.emit is also an AsyncMock.
    """
    emitter = MagicMock()
    emitter.transport = MagicMock()
    emitter.transport.emit = MagicMock()
    emitter.transport.close = MagicMock()
    emitter.default_namespace = "test-namespace"

    start_id = uuid4()
    emitter.emit_start = AsyncMock(return_value=start_id)
    emitter.emit_complete = AsyncMock(return_value=None)
    emitter.emit_fail = AsyncMock(return_value=None)
    emitter.close = MagicMock()

    return emitter


@pytest.fixture
def lineage_resource(mock_emitter: MagicMock) -> Any:
    """Create a LineageResource wrapping a mock emitter.

    Yields the resource and ensures cleanup via close().
    """
    from floe_orchestrator_dagster.resources.lineage import LineageResource

    resource = LineageResource(emitter=mock_emitter)
    yield resource
    resource.close()


@pytest.fixture
def noop_resource() -> Any:
    """Create a NoOpLineageResource."""
    from floe_orchestrator_dagster.resources.lineage import NoOpLineageResource

    return NoOpLineageResource()


# ===========================================================================
# LineageResource Tests
# ===========================================================================


class TestLineageResourceEmitStart:
    """Tests for LineageResource.emit_start — AC-1."""

    @pytest.mark.requirement(AC_1)
    def test_emit_start_returns_uuid(self, lineage_resource: Any, mock_emitter: MagicMock) -> None:
        """Test emit_start returns a UUID from the underlying async emitter."""
        result = lineage_resource.emit_start(JOB_NAME)

        assert isinstance(result, UUID), f"Expected UUID, got {type(result)}"

    @pytest.mark.requirement(AC_1)
    def test_emit_start_delegates_job_name(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_start passes job_name to the async emitter."""
        lineage_resource.emit_start(JOB_NAME)

        mock_emitter.emit_start.assert_awaited_once()
        call_kwargs = mock_emitter.emit_start.await_args
        # job_name must be the first positional arg or a kwarg
        args, kwargs = call_kwargs
        assert JOB_NAME in args or kwargs.get("job_name") == JOB_NAME

    @pytest.mark.requirement(AC_1)
    def test_emit_start_passes_inputs_outputs(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_start forwards inputs and outputs kwargs."""
        fake_inputs = [MagicMock()]
        fake_outputs = [MagicMock()]

        lineage_resource.emit_start(JOB_NAME, inputs=fake_inputs, outputs=fake_outputs)

        mock_emitter.emit_start.assert_awaited_once()
        _, kwargs = mock_emitter.emit_start.await_args
        assert kwargs.get("inputs") is fake_inputs
        assert kwargs.get("outputs") is fake_outputs

    @pytest.mark.requirement(AC_1)
    def test_emit_start_passes_run_facets_and_job_facets(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_start forwards run_facets and job_facets."""
        run_facets = {"custom": "facet_a"}
        job_facets = {"custom": "facet_b"}

        lineage_resource.emit_start(JOB_NAME, run_facets=run_facets, job_facets=job_facets)

        _, kwargs = mock_emitter.emit_start.await_args
        assert kwargs.get("run_facets") is run_facets
        assert kwargs.get("job_facets") is job_facets

    @pytest.mark.requirement(AC_1)
    def test_emit_start_returns_uuid_from_emitter_not_hardcoded(
        self, mock_emitter: MagicMock
    ) -> None:
        """Test emit_start returns the actual UUID from the emitter, not a hardcoded one.

        This catches implementations that generate their own UUID instead of
        using the one returned by the async emitter.
        """
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        specific_id = UUID("12345678-1234-5678-1234-567812345678")
        mock_emitter.emit_start = AsyncMock(return_value=specific_id)

        resource = LineageResource(emitter=mock_emitter)
        try:
            result = resource.emit_start(JOB_NAME)

            assert result == specific_id, (
                f"emit_start must return the UUID from the emitter, got {result}"
            )
        finally:
            resource.close()

    @pytest.mark.requirement(AC_1)
    def test_emit_start_different_emitter_uuids_propagate(self, mock_emitter: MagicMock) -> None:
        """Test that different UUIDs from the emitter are faithfully returned.

        Calls emit_start twice with different return values and verifies each.
        """
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        id_1 = uuid4()
        id_2 = uuid4()
        mock_emitter.emit_start = AsyncMock(side_effect=[id_1, id_2])

        resource = LineageResource(emitter=mock_emitter)
        try:
            result_1 = resource.emit_start("job_a")
            result_2 = resource.emit_start("job_b")

            assert result_1 == id_1
            assert result_2 == id_2
        finally:
            resource.close()


class TestLineageResourceEmitComplete:
    """Tests for LineageResource.emit_complete — AC-2."""

    @pytest.mark.requirement(AC_2)
    def test_emit_complete_delegates_to_emitter(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_complete calls the async emitter with run_id and job_name."""
        run_id = uuid4()
        lineage_resource.emit_complete(run_id, JOB_NAME)

        mock_emitter.emit_complete.assert_awaited_once()
        call_args = mock_emitter.emit_complete.await_args
        args, kwargs = call_args
        assert run_id in args or kwargs.get("run_id") == run_id

    @pytest.mark.requirement(AC_2)
    def test_emit_complete_passes_outputs(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_complete forwards outputs kwarg."""
        run_id = uuid4()
        fake_outputs = [MagicMock()]
        lineage_resource.emit_complete(run_id, JOB_NAME, outputs=fake_outputs)

        _, kwargs = mock_emitter.emit_complete.await_args
        assert kwargs.get("outputs") is fake_outputs

    @pytest.mark.requirement(AC_2)
    def test_emit_complete_passes_facets(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_complete forwards run_facets and job_facets."""
        run_id = uuid4()
        run_facets = {"duration": "10s"}
        job_facets = {"sql": "SELECT 1"}

        lineage_resource.emit_complete(
            run_id, JOB_NAME, run_facets=run_facets, job_facets=job_facets
        )

        _, kwargs = mock_emitter.emit_complete.await_args
        assert kwargs.get("run_facets") is run_facets
        assert kwargs.get("job_facets") is job_facets


class TestLineageResourceEmitFail:
    """Tests for LineageResource.emit_fail — AC-2."""

    @pytest.mark.requirement(AC_2)
    def test_emit_fail_delegates_to_emitter(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_fail calls the async emitter with run_id, job_name, error."""
        run_id = uuid4()
        lineage_resource.emit_fail(run_id, JOB_NAME, error_message=ERROR_MESSAGE)

        mock_emitter.emit_fail.assert_awaited_once()
        _, kwargs = mock_emitter.emit_fail.await_args
        assert kwargs.get("error_message") == ERROR_MESSAGE

    @pytest.mark.requirement(AC_2)
    def test_emit_fail_passes_run_facets(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_fail forwards run_facets kwarg."""
        run_id = uuid4()
        run_facets = {"error_detail": "stack trace"}

        lineage_resource.emit_fail(
            run_id, JOB_NAME, error_message=ERROR_MESSAGE, run_facets=run_facets
        )

        _, kwargs = mock_emitter.emit_fail.await_args
        assert kwargs.get("run_facets") is run_facets


class TestLineageResourceEmitEvent:
    """Tests for LineageResource.emit_event — AC-3."""

    @pytest.mark.requirement(AC_3)
    def test_emit_event_forwards_to_transport(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_event forwards a pre-built LineageEvent to the transport.

        The transport.emit method must be called with the event object.
        """
        mock_event = MagicMock()
        lineage_resource.emit_event(mock_event)

        # The transport's emit should have been invoked with the event
        mock_emitter.transport.emit.assert_called_once_with(mock_event)

    @pytest.mark.requirement(AC_3)
    def test_emit_event_does_not_use_emitter_methods(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test emit_event bypasses emit_start/complete/fail — goes directly to transport."""
        mock_event = MagicMock()
        lineage_resource.emit_event(mock_event)

        mock_emitter.emit_start.assert_not_awaited()
        mock_emitter.emit_complete.assert_not_awaited()
        mock_emitter.emit_fail.assert_not_awaited()


class TestLineageResourceBackgroundLoop:
    """Tests for background daemon thread and event loop — AC-4."""

    @pytest.mark.requirement(AC_4)
    def test_background_thread_is_daemon(self, lineage_resource: Any) -> None:
        """Test the background thread is a daemon thread.

        Daemon threads don't prevent process exit.
        """
        # The resource must have a thread attribute that is a daemon
        thread = getattr(lineage_resource, "_thread", None)
        if thread is None:
            # Try alternative attribute names
            for attr in dir(lineage_resource):
                val = getattr(lineage_resource, attr, None)
                if isinstance(val, threading.Thread):
                    thread = val
                    break

        assert thread is not None, "LineageResource must have a background thread"
        assert thread.daemon is True, "Background thread must be a daemon thread"

    @pytest.mark.requirement(AC_4)
    def test_background_loop_is_running(self, lineage_resource: Any) -> None:
        """Test the background event loop is running."""
        loop = getattr(lineage_resource, "_loop", None)
        if loop is None:
            for attr in dir(lineage_resource):
                val = getattr(lineage_resource, attr, None)
                if isinstance(val, asyncio.AbstractEventLoop):
                    loop = val
                    break

        assert loop is not None, "LineageResource must have a background event loop"
        assert loop.is_running(), "Background event loop must be running"

    @pytest.mark.requirement(AC_4)
    def test_emit_start_uses_run_coroutine_threadsafe(self, mock_emitter: MagicMock) -> None:
        """Test emit_start submits work via asyncio.run_coroutine_threadsafe.

        This verifies the actual threading mechanism, not just that the
        async method gets called.
        """
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        resource = LineageResource(emitter=mock_emitter)
        try:
            with patch("asyncio.run_coroutine_threadsafe") as mock_submit:
                future = MagicMock(spec=Future)
                future.result.return_value = uuid4()
                mock_submit.return_value = future

                resource.emit_start(JOB_NAME)

                mock_submit.assert_called_once()
                # First arg should be a coroutine
                coro_arg = mock_submit.call_args[0][0]
                assert asyncio.iscoroutine(coro_arg), (
                    "First argument to run_coroutine_threadsafe must be a coroutine"
                )
                # Clean up the coroutine to avoid RuntimeWarning
                coro_arg.close()
        finally:
            resource.close()


class TestLineageResourceClose:
    """Tests for close() — AC-5."""

    @pytest.mark.requirement(AC_5)
    def test_close_calls_emitter_close(
        self, lineage_resource: Any, mock_emitter: MagicMock
    ) -> None:
        """Test close() calls emitter.close() to drain the transport."""
        lineage_resource.close()

        mock_emitter.close.assert_called_once()

    @pytest.mark.requirement(AC_5)
    def test_close_stops_background_loop(self, lineage_resource: Any) -> None:
        """Test close() stops the background event loop."""
        # Get loop reference before close
        loop = getattr(lineage_resource, "_loop", None)
        if loop is None:
            for attr in dir(lineage_resource):
                val = getattr(lineage_resource, attr, None)
                if isinstance(val, asyncio.AbstractEventLoop):
                    loop = val
                    break
        assert loop is not None, "Must have a loop to test close"

        lineage_resource.close()

        # After close, loop should no longer be running
        assert not loop.is_running(), "Event loop must be stopped after close()"

    @pytest.mark.requirement(AC_5)
    def test_close_joins_background_thread(self, lineage_resource: Any) -> None:
        """Test close() joins (waits for) the background thread."""
        thread = getattr(lineage_resource, "_thread", None)
        if thread is None:
            for attr in dir(lineage_resource):
                val = getattr(lineage_resource, attr, None)
                if isinstance(val, threading.Thread):
                    thread = val
                    break
        assert thread is not None, "Must have a thread to test close"

        lineage_resource.close()

        # After close, thread should no longer be alive
        assert not thread.is_alive(), "Background thread must be joined after close()"

    @pytest.mark.requirement(AC_5)
    def test_close_closes_event_loop(self, lineage_resource: Any) -> None:
        """Test close() closes the event loop to release file descriptors."""
        loop = lineage_resource._loop

        lineage_resource.close()

        assert loop.is_closed(), "Event loop must be closed after close() to prevent FD leaks"

    @pytest.mark.requirement(AC_5)
    def test_close_logs_warning_if_thread_still_alive(
        self, mock_emitter: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test close() logs a warning when the background thread doesn't stop."""
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        resource = LineageResource(emitter=mock_emitter)
        real_thread = resource._thread
        real_loop = resource._loop

        # Patch thread.join to be a no-op and thread.is_alive to return True
        resource._thread.join = MagicMock()  # type: ignore[assignment]
        resource._thread.is_alive = MagicMock(return_value=True)  # type: ignore[assignment]

        with caplog.at_level(logging.WARNING):
            resource.close()

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("did_not_stop" in msg for msg in warning_messages), (
            "close() must warn when background thread doesn't stop"
        )

        # Clean up the real thread/loop that was left running
        real_loop.call_soon_threadsafe(real_loop.stop)
        real_thread.join(timeout=2.0)
        if not real_loop.is_running():
            real_loop.close()

    @pytest.mark.requirement(AC_5)
    def test_close_is_idempotent(self, lineage_resource: Any, mock_emitter: MagicMock) -> None:
        """Test calling close() multiple times is safe and only drains once."""
        lineage_resource.close()
        lineage_resource.close()
        lineage_resource.close()

        # emitter.close should be called at most once (idempotent)
        assert mock_emitter.close.call_count <= 1, (
            f"emitter.close called {mock_emitter.close.call_count} times; "
            "close() must be idempotent"
        )

    @pytest.mark.requirement(AC_5)
    def test_emit_start_after_close_returns_uuid(self, lineage_resource: Any) -> None:
        """Test emit_start after close() returns a fresh UUID (not crash)."""
        lineage_resource.close()

        result = lineage_resource.emit_start(JOB_NAME)
        assert isinstance(result, UUID), "emit_start after close must return a UUID, not crash"

    @pytest.mark.requirement(AC_5)
    def test_emit_start_after_close_logs_warning(
        self, lineage_resource: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test emit_start after close() logs a warning."""
        lineage_resource.close()

        with caplog.at_level(logging.WARNING):
            lineage_resource.emit_start(JOB_NAME)

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) > 0, "emit_start after close must log a warning"

    @pytest.mark.requirement(AC_5)
    def test_emit_complete_after_close_does_not_raise(self, lineage_resource: Any) -> None:
        """Test emit_complete after close() does not raise."""
        lineage_resource.close()

        # Must not raise
        lineage_resource.emit_complete(uuid4(), JOB_NAME)

    @pytest.mark.requirement(AC_5)
    def test_emit_fail_after_close_does_not_raise(self, lineage_resource: Any) -> None:
        """Test emit_fail after close() does not raise."""
        lineage_resource.close()

        lineage_resource.emit_fail(uuid4(), JOB_NAME, error_message=ERROR_MESSAGE)


class TestLineageResourceErrorHandling:
    """Tests for error resilience — AC-6."""

    @pytest.mark.requirement(AC_6)
    def test_emit_start_timeout_returns_uuid(self, mock_emitter: MagicMock) -> None:
        """Test emit_start returns a UUID even when the coroutine times out.

        A real timeout (5s) would be too slow for unit tests, so we simulate
        TimeoutError from the future.
        """
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        # Make the async call hang forever so timeout triggers
        async def slow_emit(*args: Any, **kwargs: Any) -> UUID:
            await asyncio.sleep(9999)
            return uuid4()

        mock_emitter.emit_start = slow_emit
        resource = LineageResource(emitter=mock_emitter)
        try:
            # Patch the future to raise TimeoutError immediately
            with patch("asyncio.run_coroutine_threadsafe") as mock_submit:
                future = MagicMock(spec=Future)
                future.result.side_effect = TimeoutError("timed out")
                mock_submit.return_value = future

                result = resource.emit_start(JOB_NAME)

            assert isinstance(result, UUID), "emit_start must return a UUID even on timeout"
            future.cancel.assert_called_once()
        finally:
            resource.close()

    @pytest.mark.requirement(AC_6)
    def test_emit_start_timeout_logs_warning(
        self, mock_emitter: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test emit_start logs a warning on timeout."""
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        mock_emitter.emit_start = AsyncMock(return_value=uuid4())
        resource = LineageResource(emitter=mock_emitter)
        try:
            with patch("asyncio.run_coroutine_threadsafe") as mock_submit:
                future = MagicMock(spec=Future)
                future.result.side_effect = TimeoutError("timed out")
                mock_submit.return_value = future

                with caplog.at_level(logging.WARNING):
                    resource.emit_start(JOB_NAME)

            warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
            assert len(warning_records) > 0, "Timeout must produce a warning log"
        finally:
            resource.close()

    @pytest.mark.requirement(AC_6)
    def test_emit_start_exception_returns_uuid(self, mock_emitter: MagicMock) -> None:
        """Test emit_start returns a UUID when the coroutine raises an exception."""
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        mock_emitter.emit_start = AsyncMock(side_effect=RuntimeError("transport down"))
        resource = LineageResource(emitter=mock_emitter)
        try:
            result = resource.emit_start(JOB_NAME)
            assert isinstance(result, UUID), (
                "emit_start must return a UUID even when the emitter raises"
            )
        finally:
            resource.close()

    @pytest.mark.requirement(AC_6)
    def test_emit_complete_exception_does_not_raise(self, mock_emitter: MagicMock) -> None:
        """Test emit_complete swallows exceptions from the emitter."""
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        mock_emitter.emit_complete = AsyncMock(side_effect=RuntimeError("transport down"))
        resource = LineageResource(emitter=mock_emitter)
        try:
            # Must not raise
            resource.emit_complete(uuid4(), JOB_NAME)
        finally:
            resource.close()

    @pytest.mark.requirement(AC_6)
    def test_emit_fail_exception_does_not_raise(self, mock_emitter: MagicMock) -> None:
        """Test emit_fail swallows exceptions from the emitter."""
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        mock_emitter.emit_fail = AsyncMock(side_effect=ConnectionError("network error"))
        resource = LineageResource(emitter=mock_emitter)
        try:
            # Must not raise
            resource.emit_fail(uuid4(), JOB_NAME, error_message=ERROR_MESSAGE)
        finally:
            resource.close()

    @pytest.mark.requirement(AC_6)
    def test_emit_start_exception_logs_warning(
        self, mock_emitter: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test emit_start logs a warning when the emitter raises."""
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        mock_emitter.emit_start = AsyncMock(side_effect=RuntimeError("boom"))
        resource = LineageResource(emitter=mock_emitter)
        try:
            with caplog.at_level(logging.WARNING):
                resource.emit_start(JOB_NAME)

            warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
            assert len(warning_records) > 0, "Emitter exception must produce a warning log"
        finally:
            resource.close()

    @pytest.mark.requirement(AC_6)
    def test_emit_start_uses_5s_timeout(self, mock_emitter: MagicMock) -> None:
        """Test emit_start blocks with a 5-second timeout on the future.

        Verifies the timeout argument passed to future.result().
        """
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        mock_emitter.emit_start = AsyncMock(return_value=uuid4())
        resource = LineageResource(emitter=mock_emitter)
        try:
            with patch("asyncio.run_coroutine_threadsafe") as mock_submit:
                future = MagicMock(spec=Future)
                future.result.return_value = uuid4()
                mock_submit.return_value = future

                resource.emit_start(JOB_NAME)

                # Verify timeout=5 (or 5.0) was passed
                call_args = future.result.call_args
                if call_args.args:
                    timeout_val = call_args.args[0]
                else:
                    timeout_val = call_args.kwargs.get("timeout")
                assert timeout_val == pytest.approx(5.0), (
                    f"emit_start must use 5s timeout, got {timeout_val}"
                )
        finally:
            resource.close()


class TestLineageResourceConcurrency:
    """Tests for thread-safe concurrent emission — AC-12."""

    @pytest.mark.requirement(AC_12)
    def test_concurrent_emit_start_all_return_uuids(self, mock_emitter: MagicMock) -> None:
        """Test many threads calling emit_start concurrently all get UUIDs.

        No thread should crash, and every thread must receive a UUID.
        """
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        num_threads = 20
        # Generate distinct UUIDs for each call
        expected_ids = [uuid4() for _ in range(num_threads)]
        mock_emitter.emit_start = AsyncMock(side_effect=expected_ids)

        resource = LineageResource(emitter=mock_emitter)
        try:
            results: list[UUID | None] = [None] * num_threads
            errors: list[Exception | None] = [None] * num_threads

            def worker(idx: int) -> None:
                try:
                    results[idx] = resource.emit_start(f"job_{idx}")
                except Exception as exc:
                    errors[idx] = exc

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            # No thread should have raised
            for i, err in enumerate(errors):
                assert err is None, f"Thread {i} raised: {err}"

            # Every result should be a UUID
            for i, result in enumerate(results):
                assert isinstance(result, UUID), f"Thread {i} got {type(result)}, not UUID"
        finally:
            resource.close()

    @pytest.mark.requirement(AC_12)
    def test_concurrent_emit_start_returns_unique_uuids(self, mock_emitter: MagicMock) -> None:
        """Test concurrent emit_start calls return unique UUIDs (no duplicates).

        This catches implementations that share a single hardcoded UUID.
        """
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        num_threads = 20
        expected_ids = [uuid4() for _ in range(num_threads)]
        mock_emitter.emit_start = AsyncMock(side_effect=expected_ids)

        resource = LineageResource(emitter=mock_emitter)
        try:
            results: list[UUID | None] = [None] * num_threads

            def worker(idx: int) -> None:
                results[idx] = resource.emit_start(f"job_{idx}")

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            uuid_set = {r for r in results if r is not None}
            assert len(uuid_set) == num_threads, (
                f"Expected {num_threads} unique UUIDs, got {len(uuid_set)}"
            )
        finally:
            resource.close()

    @pytest.mark.requirement(AC_12)
    def test_concurrent_mixed_operations(self, mock_emitter: MagicMock) -> None:
        """Test concurrent calls to emit_start, emit_complete, emit_fail.

        Verifies no deadlocks or crashes when mixing operation types.
        """
        from floe_orchestrator_dagster.resources.lineage import LineageResource

        mock_emitter.emit_start = AsyncMock(return_value=uuid4())
        resource = LineageResource(emitter=mock_emitter)
        try:
            errors: list[Exception | None] = [None] * 30

            def start_worker(idx: int) -> None:
                try:
                    resource.emit_start(f"job_{idx}")
                except Exception as exc:
                    errors[idx] = exc

            def complete_worker(idx: int) -> None:
                try:
                    resource.emit_complete(uuid4(), f"job_{idx}")
                except Exception as exc:
                    errors[10 + idx] = exc

            def fail_worker(idx: int) -> None:
                try:
                    resource.emit_fail(uuid4(), f"job_{idx}", error_message="err")
                except Exception as exc:
                    errors[20 + idx] = exc

            threads: list[threading.Thread] = []
            for i in range(10):
                threads.append(threading.Thread(target=start_worker, args=(i,)))
                threads.append(threading.Thread(target=complete_worker, args=(i,)))
                threads.append(threading.Thread(target=fail_worker, args=(i,)))

            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=15)

            for i, err in enumerate(errors):
                assert err is None, f"Concurrent operation {i} raised: {err}"
        finally:
            resource.close()


class TestLineageResourceTypeChecking:
    """Tests for TYPE_CHECKING guard — AC-13."""

    @pytest.mark.requirement(AC_13)
    def test_module_does_not_import_floe_core_at_runtime(self) -> None:
        """Test that floe_core imports in lineage.py are guarded by TYPE_CHECKING.

        Reads the source code and verifies that any 'from floe_core' or
        'import floe_core' statements occur only inside TYPE_CHECKING blocks.
        """
        import ast
        import inspect

        from floe_orchestrator_dagster.resources import lineage as lineage_mod

        source = inspect.getsource(lineage_mod)
        tree = ast.parse(source)

        # Collect all import nodes
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module_name = ""
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_name = node.module
                elif isinstance(node, ast.Import):
                    module_name = node.names[0].name if node.names else ""

                if "floe_core" not in module_name:
                    continue

                # This floe_core import must be inside an `if TYPE_CHECKING:` block
                # Walk up the AST to find the parent If node
                # We check by finding the If nodes that contain this import
                found_in_type_checking = False
                for if_node in ast.walk(tree):
                    if not isinstance(if_node, ast.If):
                        continue
                    # Check if the test is TYPE_CHECKING
                    test = if_node.test
                    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                        # Check if our import is in the body
                        for child in ast.walk(if_node):
                            if child is node:
                                found_in_type_checking = True
                                break
                    if found_in_type_checking:
                        break

                assert found_in_type_checking, (
                    f"floe_core import at line {node.lineno} is not inside "
                    f"'if TYPE_CHECKING:' block"
                )


# ===========================================================================
# NoOpLineageResource Tests
# ===========================================================================


class TestNoOpLineageResourceEmitStart:
    """Tests for NoOpLineageResource.emit_start — AC-7."""

    @pytest.mark.requirement(AC_7)
    def test_emit_start_returns_uuid(self, noop_resource: Any) -> None:
        """Test NoOp emit_start returns a UUID."""
        result = noop_resource.emit_start(JOB_NAME)
        assert isinstance(result, UUID)

    @pytest.mark.requirement(AC_7)
    def test_emit_start_returns_unique_uuids(self, noop_resource: Any) -> None:
        """Test successive calls return different UUIDs.

        Catches implementations that return a single hardcoded UUID.
        """
        results = [noop_resource.emit_start(f"job_{i}") for i in range(100)]
        unique = set(results)
        assert len(unique) == 100, f"Expected 100 unique UUIDs from NoOp, got {len(unique)}"

    @pytest.mark.requirement(AC_7)
    def test_emit_start_accepts_kwargs(self, noop_resource: Any) -> None:
        """Test NoOp emit_start accepts arbitrary kwargs without error."""
        result = noop_resource.emit_start(
            JOB_NAME,
            inputs=[MagicMock()],
            outputs=[MagicMock()],
            run_facets={"a": "b"},
            job_facets={"c": "d"},
        )
        assert isinstance(result, UUID)


class TestNoOpLineageResourceOtherMethods:
    """Tests for NoOpLineageResource other methods — AC-7."""

    @pytest.mark.requirement(AC_7)
    def test_emit_complete_returns_none(self, noop_resource: Any) -> None:
        """Test NoOp emit_complete returns None."""
        result = noop_resource.emit_complete(uuid4(), JOB_NAME)
        assert result is None

    @pytest.mark.requirement(AC_7)
    def test_emit_fail_returns_none(self, noop_resource: Any) -> None:
        """Test NoOp emit_fail returns None."""
        result = noop_resource.emit_fail(uuid4(), JOB_NAME, error_message=ERROR_MESSAGE)
        assert result is None

    @pytest.mark.requirement(AC_7)
    def test_emit_event_returns_none(self, noop_resource: Any) -> None:
        """Test NoOp emit_event returns None."""
        result = noop_resource.emit_event(MagicMock())
        assert result is None

    @pytest.mark.requirement(AC_7)
    def test_close_returns_none(self, noop_resource: Any) -> None:
        """Test NoOp close returns None."""
        result = noop_resource.close()
        assert result is None

    @pytest.mark.requirement(AC_7)
    def test_close_is_idempotent(self, noop_resource: Any) -> None:
        """Test NoOp close can be called multiple times."""
        noop_resource.close()
        noop_resource.close()
        noop_resource.close()
        # No exception means pass

    @pytest.mark.requirement(AC_7)
    def test_namespace_is_default(self, noop_resource: Any) -> None:
        """Test NoOp namespace property returns 'default'."""
        assert noop_resource.namespace == "default"

    @pytest.mark.requirement(AC_7)
    def test_namespace_is_string(self, noop_resource: Any) -> None:
        """Test NoOp namespace property returns a string type."""
        ns = noop_resource.namespace
        assert isinstance(ns, str)
        assert ns == "default"

    @pytest.mark.requirement(AC_7)
    def test_emit_complete_accepts_kwargs(self, noop_resource: Any) -> None:
        """Test NoOp emit_complete accepts kwargs without error."""
        noop_resource.emit_complete(uuid4(), JOB_NAME, outputs=[MagicMock()], run_facets={"a": 1})

    @pytest.mark.requirement(AC_7)
    def test_emit_fail_accepts_kwargs(self, noop_resource: Any) -> None:
        """Test NoOp emit_fail accepts kwargs without error."""
        noop_resource.emit_fail(uuid4(), JOB_NAME, error_message="err", run_facets={"a": 1})


# ===========================================================================
# Factory Function Tests — AC-8, AC-9, AC-10
# ===========================================================================

AC_8 = "AC-8"
AC_9 = "AC-9"
AC_10 = "AC-10"

# Module path prefix for patching inside lineage.py
_LINEAGE_MODULE = "floe_orchestrator_dagster.resources.lineage"


class TestCreateLineageResource:
    """Tests for create_lineage_resource(lineage_ref) — AC-8, AC-10.

    Verifies the factory loads the plugin from the registry, obtains
    transport config and namespace strategy, creates an emitter, and wraps
    it in a Dagster @resource with generator teardown.
    """

    @pytest.mark.requirement(AC_8)
    def test_returns_dict_with_lineage_key(self) -> None:
        """Test create_lineage_resource returns dict with exactly the 'lineage' key."""
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import create_lineage_resource

        lineage_ref = PluginRef(type="marquez", version="1.0.0")

        mock_plugin = MagicMock()
        mock_plugin.get_transport_config.return_value = {"url": "http://marquez:5000"}
        mock_plugin.get_namespace_strategy.return_value = {
            "default_namespace": "test-ns",
        }
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter),
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            result = create_lineage_resource(lineage_ref)

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "lineage" in result, (
            f"Result must have 'lineage' key, got keys: {list(result.keys())}"
        )
        assert len(result) == 1, f"Result must have exactly one key, got: {list(result.keys())}"

    @pytest.mark.requirement(AC_8)
    def test_loads_plugin_from_registry_with_correct_type(self) -> None:
        """Test factory calls get_registry().get(PluginType.LINEAGE, ref.type)."""
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import create_lineage_resource

        lineage_ref = PluginRef(type="marquez", version="1.0.0")

        mock_plugin = MagicMock()
        mock_plugin.get_transport_config.return_value = {"url": "http://marquez:5000"}
        mock_plugin.get_namespace_strategy.return_value = {
            "default_namespace": "test-ns",
        }
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter),
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            create_lineage_resource(lineage_ref)

            from floe_core.plugin_types import PluginType

            mock_registry.get.assert_called_once_with(PluginType.LINEAGE, "marquez")

    @pytest.mark.requirement(AC_8)
    def test_calls_get_transport_config_on_plugin(self) -> None:
        """Test factory invokes plugin.get_transport_config()."""
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import create_lineage_resource

        lineage_ref = PluginRef(type="marquez", version="1.0.0")

        mock_plugin = MagicMock()
        transport_config = {"url": "http://marquez:5000", "timeout": 30}
        mock_plugin.get_transport_config.return_value = transport_config
        mock_plugin.get_namespace_strategy.return_value = {
            "default_namespace": "prod-ns",
        }
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter),
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            create_lineage_resource(lineage_ref)

            mock_plugin.get_transport_config.assert_called_once()

    @pytest.mark.requirement(AC_8)
    def test_calls_get_namespace_strategy_on_plugin(self) -> None:
        """Test factory invokes plugin.get_namespace_strategy()."""
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import create_lineage_resource

        lineage_ref = PluginRef(type="marquez", version="1.0.0")

        mock_plugin = MagicMock()
        mock_plugin.get_transport_config.return_value = {"url": "http://marquez:5000"}
        ns_strategy = {"default_namespace": "my-namespace"}
        mock_plugin.get_namespace_strategy.return_value = ns_strategy
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter),
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            create_lineage_resource(lineage_ref)

            mock_plugin.get_namespace_strategy.assert_called_once()

    @pytest.mark.requirement(AC_8)
    def test_creates_emitter_with_transport_config_and_namespace(self) -> None:
        """Test factory passes transport_config and default_namespace to create_emitter.

        This catches implementations that hardcode config or ignore the plugin output.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import create_lineage_resource

        lineage_ref = PluginRef(type="marquez", version="1.0.0")

        mock_plugin = MagicMock()
        transport_config = {"url": "http://marquez:5000", "timeout": 30}
        mock_plugin.get_transport_config.return_value = transport_config
        mock_plugin.get_namespace_strategy.return_value = {
            "default_namespace": "custom-ns",
        }
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(
                f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter
            ) as mock_create_emitter,
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            create_lineage_resource(lineage_ref)

            mock_create_emitter.assert_called_once_with(transport_config, "custom-ns")

    @pytest.mark.requirement(AC_8)
    def test_different_plugin_type_uses_correct_registry_lookup(self) -> None:
        """Test factory uses the ref.type from lineage_ref, not a hardcoded string.

        Catches implementations that hardcode 'marquez' in the registry lookup.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import create_lineage_resource

        lineage_ref = PluginRef(type="atlan", version="2.0.0")

        mock_plugin = MagicMock()
        mock_plugin.get_transport_config.return_value = {"url": "http://atlan:9000"}
        mock_plugin.get_namespace_strategy.return_value = {
            "default_namespace": "atlan-ns",
        }
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter),
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            create_lineage_resource(lineage_ref)

            from floe_core.plugin_types import PluginType

            mock_registry.get.assert_called_once_with(PluginType.LINEAGE, "atlan")

    @pytest.mark.requirement(AC_10)
    def test_resource_value_is_dagster_resource_definition(self) -> None:
        """Test the dict value is a Dagster ResourceDefinition."""
        from dagster import ResourceDefinition
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import create_lineage_resource

        lineage_ref = PluginRef(type="marquez", version="1.0.0")

        mock_plugin = MagicMock()
        mock_plugin.get_transport_config.return_value = {"url": "http://marquez:5000"}
        mock_plugin.get_namespace_strategy.return_value = {
            "default_namespace": "test-ns",
        }
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter),
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            result = create_lineage_resource(lineage_ref)

        assert isinstance(result["lineage"], ResourceDefinition), (
            f"Value must be ResourceDefinition, got {type(result['lineage'])}"
        )


class TestCreateLineageResourceGeneratorTeardown:
    """Tests for Dagster @resource generator teardown — AC-10.

    Verifies the resource definition uses a generator pattern that
    yields the LineageResource and calls close() in the finally block.
    """

    @pytest.mark.requirement(AC_10)
    def test_resource_generator_yields_lineage_resource(self) -> None:
        """Test the @resource generator yields a LineageResource instance.

        Initialises the Dagster resource and verifies the yielded value
        has the LineageResource interface (emit_start, close, etc.).
        """
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import create_lineage_resource

        lineage_ref = PluginRef(type="marquez", version="1.0.0")

        mock_plugin = MagicMock()
        mock_plugin.get_transport_config.return_value = {"url": "http://marquez:5000"}
        mock_plugin.get_namespace_strategy.return_value = {
            "default_namespace": "test-ns",
        }
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter),
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            result = create_lineage_resource(lineage_ref)

        resource_def = result["lineage"]

        # Invoke the resource definition's generator to get the yielded value
        # Dagster ResourceDefinition wraps a generator function
        from dagster import build_init_resource_context

        init_context = build_init_resource_context()
        resource_instance = resource_def.resource_fn(init_context)

        # If it's a generator, step through it
        import types

        if isinstance(resource_instance, types.GeneratorType):
            yielded = next(resource_instance)
            assert hasattr(yielded, "emit_start"), "Yielded resource must have emit_start method"
            assert hasattr(yielded, "close"), "Yielded resource must have close method"
        else:
            # Non-generator — still must have the interface
            assert hasattr(resource_instance, "emit_start"), "Resource must have emit_start method"
            assert hasattr(resource_instance, "close"), "Resource must have close method"

    @pytest.mark.requirement(AC_10)
    def test_resource_generator_calls_close_on_teardown(self) -> None:
        """Test the @resource generator calls close() in the finally block.

        This is the critical teardown test — verifies that exhausting the
        generator (as Dagster does on resource teardown) calls close().
        """
        from floe_core.schemas.compiled_artifacts import PluginRef

        from floe_orchestrator_dagster.resources.lineage import (
            create_lineage_resource,
        )

        lineage_ref = PluginRef(type="marquez", version="1.0.0")

        mock_plugin = MagicMock()
        mock_plugin.get_transport_config.return_value = {"url": "http://marquez:5000"}
        mock_plugin.get_namespace_strategy.return_value = {
            "default_namespace": "test-ns",
        }
        mock_emitter = MagicMock()

        with (
            patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry,
            patch(f"{_LINEAGE_MODULE}.create_emitter", return_value=mock_emitter),
        ):
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get.return_value = mock_plugin

            result = create_lineage_resource(lineage_ref)

        resource_def = result["lineage"]

        from dagster import build_init_resource_context

        init_context = build_init_resource_context()
        gen = resource_def.resource_fn(init_context)

        import types

        if isinstance(gen, types.GeneratorType):
            yielded = next(gen)

            # Spy on close to verify teardown
            original_close = yielded.close
            close_called = []

            def spy_close() -> None:
                close_called.append(True)
                return original_close()

            yielded.close = spy_close

            # Simulate Dagster teardown by closing the generator
            gen.close()

            assert len(close_called) > 0, (
                "Generator teardown must call close() on the LineageResource"
            )
        else:
            pytest.fail(f"Resource function must be a generator (yield pattern), got {type(gen)}")


class TestTryCreateLineageResourceNone:
    """Tests for try_create_lineage_resource(None) — AC-9.

    When plugins is None, must return {"lineage": <NoOp resource>}.
    """

    @pytest.mark.requirement(AC_9)
    def test_none_plugins_returns_dict_with_lineage_key(self) -> None:
        """Test try_create_lineage_resource(None) returns dict with 'lineage' key."""
        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        result = try_create_lineage_resource(None)

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert "lineage" in result, f"Must have 'lineage' key, got keys: {list(result.keys())}"

    @pytest.mark.requirement(AC_9)
    def test_none_plugins_returns_exactly_one_key(self) -> None:
        """Test the result has exactly one key 'lineage', not extra keys."""
        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        result = try_create_lineage_resource(None)

        assert len(result) == 1, f"Expected exactly 1 key, got {len(result)}: {list(result.keys())}"

    @pytest.mark.requirement(AC_9)
    def test_none_plugins_never_returns_empty_dict(self) -> None:
        """Test try_create_lineage_resource(None) NEVER returns empty dict.

        This is explicitly different from the iceberg pattern where
        try_create_iceberg_resources returns {} when not configured.
        Lineage always returns {"lineage": <noop>}.
        """
        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        result = try_create_lineage_resource(None)

        assert result != {}, (
            "try_create_lineage_resource must NEVER return empty dict — "
            "must always return {'lineage': <resource>}"
        )

    @pytest.mark.requirement(AC_9)
    def test_none_plugins_resource_is_resource_definition(self) -> None:
        """Test the NoOp fallback is a proper Dagster ResourceDefinition."""
        from dagster import ResourceDefinition

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        result = try_create_lineage_resource(None)

        assert isinstance(result["lineage"], ResourceDefinition), (
            f"NoOp must be ResourceDefinition, got {type(result['lineage'])}"
        )


class TestTryCreateLineageResourceNoBackend:
    """Tests for try_create_lineage_resource(plugins_with_no_lineage) — AC-9.

    When plugins.lineage_backend is None, must return {"lineage": <NoOp>}.
    """

    @pytest.mark.requirement(AC_9)
    def test_no_lineage_backend_returns_dict_with_lineage_key(self) -> None:
        """Test plugins with lineage_backend=None returns dict with 'lineage' key."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=None,
        )

        result = try_create_lineage_resource(plugins)

        assert isinstance(result, dict)
        assert "lineage" in result
        assert result != {}, "Must not return empty dict"

    @pytest.mark.requirement(AC_9)
    def test_no_lineage_backend_does_not_touch_registry(self) -> None:
        """Test plugins with no lineage_backend does not call get_registry().

        This catches implementations that unconditionally load from registry.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=None,
        )

        with patch(f"{_LINEAGE_MODULE}.get_registry") as mock_get_registry:
            try_create_lineage_resource(plugins)

            mock_get_registry.assert_not_called()

    @pytest.mark.requirement(AC_9)
    def test_no_lineage_backend_resource_is_resource_definition(self) -> None:
        """Test the NoOp fallback is a Dagster ResourceDefinition."""
        from dagster import ResourceDefinition
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=None,
        )

        result = try_create_lineage_resource(plugins)

        assert isinstance(result["lineage"], ResourceDefinition)


class TestTryCreateLineageResourceWithBackend:
    """Tests for try_create_lineage_resource(plugins_with_lineage) — AC-8.

    When plugins.lineage_backend exists, must delegate to create_lineage_resource.
    """

    @pytest.mark.requirement(AC_8)
    def test_with_lineage_backend_calls_create_lineage_resource(self) -> None:
        """Test that try_create delegates to create_lineage_resource when backend exists."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        lineage_ref = PluginRef(type="marquez", version="1.0.0")
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=lineage_ref,
        )

        expected_result = {"lineage": MagicMock()}

        with patch(
            f"{_LINEAGE_MODULE}.create_lineage_resource",
            return_value=expected_result,
        ) as mock_create:
            result = try_create_lineage_resource(plugins)

            mock_create.assert_called_once_with(lineage_ref)
            assert result is expected_result, (
                "try_create must return the result of create_lineage_resource"
            )

    @pytest.mark.requirement(AC_8)
    def test_with_lineage_backend_passes_exact_ref(self) -> None:
        """Test the exact PluginRef is forwarded, not a copy or transformation.

        Catches implementations that extract fields instead of passing the ref.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        lineage_ref = PluginRef(
            type="openmetadata",
            version="3.0.0",
            config={"api_url": "http://omd:8585"},
        )
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=lineage_ref,
        )

        with patch(
            f"{_LINEAGE_MODULE}.create_lineage_resource",
            return_value={"lineage": MagicMock()},
        ) as mock_create:
            try_create_lineage_resource(plugins)

            passed_ref = mock_create.call_args[0][0]
            assert passed_ref is lineage_ref, "Must pass the exact PluginRef object, not a copy"

    @pytest.mark.requirement(AC_8)
    def test_with_lineage_backend_returns_dict_with_lineage_key(self) -> None:
        """Test configured lineage returns dict with 'lineage' key."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        lineage_ref = PluginRef(type="marquez", version="1.0.0")
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=lineage_ref,
        )

        mock_resource_def = MagicMock()

        with patch(
            f"{_LINEAGE_MODULE}.create_lineage_resource",
            return_value={"lineage": mock_resource_def},
        ):
            result = try_create_lineage_resource(plugins)

        assert "lineage" in result
        assert result["lineage"] is mock_resource_def

    @pytest.mark.requirement(AC_8)
    def test_always_returns_dict_never_none(self) -> None:
        """Test try_create_lineage_resource NEVER returns None.

        Tests all three paths: None plugins, no backend, with backend.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        # Path 1: None plugins
        result1 = try_create_lineage_resource(None)
        assert result1 is not None, "Must not return None for None plugins"
        assert isinstance(result1, dict)

        # Path 2: No lineage_backend
        plugins_no_lineage = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        )
        result2 = try_create_lineage_resource(plugins_no_lineage)
        assert result2 is not None, "Must not return None for no backend"
        assert isinstance(result2, dict)

        # Path 3: With lineage_backend
        plugins_with_lineage = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=PluginRef(type="marquez", version="1.0.0"),
        )

        with patch(
            f"{_LINEAGE_MODULE}.create_lineage_resource",
            return_value={"lineage": MagicMock()},
        ):
            result3 = try_create_lineage_resource(plugins_with_lineage)
        assert result3 is not None, "Must not return None for configured backend"
        assert isinstance(result3, dict)


class TestTryCreateLineageResourceConsistency:
    """Tests verifying all code paths return the same dict structure — AC-9.

    Every path must return {"lineage": <ResourceDefinition>}.
    """

    @pytest.mark.requirement(AC_9)
    def test_all_noop_paths_return_same_resource_type(self) -> None:
        """Test None plugins and no-backend paths return same ResourceDefinition type.

        Catches implementations that return different types for different NoOp paths.
        """
        from dagster import ResourceDefinition
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        from floe_orchestrator_dagster.resources.lineage import (
            try_create_lineage_resource,
        )

        # Path 1: None
        result_none = try_create_lineage_resource(None)

        # Path 2: No backend
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=None,
        )
        result_no_backend = try_create_lineage_resource(plugins)

        # Both must be ResourceDefinition
        assert isinstance(result_none["lineage"], ResourceDefinition)
        assert isinstance(result_no_backend["lineage"], ResourceDefinition)

        # Both must have the same type (same NoOp wrapper)
        assert type(result_none["lineage"]) is type(result_no_backend["lineage"]), (
            "Both NoOp paths should produce the same ResourceDefinition type"
        )
