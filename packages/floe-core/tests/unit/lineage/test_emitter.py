"""Tests for LineageEmitter and create_emitter factory.

Tests the high-level emitter that coordinates event building and transport,
and the factory function for creating emitters from configuration.
"""

from __future__ import annotations

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

from .conftest import _run

# Test constants for secret values (not real secrets)
TEST_API_KEY = "secret"  # pragma: allowlist secret


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
                "api_key": TEST_API_KEY,
            }
        )
        transport = emitter.transport
        assert isinstance(transport, HttpLineageTransport)
        assert transport._timeout == 10.0
        assert transport._api_key == TEST_API_KEY

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


class TestLineageEmitterInit:
    """Tests for LineageEmitter initialization."""

    @pytest.mark.requirement("REQ-516")
    def test_init_stores_transport(self) -> None:
        """__init__ stores the transport attribute."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        assert emitter.transport is transport

    @pytest.mark.requirement("REQ-516")
    def test_init_stores_event_builder(self) -> None:
        """__init__ stores the event_builder attribute."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        assert emitter.event_builder is builder

    @pytest.mark.requirement("REQ-516")
    def test_init_stores_default_namespace(self) -> None:
        """__init__ stores the default_namespace attribute."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "custom_namespace")

        assert emitter.default_namespace == "custom_namespace"

    @pytest.mark.requirement("REQ-516")
    def test_init_default_namespace_defaults_to_default(self) -> None:
        """__init__ uses 'default' namespace if not specified."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder)

        assert emitter.default_namespace == "default"


class TestEmitCompleteWithFacets:
    """Tests for emit_complete with facet parameters."""

    @pytest.mark.requirement("REQ-516")
    def test_emit_complete_with_run_facets(self) -> None:
        """emit_complete passes run_facets to event."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        run_id = uuid4()

        _run(
            emitter.emit_complete(
                run_id,
                "my_job",
                run_facets={"processing": {"recordCount": 1000}},
            )
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert "processing" in event.run.facets
        assert event.run.facets["processing"]["recordCount"] == 1000

    @pytest.mark.requirement("REQ-516")
    def test_emit_complete_with_job_facets(self) -> None:
        """emit_complete passes job_facets to event."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        run_id = uuid4()

        _run(
            emitter.emit_complete(
                run_id,
                "my_job",
                job_facets={"sql": {"query": "SELECT * FROM table"}},
            )
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert "sql" in event.job.facets
        assert event.job.facets["sql"]["query"] == "SELECT * FROM table"

    @pytest.mark.requirement("REQ-516")
    def test_emit_complete_with_all_optional_params(self) -> None:
        """emit_complete correctly handles all optional parameters."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        run_id = uuid4()
        outputs = [LineageDataset(namespace="gold", name="final_output")]

        _run(
            emitter.emit_complete(
                run_id,
                "my_job",
                outputs=outputs,
                run_facets={"custom": "run_value"},
                job_facets={"custom": "job_value"},
            )
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.COMPLETE
        assert len(event.outputs) == 1
        assert event.run.facets["custom"] == "run_value"
        assert event.job.facets["custom"] == "job_value"


class TestEmitFailWithFacets:
    """Tests for emit_fail with run_facets parameter."""

    @pytest.mark.requirement("REQ-516")
    def test_emit_fail_with_run_facets(self) -> None:
        """emit_fail passes run_facets to event."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        run_id = uuid4()

        _run(
            emitter.emit_fail(
                run_id,
                "my_job",
                run_facets={"errorDetails": {"stackTrace": "line 42"}},
            )
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.FAIL
        assert "errorDetails" in event.run.facets
        assert event.run.facets["errorDetails"]["stackTrace"] == "line 42"

    @pytest.mark.requirement("REQ-516")
    def test_emit_fail_with_error_message_and_run_facets(self) -> None:
        """emit_fail combines error_message and run_facets."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        run_id = uuid4()

        _run(
            emitter.emit_fail(
                run_id,
                "my_job",
                error_message="connection timeout",
                run_facets={"retryCount": 3},
            )
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.facets["errorMessage"]["message"] == "connection timeout"
        assert event.run.facets["retryCount"] == 3


class TestTransportErrorPropagation:
    """Tests for transport error handling."""

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_propagates_transport_error(self) -> None:
        """emit_start propagates transport exceptions."""
        transport = _make_mock_transport()
        transport.emit = AsyncMock(side_effect=ConnectionError("Network failure"))
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        with pytest.raises(ConnectionError, match="Network failure"):
            _run(emitter.emit_start("my_job"))

    @pytest.mark.requirement("REQ-516")
    def test_emit_complete_propagates_transport_error(self) -> None:
        """emit_complete propagates transport exceptions."""
        transport = _make_mock_transport()
        transport.emit = AsyncMock(side_effect=TimeoutError("Request timeout"))
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        with pytest.raises(TimeoutError, match="Request timeout"):
            _run(emitter.emit_complete(uuid4(), "my_job"))

    @pytest.mark.requirement("REQ-516")
    def test_emit_fail_propagates_transport_error(self) -> None:
        """emit_fail propagates transport exceptions."""
        transport = _make_mock_transport()
        transport.emit = AsyncMock(side_effect=RuntimeError("Server error"))
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        with pytest.raises(RuntimeError, match="Server error"):
            _run(emitter.emit_fail(uuid4(), "my_job"))


class TestEmitterEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_with_empty_inputs_list(self) -> None:
        """emit_start handles empty inputs list."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        _run(emitter.emit_start("my_job", inputs=[]))

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.inputs == []

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_with_empty_outputs_list(self) -> None:
        """emit_start handles empty outputs list."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        _run(emitter.emit_start("my_job", outputs=[]))

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.outputs == []

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_with_empty_facets(self) -> None:
        """emit_start handles empty facets dicts - event has empty facets."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        _run(emitter.emit_start("my_job", run_facets={}, job_facets={}))

        transport.emit.assert_awaited_once()
        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.facets == {}, "Empty run_facets should result in empty facets"
        assert event.job.facets == {}, "Empty job_facets should result in empty facets"

    @pytest.mark.requirement("REQ-516")
    def test_emit_complete_with_empty_outputs_list(self) -> None:
        """emit_complete handles empty outputs list."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        _run(emitter.emit_complete(uuid4(), "my_job", outputs=[]))

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.outputs == []

    @pytest.mark.requirement("REQ-516")
    def test_emit_start_with_multiple_inputs_and_outputs(self) -> None:
        """emit_start handles multiple datasets."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")
        inputs = [
            LineageDataset(namespace="raw", name="table_a"),
            LineageDataset(namespace="raw", name="table_b"),
            LineageDataset(namespace="raw", name="table_c"),
        ]
        outputs = [
            LineageDataset(namespace="staging", name="combined"),
            LineageDataset(namespace="staging", name="metrics"),
        ]

        _run(emitter.emit_start("multi_io_job", inputs=inputs, outputs=outputs))

        event: LineageEvent = transport.emit.call_args[0][0]
        assert len(event.inputs) == 3
        assert len(event.outputs) == 2
        assert event.inputs[0].name == "table_a"
        assert event.outputs[1].name == "metrics"

    @pytest.mark.requirement("REQ-516")
    def test_emit_fail_with_empty_error_message(self) -> None:
        """emit_fail handles empty string error message."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        _run(emitter.emit_fail(uuid4(), "my_job", error_message=""))

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.FAIL
        # Empty error message should still create the facet
        assert event.run.facets["errorMessage"]["message"] == ""


class TestCreateEmitterParametrized:
    """Parametrized tests for create_emitter factory."""

    @pytest.mark.requirement("REQ-527")
    @pytest.mark.parametrize(
        "config,expected_type",
        [
            (None, NoOpLineageTransport),
            ({}, NoOpLineageTransport),
            ({"type": None}, NoOpLineageTransport),
            ({"type": "console"}, ConsoleLineageTransport),
            ({"type": "http", "url": "http://localhost:5000"}, HttpLineageTransport),
            ({"type": "invalid"}, NoOpLineageTransport),
            ({"type": "CONSOLE"}, NoOpLineageTransport),  # Case-sensitive
            ({"type": ""}, NoOpLineageTransport),  # Empty string
        ],
    )
    def test_transport_type_selection(
        self, config: dict[str, Any] | None, expected_type: type
    ) -> None:
        """create_emitter selects correct transport based on config type."""
        emitter = create_emitter(config)
        assert isinstance(emitter.transport, expected_type)

    @pytest.mark.requirement("REQ-527")
    @pytest.mark.parametrize(
        "namespace,producer",
        [
            ("production", "floe-prod"),
            ("staging", "floe-stage"),
            ("development", "floe-dev"),
            ("", ""),  # Empty values
            ("namespace-with-dashes", "producer.with.dots"),
        ],
    )
    def test_namespace_and_producer_variations(
        self, namespace: str, producer: str
    ) -> None:
        """create_emitter correctly sets namespace and producer."""
        emitter = create_emitter(
            default_namespace=namespace,
            producer=producer,
        )
        assert emitter.default_namespace == namespace
        assert emitter.event_builder.producer == producer

    @pytest.mark.requirement("REQ-527")
    @pytest.mark.parametrize(
        "timeout",
        [0.1, 1.0, 5.0, 30.0, 120.0],
    )
    def test_http_timeout_variations(self, timeout: float) -> None:
        """create_emitter passes various timeout values to HTTP transport."""
        emitter = create_emitter(
            {"type": "http", "url": "http://localhost:5000", "timeout": timeout}
        )
        assert isinstance(emitter.transport, HttpLineageTransport)
        assert emitter.transport._timeout == timeout


class TestFullLifecycle:
    """Integration tests for complete emitter lifecycle."""

    @pytest.mark.requirement("REQ-516")
    def test_start_complete_lifecycle(self) -> None:
        """Test full start -> complete lifecycle."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        # Start the run
        run_id = _run(emitter.emit_start("lifecycle_job"))

        # Complete the run
        _run(emitter.emit_complete(run_id, "lifecycle_job"))

        # Verify both events were emitted
        assert transport.emit.await_count == 2
        start_event: LineageEvent = transport.emit.call_args_list[0][0][0]
        complete_event: LineageEvent = transport.emit.call_args_list[1][0][0]

        assert start_event.event_type == RunState.START
        assert complete_event.event_type == RunState.COMPLETE
        assert start_event.run.run_id == complete_event.run.run_id

    @pytest.mark.requirement("REQ-516")
    def test_start_fail_lifecycle(self) -> None:
        """Test full start -> fail lifecycle."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        # Start the run
        run_id = _run(emitter.emit_start("failing_job"))

        # Fail the run
        _run(emitter.emit_fail(run_id, "failing_job", error_message="Pipeline crashed"))

        # Verify both events were emitted
        assert transport.emit.await_count == 2
        start_event: LineageEvent = transport.emit.call_args_list[0][0][0]
        fail_event: LineageEvent = transport.emit.call_args_list[1][0][0]

        assert start_event.event_type == RunState.START
        assert fail_event.event_type == RunState.FAIL
        assert start_event.run.run_id == fail_event.run.run_id
        assert fail_event.run.facets["errorMessage"]["message"] == "Pipeline crashed"

    @pytest.mark.requirement("REQ-516")
    def test_emitter_close_after_lifecycle(self) -> None:
        """Test that close works correctly after emissions."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        run_id = _run(emitter.emit_start("job"))
        _run(emitter.emit_complete(run_id, "job"))
        emitter.close()

        assert transport.emit.await_count == 2
        transport.close.assert_called_once()

    @pytest.mark.requirement("REQ-516")
    def test_multiple_runs_same_emitter(self) -> None:
        """Test multiple runs through the same emitter."""
        transport = _make_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = LineageEmitter(transport, builder, "test")

        # First run
        run_id_1 = _run(emitter.emit_start("job_1"))
        _run(emitter.emit_complete(run_id_1, "job_1"))

        # Second run
        run_id_2 = _run(emitter.emit_start("job_2"))
        _run(emitter.emit_fail(run_id_2, "job_2", error_message="error"))

        # Verify all events
        assert transport.emit.await_count == 4
        assert run_id_1 != run_id_2  # Each run gets unique ID
