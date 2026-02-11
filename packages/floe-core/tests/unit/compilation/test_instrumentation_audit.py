"""Tests for plugin instrumentation audit.

Validates that ``verify_plugin_instrumentation()`` correctly identifies
plugins missing OpenTelemetry instrumentation and properly skips
telemetry backends to prevent infinite tracing loops.

Requirements:
    FR-016: verify_plugin_instrumentation() returns uninstrumented warnings
    FR-017: Compile pipeline emits warnings for uninstrumented plugins
"""

from __future__ import annotations

import pytest

from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugin_types import PluginType
from floe_core.telemetry.audit import verify_plugin_instrumentation

# ---------------------------------------------------------------------------
# Test plugin stubs
# ---------------------------------------------------------------------------


class _InstrumentedPlugin(PluginMetadata):
    """Plugin stub with tracer_name set."""

    def __init__(self, name: str = "instrumented", tracer: str = "floe.test.plugin") -> None:
        self._name = name
        self._tracer = tracer

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    @property
    def tracer_name(self) -> str | None:
        return self._tracer


class _UninstrumentedPlugin(PluginMetadata):
    """Plugin stub without tracer_name (returns default None)."""

    def __init__(self, name: str = "uninstrumented") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.requirement("FR-016")
class TestVerifyPluginInstrumentation:
    """Tests for verify_plugin_instrumentation()."""

    def test_all_instrumented_returns_no_warnings(self) -> None:
        """All plugins with tracer_name set should yield zero warnings."""
        plugins: list[tuple[PluginType, PluginMetadata]] = [
            (PluginType.COMPUTE, _InstrumentedPlugin("duckdb", "floe.compute.duckdb")),
            (PluginType.CATALOG, _InstrumentedPlugin("polaris", "floe.catalog.polaris")),
            (PluginType.ORCHESTRATOR, _InstrumentedPlugin("dagster", "floe.orchestrator.dagster")),
        ]

        warnings = verify_plugin_instrumentation(plugins)

        assert warnings == []

    def test_uninstrumented_plugin_yields_warning(self) -> None:
        """A plugin without tracer_name should produce a warning with name and type."""
        plugins: list[tuple[PluginType, PluginMetadata]] = [
            (PluginType.COMPUTE, _InstrumentedPlugin("duckdb", "floe.compute.duckdb")),
            (PluginType.CATALOG, _UninstrumentedPlugin("missing-tracer")),
        ]

        warnings = verify_plugin_instrumentation(plugins)

        assert len(warnings) == 1
        assert "missing-tracer" in warnings[0]
        assert "CATALOG" in warnings[0]
        assert "tracer_name is None" in warnings[0]

    def test_multiple_uninstrumented_plugins(self) -> None:
        """Multiple uninstrumented plugins should yield one warning each."""
        plugins: list[tuple[PluginType, PluginMetadata]] = [
            (PluginType.COMPUTE, _UninstrumentedPlugin("bad-compute")),
            (PluginType.CATALOG, _UninstrumentedPlugin("bad-catalog")),
            (PluginType.ORCHESTRATOR, _InstrumentedPlugin("dagster", "floe.orchestrator.dagster")),
        ]

        warnings = verify_plugin_instrumentation(plugins)

        assert len(warnings) == 2
        plugin_names = {w.split("'")[1] for w in warnings}
        assert plugin_names == {"bad-compute", "bad-catalog"}

    def test_telemetry_backends_skipped(self) -> None:
        """Telemetry backend plugins should be excluded from audit."""
        plugins: list[tuple[PluginType, PluginMetadata]] = [
            (PluginType.TELEMETRY_BACKEND, _UninstrumentedPlugin("console")),
            (PluginType.TELEMETRY_BACKEND, _UninstrumentedPlugin("jaeger")),
            (PluginType.COMPUTE, _InstrumentedPlugin("duckdb", "floe.compute.duckdb")),
        ]

        warnings = verify_plugin_instrumentation(plugins)

        assert warnings == []

    def test_empty_plugin_list(self) -> None:
        """Empty plugin list should return empty warnings."""
        warnings = verify_plugin_instrumentation([])

        assert warnings == []

    def test_callable_programmatically(self) -> None:
        """Audit function should be callable with any Sequence of tuples."""
        # Verify it works with a tuple (not just list)
        plugins = ((PluginType.COMPUTE, _InstrumentedPlugin("duckdb", "floe.compute.duckdb")),)

        warnings = verify_plugin_instrumentation(plugins)

        assert warnings == []
