"""Unit tests for telemetry backend fixtures.

Tests for testing.fixtures.telemetry module including JaegerConfig,
OTLPCollectorConfig, and related utilities. Integration tests require Kind cluster.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from testing.fixtures.telemetry import (
    JaegerClient,
    JaegerConfig,
    OTLPCollectorConfig,
    TelemetryConnectionError,
    check_jaeger_health,
    check_otlp_collector_health,
    get_collector_connection_info,
    get_jaeger_connection_info,
    jaeger_context,
    otlp_collector_context,
)


class TestJaegerConfig:
    """Tests for JaegerConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = JaegerConfig()
        assert config.host == "jaeger"
        assert config.otlp_grpc_port == 4317
        assert config.otlp_http_port == 4318
        assert config.query_port == 16686
        assert config.namespace == "floe-test"

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = JaegerConfig(
            host="custom-jaeger",
            otlp_grpc_port=14317,
            otlp_http_port=14318,
            query_port=26686,
            namespace="custom-ns",
        )
        assert config.host == "custom-jaeger"
        assert config.otlp_grpc_port == 14317
        assert config.otlp_http_port == 14318
        assert config.query_port == 26686
        assert config.namespace == "custom-ns"

    def test_k8s_host_property(self) -> None:
        """Test K8s DNS host generation."""
        config = JaegerConfig(
            host="jaeger",
            namespace="test-ns",
        )
        expected = "jaeger.test-ns.svc.cluster.local"
        assert config.k8s_host == expected

    def test_otlp_grpc_endpoint_property(self) -> None:
        """Test OTLP gRPC endpoint generation."""
        config = JaegerConfig(
            host="jaeger",
            otlp_grpc_port=4317,
            namespace="test-ns",
        )
        expected = "jaeger.test-ns.svc.cluster.local:4317"
        assert config.otlp_grpc_endpoint == expected

    def test_otlp_http_endpoint_property(self) -> None:
        """Test OTLP HTTP endpoint generation."""
        config = JaegerConfig(
            host="jaeger",
            otlp_http_port=4318,
            namespace="test-ns",
        )
        expected = "http://jaeger.test-ns.svc.cluster.local:4318/v1/traces"
        assert config.otlp_http_endpoint == expected

    def test_query_url_property(self) -> None:
        """Test Query URL generation."""
        config = JaegerConfig(
            host="jaeger",
            query_port=16686,
            namespace="test-ns",
        )
        expected = "http://jaeger.test-ns.svc.cluster.local:16686"
        assert config.query_url == expected

    def test_frozen_model(self) -> None:
        """Test JaegerConfig is immutable."""
        config = JaegerConfig()
        with pytest.raises(ValidationError):
            config.host = "other-jaeger"

    def test_config_from_env(self) -> None:
        """Test config reads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "JAEGER_HOST": "env-jaeger",
                "JAEGER_OTLP_GRPC_PORT": "14317",
                "JAEGER_OTLP_HTTP_PORT": "14318",
                "JAEGER_QUERY_PORT": "26686",
            },
        ):
            config = JaegerConfig()
            assert config.host == "env-jaeger"
            assert config.otlp_grpc_port == 14317
            assert config.otlp_http_port == 14318
            assert config.query_port == 26686


class TestOTLPCollectorConfig:
    """Tests for OTLPCollectorConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = OTLPCollectorConfig()
        assert config.host == "otel-collector"
        assert config.grpc_port == 4317
        assert config.http_port == 4318
        assert config.namespace == "floe-test"

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = OTLPCollectorConfig(
            host="custom-collector",
            grpc_port=14317,
            http_port=14318,
            namespace="custom-ns",
        )
        assert config.host == "custom-collector"
        assert config.grpc_port == 14317
        assert config.http_port == 14318
        assert config.namespace == "custom-ns"

    def test_k8s_host_property(self) -> None:
        """Test K8s DNS host generation."""
        config = OTLPCollectorConfig(
            host="otel-collector",
            namespace="test-ns",
        )
        expected = "otel-collector.test-ns.svc.cluster.local"
        assert config.k8s_host == expected

    def test_grpc_endpoint_property(self) -> None:
        """Test gRPC endpoint generation."""
        config = OTLPCollectorConfig(
            host="otel-collector",
            grpc_port=4317,
            namespace="test-ns",
        )
        expected = "otel-collector.test-ns.svc.cluster.local:4317"
        assert config.grpc_endpoint == expected

    def test_http_endpoint_property(self) -> None:
        """Test HTTP endpoint generation."""
        config = OTLPCollectorConfig(
            host="otel-collector",
            http_port=4318,
            namespace="test-ns",
        )
        expected = "http://otel-collector.test-ns.svc.cluster.local:4318/v1/traces"
        assert config.http_endpoint == expected

    def test_frozen_model(self) -> None:
        """Test OTLPCollectorConfig is immutable."""
        config = OTLPCollectorConfig()
        with pytest.raises(ValidationError):
            config.host = "other-collector"

    def test_config_from_env(self) -> None:
        """Test config reads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "OTEL_COLLECTOR_HOST": "env-collector",
                "OTEL_COLLECTOR_GRPC_PORT": "14317",
                "OTEL_COLLECTOR_HTTP_PORT": "14318",
            },
        ):
            config = OTLPCollectorConfig()
            assert config.host == "env-collector"
            assert config.grpc_port == 14317
            assert config.http_port == 14318


class TestJaegerClient:
    """Tests for JaegerClient class."""

    def test_client_creation(self) -> None:
        """Test JaegerClient can be created with config."""
        config = JaegerConfig()
        client = JaegerClient(config=config)
        assert client.config == config

    def test_get_services_raises_on_missing_requests(self) -> None:
        """Test get_services raises helpful error when requests not installed."""
        config = JaegerConfig()
        client = JaegerClient(config=config)

        with patch.dict("sys.modules", {"requests": None}):
            with pytest.raises(TelemetryConnectionError) as exc_info:
                client.get_services()
            assert "requests not installed" in str(exc_info.value)

    def test_get_services_success(self) -> None:
        """Test get_services returns service list on success."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": ["service-a", "service-b"]}
        mock_requests.get.return_value = mock_response

        with patch.dict("sys.modules", {"requests": mock_requests}):
            config = JaegerConfig()
            client = JaegerClient(config=config)
            services = client.get_services()

            assert services == ["service-a", "service-b"]
            mock_requests.get.assert_called_once()

    def test_get_traces_raises_on_missing_requests(self) -> None:
        """Test get_traces raises helpful error when requests not installed."""
        config = JaegerConfig()
        client = JaegerClient(config=config)

        with patch.dict("sys.modules", {"requests": None}):
            with pytest.raises(TelemetryConnectionError) as exc_info:
                client.get_traces(service="test-service")
            assert "requests not installed" in str(exc_info.value)

    def test_get_traces_success(self) -> None:
        """Test get_traces returns trace data on success."""
        mock_requests = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"traceID": "abc123", "spans": []}]
        }
        mock_requests.get.return_value = mock_response

        with patch.dict("sys.modules", {"requests": mock_requests}):
            config = JaegerConfig()
            client = JaegerClient(config=config)
            traces = client.get_traces(service="test-service", limit=10)

            assert len(traces) == 1
            assert traces[0]["traceID"] == "abc123"


class TestJaegerContext:
    """Tests for jaeger_context context manager."""

    def test_context_yields_client(self) -> None:
        """Test context manager yields JaegerClient."""
        with jaeger_context() as client:
            assert isinstance(client, JaegerClient)
            assert isinstance(client.config, JaegerConfig)

    def test_context_with_custom_config(self) -> None:
        """Test context manager uses provided config."""
        custom_config = JaegerConfig(host="custom-jaeger")
        with jaeger_context(config=custom_config) as client:
            assert client.config.host == "custom-jaeger"


class TestOTLPCollectorContext:
    """Tests for otlp_collector_context context manager."""

    def test_context_yields_config(self) -> None:
        """Test context manager yields OTLPCollectorConfig."""
        with otlp_collector_context() as config:
            assert isinstance(config, OTLPCollectorConfig)

    def test_context_with_custom_config(self) -> None:
        """Test context manager uses provided config."""
        custom_config = OTLPCollectorConfig(host="custom-collector")
        with otlp_collector_context(config=custom_config) as config:
            assert config.host == "custom-collector"


class TestHealthChecks:
    """Tests for health check functions."""

    def test_check_jaeger_health_returns_false_on_error(self) -> None:
        """Test check_jaeger_health returns False when Jaeger unavailable."""
        config = JaegerConfig(host="nonexistent-host")
        # Will fail to connect, should return False
        result = check_jaeger_health(config, timeout=0.1)
        assert result is False

    def test_check_otlp_collector_health_returns_false_on_error(self) -> None:
        """Test check_otlp_collector_health returns False when collector unavailable."""
        config = OTLPCollectorConfig(host="nonexistent-host")
        # Will fail to connect, should return False
        result = check_otlp_collector_health(config, timeout=0.1)
        assert result is False


class TestConnectionInfo:
    """Tests for connection info functions."""

    def test_get_jaeger_connection_info(self) -> None:
        """Test get_jaeger_connection_info returns expected fields."""
        config = JaegerConfig(
            host="test-jaeger",
            otlp_grpc_port=4317,
            query_port=16686,
            namespace="test-ns",
        )
        info = get_jaeger_connection_info(config)

        assert info["host"] == "test-jaeger"
        assert info["k8s_host"] == "test-jaeger.test-ns.svc.cluster.local"
        assert info["otlp_grpc_port"] == 4317
        assert info["query_port"] == 16686
        assert info["namespace"] == "test-ns"
        assert "otlp_grpc_endpoint" in info
        assert "query_url" in info

    def test_get_collector_connection_info(self) -> None:
        """Test get_collector_connection_info returns expected fields."""
        config = OTLPCollectorConfig(
            host="test-collector",
            grpc_port=4317,
            http_port=4318,
            namespace="test-ns",
        )
        info = get_collector_connection_info(config)

        assert info["host"] == "test-collector"
        assert info["k8s_host"] == "test-collector.test-ns.svc.cluster.local"
        assert info["grpc_port"] == 4317
        assert info["http_port"] == 4318
        assert info["namespace"] == "test-ns"
        assert "grpc_endpoint" in info
        assert "http_endpoint" in info
