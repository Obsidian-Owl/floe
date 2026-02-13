"""OTel pipeline configuration structural validation tests.

Tests that validate OTel Collector configuration, label alignment between
Helm chart templates and E2E tests, and observability fixture wiring.
These are unit tests that parse YAML and Python source -- no external
services or K8s cluster required.

Requirements:
    WU4-AC1: test_observability.py pod label selector uses app.kubernetes.io/component=otel
    WU4-AC2: OTel Collector config includes Jaeger exporter with OTLP gRPC endpoint
    WU4-AC3: values-test.yaml enables Jaeger and OTel
    WU4-AC4: E2E test queries Jaeger for service traces and asserts non-empty
    WU4-AC5: OTel tracer provider is initialized in E2E conftest
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

# File paths under test
TEST_OBSERVABILITY = REPO_ROOT / "tests" / "e2e" / "test_observability.py"
TEST_ROUNDTRIP = REPO_ROOT / "tests" / "e2e" / "test_observability_roundtrip_e2e.py"
E2E_CONFTEST = REPO_ROOT / "tests" / "e2e" / "conftest.py"
VALUES_YAML = REPO_ROOT / "charts" / "floe-platform" / "values.yaml"
VALUES_TEST_YAML = REPO_ROOT / "charts" / "floe-platform" / "values-test.yaml"
CONFIGMAP_OTEL = REPO_ROOT / "charts" / "floe-platform" / "templates" / "configmap-otel.yaml"

# Expected label value that the configmap-otel.yaml uses (line 13)
CORRECT_OTEL_LABEL = "otel"
WRONG_OTEL_LABEL = "opentelemetry-collector"


class TestOtelLabelAlignment:
    """WU4-AC1: Pod label selector in E2E tests matches chart label."""

    @pytest.mark.requirement("WU4-AC1")
    def test_configmap_otel_uses_correct_component_label(self) -> None:
        """Verify configmap-otel.yaml declares app.kubernetes.io/component: otel.

        The chart template is the source of truth for the label value.
        All consumers (E2E tests, kubectl selectors) must match it.
        """
        content = CONFIGMAP_OTEL.read_text()
        assert "app.kubernetes.io/component: otel" in content, (
            f"configmap-otel.yaml must contain 'app.kubernetes.io/component: otel'. "
            f"This is the source-of-truth label that E2E tests must match."
        )

    @pytest.mark.requirement("WU4-AC1")
    def test_observability_test_uses_correct_otel_label_selector(self) -> None:
        """Verify test_observability.py uses app.kubernetes.io/component=otel selector.

        The E2E test must use the SAME label as the chart template
        (configmap-otel.yaml line 13) to find OTel Collector pods.
        Using the wrong label causes kubectl to find zero pods, and the
        test wrongly concludes OTel Collector is not deployed.
        """
        content = TEST_OBSERVABILITY.read_text()

        # Must contain the correct selector
        assert f"app.kubernetes.io/component={CORRECT_OTEL_LABEL}" in content, (
            f"test_observability.py must use label selector "
            f"'app.kubernetes.io/component={CORRECT_OTEL_LABEL}' "
            f"to match configmap-otel.yaml. "
            f"Currently uses the wrong label '{WRONG_OTEL_LABEL}'."
        )

    @pytest.mark.requirement("WU4-AC1")
    def test_observability_test_does_not_use_old_otel_label(self) -> None:
        """Verify test_observability.py does NOT use the old opentelemetry-collector label.

        The old label 'opentelemetry-collector' was from a previous chart version.
        It does not match configmap-otel.yaml which uses 'otel'. If both old
        and new labels coexist, the old one must be removed to prevent confusion.
        """
        content = TEST_OBSERVABILITY.read_text()
        assert f"app.kubernetes.io/component={WRONG_OTEL_LABEL}" not in content, (
            f"test_observability.py still uses OLD label selector "
            f"'app.kubernetes.io/component={WRONG_OTEL_LABEL}'. "
            f"Must be updated to '{CORRECT_OTEL_LABEL}' to match configmap-otel.yaml."
        )

    @pytest.mark.requirement("WU4-AC1")
    def test_roundtrip_test_uses_correct_otel_label_if_present(self) -> None:
        """Verify test_observability_roundtrip_e2e.py uses correct label if referencing OTel pods.

        If the roundtrip test has kubectl label selectors for OTel pods,
        they must use 'otel' not 'opentelemetry-collector'.
        """
        content = TEST_ROUNDTRIP.read_text()
        # If the roundtrip test references any component label selector,
        # it must not use the old one
        if "app.kubernetes.io/component" in content:
            assert f"app.kubernetes.io/component={WRONG_OTEL_LABEL}" not in content, (
                f"test_observability_roundtrip_e2e.py uses old label "
                f"'{WRONG_OTEL_LABEL}'. Must use '{CORRECT_OTEL_LABEL}'."
            )


class TestOtelJaegerExporter:
    """WU4-AC2: OTel Collector config includes Jaeger exporter with OTLP gRPC."""

    @pytest.mark.requirement("WU4-AC2")
    def test_values_yaml_has_otlp_jaeger_exporter(self) -> None:
        """Verify values.yaml OTel config includes otlp/jaeger exporter.

        The exporter name must be exactly 'otlp/jaeger' in the exporters
        section of the OTel Collector config.
        """
        values = yaml.safe_load(VALUES_YAML.read_text())
        otel_config = values.get("otel", {}).get("config", {})
        exporters = otel_config.get("exporters", {})

        assert "otlp/jaeger" in exporters, (
            f"OTel Collector config must include 'otlp/jaeger' exporter. "
            f"Found exporters: {list(exporters.keys())}"
        )

    @pytest.mark.requirement("WU4-AC2")
    def test_jaeger_exporter_has_grpc_endpoint(self) -> None:
        """Verify otlp/jaeger exporter targets port 4317 (gRPC).

        The endpoint must contain ':4317' which is the standard OTLP gRPC
        port. Using HTTP port 4318 would be wrong for this exporter.
        """
        values = yaml.safe_load(VALUES_YAML.read_text())
        otel_config = values.get("otel", {}).get("config", {})
        jaeger_exporter = otel_config.get("exporters", {}).get("otlp/jaeger", {})
        endpoint = jaeger_exporter.get("endpoint", "")

        assert ":4317" in endpoint, (
            f"otlp/jaeger exporter must use gRPC port 4317. "
            f"Got endpoint: '{endpoint}'"
        )

    @pytest.mark.requirement("WU4-AC2")
    def test_jaeger_exporter_has_tls_insecure(self) -> None:
        """Verify otlp/jaeger exporter uses insecure TLS for in-cluster communication.

        Within a K8s cluster, the Jaeger collector is reached over the
        cluster network. TLS insecure must be set to true.
        """
        values = yaml.safe_load(VALUES_YAML.read_text())
        otel_config = values.get("otel", {}).get("config", {})
        jaeger_exporter = otel_config.get("exporters", {}).get("otlp/jaeger", {})
        tls = jaeger_exporter.get("tls", {})

        assert tls.get("insecure") is True, (
            f"otlp/jaeger exporter must have tls.insecure: true for in-cluster use. "
            f"Got tls config: {tls}"
        )

    @pytest.mark.requirement("WU4-AC2")
    def test_traces_pipeline_includes_jaeger_exporter(self) -> None:
        """Verify the traces pipeline routes to the otlp/jaeger exporter.

        Even if the exporter is defined, it must be wired into the traces
        pipeline to actually send data. A defined-but-unwired exporter is
        a silent no-op.
        """
        values = yaml.safe_load(VALUES_YAML.read_text())
        otel_config = values.get("otel", {}).get("config", {})
        pipelines = otel_config.get("service", {}).get("pipelines", {})
        traces_pipeline = pipelines.get("traces", {})
        exporters = traces_pipeline.get("exporters", [])

        assert "otlp/jaeger" in exporters, (
            f"Traces pipeline must include 'otlp/jaeger' in exporters. "
            f"Got exporters: {exporters}. "
            f"Without this, traces are collected but never sent to Jaeger."
        )

    @pytest.mark.requirement("WU4-AC2")
    def test_otlp_receiver_enabled_with_grpc(self) -> None:
        """Verify OTel Collector receives OTLP spans over gRPC on port 4317.

        The receiver must accept gRPC on 0.0.0.0:4317 so that platform
        components can push spans into the collector.
        """
        values = yaml.safe_load(VALUES_YAML.read_text())
        otel_config = values.get("otel", {}).get("config", {})
        receivers = otel_config.get("receivers", {})
        otlp_receiver = receivers.get("otlp", {})
        grpc_config = otlp_receiver.get("protocols", {}).get("grpc", {})
        endpoint = grpc_config.get("endpoint", "")

        assert "4317" in endpoint, (
            f"OTLP receiver must listen on gRPC port 4317. Got: '{endpoint}'"
        )


class TestValuesTestOtelJaeger:
    """WU4-AC3: values-test.yaml enables Jaeger and OTel for CI testing."""

    @pytest.mark.requirement("WU4-AC3")
    def test_otel_enabled_in_test_values(self) -> None:
        """Verify otel.enabled is true in values-test.yaml.

        Without OTel Collector enabled, traces have nowhere to go in CI.
        """
        values = yaml.safe_load(VALUES_TEST_YAML.read_text())
        otel_enabled = values.get("otel", {}).get("enabled")

        assert otel_enabled is True, (
            f"otel.enabled must be true in values-test.yaml. Got: {otel_enabled}"
        )

    @pytest.mark.requirement("WU4-AC3")
    def test_jaeger_enabled_in_test_values(self) -> None:
        """Verify jaeger.enabled is true in values-test.yaml.

        Without Jaeger, there is no trace backend for E2E observability tests.
        """
        values = yaml.safe_load(VALUES_TEST_YAML.read_text())
        jaeger_enabled = values.get("jaeger", {}).get("enabled")

        assert jaeger_enabled is True, (
            f"jaeger.enabled must be true in values-test.yaml. Got: {jaeger_enabled}"
        )

    @pytest.mark.requirement("WU4-AC3")
    def test_jaeger_all_in_one_enabled_in_test_values(self) -> None:
        """Verify Jaeger allInOne is enabled for lightweight test deployment.

        For CI testing, Jaeger all-in-one mode provides a single pod with
        collector + query + memory storage. Separate collector/query pods
        are unnecessary overhead in test environments.
        """
        values = yaml.safe_load(VALUES_TEST_YAML.read_text())
        all_in_one = values.get("jaeger", {}).get("allInOne", {})

        assert all_in_one.get("enabled") is True, (
            f"jaeger.allInOne.enabled must be true in values-test.yaml. "
            f"Got: {all_in_one.get('enabled')}"
        )

    @pytest.mark.requirement("WU4-AC3")
    def test_otel_and_jaeger_both_enabled_simultaneously(self) -> None:
        """Verify BOTH otel and jaeger are enabled (not just one).

        OTel Collector without Jaeger means traces are collected but have
        no backend. Jaeger without OTel Collector means traces bypass the
        collector pipeline (no batching, no processing).
        """
        values = yaml.safe_load(VALUES_TEST_YAML.read_text())
        otel_enabled = values.get("otel", {}).get("enabled")
        jaeger_enabled = values.get("jaeger", {}).get("enabled")

        assert otel_enabled is True and jaeger_enabled is True, (
            f"Both otel.enabled AND jaeger.enabled must be true in values-test.yaml. "
            f"Got otel.enabled={otel_enabled}, jaeger.enabled={jaeger_enabled}"
        )


class TestE2EJaegerTraceQuery:
    """WU4-AC4: E2E test queries Jaeger for service traces and asserts non-empty."""

    @pytest.mark.requirement("WU4-AC4")
    def test_roundtrip_queries_jaeger_with_service_param(self) -> None:
        """Verify roundtrip E2E test queries Jaeger /api/traces with service parameter.

        The test must query Jaeger's trace search API with a 'service'
        parameter to find traces from a specific service.
        """
        content = TEST_ROUNDTRIP.read_text()

        assert "/api/traces" in content, (
            "test_observability_roundtrip_e2e.py must query Jaeger /api/traces endpoint"
        )
        # Must pass a service parameter to the Jaeger query
        assert '"service"' in content or "'service'" in content, (
            "test_observability_roundtrip_e2e.py must pass 'service' parameter "
            "to Jaeger trace query"
        )

    @pytest.mark.requirement("WU4-AC4")
    def test_roundtrip_asserts_traces_non_empty(self) -> None:
        """Verify roundtrip test asserts that returned traces are non-empty.

        The test must not silently accept zero traces. It must fail if
        Jaeger returns an empty data array.
        """
        content = TEST_ROUNDTRIP.read_text()

        # The test must have an assertion that fails when traces are empty.
        # Look for patterns like: assert len(traces) > 0, len(data) > 0,
        # or pytest.fail when no traces found
        has_non_empty_assertion = (
            re.search(r'assert\s+len\([^)]*traces[^)]*\)\s*>\s*0', content) is not None
            or re.search(r'assert\s+len\([^)]*data[^)]*\)\s*>\s*0', content) is not None
            or re.search(r'pytest\.fail.*[Nn]o.*trace', content) is not None
            or re.search(r'assert\s+traces_found', content) is not None
        )
        assert has_non_empty_assertion, (
            "test_observability_roundtrip_e2e.py must assert traces are non-empty. "
            "Expected: assert len(traces) > 0, pytest.fail on empty traces, "
            "or equivalent non-empty guard."
        )

    @pytest.mark.requirement("WU4-AC4")
    def test_roundtrip_service_name_is_consistent(self) -> None:
        """Verify roundtrip test uses a consistent service name across real queries.

        The service name used in the Jaeger trace query must match
        the service name used elsewhere in the test to avoid querying
        for the wrong service and getting false negatives.

        Excludes sentinel/dummy service names used to test API functionality
        (e.g. 'non-existent-service').
        """
        content = TEST_ROUNDTRIP.read_text()

        # Extract all service name strings used in Jaeger queries
        # Pattern: "service": "<name>" or 'service': '<name>'
        # or params={"service": "<name>"}
        service_names_in_queries = re.findall(
            r'"service"[:\s]+["\']([^"\']+)["\']', content
        )

        assert len(service_names_in_queries) > 0, (
            "Could not find any service name in Jaeger queries. "
            "Test must query Jaeger with an explicit service name."
        )

        # Filter out sentinel/dummy names used in API validation tests
        sentinel_patterns = {"non-existent", "dummy", "test-only", "fake"}
        real_service_names = {
            name for name in service_names_in_queries
            if not any(sentinel in name.lower() for sentinel in sentinel_patterns)
        }

        assert len(real_service_names) > 0, (
            "No real service names found in Jaeger queries (all were sentinel values). "
            "Test must query Jaeger with the actual service name."
        )

        # All real service names used in queries should be the same
        assert len(real_service_names) == 1, (
            f"Roundtrip test uses multiple different service names in Jaeger queries: "
            f"{real_service_names}. "
            f"All queries should use the same service name for consistency."
        )

    @pytest.mark.requirement("WU4-AC4")
    def test_observability_test_queries_jaeger_with_service_param(self) -> None:
        """Verify test_observability.py also queries Jaeger with service parameter.

        Both E2E observability tests must query Jaeger properly.
        """
        content = TEST_OBSERVABILITY.read_text()

        assert "/api/traces" in content, (
            "test_observability.py must query Jaeger /api/traces endpoint"
        )
        assert '"service"' in content or "'service'" in content, (
            "test_observability.py must pass 'service' parameter to Jaeger trace query"
        )

    @pytest.mark.requirement("WU4-AC4")
    def test_service_names_aligned_across_e2e_tests(self) -> None:
        """Verify service names in Jaeger queries are aligned between E2E test files.

        If test_observability.py uses 'floe-platform' but the roundtrip test
        uses 'floe', traces emitted under one name will not be found by the
        other test. Both must query the same service name OR the actual
        TracerProvider must be configured to use the queried name.
        """
        obs_content = TEST_OBSERVABILITY.read_text()
        rt_content = TEST_ROUNDTRIP.read_text()

        # Extract service names from both files
        obs_service_names = set(re.findall(
            r'"service"[:\s]+["\']([^"\']+)["\']', obs_content
        ))
        rt_service_names = set(re.findall(
            r'"service"[:\s]+["\']([^"\']+)["\']', rt_content
        ))

        # Filter out obvious non-service-name strings like "non-existent-service"
        obs_real = {s for s in obs_service_names if "non-existent" not in s}
        rt_real = {s for s in rt_service_names if "non-existent" not in s}

        # Both test files should use the same service name(s) for querying
        # OR the roundtrip should be a subset (it may use fewer)
        if obs_real and rt_real:
            overlap = obs_real & rt_real
            assert len(overlap) > 0, (
                f"Service names in Jaeger queries are misaligned:\n"
                f"  test_observability.py uses: {obs_real}\n"
                f"  test_observability_roundtrip_e2e.py uses: {rt_real}\n"
                f"These must overlap so both tests query traces from the same service."
            )


class TestE2EConftestTracerProvider:
    """WU4-AC5: E2E conftest initializes OTel TracerProvider with OTLP exporter."""

    @pytest.mark.requirement("WU4-AC5")
    def test_conftest_imports_tracer_provider(self) -> None:
        """Verify E2E conftest imports TracerProvider from opentelemetry SDK.

        TracerProvider is required to create spans during E2E tests. Without
        it, no traces are emitted and observability tests cannot validate
        the full pipeline.
        """
        content = E2E_CONFTEST.read_text()

        assert "TracerProvider" in content, (
            "tests/e2e/conftest.py must import TracerProvider from "
            "opentelemetry.sdk.trace for OTel trace initialization. "
            "Currently missing -- E2E tests have no tracer configured."
        )

    @pytest.mark.requirement("WU4-AC5")
    def test_conftest_imports_otlp_exporter(self) -> None:
        """Verify E2E conftest imports OTLP span exporter.

        The TracerProvider must use an OTLP exporter to send spans to the
        OTel Collector. Without the exporter, spans are created but never
        sent anywhere.
        """
        content = E2E_CONFTEST.read_text()

        has_otlp_exporter = (
            "OTLPSpanExporter" in content
            or "otlp" in content.lower() and "exporter" in content.lower()
        )
        assert has_otlp_exporter, (
            "tests/e2e/conftest.py must import OTLPSpanExporter "
            "(from opentelemetry.exporter.otlp.proto.grpc.trace_exporter) "
            "to export spans to the OTel Collector. Currently missing."
        )

    @pytest.mark.requirement("WU4-AC5")
    def test_conftest_has_tracer_provider_fixture(self) -> None:
        """Verify E2E conftest defines a fixture that creates TracerProvider.

        A pytest fixture must exist that initializes TracerProvider and
        wires it with the OTLP exporter so E2E tests can emit real traces.
        """
        content = E2E_CONFTEST.read_text()

        # Parse the AST to find fixture-decorated functions that reference TracerProvider
        tree = ast.parse(content)

        fixture_functions: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function has @pytest.fixture decorator
                for decorator in node.decorator_list:
                    decorator_str = ast.dump(decorator)
                    if "fixture" in decorator_str:
                        fixture_functions.append(node.name)
                        break

        # Check if any fixture body contains TracerProvider
        tracer_fixture_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in fixture_functions:
                func_source = ast.get_source_segment(content, node)
                if func_source and "TracerProvider" in func_source:
                    tracer_fixture_found = True
                    break

        assert tracer_fixture_found, (
            f"tests/e2e/conftest.py must have a @pytest.fixture that creates "
            f"TracerProvider. Found fixtures: {fixture_functions}. "
            f"None of them initialize TracerProvider."
        )

    @pytest.mark.requirement("WU4-AC5")
    def test_conftest_tracer_uses_batch_processor(self) -> None:
        """Verify TracerProvider fixture uses BatchSpanProcessor for efficient export.

        SimpleSpanProcessor exports spans synchronously (blocks tests).
        BatchSpanProcessor batches and exports asynchronously, which is
        the correct choice for E2E tests that need non-blocking tracing.
        """
        content = E2E_CONFTEST.read_text()

        assert "BatchSpanProcessor" in content, (
            "tests/e2e/conftest.py must use BatchSpanProcessor with TracerProvider. "
            "SimpleSpanProcessor blocks on export; BatchSpanProcessor is non-blocking. "
            "Currently missing."
        )

    @pytest.mark.requirement("WU4-AC5")
    def test_conftest_tracer_sets_service_name(self) -> None:
        """Verify TracerProvider fixture sets a service.name resource attribute.

        Without service.name, traces appear in Jaeger under 'unknown_service'
        and cannot be found by the E2E tests that query by service name.
        """
        content = E2E_CONFTEST.read_text()

        has_service_name_config = (
            "service.name" in content
            or "service_name" in content
        )
        assert has_service_name_config, (
            "tests/e2e/conftest.py must configure service.name in TracerProvider "
            "Resource. Without it, traces appear as 'unknown_service' in Jaeger "
            "and E2E tests cannot find them. Currently missing."
        )
