"""Contract test for plugin instrumentation completeness.

Verifies that all registered floe plugins (except telemetry backends) have
proper OpenTelemetry instrumentation via the ``tracer_name`` property, and
that tracer names follow the ``floe.{category}.{implementation}`` convention.

Requirements:
    FR-022: All plugins discoverable via entry points
    SC-001: 19 of 21 plugins have non-None tracer_name
"""

from __future__ import annotations

import re
from importlib.metadata import entry_points

import pytest

from floe_core.plugin_types import PluginType

# Entry point groups to audit (PluginType groups + network_security)
_PLUGIN_GROUPS: dict[str, str] = {
    pt.value: pt.name for pt in PluginType
}
_PLUGIN_GROUPS["floe.network_security"] = "NETWORK_SECURITY"

# Groups excluded from instrumentation requirement
_EXCLUDED_GROUPS: frozenset[str] = frozenset({
    PluginType.TELEMETRY_BACKEND.value,
})

# Naming convention: floe.{category}.{implementation}
_TRACER_NAME_PATTERN = re.compile(r"^floe\.[a-z]+\.[a-z][a-z0-9_]*$")

# Expected counts
_EXPECTED_TOTAL_PLUGINS = 21
_EXPECTED_INSTRUMENTED_PLUGINS = 19


@pytest.mark.requirement("FR-022")
@pytest.mark.requirement("SC-001")
class TestPluginInstrumentationContract:
    """Contract tests for plugin OTel instrumentation."""

    def test_total_registered_plugins(self) -> None:
        """All 21 plugins are discoverable via entry points."""
        total = 0
        for group in _PLUGIN_GROUPS:
            eps = entry_points(group=group)
            total += len(list(eps))

        assert total == _EXPECTED_TOTAL_PLUGINS, (
            f"Expected {_EXPECTED_TOTAL_PLUGINS} total registered plugins, "
            f"found {total}"
        )

    def test_instrumented_plugin_count(self) -> None:
        """19 of 21 plugins have non-None tracer_name."""
        instrumented = 0
        uninstrumented: list[str] = []

        for group, group_name in _PLUGIN_GROUPS.items():
            if group in _EXCLUDED_GROUPS:
                continue
            eps = entry_points(group=group)
            for ep in eps:
                cls = ep.load()
                # Check at class level (some plugins need config for __init__)
                has_tracer = any(
                    "tracer_name" in c.__dict__ and c.__name__ != "PluginMetadata"
                    for c in cls.__mro__
                )
                if has_tracer:
                    instrumented += 1
                else:
                    uninstrumented.append(f"{group_name}/{ep.name}")

        assert instrumented == _EXPECTED_INSTRUMENTED_PLUGINS, (
            f"Expected {_EXPECTED_INSTRUMENTED_PLUGINS} instrumented plugins, "
            f"found {instrumented}. Uninstrumented: {uninstrumented}"
        )
        assert uninstrumented == [], (
            f"Uninstrumented plugins found: {uninstrumented}"
        )

    def test_telemetry_backends_excluded(self) -> None:
        """Telemetry backends (console, jaeger) do NOT have tracer_name overridden."""
        eps = entry_points(group=PluginType.TELEMETRY_BACKEND.value)
        for ep in eps:
            cls = ep.load()
            has_tracer = any(
                "tracer_name" in c.__dict__ and c.__name__ != "PluginMetadata"
                for c in cls.__mro__
            )
            assert not has_tracer, (
                f"Telemetry backend '{ep.name}' should NOT override tracer_name "
                "(risk of infinite tracing loop)"
            )

    def test_tracer_name_naming_convention(self) -> None:
        """Each tracer_name follows 'floe.{category}.{implementation}' pattern."""
        violations: list[str] = []

        for group, group_name in _PLUGIN_GROUPS.items():
            if group in _EXCLUDED_GROUPS:
                continue
            eps = entry_points(group=group)
            for ep in eps:
                cls = ep.load()
                # Try to get tracer_name from a no-arg instance or class introspection
                tracer_name = _get_tracer_name_from_class(cls)
                if tracer_name is not None and not _TRACER_NAME_PATTERN.match(tracer_name):
                    violations.append(
                        f"{group_name}/{ep.name}: tracer_name='{tracer_name}' "
                        "does not match 'floe.{category}.{implementation}'"
                    )

        assert violations == [], (
            f"Tracer name convention violations:\n" + "\n".join(violations)
        )


def _get_tracer_name_from_class(cls: type) -> str | None:
    """Extract tracer_name from a plugin class without requiring instantiation.

    Tries no-arg instantiation first, then introspects the TRACER_NAME constant
    from the plugin's tracing module.

    Args:
        cls: Plugin class to inspect.

    Returns:
        The tracer_name string, or None if not available.
    """
    # Try no-arg instantiation (works for most plugins)
    try:
        instance = cls()
        return instance.tracer_name
    except TypeError:
        pass

    # Introspect: look for TRACER_NAME in the plugin's module's sibling tracing module
    module_name = cls.__module__
    package = module_name.rsplit(".", 1)[0] if "." in module_name else module_name
    tracing_module_name = f"{package}.tracing"

    try:
        import importlib

        tracing_mod = importlib.import_module(tracing_module_name)
        return getattr(tracing_mod, "TRACER_NAME", None)
    except (ImportError, ModuleNotFoundError):
        return None
