"""Tests for lineage event builder and conversion utilities.

This module tests the EventBuilder class and to_openlineage_event() function
that simplify creating and converting LineageEvent instances.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from floe_core.lineage import (
    LineageDataset,
    LineageEvent,
    LineageJob,
    LineageRun,
    RunState,
)
from floe_core.lineage.events import EventBuilder, to_openlineage_event


class TestEventBuilder:
    """Tests for EventBuilder class."""

    def test_default_initialization(self) -> None:
        """EventBuilder initializes with default values."""
        builder = EventBuilder()
        assert builder.producer == "floe"
        assert builder.default_namespace == "default"

    def test_custom_initialization(self) -> None:
        """EventBuilder accepts custom producer and namespace."""
        builder = EventBuilder(producer="floe-dagster", default_namespace="production")
        assert builder.producer == "floe-dagster"
        assert builder.default_namespace == "production"

    @pytest.mark.requirement("REQ-516")
    def test_start_run_minimal(self) -> None:
        """start_run creates START event with minimal arguments."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")

        assert event.event_type == RunState.START
        assert event.job.name == "test_job"
        assert event.job.namespace == "default"  # Uses default_namespace
        assert isinstance(event.run.run_id, UUID)  # Auto-generated
        assert event.inputs == []
        assert event.outputs == []
        assert event.producer == "floe"
        assert isinstance(event.event_time, datetime)

    @pytest.mark.requirement("REQ-516")
    def test_start_run_with_explicit_run_id(self) -> None:
        """start_run uses explicit run_id when provided."""
        builder = EventBuilder()
        run_id = uuid4()
        event = builder.start_run(job_name="test_job", run_id=run_id)

        assert event.run.run_id == run_id

    @pytest.mark.requirement("REQ-518")
    def test_start_run_with_explicit_namespace(self) -> None:
        """start_run uses explicit job_namespace when provided."""
        builder = EventBuilder(default_namespace="default")
        event = builder.start_run(job_name="test_job", job_namespace="production")

        assert event.job.namespace == "production"

    @pytest.mark.requirement("REQ-518")
    def test_start_run_uses_default_namespace(self) -> None:
        """start_run uses default_namespace when job_namespace is None."""
        builder = EventBuilder(default_namespace="staging")
        event = builder.start_run(job_name="test_job")

        assert event.job.namespace == "staging"

    @pytest.mark.requirement("REQ-516")
    def test_start_run_with_datasets(self) -> None:
        """start_run includes input and output datasets."""
        builder = EventBuilder()
        inputs = [LineageDataset(namespace="raw", name="customers")]
        outputs = [LineageDataset(namespace="staging", name="stg_customers")]

        event = builder.start_run(
            job_name="test_job",
            inputs=inputs,
            outputs=outputs,
        )

        assert len(event.inputs) == 1
        assert event.inputs[0].name == "customers"
        assert len(event.outputs) == 1
        assert event.outputs[0].name == "stg_customers"

    def test_start_run_with_facets(self) -> None:
        """start_run includes run and job facets."""
        builder = EventBuilder()
        run_facets = {"parent": {"run_id": "parent-123"}}
        job_facets = {"sql": {"query": "SELECT * FROM table"}}

        event = builder.start_run(
            job_name="test_job",
            run_facets=run_facets,
            job_facets=job_facets,
        )

        assert event.run.facets == run_facets
        assert event.job.facets == job_facets

    @pytest.mark.requirement("REQ-516")
    def test_complete_run_minimal(self) -> None:
        """complete_run creates COMPLETE event with minimal arguments."""
        builder = EventBuilder()
        run_id = uuid4()
        event = builder.complete_run(run_id=run_id, job_name="test_job")

        assert event.event_type == RunState.COMPLETE
        assert event.run.run_id == run_id
        assert event.job.name == "test_job"
        assert event.job.namespace == "default"
        assert event.inputs == []
        assert event.outputs == []
        assert event.producer == "floe"

    @pytest.mark.requirement("REQ-516")
    def test_complete_run_preserves_run_id(self) -> None:
        """complete_run preserves run_id from START event."""
        builder = EventBuilder()
        start_event = builder.start_run(job_name="test_job")
        complete_event = builder.complete_run(
            run_id=start_event.run.run_id,
            job_name="test_job",
        )

        assert complete_event.run.run_id == start_event.run.run_id

    def test_complete_run_with_datasets(self) -> None:
        """complete_run includes input and output datasets."""
        builder = EventBuilder()
        run_id = uuid4()
        inputs = [LineageDataset(namespace="raw", name="customers")]
        outputs = [LineageDataset(namespace="staging", name="stg_customers")]

        event = builder.complete_run(
            run_id=run_id,
            job_name="test_job",
            inputs=inputs,
            outputs=outputs,
        )

        assert len(event.inputs) == 1
        assert len(event.outputs) == 1

    @pytest.mark.requirement("REQ-516")
    def test_fail_run_minimal(self) -> None:
        """fail_run creates FAIL event with minimal arguments."""
        builder = EventBuilder()
        run_id = uuid4()
        event = builder.fail_run(run_id=run_id, job_name="test_job")

        assert event.event_type == RunState.FAIL
        assert event.run.run_id == run_id
        assert event.job.name == "test_job"
        assert event.inputs == []
        assert event.outputs == []
        assert event.producer == "floe"

    @pytest.mark.requirement("REQ-516")
    def test_fail_run_with_error_message(self) -> None:
        """fail_run includes ErrorMessageRunFacet when error_message provided."""
        builder = EventBuilder(producer="floe-test")
        run_id = uuid4()
        event = builder.fail_run(
            run_id=run_id,
            job_name="test_job",
            error_message="Connection timeout",
        )

        assert "errorMessage" in event.run.facets
        error_facet = event.run.facets["errorMessage"]
        assert error_facet["message"] == "Connection timeout"
        assert error_facet["_producer"] == "floe-test"
        assert error_facet["programmingLanguage"] == "python"
        assert "_schemaURL" in error_facet

    def test_fail_run_without_error_message(self) -> None:
        """fail_run does not include ErrorMessageRunFacet when error_message is None."""
        builder = EventBuilder()
        run_id = uuid4()
        event = builder.fail_run(run_id=run_id, job_name="test_job")

        assert "errorMessage" not in event.run.facets

    def test_fail_run_preserves_existing_facets(self) -> None:
        """fail_run preserves existing run_facets when adding error message."""
        builder = EventBuilder()
        run_id = uuid4()
        existing_facets = {"parent": {"run_id": "parent-123"}}

        event = builder.fail_run(
            run_id=run_id,
            job_name="test_job",
            error_message="Test error",
            run_facets=existing_facets,
        )

        assert "parent" in event.run.facets
        assert "errorMessage" in event.run.facets

    def test_producer_field_set_correctly(self) -> None:
        """All event types use the builder's producer field."""
        builder = EventBuilder(producer="custom-producer")
        run_id = uuid4()

        start = builder.start_run(job_name="job")
        complete = builder.complete_run(run_id=run_id, job_name="job")
        fail = builder.fail_run(run_id=run_id, job_name="job")

        assert start.producer == "custom-producer"
        assert complete.producer == "custom-producer"
        assert fail.producer == "custom-producer"


class TestToOpenLineageEvent:
    """Tests for to_openlineage_event() conversion function."""

    @pytest.mark.requirement("REQ-516")
    def test_converts_start_event(self) -> None:
        """to_openlineage_event converts START event to wire format."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        assert wire_format["eventType"] == "START"
        assert isinstance(wire_format["eventTime"], str)
        assert wire_format["eventTime"].endswith("Z")
        assert "run" in wire_format
        assert "job" in wire_format
        assert "inputs" in wire_format
        assert "outputs" in wire_format
        assert wire_format["producer"] == "floe"

    def test_run_structure(self) -> None:
        """to_openlineage_event creates correct run structure."""
        builder = EventBuilder()
        run_id = uuid4()
        run_facets = {"parent": {"run_id": "parent-123"}}
        event = builder.start_run(job_name="test_job", run_id=run_id, run_facets=run_facets)
        wire_format = to_openlineage_event(event)

        assert wire_format["run"]["runId"] == str(run_id)
        assert wire_format["run"]["facets"] == run_facets

    @pytest.mark.requirement("REQ-518")
    def test_job_structure(self) -> None:
        """to_openlineage_event creates correct job structure."""
        builder = EventBuilder()
        job_facets = {"sql": {"query": "SELECT 1"}}
        event = builder.start_run(
            job_name="test_job",
            job_namespace="production",
            job_facets=job_facets,
        )
        wire_format = to_openlineage_event(event)

        assert wire_format["job"]["namespace"] == "production"
        assert wire_format["job"]["name"] == "test_job"
        assert wire_format["job"]["facets"] == job_facets

    def test_inputs_structure(self) -> None:
        """to_openlineage_event creates correct inputs structure."""
        builder = EventBuilder()
        inputs = [
            LineageDataset(
                namespace="raw",
                name="customers",
                facets={"schema": {"fields": []}},
            ),
            LineageDataset(namespace="raw", name="orders"),
        ]
        event = builder.start_run(job_name="test_job", inputs=inputs)
        wire_format = to_openlineage_event(event)

        assert len(wire_format["inputs"]) == 2
        assert wire_format["inputs"][0]["namespace"] == "raw"
        assert wire_format["inputs"][0]["name"] == "customers"
        assert "schema" in wire_format["inputs"][0]["facets"]
        assert wire_format["inputs"][1]["name"] == "orders"

    def test_outputs_structure(self) -> None:
        """to_openlineage_event creates correct outputs structure."""
        builder = EventBuilder()
        outputs = [
            LineageDataset(
                namespace="staging",
                name="stg_customers",
                facets={"dataQuality": {"score": 0.95}},
            ),
        ]
        event = builder.start_run(job_name="test_job", outputs=outputs)
        wire_format = to_openlineage_event(event)

        assert len(wire_format["outputs"]) == 1
        assert wire_format["outputs"][0]["namespace"] == "staging"
        assert wire_format["outputs"][0]["name"] == "stg_customers"
        assert wire_format["outputs"][0]["facets"]["dataQuality"]["score"] == 0.95

    def test_empty_datasets(self) -> None:
        """to_openlineage_event handles empty inputs and outputs."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        assert wire_format["inputs"] == []
        assert wire_format["outputs"] == []

    def test_event_time_format(self) -> None:
        """to_openlineage_event formats event_time as ISO 8601 with Z suffix."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        # Should be ISO 8601 format with Z suffix
        event_time = wire_format["eventTime"]
        assert event_time.endswith("Z")
        # Should be parseable as datetime
        datetime.fromisoformat(event_time.rstrip("Z"))

    @pytest.mark.requirement("REQ-516")
    def test_complete_event_conversion(self) -> None:
        """to_openlineage_event converts COMPLETE event correctly."""
        builder = EventBuilder()
        run_id = uuid4()
        event = builder.complete_run(run_id=run_id, job_name="test_job")
        wire_format = to_openlineage_event(event)

        assert wire_format["eventType"] == "COMPLETE"
        assert wire_format["run"]["runId"] == str(run_id)

    @pytest.mark.requirement("REQ-516")
    def test_fail_event_conversion(self) -> None:
        """to_openlineage_event converts FAIL event with error facet."""
        builder = EventBuilder()
        run_id = uuid4()
        event = builder.fail_run(
            run_id=run_id,
            job_name="test_job",
            error_message="Test error",
        )
        wire_format = to_openlineage_event(event)

        assert wire_format["eventType"] == "FAIL"
        assert "errorMessage" in wire_format["run"]["facets"]
        assert wire_format["run"]["facets"]["errorMessage"]["message"] == "Test error"

    def test_producer_field(self) -> None:
        """to_openlineage_event includes producer field."""
        builder = EventBuilder(producer="floe-custom")
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        assert wire_format["producer"] == "floe-custom"

    def test_roundtrip_compatibility(self) -> None:
        """Wire format can be used to reconstruct event data."""
        builder = EventBuilder()
        inputs = [LineageDataset(namespace="raw", name="customers")]
        outputs = [LineageDataset(namespace="staging", name="stg_customers")]
        event = builder.start_run(
            job_name="test_job",
            job_namespace="production",
            inputs=inputs,
            outputs=outputs,
        )
        wire_format = to_openlineage_event(event)

        # Verify all essential data is preserved
        assert wire_format["eventType"] == event.event_type.value
        assert wire_format["job"]["name"] == event.job.name
        assert wire_format["job"]["namespace"] == event.job.namespace
        assert wire_format["run"]["runId"] == str(event.run.run_id)
        assert len(wire_format["inputs"]) == len(event.inputs)
        assert len(wire_format["outputs"]) == len(event.outputs)


class TestLineageEventEdgeCases:
    """Tests for edge cases in LineageEvent creation and validation."""

    @pytest.mark.requirement("REQ-516")
    def test_lineage_event_minimal_creation(self) -> None:
        """LineageEvent can be created with only required fields."""
        job = LineageJob(namespace="test", name="test_job")
        event = LineageEvent(event_type=RunState.START, job=job)

        assert event.event_type == RunState.START
        assert event.job.name == "test_job"
        assert event.job.namespace == "test"
        assert isinstance(event.run.run_id, UUID)
        assert event.inputs == []
        assert event.outputs == []
        assert event.producer == "floe"
        assert isinstance(event.event_time, datetime)

    @pytest.mark.requirement("REQ-516")
    def test_lineage_event_all_fields(self) -> None:
        """LineageEvent can be created with all optional fields."""
        run_id = uuid4()
        event_time = datetime.now(timezone.utc)
        inputs = [LineageDataset(namespace="raw", name="input1")]
        outputs = [LineageDataset(namespace="staging", name="output1")]
        run_facets = {"parent": {"run_id": "parent-123"}}
        job_facets = {"sql": {"query": "SELECT 1"}}

        event = LineageEvent(
            event_type=RunState.COMPLETE,
            event_time=event_time,
            run=LineageRun(run_id=run_id, facets=run_facets),
            job=LineageJob(namespace="prod", name="full_job", facets=job_facets),
            inputs=inputs,
            outputs=outputs,
            producer="custom-producer",
        )

        assert event.event_type == RunState.COMPLETE
        assert event.event_time == event_time
        assert event.run.run_id == run_id
        assert event.run.facets == run_facets
        assert event.job.namespace == "prod"
        assert event.job.name == "full_job"
        assert event.job.facets == job_facets
        assert len(event.inputs) == 1
        assert len(event.outputs) == 1
        assert event.producer == "custom-producer"

    def test_lineage_event_immutability(self) -> None:
        """LineageEvent is frozen and cannot be modified."""
        job = LineageJob(namespace="test", name="test_job")
        event = LineageEvent(event_type=RunState.START, job=job)

        with pytest.raises(ValidationError):
            event.producer = "modified"  # type: ignore

    def test_lineage_dataset_minimal_creation(self) -> None:
        """LineageDataset can be created with only required fields."""
        dataset = LineageDataset(namespace="raw", name="customers")

        assert dataset.namespace == "raw"
        assert dataset.name == "customers"
        assert dataset.facets == {}

    def test_lineage_dataset_with_facets(self) -> None:
        """LineageDataset can include facets."""
        facets = {"schema": {"fields": [{"name": "id", "type": "int"}]}}
        dataset = LineageDataset(namespace="raw", name="customers", facets=facets)

        assert dataset.facets == facets
        assert dataset.facets["schema"]["fields"][0]["name"] == "id"

    def test_lineage_dataset_immutability(self) -> None:
        """LineageDataset is frozen and cannot be modified."""
        dataset = LineageDataset(namespace="raw", name="customers")

        with pytest.raises(ValidationError):
            dataset.name = "modified"  # type: ignore

    def test_lineage_dataset_empty_namespace_invalid(self) -> None:
        """LineageDataset requires non-empty namespace."""
        with pytest.raises(ValidationError):
            LineageDataset(namespace="", name="customers")

    def test_lineage_dataset_empty_name_invalid(self) -> None:
        """LineageDataset requires non-empty name."""
        with pytest.raises(ValidationError):
            LineageDataset(namespace="raw", name="")

    def test_lineage_job_minimal_creation(self) -> None:
        """LineageJob can be created with only required fields."""
        job = LineageJob(namespace="floe", name="test_job")

        assert job.namespace == "floe"
        assert job.name == "test_job"
        assert job.facets == {}

    def test_lineage_job_with_facets(self) -> None:
        """LineageJob can include facets."""
        facets = {"sql": {"query": "SELECT * FROM table"}}
        job = LineageJob(namespace="floe", name="test_job", facets=facets)

        assert job.facets == facets

    def test_lineage_job_empty_namespace_invalid(self) -> None:
        """LineageJob requires non-empty namespace."""
        with pytest.raises(ValidationError):
            LineageJob(namespace="", name="test_job")

    def test_lineage_job_empty_name_invalid(self) -> None:
        """LineageJob requires non-empty name."""
        with pytest.raises(ValidationError):
            LineageJob(namespace="floe", name="")

    def test_lineage_run_auto_generates_run_id(self) -> None:
        """LineageRun auto-generates run_id if not provided."""
        run1 = LineageRun()
        run2 = LineageRun()

        assert isinstance(run1.run_id, UUID)
        assert isinstance(run2.run_id, UUID)
        assert run1.run_id != run2.run_id

    def test_lineage_run_with_explicit_run_id(self) -> None:
        """LineageRun accepts explicit run_id."""
        run_id = uuid4()
        run = LineageRun(run_id=run_id)

        assert run.run_id == run_id

    def test_lineage_run_with_facets(self) -> None:
        """LineageRun can include facets."""
        facets = {"parent": {"run_id": "parent-123"}}
        run = LineageRun(facets=facets)

        assert run.facets == facets

    @pytest.mark.requirement("REQ-516")
    def test_event_timestamp_is_utc(self) -> None:
        """Event timestamp is always in UTC timezone."""
        event = LineageEvent(
            event_type=RunState.START,
            job=LineageJob(namespace="test", name="test_job"),
        )

        assert event.event_time.tzinfo is not None
        assert event.event_time.tzinfo == timezone.utc

    def test_event_timestamp_custom(self) -> None:
        """Event timestamp can be set explicitly."""
        custom_time = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        event = LineageEvent(
            event_type=RunState.START,
            event_time=custom_time,
            job=LineageJob(namespace="test", name="test_job"),
        )

        assert event.event_time == custom_time

    @pytest.mark.requirement("REQ-516")
    @pytest.mark.parametrize(
        "state",
        [
            RunState.START,
            RunState.RUNNING,
            RunState.COMPLETE,
            RunState.ABORT,
            RunState.FAIL,
            RunState.OTHER,
        ],
    )
    def test_all_run_states_valid(self, state: RunState) -> None:
        """All RunState enum values are valid for events."""
        event = LineageEvent(
            event_type=state,
            job=LineageJob(namespace="test", name="test_job"),
        )

        assert event.event_type == state
        assert event.event_type.value in [
            "START",
            "RUNNING",
            "COMPLETE",
            "ABORT",
            "FAIL",
            "OTHER",
        ]

    def test_event_with_multiple_inputs_outputs(self) -> None:
        """Event can have multiple input and output datasets."""
        inputs = [
            LineageDataset(namespace="raw", name="customers"),
            LineageDataset(namespace="raw", name="orders"),
            LineageDataset(namespace="raw", name="products"),
        ]
        outputs = [
            LineageDataset(namespace="staging", name="stg_customers"),
            LineageDataset(namespace="staging", name="stg_orders"),
        ]

        event = LineageEvent(
            event_type=RunState.COMPLETE,
            job=LineageJob(namespace="test", name="test_job"),
            inputs=inputs,
            outputs=outputs,
        )

        assert len(event.inputs) == 3
        assert len(event.outputs) == 2
        assert event.inputs[0].name == "customers"
        assert event.outputs[1].name == "stg_orders"

    def test_event_with_complex_facets(self) -> None:
        """Event facets can contain complex nested structures."""
        run_facets = {
            "parent": {"run_id": "parent-123"},
            "metadata": {
                "nested": {
                    "deep": {
                        "value": "test",
                        "list": [1, 2, 3],
                    }
                }
            },
        }
        job_facets = {
            "sql": {"query": "SELECT * FROM table WHERE id > 100"},
            "documentation": {"description": "Test job"},
        }

        event = LineageEvent(
            event_type=RunState.START,
            job=LineageJob(namespace="test", name="test_job", facets=job_facets),
            run=LineageRun(facets=run_facets),
        )

        assert event.run.facets["metadata"]["nested"]["deep"]["value"] == "test"
        assert event.job.facets["sql"]["query"] == "SELECT * FROM table WHERE id > 100"

    def test_event_producer_validation(self) -> None:
        """Event producer must be non-empty string."""
        with pytest.raises(ValidationError):
            LineageEvent(
                event_type=RunState.START,
                job=LineageJob(namespace="test", name="test_job"),
                producer="",
            )

    def test_event_extra_fields_forbidden(self) -> None:
        """LineageEvent forbids extra fields (strict validation)."""
        with pytest.raises(ValidationError):
            LineageEvent(
                event_type=RunState.START,
                job=LineageJob(namespace="test", name="test_job"),
                extra_field="should_fail",  # type: ignore
            )


class TestEventSerialization:
    """Tests for event serialization to dict and JSON formats."""

    @pytest.mark.requirement("REQ-516")
    def test_event_to_dict_complete(self) -> None:
        """Event can be serialized to dictionary."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        assert isinstance(wire_format, dict)
        assert "eventType" in wire_format
        assert "eventTime" in wire_format
        assert "run" in wire_format
        assert "job" in wire_format
        assert "inputs" in wire_format
        assert "outputs" in wire_format
        assert "producer" in wire_format
        assert "schemaURL" in wire_format

    def test_event_to_dict_json_serializable(self) -> None:
        """Event dict is JSON serializable."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        # Should not raise
        json_str = json.dumps(wire_format)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_event_dict_roundtrip_json(self) -> None:
        """Event can be serialized to JSON and back."""
        builder = EventBuilder()
        inputs = [LineageDataset(namespace="raw", name="customers")]
        outputs = [LineageDataset(namespace="staging", name="stg_customers")]
        event = builder.start_run(
            job_name="test_job",
            job_namespace="production",
            inputs=inputs,
            outputs=outputs,
        )
        wire_format = to_openlineage_event(event)

        # Serialize to JSON and back
        json_str = json.dumps(wire_format)
        restored = json.loads(json_str)

        # Verify data integrity
        assert restored["eventType"] == "START"
        assert restored["job"]["name"] == "test_job"
        assert restored["job"]["namespace"] == "production"
        assert len(restored["inputs"]) == 1
        assert len(restored["outputs"]) == 1
        assert restored["inputs"][0]["name"] == "customers"
        assert restored["outputs"][0]["name"] == "stg_customers"

    def test_event_dict_with_facets_serializable(self) -> None:
        """Event with complex facets is JSON serializable."""
        builder = EventBuilder()
        run_facets = {"parent": {"run_id": "parent-123"}}
        job_facets = {"sql": {"query": "SELECT * FROM table"}}

        event = builder.start_run(
            job_name="test_job",
            run_facets=run_facets,
            job_facets=job_facets,
        )
        wire_format = to_openlineage_event(event)

        # Should not raise
        json_str = json.dumps(wire_format)
        restored = json.loads(json_str)

        assert restored["run"]["facets"]["parent"]["run_id"] == "parent-123"
        assert restored["job"]["facets"]["sql"]["query"] == "SELECT * FROM table"

    def test_event_time_iso8601_format(self) -> None:
        """Event time is formatted as ISO 8601 with Z suffix."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        event_time = wire_format["eventTime"]
        assert isinstance(event_time, str)
        assert event_time.endswith("Z")
        # Should be parseable
        datetime.fromisoformat(event_time.rstrip("Z"))

    def test_run_id_string_format(self) -> None:
        """Run ID is formatted as string UUID."""
        builder = EventBuilder()
        run_id = uuid4()
        event = builder.start_run(job_name="test_job", run_id=run_id)
        wire_format = to_openlineage_event(event)

        assert wire_format["run"]["runId"] == str(run_id)
        assert isinstance(wire_format["run"]["runId"], str)

    def test_dataset_facets_preserved_in_dict(self) -> None:
        """Dataset facets are preserved in serialized dict."""
        builder = EventBuilder()
        dataset_facets = {"schema": {"fields": [{"name": "id", "type": "int"}]}}
        inputs = [LineageDataset(namespace="raw", name="customers", facets=dataset_facets)]

        event = builder.start_run(job_name="test_job", inputs=inputs)
        wire_format = to_openlineage_event(event)

        assert wire_format["inputs"][0]["facets"] == dataset_facets
        assert wire_format["inputs"][0]["facets"]["schema"]["fields"][0]["name"] == "id"

    def test_empty_facets_in_dict(self) -> None:
        """Empty facets are preserved as empty dicts in serialized dict."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        assert wire_format["run"]["facets"] == {}
        assert wire_format["job"]["facets"] == {}

    @pytest.mark.requirement("REQ-516")
    def test_schema_url_present(self) -> None:
        """Serialized event includes OpenLineage schema URL."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job")
        wire_format = to_openlineage_event(event)

        assert "schemaURL" in wire_format
        assert wire_format["schemaURL"] == "https://openlineage.io/spec/2-0-2/OpenLineage.json"


class TestEventBuilderEdgeCases:
    """Tests for edge cases in EventBuilder methods."""

    def test_builder_with_empty_producer_creates_event_with_empty_producer(
        self,
    ) -> None:
        """EventBuilder accepts empty producer string (validation happens at event creation)."""
        builder = EventBuilder(producer="")
        assert builder.producer == ""

    def test_builder_with_empty_namespace_creates_event_with_empty_namespace(
        self,
    ) -> None:
        """EventBuilder accepts empty default_namespace (validation happens at event creation)."""
        builder = EventBuilder(default_namespace="")
        assert builder.default_namespace == ""

    def test_start_run_with_empty_job_name_invalid(self) -> None:
        """start_run rejects empty job_name."""
        builder = EventBuilder()
        with pytest.raises(ValidationError):
            builder.start_run(job_name="")

    def test_start_run_with_empty_job_namespace_invalid(self) -> None:
        """start_run rejects empty job_namespace."""
        builder = EventBuilder()
        with pytest.raises(ValidationError):
            builder.start_run(job_name="test_job", job_namespace="")

    def test_complete_run_with_empty_job_name_invalid(self) -> None:
        """complete_run rejects empty job_name."""
        builder = EventBuilder()
        with pytest.raises(ValidationError):
            builder.complete_run(run_id=uuid4(), job_name="")

    def test_fail_run_with_empty_job_name_invalid(self) -> None:
        """fail_run rejects empty job_name."""
        builder = EventBuilder()
        with pytest.raises(ValidationError):
            builder.fail_run(run_id=uuid4(), job_name="")

    def test_start_run_with_empty_inputs_list(self) -> None:
        """start_run handles empty inputs list."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job", inputs=[])

        assert event.inputs == []

    def test_start_run_with_empty_outputs_list(self) -> None:
        """start_run handles empty outputs list."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job", outputs=[])

        assert event.outputs == []

    def test_start_run_with_none_inputs_defaults_to_empty(self) -> None:
        """start_run with None inputs defaults to empty list."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job", inputs=None)

        assert event.inputs == []

    def test_start_run_with_none_outputs_defaults_to_empty(self) -> None:
        """start_run with None outputs defaults to empty list."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job", outputs=None)

        assert event.outputs == []

    def test_start_run_with_none_facets_defaults_to_empty(self) -> None:
        """start_run with None facets defaults to empty dict."""
        builder = EventBuilder()
        event = builder.start_run(job_name="test_job", run_facets=None, job_facets=None)

        assert event.run.facets == {}
        assert event.job.facets == {}

    def test_fail_run_with_none_error_message(self) -> None:
        """fail_run with None error_message does not add error facet."""
        builder = EventBuilder()
        event = builder.fail_run(run_id=uuid4(), job_name="test_job", error_message=None)

        assert "errorMessage" not in event.run.facets

    def test_fail_run_with_empty_error_message(self) -> None:
        """fail_run with empty error_message still adds error facet."""
        builder = EventBuilder()
        event = builder.fail_run(run_id=uuid4(), job_name="test_job", error_message="")

        assert "errorMessage" in event.run.facets
        assert event.run.facets["errorMessage"]["message"] == ""

    def test_fail_run_error_facet_structure(self) -> None:
        """fail_run error facet has correct structure."""
        builder = EventBuilder(producer="test-producer")
        event = builder.fail_run(
            run_id=uuid4(),
            job_name="test_job",
            error_message="Test error message",
        )

        error_facet = event.run.facets["errorMessage"]
        assert error_facet["message"] == "Test error message"
        assert error_facet["_producer"] == "test-producer"
        assert error_facet["programmingLanguage"] == "python"
        assert "_schemaURL" in error_facet
        assert "ErrorMessageRunFacet" in error_facet["_schemaURL"]

    def test_complete_run_with_none_inputs_defaults_to_empty(self) -> None:
        """complete_run with None inputs defaults to empty list."""
        builder = EventBuilder()
        event = builder.complete_run(run_id=uuid4(), job_name="test_job", inputs=None)

        assert event.inputs == []

    def test_complete_run_with_none_outputs_defaults_to_empty(self) -> None:
        """complete_run with None outputs defaults to empty list."""
        builder = EventBuilder()
        event = builder.complete_run(run_id=uuid4(), job_name="test_job", outputs=None)

        assert event.outputs == []

    @pytest.mark.parametrize(
        "producer,namespace",
        [
            ("floe", "default"),
            ("floe-dagster", "production"),
            ("custom-producer", "custom-namespace"),
            ("a", "b"),  # Single character names
        ],
    )
    def test_builder_initialization_parametrized(self, producer: str, namespace: str) -> None:
        """EventBuilder initializes with various producer and namespace values."""
        builder = EventBuilder(producer=producer, default_namespace=namespace)

        assert builder.producer == producer
        assert builder.default_namespace == namespace

    @pytest.mark.parametrize(
        "job_name,job_namespace",
        [
            ("simple_job", "default"),
            ("dbt_run_customers", "production"),
            ("job-with-dashes", "namespace-with-dashes"),
            ("job_with_underscores", "namespace_with_underscores"),
        ],
    )
    def test_start_run_with_various_names(self, job_name: str, job_namespace: str) -> None:
        """start_run handles various job name and namespace formats."""
        builder = EventBuilder()
        event = builder.start_run(job_name=job_name, job_namespace=job_namespace)

        assert event.job.name == job_name
        assert event.job.namespace == job_namespace
