"""Shared plugin lifecycle observability helpers."""

from __future__ import annotations

from typing import Any

from floe_core.telemetry.context import _clean_value, _is_secret_key

PluginLifecycleAttributeValue = str | int | float | bool


def plugin_lifecycle_attributes(
    *,
    plugin_type: str,
    plugin_name: str,
    plugin_version: str,
    floe_api_version: str,
    phase: str,
    status: str,
    error_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, PluginLifecycleAttributeValue]:
    """Return secret-free attributes for plugin lifecycle telemetry."""
    attrs: dict[str, PluginLifecycleAttributeValue] = {
        "floe.plugin.type": plugin_type,
        "floe.plugin.name": plugin_name,
        "floe.plugin.version": plugin_version,
        "floe.plugin.floe_api_version": floe_api_version,
        "floe.plugin.lifecycle.phase": phase,
        "floe.plugin.lifecycle.status": status,
    }
    if error_type is not None:
        attrs["floe.error.type"] = error_type
    if extra:
        attrs.update(
            {key: _clean_value(value) for key, value in extra.items() if not _is_secret_key(key)}
        )
    return attrs


__all__ = ["PluginLifecycleAttributeValue", "plugin_lifecycle_attributes"]
