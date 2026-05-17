"""Regression tests for E2E observability trigger helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from testing.ci.customer360_observability import (
    EvidenceRecord,
    EvidenceStatus,
    ObservabilityContext,
    classify_evidence_records,
    query_loki_logs,
    query_marquez_lineage,
    query_prometheus_metrics,
    query_trace_backend,
)
from tests.e2e import conftest as e2e_conftest


def test_trigger_lineage_run_waits_for_marquez_after_launch_timeout() -> None:
    """Dagster launch timeouts may still enqueue a run; wait for lineage proof."""
    marquez_client = MagicMock()
    before_run_ids = {"existing-run"}

    with (
        patch.object(
            e2e_conftest,
            "_discover_repo_for_asset",
            return_value=("repo", "location", ["stg_crm_customers"], "__ASSET_JOB"),
        ),
        patch.object(e2e_conftest.httpx, "post", side_effect=httpx.ReadTimeout("slow")),
        patch.object(
            e2e_conftest,
            "_wait_for_fresh_completed_marquez_run",
            return_value=True,
        ) as wait_for_fresh_run,
    ):
        e2e_conftest._trigger_lineage_run(
            lambda *_args, **_kwargs: None,
            marquez_client,
            expected_namespace="customer-360",
            expected_job_name="customer-360",
            before_run_ids=before_run_ids,
        )

    wait_for_fresh_run.assert_called_once_with(
        marquez_client,
        namespace="customer-360",
        job_name="customer-360",
        before_run_ids=before_run_ids,
        timeout=e2e_conftest._DAGSTER_LAUNCH_TIMEOUT_MARQUEZ_GRACE_SECONDS,
    )


def _context() -> ObservabilityContext:
    return ObservabilityContext(
        product="customer-360",
        run_id="run-123",
        table="mart_customer_360",
        freshness_window_seconds=300,
        now_epoch_seconds=1_700_000_000.0,
    )


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests: list[tuple[str, dict[str, object] | None]] = []

    def get(
        self,
        url: str,
        params: dict[str, object] | None = None,
    ) -> _FakeResponse:
        self.requests.append((url, params))
        return _FakeResponse(self.payload)


def test_customer360_observability_classifies_backend_unreachable() -> None:
    """Transport failures are infrastructure/backend failures, not product failures."""
    result = classify_evidence_records(
        backend="jaeger",
        query="service=customer-360",
        context=_context(),
        records=None,
        backend_error="connection refused",
    )

    assert result.status is EvidenceStatus.BACKEND_UNREACHABLE
    assert not result.ok
    assert result.backend == "jaeger"
    assert "connection refused" in result.message


def test_customer360_observability_classifies_reachable_backend_with_no_fresh_evidence() -> None:
    """Reachable empty backends report missing evidence, not backend failure."""
    result = classify_evidence_records(
        backend="loki",
        query='{product="customer-360"}',
        context=_context(),
        records=[],
    )

    assert result.status is EvidenceStatus.NO_FRESH_EVIDENCE
    assert result.evidence_count == 0
    assert "no evidence" in result.message.lower()


def test_customer360_observability_classifies_stale_evidence() -> None:
    """Matching evidence older than the freshness window is stale."""
    result = classify_evidence_records(
        backend="prometheus",
        query='floe_product_run_status{product="customer-360"}',
        context=_context(),
        records=[
            EvidenceRecord(
                payload={
                    "product": "customer-360",
                    "run_id": "run-123",
                    "table": "mart_customer_360",
                    "status": "success",
                },
                timestamp_epoch_seconds=1_699_999_000.0,
            )
        ],
    )

    assert result.status is EvidenceStatus.STALE_EVIDENCE
    assert result.evidence_count == 1
    assert "stale" in result.message.lower()


def test_customer360_observability_classifies_wrong_context_evidence() -> None:
    """Evidence for another product/run/table is a context mismatch."""
    result = classify_evidence_records(
        backend="marquez",
        query="/api/v1/namespaces/customer-360/jobs/customer-360/runs",
        context=_context(),
        records=[
            EvidenceRecord(
                payload={
                    "product": "iot-telemetry",
                    "run_id": "run-999",
                    "table": "mart_iot_telemetry",
                    "status": "success",
                },
                timestamp_epoch_seconds=1_699_999_950.0,
            )
        ],
    )

    assert result.status is EvidenceStatus.WRONG_CONTEXT
    assert result.evidence_count == 1
    assert "customer-360" in result.message
    assert "run-123" in result.message
    assert "mart_customer_360" in result.message


@pytest.mark.parametrize("status", ["FAILURE", "failed", "ERROR", "canceled"])
def test_customer360_observability_classifies_product_execution_failure(status: str) -> None:
    """Failure records for the requested run are product failures."""
    result = classify_evidence_records(
        backend="dagster",
        query="runOrError(runId: run-123)",
        context=_context(),
        records=[
            EvidenceRecord(
                payload={
                    "product": "customer-360",
                    "runId": "run-123",
                    "table": "mart_customer_360",
                    "status": status,
                },
                timestamp_epoch_seconds=1_699_999_950.0,
            )
        ],
    )

    assert result.status is EvidenceStatus.PRODUCT_FAILURE
    assert result.evidence_count == 1
    assert "product execution failed" in result.message.lower()


def test_customer360_trace_helper_queries_jaeger_by_service_product_and_run() -> None:
    """Trace helper queries Jaeger and classifies exact run/table context."""
    client = _FakeClient(
        {
            "data": [
                {
                    "traceID": "trace-1",
                    "spans": [
                        {
                            "operationName": "customer-360 run root",
                            "startTime": 1_699_999_950_000_000,
                            "tags": [
                                {"key": "product", "value": "customer-360"},
                                {"key": "dagster.run_id", "value": "run-123"},
                                {"key": "table", "value": "mart_customer_360"},
                            ],
                        }
                    ],
                }
            ]
        }
    )

    result = query_trace_backend(
        jaeger_url="http://jaeger",
        service="customer-360",
        context=_context(),
        client=client,  # type: ignore[arg-type]
    )

    assert result.status is EvidenceStatus.PASS
    assert client.requests == [
        ("http://jaeger/api/traces", {"service": "customer-360", "limit": "50"})
    ]


def test_customer360_loki_helper_queries_logs_by_product_and_run() -> None:
    """Loki helper queries structured logs without live services."""
    client = _FakeClient(
        {
            "data": {
                "result": [
                    {
                        "stream": {"service_name": "customer-360"},
                        "values": [
                            [
                                "1699999950000000000",
                                '{"product":"customer-360","run_id":"run-123"}',
                            ]
                        ],
                    }
                ]
            }
        }
    )
    context = ObservabilityContext(
        product="customer-360",
        run_id="run-123",
        freshness_window_seconds=300,
        now_epoch_seconds=1_700_000_000.0,
    )

    result = query_loki_logs(
        loki_url="http://loki",
        product="customer-360",
        run_id="run-123",
        context=context,
        client=client,  # type: ignore[arg-type]
    )

    assert result.status is EvidenceStatus.PASS
    assert client.requests[0][0] == "http://loki/loki/api/v1/query_range"
    assert 'customer-360" |= "run-123' in str(client.requests[0][1])


def test_customer360_prometheus_helper_queries_metrics_by_product_status_and_plugin() -> None:
    """Prometheus helper queries product/status/plugin labels."""
    client = _FakeClient(
        {
            "data": {
                "result": [
                    {
                        "metric": {
                            "product": "customer-360",
                            "run_id": "run-123",
                            "status": "success",
                            "plugin": "dagster",
                        },
                        "value": [1_699_999_950.0, "1"],
                    }
                ]
            }
        }
    )
    context = ObservabilityContext(
        product="customer-360",
        run_id="run-123",
        freshness_window_seconds=300,
        now_epoch_seconds=1_700_000_000.0,
    )

    result = query_prometheus_metrics(
        prometheus_url="http://prometheus",
        product="customer-360",
        status="success",
        plugin="dagster",
        context=context,
        client=client,  # type: ignore[arg-type]
    )

    assert result.status is EvidenceStatus.PASS
    assert client.requests == [
        (
            "http://prometheus/api/v1/query",
            {
                "query": (
                    'floe_product_run_status{product="customer-360",'
                    'status="success",plugin=~"dagster"}'
                )
            },
        )
    ]


def test_customer360_marquez_helper_queries_lineage_by_namespace_job_and_run() -> None:
    """Marquez helper queries namespace/job runs and classifies the run context."""
    client = _FakeClient(
        {
            "runs": [
                {
                    "id": "run-123",
                    "state": "COMPLETED",
                    "startedAt": "2023-11-14T22:12:30Z",
                    "outputs": [{"name": "mart_customer_360"}],
                    "facets": {"product": {"name": "customer-360"}},
                }
            ]
        }
    )

    result = query_marquez_lineage(
        marquez_url="http://marquez",
        namespace="customer-360",
        job_name="customer-360",
        context=_context(),
        client=client,  # type: ignore[arg-type]
    )

    assert result.status is EvidenceStatus.PASS
    assert client.requests == [
        (
            "http://marquez/api/v1/namespaces/customer-360/jobs/customer-360/runs",
            None,
        )
    ]
