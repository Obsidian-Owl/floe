"""Telemetry backend pytest fixtures for integration tests.

Provides configuration and context managers for OpenTelemetry backend services
(Jaeger, OTLP Collector) running in Kind cluster.

Example:
    from testing.fixtures.telemetry import jaeger_context, JaegerConfig

    def test_with_jaeger(jaeger_client):
        # Send trace to Jaeger
        with tracer.start_as_current_span("test-span"):
            pass
        # Query traces via Jaeger API
        traces = jaeger_client.get_traces(service="test-service")
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JaegerConfig(BaseModel):
    """Configuration for Jaeger tracing backend.

    Attributes:
        host: Jaeger host. Defaults to K8s service name.
        otlp_grpc_port: OTLP gRPC receiver port (4317).
        otlp_http_port: OTLP HTTP receiver port (4318).
        query_port: Jaeger Query API port (16686).
        namespace: K8s namespace where Jaeger runs.
    """

    model_config = ConfigDict(frozen=True)

    host: str = Field(default_factory=lambda: os.environ.get("JAEGER_HOST", "jaeger"))
    otlp_grpc_port: int = Field(
        default_factory=lambda: int(os.environ.get("JAEGER_OTLP_GRPC_PORT", "4317"))
    )
    otlp_http_port: int = Field(
        default_factory=lambda: int(os.environ.get("JAEGER_OTLP_HTTP_PORT", "4318"))
    )
    query_port: int = Field(
        default_factory=lambda: int(os.environ.get("JAEGER_QUERY_PORT", "16686"))
    )
    namespace: str = Field(default="floe-test")

    @property
    def k8s_host(self) -> str:
        """Get fully qualified K8s DNS name."""
        return f"{self.host}.{self.namespace}.svc.cluster.local"

    @property
    def otlp_grpc_endpoint(self) -> str:
        """Get OTLP gRPC endpoint URL."""
        return f"{self.k8s_host}:{self.otlp_grpc_port}"

    @property
    def otlp_http_endpoint(self) -> str:
        """Get OTLP HTTP endpoint URL."""
        return f"http://{self.k8s_host}:{self.otlp_http_port}/v1/traces"

    @property
    def query_url(self) -> str:
        """Get Jaeger Query API URL."""
        return f"http://{self.k8s_host}:{self.query_port}"


class OTLPCollectorConfig(BaseModel):
    """Configuration for OTLP Collector.

    Attributes:
        host: Collector host. Defaults to K8s service name.
        grpc_port: OTLP gRPC port (4317).
        http_port: OTLP HTTP port (4318).
        namespace: K8s namespace where collector runs.
    """

    model_config = ConfigDict(frozen=True)

    host: str = Field(
        default_factory=lambda: os.environ.get("OTEL_COLLECTOR_HOST", "otel-collector")
    )
    grpc_port: int = Field(
        default_factory=lambda: int(os.environ.get("OTEL_COLLECTOR_GRPC_PORT", "4317"))
    )
    http_port: int = Field(
        default_factory=lambda: int(os.environ.get("OTEL_COLLECTOR_HTTP_PORT", "4318"))
    )
    namespace: str = Field(default="floe-test")

    @property
    def k8s_host(self) -> str:
        """Get fully qualified K8s DNS name."""
        return f"{self.host}.{self.namespace}.svc.cluster.local"

    @property
    def grpc_endpoint(self) -> str:
        """Get gRPC endpoint URL."""
        return f"{self.k8s_host}:{self.grpc_port}"

    @property
    def http_endpoint(self) -> str:
        """Get HTTP endpoint URL."""
        return f"http://{self.k8s_host}:{self.http_port}/v1/traces"


class TelemetryConnectionError(Exception):
    """Raised when telemetry backend connection fails."""

    pass


@dataclass(frozen=True)
class JaegerClient:
    """Client for querying Jaeger traces.

    Provides methods to query traces from Jaeger Query API.
    Used in integration tests to verify trace export.

    Attributes:
        config: Jaeger configuration.
    """

    config: JaegerConfig

    def get_services(self) -> list[str]:
        """Get list of services with traces.

        Returns:
            List of service names.

        Raises:
            TelemetryConnectionError: If Jaeger is unavailable.
        """
        try:
            import requests
        except ImportError as e:
            raise TelemetryConnectionError(
                "requests not installed. Install with: pip install requests"
            ) from e

        try:
            response = requests.get(
                f"{self.config.query_url}/api/services",
                timeout=5.0,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            result: list[str] = data.get("data", [])
            return result
        except Exception as e:
            raise TelemetryConnectionError(
                f"Failed to query Jaeger services at {self.config.query_url}: {e}"
            ) from e

    def get_traces(
        self,
        service: str,
        *,
        limit: int = 20,
        lookback: str = "1h",
    ) -> list[dict[str, Any]]:
        """Get traces for a service.

        Args:
            service: Service name to query.
            limit: Maximum number of traces. Defaults to 20.
            lookback: Time range to search. Defaults to "1h".

        Returns:
            List of trace data dictionaries.

        Raises:
            TelemetryConnectionError: If Jaeger is unavailable.
        """
        try:
            import requests
        except ImportError as e:
            raise TelemetryConnectionError(
                "requests not installed. Install with: pip install requests"
            ) from e

        try:
            params: dict[str, str | int] = {
                "service": service,
                "limit": limit,
                "lookback": lookback,
            }
            response = requests.get(
                f"{self.config.query_url}/api/traces",
                params=params,
                timeout=5.0,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            result: list[dict[str, Any]] = data.get("data", [])
            return result
        except Exception as e:
            raise TelemetryConnectionError(
                f"Failed to query Jaeger traces at {self.config.query_url}: {e}"
            ) from e


def check_jaeger_health(config: JaegerConfig, timeout: float = 5.0) -> bool:
    """Check if Jaeger is healthy.

    Args:
        config: Jaeger configuration.
        timeout: Request timeout in seconds.

    Returns:
        True if Jaeger is responding, False otherwise.
    """
    try:
        import requests

        response = requests.get(
            f"{config.query_url}/",
            timeout=timeout,
        )
        is_healthy: bool = response.status_code == 200
        return is_healthy
    except Exception:
        return False


def check_otlp_collector_health(config: OTLPCollectorConfig, timeout: float = 5.0) -> bool:
    """Check if OTLP Collector is healthy.

    Uses TCP check on gRPC port since collector may not have HTTP health endpoint.

    Args:
        config: OTLP Collector configuration.
        timeout: Connection timeout in seconds.

    Returns:
        True if collector is responding, False otherwise.
    """
    import socket

    try:
        with socket.create_connection((config.k8s_host, config.grpc_port), timeout=timeout):
            return True
    except OSError:
        return False


@contextmanager
def jaeger_context(
    config: JaegerConfig | None = None,
) -> Generator[JaegerClient, None, None]:
    """Context manager for Jaeger client.

    Creates JaegerClient on entry. No cleanup needed on exit.

    Args:
        config: Optional JaegerConfig. Uses defaults if not provided.

    Yields:
        JaegerClient instance.

    Example:
        with jaeger_context() as client:
            traces = client.get_traces(service="my-service")
    """
    if config is None:
        config = JaegerConfig()

    client = JaegerClient(config=config)
    yield client
    # JaegerClient is stateless, no cleanup needed


@contextmanager
def otlp_collector_context(
    config: OTLPCollectorConfig | None = None,
) -> Generator[OTLPCollectorConfig, None, None]:
    """Context manager for OTLP Collector configuration.

    Provides config for OTLP exporter setup.

    Args:
        config: Optional OTLPCollectorConfig. Uses defaults if not provided.

    Yields:
        OTLPCollectorConfig instance.

    Example:
        with otlp_collector_context() as config:
            exporter = OTLPSpanExporter(endpoint=config.grpc_endpoint)
    """
    if config is None:
        config = OTLPCollectorConfig()

    yield config
    # Config is immutable, no cleanup needed


def get_jaeger_connection_info(config: JaegerConfig) -> dict[str, Any]:
    """Get connection info dictionary (for logging/debugging).

    Args:
        config: Jaeger configuration.

    Returns:
        Dictionary with connection info.
    """
    return {
        "host": config.host,
        "k8s_host": config.k8s_host,
        "otlp_grpc_port": config.otlp_grpc_port,
        "otlp_http_port": config.otlp_http_port,
        "query_port": config.query_port,
        "otlp_grpc_endpoint": config.otlp_grpc_endpoint,
        "otlp_http_endpoint": config.otlp_http_endpoint,
        "query_url": config.query_url,
        "namespace": config.namespace,
    }


def get_collector_connection_info(config: OTLPCollectorConfig) -> dict[str, Any]:
    """Get connection info dictionary (for logging/debugging).

    Args:
        config: OTLP Collector configuration.

    Returns:
        Dictionary with connection info.
    """
    return {
        "host": config.host,
        "k8s_host": config.k8s_host,
        "grpc_port": config.grpc_port,
        "http_port": config.http_port,
        "grpc_endpoint": config.grpc_endpoint,
        "http_endpoint": config.http_endpoint,
        "namespace": config.namespace,
    }


__all__ = [
    "JaegerClient",
    "JaegerConfig",
    "OTLPCollectorConfig",
    "TelemetryConnectionError",
    "check_jaeger_health",
    "check_otlp_collector_health",
    "get_collector_connection_info",
    "get_jaeger_connection_info",
    "jaeger_context",
    "otlp_collector_context",
]
