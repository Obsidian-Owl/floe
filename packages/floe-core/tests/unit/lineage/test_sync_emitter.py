"""Tests for SyncLineageEmitter and create_sync_emitter factory.

Tests the synchronous emitter that coordinates EventBuilder and sync transports,
plus the factory function for creating sync emitters from configuration.

"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from floe_core.lineage.emitter import SyncLineageEmitter, create_sync_emitter
from floe_core.lineage.events import EventBuilder
from floe_core.lineage.transport import (
    SyncConsoleLineageTransport,
    SyncHttpLineageTransport,
    SyncNoOpTransport,
)
from floe_core.lineage.types import LineageDataset, LineageEvent, RunState

# Test constants for secret values (not real secrets)
TEST_API_KEY = "test-sync-emitter-key"  # pragma: allowlist secret
TEST_HTTP_URL = "http://localhost:5000/api/v1/lineage"


def _make_sync_mock_transport() -> MagicMock:
    """Create a mock sync transport with synchronous emit and close."""
    transport = MagicMock()
    transport.emit = MagicMock(return_value=None)
    transport.close = MagicMock(return_value=None)
    return transport


class TestSyncLineageEmitterInit:
    """Tests for SyncLineageEmitter initialization."""

    @pytest.mark.requirement("AC-OLC-3")
    def test_init_stores_transport(self) -> None:
        """__init__ stores the transport attribute for later use."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        assert emitter.transport is transport

    @pytest.mark.requirement("AC-OLC-3")
    def test_init_stores_event_builder(self) -> None:
        """__init__ stores the event_builder attribute."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        assert emitter.event_builder is builder

    @pytest.mark.requirement("AC-OLC-3")
    def test_init_stores_default_namespace(self) -> None:
        """__init__ stores the default_namespace attribute."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "custom_ns")

        assert emitter.default_namespace == "custom_ns"

    @pytest.mark.requirement("AC-OLC-3")
    def test_init_default_namespace_defaults_to_default(self) -> None:
        """__init__ uses 'default' namespace when not specified."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder)

        assert emitter.default_namespace == "default"


class TestSyncEmitStart:
    """Tests for SyncLineageEmitter.emit_start()."""

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_returns_uuid(self) -> None:
        """emit_start returns a UUID run_id."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        run_id = emitter.emit_start("my_job")

        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_calls_transport_emit(self) -> None:
        """emit_start MUST call transport.emit() -- not just return a UUID.

        Guards against an accomplishment-simulator that generates a UUID
        but never actually emits the event.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.emit_start("my_job")

        transport.emit.assert_called_once()
        event: LineageEvent = transport.emit.call_args[0][0]
        assert isinstance(event, LineageEvent)
        assert event.event_type == RunState.START
        assert event.job.name == "my_job"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_event_run_id_matches_return(self) -> None:
        """The run_id in the emitted event must match the returned run_id.

        Guards against returning a different UUID than what was emitted.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        run_id = emitter.emit_start("my_job")

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.run_id == run_id

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_generates_run_id_when_none(self) -> None:
        """emit_start auto-generates a UUID when run_id is not provided.

        Two calls must produce different UUIDs.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        run_id_1 = emitter.emit_start("job_a")
        run_id_2 = emitter.emit_start("job_b")

        assert run_id_1 != run_id_2, "Auto-generated run_ids must be unique"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_uses_explicit_run_id(self) -> None:
        """emit_start uses the provided run_id instead of generating one."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        expected_id = uuid4()

        run_id = emitter.emit_start("my_job", run_id=expected_id)

        assert run_id == expected_id

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_with_inputs_and_outputs(self) -> None:
        """emit_start passes inputs and outputs through to the event."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        inp = [LineageDataset(namespace="raw", name="source_table")]
        out = [LineageDataset(namespace="staging", name="dest_table")]

        emitter.emit_start("etl_job", inputs=inp, outputs=out)

        event: LineageEvent = transport.emit.call_args[0][0]
        assert len(event.inputs) == 1
        assert event.inputs[0].name == "source_table"
        assert event.inputs[0].namespace == "raw"
        assert len(event.outputs) == 1
        assert event.outputs[0].name == "dest_table"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_with_run_facets(self) -> None:
        """emit_start passes run_facets through to the event."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.emit_start("my_job", run_facets={"custom_key": "custom_value"})

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.facets["custom_key"] == "custom_value"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_with_job_facets(self) -> None:
        """emit_start passes job_facets through to the event."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.emit_start("my_job", job_facets={"sql": "SELECT 1"})

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.job.facets["sql"] == "SELECT 1"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_is_synchronous(self) -> None:
        """emit_start must be a plain function, not a coroutine.

        Guards against copy-paste from async LineageEmitter without
        removing the 'async' keyword.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        assert not inspect.iscoroutinefunction(emitter.emit_start), (
            "emit_start() must be synchronous (def, not async def)"
        )

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_uses_event_builder(self) -> None:
        """emit_start must use EventBuilder (shared with async emitter).

        Verify the event has the correct producer and namespace from
        the builder, proving it delegates to EventBuilder.start_run().
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="my-producer", default_namespace="prod")
        emitter = SyncLineageEmitter(transport, builder, "prod")

        emitter.emit_start("my_job")

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.producer == "my-producer", "Event producer must come from EventBuilder"
        assert event.job.namespace == "prod", "Job namespace must come from EventBuilder"


class TestSyncEmitComplete:
    """Tests for SyncLineageEmitter.emit_complete()."""

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_complete_calls_transport_emit(self) -> None:
        """emit_complete must call transport.emit() with a COMPLETE event."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        run_id = uuid4()

        emitter.emit_complete(run_id, "my_job")

        transport.emit.assert_called_once()
        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.COMPLETE
        assert event.run.run_id == run_id
        assert event.job.name == "my_job"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_complete_requires_run_id_and_job_name(self) -> None:
        """emit_complete requires run_id and job_name as positional/keyword args.

        Guards against an implementation that makes these optional.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        # Should work with both args
        run_id = uuid4()
        emitter.emit_complete(run_id, "my_job")

        # Verify the event got the right run_id and job_name
        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.run_id == run_id
        assert event.job.name == "my_job"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_complete_with_outputs(self) -> None:
        """emit_complete passes outputs through to event."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        out = [LineageDataset(namespace="gold", name="final_table")]

        emitter.emit_complete(uuid4(), "my_job", outputs=out)

        event: LineageEvent = transport.emit.call_args[0][0]
        assert len(event.outputs) == 1
        assert event.outputs[0].name == "final_table"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_complete_with_facets(self) -> None:
        """emit_complete passes run_facets and job_facets through."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.emit_complete(
            uuid4(),
            "my_job",
            run_facets={"processing": {"rowCount": 42}},
            job_facets={"query": "SELECT *"},
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.facets["processing"]["rowCount"] == 42
        assert event.job.facets["query"] == "SELECT *"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_complete_is_synchronous(self) -> None:
        """emit_complete must be synchronous."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        assert not inspect.iscoroutinefunction(emitter.emit_complete), (
            "emit_complete() must be synchronous (def, not async def)"
        )

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_complete_returns_none(self) -> None:
        """emit_complete returns None (unlike emit_start which returns UUID)."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        result = emitter.emit_complete(uuid4(), "my_job")

        assert result is None


class TestSyncEmitFail:
    """Tests for SyncLineageEmitter.emit_fail()."""

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_calls_transport_emit(self) -> None:
        """emit_fail must call transport.emit() with a FAIL event."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        run_id = uuid4()

        emitter.emit_fail(run_id, "my_job")

        transport.emit.assert_called_once()
        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.event_type == RunState.FAIL
        assert event.run.run_id == run_id
        assert event.job.name == "my_job"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_requires_run_id_and_job_name(self) -> None:
        """emit_fail requires run_id and job_name."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        run_id = uuid4()

        emitter.emit_fail(run_id, "failing_job")

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.run_id == run_id
        assert event.job.name == "failing_job"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_with_error_message_creates_facet(self) -> None:
        """emit_fail with error_message creates an ErrorMessageRunFacet.

        The facet must contain the exact error message string, the producer,
        the schema URL, and programmingLanguage. This is the OpenLineage spec.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        run_id = uuid4()

        emitter.emit_fail(run_id, "my_job", error_message="connection timed out")

        event: LineageEvent = transport.emit.call_args[0][0]
        assert "errorMessage" in event.run.facets, (
            "emit_fail with error_message must create errorMessage facet"
        )
        facet = event.run.facets["errorMessage"]
        assert facet["message"] == "connection timed out", (
            f"Error message must be exact, got: {facet.get('message')}"
        )
        assert facet["programmingLanguage"] == "python", (
            "ErrorMessageRunFacet must include programmingLanguage='python'"
        )
        assert "ErrorMessageRunFacet" in facet["_schemaURL"], (
            "ErrorMessageRunFacet must have correct schema URL"
        )

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_without_error_message_no_facet(self) -> None:
        """emit_fail without error_message must NOT create errorMessage facet."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.emit_fail(uuid4(), "my_job")

        event: LineageEvent = transport.emit.call_args[0][0]
        assert "errorMessage" not in event.run.facets

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_with_empty_error_message(self) -> None:
        """emit_fail with empty string error_message still creates facet.

        Empty string is not None -- the facet should still be present.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.emit_fail(uuid4(), "my_job", error_message="")

        event: LineageEvent = transport.emit.call_args[0][0]
        assert "errorMessage" in event.run.facets
        assert event.run.facets["errorMessage"]["message"] == ""

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_with_run_facets(self) -> None:
        """emit_fail passes run_facets through to event."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.emit_fail(
            uuid4(),
            "my_job",
            run_facets={"retryCount": 3},
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.facets["retryCount"] == 3

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_combines_error_message_and_run_facets(self) -> None:
        """emit_fail with both error_message and run_facets includes both.

        Guards against an implementation that overwrites run_facets with
        the error facet or vice versa.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.emit_fail(
            uuid4(),
            "my_job",
            error_message="disk full",
            run_facets={"retryCount": 5},
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.facets["errorMessage"]["message"] == "disk full"
        assert event.run.facets["retryCount"] == 5

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_is_synchronous(self) -> None:
        """emit_fail must be synchronous."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        assert not inspect.iscoroutinefunction(emitter.emit_fail), (
            "emit_fail() must be synchronous (def, not async def)"
        )

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_returns_none(self) -> None:
        """emit_fail returns None."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        result = emitter.emit_fail(uuid4(), "my_job")

        assert result is None


class TestSyncEmitterClose:
    """Tests for SyncLineageEmitter.close()."""

    @pytest.mark.requirement("AC-OLC-3")
    def test_close_delegates_to_transport(self) -> None:
        """close() must call transport.close().

        Guards against a no-op close that ignores the transport.
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        emitter.close()

        transport.close.assert_called_once()

    @pytest.mark.requirement("AC-OLC-3")
    def test_close_is_synchronous(self) -> None:
        """close() must be synchronous."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        assert not inspect.iscoroutinefunction(emitter.close), (
            "close() must be synchronous (def, not async def)"
        )


class TestSyncEmitterErrorPropagation:
    """Tests for transport error handling in sync emitter."""

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_propagates_transport_error(self) -> None:
        """Transport exceptions from emit_start must propagate to caller."""
        transport = _make_sync_mock_transport()
        transport.emit.side_effect = ConnectionError("Network failure")
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        with pytest.raises(ConnectionError, match="Network failure"):
            emitter.emit_start("my_job")

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_complete_propagates_transport_error(self) -> None:
        """Transport exceptions from emit_complete must propagate."""
        transport = _make_sync_mock_transport()
        transport.emit.side_effect = TimeoutError("Request timeout")
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        with pytest.raises(TimeoutError, match="Request timeout"):
            emitter.emit_complete(uuid4(), "my_job")

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_propagates_transport_error(self) -> None:
        """Transport exceptions from emit_fail must propagate."""
        transport = _make_sync_mock_transport()
        transport.emit.side_effect = RuntimeError("Server error")
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        with pytest.raises(RuntimeError, match="Server error"):
            emitter.emit_fail(uuid4(), "my_job")


class TestSyncEmitterLifecycle:
    """Integration-style tests for complete sync emitter lifecycle."""

    @pytest.mark.requirement("AC-OLC-3")
    def test_start_complete_lifecycle(self) -> None:
        """Full start -> complete lifecycle emits two events with matching run_id."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        run_id = emitter.emit_start("lifecycle_job")
        emitter.emit_complete(run_id, "lifecycle_job")

        assert transport.emit.call_count == 2
        start_event: LineageEvent = transport.emit.call_args_list[0][0][0]
        complete_event: LineageEvent = transport.emit.call_args_list[1][0][0]

        assert start_event.event_type == RunState.START
        assert complete_event.event_type == RunState.COMPLETE
        assert start_event.run.run_id == complete_event.run.run_id

    @pytest.mark.requirement("AC-OLC-3")
    def test_start_fail_lifecycle(self) -> None:
        """Full start -> fail lifecycle emits two events with matching run_id."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        run_id = emitter.emit_start("failing_job")
        emitter.emit_fail(run_id, "failing_job", error_message="Pipeline crashed")

        assert transport.emit.call_count == 2
        start_event: LineageEvent = transport.emit.call_args_list[0][0][0]
        fail_event: LineageEvent = transport.emit.call_args_list[1][0][0]

        assert start_event.event_type == RunState.START
        assert fail_event.event_type == RunState.FAIL
        assert start_event.run.run_id == fail_event.run.run_id
        assert fail_event.run.facets["errorMessage"]["message"] == "Pipeline crashed"

    @pytest.mark.requirement("AC-OLC-3")
    def test_close_after_lifecycle(self) -> None:
        """close() works after emissions."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        run_id = emitter.emit_start("job")
        emitter.emit_complete(run_id, "job")
        emitter.close()

        assert transport.emit.call_count == 2
        transport.close.assert_called_once()

    @pytest.mark.requirement("AC-OLC-3")
    def test_multiple_runs_same_emitter(self) -> None:
        """Multiple runs through the same emitter produce distinct run_ids."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        run_id_1 = emitter.emit_start("job_a")
        emitter.emit_complete(run_id_1, "job_a")
        run_id_2 = emitter.emit_start("job_b")
        emitter.emit_fail(run_id_2, "job_b", error_message="error")

        assert transport.emit.call_count == 4
        assert run_id_1 != run_id_2, "Each run must have a unique run_id"


class TestSyncEmitterSignatureParityWithAsync:
    """Tests ensuring sync emitter has same parameter signatures as async.

    Guards against a partial implementation that omits parameters available
    in the async version.
    """

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_start_accepts_all_parameters(self) -> None:
        """emit_start must accept job_name, run_id, inputs, outputs, run_facets, job_facets.

        This is the same signature as async LineageEmitter.emit_start().
        """
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        explicit_id = uuid4()
        inp = [LineageDataset(namespace="raw", name="t1")]
        out = [LineageDataset(namespace="staging", name="t2")]

        # Must not raise -- all parameters accepted
        run_id = emitter.emit_start(
            "full_param_job",
            run_id=explicit_id,
            inputs=inp,
            outputs=out,
            run_facets={"key": "val"},
            job_facets={"sql": "SELECT 1"},
        )

        assert run_id == explicit_id
        event: LineageEvent = transport.emit.call_args[0][0]
        assert len(event.inputs) == 1
        assert len(event.outputs) == 1
        assert event.run.facets["key"] == "val"
        assert event.job.facets["sql"] == "SELECT 1"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_complete_accepts_all_parameters(self) -> None:
        """emit_complete must accept run_id, job_name, outputs, run_facets, job_facets."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")
        out = [LineageDataset(namespace="gold", name="result")]

        # Must not raise
        emitter.emit_complete(
            uuid4(),
            "my_job",
            outputs=out,
            run_facets={"duration_ms": 1234},
            job_facets={"version": "1.0"},
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert len(event.outputs) == 1
        assert event.run.facets["duration_ms"] == 1234
        assert event.job.facets["version"] == "1.0"

    @pytest.mark.requirement("AC-OLC-3")
    def test_emit_fail_accepts_error_message_and_run_facets(self) -> None:
        """emit_fail must accept run_id, job_name, error_message, run_facets."""
        transport = _make_sync_mock_transport()
        builder = EventBuilder(producer="floe", default_namespace="test")
        emitter = SyncLineageEmitter(transport, builder, "test")

        # Must not raise
        emitter.emit_fail(
            uuid4(),
            "my_job",
            error_message="disk full",
            run_facets={"attempt": 3},
        )

        event: LineageEvent = transport.emit.call_args[0][0]
        assert event.run.facets["errorMessage"]["message"] == "disk full"
        assert event.run.facets["attempt"] == 3


class TestCreateSyncEmitterTransportSelection:
    """Tests for create_sync_emitter factory transport type routing."""

    @pytest.mark.requirement("AC-OLC-4")
    def test_none_config_creates_noop(self) -> None:
        """None config creates emitter with SyncNoOpTransport."""
        emitter = create_sync_emitter()
        assert isinstance(emitter.transport, SyncNoOpTransport)

    @pytest.mark.requirement("AC-OLC-4")
    def test_none_type_creates_noop(self) -> None:
        """Config with type=None creates SyncNoOpTransport."""
        emitter = create_sync_emitter({"type": None})
        assert isinstance(emitter.transport, SyncNoOpTransport)

    @pytest.mark.requirement("AC-OLC-4")
    def test_empty_dict_creates_noop(self) -> None:
        """Empty dict config (no 'type' key) creates SyncNoOpTransport."""
        emitter = create_sync_emitter({})
        assert isinstance(emitter.transport, SyncNoOpTransport)

    @pytest.mark.requirement("AC-OLC-4")
    def test_console_config_creates_console(self) -> None:
        """Console config creates emitter with SyncConsoleLineageTransport."""
        emitter = create_sync_emitter({"type": "console"})
        assert isinstance(emitter.transport, SyncConsoleLineageTransport)

    @pytest.mark.requirement("AC-OLC-4")
    def test_http_config_creates_http(self) -> None:
        """HTTP config creates emitter with SyncHttpLineageTransport."""
        emitter = create_sync_emitter({"type": "http", "url": TEST_HTTP_URL})
        assert isinstance(emitter.transport, SyncHttpLineageTransport)

    @pytest.mark.requirement("AC-OLC-4")
    def test_unknown_type_creates_noop(self) -> None:
        """Unrecognized type falls back to SyncNoOpTransport."""
        emitter = create_sync_emitter({"type": "kafka"})
        assert isinstance(emitter.transport, SyncNoOpTransport)

    @pytest.mark.requirement("AC-OLC-4")
    def test_case_sensitive_type(self) -> None:
        """Type matching is case-sensitive: 'CONSOLE' is unrecognized."""
        emitter = create_sync_emitter({"type": "CONSOLE"})
        assert isinstance(emitter.transport, SyncNoOpTransport)

    @pytest.mark.requirement("AC-OLC-4")
    def test_empty_string_type_creates_noop(self) -> None:
        """Empty string type falls back to SyncNoOpTransport."""
        emitter = create_sync_emitter({"type": ""})
        assert isinstance(emitter.transport, SyncNoOpTransport)


class TestCreateSyncEmitterHttpConfig:
    """Tests for create_sync_emitter HTTP transport configuration."""

    @pytest.mark.requirement("AC-OLC-4")
    def test_http_passes_url(self) -> None:
        """HTTP transport must receive the configured URL."""
        emitter = create_sync_emitter({"type": "http", "url": TEST_HTTP_URL})
        transport = emitter.transport
        assert isinstance(transport, SyncHttpLineageTransport)
        assert transport._url == TEST_HTTP_URL

    @pytest.mark.requirement("AC-OLC-4")
    def test_http_passes_timeout(self) -> None:
        """HTTP transport must receive the configured timeout."""
        emitter = create_sync_emitter(
            {
                "type": "http",
                "url": TEST_HTTP_URL,
                "timeout": 15.0,
            }
        )
        transport = emitter.transport
        assert isinstance(transport, SyncHttpLineageTransport)
        assert transport._timeout == pytest.approx(15.0)

    @pytest.mark.requirement("AC-OLC-4")
    def test_http_passes_api_key(self) -> None:
        """HTTP transport must receive the configured api_key."""
        emitter = create_sync_emitter(
            {
                "type": "http",
                "url": TEST_HTTP_URL,
                "api_key": TEST_API_KEY,
            }
        )
        transport = emitter.transport
        assert isinstance(transport, SyncHttpLineageTransport)
        assert transport._api_key == TEST_API_KEY

    @pytest.mark.requirement("AC-OLC-4")
    def test_http_default_timeout(self) -> None:
        """HTTP transport uses default timeout when not specified."""
        emitter = create_sync_emitter({"type": "http", "url": TEST_HTTP_URL})
        transport = emitter.transport
        assert isinstance(transport, SyncHttpLineageTransport)
        assert transport._timeout == pytest.approx(5.0)


class TestCreateSyncEmitterNamespaceAndProducer:
    """Tests for create_sync_emitter namespace and producer configuration."""

    @pytest.mark.requirement("AC-OLC-4")
    def test_factory_sets_namespace(self) -> None:
        """Factory passes default_namespace to the emitter."""
        emitter = create_sync_emitter(default_namespace="production")
        assert emitter.default_namespace == "production"

    @pytest.mark.requirement("AC-OLC-4")
    def test_factory_sets_producer(self) -> None:
        """Factory passes producer to the EventBuilder."""
        emitter = create_sync_emitter(producer="floe-test")
        assert emitter.event_builder.producer == "floe-test"

    @pytest.mark.requirement("AC-OLC-4")
    def test_factory_namespace_propagates_to_builder(self) -> None:
        """Factory namespace is used by EventBuilder for events."""
        emitter = create_sync_emitter(default_namespace="staging")
        assert emitter.event_builder.default_namespace == "staging"

    @pytest.mark.requirement("AC-OLC-4")
    def test_factory_default_namespace_is_default(self) -> None:
        """Factory defaults to 'default' namespace when not specified."""
        emitter = create_sync_emitter()
        assert emitter.default_namespace == "default"

    @pytest.mark.requirement("AC-OLC-4")
    def test_factory_default_producer_is_floe(self) -> None:
        """Factory defaults to 'floe' producer when not specified."""
        emitter = create_sync_emitter()
        assert emitter.event_builder.producer == "floe"


class TestCreateSyncEmitterReturnsWorkingEmitter:
    """Tests that factory-created emitters actually work end-to-end."""

    @pytest.mark.requirement("AC-OLC-4")
    def test_noop_emitter_can_emit(self) -> None:
        """Factory-created NoOp emitter can complete full lifecycle."""
        emitter = create_sync_emitter()
        run_id = emitter.emit_start("factory_test")
        assert isinstance(run_id, UUID)
        emitter.emit_complete(run_id, "factory_test")
        emitter.close()

    @pytest.mark.requirement("AC-OLC-4")
    def test_console_emitter_can_emit(self) -> None:
        """Factory-created console emitter can complete full lifecycle."""
        emitter = create_sync_emitter({"type": "console"}, default_namespace="test")
        run_id = emitter.emit_start("console_factory_test")
        assert isinstance(run_id, UUID)
        emitter.emit_complete(run_id, "console_factory_test")
        emitter.close()

    @pytest.mark.requirement("AC-OLC-4")
    def test_factory_returns_sync_emitter_type(self) -> None:
        """Factory must return SyncLineageEmitter, not async LineageEmitter."""
        emitter = create_sync_emitter()
        assert isinstance(emitter, SyncLineageEmitter)

    @pytest.mark.requirement("AC-OLC-4")
    def test_factory_same_config_format_as_async(self) -> None:
        """Factory accepts same config dict format as async create_emitter().

        Ensures parity between sync and async factory signatures.
        """
        configs: list[dict[str, Any] | None] = [
            None,
            {"type": None},
            {"type": "console"},
            {"type": "http", "url": TEST_HTTP_URL, "timeout": 10.0, "api_key": TEST_API_KEY},
            {"type": "unknown"},
        ]
        for config in configs:
            emitter = create_sync_emitter(config)
            assert isinstance(emitter, SyncLineageEmitter), (
                f"create_sync_emitter({config}) must return SyncLineageEmitter"
            )


class TestCreateSyncEmitterParametrized:
    """Parametrized tests for create_sync_emitter factory."""

    @pytest.mark.requirement("AC-OLC-4")
    @pytest.mark.parametrize(
        "config,expected_type",
        [
            (None, SyncNoOpTransport),
            ({}, SyncNoOpTransport),
            ({"type": None}, SyncNoOpTransport),
            ({"type": "console"}, SyncConsoleLineageTransport),
            ({"type": "http", "url": "http://localhost:5000"}, SyncHttpLineageTransport),
            ({"type": "invalid"}, SyncNoOpTransport),
            ({"type": "CONSOLE"}, SyncNoOpTransport),
            ({"type": ""}, SyncNoOpTransport),
            ({"type": "Http"}, SyncNoOpTransport),
            ({"type": "HTTP"}, SyncNoOpTransport),
        ],
    )
    def test_transport_type_selection(
        self, config: dict[str, Any] | None, expected_type: type
    ) -> None:
        """create_sync_emitter selects correct SYNC transport based on config type."""
        emitter = create_sync_emitter(config)
        assert isinstance(emitter.transport, expected_type), (
            f"Config {config} should produce {expected_type.__name__}, "
            f"got {type(emitter.transport).__name__}"
        )

    @pytest.mark.requirement("AC-OLC-4")
    @pytest.mark.parametrize(
        "namespace,producer",
        [
            ("production", "floe-prod"),
            ("staging", "floe-stage"),
            ("development", "floe-dev"),
            ("ns-with-dashes", "producer.with.dots"),
        ],
    )
    def test_namespace_and_producer_variations(self, namespace: str, producer: str) -> None:
        """create_sync_emitter correctly sets namespace and producer."""
        emitter = create_sync_emitter(
            default_namespace=namespace,
            producer=producer,
        )
        assert emitter.default_namespace == namespace
        assert emitter.event_builder.producer == producer


class TestCreateSyncEmitterValidation:
    """Tests for input validation in create_sync_emitter factory."""

    @pytest.mark.requirement("AC-OLC-4")
    def test_http_without_url_raises_value_error(self) -> None:
        """HTTP transport config missing 'url' raises ValueError, not KeyError."""
        with pytest.raises(ValueError, match="HTTP transport requires a 'url' key"):
            create_sync_emitter({"type": "http"})

    @pytest.mark.requirement("AC-OLC-4")
    def test_http_with_none_url_raises_value_error(self) -> None:
        """HTTP transport config with url=None raises ValueError."""
        with pytest.raises(ValueError, match="HTTP transport requires a 'url' key"):
            create_sync_emitter({"type": "http", "url": None})
