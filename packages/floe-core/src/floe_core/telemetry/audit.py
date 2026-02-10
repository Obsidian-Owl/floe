"""Plugin instrumentation audit for the floe platform.

This module provides utilities to verify that all registered plugins have
proper OpenTelemetry instrumentation. The audit checks that each plugin
reports a ``tracer_name`` via the ``PluginMetadata`` property, which signals
that the plugin creates OTel spans for its operations.

Telemetry backend plugins (e.g., console, jaeger) are excluded from the
audit to prevent infinite tracing loops.

Requirements:
    FR-016: verify_plugin_instrumentation() returns uninstrumented warnings
    FR-017: Compile pipeline emits warnings for uninstrumented plugins

Example:
    >>> from floe_core.telemetry.audit import verify_plugin_instrumentation
    >>> warnings = verify_plugin_instrumentation(plugins)
    >>> if warnings:
    ...     for w in warnings:
    ...         print(w)
"""

from __future__ import annotations

from collections.abc import Sequence

import structlog

from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugin_types import PluginType

logger = structlog.get_logger(__name__)

# Plugin types excluded from instrumentation audit.
# Telemetry backends must NOT trace themselves (infinite loop).
_EXCLUDED_PLUGIN_TYPES: frozenset[PluginType] = frozenset({
    PluginType.TELEMETRY_BACKEND,
})


def verify_plugin_instrumentation(
    plugins: Sequence[tuple[PluginType, PluginMetadata]],
) -> list[str]:
    """Check that all non-excluded plugins have OpenTelemetry instrumentation.

    Iterates over a list of (plugin_type, plugin_metadata) tuples and checks
    that each plugin's ``tracer_name`` property returns a non-None value.
    Plugins whose type is in the excluded set (e.g., telemetry backends) are
    skipped to prevent infinite tracing loops.

    Args:
        plugins: Sequence of (PluginType, PluginMetadata) tuples to audit.

    Returns:
        List of warning messages for uninstrumented plugins. Empty list
        means all auditable plugins are properly instrumented.

    Example:
        >>> from floe_core.plugin_types import PluginType
        >>> warnings = verify_plugin_instrumentation([
        ...     (PluginType.COMPUTE, my_compute_plugin),
        ...     (PluginType.TELEMETRY_BACKEND, my_telemetry_plugin),
        ... ])
    """
    warnings: list[str] = []

    for plugin_type, plugin in plugins:
        if plugin_type in _EXCLUDED_PLUGIN_TYPES:
            logger.debug(
                "audit_plugin_skipped",
                plugin_name=plugin.name,
                plugin_type=plugin_type.name,
                reason="excluded_type",
            )
            continue

        if plugin.tracer_name is None:
            msg = (
                f"Plugin '{plugin.name}' (type={plugin_type.name}) "
                "is not instrumented (tracer_name is None)"
            )
            warnings.append(msg)

    return warnings
