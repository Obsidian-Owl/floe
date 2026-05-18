"""Contract tests for Customer 360 backend observability helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import httpx

from testing.ci.customer360_observability import (
    EvidenceStatus,
    ObservabilityContext,
    build_marquez_graph_node_id,
    build_marquez_graph_query_url,
    extract_grafana_panel_queries,
    query_grafana_dashboard_panels,
    query_loki_logs,
    query_marquez_lineage,
    query_prometheus_instant_metrics,
    query_prometheus_metrics,
)

JsonObject = dict[str, Any]
HttpParams = Mapping[str, object] | None


class _FakeResponse:
    def __init__(
        self,
        payload: JsonObject | str,
        *,
        status_code: int = 200,
        error: Exception | None = None,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> JsonObject:
        if isinstance(self._payload, dict):
            return self._payload
        raise ValueError("response is not JSON")


class _FakeClient:
    def __init__(self, responses: Mapping[str, JsonObject | str | _FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, HttpParams]] = []

    def get(self, url: str, params: HttpParams = None) -> _FakeResponse:
        self.requests.append((url, params))
        response = self.responses.get(url)
        if isinstance(response, _FakeResponse):
            return response
        if response is not None:
            return _FakeResponse(response)
        raise AssertionError(f"No fake response configured for {url}")


def _context() -> ObservabilityContext:
    return ObservabilityContext(
        product="customer-360",
        run_id="run-123",
        table="mart_customer_360",
        freshness_window_seconds=300,
        now_epoch_seconds=1_700_000_000.0,
    )


def test_evidence_status_covers_all_alpha_failure_classes() -> None:
    """Backend helpers can represent every alpha evidence class explicitly."""
    assert {status.value for status in EvidenceStatus} >= {
        "pass",
        "product_failure",
        "platform_service_failure",
        "backend_unreachable",
        "no_fresh_evidence",
        "wrong_context",
        "stale_evidence",
        "dashboard_datasource_drift",
        "contract_gap",
    }


def test_marquez_helper_uses_api_endpoints_and_graph_node_helpers() -> None:
    """Marquez proof comes from namespace/job/run/dataset/lineage APIs, not root UI."""
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
            "http://marquez/api/v1/namespaces/customer-360/datasets": {
                "datasets": [{"name": "mart_customer_360"}]
            },
            (
                "http://marquez/api/v1/namespaces/customer-360/jobs/"
                "model.customer_360.mart_customer_360/runs"
            ): {
                "runs": [
                    {
                        "id": "model-run-1",
                        "state": "COMPLETED",
                        "endedAt": "2023-11-14T22:12:40Z",
                        "facets": {"parent": {"run": {"runId": "run-123"}}},
                    }
                ]
            },
            "http://marquez/api/v1/lineage": {"graph": []},
        }
    )

    node_id = build_marquez_graph_node_id(
        node_type="dataset",
        namespace="customer-360",
        name="mart_customer_360",
    )
    result = query_marquez_lineage(
        marquez_url="http://marquez",
        namespace="customer-360",
        job_name="customer-360",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert node_id == "dataset:customer-360:mart_customer_360"
    assert build_marquez_graph_query_url("http://marquez") == "http://marquez/api/v1/lineage"
    assert result.status is EvidenceStatus.PASS
    requested_urls = {url for url, _params in client.requests}
    assert "http://marquez/" not in requested_urls
    assert "http://marquez/api/v1/namespaces/customer-360/datasets" in requested_urls
    assert (
        "http://marquez/api/v1/lineage",
        {"nodeId": node_id, "depth": "2"},
    ) in client.requests


def test_loki_helper_checks_ready_and_query_range_without_root_ui() -> None:
    """Loki root 404 is irrelevant when /ready and query_range pass."""
    client = _FakeClient(
        {
            "http://loki/ready": "ready\n",
            "http://loki/loki/api/v1/query_range": {
                "data": {
                    "result": [
                        {
                            "stream": {"service_name": "customer-360"},
                            "values": [
                                [
                                    "1699999950000000000",
                                    (
                                        '{"product":"customer-360","run_id":"run-123",'
                                        '"message":"runtime completed"}'
                                    ),
                                ]
                            ],
                        }
                    ]
                }
            },
        }
    )

    result = query_loki_logs(
        loki_url="http://loki",
        product="customer-360",
        run_id="run-123",
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert result.status is EvidenceStatus.PASS
    assert ("http://loki/ready", None) in client.requests
    assert all(url != "http://loki/" for url, _params in client.requests)


def test_prometheus_helpers_support_instant_and_range_queries() -> None:
    """Prometheus proof can be checked through instant or range query APIs."""
    instant_client = _FakeClient(
        {
            "http://prom/api/v1/query": {
                "data": {
                    "result": [
                        {
                            "metric": {
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
        }
    )
    range_client = _FakeClient(
        {
            "http://prom/api/v1/query_range": {
                "data": {
                    "result": [
                        {
                            "metric": {
                                "floe_product_name": "customer-360",
                                "floe_status": "success",
                                "floe_plugin_name": "dagster",
                                "floe_asset_key": "mart_customer_360",
                            },
                            "values": [[1_699_999_950.0, "1"]],
                        }
                    ]
                }
            }
        }
    )

    instant = query_prometheus_instant_metrics(
        prometheus_url="http://prom",
        product="customer-360",
        status="success",
        plugin="dagster",
        context=_context(),
        client=cast(httpx.Client, instant_client),
    )
    ranged = query_prometheus_metrics(
        prometheus_url="http://prom",
        product="customer-360",
        status="success",
        plugin="dagster",
        context=_context(),
        client=cast(httpx.Client, range_client),
    )

    assert instant.status is EvidenceStatus.PASS
    assert ranged.status is EvidenceStatus.PASS
    assert instant.url == "http://prom/api/v1/query"
    assert ranged.url == "http://prom/api/v1/query_range"


def test_grafana_panel_queries_classify_datasource_drift() -> None:
    """Empty panel results through Grafana are datasource drift when backend queries pass."""
    dashboard = {
        "dashboard": {
            "panels": [
                {
                    "title": "Customer 360 materializations",
                    "datasource": {"uid": "grafana-prometheus"},
                    "targets": [
                        {
                            "datasource": {"uid": "grafana-prometheus"},
                            "expr": (
                                "floe_asset_materializations_total"
                                '{floe_product_name="customer-360"}'
                            ),
                        }
                    ],
                }
            ]
        }
    }
    client = _FakeClient(
        {
            "http://grafana/api/datasources/uid/grafana-prometheus": {
                "uid": "grafana-prometheus",
                "type": "prometheus",
                "url": "http://prometheus",
            },
            "http://grafana/api/ds/query": {"results": {"A": {"frames": []}}},
        }
    )

    panel_queries = extract_grafana_panel_queries(dashboard)
    result = query_grafana_dashboard_panels(
        grafana_url="http://grafana",
        dashboard=dashboard,
        backend_results={"prometheus": True},
        context=_context(),
        client=cast(httpx.Client, client),
    )

    assert panel_queries == (
        {
            "panel_title": "Customer 360 materializations",
            "datasource_uid": "grafana-prometheus",
            "query": 'floe_asset_materializations_total{floe_product_name="customer-360"}',
            "backend": "prometheus",
        },
    )
    assert result.status is EvidenceStatus.DASHBOARD_DATASOURCE_DRIFT
    assert result.diagnostics["datasource_uid"] == "grafana-prometheus"
