"""RED tests for Customer 360 Marquez lineage validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from customer360_observability import (
    EvidenceResult,
    EvidenceStatus,
    ObservabilityContext,
    _marquez_graph_node_count,
    query_marquez_lineage,
)

MARQUEZ_URL = "http://marquez.test"
NAMESPACE = "customer-360"
JOB_NAME = "customer-360"
RUN_ID = "customer-360-run-123"
TABLE = "mart_customer_360"
DATASET_NAME = "customer_360.main.mart_customer_360"
UPSTREAM_DATASET_NAME = "customer_360.main.stg_customers"
DOWNSTREAM_DATASET_NAME = "customer_360.main.customer_360_export"
DATASET_NODE_ID = f"dataset:{NAMESPACE}:{DATASET_NAME}"
UPSTREAM_DATASET_NODE_ID = f"dataset:{NAMESPACE}:{UPSTREAM_DATASET_NAME}"
DOWNSTREAM_DATASET_NODE_ID = f"dataset:{NAMESPACE}:{DOWNSTREAM_DATASET_NAME}"
JOB_NODE_ID = f"job:{NAMESPACE}:{DATASET_NAME}"
FRESH_EPOCH_SECONDS = 1_700_000_000.0


@dataclass(frozen=True)
class _FakeResponse:
    payload: dict[str, Any]
    status_code: int = 200

    def json(self) -> dict[str, Any]:
        """Return the configured JSON payload."""
        return self.payload

    def raise_for_status(self) -> None:
        """Raise for non-2xx responses like httpx.Response."""
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeMarquezClient:
    def __init__(self, routes: dict[str, _FakeResponse]) -> None:
        self._routes = routes
        self.requests: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResponse:
        """Record GET requests and return route fixtures by path."""
        self.requests.append((url, params))
        path = urlparse(url).path
        return self._routes.get(path, _FakeResponse({}, status_code=404))

    @property
    def requested_paths(self) -> list[str]:
        return [urlparse(url).path for url, _params in self.requests]

    def requested_path_with_params(self, path: str, expected: dict[str, str]) -> bool:
        """Return whether a path was requested with the expected query params."""
        for url, params in self.requests:
            parsed = urlparse(url)
            if parsed.path != path:
                continue
            query_params = {
                key: values[-1] for key, values in parse_qs(parsed.query).items() if values
            }
            if params:
                query_params.update({key: str(value) for key, value in params.items()})
            if all(query_params.get(key) == value for key, value in expected.items()):
                return True
        return False


def _context() -> ObservabilityContext:
    return ObservabilityContext(
        product=NAMESPACE,
        run_id=RUN_ID,
        table=TABLE,
        freshness_window_seconds=300.0,
        now_epoch_seconds=FRESH_EPOCH_SECONDS + 10.0,
    )


def _product_run() -> dict[str, Any]:
    return {
        "id": RUN_ID,
        "runId": RUN_ID,
        "state": "COMPLETED",
        "startedAt": FRESH_EPOCH_SECONDS,
        "endedAt": FRESH_EPOCH_SECONDS,
        "job": {"namespace": NAMESPACE, "name": JOB_NAME},
        "product": NAMESPACE,
    }


def _model_run() -> dict[str, Any]:
    return {
        "id": "customer-360-model-run-123",
        "runId": "customer-360-model-run-123",
        "state": "COMPLETED",
        "startedAt": FRESH_EPOCH_SECONDS,
        "endedAt": FRESH_EPOCH_SECONDS,
        "job": {"namespace": NAMESPACE, "name": DATASET_NAME},
        "product": NAMESPACE,
        "table": TABLE,
        "parent_run_id": RUN_ID,
    }


def _routes(
    *,
    namespace_status: int = 200,
    product_runs_status: int = 200,
    jobs: dict[str, Any] | None = None,
    datasets: dict[str, Any] | None = None,
    lineage: dict[str, Any] | None = None,
) -> dict[str, _FakeResponse]:
    return {
        f"/api/v1/namespaces/{NAMESPACE}": _FakeResponse(
            {"name": NAMESPACE},
            status_code=namespace_status,
        ),
        f"/api/v1/namespaces/{NAMESPACE}/jobs/{JOB_NAME}/runs": _FakeResponse(
            {"runs": [_product_run()]},
            status_code=product_runs_status,
        ),
        f"/api/v1/namespaces/{NAMESPACE}/jobs": _FakeResponse(
            jobs if jobs is not None else {"jobs": [{"name": JOB_NAME}, {"name": DATASET_NAME}]}
        ),
        f"/api/v1/namespaces/{NAMESPACE}/jobs/{DATASET_NAME}/runs": _FakeResponse(
            {"runs": [_model_run()]}
        ),
        f"/api/v1/namespaces/{NAMESPACE}/datasets": _FakeResponse(
            datasets
            if datasets is not None
            else {
                "datasets": [
                    {
                        "namespace": NAMESPACE,
                        "name": DATASET_NAME,
                        "type": "ICEBERG",
                    }
                ]
            }
        ),
        "/api/v1/lineage": _FakeResponse(
            lineage
            if lineage is not None
            else {
                "depth": 3,
                "graph": {
                    "nodes": [
                        {"id": UPSTREAM_DATASET_NODE_ID, "type": "DATASET"},
                        {"id": DATASET_NODE_ID, "type": "DATASET"},
                        {"id": JOB_NODE_ID, "type": "JOB"},
                    ],
                    "edges": [
                        {"origin": UPSTREAM_DATASET_NODE_ID, "destination": JOB_NODE_ID},
                        {"origin": JOB_NODE_ID, "destination": DATASET_NODE_ID},
                    ],
                },
            }
        ),
    }


def _query(client: _FakeMarquezClient) -> EvidenceResult:
    return query_marquez_lineage(
        marquez_url=MARQUEZ_URL,
        namespace=NAMESPACE,
        job_name=JOB_NAME,
        context=_context(),
        client=client,
    )


@pytest.mark.requirement("alpha-demo")
def test_marquez_lineage_queries_api_surfaces_for_customer360_dataset() -> None:
    """Lineage proof queries Marquez API resources, not service root or UI."""
    client = _FakeMarquezClient(_routes())

    result = _query(client)

    assert result.status is EvidenceStatus.PASS
    assert "/" not in client.requested_paths
    assert "/api/v1" not in client.requested_paths
    assert f"/api/v1/namespaces/{NAMESPACE}" in client.requested_paths
    assert f"/api/v1/namespaces/{NAMESPACE}/jobs/{JOB_NAME}/runs" in client.requested_paths
    assert f"/api/v1/namespaces/{NAMESPACE}/jobs" in client.requested_paths
    assert f"/api/v1/namespaces/{NAMESPACE}/datasets" in client.requested_paths
    assert client.requested_path_with_params(
        "/api/v1/lineage",
        {"nodeId": DATASET_NODE_ID, "depth": "3"},
    )


@pytest.mark.requirement("alpha-demo")
@pytest.mark.parametrize(
    ("namespace_status", "product_runs_status"),
    [(404, 200), (200, 404)],
)
def test_marquez_missing_namespace_or_job_context_is_wrong_context(
    namespace_status: int,
    product_runs_status: int,
) -> None:
    """Reachable Marquez with missing expected context is not a backend outage."""
    client = _FakeMarquezClient(
        _routes(
            namespace_status=namespace_status,
            product_runs_status=product_runs_status,
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.WRONG_CONTEXT
    assert result.diagnostics["expected_context"] == f"{NAMESPACE} / {RUN_ID}"


@pytest.mark.requirement("alpha-demo")
def test_marquez_product_runs_without_dataset_or_graph_detail_are_contract_gap() -> None:
    """Product/model runs without dataset and graph proof are a contract gap."""
    client = _FakeMarquezClient(
        _routes(
            datasets={"datasets": []},
            lineage={"depth": 3, "graph": {"nodes": [], "edges": []}},
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.CONTRACT_GAP
    assert result.url == f"{MARQUEZ_URL}/api/v1/namespaces/{NAMESPACE}/datasets"


@pytest.mark.requirement("alpha-demo")
def test_marquez_product_runs_with_shallow_lineage_graph_are_contract_gap() -> None:
    """A single-node graph does not prove materialized model/table depth."""
    client = _FakeMarquezClient(
        _routes(
            lineage={
                "graph": {
                    "nodes": [{"id": DATASET_NODE_ID, "type": "DATASET"}],
                    "edges": [],
                },
            },
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.CONTRACT_GAP
    assert result.diagnostics["contract_gap"] == "marquez_lineage_graph_detail"
    assert result.url == f"{MARQUEZ_URL}/api/v1/lineage"


@pytest.mark.requirement("alpha-demo")
def test_marquez_product_runs_with_disconnected_lineage_graph_are_contract_gap() -> None:
    """Unconnected graph nodes do not prove materialized table/model lineage."""
    client = _FakeMarquezClient(
        _routes(
            lineage={
                "graph": {
                    "nodes": [
                        {"id": DATASET_NODE_ID, "type": "DATASET"},
                        {"id": f"dataset:{NAMESPACE}:unrelated.table", "type": "DATASET"},
                    ],
                },
            },
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.CONTRACT_GAP
    assert result.diagnostics["contract_gap"] == "marquez_lineage_graph_detail"


@pytest.mark.requirement("alpha-demo")
def test_marquez_product_runs_with_ghost_lineage_edge_are_contract_gap() -> None:
    """Edges must connect returned graph nodes, not arbitrary identifiers."""
    client = _FakeMarquezClient(
        _routes(
            lineage={
                "graph": {
                    "nodes": [
                        {"id": DATASET_NODE_ID, "type": "DATASET"},
                        {"id": f"dataset:{NAMESPACE}:unrelated.table", "type": "DATASET"},
                    ],
                    "edges": [{"origin": "not-a-returned-node", "destination": DATASET_NODE_ID}],
                },
            },
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.CONTRACT_GAP
    assert result.diagnostics["contract_gap"] == "marquez_lineage_graph_detail"


@pytest.mark.requirement("alpha-demo")
def test_marquez_graph_node_count_ignores_mapping_keys_without_nodes() -> None:
    """Malformed graph mappings without nodes do not count dict keys as nodes."""
    node_count = _marquez_graph_node_count(
        {
            "graph": {
                "edges": [
                    {"origin": UPSTREAM_DATASET_NODE_ID, "destination": JOB_NODE_ID},
                    {"origin": JOB_NODE_ID, "destination": DATASET_NODE_ID},
                ]
            }
        }
    )

    assert node_count == 0


@pytest.mark.requirement("alpha-demo")
def test_marquez_product_runs_with_target_job_only_lineage_graph_are_contract_gap() -> None:
    """Target-to-job alone does not prove upstream model/table lineage depth."""
    client = _FakeMarquezClient(
        _routes(
            lineage={
                "graph": {
                    "nodes": [
                        {"id": DATASET_NODE_ID, "type": "DATASET"},
                        {"id": JOB_NODE_ID, "type": "JOB"},
                    ],
                    "edges": [{"origin": JOB_NODE_ID, "destination": DATASET_NODE_ID}],
                },
            },
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.CONTRACT_GAP
    assert result.diagnostics["contract_gap"] == "marquez_lineage_graph_detail"


@pytest.mark.requirement("alpha-demo")
def test_marquez_product_runs_with_downstream_only_lineage_graph_are_contract_gap() -> None:
    """Downstream lineage from the target table is not upstream model/table proof."""
    client = _FakeMarquezClient(
        _routes(
            lineage={
                "graph": {
                    "nodes": [
                        {"id": DATASET_NODE_ID, "type": "DATASET"},
                        {"id": JOB_NODE_ID, "type": "JOB"},
                        {"id": DOWNSTREAM_DATASET_NODE_ID, "type": "DATASET"},
                    ],
                    "edges": [
                        {"origin": DATASET_NODE_ID, "destination": JOB_NODE_ID},
                        {"origin": JOB_NODE_ID, "destination": DOWNSTREAM_DATASET_NODE_ID},
                    ],
                },
            },
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.CONTRACT_GAP
    assert result.diagnostics["contract_gap"] == "marquez_lineage_graph_detail"


@pytest.mark.requirement("alpha-demo")
def test_marquez_dataset_evidence_from_wrong_namespace_is_wrong_context() -> None:
    """Dataset evidence must come from the expected Marquez namespace."""
    client = _FakeMarquezClient(
        _routes(
            datasets={
                "datasets": [
                    {
                        "namespace": "wrong-namespace",
                        "name": DATASET_NAME,
                    }
                ]
            }
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.WRONG_CONTEXT
    assert result.diagnostics["expected_context"] == f"{NAMESPACE} / {RUN_ID} / {TABLE}"
    assert result.url == f"{MARQUEZ_URL}/api/v1/namespaces/{NAMESPACE}/datasets"


@pytest.mark.requirement("alpha-demo")
def test_marquez_wrong_namespace_dataset_does_not_drive_lineage_query() -> None:
    """Wrong-namespace dataset records are classified before graph API calls."""
    client = _FakeMarquezClient(
        {
            **_routes(
                datasets={
                    "datasets": [
                        {
                            "namespace": "wrong-namespace",
                            "name": DATASET_NAME,
                        }
                    ]
                }
            ),
            "/api/v1/lineage": _FakeResponse({}, status_code=500),
        }
    )

    result = _query(client)

    assert result.status is EvidenceStatus.WRONG_CONTEXT
    assert "/api/v1/lineage" not in client.requested_paths


@pytest.mark.requirement("alpha-demo")
def test_marquez_graph_evidence_from_wrong_namespace_is_wrong_context() -> None:
    """Graph nodes must be in the expected Marquez namespace."""
    wrong_dataset_node = f"dataset:wrong-namespace:{DATASET_NAME}"
    wrong_job_node = f"job:wrong-namespace:{DATASET_NAME}"
    client = _FakeMarquezClient(
        _routes(
            lineage={
                "graph": {
                    "nodes": [
                        {"id": f"dataset:wrong-namespace:{UPSTREAM_DATASET_NAME}"},
                        {"id": wrong_dataset_node},
                        {"id": wrong_job_node},
                    ],
                    "edges": [
                        {
                            "origin": f"dataset:wrong-namespace:{UPSTREAM_DATASET_NAME}",
                            "destination": wrong_job_node,
                        },
                        {"origin": wrong_job_node, "destination": wrong_dataset_node},
                    ],
                },
            },
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.WRONG_CONTEXT
    assert result.diagnostics["expected_context"] == f"{NAMESPACE} / {RUN_ID} / {TABLE}"
    assert result.url == f"{MARQUEZ_URL}/api/v1/lineage"


@pytest.mark.requirement("alpha-demo")
def test_marquez_model_run_api_failure_reports_model_run_url() -> None:
    """Model/table run API failures point operators at the failed endpoint."""
    client = _FakeMarquezClient(
        {
            **_routes(),
            f"/api/v1/namespaces/{NAMESPACE}/jobs/{DATASET_NAME}/runs": _FakeResponse(
                {},
                status_code=500,
            ),
        }
    )

    result = _query(client)

    assert result.status is EvidenceStatus.BACKEND_UNREACHABLE
    assert result.url == f"{MARQUEZ_URL}/api/v1/namespaces/{NAMESPACE}/jobs/{DATASET_NAME}/runs"


@pytest.mark.requirement("alpha-demo")
def test_marquez_product_runs_without_model_table_runs_are_contract_gap() -> None:
    """Product runs without materialized model/table runs are an emission gap."""
    client = _FakeMarquezClient(_routes(jobs={"jobs": [{"name": JOB_NAME}]}))

    result = _query(client)

    assert result.status is EvidenceStatus.CONTRACT_GAP
    assert result.diagnostics["contract_gap"] == "marquez_model_table_run_detail"


@pytest.mark.requirement("alpha-demo")
def test_marquez_lineage_pass_includes_product_model_dataset_and_graph_diagnostics() -> None:
    """Full Customer 360 lineage proof reports every evidence family."""
    client = _FakeMarquezClient(_routes())

    result = _query(client)

    assert result.status is EvidenceStatus.PASS
    assert result.diagnostics["product_run_count"] == "1"
    assert result.diagnostics["model_table_count"] == "1"
    assert result.diagnostics["dataset_count"] == "1"
    assert result.diagnostics["lineage_graph_depth"] == "2"
    assert result.diagnostics["lineage_graph_requested_depth"] == "3"
    assert result.diagnostics["lineage_graph_count"] == "1"


@pytest.mark.requirement("alpha-demo")
def test_marquez_lineage_accepts_list_shaped_graph_response() -> None:
    """Marquez may return lineage graph as a node list rather than nodes/edges."""
    client = _FakeMarquezClient(
        _routes(
            lineage={
                "graph": [
                    {
                        "id": UPSTREAM_DATASET_NODE_ID,
                        "type": "DATASET",
                        "outEdges": [
                            {"origin": UPSTREAM_DATASET_NODE_ID, "destination": JOB_NODE_ID}
                        ],
                    },
                    {
                        "id": JOB_NODE_ID,
                        "type": "JOB",
                        "inEdges": [
                            {"origin": UPSTREAM_DATASET_NODE_ID, "destination": JOB_NODE_ID}
                        ],
                        "outEdges": [{"origin": JOB_NODE_ID, "destination": DATASET_NODE_ID}],
                    },
                    {
                        "id": DATASET_NODE_ID,
                        "type": "DATASET",
                        "inEdges": [{"origin": JOB_NODE_ID, "destination": DATASET_NODE_ID}],
                    },
                ]
            }
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.PASS
    assert result.diagnostics["lineage_graph_depth"] == "2"


@pytest.mark.requirement("alpha-demo")
def test_marquez_lineage_rejects_disconnected_list_shaped_graph_response() -> None:
    """List-shaped Marquez graph nodes still need inEdges/outEdges connectivity."""
    client = _FakeMarquezClient(
        _routes(
            lineage={
                "graph": [
                    {"id": UPSTREAM_DATASET_NODE_ID, "type": "DATASET"},
                    {"id": JOB_NODE_ID, "type": "JOB"},
                    {"id": DATASET_NODE_ID, "type": "DATASET"},
                ]
            }
        )
    )

    result = _query(client)

    assert result.status is EvidenceStatus.CONTRACT_GAP
    assert result.diagnostics["contract_gap"] == "marquez_lineage_graph_detail"


@pytest.mark.requirement("alpha-demo")
def test_marquez_lineage_dataset_api_failure_reports_dataset_url() -> None:
    """Dataset API failures point operators at the failed endpoint."""
    client = _FakeMarquezClient(
        {
            **_routes(),
            f"/api/v1/namespaces/{NAMESPACE}/datasets": _FakeResponse(
                {},
                status_code=500,
            ),
        }
    )

    result = _query(client)

    assert result.status is EvidenceStatus.BACKEND_UNREACHABLE
    assert result.url == f"{MARQUEZ_URL}/api/v1/namespaces/{NAMESPACE}/datasets"


@pytest.mark.requirement("alpha-demo")
def test_marquez_lineage_graph_api_failure_reports_lineage_url() -> None:
    """Lineage graph API failures point operators at the failed endpoint."""
    client = _FakeMarquezClient(
        {
            **_routes(),
            "/api/v1/lineage": _FakeResponse(
                {},
                status_code=500,
            ),
        }
    )

    result = _query(client)

    assert result.status is EvidenceStatus.BACKEND_UNREACHABLE
    assert result.url == f"{MARQUEZ_URL}/api/v1/lineage"
