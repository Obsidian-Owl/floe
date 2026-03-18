"""Unit tests for extract_dbt_model_lineage() function.

Tests verify per-model OpenLineage event extraction from dbt artifacts.
The function reads manifest.json + run_results.json from a project directory,
uses DbtLineageExtractor for inputs/outputs, attaches ParentRunFacet,
ColumnLineageFacet, and timing from run_results, and returns a list of
LineageEvent pairs (START, COMPLETE/FAIL) per model.

Requirements:
    AC-4: Per-model lineage extracted from dbt artifacts
    AC-5: Per-model events carry ParentRunFacet
    AC-6: Per-model events use timing from run_results.json
    AC-7: Per-model events include inputs/outputs from DbtLineageExtractor
    AC-9: Graceful degradation when artifacts missing
    AC-12: Column lineage facets when available
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from floe_core.lineage.types import LineageEvent, RunState

from floe_orchestrator_dagster.lineage_extraction import extract_dbt_model_lineage

# ---------------------------------------------------------------------------
# Constants for repeated string literals
# ---------------------------------------------------------------------------
MODEL_UID_STG_CUSTOMERS = "model.customer_360.stg_customers"
MODEL_UID_DIM_CUSTOMERS = "model.customer_360.dim_customers"
SOURCE_UID_RAW_CUSTOMERS = "source.customer_360.raw.customers"
DEFAULT_NAMESPACE = "test-namespace"
PARENT_JOB_NAME = "dagster_dbt_asset"
COMPILE_STEP_NAME = "compile"
EXECUTE_STEP_NAME = "execute"


# ---------------------------------------------------------------------------
# Helpers for building dbt artifact files
# ---------------------------------------------------------------------------


def _write_manifest(
    target_dir: Path,
    nodes: dict[str, Any] | None = None,
    parent_map: dict[str, list[str]] | None = None,
    sources: dict[str, Any] | None = None,
) -> Path:
    """Write a manifest.json to target_dir and return its path."""
    manifest: dict[str, Any] = {
        "nodes": nodes or {},
        "parent_map": parent_map or {},
        "sources": sources or {},
    }
    path = target_dir / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def _write_run_results(
    target_dir: Path,
    results: list[dict[str, Any]],
) -> Path:
    """Write a run_results.json to target_dir and return its path."""
    run_results: dict[str, Any] = {"results": results}
    path = target_dir / "run_results.json"
    path.write_text(json.dumps(run_results))
    return path


def _make_timing(
    started_at: str = "2026-03-18T10:00:00Z",
    completed_at: str = "2026-03-18T10:00:05Z",
    name: str = EXECUTE_STEP_NAME,
) -> dict[str, str]:
    """Build a single timing entry for run_results."""
    return {
        "name": name,
        "started_at": started_at,
        "completed_at": completed_at,
    }


def _make_result(
    unique_id: str,
    status: str = "success",
    timing: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a single result entry for run_results."""
    if timing is None:
        timing = [
            _make_timing(
                name=COMPILE_STEP_NAME,
                started_at="2026-03-18T10:00:00Z",
                completed_at="2026-03-18T10:00:01Z",
            ),
            _make_timing(
                name=EXECUTE_STEP_NAME,
                started_at="2026-03-18T10:00:01Z",
                completed_at="2026-03-18T10:00:05Z",
            ),
        ]
    return {
        "unique_id": unique_id,
        "status": status,
        "timing": timing,
    }


def _make_node(
    database: str = "analytics",
    schema: str = "public",
    name: str = "stg_customers",
    columns: dict[str, dict[str, Any]] | None = None,
    depends_on_nodes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a dbt manifest node."""
    node: dict[str, Any] = {
        "database": database,
        "schema": schema,
        "name": name,
    }
    if columns is not None:
        node["columns"] = columns
    if depends_on_nodes is not None:
        node["depends_on"] = {"nodes": depends_on_nodes}
    return node


def _make_source(
    database: str = "raw_db",
    schema: str = "public",
    name: str = "customers",
) -> dict[str, Any]:
    """Build a dbt manifest source."""
    return {
        "database": database,
        "schema": schema,
        "name": name,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a project directory with a target/ subdirectory."""
    target = tmp_path / "target"
    target.mkdir()
    return tmp_path


@pytest.fixture
def parent_run_id() -> UUID:
    """Fixed parent run ID for deterministic assertions."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def single_model_project(project_dir: Path) -> Path:
    """Project with one successful model that has a source dependency."""
    target = project_dir / "target"
    _write_manifest(
        target,
        nodes={
            MODEL_UID_STG_CUSTOMERS: _make_node(
                columns={"id": {"name": "id", "data_type": "INTEGER"}},
                depends_on_nodes=[SOURCE_UID_RAW_CUSTOMERS],
            ),
        },
        parent_map={
            MODEL_UID_STG_CUSTOMERS: [SOURCE_UID_RAW_CUSTOMERS],
        },
        sources={
            SOURCE_UID_RAW_CUSTOMERS: _make_source(),
        },
    )
    _write_run_results(
        target,
        results=[_make_result(MODEL_UID_STG_CUSTOMERS)],
    )
    return project_dir


@pytest.fixture
def multi_model_project(project_dir: Path) -> Path:
    """Project with two models: stg_customers -> dim_customers."""
    target = project_dir / "target"
    _write_manifest(
        target,
        nodes={
            MODEL_UID_STG_CUSTOMERS: _make_node(
                columns={"id": {"name": "id", "data_type": "INTEGER"}},
                depends_on_nodes=[SOURCE_UID_RAW_CUSTOMERS],
            ),
            MODEL_UID_DIM_CUSTOMERS: _make_node(
                name="dim_customers",
                columns={
                    "id": {"name": "id", "data_type": "INTEGER"},
                    "full_name": {"name": "full_name", "data_type": "VARCHAR"},
                },
                depends_on_nodes=[MODEL_UID_STG_CUSTOMERS],
            ),
        },
        parent_map={
            MODEL_UID_STG_CUSTOMERS: [SOURCE_UID_RAW_CUSTOMERS],
            MODEL_UID_DIM_CUSTOMERS: [MODEL_UID_STG_CUSTOMERS],
        },
        sources={
            SOURCE_UID_RAW_CUSTOMERS: _make_source(),
        },
    )
    _write_run_results(
        target,
        results=[
            _make_result(MODEL_UID_STG_CUSTOMERS),
            _make_result(
                MODEL_UID_DIM_CUSTOMERS,
                timing=[
                    _make_timing(
                        name=COMPILE_STEP_NAME,
                        started_at="2026-03-18T10:00:05Z",
                        completed_at="2026-03-18T10:00:06Z",
                    ),
                    _make_timing(
                        name=EXECUTE_STEP_NAME,
                        started_at="2026-03-18T10:00:06Z",
                        completed_at="2026-03-18T10:00:12Z",
                    ),
                ],
            ),
        ],
    )
    return project_dir


# ===========================================================================
# AC-4: Per-model lineage extracted from dbt artifacts
# ===========================================================================


class TestAC4PerModelLineageExtraction:
    """Test that extract_dbt_model_lineage reads artifacts and returns events."""

    @pytest.mark.requirement("AC-4")
    def test_returns_list_of_lineage_events(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Function returns a list of LineageEvent instances, not dicts."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert isinstance(events, list)
        for event in events:
            assert isinstance(event, LineageEvent)

    @pytest.mark.requirement("AC-4")
    def test_single_model_produces_start_and_complete_pair(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """One successful model should produce exactly one START and one COMPLETE event."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert len(events) == 2
        event_types = [e.event_type for e in events]
        assert event_types[0] == RunState.START
        assert event_types[1] == RunState.COMPLETE

    @pytest.mark.requirement("AC-4")
    def test_start_and_complete_share_same_run_id(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """START and COMPLETE events for the same model must share one run_id."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert len(events) == 2
        assert events[0].run.run_id == events[1].run.run_id
        assert isinstance(events[0].run.run_id, UUID)

    @pytest.mark.requirement("AC-4")
    def test_multi_model_produces_events_per_model(
        self,
        multi_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Two models should produce 4 events (2 per model)."""
        events = extract_dbt_model_lineage(
            project_dir=multi_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert len(events) == 4

        start_events = [e for e in events if e.event_type == RunState.START]
        complete_events = [e for e in events if e.event_type == RunState.COMPLETE]
        assert len(start_events) == 2
        assert len(complete_events) == 2

    @pytest.mark.requirement("AC-4")
    def test_each_model_has_distinct_run_id(
        self,
        multi_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Each model's event pair must use a different run_id."""
        events = extract_dbt_model_lineage(
            project_dir=multi_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_events = [e for e in events if e.event_type == RunState.START]
        run_ids = {e.run.run_id for e in start_events}
        assert len(run_ids) == 2, "Each model must get a unique run_id"

    @pytest.mark.requirement("AC-4")
    def test_job_name_contains_model_unique_id(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Event job.name must identify the specific dbt model."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        # The job name should reference the model
        for event in events:
            assert "stg_customers" in event.job.name

    @pytest.mark.requirement("AC-4")
    def test_job_namespace_matches_provided_namespace(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Event job.namespace must equal the namespace parameter."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        for event in events:
            assert event.job.namespace == DEFAULT_NAMESPACE

    @pytest.mark.requirement("AC-4")
    def test_failed_model_produces_start_and_fail_pair(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """A model with status 'error' should produce START + FAIL events."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[_make_result(MODEL_UID_STG_CUSTOMERS, status="error")],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert len(events) == 2
        assert events[0].event_type == RunState.START
        assert events[1].event_type == RunState.FAIL

    @pytest.mark.requirement("AC-4")
    def test_mixed_success_and_failure_models(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """Mixed results: one success + one failure = START+COMPLETE + START+FAIL."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={
                MODEL_UID_STG_CUSTOMERS: _make_node(),
                MODEL_UID_DIM_CUSTOMERS: _make_node(name="dim_customers"),
            },
            parent_map={
                MODEL_UID_STG_CUSTOMERS: [],
                MODEL_UID_DIM_CUSTOMERS: [MODEL_UID_STG_CUSTOMERS],
            },
        )
        _write_run_results(
            target,
            results=[
                _make_result(MODEL_UID_STG_CUSTOMERS, status="success"),
                _make_result(MODEL_UID_DIM_CUSTOMERS, status="error"),
            ],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert len(events) == 4

        # Find events per model by checking job name
        stg_events = [e for e in events if "stg_customers" in e.job.name]
        dim_events = [e for e in events if "dim_customers" in e.job.name]

        assert len(stg_events) == 2
        assert stg_events[0].event_type == RunState.START
        assert stg_events[1].event_type == RunState.COMPLETE

        assert len(dim_events) == 2
        assert dim_events[0].event_type == RunState.START
        assert dim_events[1].event_type == RunState.FAIL

    @pytest.mark.requirement("AC-4")
    def test_only_model_nodes_processed(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """Only model.* nodes from run_results should produce events; test nodes ignored."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={
                MODEL_UID_STG_CUSTOMERS: _make_node(),
                "test.customer_360.not_null_id": {
                    "depends_on": {"nodes": [MODEL_UID_STG_CUSTOMERS]},
                },
            },
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[
                _make_result(MODEL_UID_STG_CUSTOMERS),
                _make_result("test.customer_360.not_null_id"),
            ],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        # Only model events should be returned
        assert len(events) == 2
        assert all("stg_customers" in e.job.name for e in events)


# ===========================================================================
# AC-5: Per-model events carry ParentRunFacet
# ===========================================================================


class TestAC5ParentRunFacet:
    """Test that START events carry ParentRunFacet."""

    @pytest.mark.requirement("AC-5")
    def test_start_event_has_parent_run_facet(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """START event run.facets must contain 'parentRun' key."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_event = events[0]
        assert start_event.event_type == RunState.START
        assert "parentRun" in start_event.run.facets

    @pytest.mark.requirement("AC-5")
    def test_parent_run_facet_contains_parent_run_id(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """ParentRunFacet must reference the exact parent_run_id passed in."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        parent_facet = events[0].run.facets["parentRun"]
        assert parent_facet["run"]["runId"] == str(parent_run_id)

    @pytest.mark.requirement("AC-5")
    def test_parent_run_facet_contains_parent_job_name(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """ParentRunFacet must reference the exact parent_job_name passed in."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        parent_facet = events[0].run.facets["parentRun"]
        assert parent_facet["job"]["name"] == PARENT_JOB_NAME

    @pytest.mark.requirement("AC-5")
    def test_parent_run_facet_contains_namespace(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """ParentRunFacet must reference the namespace passed in."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        parent_facet = events[0].run.facets["parentRun"]
        assert parent_facet["job"]["namespace"] == DEFAULT_NAMESPACE

    @pytest.mark.requirement("AC-5")
    def test_all_start_events_carry_parent_facet_in_multi_model(
        self,
        multi_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Every START event across multiple models must have the ParentRunFacet."""
        events = extract_dbt_model_lineage(
            project_dir=multi_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_events = [e for e in events if e.event_type == RunState.START]
        assert len(start_events) == 2

        for start_event in start_events:
            parent_facet = start_event.run.facets["parentRun"]
            assert parent_facet["run"]["runId"] == str(parent_run_id)
            assert parent_facet["job"]["name"] == PARENT_JOB_NAME
            assert parent_facet["job"]["namespace"] == DEFAULT_NAMESPACE

    @pytest.mark.requirement("AC-5")
    def test_parent_facet_built_by_parent_run_facet_builder(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """ParentRunFacet must have the OpenLineage _schemaURL from the builder."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        parent_facet = events[0].run.facets["parentRun"]
        # ParentRunFacetBuilder sets _schemaURL
        assert "_schemaURL" in parent_facet
        assert "ParentRunFacet" in parent_facet["_schemaURL"]


# ===========================================================================
# AC-6: Per-model events use timing from run_results.json
# ===========================================================================


class TestAC6TimingFromRunResults:
    """Test that event_time comes from run_results timing entries."""

    @pytest.mark.requirement("AC-6")
    def test_start_event_uses_first_timing_started_at(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """START event_time must equal timing[0].started_at."""
        compile_start = "2026-03-18T10:00:00Z"
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[
                _make_result(
                    MODEL_UID_STG_CUSTOMERS,
                    timing=[
                        _make_timing(
                            name=COMPILE_STEP_NAME,
                            started_at=compile_start,
                            completed_at="2026-03-18T10:00:01Z",
                        ),
                        _make_timing(
                            name=EXECUTE_STEP_NAME,
                            started_at="2026-03-18T10:00:01Z",
                            completed_at="2026-03-18T10:00:05Z",
                        ),
                    ],
                )
            ],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_event = events[0]
        assert start_event.event_type == RunState.START
        expected = datetime(2026, 3, 18, 10, 0, 0, tzinfo=timezone.utc)
        assert start_event.event_time == expected

    @pytest.mark.requirement("AC-6")
    def test_complete_event_uses_last_timing_completed_at(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """COMPLETE event_time must equal timing[-1].completed_at."""
        execute_completed = "2026-03-18T10:00:05Z"
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[
                _make_result(
                    MODEL_UID_STG_CUSTOMERS,
                    timing=[
                        _make_timing(
                            name=COMPILE_STEP_NAME,
                            started_at="2026-03-18T10:00:00Z",
                            completed_at="2026-03-18T10:00:01Z",
                        ),
                        _make_timing(
                            name=EXECUTE_STEP_NAME,
                            started_at="2026-03-18T10:00:01Z",
                            completed_at=execute_completed,
                        ),
                    ],
                )
            ],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        complete_event = events[1]
        assert complete_event.event_type == RunState.COMPLETE
        expected = datetime(2026, 3, 18, 10, 0, 5, tzinfo=timezone.utc)
        assert complete_event.event_time == expected

    @pytest.mark.requirement("AC-6")
    def test_fail_event_uses_last_timing_completed_at(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """FAIL event_time must equal timing[-1].completed_at."""
        fail_time = "2026-03-18T10:00:03Z"
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[
                _make_result(
                    MODEL_UID_STG_CUSTOMERS,
                    status="error",
                    timing=[
                        _make_timing(
                            name=COMPILE_STEP_NAME,
                            started_at="2026-03-18T10:00:00Z",
                            completed_at=fail_time,
                        ),
                    ],
                )
            ],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        fail_event = events[1]
        assert fail_event.event_type == RunState.FAIL
        expected = datetime(2026, 3, 18, 10, 0, 3, tzinfo=timezone.utc)
        assert fail_event.event_time == expected

    @pytest.mark.requirement("AC-6")
    def test_different_models_use_their_own_timing(
        self,
        multi_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Each model's events must use timing from its own run_results entry."""
        events = extract_dbt_model_lineage(
            project_dir=multi_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )

        # stg_customers timing: started 10:00:00, completed 10:00:05
        stg_events = [e for e in events if "stg_customers" in e.job.name]
        stg_start = datetime(2026, 3, 18, 10, 0, 0, tzinfo=timezone.utc)
        stg_complete = datetime(2026, 3, 18, 10, 0, 5, tzinfo=timezone.utc)
        assert stg_events[0].event_time == stg_start
        assert stg_events[1].event_time == stg_complete

        # dim_customers timing: started 10:00:05, completed 10:00:12
        dim_events = [e for e in events if "dim_customers" in e.job.name]
        dim_start = datetime(2026, 3, 18, 10, 0, 5, tzinfo=timezone.utc)
        dim_complete = datetime(2026, 3, 18, 10, 0, 12, tzinfo=timezone.utc)
        assert dim_events[0].event_time == dim_start
        assert dim_events[1].event_time == dim_complete

    @pytest.mark.requirement("AC-6")
    def test_empty_timing_array_uses_sensible_default(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """Empty timing array should still produce events (not crash)."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[_make_result(MODEL_UID_STG_CUSTOMERS, timing=[])],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        # Should still produce events even without timing
        assert len(events) == 2
        # event_time should be a datetime (some fallback)
        assert isinstance(events[0].event_time, datetime)
        assert isinstance(events[1].event_time, datetime)

    @pytest.mark.requirement("AC-6")
    def test_single_timing_entry(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """With only one timing entry, START uses its started_at, end uses its completed_at."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[
                _make_result(
                    MODEL_UID_STG_CUSTOMERS,
                    timing=[
                        _make_timing(
                            name=EXECUTE_STEP_NAME,
                            started_at="2026-03-18T11:00:00Z",
                            completed_at="2026-03-18T11:00:10Z",
                        ),
                    ],
                )
            ],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert events[0].event_time == datetime(2026, 3, 18, 11, 0, 0, tzinfo=timezone.utc)
        assert events[1].event_time == datetime(2026, 3, 18, 11, 0, 10, tzinfo=timezone.utc)


# ===========================================================================
# AC-7: Per-model events include inputs/outputs from DbtLineageExtractor
# ===========================================================================


class TestAC7InputsOutputsFromExtractor:
    """Test that events carry inputs/outputs from DbtLineageExtractor."""

    @pytest.mark.requirement("AC-7")
    def test_start_event_has_inputs(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """START event must have input datasets from the extractor."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_event = events[0]
        assert len(start_event.inputs) >= 1
        # Should reference the raw source
        input_names = [d.name for d in start_event.inputs]
        assert any("customers" in name for name in input_names)

    @pytest.mark.requirement("AC-7")
    def test_start_event_has_outputs(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """START event must have output datasets from the extractor."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_event = events[0]
        assert len(start_event.outputs) >= 1
        output_names = [d.name for d in start_event.outputs]
        assert any("stg_customers" in name for name in output_names)

    @pytest.mark.requirement("AC-7")
    def test_complete_event_also_has_inputs_outputs(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """COMPLETE event should also carry the same inputs/outputs."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_event = events[0]
        complete_event = events[1]

        # Both events should carry datasets
        assert len(complete_event.inputs) == len(start_event.inputs)
        assert len(complete_event.outputs) == len(start_event.outputs)

    @pytest.mark.requirement("AC-7")
    def test_model_without_dependencies_has_empty_inputs(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """A model with no parents should have empty inputs list."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[_make_result(MODEL_UID_STG_CUSTOMERS)],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_event = events[0]
        assert start_event.inputs == []
        # But should still have output (the model itself)
        assert len(start_event.outputs) >= 1

    @pytest.mark.requirement("AC-7")
    def test_inputs_are_lineage_dataset_instances(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Input and output items must be LineageDataset instances."""
        from floe_core.lineage.types import LineageDataset

        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        for event in events:
            for inp in event.inputs:
                assert isinstance(inp, LineageDataset)
            for out in event.outputs:
                assert isinstance(out, LineageDataset)

    @pytest.mark.requirement("AC-7")
    def test_multi_model_events_have_correct_lineage_per_model(
        self,
        multi_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """dim_customers should depend on stg_customers, not on the raw source directly."""
        events = extract_dbt_model_lineage(
            project_dir=multi_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )

        dim_start_events = [
            e for e in events if e.event_type == RunState.START and "dim_customers" in e.job.name
        ]
        assert len(dim_start_events) == 1
        dim_start = dim_start_events[0]

        # dim_customers depends on stg_customers (not raw source)
        input_names = [d.name for d in dim_start.inputs]
        assert any("stg_customers" in name for name in input_names)

        # output should be dim_customers
        output_names = [d.name for d in dim_start.outputs]
        assert any("dim_customers" in name for name in output_names)


# ===========================================================================
# AC-9: Graceful degradation when artifacts missing
# ===========================================================================


class TestAC9GracefulDegradation:
    """Test that missing artifacts return empty list without raising."""

    @pytest.mark.requirement("AC-9")
    def test_missing_manifest_returns_empty_list(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """If manifest.json doesn't exist, return empty list."""
        target = project_dir / "target"
        # Only write run_results, no manifest
        _write_run_results(target, results=[_make_result(MODEL_UID_STG_CUSTOMERS)])

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert events == []

    @pytest.mark.requirement("AC-9")
    def test_missing_run_results_returns_empty_list(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """If run_results.json doesn't exist, return empty list."""
        target = project_dir / "target"
        # Only write manifest, no run_results
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert events == []

    @pytest.mark.requirement("AC-9")
    def test_missing_both_artifacts_returns_empty_list(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """If both artifacts are missing, return empty list."""
        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert events == []

    @pytest.mark.requirement("AC-9")
    def test_missing_target_directory_returns_empty_list(
        self,
        tmp_path: Path,
        parent_run_id: UUID,
    ) -> None:
        """If target/ directory doesn't exist at all, return empty list."""
        # tmp_path has no target/ subdirectory
        events = extract_dbt_model_lineage(
            project_dir=tmp_path,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert events == []

    @pytest.mark.requirement("AC-9")
    def test_missing_artifacts_does_not_raise(
        self,
        tmp_path: Path,
        parent_run_id: UUID,
    ) -> None:
        """Missing artifacts must NOT raise any exception."""
        # This should not raise FileNotFoundError or any other exception
        result = extract_dbt_model_lineage(
            project_dir=tmp_path,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert isinstance(result, list)

    @pytest.mark.requirement("AC-9")
    def test_missing_manifest_logs_warning(
        self,
        project_dir: Path,
        parent_run_id: UUID,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Missing manifest.json should log a warning."""
        target = project_dir / "target"
        _write_run_results(target, results=[_make_result(MODEL_UID_STG_CUSTOMERS)])

        with caplog.at_level(logging.WARNING):
            extract_dbt_model_lineage(
                project_dir=project_dir,
                parent_run_id=parent_run_id,
                parent_job_name=PARENT_JOB_NAME,
                namespace=DEFAULT_NAMESPACE,
            )

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) >= 1
        assert any("manifest" in msg.lower() for msg in warning_messages)

    @pytest.mark.requirement("AC-9")
    def test_missing_run_results_logs_warning(
        self,
        project_dir: Path,
        parent_run_id: UUID,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Missing run_results.json should log a warning."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )

        with caplog.at_level(logging.WARNING):
            extract_dbt_model_lineage(
                project_dir=project_dir,
                parent_run_id=parent_run_id,
                parent_job_name=PARENT_JOB_NAME,
                namespace=DEFAULT_NAMESPACE,
            )

        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_messages) >= 1
        assert any("run_results" in msg.lower() for msg in warning_messages)

    @pytest.mark.requirement("AC-9")
    def test_malformed_json_returns_empty_list(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """Malformed JSON in artifacts should return empty list, not raise."""
        target = project_dir / "target"
        (target / "manifest.json").write_text("{invalid json")
        _write_run_results(target, results=[_make_result(MODEL_UID_STG_CUSTOMERS)])

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert events == []

    @pytest.mark.requirement("AC-9")
    def test_oserror_on_artifact_read_returns_empty_list(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """OSError (e.g. permission denied) when reading artifact returns empty list."""
        target = project_dir / "target"
        manifest_path = target / "manifest.json"
        manifest_path.write_text("{}")
        # Make file unreadable to trigger OSError
        manifest_path.chmod(0o000)
        _write_run_results(target, results=[_make_result(MODEL_UID_STG_CUSTOMERS)])

        try:
            events = extract_dbt_model_lineage(
                project_dir=project_dir,
                parent_run_id=parent_run_id,
                parent_job_name=PARENT_JOB_NAME,
                namespace=DEFAULT_NAMESPACE,
            )
            assert events == []
        finally:
            manifest_path.chmod(0o644)

    @pytest.mark.requirement("AC-6")
    def test_malformed_timing_entry_missing_keys_uses_fallback(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """Timing entries missing started_at/completed_at should use fallback, not crash."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        # Timing with missing keys
        _write_run_results(
            target,
            results=[
                _make_result(
                    MODEL_UID_STG_CUSTOMERS,
                    timing=[{"name": "execute"}],  # Missing started_at/completed_at
                )
            ],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert len(events) == 2
        assert isinstance(events[0].event_time, datetime)

    @pytest.mark.requirement("AC-9")
    def test_bad_model_does_not_abort_remaining_models(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """If one model's extraction raises, remaining models still produce events."""
        target = project_dir / "target"
        # First model has a valid node, second model is NOT in manifest (will cause extractor error)
        _write_manifest(
            target,
            nodes={
                MODEL_UID_STG_CUSTOMERS: _make_node(),
                # dim_customers NOT in nodes — extractor may raise
            },
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[
                # This model is in the manifest — should succeed
                _make_result(MODEL_UID_STG_CUSTOMERS),
                # This model is NOT in the manifest — extraction should fail gracefully
                _make_result(MODEL_UID_DIM_CUSTOMERS),
            ],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        # At minimum the first model should have produced events
        stg_events = [e for e in events if "stg_customers" in e.job.name]
        assert len(stg_events) >= 2

    @pytest.mark.requirement("AC-4")
    def test_skipped_model_emits_fail_state(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """A model with status 'skipped' should emit FAIL, not COMPLETE."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[_make_result(MODEL_UID_STG_CUSTOMERS, status="skipped")],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        assert len(events) == 2
        assert events[0].event_type == RunState.START
        assert events[1].event_type == RunState.FAIL


# ===========================================================================
# AC-12: Column lineage facets when available
# ===========================================================================


class TestAC12ColumnLineageFacets:
    """Test column lineage facets on output datasets when column metadata exists."""

    @pytest.mark.requirement("AC-12")
    def test_output_dataset_has_column_lineage_facet(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Output dataset facets should contain 'columnLineage' when columns exist."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_event = events[0]
        assert len(start_event.outputs) >= 1
        output_facets = start_event.outputs[0].facets
        assert "columnLineage" in output_facets

    @pytest.mark.requirement("AC-12")
    def test_column_lineage_facet_has_fields_key(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Column lineage facet must have a 'fields' dict."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        col_lineage = events[0].outputs[0].facets["columnLineage"]
        assert "fields" in col_lineage
        assert isinstance(col_lineage["fields"], dict)

    @pytest.mark.requirement("AC-12")
    def test_column_lineage_contains_model_columns(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Column lineage fields should list the model's columns."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        col_lineage = events[0].outputs[0].facets["columnLineage"]
        # single_model_project has column "id"
        assert "id" in col_lineage["fields"]

    @pytest.mark.requirement("AC-12")
    def test_column_lineage_has_schema_url(
        self,
        single_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Column lineage facet must have the OpenLineage _schemaURL."""
        events = extract_dbt_model_lineage(
            project_dir=single_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        col_lineage = events[0].outputs[0].facets["columnLineage"]
        assert "_schemaURL" in col_lineage
        assert "ColumnLineage" in col_lineage["_schemaURL"]

    @pytest.mark.requirement("AC-12")
    def test_no_column_lineage_when_no_columns(
        self,
        project_dir: Path,
        parent_run_id: UUID,
    ) -> None:
        """If model has no column metadata, output should not have columnLineage facet."""
        target = project_dir / "target"
        _write_manifest(
            target,
            nodes={MODEL_UID_STG_CUSTOMERS: _make_node()},  # No columns
            parent_map={MODEL_UID_STG_CUSTOMERS: []},
        )
        _write_run_results(
            target,
            results=[_make_result(MODEL_UID_STG_CUSTOMERS)],
        )

        events = extract_dbt_model_lineage(
            project_dir=project_dir,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )
        start_event = events[0]
        assert len(start_event.outputs) >= 1
        output_facets = start_event.outputs[0].facets
        assert "columnLineage" not in output_facets

    @pytest.mark.requirement("AC-12")
    def test_multi_column_lineage(
        self,
        multi_model_project: Path,
        parent_run_id: UUID,
    ) -> None:
        """Model with multiple columns should have all columns in lineage facet."""
        events = extract_dbt_model_lineage(
            project_dir=multi_model_project,
            parent_run_id=parent_run_id,
            parent_job_name=PARENT_JOB_NAME,
            namespace=DEFAULT_NAMESPACE,
        )

        # dim_customers has columns: id, full_name
        dim_events = [
            e for e in events if e.event_type == RunState.START and "dim_customers" in e.job.name
        ]
        assert len(dim_events) == 1
        dim_start = dim_events[0]
        assert len(dim_start.outputs) >= 1
        col_lineage = dim_start.outputs[0].facets["columnLineage"]
        assert "id" in col_lineage["fields"]
        assert "full_name" in col_lineage["fields"]
