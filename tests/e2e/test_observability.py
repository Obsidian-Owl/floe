"""End-to-end tests for observability integration.

This test validates that the observability stack (OpenTelemetry, OpenLineage,
Prometheus, structured logging) delivers REAL data after pipeline execution.

Requirements Covered:
- FR-040: OpenTelemetry span-per-model tracing
- FR-041: OpenLineage event emission (4 emission points)
- FR-042: Trace/lineage correlation via trace_id
- FR-043: Prometheus metrics collection
- FR-045: Structured logging with trace_id
- FR-046: Observability must be non-blocking
- FR-047: Jaeger trace query validation
- FR-048: Marquez lineage graph validation

Per testing standards: Tests FAIL when infrastructure is unavailable.
No pytest.skip() - see .claude/rules/testing-standards.md
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote

import httpx
import pytest
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.fixtures.services import ServiceEndpoint

_COMPLETED_MARQUEZ_STATE = "COMPLETED"


def _marquez_job_runs(
    marquez_client: httpx.Client,
    *,
    namespace: str,
    job_name: str,
    allow_missing: bool = False,
) -> list[dict[str, Any]]:
    """Query Marquez runs for a namespace/job pair."""
    encoded_namespace = quote(namespace, safe="")
    encoded_job_name = quote(job_name, safe="")
    response = marquez_client.get(
        f"/api/v1/namespaces/{encoded_namespace}/jobs/{encoded_job_name}/runs"
    )
    if allow_missing and response.status_code == 404:
        return []
    assert response.status_code == 200, (
        f"Marquez runs endpoint failed for {namespace}/{job_name}: "
        f"{response.status_code} - {response.text}"
    )
    runs = response.json().get("runs", [])
    assert isinstance(runs, list), f"Marquez runs should be a list, got {type(runs)}"
    return runs


def _marquez_run_state(run: dict[str, Any]) -> str:
    """Return normalized Marquez run state across API response variants."""
    return str(run.get("state") or run.get("currentState") or "").upper()


def _marquez_run_identity(run: dict[str, Any]) -> str:
    """Return a stable identity for comparing Marquez runs across snapshots."""
    for key in ("id", "runId", "run_id"):
        value = run.get(key)
        if value:
            return str(value)
    nested_run = run.get("run")
    if isinstance(nested_run, dict):
        for key in ("runId", "id", "run_id"):
            value = nested_run.get(key)
            if value:
                return str(value)
    return str(run)


def _marquez_run_identity_candidates(run: dict[str, Any]) -> set[str]:
    """Return all run id variants Marquez may expose for one run."""
    candidates: set[str] = set()
    for key in ("id", "runId", "run_id"):
        value = run.get(key)
        if value:
            candidates.add(str(value))

    nested_run = run.get("run")
    if isinstance(nested_run, dict):
        for key in ("id", "runId", "run_id"):
            value = nested_run.get(key)
            if value:
                candidates.add(str(value))

    return candidates


def _marquez_run_id_snapshot(
    marquez_client: httpx.Client,
    *,
    namespace: str,
    job_name: str,
) -> set[str]:
    """Return current Marquez run identities without requiring the job to exist."""
    return {
        _marquez_run_identity(run)
        for run in _marquez_job_runs(
            marquez_client,
            namespace=namespace,
            job_name=job_name,
            allow_missing=True,
        )
    }


def _marquez_namespace_jobs(
    marquez_client: httpx.Client,
    *,
    namespace: str,
    allow_missing: bool = False,
) -> list[dict[str, Any]]:
    """Query Marquez jobs for one namespace."""
    response = marquez_client.get(f"/api/v1/namespaces/{quote(namespace, safe='')}/jobs")
    if allow_missing and response.status_code == 404:
        return []
    assert response.status_code == 200, (
        f"Marquez jobs endpoint failed for {namespace}: {response.status_code} - {response.text}"
    )
    jobs = response.json().get("jobs", [])
    assert isinstance(jobs, list), f"Marquez jobs should be a list, got {type(jobs)}"
    return jobs


def _marquez_namespace_run_snapshot(
    marquez_client: httpx.Client,
    *,
    namespace: str,
) -> dict[str, set[str]]:
    """Return current run identities for every job in a namespace."""
    snapshot: dict[str, set[str]] = {}
    for job in _marquez_namespace_jobs(
        marquez_client,
        namespace=namespace,
        allow_missing=True,
    ):
        job_name = job.get("name")
        if not job_name:
            continue
        snapshot[str(job_name)] = _marquez_run_id_snapshot(
            marquez_client,
            namespace=namespace,
            job_name=str(job_name),
        )
    return snapshot


def _fresh_completed_runs(
    marquez_client: httpx.Client,
    *,
    namespace: str,
    job_name: str,
    before_run_ids: set[str],
) -> list[dict[str, Any]]:
    """Return runs that appeared after the snapshot and completed successfully."""
    return [
        run
        for run in _marquez_job_runs(
            marquez_client,
            namespace=namespace,
            job_name=job_name,
        )
        if _marquez_run_identity(run) not in before_run_ids
        and _marquez_run_state(run) == _COMPLETED_MARQUEZ_STATE
    ]


def _fresh_completed_runs_for_jobs(
    marquez_client: httpx.Client,
    *,
    namespace: str,
    job_names: set[str],
    before_run_ids_by_job: dict[str, set[str]],
) -> list[dict[str, Any]]:
    """Return fresh completed Marquez runs for the supplied namespace/jobs."""
    fresh_runs: list[dict[str, Any]] = []
    for job_name in sorted(job_names):
        before_run_ids = before_run_ids_by_job.get(job_name, set())
        for run in _marquez_job_runs(
            marquez_client,
            namespace=namespace,
            job_name=job_name,
            allow_missing=True,
        ):
            if (
                _marquez_run_identity(run) not in before_run_ids
                and _marquez_run_state(run) == _COMPLETED_MARQUEZ_STATE
            ):
                run["_job_name"] = job_name
                run["_namespace"] = namespace
                fresh_runs.append(run)
    return fresh_runs


def _expected_model_job_names(artifacts: Any) -> set[str]:
    """Return artifact-derived Marquez job names that can represent dbt models."""
    product_name = str(artifacts.metadata.product_name)
    dbt_project_name = re.sub(r"[^A-Za-z0-9_]", "_", product_name).strip("_") or "floe"
    model_names = [model.name for model in artifacts.transforms.models]
    return {
        candidate
        for model_name in model_names
        for candidate in (
            model_name,
            f"model.{dbt_project_name}.{model_name}",
            f"{product_name}.model.{dbt_project_name}.{model_name}",
        )
    }


def _run_has_nonzero_duration(run: dict[str, Any]) -> bool:
    """Return whether a Marquez run exposes a positive startedAt to endedAt duration."""
    from datetime import datetime

    started_at: str = run.get("startedAt", "")
    ended_at: str = run.get("endedAt", "")
    if not started_at or not ended_at:
        return False
    try:
        start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    return (end_dt - start_dt).total_seconds() > 0


def _parent_run_id_from_run(run: dict[str, Any]) -> str | None:
    """Return a parent facet run id from a Marquez run response if exposed."""
    facets: dict[str, Any] = run.get("facets") or {}
    parent_facet: dict[str, Any] | None = None
    if "parentRun" in facets:
        parent_facet = facets["parentRun"]
    elif "parent" in facets:
        parent_facet = facets["parent"]
    else:
        run_facets: dict[str, Any] = facets.get("run") or {}
        if "parentRun" in run_facets:
            parent_facet = run_facets["parentRun"]
        elif "parent" in run_facets:
            parent_facet = run_facets["parent"]

    if not isinstance(parent_facet, dict):
        return None
    parent_run = parent_facet.get("run")
    if isinstance(parent_run, dict):
        parent_run_id = parent_run.get("runId") or parent_run.get("id")
        if parent_run_id:
            return str(parent_run_id)
    parent_run_id = parent_facet.get("runId") or parent_facet.get("id")
    return str(parent_run_id) if parent_run_id else None


def _parent_run_id_from_event(event: dict[str, Any]) -> str | None:
    """Return a parent facet run id from an OpenLineage event if exposed."""
    payload = _lineage_event_payload(event)
    run = payload.get("run") or event.get("run")
    if not isinstance(run, dict):
        return None
    return _parent_run_id_from_run(run)


def _parent_run_id_from_marquez_run_facets(
    marquez_client: Any,
    run: dict[str, Any],
) -> str | None:
    """Return a parent facet run id via Marquez's dedicated run facets endpoint."""
    for run_id in sorted(_marquez_run_identity_candidates(run)):
        response = marquez_client.get(
            f"/api/v1/runs/{quote(run_id, safe='')}/facets",
            params={"type": "run"},
        )
        if response.status_code != 200:
            continue
        facets = response.json().get("facets")
        if not isinstance(facets, dict):
            continue
        parent_run_id = _parent_run_id_from_run({"facets": facets})
        if parent_run_id:
            return parent_run_id
    return None


def _lineage_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Return the OpenLineage event payload across Marquez response variants."""
    for key in ("event", "lineageEvent", "openLineageEvent"):
        payload = event.get(key)
        if isinstance(payload, dict):
            return payload
    return event


def _lineage_event_type(event: dict[str, Any]) -> str:
    """Return normalized OpenLineage eventType across response variants."""
    payload = _lineage_event_payload(event)
    return str(event.get("eventType") or payload.get("eventType") or "").upper()


def _lineage_event_run_id(event: dict[str, Any]) -> str | None:
    """Return the OpenLineage run id from a Marquez events API item."""
    payload = _lineage_event_payload(event)
    run = payload.get("run") or event.get("run")
    if isinstance(run, dict):
        for key in ("runId", "run_id", "id"):
            value = run.get(key)
            if value:
                return str(value)

    for key in ("runId", "run_id", "runUuid", "runUUID"):
        value = event.get(key) or payload.get(key)
        if value:
            return str(value)
    return None


def _lineage_event_job(event: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (namespace, job name) from a Marquez events API item."""
    payload = _lineage_event_payload(event)
    job = payload.get("job") or event.get("job")
    if isinstance(job, dict):
        namespace = job.get("namespace") or job.get("namespaceName")
        name = job.get("name") or job.get("jobName")
        return (
            str(namespace) if namespace else None,
            str(name) if name else None,
        )

    namespace = event.get("namespace") or event.get("jobNamespace")
    name = event.get("jobName") or event.get("job")
    return (
        str(namespace) if namespace else None,
        str(name) if name else None,
    )


def _runtime_lineage_identity_from_events(
    events: list[dict[str, Any]],
) -> tuple[str, str] | None:
    """Return the first namespace/job identity emitted by fresh lineage events."""
    for event in events:
        namespace, job_name = _lineage_event_job(event)
        if namespace and job_name:
            return namespace, job_name
    return None


def _lineage_event_matches_fresh_run(
    event: dict[str, Any],
    *,
    namespace: str,
    job_name: str,
    fresh_run_ids: set[str],
) -> bool:
    """Return whether an events API item can be tied to the fresh runtime run."""
    event_run_id = _lineage_event_run_id(event)
    if event_run_id is None or event_run_id not in fresh_run_ids:
        return False

    event_namespace, event_job_name = _lineage_event_job(event)
    if event_namespace is not None and event_namespace != namespace:
        return False
    if event_job_name is not None and event_job_name != job_name:
        return False
    return True


def _lineage_event_matches_fresh_jobs(
    event: dict[str, Any],
    *,
    namespace: str,
    job_names: set[str],
    fresh_run_ids: set[str],
) -> bool:
    """Return whether an events API item can be tied to fresh runtime jobs."""
    event_run_id = _lineage_event_run_id(event)
    if event_run_id is None or event_run_id not in fresh_run_ids:
        return False

    event_namespace, event_job_name = _lineage_event_job(event)
    if event_namespace is not None and event_namespace != namespace:
        return False
    if event_job_name is not None and event_job_name not in job_names:
        return False
    return True


@pytest.mark.developer_workflow
def test_runtime_lineage_identity_prefers_fresh_event_job() -> None:
    """Marquez validation should query the identity emitted by OpenLineage."""
    event = {
        "event": {
            "job": {
                "namespace": "customer-360",
                "name": "dbt.customer_360.mart_customer_360",
            }
        }
    }

    assert _runtime_lineage_identity_from_events([event]) == (
        "customer-360",
        "dbt.customer_360.mart_customer_360",
    )


@pytest.mark.developer_workflow
def test_parent_run_id_from_marquez_run_facets_uses_facets_endpoint() -> None:
    """Marquez validation should use the documented run facets endpoint."""

    class _Response:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "facets": {
                    "parent": {
                        "run": {"runId": "parent-run-id"},
                        "job": {"namespace": "customer-360", "name": "asset-job"},
                    }
                }
            }

    class _Client:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str] | None]] = []

        def get(self, path: str, params: dict[str, str] | None = None) -> _Response:
            self.calls.append((path, params))
            return _Response()

    client = _Client()

    assert _parent_run_id_from_marquez_run_facets(client, {"id": "model-run-id"}) == (
        "parent-run-id"
    )
    assert client.calls == [
        ("/api/v1/runs/model-run-id/facets", {"type": "run"}),
    ]


@pytest.mark.developer_workflow
def test_expected_model_job_names_include_product_scoped_runtime_identity() -> None:
    """Runtime model job candidates include product-scoped dbt unique IDs."""

    class _Model:
        name = "stg_crm_customers"

    class _Transforms:
        models = [_Model()]

    class _Metadata:
        product_name = "customer-360"

    class _Artifacts:
        metadata = _Metadata()
        transforms = _Transforms()

    job_names = _expected_model_job_names(_Artifacts())

    assert "customer-360.model.customer_360.stg_crm_customers" in job_names


class TestObservability(IntegrationTestBase):
    """E2E tests for observability stack integration.

    These tests validate that observability features deliver real data:
    1. OpenTelemetry traces exist and are queryable in Jaeger
    2. OpenLineage events are emitted to Marquez with real job data
    3. Trace IDs correlate between OTel spans and OpenLineage events
    4. Metrics pipeline is deployed and healthy via OTel Collector
    5. Structured logs contain trace context during compilation
    6. Observability failures do not block pipeline execution
    7. Marquez lineage graph contains real pipeline lineage

    Requires all platform services running:
    - Dagster (orchestrator)
    - Jaeger (trace collection)
    - Marquez (lineage tracking)
    - OTel Collector (telemetry gateway)
    """

    # Services required for observability E2E tests
    # Only NodePort-accessible services in required_services
    # Other services (marquez, prometheus, otel-collector) checked individually
    required_services: ClassVar[list[str]] = [
        "dagster",
        "jaeger-query",
    ]

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-047")
    def test_otel_traces_in_jaeger(
        self,
        e2e_namespace: str,
        jaeger_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Validate that OTel traces with real spans exist in Jaeger for the customer-360 service.

        Demands that:
        1. Jaeger contains traces for the 'customer-360' service
        2. Traces contain spans with operation names
        3. The services list includes 'customer-360'

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")
        self.check_infrastructure("jaeger-query")

        # Query Jaeger for customer-360 service traces
        service_name = "customer-360"
        traces_response = jaeger_client.get(
            "/api/traces",
            params={"service": service_name, "limit": 5},
        )
        assert traces_response.status_code == 200, (
            f"Jaeger traces query failed: {traces_response.status_code}"
        )
        traces_json = traces_response.json()
        assert "data" in traces_json, "Jaeger traces response missing 'data' key"

        traces = traces_json["data"]
        assert len(traces) > 0, (
            "OBSERVABILITY GAP: No traces found for 'customer-360' service in Jaeger.\n"
            "The OTel pipeline is not emitting traces during compilation or pipeline execution.\n"
            "Fix: Configure OTel SDK in floe-core compilation "
            "stages to emit spans.\n"
            "Expected: Each compilation stage should emit a span."
        )

        # Validate trace structure contains real spans
        first_trace = traces[0]
        assert "traceID" in first_trace, "Trace missing traceID"
        assert "spans" in first_trace, "Trace missing spans"
        assert len(first_trace["spans"]) > 0, (
            "Trace exists but has no spans. OTel instrumentation is emitting "
            "empty traces without span data."
        )

        # Validate spans have required attributes for pipeline debugging
        first_span = first_trace["spans"][0]
        assert "operationName" in first_span, "Span missing operationName"
        assert len(first_span["operationName"]) > 0, (
            "Span has empty operationName -- OTel instrumentation not setting span names"
        )

        # Verify services list includes customer-360
        response = jaeger_client.get("/api/services")
        assert response.status_code == 200, (
            f"Jaeger services endpoint failed: {response.status_code}"
        )
        services_json = response.json()
        assert "data" in services_json, "Jaeger services response missing 'data' key"
        services = services_json["data"]
        assert "customer-360" in services, (
            f"OBSERVABILITY GAP: 'customer-360' not in Jaeger services list.\n"
            f"Services found: {services}\n"
            "Fix: Configure OTel SDK with service.name='customer-360'"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("FR-048")
    @pytest.mark.requirement("AC-4")
    def test_openlineage_events_in_marquez(
        self,
        e2e_namespace: str,
        marquez_client: httpx.Client,
        dagster_client: Any,
        compiled_artifacts: Callable[[Path], Any],
        project_root: Path,
        trigger_lineage_run: Callable[..., None],
    ) -> None:
        """Validate that Marquez contains real OpenLineage jobs from pipeline execution.

        Demands that:
        1. Marquez API is accessible and namespace creation works
        2. Real OpenLineage jobs exist in at least one namespace
        3. Pipeline execution has emitted RunEvent.START/COMPLETE events
        4. Jobs match the product name from this pipeline run

        Args:
            e2e_namespace: Unique namespace for test isolation.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client.
            compiled_artifacts: Real compiler fixture used to resolve lineage namespace.
            project_root: Repository root fixture.
            trigger_lineage_run: Callable that triggers one fresh runtime lineage run.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")
        try:
            self.check_infrastructure("marquez")
        except Exception:
            pytest.fail(
                "Marquez not accessible. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000 -n floe-test"
            )

        # Verify Marquez API responds with namespaces list
        response = marquez_client.get("/api/v1/namespaces")
        assert response.status_code == 200, (
            f"Marquez namespaces endpoint failed: {response.status_code}"
        )

        # Verify response structure
        response_json = response.json()
        assert "namespaces" in response_json, "Marquez response missing 'namespaces' key"
        assert isinstance(response_json["namespaces"], list), (
            f"Namespaces should be a list, got: {type(response_json['namespaces'])}"
        )

        # Test creating a namespace (validates write capability)
        test_namespace = f"floe-test-{e2e_namespace}"
        create_response = marquez_client.put(
            f"/api/v1/namespaces/{test_namespace}",
            json={
                "ownerName": "floe-e2e-test",
                "description": "E2E test namespace for OpenLineage validation",
            },
        )
        assert create_response.status_code in (
            200,
            201,
        ), f"Failed to create namespace: {create_response.status_code} - {create_response.text}"

        # Verify namespace was created
        verify_response = marquez_client.get(f"/api/v1/namespaces/{test_namespace}")
        assert verify_response.status_code == 200, f"Created namespace not found: {test_namespace}"

        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)
        runtime_namespace = artifacts.observability.lineage_namespace
        runtime_job_name = artifacts.metadata.product_name
        before_run_ids = _marquez_run_id_snapshot(
            marquez_client,
            namespace=runtime_namespace,
            job_name=runtime_job_name,
        )
        lineage_events_before_response = marquez_client.get(
            "/api/v1/events/lineage",
            params={"limit": 100},
        )
        assert lineage_events_before_response.status_code == 200, (
            "Marquez lineage events endpoint failed before runtime trigger: "
            f"{lineage_events_before_response.status_code} - "
            f"{lineage_events_before_response.text}"
        )
        lineage_events_before = lineage_events_before_response.json().get("events", [])
        before_lineage_event_run_ids = {
            run_id
            for event in lineage_events_before
            if (run_id := _lineage_event_run_id(event)) is not None
        }
        trigger_lineage_run(
            expected_namespace=runtime_namespace,
            expected_job_name=runtime_job_name,
            before_run_ids=before_run_ids,
        )

        # Query for REAL jobs -- not just API responds
        jobs_response = marquez_client.get(f"/api/v1/namespaces/{test_namespace}/jobs")
        assert jobs_response.status_code == 200, (
            f"Jobs endpoint failed: {jobs_response.status_code}"
        )

        lineage_events_response = marquez_client.get(
            "/api/v1/events/lineage",
            params={"limit": 100},
        )
        assert lineage_events_response.status_code == 200, (
            "Marquez lineage events endpoint failed after runtime trigger: "
            f"{lineage_events_response.status_code} - {lineage_events_response.text}"
        )
        lineage_events = lineage_events_response.json().get("events", [])
        fresh_lineage_events = [
            event
            for event in lineage_events
            if (run_id := _lineage_event_run_id(event)) is not None
            and run_id not in before_lineage_event_run_ids
        ]
        assert fresh_lineage_events, (
            "OBSERVABILITY GAP: No fresh OpenLineage events found after runtime trigger.\n"
            f"Existing event run ids before trigger: {len(before_lineage_event_run_ids)}\n"
            "Expected the runtime trigger to emit OpenLineage events with new run ids."
        )

        event_identity = _runtime_lineage_identity_from_events(fresh_lineage_events)
        assert event_identity is not None, (
            "Runtime OpenLineage events were received but no job namespace/name "
            f"could be extracted. events={fresh_lineage_events[:3]}"
        )
        event_namespace, event_job_name = event_identity

        runtime_jobs_response = marquez_client.get(
            f"/api/v1/namespaces/{quote(event_namespace, safe='')}/jobs"
        )
        assert runtime_jobs_response.status_code == 200, (
            f"Marquez runtime namespace jobs query failed for emitted namespace "
            f"{event_namespace}: {runtime_jobs_response.status_code} - "
            f"{runtime_jobs_response.text}"
        )
        all_jobs: list[dict[str, Any]] = runtime_jobs_response.json().get("jobs", [])

        # We need REAL OpenLineage events from pipeline execution
        assert len(all_jobs) > 0, (
            "OBSERVABILITY GAP: No OpenLineage jobs found in runtime namespace.\n"
            "The platform is not emitting OpenLineage events during pipeline execution.\n"
            "Fix: Configure dbt-openlineage or Dagster OpenLineage integration to emit "
            "RunEvent.START and RunEvent.COMPLETE events.\n"
            f"Namespace checked: {event_namespace}"
        )

        job_names = [job.get("name", "") for job in all_jobs]
        assert event_job_name in job_names, (
            "OBSERVABILITY GAP: Emitted runtime OpenLineage job not found in Marquez.\n"
            f"Emitted namespace/job: {event_namespace}/{event_job_name}\n"
            f"Artifact-derived namespace/job used to trigger: "
            f"{runtime_namespace}/{runtime_job_name}\n"
            f"Job names found: {job_names}\n"
            "Expected Marquez to expose the namespace/job from the emitted "
            "OpenLineage event."
        )

        runtime_runs = _marquez_job_runs(
            marquez_client,
            namespace=event_namespace,
            job_name=event_job_name,
        )
        fresh_lineage_event_run_ids = {
            run_id
            for event in fresh_lineage_events
            if (run_id := _lineage_event_run_id(event)) is not None
        }
        fresh_completed_runs = [
            run
            for run in runtime_runs
            if _marquez_run_identity_candidates(run) & fresh_lineage_event_run_ids
            and _marquez_run_state(run) == _COMPLETED_MARQUEZ_STATE
        ]
        run_states = {_marquez_run_state(run) for run in runtime_runs if _marquez_run_state(run)}
        assert fresh_completed_runs, (
            "OBSERVABILITY GAP: Runtime OpenLineage did not create a fresh "
            "COMPLETED Marquez run.\n"
            f"Emitted namespace/job: {event_namespace}/{event_job_name}\n"
            f"Fresh event run ids: {sorted(fresh_lineage_event_run_ids)}\n"
            f"Run states found: {sorted(run_states)}\n"
            "Expected a new run with state COMPLETED."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-042")
    @pytest.mark.requirement("AC-7")
    def test_trace_lineage_correlation(
        self,
        e2e_namespace: str,
        jaeger_client: httpx.Client,
        marquez_client: httpx.Client,
        dagster_client: Any,
        seed_observability: None,
    ) -> None:
        """Validate that trace_id correlates between Jaeger traces and Marquez lineage events.

        Demands that:
        1. Jaeger has floe-related service traces (AND condition)
        2. Marquez has floe-related namespaces with pipeline data (AND condition)
        3. A trace_id from Jaeger matches a run_id or trace_id in Marquez events
        4. BOTH systems must have data for correlation to be meaningful

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")
        self.check_infrastructure("jaeger-query")
        try:
            self.check_infrastructure("marquez")
        except Exception:
            pytest.fail(
                "Marquez not accessible. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000 -n floe-test"
            )

        # Query for REAL traces in Jaeger for any floe-related service
        all_services_response = jaeger_client.get("/api/services")
        assert all_services_response.status_code == 200
        # Jaeger returns {"data": null} when no services exist — coalesce to []
        all_services = all_services_response.json().get("data") or []

        floe_services = [
            s
            for s in all_services
            if any(
                term in s.lower()
                for term in (
                    "floe",
                    "dagster",
                    "customer-360",
                    "iot-telemetry",
                    "financial-risk",
                )
            )
        ]

        # Query Marquez for REAL jobs
        all_namespaces_response = marquez_client.get("/api/v1/namespaces")
        assert all_namespaces_response.status_code == 200
        all_namespaces = all_namespaces_response.json().get("namespaces", [])

        # Runtime lineage events may land in "default" or any configured namespace.
        # Include "default" as a fallback so jobs emitted without a custom namespace are found.
        floe_namespaces = [
            ns["name"]
            for ns in all_namespaces
            if "floe" in ns["name"].lower()
            or "customer" in ns["name"].lower()
            or "iot" in ns["name"].lower()
            or "financial" in ns["name"].lower()
            or ns["name"].lower() == "default"
        ]

        # BOTH systems must have pipeline data for correlation to work (AND, not OR)
        assert len(floe_services) > 0 and len(floe_namespaces) > 0, (
            "CORRELATION GAP: Both Jaeger AND Marquez must have pipeline data.\n"
            f"Jaeger floe services: {floe_services} (found: {len(floe_services)})\n"
            f"Marquez floe namespaces: {floe_namespaces} (found: {len(floe_namespaces)})\n"
            f"All Jaeger services: {all_services}\n"
            f"All Marquez namespaces: {[ns['name'] for ns in all_namespaces]}\n"
            "Fix: Run a pipeline with both OTel tracing and OpenLineage emission enabled, "
            "using the same run_id for correlation."
        )

        # Now verify actual correlation: get a trace_id from Jaeger
        # and check Marquez has a lineage event with matching run_id/trace_id
        jaeger_trace_id: str | None = None
        for service in floe_services:
            traces_response = jaeger_client.get(
                "/api/traces",
                params={"service": service, "limit": 5},
            )
            if traces_response.status_code == 200:
                traces = traces_response.json().get("data", [])
                if traces:
                    jaeger_trace_id = traces[0].get("traceID")
                    break

        assert jaeger_trace_id is not None, (
            "CORRELATION GAP: Floe services exist in Jaeger but no traces found.\n"
            f"Services checked: {floe_services}"
        )

        # Query Marquez for lineage events that reference this trace_id
        correlation_found = False
        for ns_name in floe_namespaces:
            jobs_response = marquez_client.get(f"/api/v1/namespaces/{ns_name}/jobs")
            if jobs_response.status_code != 200:
                continue
            jobs = jobs_response.json().get("jobs", [])
            for job in jobs:
                runs_response = marquez_client.get(
                    f"/api/v1/namespaces/{ns_name}/jobs/{job['name']}/runs"
                )
                if runs_response.status_code != 200:
                    continue
                runs = runs_response.json().get("runs", [])
                for run in runs:
                    # Check if run_id or facets contain the trace_id
                    run_id = run.get("id", "")
                    facets = run.get("facets", {})
                    # Check for trace_id in parent run facet or custom facets
                    facets_str = json.dumps(facets)
                    if jaeger_trace_id in run_id or jaeger_trace_id in facets_str:
                        correlation_found = True
                        break
                if correlation_found:
                    break
            if correlation_found:
                break

        assert correlation_found, (
            "CORRELATION GAP: trace_id from Jaeger not found in Marquez lineage events.\n"
            f"Jaeger trace_id: {jaeger_trace_id}\n"
            f"Namespaces searched: {floe_namespaces}\n"
            "Fix: Pipeline must propagate OTel trace_id into OpenLineage run facets "
            "so that traces and lineage events can be correlated."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-043")
    def test_prometheus_metrics(
        self,
        e2e_namespace: str,
        dagster_client: Any,
    ) -> None:
        """Validate that OTel Collector is deployed and healthy for metrics pipeline.

        Demands that:
        1. OTel Collector service exists in the K8s cluster
        2. OTel Collector pods are in Running state

        ARCHITECTURE NOTE: Prometheus is NOT part of the floe platform.
        Metrics flow through OTel Collector to external metrics backend.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            dagster_client: Dagster GraphQL client.
        """
        import subprocess

        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")

        # Verify OTel Collector is deployed AND healthy
        result = subprocess.run(
            ["kubectl", "get", "svc", "-n", "floe-test", "-o", "name"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            pytest.fail(
                "INFRASTRUCTURE ERROR: Failed to query K8s services.\n"
                f"Error: {result.stderr.strip()}\n"
                "Check: kubectl access to namespace 'floe-test'"
            )

        services = result.stdout.lower()
        assert "otel" in services or "opentelemetry" in services, (
            "INFRASTRUCTURE GAP: OTel Collector not deployed.\n"
            "\n"
            "ARCHITECTURE: Metrics flow through OTel Collector.\n"
            "Platform -> OTel Collector -> External Backend\n"
            "\n"
            "ROOT CAUSE: OTel Collector is disabled in test values.\n"
            "File: charts/floe-platform/values-test.yaml\n"
            "Setting: otel.enabled: false\n"
            "\n"
            "FIX: Enable OTel Collector:\n"
            "  otel:\n"
            "    enabled: true\n"
            "\n"
            f"Services found:\n{result.stdout}"
        )

        # If OTel Collector IS deployed, verify it's actually running
        pod_result = subprocess.run(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "floe-test",
                "-l",
                "app.kubernetes.io/name=otel",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        # Verify old label is NOT used in this query (negative assertion)
        # The old label 'opentelemetry-collector' would find zero pods since
        # the chart uses 'otel' as the component label (configmap-otel.yaml).
        assert "opentelemetry-collector" not in " ".join(pod_result.args), (
            "Pod query uses old label 'opentelemetry-collector'. "
            "Must use 'otel' to match configmap-otel.yaml."
        )

        # Pod query MUST succeed -- no silent fallback
        assert pod_result.returncode == 0, (
            f"INFRASTRUCTURE ERROR: Failed to query OTel Collector pods.\n"
            f"Error: {pod_result.stderr.strip()}\n"
            "kubectl must be able to query pods in 'floe-test' namespace."
        )
        assert pod_result.stdout.strip(), (
            "INFRASTRUCTURE GAP: No OTel Collector pods found matching label "
            "app.kubernetes.io/name=otel.\n"
            "OTel Collector service exists but no pods are scheduled."
        )
        phases = pod_result.stdout.strip().split()
        assert all(p == "Running" for p in phases), (
            f"OTel Collector pods not all running. Phases: {phases}"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-045")
    def test_structured_logs_with_trace_id(
        self,
        e2e_namespace: str,
        dagster_client: Any,
    ) -> None:
        """Validate that compilation emits structured logs containing trace_id context.

        Demands that:
        1. Compilation produces log output
        2. Log lines contain trace_id field in 32-hex-char format
        3. trace_id in logs matches the span trace_id from compilation
        4. Dagster runs endpoint is accessible for log correlation

        Args:
            e2e_namespace: Unique namespace for test isolation.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")

        # Validate that compilation emits structured logs with trace context
        import io
        import logging
        from pathlib import Path

        from floe_core.compilation.stages import compile_pipeline
        from floe_core.telemetry.initialization import (
            ensure_telemetry_initialized,
            reset_telemetry,
        )

        project_root = Path(__file__).parent.parent.parent
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Initialize telemetry so structlog is configured with trace context
        # injection via stdlib LoggerFactory.  Set OTEL_EXPORTER_OTLP_ENDPOINT
        # so a real TracerProvider is created (not NoOp) and spans carry valid
        # (non-zero) trace_ids that add_trace_context will inject into logs.
        old_otlp = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        old_insecure = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ServiceEndpoint("otel-collector-grpc").url
        os.environ["OTEL_EXPORTER_OTLP_INSECURE"] = "true"

        # Capture log output during compilation
        log_buffer = io.StringIO()
        handler = logging.StreamHandler(log_buffer)
        handler.setLevel(logging.DEBUG)
        root_logger = logging.getLogger("floe_core")
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(handler)

        try:
            ensure_telemetry_initialized()
            artifacts = compile_pipeline(spec_path, manifest_path)
            assert artifacts is not None, "Compilation should succeed"
        finally:
            root_logger.removeHandler(handler)
            reset_telemetry()
            # Restore OTel env vars to avoid leaking to other tests
            for key, old_val in (
                ("OTEL_EXPORTER_OTLP_ENDPOINT", old_otlp),
                ("OTEL_EXPORTER_OTLP_INSECURE", old_insecure),
            ):
                if old_val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_val

        log_output = log_buffer.getvalue()

        # Compilation should produce SOME log output
        assert len(log_output) > 0, (
            "OBSERVABILITY GAP: Compilation produces no log output.\n"
            "Fix: Add structured logging to compilation stages with trace_id context."
        )

        # Parse each log line and validate trace_id presence and format
        trace_ids_found: list[str] = []
        for line in log_output.strip().splitlines():
            # Look for trace_id in structured log output
            # Matches both JSON and key-value structured log formats
            trace_id_match = re.search(
                r'["\']?trace_id["\']?\s*[:=]\s*["\']?([a-f0-9]{32})["\']?',
                line,
            )
            if trace_id_match:
                trace_ids_found.append(trace_id_match.group(1))

        assert len(trace_ids_found) > 0, (
            "OBSERVABILITY GAP: No trace_id found in compilation log output.\n"
            "Log output exists but does not contain trace_id fields.\n"
            "Fix: Inject OTel trace_id into structured log context during compilation.\n"
            "Expected: trace_id as 32-hex-char string in each log line.\n"
            f"Sample log output (first 500 chars): {log_output[:500]}"
        )

        # Validate all found trace_ids match 32-hex-char format
        for tid in trace_ids_found:
            assert re.match(r"^[a-f0-9]{32}$", tid), (
                f"Invalid trace_id format: '{tid}'. Expected 32 hex characters."
            )

        # All trace_ids from a single compilation should be the same
        unique_trace_ids = set(trace_ids_found)
        assert len(unique_trace_ids) == 1, (
            f"OBSERVABILITY GAP: Multiple distinct trace_ids in single compilation.\n"
            f"Found {len(unique_trace_ids)} unique trace_ids: {unique_trace_ids}\n"
            "A single compilation run should propagate one trace_id across all stages."
        )

        # Verify Dagster API is also accessible for runtime log correlation
        query = """
        query GetRuns {
            runsOrError {
                __typename
                ... on Runs {
                    results {
                        runId
                    }
                }
            }
        }
        """

        try:
            result = dagster_client._execute(query)
            assert "runsOrError" in result, (
                f"Dagster query response missing 'runsOrError' key. Got: {result}"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to query Dagster runs endpoint: {e}\n"
                "Dagster webserver must be accessible for log correlation."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-046")
    def test_observability_non_blocking(
        self,
        e2e_namespace: str,
        dagster_client: Any,
    ) -> None:
        """Validate that compilation succeeds even when OTel endpoint is unreachable.

        Demands that:
        1. Compilation completes with unreachable OTel endpoint
        2. CompiledArtifacts are valid despite observability failure
        3. Observability is non-blocking per FR-046

        Args:
            e2e_namespace: Unique namespace for test isolation.
            dagster_client: Dagster GraphQL client.
        """
        import os
        from pathlib import Path

        from floe_core.compilation.stages import compile_pipeline

        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")

        project_root = Path(__file__).parent.parent.parent
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Compile with OTel endpoint pointing to unreachable address
        # Observability failures must NOT block compilation
        original_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        try:
            os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://192.0.2.1:4317"  # RFC 5737 TEST-NET
            artifacts = compile_pipeline(spec_path, manifest_path)
        finally:
            if original_endpoint is not None:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original_endpoint
            elif "OTEL_EXPORTER_OTLP_ENDPOINT" in os.environ:
                del os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]

        # Compilation MUST succeed even with unreachable OTel endpoint
        assert artifacts is not None, (
            "BLOCKING OBSERVABILITY: Compilation failed when OTel endpoint was unreachable.\n"
            "Observability must be non-blocking per FR-046."
        )
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION, (
            "Compilation output should be valid even with unreachable OTel endpoint"
        )
        assert artifacts.metadata.product_name == "customer-360", (
            "Compilation should produce correct artifacts even without observability"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-048")
    def test_marquez_lineage_graph(
        self,
        e2e_namespace: str,
        marquez_client: httpx.Client,
        dagster_client: Any,
        compiled_artifacts: Callable[[Path], Any],
        project_root: Path,
        trigger_lineage_run: Callable[..., None],
    ) -> None:
        """Validate that Marquez contains real lineage data queryable via the lineage graph API.

        Demands that:
        1. A fresh runtime run completes for the artifact-derived namespace/job
        2. Lineage graph API returns data for that exact namespace/job
        3. Lineage response contains a 'graph' key with actual lineage data

        This test also validates port-forward stability (AC-19.3) implicitly:
        it performs multiple sequential Marquez API calls (fresh run snapshot,
        job query, lineage graph query). If the port-forward drops mid-test,
        these calls fail with clear connection errors.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client (for infrastructure check).
            compiled_artifacts: Real compiler fixture used to resolve lineage namespace.
            project_root: Repository root fixture.
            trigger_lineage_run: Callable that triggers one fresh runtime lineage run.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")
        try:
            self.check_infrastructure("marquez")
        except Exception:
            pytest.fail(
                "Marquez not accessible. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000 -n floe-test"
            )

        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)
        runtime_namespace = artifacts.observability.lineage_namespace
        runtime_job_name = artifacts.metadata.product_name

        before_run_ids = _marquez_run_id_snapshot(
            marquez_client,
            namespace=runtime_namespace,
            job_name=runtime_job_name,
        )
        trigger_lineage_run(
            expected_namespace=runtime_namespace,
            expected_job_name=runtime_job_name,
            before_run_ids=before_run_ids,
        )

        fresh_completed_runs = _fresh_completed_runs(
            marquez_client,
            namespace=runtime_namespace,
            job_name=runtime_job_name,
            before_run_ids=before_run_ids,
        )
        all_runs = _marquez_job_runs(
            marquez_client,
            namespace=runtime_namespace,
            job_name=runtime_job_name,
        )
        run_states = {_marquez_run_state(run) for run in all_runs if _marquez_run_state(run)}
        assert fresh_completed_runs, (
            "LINEAGE GAP: Lineage graph test did not create a fresh COMPLETED "
            "Marquez run before querying the graph.\n"
            f"Expected namespace/job: {runtime_namespace}/{runtime_job_name}\n"
            f"Existing run ids before trigger: {len(before_run_ids)}\n"
            f"Run states found: {sorted(run_states)}"
        )

        runtime_jobs = _marquez_namespace_jobs(
            marquez_client,
            namespace=runtime_namespace,
        )
        runtime_job_names = [job.get("name") for job in runtime_jobs]
        assert runtime_job_name in runtime_job_names, (
            "LINEAGE GAP: Fresh runtime job not found in artifact-derived namespace.\n"
            f"Expected namespace/job: {runtime_namespace}/{runtime_job_name}\n"
            f"Job names found: {runtime_job_names}"
        )

        # Query lineage for the exact artifact-derived runtime job, not a stale global job.
        lineage_response = marquez_client.get(
            "/api/v1/lineage",
            params={
                "nodeId": f"job:{runtime_namespace}:{runtime_job_name}",
                "depth": 3,
            },
        )
        assert lineage_response.status_code == 200, (
            f"Lineage graph query failed for job {runtime_job_name}: "
            f"{lineage_response.status_code} - {lineage_response.text}"
        )

        lineage_data = lineage_response.json()
        assert "graph" in lineage_data, (
            f"Lineage response missing 'graph' key: {list(lineage_data.keys())}"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-047")
    def test_trace_content_validation(
        self,
        e2e_namespace: str,
        jaeger_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Validate that trace spans contain floe-specific attributes for pipeline observability.

        Demands that:
        1. Jaeger contains traces for the 'customer-360' service
        2. Traces contain spans with floe-specific attributes
        3. Spans have attributes like floe.product_name or floe.stage

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")
        self.check_infrastructure("jaeger-query")

        # Query for traces from customer-360 service (real service name)
        service_name = "customer-360"
        response = jaeger_client.get(
            "/api/traces",
            params={
                "service": service_name,
                "limit": 10,
            },
        )
        assert response.status_code == 200, (
            f"Jaeger trace query for {service_name} failed: {response.status_code}"
        )

        response_json = response.json()
        assert "data" in response_json, "Jaeger response missing 'data' key"
        traces = response_json["data"]
        assert isinstance(traces, list), f"Traces should be a list, got: {type(traces)}"

        # Traces MUST exist for pipeline observability
        assert len(traces) > 0, (
            "TRACE GAP: No traces found for 'customer-360' service.\n"
            "OTel instrumentation is not emitting traces with pipeline attributes.\n"
            "Fix: Configure OTel SDK with service.name='customer-360' and "
            "add floe.product_name, floe.stage attributes to spans."
        )

        # Validate trace structure
        first_trace = traces[0]
        assert "traceID" in first_trace, "Trace missing traceID field"
        assert "spans" in first_trace, "Trace missing spans field"
        assert len(first_trace["spans"]) > 0, "Trace has no spans"

        first_span = first_trace["spans"][0]
        assert "spanID" in first_span, "Span missing spanID"
        assert "operationName" in first_span, "Span missing operationName"

        # Validate span tags contain pipeline attributes
        tags = first_span.get("tags", [])

        # At minimum, spans should have standard OTel attributes
        assert len(tags) > 0, (
            "Span has no tags/attributes. OTel instrumentation is not "
            "attaching pipeline metadata to spans."
        )

        # Validate tag structure
        for tag in tags:
            assert "key" in tag, "Tag missing 'key' field"
            assert "value" in tag or "vStr" in tag or "vLong" in tag, "Tag missing value field"

        # Check for domain-specific attributes across all spans in the trace
        # TODO(#144): When attribute naming migrates to floe.{domain}.* convention,
        # update these prefixes to floe.compile.*, floe.governance.*, floe.enforcement.*
        all_tag_keys: set[str] = set()
        for span in first_trace["spans"]:
            for tag in span.get("tags", []):
                all_tag_keys.add(tag.get("key", ""))

        # Production uses domain-specific prefixes, not just floe.*
        domain_attributes = [
            k
            for k in all_tag_keys
            if k.startswith(("compile.", "governance.", "enforcement.", "floe."))
        ]
        assert len(domain_attributes) > 0, (
            "TRACE GAP: No domain-specific attributes found in trace spans.\n"
            f"Tag keys found: {sorted(all_tag_keys)}\n"
            "Expected attributes with prefixes: compile.*, governance.*, enforcement.*, floe.*\n"
            "Fix: Ensure OTel spans include domain-specific attributes "
            "during compilation and execution."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("AC-5")
    @pytest.mark.requirement("AC-6")
    def test_openlineage_four_emission_points(
        self,
        e2e_namespace: str,
        marquez_client: httpx.Client,
        dagster_client: Any,
        compiled_artifacts: Callable[[Path], Any],
        project_root: Path,
        trigger_lineage_run: Callable[..., None],
    ) -> None:
        """Validate platform emits OpenLineage events at all 4 required lifecycle points.

        Triggers real compilation and then queries Marquez for events emitted
        BY the platform. Does NOT manually POST synthetic events.

        The 4 required emission points are:
        1. dbt model start (RunEvent.START for each model)
        2. dbt model complete (RunEvent.COMPLETE for each model)
        3. Pipeline start (job-level RunEvent.START)
        4. Pipeline complete (job-level RunEvent.COMPLETE)

        WILL FAIL if the platform does not emit OpenLineage events during compilation.
        This is expected until OpenLineage integration is wired.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client.
            compiled_artifacts: Real compiler fixture used to resolve lineage namespace.
            project_root: Repository root fixture.
            trigger_lineage_run: Callable that triggers one fresh runtime lineage run.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")
        try:
            self.check_infrastructure("marquez")
        except Exception:
            pytest.fail(
                "Marquez not accessible. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000 -n floe-test"
            )

        # Snapshot compilation model runs before compile_pipeline() because
        # compilation-time model jobs land in floe.compilation. The model job
        # names are resolved from artifacts after compilation, so this captures
        # the whole namespace and filters to artifact-derived names later.
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        compilation_model_namespace = "floe.compilation"
        compilation_model_run_ids_before = _marquez_namespace_run_snapshot(
            marquez_client,
            namespace=compilation_model_namespace,
        )

        artifacts = compiled_artifacts(spec_path)
        runtime_namespace = artifacts.observability.lineage_namespace
        runtime_job_name = artifacts.metadata.product_name
        model_job_names = _expected_model_job_names(artifacts)

        # Snapshot artifact-derived runtime jobs after compilation but before
        # the Dagster trigger, so runtime model evidence must come from this run.
        runtime_model_run_ids_before = _marquez_namespace_run_snapshot(
            marquez_client,
            namespace=runtime_namespace,
        )
        before_run_ids = _marquez_run_id_snapshot(
            marquez_client,
            namespace=runtime_namespace,
            job_name=runtime_job_name,
        )
        trigger_lineage_run(
            expected_namespace=runtime_namespace,
            expected_job_name=runtime_job_name,
            before_run_ids=before_run_ids,
        )

        fresh_completed_runs = _fresh_completed_runs(
            marquez_client,
            namespace=runtime_namespace,
            job_name=runtime_job_name,
            before_run_ids=before_run_ids,
        )
        all_pipeline_runs = _marquez_job_runs(
            marquez_client,
            namespace=runtime_namespace,
            job_name=runtime_job_name,
        )
        run_states = {
            _marquez_run_state(run) for run in all_pipeline_runs if _marquez_run_state(run)
        }
        assert fresh_completed_runs, (
            "EMISSION GAP: Pipeline runtime did not create a fresh COMPLETED "
            "Marquez run.\n"
            f"Expected namespace/job: {runtime_namespace}/{runtime_job_name}\n"
            f"Existing run ids before trigger: {len(before_run_ids)}\n"
            f"Run states found: {sorted(run_states)}"
        )

        fresh_runtime_model_runs = _fresh_completed_runs_for_jobs(
            marquez_client,
            namespace=runtime_namespace,
            job_names=model_job_names,
            before_run_ids_by_job=runtime_model_run_ids_before,
        )
        fresh_compilation_model_runs = _fresh_completed_runs_for_jobs(
            marquez_client,
            namespace=compilation_model_namespace,
            job_names=model_job_names,
            before_run_ids_by_job=compilation_model_run_ids_before,
        )
        fresh_model_runs = fresh_runtime_model_runs + fresh_compilation_model_runs
        fresh_model_job_names = {str(run.get("_job_name", "")) for run in fresh_model_runs}
        assert fresh_model_runs, (
            "EMISSION GAP: No fresh dbt model runs found in Marquez.\n"
            f"Expected model job names: {sorted(model_job_names)}\n"
            f"Runtime namespace checked: {runtime_namespace}\n"
            f"Compilation namespace checked: {compilation_model_namespace}\n"
            "Stale model jobs from previous runs are not accepted as evidence.\n"
            "Fix: Emit RunEvent.START and RunEvent.COMPLETE for each dbt model execution."
        )

        runtime_jobs = _marquez_namespace_jobs(
            marquez_client,
            namespace=runtime_namespace,
        )
        runtime_job_names = [job.get("name", "") for job in runtime_jobs]
        assert runtime_job_name in runtime_job_names, (
            "EMISSION GAP: No fresh pipeline-level job found in Marquez.\n"
            f"Expected namespace/job: {runtime_namespace}/{runtime_job_name}\n"
            f"Runtime job names found: {runtime_job_names}\n"
            "The fresh COMPLETED run above proves this exact job, but the jobs "
            "endpoint must also expose it for lineage graph queries."
        )

        fresh_run_ids: set[str] = set()
        for run in fresh_completed_runs:
            fresh_run_ids.update(_marquez_run_identity_candidates(run))
        fresh_model_run_ids: set[str] = set()
        for run in fresh_model_runs:
            fresh_model_run_ids.update(_marquez_run_identity_candidates(run))

        # Validate START and COMPLETE evidence for the fresh runtime run.
        # Per-model emission pairs are back-to-back synchronous, so Marquez
        # may only surface the terminal COMPLETED run state (the intermediate
        # START state is too brief to observe via the runs API). Prefer the
        # lineage events API only when its event metadata can be tied to the
        # fresh run id/namespace/job. Global event types are diagnostic only:
        # stale events from another run do not prove this runtime run emitted.
        events_response = marquez_client.get("/api/v1/events/lineage", params={"limit": 100})
        scoped_event_types: set[str] = set()
        global_event_types: set[str] = set()
        scoped_model_events: list[dict[str, Any]] = []
        if events_response.status_code == 200:
            events = events_response.json().get("events", [])
            global_event_types = {_lineage_event_type(e) for e in events if _lineage_event_type(e)}
            scoped_event_types = {
                _lineage_event_type(e)
                for e in events
                if _lineage_event_type(e)
                and _lineage_event_matches_fresh_run(
                    e,
                    namespace=runtime_namespace,
                    job_name=runtime_job_name,
                    fresh_run_ids=fresh_run_ids,
                )
            }
            scoped_model_events = [
                e
                for e in events
                if _lineage_event_matches_fresh_jobs(
                    e,
                    namespace=runtime_namespace,
                    job_names=model_job_names,
                    fresh_run_ids=fresh_model_run_ids,
                )
            ]
            runtime_model_event_run_ids: set[str] = set()
            for run in fresh_runtime_model_runs:
                runtime_model_event_run_ids.update(_marquez_run_identity_candidates(run))
            scoped_runtime_model_events = [
                e
                for e in events
                if _lineage_event_matches_fresh_jobs(
                    e,
                    namespace=runtime_namespace,
                    job_names=model_job_names,
                    fresh_run_ids=runtime_model_event_run_ids,
                )
            ]
            scoped_model_event_types = {
                _lineage_event_type(e) for e in scoped_model_events if _lineage_event_type(e)
            }
        else:
            scoped_model_event_types = set()
            scoped_runtime_model_events = []

        fresh_run_started = any(run.get("startedAt") for run in fresh_completed_runs)
        fresh_run_completed = bool(fresh_completed_runs)
        fresh_model_started = any(run.get("startedAt") for run in fresh_model_runs)
        fresh_model_completed = bool(fresh_model_runs)
        has_pipeline_start = "START" in scoped_event_types or fresh_run_started
        has_pipeline_complete = "COMPLETE" in scoped_event_types or fresh_run_completed
        has_model_start = "START" in scoped_model_event_types or fresh_model_started
        has_model_complete = "COMPLETE" in scoped_model_event_types or fresh_model_completed

        event_types_display = (
            (
                f"scoped={sorted(scoped_event_types)}, "
                f"scoped_model={sorted(scoped_model_event_types)}, "
                f"global={sorted(global_event_types)} "
                "(global types are not used as fresh-run proof)"
            )
            if events_response.status_code == 200
            else "N/A (events API unavailable)"
        )
        assert (
            has_pipeline_start and has_pipeline_complete and has_model_start and has_model_complete
        ), (
            "EMISSION GAP: Not all lifecycle events found.\n"
            f"Event types found: {event_types_display}\n"
            f"Run states found: {sorted(run_states)}\n"
            f"Fresh model jobs found: {sorted(fresh_model_job_names)}\n"
            "Expected both START and COMPLETE lifecycle events.\n"
            "Fix: Emit RunEvent.START at job begin "
            "and RunEvent.COMPLETE at job end.\n"
            "All 4 emission points per FR-041: "
            "dbt model START, dbt model COMPLETE, "
            "pipeline START, pipeline COMPLETE."
        )

        # -------------------------------------------------------------------
        # AC-5: Runtime lineage events have meaningful (non-zero) durations.
        # -------------------------------------------------------------------
        fresh_scoped_runs = fresh_completed_runs + fresh_model_runs
        assert any(_run_has_nonzero_duration(run) for run in fresh_scoped_runs), (
            "DURATION GAP: No fresh Marquez runs have non-zero duration "
            "(startedAt → endedAt).\n"
            "Runtime lineage events MUST have meaningful durations proving "
            "they were emitted at actual execution boundaries, "
            "not back-to-back during compilation.\n"
            f"Fresh pipeline runs inspected: {len(fresh_completed_runs)}\n"
            f"Fresh model runs inspected: {len(fresh_model_runs)}\n"
            "Fix: Ensure LineageResource emits START at execution begin "
            "and COMPLETE at execution end with real timestamps."
        )

        # -------------------------------------------------------------------
        # AC-6: Per-model events carry a parent facet linking to the
        #       parent Dagster asset run.
        # -------------------------------------------------------------------
        assert any(
            _parent_run_id_from_run(run)
            or _parent_run_id_from_marquez_run_facets(marquez_client, run)
            for run in fresh_runtime_model_runs
        ) or any(_parent_run_id_from_event(event) for event in scoped_runtime_model_events), (
            "PARENT FACET GAP: No fresh Marquez model runs contain a valid 'parent' "
            "facet with a runId.\n"
            "Per-model dbt lineage events MUST include the OpenLineage parent facet "
            "linking to the parent Dagster asset run.\n"
            f"Fresh runtime model runs inspected: {len(fresh_runtime_model_runs)}\n"
            f"Fresh runtime model events inspected: {len(scoped_runtime_model_events)}\n"
            f"Fresh model jobs inspected: {sorted(fresh_model_job_names)}\n"
            "Stale model runs from previous executions are not accepted as evidence.\n"
            "Fix: Ensure LineageResource passes parent_run_id "
            "when extracting per-model lineage events."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-040")
    def test_compilation_emits_otel_spans(
        self,
        e2e_namespace: str,
        jaeger_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Validate that compile_pipeline() emits OTel spans queryable in Jaeger.

        This is the TRIGGER test -- other observability tests depend on compilation
        actually emitting OTel spans. Runs compile_pipeline() for customer-360 and
        immediately queries Jaeger for traces from the 'customer-360' service.

        WILL FAIL if compilation does not emit OTel spans -- this is expected until
        OTel SDK instrumentation is wired into compilation stages.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        import time
        from pathlib import Path

        from floe_core.compilation.stages import compile_pipeline

        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster")
        self.check_infrastructure("jaeger-query")

        project_root = Path(__file__).parent.parent.parent
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Record timestamp before compilation (microseconds for Jaeger API)
        start_time_us = int(time.time() * 1_000_000)

        # Ensure this compilation emits spans under customer-360 service
        from floe_core.telemetry.initialization import (
            ensure_telemetry_initialized,
            reset_telemetry,
        )

        # Save OTel env vars before mutation for cleanup
        old_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        old_insecure = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE")
        old_service = os.environ.get("OTEL_SERVICE_NAME")

        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ServiceEndpoint("otel-collector-grpc").url
        os.environ["OTEL_EXPORTER_OTLP_INSECURE"] = "true"
        os.environ["OTEL_SERVICE_NAME"] = "customer-360"
        try:
            reset_telemetry()
            ensure_telemetry_initialized()

            # Run real compilation -- should emit OTel spans
            artifacts = compile_pipeline(spec_path, manifest_path)
            assert artifacts is not None, "Compilation must succeed"
            assert artifacts.metadata.product_name == "customer-360", (
                "Compiled wrong product -- expected customer-360"
            )

            # Flush spans before polling Jaeger — BatchSpanProcessor has
            # a 5000ms schedule delay that would otherwise cause timeouts.
            from opentelemetry import trace as otel_trace

            provider = otel_trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                provider.force_flush(timeout_millis=5000)

            # Poll for traces to appear in Jaeger
            def check_jaeger_traces() -> bool:
                """Check if Jaeger has traces from customer-360 service."""
                end_time_us = int(time.time() * 1_000_000)
                resp = jaeger_client.get(
                    "/api/traces",
                    params={
                        "service": "customer-360",
                        "start": start_time_us,
                        "end": end_time_us,
                        "limit": 20,
                    },
                )
                if resp.status_code != 200:
                    return False
                traces = resp.json().get("data", [])
                return len(traces) > 0

            from testing.fixtures.polling import wait_for_condition

            traces_available = wait_for_condition(
                check_jaeger_traces,
                timeout=30.0,
                interval=1.0,
                description="Jaeger traces to appear",
            )

            # Query Jaeger for traces from 'customer-360' service within the last 60 seconds
            end_time_us = int(time.time() * 1_000_000)
            traces_response = jaeger_client.get(
                "/api/traces",
                params={
                    "service": "customer-360",
                    "start": start_time_us,
                    "end": end_time_us,
                    "limit": 20,
                },
            )
            assert traces_response.status_code == 200 and traces_available, (
                f"Jaeger traces query failed: {traces_response.status_code}"
            )

            traces_json = traces_response.json()
            assert "data" in traces_json, "Jaeger response missing 'data' key"
            traces = traces_json["data"]

            assert len(traces) > 0, (
                "COMPILATION OTEL GAP: No traces emitted by compile_pipeline().\n"
                "Compilation completed successfully but no OTel spans were recorded "
                "in Jaeger.\n"
                f"Time window: {start_time_us} to {end_time_us}\n"
                "Fix: Wire OTel SDK into compile_pipeline() stages to emit spans.\n"
                "Each compilation stage (LOAD, VALIDATE, RESOLVE, ENFORCE, COMPILE, "
                "GENERATE) should emit a span under the 'customer-360' service."
            )

            # Validate that spans match compilation stages
            all_operation_names: list[str] = []
            for trace in traces:
                for span in trace.get("spans", []):
                    op_name = span.get("operationName", "")
                    if op_name:
                        all_operation_names.append(op_name)

            assert len(all_operation_names) > 0, (
                "Traces found but all spans have empty operation names."
            )

            # Check for compilation stage spans
            compilation_keywords = [
                "compile",
                "load",
                "validate",
                "resolve",
                "enforce",
                "generate",
            ]
            has_compilation_span = any(
                any(kw in op.lower() for kw in compilation_keywords) for op in all_operation_names
            )

            assert has_compilation_span, (
                "COMPILATION OTEL GAP: Traces exist but no compilation stage spans "
                "found.\n"
                f"Operation names found: {all_operation_names}\n"
                "Expected spans matching compilation stages: "
                "LOAD, VALIDATE, RESOLVE, ENFORCE, COMPILE, GENERATE.\n"
                "Fix: Name OTel spans after compilation stages in compile_pipeline()."
            )
        finally:
            # Restore OTel env vars to avoid leaking to other tests
            reset_telemetry()
            for key, old_val in (
                ("OTEL_EXPORTER_OTLP_ENDPOINT", old_endpoint),
                ("OTEL_EXPORTER_OTLP_INSECURE", old_insecure),
                ("OTEL_SERVICE_NAME", old_service),
            ):
                if old_val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_val
