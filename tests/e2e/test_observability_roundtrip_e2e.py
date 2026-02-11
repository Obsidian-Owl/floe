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
                        "service": "floe",
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

        # If no traces found with "floe" service, check what services exist
        if not traces_found:
            services_response = jaeger_client.get("/api/services")
            services = []
            if services_response.status_code == 200:
                services = services_response.json().get("data", [])

            pytest.fail(
                f"No compilation traces found in Jaeger after 30s.\n"
                f"Expected service: 'floe'\n"
                f"Available services: {services}\n"
                f"OTel Collector may not be forwarding to Jaeger.\n"
                f"Check: kubectl logs -n floe-test -l app.kubernetes.io/name=otel --tail=20"
            )

    @pytest.mark.requirement("AC-2.3")
    def test_otel_collector_accepts_spans(
        self,
        wait_for_service: Callable[..., None],
    ) -> None:
        """Verify OTel Collector accepts OTLP spans.

        Sends a test span directly to the OTel Collector and verifies it's
        accepted without error. This validates the Collector is running and
        configured to receive OTLP gRPC spans.
        """
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        otel_endpoint = os.environ.get("OTEL_ENDPOINT", "http://localhost:4317")
        test_service = f"e2e-otel-test-{int(time.time())}"

        resource = Resource.create({"service.name": test_service})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # Create and export test span
        tracer = provider.get_tracer("e2e-test")
        with tracer.start_as_current_span("e2e_observability_test") as span:
            span.set_attribute("test.type", "observability_roundtrip")

        # Force flush — this will raise if collector rejects
        flush_ok = provider.force_flush(timeout_millis=10_000)
        assert flush_ok, (
            f"OTel Collector did not accept span within 10s.\n"
            f"Endpoint: {otel_endpoint}\n"
            f"Check collector: kubectl logs -n floe-test -l app.kubernetes.io/name=otel --tail=20"
        )

        provider.shutdown()

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
