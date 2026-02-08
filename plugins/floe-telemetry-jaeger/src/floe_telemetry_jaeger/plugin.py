"""Jaeger telemetry backend plugin implementation.

Provides OTLP exporter configuration for Jaeger distributed tracing.

Contract Version: 1.0.0

Requirements Covered:
- FR-029: Jaeger backend for production tracing

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

import logging
import os
from typing import Any

from floe_core.plugins.telemetry import TelemetryBackendPlugin

logger = logging.getLogger(__name__)


class JaegerTelemetryPlugin(TelemetryBackendPlugin):
    """Jaeger telemetry backend plugin for production tracing.

    This plugin configures OpenTelemetry to export traces to Jaeger via OTLP.
    Jaeger is a distributed tracing platform that provides:
    - Trace visualization and analysis
    - Service dependency graphs
    - Performance optimization insights

    The plugin supports both gRPC and HTTP protocols for OTLP export.

    Example:
        >>> from floe_telemetry_jaeger import JaegerTelemetryPlugin
        >>> plugin = JaegerTelemetryPlugin()
        >>> plugin.get_otlp_exporter_config()
        {'exporter_type': 'otlp', 'endpoint': 'jaeger-collector:4317', ...}

    See Also:
        - TelemetryBackendPlugin: Abstract base class for telemetry plugins
        - ConsoleTelemetryPlugin: Development-focused console output
    """

    # Default Jaeger collector endpoint (gRPC)
    DEFAULT_ENDPOINT = "jaeger-collector:4317"

    @property
    def name(self) -> str:
        """Return the plugin name.

        Returns:
            "jaeger" - the unique identifier for this plugin.
        """
        return "jaeger"

    @property
    def version(self) -> str:
        """Return the plugin version.

        Returns:
            Current version following semver format.
        """
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Return the required floe API version.

        Returns:
            Minimum floe API version required by this plugin.
        """
        return "1.0"

    @property
    def description(self) -> str:
        """Return a human-readable description.

        Returns:
            Description of the Jaeger telemetry plugin.
        """
        return "Jaeger telemetry backend for production distributed tracing"

    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Return OTLP exporter configuration for Jaeger.

        Configures the OTLP exporter to send traces to Jaeger collector.
        Supports environment variable overrides:
        - OTEL_EXPORTER_OTLP_ENDPOINT: Collector endpoint
        - OTEL_EXPORTER_OTLP_INSECURE: Disable TLS (default: true for dev)

        Returns:
            OTLP exporter configuration dictionary.
        """
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", self.DEFAULT_ENDPOINT)
        insecure = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"

        return {
            "exporter_type": "otlp",
            "endpoint": endpoint,
            "insecure": insecure,
            "protocol": "grpc",
        }

    def get_helm_values(self) -> dict[str, Any]:
        """Return Helm values for Jaeger deployment.

        Provides configuration for deploying Jaeger as a self-hosted
        telemetry backend in Kubernetes.

        Returns:
            Helm chart values for Jaeger deployment.
        """
        return {
            "collector": {
                "resources": {
                    "limits": {"cpu": "500m", "memory": "512Mi"},
                    "requests": {"cpu": "100m", "memory": "128Mi"},
                }
            },
            "query": {
                "resources": {
                    "limits": {"cpu": "250m", "memory": "256Mi"},
                    "requests": {"cpu": "50m", "memory": "64Mi"},
                }
            },
            "storage": {
                "type": "memory",  # Default for dev; override for production
            },
        }

    def validate_connection(self) -> bool:
        """Validate connection to Jaeger backend.

        Attempts TCP connection to the configured OTLP endpoint to verify
        that the Jaeger collector is reachable.

        Returns:
            True if the Jaeger collector is reachable, False otherwise.

        Note:
            Uses TCP connectivity check rather than full OTLP handshake
            to avoid blocking on connection timeouts during configuration.
        """
        import socket

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", self.DEFAULT_ENDPOINT)

        # Parse host:port (handle http:// or https:// prefix)
        if "://" in endpoint:
            endpoint = endpoint.split("://", 1)[1]

        # Split host and port
        if ":" in endpoint:
            host, port_str = endpoint.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                # Invalid port format
                return False
        else:
            # No port specified, use default gRPC port
            host = endpoint
            port = 4317

        # Attempt TCP connection with timeout
        try:
            with socket.create_connection((host, port), timeout=5.0):
                return True
        except OSError:
            # Includes socket.gaierror (DNS), socket.timeout, connection refused
            return False
        except Exception as e:
            logger.warning("Unexpected error validating Jaeger connection: %s", e)
            return False
