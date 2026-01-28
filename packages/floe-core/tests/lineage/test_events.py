"""Tests for lineage event builder and conversion utilities.

This module tests the EventBuilder class and to_openlineage_event() function
that simplify creating and converting LineageEvent instances.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from floe_core.lineage import LineageDataset, LineageJob, RunState
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
