"""Regression tests for E2E observability trigger helpers."""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping
from typing import Any, cast
from unittest.mock import MagicMock, patch

import httpx
import pytest

from testing.ci.customer360_observability import (
    Customer360ObservabilityConfig,
    EvidenceRecord,
    EvidenceResult,
    EvidenceStatus,
    ObservabilityContext,
    classify_evidence_records,
    query_loki_logs,
    query_marquez_lineage,
    query_prometheus_metrics,
    query_trace_backend,
    validate_customer360_observability,
)

e2e_conftest = cast(Any, importlib.import_module("tests.e2e.conftest"))


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


JsonObject = dict[str, Any]
HttpParams = Mapping[str, object] | None


class _FakeResponse:
    def __init__(
        self,
        payload: JsonObject,
        *,
        status_code: int = 200,
        error: Exception | None = None,
        json_error: Exception | None = None,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self._error = error
        self._json_error = json_error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error
        return None

    def json(self) -> JsonObject:
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _FakeClient:
    def __init__(
        self,
        payload: JsonObject | Mapping[str, JsonObject | _FakeResponse],
    ) -> None:
        self.payload = payload
        self.requests: list[tuple[str, HttpParams]] = []

    def get(
        self,
        url: str,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResponse:
        self.requests.append((url, params))
        if _is_url_payload_map(self.payload) and url in self.payload:
            payload = self.payload[url]
            if isinstance(payload, _FakeResponse):
                return payload
            return _FakeResponse(payload)
        if isinstance(self.payload, dict):
            return _FakeResponse(self.payload)
        raise AssertionError(f"No fake response configured for {url}")


def _is_url_payload_map(
    payload: JsonObject | Mapping[str, JsonObject | _FakeResponse],
) -> bool:
    return all(isinstance(value, (dict, _FakeResponse)) for value in payload.values())


def _pass_result(backend: str, payload: Mapping[str, Any]) -> EvidenceResult:
    return EvidenceResult(
        backend=backend,
        status=EvidenceStatus.PASS,
        query=backend,
        message=f"{backend} pass",
        records=(
            EvidenceRecord(
                payload=payload,
                timestamp_epoch_seconds=1_699_999_950.0,
            ),
        ),
    )


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


def test_customer360_observability_config_uses_in_cluster_service_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live E2E jobs must not fall back to localhost-only demo ports."""
    for key in (
        "FLOE_DEMO_DAGSTER_URL",
        "FLOE_DEMO_JAEGER_URL",
        "FLOE_DEMO_LOKI_URL",
        "FLOE_DEMO_PROMETHEUS_URL",
        "FLOE_DEMO_MARQUEZ_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("DAGSTER_URL", "http://floe-platform-dagster-webserver:3000")
    monkeypatch.setenv("JAEGER_URL", "http://floe-platform-jaeger-query:16686")
    monkeypatch.setenv("LOKI_HOST", "floe-platform-loki")
    monkeypatch.setenv("PROMETHEUS_HOST", "floe-platform-prometheus")
    monkeypatch.setenv("MARQUEZ_HOST", "floe-platform-marquez")

    config = Customer360ObservabilityConfig.from_env()

    assert config.dagster_url == "http://floe-platform-dagster-webserver:3000"
    assert config.jaeger_url == "http://floe-platform-jaeger-query:16686"
    assert config.loki_url == "http://floe-platform-loki:3100"
    assert config.prometheus_url == "http://floe-platform-prometheus:9090"
    assert config.marquez_url == "http://floe-platform-marquez:5000"


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
    """Trace helper queries Jaeger with actual OTel product/run tags."""
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
                                {"key": "floe.product.name", "value": "customer-360"},
                                {"key": "floe.run.id", "value": "run-123"},
                                {"key": "floe.table.name", "value": "mart_customer_360"},
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
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.PASS
    params = client.requests[0][1]
    assert isinstance(params, Mapping)
    tag_value = params["tags"]
    assert isinstance(tag_value, str)
    tags = json.loads(tag_value)
    assert tags == {"floe.product.name": "customer-360", "floe.run.id": "run-123"}
    assert client.requests == [
        (
            "http://jaeger/api/traces",
            {
                "service": "customer-360",
                "limit": "50",
                "tags": '{"floe.product.name":"customer-360","floe.run.id":"run-123"}',
            },
        )
    ]


def test_customer360_trace_helper_accepts_run_level_records_across_assets() -> None:
    """Trace proof should classify all traces for a run, not one table-only trace."""
    client = _FakeClient(
        {
            "data": [
                {
                    "traceID": "trace-dbt",
                    "spans": [
                        {
                            "operationName": "floe.orchestrator.dagster.asset.customer-360",
                            "startTime": 1_699_999_950_000_000,
                            "tags": [
                                {"key": "floe.product.name", "value": "customer-360"},
                                {"key": "floe.run.id", "value": "run-123"},
                                {"key": "floe.plugin.name", "value": "dagster"},
                                {"key": "floe.table.name", "value": "mart_customer_360"},
                            ],
                        }
                    ],
                },
                {
                    "traceID": "trace-ingestion",
                    "spans": [
                        {
                            "operationName": (
                                "floe.orchestrator.dagster.asset.run_ingestion_raw_customers"
                            ),
                            "startTime": 1_699_999_951_000_000,
                            "tags": [
                                {"key": "floe.product.name", "value": "customer-360"},
                                {"key": "floe.run.id", "value": "run-123"},
                                {"key": "floe.stage", "value": "ingestion"},
                                {"key": "floe.table.name", "value": "bronze.raw_customers"},
                            ],
                        }
                    ],
                },
            ]
        }
    )
    context = ObservabilityContext(
        product="customer-360",
        run_id="run-123",
        freshness_window_seconds=300,
        now_epoch_seconds=1_700_000_000.0,
    )

    result = query_trace_backend(
        jaeger_url="http://jaeger",
        service="customer-360",
        context=context,
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.PASS
    assert result.evidence_count == 2


def test_customer360_validation_polls_until_backends_have_full_runtime_evidence() -> None:
    """The live gate waits for collector/backend ingestion after Dagster run success."""
    dagster_result = _pass_result("dagster", {"product": "customer-360", "runId": "run-123"})
    trace_partial = _pass_result(
        "traces",
        {
            "traceID": "trace-ingestion",
            "spans": [
                {
                    "operationName": "floe.orchestrator.dagster.asset.run_ingestion_raw_customers",
                    "tags": [
                        {"key": "floe.product.name", "value": "customer-360"},
                        {"key": "floe.run.id", "value": "run-123"},
                        {"key": "floe.stage", "value": "ingestion"},
                        {"key": "floe.plugin.name", "value": "dlt"},
                    ],
                }
            ],
        },
    )
    trace_complete = _pass_result(
        "traces",
        {
            "traceID": "trace-transform",
            "spans": [
                {
                    "operationName": "floe.customer-360.run",
                    "tags": [
                        {"key": "floe.product.name", "value": "customer-360"},
                        {"key": "floe.run.id", "value": "run-123"},
                    ],
                },
                {"operationName": "floe.orchestrator.dagster.asset.customer-360"},
                {"operationName": "floe.dbt.customer-360.models mart_customer_360"},
                {"operationName": "ingestion dlt raw_customers"},
                {"operationName": "iceberg catalog storage export"},
            ],
        },
    )
    logs_missing = EvidenceResult(
        backend="logs",
        status=EvidenceStatus.NO_FRESH_EVIDENCE,
        query="logs",
        message="not indexed yet",
    )
    logs_complete = _pass_result(
        "logs",
        {"message": '{"product":"customer-360","run_id":"run-123"}'},
    )
    metrics_result = _pass_result("metrics", {"metric": {"floe_product_name": "customer-360"}})
    lineage_result = _pass_result("lineage", {"facets": {"trace_id": "trace-transform"}})

    config = Customer360ObservabilityConfig(
        run_id="run-123",
        evidence_poll_timeout_seconds=1,
        evidence_poll_interval_seconds=0.1,
    )

    with (
        patch(
            "testing.ci.customer360_observability.query_dagster_run",
            return_value=dagster_result,
        ),
        patch(
            "testing.ci.customer360_observability.query_trace_backend",
            side_effect=[trace_partial, trace_complete],
        ) as trace_query,
        patch(
            "testing.ci.customer360_observability.query_loki_logs",
            side_effect=[logs_missing, logs_complete],
        ),
        patch(
            "testing.ci.customer360_observability.query_prometheus_metrics",
            return_value=metrics_result,
        ),
        patch(
            "testing.ci.customer360_observability.query_marquez_lineage",
            return_value=lineage_result,
        ),
        patch("testing.fixtures.polling.time.sleep") as sleep,
    ):
        result = validate_customer360_observability(config)

    assert result.ok
    assert trace_query.call_count == 2
    sleep.assert_called_once()
    assert result.evidence["observability.traces.dbt_model_spans"] == "true"
    assert result.evidence["observability.traces.catalog_storage_iceberg_spans"] == "true"


def test_customer360_loki_helper_queries_logs_by_product_and_run() -> None:
    """Loki helper queries structured logs without live services."""
    client = _FakeClient(
        {
            "http://loki/ready": {},
            "http://loki/loki/api/v1/query_range": {
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
            },
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
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.PASS
    assert client.requests[0] == ("http://loki/ready", None)
    assert client.requests[1][0] == "http://loki/loki/api/v1/query_range"
    params = client.requests[1][1]
    assert isinstance(params, Mapping)
    assert params["query"] == '{service_name=~".+"} |= "customer-360" |= "run-123"'


def test_customer360_prometheus_helper_queries_metrics_by_product_status_and_plugin() -> None:
    """Prometheus helper uses actual runtime metric names and bounded labels."""
    client = _FakeClient(
        {
            "data": {
                "result": [
                    {
                        "metric": {
                            "__name__": "floe_asset_materializations_total",
                            "floe_product_name": "customer-360",
                            "floe_status": "success",
                            "floe_plugin_name": "dagster",
                            "floe_asset_key": "mart_customer_360",
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
        table="mart_customer_360",
        freshness_window_seconds=300,
        now_epoch_seconds=1_700_000_000.0,
    )

    result = query_prometheus_metrics(
        prometheus_url="http://prometheus",
        product="customer-360",
        status="success",
        plugin="dagster",
        context=context,
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.PASS
    assert client.requests == [
        (
            "http://prometheus/api/v1/query_range",
            {
                "query": (
                    'floe_asset_materializations_total{floe_product_name="customer-360",'
                    'floe_status="success",floe_plugin_name=~"dagster"}'
                ),
                "start": "1699999700.000",
                "end": "1700000000.000",
                "step": "15s",
            },
        )
    ]


def test_customer360_prometheus_helper_matches_plugin_regex() -> None:
    """Metric classification uses the same regex plugin semantics as Prometheus."""
    client = _FakeClient(
        {
            "data": {
                "result": [
                    {
                        "metric": {
                            "__name__": "floe_asset_materializations_total",
                            "floe_product_name": "customer-360",
                            "floe_status": "success",
                            "floe_plugin_name": "dagster",
                            "floe_asset_key": "mart_customer_360",
                        },
                        "value": [1_699_999_950.0, "1"],
                    }
                ]
            }
        }
    )

    result = query_prometheus_metrics(
        prometheus_url="http://prometheus",
        product="customer-360",
        status="success",
        plugin="dagster|dbt",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.PASS


def test_customer360_prometheus_helper_rejects_invalid_plugin_regex_without_crashing() -> None:
    """Invalid plugin regexes classify as wrong context instead of crashing."""
    client = _FakeClient(
        {
            "data": {
                "result": [
                    {
                        "metric": {
                            "__name__": "floe_asset_materializations_total",
                            "floe_product_name": "customer-360",
                            "floe_status": "success",
                            "floe_plugin_name": "dagster",
                            "floe_asset_key": "mart_customer_360",
                        },
                        "value": [1_699_999_950.0, "1"],
                    }
                ]
            }
        }
    )

    result = query_prometheus_metrics(
        prometheus_url="http://prometheus",
        product="customer-360",
        status="success",
        plugin="[",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.WRONG_CONTEXT


def test_customer360_marquez_helper_queries_lineage_by_namespace_job_and_run() -> None:
    """Marquez helper accepts product-run and model/table evidence as separate records."""
    client = _FakeClient(
        {
            "http://marquez/api/v1/namespaces/customer-360/jobs/customer-360/runs": {
                "runs": [
                    {
                        "id": "run-123",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:30Z",
                        "facets": {"product": {"name": "customer-360"}},
                    }
                ]
            },
            "http://marquez/api/v1/namespaces/customer-360/jobs": {
                "jobs": [
                    {"name": "customer-360"},
                    {"name": "model.customer_360.mart_customer_360"},
                ]
            },
            (
                "http://marquez/api/v1/namespaces/customer-360/jobs/"
                "model.customer_360.mart_customer_360/runs"
            ): {
                "runs": [
                    {
                        "id": "model-run-1",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:31Z",
                        "endedAt": "2023-11-14T22:12:40Z",
                        "facets": {
                            "parent": {
                                "run": {"runId": "run-123"},
                                "job": {
                                    "namespace": "customer-360",
                                    "name": "customer-360",
                                },
                            }
                        },
                    }
                ]
            },
        }
    )

    result = query_marquez_lineage(
        marquez_url="http://marquez",
        namespace="customer-360",
        job_name="customer-360",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.PASS
    assert client.requests == [
        (
            "http://marquez/api/v1/namespaces/customer-360/jobs/customer-360/runs",
            None,
        ),
        ("http://marquez/api/v1/namespaces/customer-360/jobs", None),
        ("http://marquez/api/v1/namespaces/customer-360/datasets", None),
        (
            "http://marquez/api/v1/lineage",
            {
                "nodeId": "dataset:customer-360:mart_customer_360",
                "depth": "2",
            },
        ),
        (
            (
                "http://marquez/api/v1/namespaces/customer-360/jobs/"
                "model.customer_360.mart_customer_360/runs"
            ),
            None,
        ),
    ]


def test_customer360_marquez_helper_rejects_namespace_only_model_jobs() -> None:
    """Namespace job existence alone is not fresh model/table lineage evidence."""
    client = _FakeClient(
        {
            "http://marquez/api/v1/namespaces/customer-360/jobs/customer-360/runs": {
                "runs": [
                    {
                        "id": "run-123",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:30Z",
                        "facets": {"product": {"name": "customer-360"}},
                    }
                ]
            },
            "http://marquez/api/v1/namespaces/customer-360/jobs": {
                "jobs": [{"name": "mart_customer_360"}]
            },
            "http://marquez/api/v1/namespaces/customer-360/jobs/mart_customer_360/runs": {
                "runs": []
            },
        }
    )

    result = query_marquez_lineage(
        marquez_url="http://marquez",
        namespace="customer-360",
        job_name="customer-360",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.NO_FRESH_EVIDENCE
    assert "model/table" in result.message


def test_customer360_marquez_helper_uses_run_facets_for_parent_link() -> None:
    """Model runs without inline facets can prove lineage via Marquez run facets."""
    client = _FakeClient(
        {
            "http://marquez/api/v1/namespaces/customer-360/jobs/customer-360/runs": {
                "runs": [
                    {
                        "id": "run-123",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:30Z",
                        "facets": {"product": {"name": "customer-360"}},
                    }
                ]
            },
            "http://marquez/api/v1/namespaces/customer-360/jobs": {
                "jobs": [{"name": "model.customer_360.mart_customer_360"}]
            },
            (
                "http://marquez/api/v1/namespaces/customer-360/jobs/"
                "model.customer_360.mart_customer_360/runs"
            ): {
                "runs": [
                    {
                        "id": "model-run-1",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:31Z",
                        "endedAt": "2023-11-14T22:12:40Z",
                    }
                ]
            },
            "http://marquez/api/v1/runs/model-run-1/facets": {
                "facets": {
                    "parent": {
                        "run": {"runId": "run-123"},
                        "job": {"namespace": "customer-360", "name": "customer-360"},
                    }
                }
            },
        }
    )

    result = query_marquez_lineage(
        marquez_url="http://marquez",
        namespace="customer-360",
        job_name="customer-360",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.PASS
    assert (
        "http://marquez/api/v1/runs/model-run-1/facets",
        {"type": "run"},
    ) in client.requests


def test_customer360_marquez_helper_treats_optional_facet_failure_as_wrong_context() -> None:
    """Optional run facet lookup failures do not make reachable Marquez unreachable."""
    facets_url = "http://marquez/api/v1/runs/model-run-1/facets"
    client = _FakeClient(
        {
            "http://marquez/api/v1/namespaces/customer-360/jobs/customer-360/runs": {
                "runs": [
                    {
                        "id": "run-123",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:30Z",
                        "facets": {"product": {"name": "customer-360"}},
                    }
                ]
            },
            "http://marquez/api/v1/namespaces/customer-360/jobs": {
                "jobs": [{"name": "model.customer_360.mart_customer_360"}]
            },
            (
                "http://marquez/api/v1/namespaces/customer-360/jobs/"
                "model.customer_360.mart_customer_360/runs"
            ): {
                "runs": [
                    {
                        "id": "model-run-1",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:31Z",
                        "endedAt": "2023-11-14T22:12:40Z",
                    }
                ]
            },
            facets_url: _FakeResponse(
                {},
                status_code=404,
                error=httpx.HTTPStatusError(
                    "not found",
                    request=httpx.Request("GET", facets_url),
                    response=httpx.Response(404),
                ),
            ),
        }
    )

    result = query_marquez_lineage(
        marquez_url="http://marquez",
        namespace="customer-360",
        job_name="customer-360",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.WRONG_CONTEXT


def test_customer360_marquez_helper_treats_malformed_optional_facets_as_wrong_context() -> None:
    """Malformed optional run facet payloads do not hide reachable Marquez evidence."""
    facets_url = "http://marquez/api/v1/runs/model-run-1/facets"
    client = _FakeClient(
        {
            "http://marquez/api/v1/namespaces/customer-360/jobs/customer-360/runs": {
                "runs": [
                    {
                        "id": "run-123",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:30Z",
                        "facets": {"product": {"name": "customer-360"}},
                    }
                ]
            },
            "http://marquez/api/v1/namespaces/customer-360/jobs": {
                "jobs": [{"name": "model.customer_360.mart_customer_360"}]
            },
            (
                "http://marquez/api/v1/namespaces/customer-360/jobs/"
                "model.customer_360.mart_customer_360/runs"
            ): {
                "runs": [
                    {
                        "id": "model-run-1",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:31Z",
                        "endedAt": "2023-11-14T22:12:40Z",
                    }
                ]
            },
            facets_url: _FakeResponse({}, json_error=ValueError("malformed json")),
        }
    )

    result = query_marquez_lineage(
        marquez_url="http://marquez",
        namespace="customer-360",
        job_name="customer-360",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.WRONG_CONTEXT


def test_customer360_marquez_helper_rejects_stale_model_run_parent_evidence() -> None:
    """Model/table lineage must be fresh even when it has the right parent run."""
    client = _FakeClient(
        {
            "http://marquez/api/v1/namespaces/customer-360/jobs/customer-360/runs": {
                "runs": [
                    {
                        "id": "run-123",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T22:12:30Z",
                        "facets": {"product": {"name": "customer-360"}},
                    }
                ]
            },
            "http://marquez/api/v1/namespaces/customer-360/jobs": {
                "jobs": [{"name": "model.customer_360.mart_customer_360"}]
            },
            (
                "http://marquez/api/v1/namespaces/customer-360/jobs/"
                "model.customer_360.mart_customer_360/runs"
            ): {
                "runs": [
                    {
                        "id": "model-run-1",
                        "state": "COMPLETED",
                        "startedAt": "2023-11-14T21:55:00Z",
                        "endedAt": "2023-11-14T21:56:00Z",
                        "facets": {"parent": {"run": {"runId": "run-123"}}},
                    }
                ]
            },
        }
    )

    result = query_marquez_lineage(
        marquez_url="http://marquez",
        namespace="customer-360",
        job_name="customer-360",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.STALE_EVIDENCE
