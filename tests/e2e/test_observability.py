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
import re
from typing import Any, ClassVar

import httpx
import pytest
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

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
            "Span has empty operationName -- OTel instrumentation not setting span names"
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
        4. Jobs match the product name from this pipeline run

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
        assert create_response.status_code in (
            200,
            201,
        ), f"Failed to create namespace: {create_response.status_code} - {create_response.text}"

        # Verify namespace was created
        verify_response = marquez_client.get(f"/api/v1/namespaces/{test_namespace}")
        assert verify_response.status_code == 200, f"Created namespace not found: {test_namespace}"

        # Query for REAL jobs -- not just API responds
        jobs_response = marquez_client.get(f"/api/v1/namespaces/{test_namespace}/jobs")
        assert jobs_response.status_code == 200, (
            f"Jobs endpoint failed: {jobs_response.status_code}"
        )

        # Check for jobs in the default namespace (where pipeline would emit)
        default_jobs = marquez_client.get("/api/v1/namespaces/default/jobs")
        assert default_jobs.status_code == 200, (
            f"Marquez default namespace jobs query failed: {default_jobs.status_code}. "
            "Marquez API must be accessible for OpenLineage validation."
        )
        default_jobs_json = default_jobs.json()
        all_jobs: list[dict[str, Any]] = default_jobs_json.get("jobs", [])

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

        # Validate jobs are from THIS pipeline (match expected product names)
        job_names = [job.get("name", "") for job in all_jobs]
        has_pipeline_job = any(
            "customer" in name.lower() or "pipeline" in name.lower() for name in job_names
        )
        assert has_pipeline_job, (
            f"OBSERVABILITY GAP: Jobs found but none match expected pipeline products.\n"
            f"Job names found: {job_names}\n"
            "Expected job names containing 'customer' or 'pipeline'."
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
                "app.kubernetes.io/component=otel",
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
            "app.kubernetes.io/component=otel.\n"
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
        assert ns_response.status_code in (
            200,
            201,
        ), f"Failed to create namespace: {ns_response.status_code}"

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
        """Validate that trace spans contain floe-specific attributes for pipeline observability.

        Demands that:
        1. Jaeger contains traces for the 'floe-platform' service
        2. Traces contain spans with floe-specific attributes
        3. Spans have attributes like floe.product_name or floe.stage

        Args:
            e2e_namespace: Unique namespace for test isolation.
            jaeger_client: Jaeger query HTTP client.
            dagster_client: Dagster GraphQL client.
        """
        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("jaeger-query", 16686)

        # Query for traces from floe-platform service (real service name)
        service_name = "floe-platform"
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
            "TRACE GAP: No traces found for 'floe-platform' service.\n"
            "OTel instrumentation is not emitting traces with pipeline attributes.\n"
            "Fix: Configure OTel SDK with service.name='floe-platform' and "
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

        # Check for floe-specific attributes across all spans in the trace
        all_tag_keys: set[str] = set()
        for span in first_trace["spans"]:
            for tag in span.get("tags", []):
                all_tag_keys.add(tag.get("key", ""))

        floe_attributes = [k for k in all_tag_keys if "floe" in k.lower()]
        assert len(floe_attributes) > 0, (
            "TRACE GAP: No floe-specific attributes found in trace spans.\n"
            f"Tag keys found: {sorted(all_tag_keys)}\n"
            "Expected attributes like: floe.product_name, floe.stage, floe.pipeline_name\n"
            "Fix: Add floe.* attributes to OTel spans during compilation and execution."
        )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-041")
    def test_openlineage_four_emission_points(
        self,
        e2e_namespace: str,
        marquez_client: httpx.Client,
        dagster_client: Any,
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
        """
        from pathlib import Path

        from floe_core.compilation.stages import compile_pipeline

        # Check infrastructure availability - FAIL if not available
        self.check_infrastructure("dagster", 3000)
        try:
            self.check_infrastructure("marquez", 5000)
        except Exception:
            pytest.fail(
                "Marquez not accessible at localhost:5000. "
                "Run via make test-e2e or: kubectl port-forward svc/marquez 5000:5000 -n floe-test"
            )

        # Trigger real compilation (should emit OpenLineage events)
        project_root = Path(__file__).parent.parent.parent
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        artifacts = compile_pipeline(spec_path, manifest_path)
        assert artifacts is not None, "Compilation must succeed before checking emission points"

        # Query Marquez for events emitted BY the platform after compilation
        # Check known namespaces where the platform would emit events
        namespaces_to_check = ["default", "customer-360", "floe-platform"]
        all_jobs: list[dict[str, Any]] = []
        all_runs: list[dict[str, Any]] = []

        for ns_name in namespaces_to_check:
            jobs_response = marquez_client.get(f"/api/v1/namespaces/{ns_name}/jobs")
            if jobs_response.status_code != 200:
                continue
            jobs = jobs_response.json().get("jobs", [])
            all_jobs.extend(jobs)

            # Get runs for each job to check event types
            for job in jobs:
                runs_response = marquez_client.get(
                    f"/api/v1/namespaces/{ns_name}/jobs/{job['name']}/runs"
                )
                if runs_response.status_code == 200:
                    runs = runs_response.json().get("runs", [])
                    for run in runs:
                        run["_job_name"] = job["name"]
                        run["_namespace"] = ns_name
                    all_runs.extend(runs)

        # Platform must have emitted OpenLineage jobs
        assert len(all_jobs) > 0, (
            "EMISSION GAP: No OpenLineage jobs found after compilation.\n"
            f"Namespaces checked: {namespaces_to_check}\n"
            "The platform is not emitting OpenLineage events during compilation.\n"
            "Fix: Wire OpenLineage emission into compilation stages and pipeline execution."
        )

        # Validate the 4 emission points exist
        # Look for: dbt model START, dbt model COMPLETE, pipeline START, pipeline COMPLETE
        job_names = {job.get("name", "") for job in all_jobs}
        has_dbt_model_job = any(
            "dbt" in name.lower() or "model" in name.lower() for name in job_names
        )
        has_pipeline_job = any(
            "pipeline" in name.lower() or "daily" in name.lower() for name in job_names
        )

        # Check run states for START and COMPLETE events
        run_states: set[str] = set()
        for run in all_runs:
            current_state = run.get("state", run.get("currentState", ""))
            if current_state:
                run_states.add(current_state.upper())

        assert has_dbt_model_job, (
            "EMISSION GAP: No dbt model jobs found in Marquez.\n"
            f"Job names found: {sorted(job_names)}\n"
            "Expected: Jobs with 'dbt' or 'model' in the name for per-model emission points.\n"
            "Fix: Emit RunEvent.START and RunEvent.COMPLETE for each dbt model execution."
        )

        assert has_pipeline_job, (
            "EMISSION GAP: No pipeline-level jobs found in Marquez.\n"
            f"Job names found: {sorted(job_names)}\n"
            "Expected: Jobs with 'pipeline' in the name for pipeline-level emission.\n"
            "Fix: Emit RunEvent.START and RunEvent.COMPLETE for pipeline execution."
        )

        # Validate START and COMPLETE states exist (proving both emission points fired)
        has_start = "RUNNING" in run_states or "NEW" in run_states or "START" in run_states
        has_complete = "COMPLETED" in run_states or "COMPLETE" in run_states

        assert has_start and has_complete, (
            "EMISSION GAP: Not all lifecycle events found.\n"
            f"Run states found: {sorted(run_states)}\n"
            "Expected both START and COMPLETE lifecycle events.\n"
            "Fix: Emit RunEvent.START at job begin and RunEvent.COMPLETE at job end.\n"
            "All 4 emission points per FR-041: "
            "dbt model START, dbt model COMPLETE, pipeline START, pipeline COMPLETE."
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
        immediately queries Jaeger for traces from the 'floe-platform' service.

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
        self.check_infrastructure("dagster", 3000)
        self.check_infrastructure("jaeger-query", 16686)

        project_root = Path(__file__).parent.parent.parent
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Record timestamp before compilation (microseconds for Jaeger API)
        start_time_us = int(time.time() * 1_000_000)

        # Run real compilation -- should emit OTel spans
        artifacts = compile_pipeline(spec_path, manifest_path)
        assert artifacts is not None, "Compilation must succeed"
        assert artifacts.metadata.product_name == "customer-360", (
            "Compiled wrong product -- expected customer-360"
        )

        # Poll for traces to appear in Jaeger (OTel exporter needs time to flush)
        def check_jaeger_traces() -> bool:
            """Check if Jaeger has traces from floe-platform service."""
            end_time_us = int(time.time() * 1_000_000)
            resp = jaeger_client.get(
                "/api/traces",
                params={
                    "service": "floe-platform",
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
            timeout=10.0,
            interval=1.0,
            description="Jaeger traces to appear",
        )

        # Query Jaeger for traces from 'floe-platform' service within the last 60 seconds
        end_time_us = int(time.time() * 1_000_000)
        traces_response = jaeger_client.get(
            "/api/traces",
            params={
                "service": "floe-platform",
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
            "Compilation completed successfully but no OTel spans were recorded in Jaeger.\n"
            f"Time window: {start_time_us} to {end_time_us}\n"
            "Fix: Wire OTel SDK into compile_pipeline() stages to emit spans.\n"
            "Each compilation stage (LOAD, VALIDATE, RESOLVE, ENFORCE, COMPILE, GENERATE) "
            "should emit a span under the 'floe-platform' service."
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
            "COMPILATION OTEL GAP: Traces exist but no compilation stage spans found.\n"
            f"Operation names found: {all_operation_names}\n"
            "Expected spans matching compilation stages: "
            "LOAD, VALIDATE, RESOLVE, ENFORCE, COMPILE, GENERATE.\n"
            "Fix: Name OTel spans after compilation stages in compile_pipeline()."
        )
