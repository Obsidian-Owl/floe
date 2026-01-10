"""Integration tests for JaegerTelemetryPlugin.

Tests verify actual connectivity and OTLP export to Jaeger collector.

Contract Version: 1.0.0

Requirements Covered:
- FR-029: Jaeger backend for production tracing

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase

if TYPE_CHECKING:
    from floe_telemetry_jaeger import JaegerTelemetryPlugin


class TestJaegerPluginIntegration(IntegrationTestBase):
    """Integration tests for Jaeger telemetry plugin with real Jaeger collector.

    These tests require a running Jaeger collector accessible via gRPC.
    The collector must be deployed in the K8s cluster and accessible
    via localhost:4317 (NodePort mapping) or OTEL_EXPORTER_OTLP_ENDPOINT.
    """

    # Don't use cluster DNS - we connect via NodePort from host
    required_services: list[tuple[str, int]] = []

    def setup_method(self) -> None:
        """Set up test fixtures, checking localhost connectivity."""
        import socket

        super().setup_method()

        # Check Jaeger is accessible via NodePort (localhost:4317)
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
        if "://" in endpoint:
            endpoint = endpoint.split("://", 1)[1]
        host, port_str = endpoint.rsplit(":", 1) if ":" in endpoint else (endpoint, "4317")

        try:
            with socket.create_connection((host, int(port_str)), timeout=5.0):
                pass  # Connection succeeded
        except OSError as e:
            pytest.fail(
                f"Jaeger not accessible at {host}:{port_str}: {e}\n"
                f"Ensure Kind cluster has Jaeger deployed: make kind-up"
            )

    @pytest.fixture
    def plugin(self) -> JaegerTelemetryPlugin:
        """Create JaegerTelemetryPlugin instance for testing.

        Returns:
            Configured JaegerTelemetryPlugin instance.
        """
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        return JaegerTelemetryPlugin()

    @pytest.fixture
    def jaeger_endpoint(self) -> str:
        """Get Jaeger collector endpoint for tests.

        Uses environment variable if set, otherwise uses localhost
        which is mapped via NodePort in Kind cluster.

        Returns:
            Endpoint string in host:port format.
        """
        return os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "localhost:4317",
        )

    @pytest.mark.requirement("FR-029")
    @pytest.mark.integration
    def test_validate_connection_with_real_jaeger(
        self,
        plugin: JaegerTelemetryPlugin,
        jaeger_endpoint: str,
    ) -> None:
        """Test validate_connection returns True with real Jaeger collector.

        Verifies that the plugin can establish a TCP connection to the
        running Jaeger collector.
        """
        # Set endpoint environment variable for plugin
        original = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = jaeger_endpoint

        try:
            result = plugin.validate_connection()
            assert result is True, (
                f"validate_connection() returned False for endpoint {jaeger_endpoint}. "
                "Ensure Jaeger collector is running and accessible."
            )
        finally:
            # Cleanup environment
            if original is None:
                os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            else:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original

    @pytest.mark.requirement("FR-029")
    @pytest.mark.integration
    def test_validate_connection_fails_with_invalid_endpoint(
        self,
        plugin: JaegerTelemetryPlugin,
    ) -> None:
        """Test validate_connection returns False with unreachable endpoint.

        Verifies that the plugin correctly handles connection failures
        when the configured endpoint is not reachable.
        """
        original = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "nonexistent-jaeger-host:4317"

        try:
            result = plugin.validate_connection()
            assert result is False, (
                "validate_connection() returned True for nonexistent endpoint. "
                "Expected False for unreachable hosts."
            )
        finally:
            if original is None:
                os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            else:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original

    @pytest.mark.requirement("FR-029")
    @pytest.mark.integration
    def test_otlp_exporter_config_uses_configured_endpoint(
        self,
        plugin: JaegerTelemetryPlugin,
        jaeger_endpoint: str,
    ) -> None:
        """Test OTLP exporter config uses configured endpoint.

        Verifies that the exporter configuration reflects the
        environment-configured endpoint.
        """
        original = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = jaeger_endpoint

        try:
            config: dict[str, Any] = plugin.get_otlp_exporter_config()

            assert config["endpoint"] == jaeger_endpoint
            assert config["exporter_type"] == "otlp"
            assert config["protocol"] == "grpc"
        finally:
            if original is None:
                os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            else:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original

    @pytest.mark.requirement("FR-029")
    @pytest.mark.integration
    def test_plugin_lifecycle_with_real_jaeger(
        self,
        plugin: JaegerTelemetryPlugin,
    ) -> None:
        """Test plugin startup/shutdown lifecycle with real Jaeger.

        Verifies that the plugin can complete its lifecycle (startup,
        health check, shutdown) when connected to a real Jaeger instance.
        """
        from floe_core.plugin_metadata import HealthState

        # Startup should not raise
        plugin.startup()

        try:
            # Health check should be healthy
            health = plugin.health_check()
            assert health.state == HealthState.HEALTHY, (
                f"Expected HEALTHY state after startup, got {health.state}"
            )
        finally:
            # Shutdown should not raise
            plugin.shutdown()

    @pytest.mark.requirement("FR-029")
    @pytest.mark.integration
    def test_plugin_helm_values_for_k8s_deployment(
        self,
        plugin: JaegerTelemetryPlugin,
    ) -> None:
        """Test get_helm_values returns valid K8s deployment configuration.

        Verifies that the Helm values contain valid resource specifications
        for deploying Jaeger in a K8s environment.
        """
        values: dict[str, Any] = plugin.get_helm_values()

        # Should have collector configuration
        assert "collector" in values, "Helm values should include collector config"

        # Collector should have resource limits
        collector = values["collector"]
        assert "resources" in collector, "Collector should have resource limits"
        assert "limits" in collector["resources"]
        assert "requests" in collector["resources"]

        # Should have storage configuration
        assert "storage" in values, "Helm values should include storage config"
        assert "type" in values["storage"]
