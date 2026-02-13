"""E2E test: Observability Round-Trip (AC-2.3).

Validates the full observability pipeline:
    Compile with OTel config → run pipeline → query Jaeger for traces

Unlike the existing test_observability.py which validates OTel SDK configuration,
this test validates the full round-trip: compilation produces traced artifacts →
pipeline execution sends traces through OTel Collector → traces land in Jaeger.

Prerequisites:
    - Kind cluster with OTel Collector and Jaeger: make kind-up
    - Port-forwards active: make test-e2e

See Also:
    - .specwright/work/test-hardening-audit/spec.md: AC-2.3
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from testing.fixtures.polling import wait_for_condition

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.e2e
@pytest.mark.requirement("AC-2.3")
class TestObservabilityRoundTrip:
    """Observability round-trip: compile → traces in Jaeger.

    Validates that OTel traces generated during compilation flow through
    the OTel Collector and land in Jaeger where they can be queried.
    """

    @pytest.mark.requirement("AC-2.3")
    def test_compilation_generates_traces(
        self,
        compiled_artifacts: Callable[[Path], Any],
        project_root: Path,
        jaeger_client: httpx.Client,
    ) -> None:
        """Compile a product and verify traces appear in Jaeger.

        Exercises the full trace pipeline:
        1. Compile customer-360 through the OTel-instrumented pipeline
        2. Wait for traces to propagate through OTel Collector to Jaeger
        3. Query Jaeger API for traces from the floe service
        4. Verify span hierarchy shows compilation stages
        """
        # Record timestamp before compilation for Jaeger query
        start_time = int(time.time() * 1_000_000)  # Jaeger uses microseconds

        # Compile through the real OTel-instrumented pipeline
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)
        assert artifacts.version, "Compilation failed"

        # Wait for traces to propagate (OTel Collector batches spans)
        end_time = int(time.time() * 1_000_000)

        def check_traces_in_jaeger() -> bool:
            """Check if compilation traces appear in Jaeger."""
            try:
                response = jaeger_client.get(
                    "/api/traces",
                    params={
                        "service": "floe-platform",
                        "start": start_time,
                        "end": end_time + 60_000_000,  # +60s buffer
                        "limit": 20,
                    },
                )
                if response.status_code != 200:
                    return False
                data = response.json()
                return len(data.get("data", [])) > 0
            except (httpx.HTTPError, ValueError):
                return False

        traces_found = wait_for_condition(
            check_traces_in_jaeger,
            timeout=30.0,
            interval=3.0,
            description="compilation traces to appear in Jaeger",
            raise_on_timeout=False,
        )

        # If no traces found with "floe-platform" service, check what services exist
        if not traces_found:
            services_response = jaeger_client.get("/api/services")
            services: list[str] = []
            if services_response.status_code == 200:
                services = services_response.json().get("data", [])

            pytest.fail(
                f"No compilation traces found in Jaeger after 30s.\n"
                f"Expected service: 'floe-platform'\n"
                f"Available services: {services}\n"
                f"OTel Collector may not be forwarding to Jaeger.\n"
                f"Check: kubectl logs -n floe-test -l app.kubernetes.io/name=otel --tail=20"
            )

        # Validate span hierarchy — spans should have parent-child relationships
        traces_response = jaeger_client.get(
            "/api/traces",
            params={
                "service": "floe-platform",
                "start": start_time,
                "end": end_time + 60_000_000,
                "limit": 5,
            },
        )
        assert traces_response.status_code == 200, (
            f"Jaeger trace query failed: {traces_response.status_code}"
        )

        traces_data = traces_response.json().get("data", [])
        assert len(traces_data) > 0, "No traces returned for span hierarchy validation"

        # Inspect the first trace for span structure
        first_trace = traces_data[0]
        spans = first_trace.get("spans", [])
        assert len(spans) > 0, "Trace has no spans"

        # Collect span IDs and parent span IDs
        span_ids = {s["spanID"] for s in spans}
        spans_with_parent = [
            s
            for s in spans
            if s.get("references")
            and any(
                ref.get("refType") == "CHILD_OF" and ref.get("spanID") in span_ids
                for ref in s["references"]
            )
        ]

        # Verify parent-child relationships exist (compilation has nested stages)
        assert len(spans_with_parent) > 0, (
            f"No parent-child span relationships found in trace. "
            f"Compilation should produce nested spans for stages. "
            f"Span count: {len(spans)}, "
            f"Operations: {[s.get('operationName', '?') for s in spans[:10]]}"
        )

        # Verify spans have meaningful operation names
        operation_names = [s.get("operationName", "") for s in spans]
        non_empty_ops = [op for op in operation_names if op]
        assert len(non_empty_ops) == len(spans), (
            f"Some spans have empty operationName: "
            f"{[s['spanID'] for s in spans if not s.get('operationName')]}"
        )

    @pytest.mark.requirement("AC-2.3")
    def test_otel_collector_accepts_spans(
        self,
        otel_tracer_provider: Any,
    ) -> None:
        """Verify OTel Collector accepts OTLP spans.

        Uses the shared otel_tracer_provider fixture (conftest.py) to send a
        test span to the OTel Collector and verifies it's accepted without
        error. This validates the Collector is running and configured to
        receive OTLP gRPC spans.

        Args:
            otel_tracer_provider: Session-scoped TracerProvider from conftest.
        """
        # Use the shared TracerProvider fixture
        tracer = otel_tracer_provider.get_tracer("e2e-test")
        with tracer.start_as_current_span("e2e_observability_test") as span:
            span.set_attribute("test.type", "observability_roundtrip")

        # Force flush — this will raise if collector rejects
        otel_endpoint = os.environ.get("OTEL_ENDPOINT", "http://localhost:4317")
        flush_ok = otel_tracer_provider.force_flush(timeout_millis=10_000)
        assert flush_ok, (
            f"OTel Collector did not accept span within 10s.\n"
            f"Endpoint: {otel_endpoint}\n"
            f"Check collector: kubectl logs -n floe-test -l app.kubernetes.io/name=otel --tail=20"
        )

    @pytest.mark.requirement("AC-2.3")
    def test_jaeger_query_api_functional(
        self,
        jaeger_client: httpx.Client,
    ) -> None:
        """Verify Jaeger query API can list services and search traces.

        Goes beyond health check — validates that Jaeger's query engine
        is functional and can execute search operations.
        """
        # List services
        response = jaeger_client.get("/api/services")
        assert response.status_code == 200, f"Jaeger /api/services returned {response.status_code}"
        data = response.json()
        assert "data" in data, f"Jaeger response missing 'data': {data}"
        assert isinstance(data["data"], list), "Jaeger services should be a list"

        # Execute a trace search (even if empty results)
        search_response = jaeger_client.get(
            "/api/traces",
            params={
                "service": "non-existent-service",
                "limit": 1,
            },
        )
        assert search_response.status_code == 200, (
            f"Jaeger trace search returned {search_response.status_code}"
        )
        search_data = search_response.json()
        assert "data" in search_data, "Jaeger search response missing 'data'"
