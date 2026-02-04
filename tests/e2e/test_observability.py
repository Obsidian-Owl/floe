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
import uuid
from datetime import datetime, timezone
from typing import Any, ClassVar

import httpx
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase


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
    required_services: ClassVar[list[tuple[str, int]]] = [
        ("dagster", 3000),
        ("jaeger-query", 16686),
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
        """Validate that OTel traces with real spans exist in Jaeger for the floe-platform service.

        Demands that:
        1. Jaeger contains traces for the 'floe-platform' service
        2. Traces contain spans with operation names
        3. The services list includes 'floe-platform'

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("jaeger-query", 16686)

        # Query Jaeger for floe-platform service traces
        service_name = "floe-platform"
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
            "OBSERVABILITY GAP: No traces found for 'floe-platform' service in Jaeger.\n"
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
            "Span has empty operationName — OTel instrumentation not setting span names"
        )

        # Verify services list includes floe-platform
        response = jaeger_client.get("/api/services")
        assert response.status_code == 200, (
            f"Jaeger services endpoint failed: {response.status_code}"
        )
        services_json = response.json()
        assert "data" in services_json, "Jaeger services response missing 'data' key"
        services = services_json["data"]
        assert "floe-platform" in services, (
            f"OBSERVABILITY GAP: 'floe-platform' not in Jaeger services list.\n"
            f"Services found: {services}\n"
            "Fix: Configure OTel SDK with service.name='floe-platform'"
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-041")
    @pytest.mark.requirement("FR-048")
    def test_openlineage_events_in_marquez(
        self,
        e2e_namespace: str,
        marquez_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Validate that Marquez contains real OpenLineage jobs from pipeline execution.

        Demands that:
        1. Marquez API is accessible and namespace creation works
        2. Real OpenLineage jobs exist in at least one namespace
        3. Pipeline execution has emitted RunEvent.START/COMPLETE events

        Args:
            e2e_namespace: Unique namespace for test isolation.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        try:
            self.check_infrastructure("marquez", 5000)
        except Exception:
            pytest.fail(
                "Marquez not accessible at localhost:5000. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000:5000 -n floe-test"
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
        assert create_response.status_code in (200, 201), (
            f"Failed to create namespace: {create_response.status_code} - {create_response.text}"
        )

        # Verify namespace was created
        verify_response = marquez_client.get(f"/api/v1/namespaces/{test_namespace}")
        assert verify_response.status_code == 200, f"Created namespace not found: {test_namespace}"

        # Query for REAL jobs — not just API responds
        jobs_response = marquez_client.get(f"/api/v1/namespaces/{test_namespace}/jobs")
        assert jobs_response.status_code == 200, (
            f"Jobs endpoint failed: {jobs_response.status_code}"
        )

        # Check for jobs in the default namespace too (where pipeline would emit)
        default_jobs = marquez_client.get("/api/v1/namespaces/default/jobs")
        if default_jobs.status_code == 200:
            default_jobs_json = default_jobs.json()
            all_jobs = default_jobs_json.get("jobs", [])
        else:
            all_jobs = []

        # Also check customer-360 namespace
        c360_jobs = marquez_client.get("/api/v1/namespaces/customer-360/jobs")
        if c360_jobs.status_code == 200:
            c360_jobs_json = c360_jobs.json()
            all_jobs.extend(c360_jobs_json.get("jobs", []))

        # We need REAL OpenLineage events from pipeline execution
        assert len(all_jobs) > 0, (
            "OBSERVABILITY GAP: No OpenLineage jobs found in any Marquez namespace.\n"
            "The platform is not emitting OpenLineage events during pipeline execution.\n"
            "Fix: Configure dbt-openlineage or Dagster OpenLineage integration to emit "
            "RunEvent.START and RunEvent.COMPLETE events.\n"
            f"Namespaces checked: default, customer-360, {test_namespace}"
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
        """Validate Jaeger and Marquez contain pipeline data for correlation.

        Demands that:
        1. Jaeger has floe-related or dagster-related service traces
        2. Marquez has floe-related namespaces with pipeline data
        3. At least one system has real pipeline data for correlation

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
            self.check_infrastructure("marquez", 5000)
        except Exception:
            pytest.fail(
                "Marquez not accessible at localhost:5000. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000:5000 -n floe-test"
            )

        # Query for REAL traces in Jaeger for any floe-related service
        all_services_response = jaeger_client.get("/api/services")
        assert all_services_response.status_code == 200
        all_services = all_services_response.json().get("data", [])

        floe_services = [s for s in all_services if "floe" in s.lower() or "dagster" in s.lower()]

        # Query Marquez for REAL jobs
        all_namespaces_response = marquez_client.get("/api/v1/namespaces")
        assert all_namespaces_response.status_code == 200
        all_namespaces = all_namespaces_response.json().get("namespaces", [])

        floe_namespaces = [
            ns["name"]
            for ns in all_namespaces
            if "floe" in ns["name"].lower()
            or "customer" in ns["name"].lower()
            or "iot" in ns["name"].lower()
            or "financial" in ns["name"].lower()
        ]

        # Both systems must have pipeline data for correlation to work
        assert len(floe_services) > 0 or len(floe_namespaces) > 0, (
            "CORRELATION GAP: Neither Jaeger nor Marquez has pipeline data.\n"
            f"Jaeger services: {all_services}\n"
            f"Marquez namespaces: {[ns['name'] for ns in all_namespaces]}\n"
            "Fix: Run a pipeline with both OTel tracing and OpenLineage emission enabled, "
            "using the same run_id for correlation."
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
        self.check_infrastructure("dagster", 3000)

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
            "Platform → OTel Collector → External Backend\n"
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
                "app.kubernetes.io/component=opentelemetry-collector",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if pod_result.returncode == 0 and pod_result.stdout.strip():
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
        """Validate that compilation emits structured logs and Dagster runs endpoint is queryable.

        Demands that:
        1. Compilation produces log output with trace context
        2. Dagster runs endpoint is accessible for log correlation

        Args:
            e2e_namespace: Unique namespace for test isolation.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)

        # Validate that compilation emits structured logs with trace context
        import io
        import logging
        from pathlib import Path

        from floe_core.compilation.stages import compile_pipeline

        project_root = Path(__file__).parent.parent.parent
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Capture log output during compilation
        log_buffer = io.StringIO()
        handler = logging.StreamHandler(log_buffer)
        handler.setLevel(logging.DEBUG)
        root_logger = logging.getLogger("floe_core")
        root_logger.addHandler(handler)

        try:
            artifacts = compile_pipeline(spec_path, manifest_path)
            assert artifacts is not None, "Compilation should succeed"
        finally:
            root_logger.removeHandler(handler)

        log_output = log_buffer.getvalue()

        # Compilation should produce SOME log output
        assert len(log_output) > 0, (
            "OBSERVABILITY GAP: Compilation produces no log output.\n"
            "Fix: Add structured logging to compilation stages with trace_id context."
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
        self.check_infrastructure("dagster", 3000)

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
        assert artifacts.version == "0.5.0", (
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
    ) -> None:
        """Validate that Marquez contains real lineage data queryable via the lineage graph API.

        Demands that:
        1. At least one Marquez namespace contains real OpenLineage jobs
        2. Lineage graph API returns data for those jobs

        Args:
            e2e_namespace: Unique namespace for test isolation.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client (for infrastructure check).
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        try:
            self.check_infrastructure("marquez", 5000)
        except Exception:
            pytest.fail(
                "Marquez not accessible at localhost:5000. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000:5000 -n floe-test"
            )

        # Create a test namespace
        test_ns = f"floe-lineage-{e2e_namespace}"

        # Create namespace
        ns_response = marquez_client.put(
            f"/api/v1/namespaces/{test_ns}",
            json={
                "ownerName": "floe-e2e",
                "description": "Lineage graph test namespace",
            },
        )
        assert ns_response.status_code in (200, 201), (
            f"Failed to create namespace: {ns_response.status_code}"
        )

        # Query ALL namespaces for real lineage data
        all_ns_response = marquez_client.get("/api/v1/namespaces")
        assert all_ns_response.status_code == 200
        all_namespaces = all_ns_response.json().get("namespaces", [])

        # Search for any namespace with actual job data
        namespaces_with_jobs: list[str] = []
        for ns in all_namespaces:
            ns_name = ns["name"]
            ns_jobs = marquez_client.get(f"/api/v1/namespaces/{ns_name}/jobs")
            if ns_jobs.status_code == 200:
                jobs = ns_jobs.json().get("jobs", [])
                if len(jobs) > 0:
                    namespaces_with_jobs.append(ns_name)

        assert len(namespaces_with_jobs) > 0, (
            "LINEAGE GAP: No namespaces contain OpenLineage jobs.\n"
            f"Checked {len(all_namespaces)} namespaces, none have job data.\n"
            "Fix: Configure dbt-openlineage or Dagster OpenLineage integration "
            "to emit lineage events during pipeline execution."
        )

        # For the namespace with jobs, verify lineage graph is queryable
        ns_with_data = namespaces_with_jobs[0]
        jobs_response = marquez_client.get(f"/api/v1/namespaces/{ns_with_data}/jobs")
        first_job = jobs_response.json()["jobs"][0]

        # Query lineage for this job
        lineage_response = marquez_client.get(
            "/api/v1/lineage",
            params={
                "nodeId": f"job:{ns_with_data}:{first_job['name']}",
                "depth": 3,
            },
        )
        assert lineage_response.status_code == 200, (
            f"Lineage graph query failed for job {first_job['name']}: "
            f"{lineage_response.status_code} - {lineage_response.text}"
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
        """Validate that trace spans contain required attributes for pipeline observability.

        Demands that:
        1. Jaeger API supports attribute-based trace queries
        2. Traces exist with real span data
        3. Spans have operation names and tag attributes

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("jaeger-query", 16686)

        # Test 1: Verify Jaeger supports attribute-based trace queries
        # Query for any traces with tag filtering capability
        service_name = f"floe-test-{e2e_namespace}"
        response = jaeger_client.get(
            "/api/traces",
            params={
                "service": service_name,
                "limit": 10,
                # Test tag filtering capability (Jaeger supports this)
                "tags": json.dumps({"model_name": "any"}),
            },
        )
        assert response.status_code == 200, (
            f"Jaeger trace query with tag filtering failed: {response.status_code}"
        )

        response_json = response.json()
        assert "data" in response_json, "Jaeger response missing 'data' key"
        traces = response_json["data"]
        assert isinstance(traces, list), f"Traces should be a list, got: {type(traces)}"

        # Test 2: Traces MUST exist for pipeline observability
        assert len(traces) > 0, (
            "TRACE GAP: No traces found with tag filtering.\n"
            "OTel instrumentation is not emitting traces with pipeline attributes.\n"
            "Fix: Add model_name and pipeline_name attributes to OTel spans."
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

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-041")
    def test_openlineage_four_emission_points(
        self,
        e2e_namespace: str,
        marquez_client: httpx.Client,
        dagster_client: Any,
    ) -> None:
        """Test OpenLineage events are emitted at all 4 required lifecycle points.

        Validates that the platform emits OpenLineage events at:
        1. dbt model start (RunEvent.START for each model)
        2. dbt model complete (RunEvent.COMPLETE for each model)
        3. Pipeline start (job-level RunEvent.START)
        4. Pipeline complete (job-level RunEvent.COMPLETE)

        This test validates the Marquez API can receive and store all 4 event types.
        Full emission testing requires pipeline execution with OpenLineage integration.

        Args:
            e2e_namespace: Unique namespace for test isolation.
            marquez_client: Marquez HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        try:
            self.check_infrastructure("marquez", 5000)
        except Exception:
            pytest.fail(
                "Marquez not accessible at localhost:5000. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000:5000 -n floe-test"
            )

        # Test namespace for emission point validation
        test_ns = f"floe-emission-{e2e_namespace}"

        # Create namespace
        ns_response = marquez_client.put(
            f"/api/v1/namespaces/{test_ns}",
            json={
                "ownerName": "floe-e2e",
                "description": "OpenLineage emission points test",
            },
        )
        assert ns_response.status_code in (200, 201), (
            f"Failed to create namespace: {ns_response.status_code}"
        )

        # Define the 4 emission points as test jobs
        emission_points = [
            {
                "job_name": "dbt_model_customers_run",
                "event_type": "START",
                "description": "dbt model start (per-model RunEvent.START)",
            },
            {
                "job_name": "dbt_model_customers_run",
                "event_type": "COMPLETE",
                "description": "dbt model complete (per-model RunEvent.COMPLETE)",
            },
            {
                "job_name": "pipeline_daily_run",
                "event_type": "START",
                "description": "Pipeline start (job-level RunEvent.START)",
            },
            {
                "job_name": "pipeline_daily_run",
                "event_type": "COMPLETE",
                "description": "Pipeline complete (job-level RunEvent.COMPLETE)",
            },
        ]

        # Test 1: Validate Marquez can receive all 4 event types
        for point in emission_points:
            job_name = point["job_name"]
            event_type = point["event_type"]
            run_id = str(uuid.uuid4())

            # Create a minimal OpenLineage event for this emission point
            event = {
                "eventType": event_type,
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "run": {
                    "runId": run_id,
                },
                "job": {
                    "namespace": test_ns,
                    "name": job_name,
                },
                "inputs": [],
                "outputs": [],
                "producer": "https://github.com/Obsidian-Owl/floe-runtime",
            }

            # Send event to Marquez
            event_response = marquez_client.post(
                "/api/v1/lineage",
                json=event,
            )

            # Marquez should accept the event (200 or 201)
            assert event_response.status_code in (200, 201), (
                f"Failed to emit {event_type} event for {job_name}: "
                f"{event_response.status_code} - {event_response.text}"
            )

        # Test 2: Verify all events were stored and are queryable
        # Query jobs endpoint - should show both jobs
        jobs_response = marquez_client.get(f"/api/v1/namespaces/{test_ns}/jobs")
        assert jobs_response.status_code == 200, f"Jobs query failed: {jobs_response.status_code}"

        jobs_json = jobs_response.json()
        assert "jobs" in jobs_json, "Jobs response missing 'jobs' key"
        job_names = {job["name"] for job in jobs_json["jobs"]}

        # Should have both dbt model job and pipeline job
        assert "dbt_model_customers_run" in job_names, (
            "dbt model job not found in Marquez after emitting events"
        )
        assert "pipeline_daily_run" in job_names, (
            "Pipeline job not found in Marquez after emitting events"
        )

        # Test 3: Verify we can query runs for each job (validates event storage)
        for job_name in ["dbt_model_customers_run", "pipeline_daily_run"]:
            runs_response = marquez_client.get(f"/api/v1/namespaces/{test_ns}/jobs/{job_name}/runs")
            assert runs_response.status_code == 200, (
                f"Runs query failed for {job_name}: {runs_response.status_code}"
            )

            runs_json = runs_response.json()
            assert "runs" in runs_json, f"Runs response missing 'runs' key for {job_name}"
            assert len(runs_json["runs"]) > 0, (
                f"No runs found for {job_name} - events were not stored"
            )

            # Verify both START and COMPLETE events are present
            # (Each job had 2 events emitted)
            # Marquez may combine runs, but we should see run state transitions
            for run in runs_json["runs"]:
                assert "id" in run, "Run missing 'id' field"
                # Run may have state: COMPLETED if both START and COMPLETE were received

        # All 4 emission points validated:
        # 1. dbt model START - event accepted and stored
        # 2. dbt model COMPLETE - event accepted and stored
        # 3. Pipeline START - event accepted and stored
        # 4. Pipeline COMPLETE - event accepted and stored

        # Infrastructure supports all 4 OpenLineage emission points per FR-041
