"""Tests for LineageEmitter and create_emitter factory.

Tests the high-level emitter that coordinates event building and transport,
and the factory function for creating emitters from configuration.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from floe_core.lineage.emitter import LineageEmitter, create_emitter
from floe_core.lineage.events import EventBuilder
from floe_core.lineage.transport import (
    ConsoleLineageTransport,
    HttpLineageTransport,
    NoOpLineageTransport,
)
from floe_core.lineage.types import LineageDataset, LineageEvent, RunState


def _run(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _make_mock_transport() -> MagicMock:
    """Create a mock transport with async emit and sync close."""
    transport = MagicMock()
    transport.emit = AsyncMock()
    transport.close = MagicMock()
    return transport


class TestLineageEmitter:
    """Tests for LineageEmitter class."""

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_returns_uuid(self) -> None:
        """emit_start returns a UUID run_id."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        run_id = _run(emitter.emit_start("my_job"))

        assert isinstance(run_id, UUID)
        transport.emit.assert_awaited_once()
        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.START
        assert event.job.name == "my_job"
        assert event.run.run_id == run_id

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_with_explicit_run_id(self) -> None:
        """emit_start uses provided run_id."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        expected_id = uuid4()

        run_id = _run(emitter.emit_start("my_job", run_id=expected_id))

        assert run_id == expected_id

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_with_datasets(self) -> None:
        """emit_start passes inputs and outputs to event."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        inp = [LineageDataset(namespace="raw", name="input_table")]
        out = [LineageDataset(namespace="staging", name="output_table")]

        _run(emitter.emit_start("my_job", inputs=inp, outputs=out))

        event: LineageEvent = transport.emit.call_args[0][0]
        assert len(event.inputs) == 1
        assert len(event.outputs) == 1
        assert event.inputs[0].name == "input_table"

    @pytest.mark.requirement("REQ-516")
    def test_emit_complete_uses_same_run_id(self) -> None:
        """emit_complete emits COMPLETE event with the given run_id."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        run_id = uuid4()

        _run(emitter.emit_complete(run_id, "my_job"))

        transport.emit.assert_awaited_once()
        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.COMPLETE
        assert event.run.run_id == run_id
        assert event.job.name == "my_job"

    @pytest.mark.requirement("REQ-516")
    def test_emit_complete_with_outputs(self) -> None:
        """emit_complete passes outputs to event."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        out = [LineageDataset(namespace="gold", name="result")]

        _run(emitter.emit_complete(uuid4(), "my_job", outputs=out))

        event: LineageEvent = transport.emit.call_args[0][0]
        assert len(event.outputs) == 1

    @pytest.mark.requirement("REQ-516")
    def test_emit_fail_includes_error_message(self) -> None:
        """emit_fail emits FAIL event with error message facet."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        run_id = uuid4()

        _run(emitter.emit_fail(run_id, "my_job", error_message="something broke"))

        transport.emit.assert_awaited_once()
        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.FAIL
        assert event.run.run_id == run_id
        assert "errorMessage" in event.run.facets
        assert event.run.facets["errorMessage"]["message"] == "something broke"

    @pytest.mark.requirement("REQ-516")
    def test_emit_fail_without_error_message(self) -> None:
        """emit_fail works without error_message."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        _run(emitter.emit_fail(uuid4(), "my_job"))

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.FAIL
        assert "errorMessage" not in event.run.facets

    def test_close_calls_transport_close(self) -> None:
        """close() delegates to transport.close()."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        emitter.close()

        transport.close.assert_called_once()

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_with_facets(self) -> None:
        """emit_start passes run_facets and job_facets."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        _run(
            emitter.emit_start(
                "my_job",
                run_facets={"custom": "value"},
                job_facets={"sql": "SELECT 1"},
            )
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.facets["custom"] == "value"
        assert event.job.facets["sql"] == "SELECT 1"


class TestCreateEmitter:
    """Tests for create_emitter factory function."""

    @pytest.mark.requirement("REQ-527")
    def test_no_config_creates_noop(self) -> None:
        """No config creates emitter with NoOpLineageTransport."""
        emitter = create_emitter()
        assert isinstance(emitter.transport, NoOpLineageTransport)

    @pytest.mark.requirement("REQ-527")
    def test_none_type_creates_noop(self) -> None:
        """Config with type=None creates NoOp emitter."""
        emitter = create_emitter({"type": None})
        assert isinstance(emitter.transport, NoOpLineageTransport)

    @pytest.mark.requirement("REQ-527")
    def test_console_config_creates_console(self) -> None:
        """Console config creates emitter with ConsoleLineageTransport."""
        emitter = create_emitter({"type": "console"})
        assert isinstance(emitter.transport, ConsoleLineageTransport)

    @pytest.mark.requirement("REQ-527")
    def test_http_config_creates_http(self) -> None:
        """HTTP config creates emitter with HttpLineageTransport."""
        emitter = create_emitter({"type": "http", "url": "http://localhost:5000"})
        assert isinstance(emitter.transport, HttpLineageTransport)

    @pytest.mark.requirement("REQ-527")
    def test_http_config_with_options(self) -> None:
        """HTTP config passes timeout and api_key."""
        emitter = create_emitter(
            {
                "type": "http",
                "url": "http://localhost:5000",
                "timeout": 10.0,
                "api_key": "secret",
            }  # pragma: allowlist secret
        )
        transport = emitter.transport
        assert isinstance(transport, HttpLineageTransport)
        assert transport._timeout == 10.0
        assert transport._api_key == "secret"

    @pytest.mark.requirement("REQ-527")
    def test_unknown_type_creates_noop(self) -> None:
        """Unknown transport type falls back to NoOp."""
        emitter = create_emitter({"type": "unknown_backend"})
        assert isinstance(emitter.transport, NoOpLineageTransport)

    @pytest.mark.requirement("REQ-527")
    def test_factory_sets_namespace_and_producer(self) -> None:
        """Factory passes namespace and producer to builder."""
        emitter = create_emitter(
            default_namespace="production",
            producer="floe-test",
        )
        assert emitter.default_namespace == "production"
        assert emitter.event_builder.producer == "floe-test"
        assert emitter.event_builder.default_namespace == "production"

    @pytest.mark.requirement("REQ-527")
    def test_factory_creates_working_emitter(self) -> None:
        """Factory-created console emitter can emit events."""
        emitter = create_emitter({"type": "console"}, default_namespace="test")
        run_id = _run(emitter.emit_start("factory_test_job"))
        assert isinstance(run_id, UUID)
        emitter.close()
