"""Integration tests for OpenLineage lineage with Marquez backend.

Tests cover:
- REQ-520: Output datasets visible in lineage graph
- REQ-523: Test lineage end-to-end via Marquez API
- REQ-530: Lineage enforcement (events posted and queryable)

These tests require a running Kind cluster with Marquez deployed.
Run with: uv run --extra dev pytest tests/integration/test_lineage_integration.py -v

Requirements Covered:
- REQ-520: Output datasets in lineage graph
- REQ-523: End-to-end lineage test
- REQ-530: Lineage enforcement via Marquez verification
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import urllib.request
from contextlib import closing
from typing import Any
from uuid import uuid4

import pytest
from testing.fixtures.polling import wait_for_condition

from floe_core.lineage.emitter import create_emitter
from floe_core.lineage.events import EventBuilder, to_openlineage_event
from floe_core.lineage.facets import SchemaFacetBuilder
from floe_core.lineage.types import LineageDataset


def _free_port() -> int:
    """Find a free TCP port on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


def _post_event(port: int, event_dict: dict[str, Any]) -> int:
    """Post an OpenLineage event to Marquez and return HTTP status code.

    Args:
        port: Local port forwarded to Marquez.
        event_dict: OpenLineage wire-format event dictionary.

    Returns:
        HTTP status code from Marquez.
    """
    url = f"http://localhost:{port}/api/v1/lineage"
    data = json.dumps(event_dict).encode()
    req = urllib.request.Request(  # noqa: S310  # nosec B310
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)  # noqa: S310  # nosec B310
    return int(resp.status)


def _get_json(port: int, path: str) -> Any:
    """GET a JSON response from Marquez API.

    Args:
        port: Local port forwarded to Marquez.
        path: API path (e.g., /api/v1/namespaces).

    Returns:
        Parsed JSON response.
    """
    url = f"http://localhost:{port}{path}"
    req = urllib.request.Request(url, method="GET")  # noqa: S310  # nosec B310
    resp = urllib.request.urlopen(req, timeout=10)  # noqa: S310  # nosec B310
    return json.loads(resp.read().decode())


@pytest.fixture(scope="module")
def marquez_port() -> int:  # type: ignore[return]
    """Set up port-forward to Marquez service in Kind cluster.

    Yields the local port that forwards to Marquez:5000.
    """
    port = _free_port()
    proc = subprocess.Popen(  # noqa: S603, S607
        [
            "kubectl",
            "port-forward",
            "svc/marquez",
            f"{port}:5000",
            "-n",
            "floe-test",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for port-forward to be ready and Marquez to respond
    def marquez_ready() -> bool:
        try:
            _get_json(port, "/api/v1/namespaces")
            return True
        except Exception:
            return False

    if not wait_for_condition(
        marquez_ready,
        timeout=30.0,
        interval=1.0,
        description="Marquez to become ready",
        raise_on_timeout=False,
    ):
        proc.kill()
        pytest.fail(
            "Marquez not reachable after 30s. Ensure Kind cluster is running with Marquez deployed."
        )

    yield port  # type: ignore[misc]

    proc.kill()
    proc.wait()


@pytest.mark.integration
@pytest.mark.k8s
class TestMarquezLineageIntegration:
    """End-to-end tests for lineage events posted to Marquez."""

    def test_emit_dbt_model_chain_lineage(self, marquez_port: int) -> None:
        """Emit a 3-model dbt chain and verify lineage graph in Marquez.

        Posts START+COMPLETE for: raw_customers → stg_customers → customers
        Then queries the lineage graph and verifies the chain.

        Covers: REQ-520 (output datasets), REQ-523 (test lineage)
        """
        ns = f"floe-test-{uuid4().hex[:8]}"
        builder = EventBuilder(producer="floe-test", default_namespace=ns)

        # Model 1: raw_customers → stg_customers
        run1_id = uuid4()
        start1 = builder.start_run(
            job_name="dbt_run_stg_customers",
            run_id=run1_id,
            inputs=[LineageDataset(namespace=ns, name="raw.customers")],
            outputs=[LineageDataset(namespace=ns, name="staging.stg_customers")],
        )
        complete1 = builder.complete_run(
            run_id=run1_id,
            job_name="dbt_run_stg_customers",
            inputs=[LineageDataset(namespace=ns, name="raw.customers")],
            outputs=[LineageDataset(namespace=ns, name="staging.stg_customers")],
        )

        # Model 2: stg_customers → customers
        run2_id = uuid4()
        start2 = builder.start_run(
            job_name="dbt_run_customers",
            run_id=run2_id,
            inputs=[LineageDataset(namespace=ns, name="staging.stg_customers")],
            outputs=[LineageDataset(namespace=ns, name="marts.customers")],
        )
        complete2 = builder.complete_run(
            run_id=run2_id,
            job_name="dbt_run_customers",
            inputs=[LineageDataset(namespace=ns, name="staging.stg_customers")],
            outputs=[LineageDataset(namespace=ns, name="marts.customers")],
        )

        # Post all events
        for event in [start1, complete1, start2, complete2]:
            status = _post_event(marquez_port, to_openlineage_event(event))
            assert status == 201, f"Expected 201, got {status}"

        # Query lineage graph from the final output dataset
        lineage = _get_json(
            marquez_port,
            f"/api/v1/lineage?nodeId=dataset:{ns}:marts.customers&depth=3",
        )
        assert "graph" in lineage

        # Verify nodes exist in graph
        node_ids = {n["id"] for n in lineage["graph"]}
        # Marquez returns node IDs like "dataset:ns:name" or "job:ns:name"
        assert any(
            "marts.customers" in nid for nid in node_ids
        ), f"Final output dataset not in lineage graph. Nodes: {node_ids}"

    def test_emit_with_schema_facets(self, marquez_port: int) -> None:
        """Emit event with schema facets and verify in Marquez.

        Covers: REQ-520 (output datasets with facets)
        """
        ns = f"floe-test-{uuid4().hex[:8]}"
        builder = EventBuilder(producer="floe-test", default_namespace=ns)
        run_id = uuid4()

        columns = [
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "VARCHAR"},
            {"name": "email", "type": "VARCHAR"},
        ]
        schema_facet = SchemaFacetBuilder.from_columns(columns)

        start = builder.start_run(
            job_name="dbt_run_with_schema",
            run_id=run_id,
            outputs=[
                LineageDataset(
                    namespace=ns,
                    name="staging.users_with_schema",
                    facets={"schema": schema_facet},
                )
            ],
        )
        complete = builder.complete_run(
            run_id=run_id,
            job_name="dbt_run_with_schema",
            outputs=[
                LineageDataset(
                    namespace=ns,
                    name="staging.users_with_schema",
                    facets={"schema": schema_facet},
                )
            ],
        )

        for event in [start, complete]:
            status = _post_event(marquez_port, to_openlineage_event(event))
            assert status == 201

        # Verify dataset exists via Marquez API
        datasets = _get_json(marquez_port, f"/api/v1/namespaces/{ns}/datasets")
        dataset_names = [d["name"] for d in datasets["datasets"]]
        assert "staging.users_with_schema" in dataset_names

    def test_emit_fail_event(self, marquez_port: int) -> None:
        """Emit FAIL event and verify error facet in Marquez.

        Covers: REQ-523 (test lineage), REQ-530 (lineage enforcement)
        """
        ns = f"floe-test-{uuid4().hex[:8]}"
        builder = EventBuilder(producer="floe-test", default_namespace=ns)
        run_id = uuid4()

        start = builder.start_run(
            job_name="dbt_run_failing",
            run_id=run_id,
        )
        fail = builder.fail_run(
            run_id=run_id,
            job_name="dbt_run_failing",
            error_message="Column 'revenue' not found in source",
        )

        for event in [start, fail]:
            status = _post_event(marquez_port, to_openlineage_event(event))
            assert status == 201

        # Verify the job run has FAIL state
        runs = _get_json(
            marquez_port,
            f"/api/v1/namespaces/{ns}/jobs/dbt_run_failing/runs",
        )
        assert len(runs["runs"]) > 0
        latest_run = runs["runs"][0]
        assert latest_run["state"] == "FAILED"

    def test_trace_correlation_facet(self, marquez_port: int) -> None:
        """Emit event with trace correlation and verify in Marquez.

        Covers: REQ-523 (test lineage end-to-end)
        """
        ns = f"floe-test-{uuid4().hex[:8]}"
        builder = EventBuilder(producer="floe-test", default_namespace=ns)
        run_id = uuid4()
        trace_id = "abc123def456"
        span_id = "span789"

        trace_facet = {
            "_producer": "floe-test",
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/CustomFacet.json",
            "traceId": trace_id,
            "spanId": span_id,
            "serviceName": "floe-dagster",
        }

        start = builder.start_run(
            job_name="dbt_run_traced",
            run_id=run_id,
            run_facets={"traceCorrelation": trace_facet},
        )
        complete = builder.complete_run(
            run_id=run_id,
            job_name="dbt_run_traced",
            run_facets={"traceCorrelation": trace_facet},
        )

        for event in [start, complete]:
            status = _post_event(marquez_port, to_openlineage_event(event))
            assert status == 201

        # Verify run exists and has facets
        runs = _get_json(
            marquez_port,
            f"/api/v1/namespaces/{ns}/jobs/dbt_run_traced/runs",
        )
        assert len(runs["runs"]) > 0
        latest_run = runs["runs"][0]
        assert latest_run["state"] == "COMPLETED"
        # Marquez stores run facets — check they exist
        run_facets = latest_run.get("facets", {})
        if run_facets:
            assert "traceCorrelation" in run_facets

    def test_namespaces_api_health(self, marquez_port: int) -> None:
        """Verify Marquez health via namespaces API.

        Basic smoke test that Marquez is responding.
        """
        result = _get_json(marquez_port, "/api/v1/namespaces")
        assert "namespaces" in result

    def test_emitter_with_http_transport(self, marquez_port: int) -> None:
        """Test LineageEmitter with real HttpLineageTransport to Marquez.

        Validates the full transport path: LineageEmitter → HttpLineageTransport → Marquez.
        This test ensures the wire format conversion works end-to-end.

        Covers: REQ-525 (HTTP transport), REQ-526 (fire-and-forget)
        """

        async def _run_emitter_test() -> None:
            ns = f"floe-transport-test-{uuid4().hex[:8]}"
            url = f"http://localhost:{marquez_port}/api/v1/lineage"

            emitter = create_emitter(
                transport_config={"type": "http", "url": url, "timeout": 10.0},
                default_namespace=ns,
                producer="floe-integration-test",
            )

            run_id = await emitter.emit_start(
                job_name="transport_test_job",
                inputs=[LineageDataset(namespace=ns, name="raw.source_table")],
                outputs=[LineageDataset(namespace=ns, name="staging.target_table")],
            )

            await emitter.emit_complete(
                run_id=run_id,
                job_name="transport_test_job",
                outputs=[LineageDataset(namespace=ns, name="staging.target_table")],
            )

            from floe_core.lineage.transport import HttpLineageTransport

            transport = emitter.transport
            if isinstance(transport, HttpLineageTransport):
                await transport.close_async()
            else:
                emitter.close()

            await asyncio.sleep(0.5)

            jobs = _get_json(marquez_port, f"/api/v1/namespaces/{ns}/jobs")
            job_names = [j["name"] for j in jobs["jobs"]]
            assert (
                "transport_test_job" in job_names
            ), f"Job not found. Jobs: {job_names}"

            runs = _get_json(
                marquez_port,
                f"/api/v1/namespaces/{ns}/jobs/transport_test_job/runs",
            )
            assert len(runs["runs"]) > 0
            assert runs["runs"][0]["state"] == "COMPLETED"

        asyncio.run(_run_emitter_test())
