"""Contract test: Resource factory semantics (AC-6).

Enforces that ALL try_create_* resource factory functions follow a
consistent contract:
- Return dict for "not configured" (plugins=None)
- Propagate exceptions for "configured but broken"
- Log at WARNING level when unconfigured
- Use structured log keys: {resource}_not_configured, {resource}_creation_failed

Adding a new factory without following this pattern will cause these
parametrized tests to fail.

Requirements:
    AC-6: Contract test enforces factory semantics for all factories
"""

from __future__ import annotations

import importlib
import logging
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

# ---------------------------------------------------------------------------
# Factory registry — add new factories here to enforce the contract
# ---------------------------------------------------------------------------

_FACTORIES: list[dict[str, Any]] = [
    {
        "id": "iceberg",
        "module": "floe_orchestrator_dagster.resources.iceberg",
        "function": "try_create_iceberg_resources",
        "configured_plugins": lambda: ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="1.0.0", config=None),
            orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
            catalog=PluginRef(type="polaris", version="0.1.0", config={"uri": "http://p"}),
            storage=PluginRef(type="s3", version="1.0.0", config={"bucket": "b"}),
            ingestion=None,
            semantic=None,
        ),
    },
    {
        "id": "ingestion",
        "module": "floe_orchestrator_dagster.resources.ingestion",
        "function": "try_create_ingestion_resources",
        "configured_plugins": lambda: ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="1.0.0", config=None),
            orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
            catalog=None,
            storage=None,
            ingestion=PluginRef(type="dlt", version="0.1.0", config=None),
            semantic=None,
        ),
    },
    {
        "id": "semantic",
        "module": "floe_orchestrator_dagster.resources.semantic",
        "function": "try_create_semantic_resources",
        "configured_plugins": lambda: ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="1.0.0", config=None),
            orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=PluginRef(type="cube", version="0.1.0", config=None),
        ),
    },
    {
        "id": "lineage",
        "module": "floe_orchestrator_dagster.resources.lineage",
        "function": "try_create_lineage_resource",
        "configured_plugins": lambda: ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="1.0.0", config=None),
            orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
            catalog=None,
            storage=None,
            ingestion=None,
            semantic=None,
            lineage_backend=PluginRef(type="marquez", version="0.1.0", config=None),
        ),
    },
]


def _get_factory(entry: dict[str, Any]) -> Any:
    """Import and return the factory function."""
    mod = importlib.import_module(entry["module"])
    return getattr(mod, entry["function"])


@pytest.fixture(params=_FACTORIES, ids=[f["id"] for f in _FACTORIES])
def factory_entry(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Parametrize across all resource factories."""
    return request.param


# ---------------------------------------------------------------------------
# Contract: unconfigured → returns dict
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-6")
def test_unconfigured_returns_dict(factory_entry: dict[str, Any]) -> None:
    """Factory returns dict when plugins=None (not configured).

    All factories MUST return a dict (either empty or with a NoOp resource)
    when no plugins are configured.
    """
    factory_fn = _get_factory(factory_entry)
    result = factory_fn(plugins=None)
    assert isinstance(result, dict), (
        f"{factory_entry['function']} returned {type(result).__name__}, expected dict"
    )


# ---------------------------------------------------------------------------
# Contract: configured but broken → propagates exception
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-6")
def test_configured_but_broken_propagates_exception(
    factory_entry: dict[str, Any],
) -> None:
    """Factory re-raises when plugin IS configured but initialization fails.

    All factories MUST propagate exceptions — no silent swallowing.
    """
    factory_fn = _get_factory(factory_entry)
    plugins = factory_entry["configured_plugins"]()

    mock_registry = MagicMock()
    mock_registry.get.side_effect = ConnectionError("connection refused")

    patch_targets = ["floe_core.plugin_registry.get_registry"]
    mod_obj = importlib.import_module(factory_entry["module"])
    if hasattr(mod_obj, "get_registry"):
        patch_targets.append(f"{factory_entry['module']}.get_registry")

    with ExitStack() as stack:
        for t in patch_targets:
            stack.enter_context(patch(t, return_value=mock_registry))
        with pytest.raises(ConnectionError, match="connection refused"):
            factory_fn(plugins)


# ---------------------------------------------------------------------------
# Contract: unconfigured → WARNING log level
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-6")
def test_unconfigured_logs_at_warning(
    factory_entry: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Factory logs at WARNING (not DEBUG) when unconfigured.

    All factories MUST emit a WARNING-level log when plugins are not configured.
    """
    factory_fn = _get_factory(factory_entry)

    with caplog.at_level(logging.DEBUG):
        factory_fn(plugins=None)

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) >= 1, (
        f"{factory_entry['function']} did not emit WARNING when unconfigured. "
        f"Records: {[(r.levelname, r.message) for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# Contract: structured log key format
# ---------------------------------------------------------------------------


@pytest.mark.requirement("AC-6")
def test_unconfigured_uses_structured_log_key(
    factory_entry: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Factory uses '{resource}_not_configured' log key format.

    All factories MUST use structured log keys following the convention
    {resource}_not_configured (e.g., "iceberg_not_configured").
    """
    factory_fn = _get_factory(factory_entry)
    resource_name = factory_entry["id"]
    expected_key = f"{resource_name}_not_configured"

    with caplog.at_level(logging.WARNING):
        factory_fn(plugins=None)

    messages = [r.message for r in caplog.records]
    assert any(expected_key in msg for msg in messages), (
        f"{factory_entry['function']} did not emit '{expected_key}'. Got: {messages}"
    )
