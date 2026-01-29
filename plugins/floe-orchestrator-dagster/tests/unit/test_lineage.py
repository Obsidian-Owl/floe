"""Unit tests for lineage event emission in DagsterOrchestratorPlugin.

These tests verify the emit_lineage_event() method constructs correct
OpenLineage events and handles unconfigured backends gracefully.

Note: @pytest.mark.requirement markers are used for traceability to spec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from floe_core.lineage import LineageDataset, RunState
from floe_core.plugins.orchestrator import Dataset

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestLineageEventValidation:
    """Test event type validation.

    Validates FR-016: System MUST support START/COMPLETE/FAIL event types.
    """

    @pytest.mark.requirement("FR-016")
    def test_start_event_type_valid(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test START event type is accepted."""
        run_id = dagster_plugin.emit_lineage_event(RunState.START, "job")
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_complete_event_type_valid(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test COMPLETE event type is accepted."""
        run_id = dagster_plugin.emit_lineage_event(RunState.COMPLETE, "job")
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_fail_event_type_valid(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test FAIL event type is accepted."""
        run_id = dagster_plugin.emit_lineage_event(RunState.FAIL, "job")
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_running_event_type_valid(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test RUNNING event type is accepted."""
        run_id = dagster_plugin.emit_lineage_event(RunState.RUNNING, "job")
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_abort_event_type_valid(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test ABORT event type is accepted."""
        run_id = dagster_plugin.emit_lineage_event(RunState.ABORT, "job")
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_other_event_type_valid(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test OTHER event type is accepted."""
        run_id = dagster_plugin.emit_lineage_event(RunState.OTHER, "job")
        assert isinstance(run_id, UUID)


class TestLineageEventInputsOutputs:
    """Test handling of input/output datasets.

    Validates FR-017: System MUST include inputs and outputs in lineage events.
    """

    @pytest.mark.requirement("FR-017")
    def test_empty_inputs_outputs(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test lineage event with empty inputs and outputs."""
        run_id = dagster_plugin.emit_lineage_event(RunState.START, "job")
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-017")
    def test_single_input_dataset(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test lineage event with single input dataset."""
        inputs = [LineageDataset(namespace="floe", name="raw.customers")]

        run_id = dagster_plugin.emit_lineage_event(RunState.START, "job", inputs=inputs)
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-017")
    def test_single_output_dataset(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test lineage event with single output dataset."""
        outputs = [LineageDataset(namespace="floe", name="staging.stg_customers")]

        run_id = dagster_plugin.emit_lineage_event(RunState.COMPLETE, "job", outputs=outputs)
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-017")
    def test_multiple_inputs_outputs(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test lineage event with multiple inputs and outputs."""
        inputs = [
            LineageDataset(namespace="floe", name="raw.orders"),
            LineageDataset(namespace="floe", name="raw.customers"),
            LineageDataset(namespace="floe", name="raw.products"),
        ]
        outputs = [
            LineageDataset(namespace="floe", name="staging.fact_orders"),
        ]

        run_id = dagster_plugin.emit_lineage_event(
            RunState.COMPLETE, "transform_job", inputs=inputs, outputs=outputs
        )
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-017")
    def test_dataset_with_different_namespaces(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test datasets can have different namespaces."""
        inputs = [
            LineageDataset(namespace="external", name="api.data"),
            LineageDataset(namespace="floe", name="raw.config"),
        ]
        outputs = [
            LineageDataset(namespace="floe", name="staging.merged"),
        ]

        run_id = dagster_plugin.emit_lineage_event(
            RunState.COMPLETE, "merge_job", inputs=inputs, outputs=outputs
        )
        assert isinstance(run_id, UUID)


class TestLineageEventNoOp:
    """Test graceful no-op when no backend configured.

    Validates FR-018: System MUST not raise when lineage backend unconfigured.
    """

    @pytest.mark.requirement("FR-018")
    def test_no_backend_is_noop(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test emit_lineage_event is no-op when no backend configured."""
        inputs = [LineageDataset(namespace="floe", name="input")]
        outputs = [LineageDataset(namespace="floe", name="output")]

        # Should not raise and returns a UUID
        run_id = dagster_plugin.emit_lineage_event(
            RunState.START, "test_job", inputs=inputs, outputs=outputs
        )
        assert isinstance(run_id, UUID)

        run_id = dagster_plugin.emit_lineage_event(
            RunState.COMPLETE, "test_job", inputs=inputs, outputs=outputs
        )
        assert isinstance(run_id, UUID)

        run_id = dagster_plugin.emit_lineage_event(
            RunState.FAIL, "test_job", inputs=inputs, outputs=outputs
        )
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-018")
    def test_no_backend_no_event_stored(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test no lineage event is stored when no backend configured."""
        dagster_plugin.emit_lineage_event(RunState.START, "job")

        # _last_lineage_event should not exist (only set when backend exists)
        assert not hasattr(dagster_plugin, "_last_lineage_event")

    @pytest.mark.requirement("FR-018")
    def test_multiple_events_without_backend(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test multiple events work without backend."""
        for event_type in [RunState.START, RunState.COMPLETE, RunState.FAIL]:
            for i in range(5):
                run_id = dagster_plugin.emit_lineage_event(event_type, f"job_{i}")
                assert isinstance(run_id, UUID)


class TestOpenLineageEventStructure:
    """Test OpenLineage event structure is correct.

    Note: _build_openlineage_event is a private helper that uses string event types.
    Validates FR-016: OpenLineage event structure compliance.
    """

    @pytest.mark.requirement("FR-016")
    def test_build_event_contains_event_type(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test built event contains eventType."""
        event = dagster_plugin._build_openlineage_event("START", "job", [], [])

        assert event["eventType"] == "START"

    @pytest.mark.requirement("FR-016")
    def test_build_event_contains_event_time(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test built event contains eventTime in ISO format."""
        event = dagster_plugin._build_openlineage_event("START", "job", [], [])

        assert "eventTime" in event
        # Should be ISO format with timezone
        assert "T" in event["eventTime"]
        assert "+" in event["eventTime"] or "Z" in event["eventTime"]

    @pytest.mark.requirement("FR-016")
    def test_build_event_contains_producer(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test built event contains producer identifier."""
        event = dagster_plugin._build_openlineage_event("START", "job", [], [])

        assert "producer" in event
        assert "floe-orchestrator-dagster" in event["producer"]
        assert dagster_plugin.version in event["producer"]

    @pytest.mark.requirement("FR-016")
    def test_build_event_contains_job(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test built event contains job with namespace and name."""
        event = dagster_plugin._build_openlineage_event("START", "my_job", [], [])

        assert "job" in event
        assert event["job"]["namespace"] == "floe"
        assert event["job"]["name"] == "my_job"

    @pytest.mark.requirement("FR-017")
    def test_build_event_contains_inputs(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test built event contains inputs list."""
        inputs = [
            Dataset(namespace="floe", name="raw.customers"),
            Dataset(namespace="external", name="api.data"),
        ]

        event = dagster_plugin._build_openlineage_event("START", "job", inputs, [])

        assert "inputs" in event
        assert len(event["inputs"]) == 2
        assert event["inputs"][0]["namespace"] == "floe"
        assert event["inputs"][0]["name"] == "raw.customers"
        assert event["inputs"][1]["namespace"] == "external"
        assert event["inputs"][1]["name"] == "api.data"

    @pytest.mark.requirement("FR-017")
    def test_build_event_contains_outputs(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test built event contains outputs list."""
        outputs = [
            Dataset(namespace="floe", name="staging.stg_customers"),
        ]

        event = dagster_plugin._build_openlineage_event("COMPLETE", "job", [], outputs)

        assert "outputs" in event
        assert len(event["outputs"]) == 1
        assert event["outputs"][0]["namespace"] == "floe"
        assert event["outputs"][0]["name"] == "staging.stg_customers"

    @pytest.mark.requirement("FR-017")
    def test_build_event_empty_inputs_outputs(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test built event has empty lists for inputs/outputs when none provided."""
        event = dagster_plugin._build_openlineage_event("START", "job", [], [])

        assert event["inputs"] == []
        assert event["outputs"] == []


class TestLineageEventEdgeCases:
    """Test edge cases for lineage event emission.

    Validates FR-016: Edge cases for lineage event handling.
    """

    @pytest.mark.requirement("FR-016")
    def test_job_name_with_underscores(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test job name with underscores."""
        run_id = dagster_plugin.emit_lineage_event(RunState.START, "my_dbt_job_v2")
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_job_name_with_dots(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test job name with dots."""
        run_id = dagster_plugin.emit_lineage_event(RunState.START, "staging.customers")
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-017")
    def test_dataset_name_with_special_chars(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test dataset names with dots and underscores."""
        inputs = [LineageDataset(namespace="floe.prod", name="raw_v2.customers_2024")]

        run_id = dagster_plugin.emit_lineage_event(RunState.START, "job", inputs=inputs)
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-017")
    def test_long_dataset_list(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test handling many datasets."""
        inputs = [LineageDataset(namespace="floe", name=f"source_{i}") for i in range(20)]
        outputs = [LineageDataset(namespace="floe", name=f"output_{i}") for i in range(10)]

        run_id = dagster_plugin.emit_lineage_event(
            RunState.COMPLETE, "big_job", inputs=inputs, outputs=outputs
        )
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_emit_returns_uuid(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test emit_lineage_event returns a UUID."""
        run_id = dagster_plugin.emit_lineage_event(RunState.START, "job")

        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_emit_accepts_custom_run_id(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test emit_lineage_event accepts custom run_id."""
        from uuid import uuid4

        custom_id = uuid4()
        run_id = dagster_plugin.emit_lineage_event(RunState.START, "job", run_id=custom_id)

        assert run_id == custom_id
        assert isinstance(run_id, UUID)

    @pytest.mark.requirement("FR-016")
    def test_emit_accepts_custom_namespace(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test emit_lineage_event accepts custom job_namespace."""
        run_id = dagster_plugin.emit_lineage_event(RunState.START, "job", job_namespace="custom-ns")
        assert isinstance(run_id, UUID)
