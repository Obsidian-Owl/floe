"""Console telemetry backend plugin implementation.

Provides a ConsoleSpanExporter for local development and debugging.
Traces are printed to stdout in a human-readable format.

Contract Version: 1.0.0

Requirements Covered:
- FR-027: Console backend for local development

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

from typing import Any

from floe_core.plugins.telemetry import TelemetryBackendPlugin


class ConsoleTelemetryPlugin(TelemetryBackendPlugin):
    """Console telemetry backend plugin for local development.

    This plugin configures OpenTelemetry to output traces to the console
    instead of sending them to an OTLP Collector. This is useful for:
    - Local development and debugging
    - Quick verification of trace instrumentation
    - Environments where no OTLP Collector is available

    The console backend does not require any external services or Helm
    deployment, making it ideal for getting started quickly.

    Example:
        >>> from floe_telemetry_console import ConsoleTelemetryPlugin
        >>> plugin = ConsoleTelemetryPlugin()
        >>> plugin.validate_connection()
        True
        >>> plugin.get_otlp_exporter_config()
        {'exporter_type': 'console'}

    See Also:
        - TelemetryBackendPlugin: Abstract base class for telemetry plugins
        - JaegerTelemetryPlugin: Production-ready telemetry backend
    """

    @property
    def name(self) -> str:
        """Return the plugin name.

        Returns:
            "console" - the unique identifier for this plugin.
        """
        return "console"

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
            Description of the console telemetry plugin.
        """
        return "Console telemetry backend for local development and debugging"

    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Return console exporter configuration.

        The console backend does not use OTLP Collector - instead it
        configures a ConsoleSpanExporter directly in the SDK.

        Returns:
            Configuration indicating console exporter type.
        """
        return {"exporter_type": "console"}

    def get_helm_values(self) -> dict[str, Any]:
        """Return Helm values for deployment.

        The console backend does not require any Kubernetes resources
        since it outputs directly to stdout.

        Returns:
            Empty dict - no Helm deployment needed.
        """
        return {}

    def validate_connection(self) -> bool:
        """Validate the console backend is available.

        Console output is always available (stdout is always present),
        so this always returns True.

        Returns:
            True - console is always available.
        """
        return True
