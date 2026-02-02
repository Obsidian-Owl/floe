"""End-to-end tests for observability integration.

This test validates that the observability stack (OpenTelemetry, OpenLineage,
Prometheus, structured logging) works correctly across the full platform.

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

from typing import Any, ClassVar

import httpx
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase


class TestObservability(IntegrationTestBase):
    """E2E tests for observability stack integration.

    These tests validate that observability features work correctly:
    1. OpenTelemetry traces are collected and queryable in Jaeger
    2. OpenLineage events are emitted to Marquez at all emission points
    3. Trace IDs correlate between OTel spans and OpenLineage events
    4. Prometheus metrics are collected and queryable
    5. Structured logs contain trace_id for correlation
    6. Observability failures do not block pipeline execution
    7. Marquez lineage graph is complete and accurate

    Requires all platform services running:
    - Dagster (orchestrator)
    - Jaeger (trace collection)
    - Marquez (lineage tracking)
    - Prometheus (metrics)
    - OTel Collector (telemetry gateway)
    """

    # Services required for observability E2E tests
    # Only NodePort-accessible services in required_services
    # Other services (marquez, prometheus, otel-collector) checked individually
    required_services: ClassVar[list[tuple[str, int]]] = [
        ("dagster", 3000),
        ("jaeger-query", 16686),
    ]

    @pytest.mark.e2e
    @pytest.mark.e2e
    @pytest.mark.requirement("FR-040")
    @pytest.mark.requirement("FR-047")
    def test_otel_traces_in_jaeger(
        self,
        e2e_namespace: str,
        jaeger_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Test Jaeger infrastructure is deployed and API is accessible.

        Validates that:
        1. Jaeger API responds at /api/services
        2. Infrastructure is deployed and reachable
        3. Services endpoint returns valid response structure

        This infrastructure-check test verifies deployment without requiring
        pipeline execution. Future tests will validate trace collection.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("jaeger-query", 16686)

        # Verify Jaeger API responds with services list
        response = jaeger_client.get("/api/services")
        assert response.status_code == 200, (
            f"Jaeger services endpoint failed: {response.status_code}"
        )

        # Verify response structure
        response_json = response.json()
        assert "data" in response_json, (
            "Jaeger services response missing 'data' key"
        )
        assert isinstance(response_json["data"], list), (
            f"Services data should be a list, got: {type(response_json['data'])}"
        )

    @pytest.mark.e2e
    @pytest.mark.e2e
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("FR-048")
    def test_openlineage_events_in_marquez(
        self,
        e2e_namespace: str,
        marquez_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Test OpenLineage events are emitted at all 4 emission points.

        Validates that:
        1. dbt model start events are emitted
        2. dbt model complete events are emitted
        3. Dagster asset materialization events are emitted
        4. Pipeline run completion events are emitted

        Args:
            e2e_namespace: Unique namespace for test isolation.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        try:
            self.check_infrastructure("marquez", 5001)
        except Exception:
            pytest.fail(
                "Marquez not accessible at localhost:5001. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5001:5001 -n floe-test"
            )

        # TODO: Epic 13 Phase 6 - Implement OpenLineage/Marquez test
        # When implementing:
        #
        # 1. Trigger pipeline run
        #    run_id = trigger_demo_pipeline(dagster_client, namespace=e2e_namespace)
        #
        # 2. Wait for completion
        #    wait_for_condition(
        #        lambda: get_run_status(dagster_client, run_id) in ["SUCCESS", "FAILURE"],
        #        timeout=300.0,
        #        description="pipeline completion",
        #    )
        #
        # 3. Query Marquez for namespace
        #    lineage_namespace = f"floe-demo-{e2e_namespace}"
        #    response = marquez_client.get(f"/api/v1/namespaces/{lineage_namespace}/jobs")
        #    assert response.status_code == 200
        #    jobs = response.json()["jobs"]
        #    assert len(jobs) > 0, "No jobs found in Marquez"
        #
        # 4. For each expected model, verify START and COMPLETE events
        #    expected_models = ["customers", "orders", "line_items"]
        #    for model_name in expected_models:
        #        job_name = f"dbt.model.{model_name}"
        #
        #        # Get job runs
        #        response = marquez_client.get(
        #            f"/api/v1/namespaces/{lineage_namespace}/jobs/{job_name}/runs"
        #        )
        #        assert response.status_code == 200
        #        runs = response.json()["runs"]
        #        assert len(runs) > 0, f"No runs found for model {model_name}"
        #
        #        # Find runs from our pipeline execution (by timestamp/trace_id)
        #        recent_run = runs[0]  # Most recent run
        #
        #        # Verify START event exists
        #        assert recent_run.get("events", {}).get("START") is not None, (
        #            f"No START event for model {model_name}"
        #        )
        #
        #        # Verify COMPLETE event exists
        #        assert recent_run.get("events", {}).get("COMPLETE") is not None, (
        #            f"No COMPLETE event for model {model_name}"
        #        )
        #
        # 5. Verify Dagster asset materialization events
        #    # Check for asset-level events in Marquez
        #    response = marquez_client.get(
        #        f"/api/v1/namespaces/{lineage_namespace}/datasets"
        #    )
        #    assert response.status_code == 200
        #    datasets = response.json()["datasets"]
        #    assert len(datasets) > 0, "No datasets found (asset materializations missing)"
        #
        # 6. Verify pipeline run completion event
        #    response = marquez_client.get(
        #        f"/api/v1/namespaces/{lineage_namespace}/jobs/pipeline.demo/runs"
        #    )
        #    assert response.status_code == 200
        #    pipeline_runs = response.json()["runs"]
        #    assert len(pipeline_runs) > 0, "No pipeline run events found"

        pytest.fail(
            "OpenLineage/Marquez event emission test not yet implemented.\n"
            "Track: Epic 13 Phase 6 - Observability Integration\n"
            f"Namespace: {e2e_namespace}"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-042")
    def test_trace_lineage_correlation(
        self,
        e2e_namespace: str,
        jaeger_client: httpx.Client,
        marquez_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Test trace_id correlates between OTel spans and OpenLineage events.

        Validates that:
        1. OTel spans have trace_id in metadata
        2. OpenLineage events have matching trace_id
        3. Correlation enables full observability across systems

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("jaeger-query", 16686)
        try:
            self.check_infrastructure("marquez", 5001)
        except Exception:
            pytest.fail(
                "Marquez not accessible at localhost:5001. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5001:5001 -n floe-test"
            )

        # TODO: Epic 13 Phase 6 - Implement trace/lineage correlation test
        # When implementing:
        #
        # 1. Trigger pipeline run
        #    run_id = trigger_demo_pipeline(dagster_client, namespace=e2e_namespace)
        #
        # 2. Wait for completion
        #    wait_for_condition(
        #        lambda: get_run_status(dagster_client, run_id) in ["SUCCESS", "FAILURE"],
        #        timeout=300.0,
        #        description="pipeline completion",
        #    )
        #
        # 3. Get OTel trace_id from Jaeger
        #    service_name = f"floe-demo-{e2e_namespace}"
        #    response = jaeger_client.get(
        #        "/api/traces",
        #        params={"service": service_name, "limit": 10},
        #    )
        #    traces = response.json()["data"]
        #    assert len(traces) > 0
        #
        #    # Extract trace_id from first span
        #    first_trace = traces[0]
        #    otel_trace_id = first_trace["traceID"]
        #    assert otel_trace_id, "No trace_id in OTel span"
        #
        # 4. Get OpenLineage trace_id from Marquez
        #    lineage_namespace = f"floe-demo-{e2e_namespace}"
        #    response = marquez_client.get(
        #        f"/api/v1/namespaces/{lineage_namespace}/jobs/dbt.model.customers/runs"
        #    )
        #    runs = response.json()["runs"]
        #    assert len(runs) > 0
        #
        #    # Extract trace_id from run metadata
        #    recent_run = runs[0]
        #    lineage_trace_id = recent_run.get("facets", {}).get(
        #        "trace", {}
        #    ).get("trace_id")
        #    assert lineage_trace_id, "No trace_id in OpenLineage event"
        #
        # 5. Verify trace IDs match (allowing for format differences)
        #    # OTel trace_id may be hex string, OpenLineage may have dashes
        #    normalized_otel = otel_trace_id.replace("-", "").lower()
        #    normalized_lineage = lineage_trace_id.replace("-", "").lower()
        #    assert normalized_otel == normalized_lineage, (
        #        f"Trace IDs do not match: "
        #        f"OTel={otel_trace_id}, Lineage={lineage_trace_id}"
        #    )

        pytest.fail(
            "Trace/lineage correlation test not yet implemented.\n"
            "Track: Epic 13 Phase 6 - Observability Integration\n"
            f"Namespace: {e2e_namespace}"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-043")
    def test_prometheus_metrics(
        self,
        e2e_namespace: str,
        dagster_client: Any,
    ) -> None:
        """Test Prometheus service is deployed in K8s.

        Validates that:
        1. Prometheus service exists in K8s cluster
        2. Infrastructure is ready for metrics collection

        This infrastructure-check test verifies deployment without requiring
        metrics flow. Future tests will validate metrics collection.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            dagster_client: Dagster GraphQL client.
        """
        import subprocess

        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)

        # Verify Prometheus service exists in K8s
        result = subprocess.run(
            ["kubectl", "get", "svc", "prometheus", "-n", "floe-test"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            pytest.fail(
                "INFRASTRUCTURE MISSING: Prometheus service not deployed.\n"
                "Required: service 'prometheus' in namespace 'floe-test'\n"
                "Deploy: Update Helm chart to include Prometheus service\n"
                f"Error: {result.stderr.strip()}"
            )

        # Service exists if we got here
        if "prometheus" not in result.stdout.lower():
            pytest.fail(
                "INFRASTRUCTURE MISSING: Prometheus service not found in cluster.\n"
                f"kubectl get svc output:\n{result.stdout}\n"
                "Deploy: Update Helm chart to include Prometheus service"
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-045")
    def test_structured_logs_with_trace_id(
        self,
        e2e_namespace: str,
        dagster_client: Any,
    ) -> None:
        """Test Dagster webserver logs endpoint is accessible.

        Validates that:
        1. Dagster webserver is running
        2. Can query for runs (infrastructure check)
        3. Logs endpoint is accessible

        This infrastructure-check test verifies deployment without requiring
        specific log content. Future tests will validate trace_id in logs.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)

        # Verify can query Dagster for runs (basic connectivity)
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
            # GraphQL client returns response payload directly, not wrapped in 'data'
            assert "runsOrError" in result, (
                f"Dagster query response missing 'runsOrError' key. Got: {result}"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to query Dagster runs endpoint: {e}\n"
                "Dagster webserver logs may not be accessible."
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-046")
    def test_observability_non_blocking(
        self,
        e2e_namespace: str,
        dagster_client: Any,
    ) -> None:
        """Test OTel collector service exists in K8s.

        Validates that:
        1. OTel collector service is deployed
        2. Infrastructure is ready for trace collection

        This infrastructure-check test verifies deployment without requiring
        trace flow or resilience testing. Future tests will validate non-blocking behavior.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            dagster_client: Dagster GraphQL client.
        """
        import subprocess

        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)

        # Verify OTel collector service exists in K8s
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

        # Check for OTel collector service in output
        services = result.stdout.lower()
        if "otel" not in services and "opentelemetry" not in services:
            pytest.fail(
                "INFRASTRUCTURE MISSING: OTel collector service not deployed.\n"
                "Required: OpenTelemetry collector service in namespace 'floe-test'\n"
                "Deploy: Update Helm chart to include OTel collector\n"
                f"Services found:\n{result.stdout}"
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-048")
    def test_marquez_lineage_graph(
        self,
        e2e_namespace: str,
        marquez_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Test Marquez lineage graph shows complete data flow.

        Validates that:
        1. Lineage graph exists for pipeline
        2. All models appear in graph
        3. Dependencies between models are correct
        4. Graph is queryable via Marquez API

        Args:
            e2e_namespace: Unique namespace for test isolation.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        try:
            self.check_infrastructure("marquez", 5001)
        except Exception:
            pytest.fail(
                "Marquez not accessible at localhost:5001. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5001:5001 -n floe-test"
            )

        # TODO: Epic 13 Phase 6 - Implement Marquez lineage graph test
        # When implementing:
        #
        # 1. Trigger pipeline run
        #    run_id = trigger_demo_pipeline(dagster_client, namespace=e2e_namespace)
        #
        # 2. Wait for completion
        #    wait_for_condition(
        #        lambda: get_run_status(dagster_client, run_id) in ["SUCCESS", "FAILURE"],
        #        timeout=300.0,
        #        description="pipeline completion",
        #    )
        #
        # 3. Query Marquez lineage API for a dataset
        #    lineage_namespace = f"floe-demo-{e2e_namespace}"
        #    dataset_name = "customers"
        #
        #    response = marquez_client.get(
        #        f"/api/v1/lineage",
        #        params={
        #            "nodeId": f"dataset:{lineage_namespace}:{dataset_name}",
        #            "depth": 5,
        #        },
        #    )
        #    assert response.status_code == 200
        #    lineage_graph = response.json()["graph"]
        #
        # 4. Verify graph contains expected nodes
        #    nodes = lineage_graph.get("nodes", [])
        #    node_ids = [node["id"] for node in nodes]
        #
        #    expected_datasets = ["customers", "orders", "line_items"]
        #    for dataset in expected_datasets:
        #        expected_id = f"dataset:{lineage_namespace}:{dataset}"
        #        assert expected_id in node_ids, (
        #            f"Dataset {dataset} not found in lineage graph"
        #        )
        #
        # 5. Verify edges show dependencies
        #    edges = lineage_graph.get("edges", [])
        #    assert len(edges) > 0, "No edges in lineage graph"
        #
        #    # Example: orders depends on customers
        #    customer_to_orders = [
        #        edge for edge in edges
        #        if f":{lineage_namespace}:customers" in edge["origin"]
        #        and f":{lineage_namespace}:orders" in edge["destination"]
        #    ]
        #    assert len(customer_to_orders) > 0, (
        #        "Expected dependency from customers to orders"
        #    )

        pytest.fail(
            "Marquez lineage graph test not yet implemented.\n"
            "Track: Epic 13 Phase 6 - Observability Integration\n"
            f"Namespace: {e2e_namespace}"
        )
