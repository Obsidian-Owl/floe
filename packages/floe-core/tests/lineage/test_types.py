"""Tests for core lineage types and protocols.

This module tests the Pydantic models and protocols that form the foundation
of floe's OpenLineage integration.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from floe_core.lineage import (
    LineageDataset,
    LineageEvent,
    LineageExtractor,
    LineageJob,
    LineageRun,
    LineageTransport,
    RunState,
)


class TestRunState:
    """Tests for RunState enum."""

    @pytest.mark.requirement("REQ-516")
    def test_has_all_openlineage_values(self) -> None:
        """RunState enum has all 6 OpenLineage spec values."""
        expected = {"START", "RUNNING", "COMPLETE", "ABORT", "FAIL", "OTHER"}
        actual = {s.value for s in RunState}
        assert actual == expected

    def test_is_string_enum(self) -> None:
        """RunState values are strings."""
        assert RunState.START == "START"
        assert isinstance(RunState.START, str)


class TestLineageDataset:
    """Tests for LineageDataset model."""

    def test_create_minimal(self) -> None:
        """Create dataset with minimal required fields."""
        ds = LineageDataset(namespace="prod", name="db.schema.table")
        assert ds.namespace == "prod"
        assert ds.name == "db.schema.table"
        assert ds.facets == {}

    def test_create_with_facets(self) -> None:
        """Create dataset with facets."""
        ds = LineageDataset(
            namespace="prod",
            name="db.schema.table",
            facets={"schema": {"fields": [{"name": "id", "type": "INTEGER"}]}},
        )
        assert "schema" in ds.facets

    def test_frozen_immutability(self) -> None:
        """Dataset is immutable after creation."""
        ds = LineageDataset(namespace="prod", name="table")
        with pytest.raises(ValidationError):
            ds.namespace = "other"  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        """Dataset can be serialized and deserialized."""
        ds = LineageDataset(namespace="prod", name="table", facets={"k": "v"})
        data = ds.model_dump(mode="json")
        ds2 = LineageDataset.model_validate(data)
        assert ds == ds2

    def test_rejects_empty_namespace(self) -> None:
        """Dataset rejects empty namespace."""
        with pytest.raises(ValidationError):
            LineageDataset(namespace="", name="table")

    def test_rejects_extra_fields(self) -> None:
        """Dataset rejects extra fields."""
        with pytest.raises(ValidationError):
            LineageDataset(namespace="ns", name="t", unknown="x")  # type: ignore[call-arg]


class TestLineageRun:
    """Tests for LineageRun model."""

    def test_auto_generates_run_id(self) -> None:
        """Run auto-generates UUID if not provided."""
        run = LineageRun()
        assert isinstance(run.run_id, UUID)

    def test_explicit_run_id(self) -> None:
        """Run accepts explicit run_id."""
        rid = uuid4()
        run = LineageRun(run_id=rid)
        assert run.run_id == rid

    def test_serialization_roundtrip(self) -> None:
        """Run can be serialized and deserialized."""
        run = LineageRun(facets={"parent": {"run_id": "abc"}})
        data = run.model_dump(mode="json")
        run2 = LineageRun.model_validate(data)
        assert run.run_id == run2.run_id


class TestLineageJob:
    """Tests for LineageJob model."""

    def test_create(self) -> None:
        """Create job with required fields."""
        job = LineageJob(namespace="floe", name="dbt_run_customers")
        assert job.namespace == "floe"
        assert job.name == "dbt_run_customers"

    def test_rejects_empty_name(self) -> None:
        """Job rejects empty name."""
        with pytest.raises(ValidationError):
            LineageJob(namespace="ns", name="")


class TestLineageEvent:
    """Tests for LineageEvent model."""

    @pytest.mark.requirement("REQ-516")
    def test_create_start_event(self) -> None:
        """Create START event with minimal fields."""
        event = LineageEvent(
            event_type=RunState.START,
            job=LineageJob(namespace="floe", name="test_job"),
        )
        assert event.event_type == RunState.START
        assert isinstance(event.event_time, datetime)
        assert isinstance(event.run.run_id, UUID)
        assert event.producer == "floe"

    def test_full_event_roundtrip(self) -> None:
        """Event with all fields can be serialized and deserialized."""
        event = LineageEvent(
            event_type=RunState.COMPLETE,
            run=LineageRun(),
            job=LineageJob(namespace="floe", name="job1"),
            inputs=[LineageDataset(namespace="ns", name="in1")],
            outputs=[LineageDataset(namespace="ns", name="out1")],
            producer="floe-test",
        )
        data = event.model_dump(mode="json")
        event2 = LineageEvent.model_validate(data)
        assert event2.event_type == RunState.COMPLETE
        assert len(event2.inputs) == 1
        assert len(event2.outputs) == 1

    def test_frozen(self) -> None:
        """Event is immutable after creation."""
        event = LineageEvent(
            event_type=RunState.START,
            job=LineageJob(namespace="ns", name="j"),
        )
        with pytest.raises(ValidationError):
            event.event_type = RunState.FAIL  # type: ignore[misc]


class TestProtocols:
    """Tests for protocol runtime checking."""

    def test_transport_is_runtime_checkable(self) -> None:
        """LineageTransport protocol is runtime checkable."""
        from floe_core.lineage.transport import NoOpLineageTransport

        transport = NoOpLineageTransport()
        assert isinstance(transport, LineageTransport)

    def test_extractor_is_runtime_checkable(self) -> None:
        """LineageExtractor protocol is runtime checkable."""
        from floe_core.lineage.extractors.dbt import DbtLineageExtractor

        extractor = DbtLineageExtractor(manifest={}, default_namespace="test")
        assert isinstance(extractor, LineageExtractor)
