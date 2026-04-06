"""Unit tests for standardized resource factory semantics (AC-1, AC-2, AC-3).

Parametrized tests asserting all 4 try_create_* factory functions follow
consistent behavior:
- Re-raise on configured-but-broken (AC-1)
- WARNING log for unconfigured plugins (AC-2)
- Structured log message format (AC-3)
"""

from __future__ import annotations

import logging
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins


def _plugins_with_iceberg() -> ResolvedPlugins:
    """ResolvedPlugins with catalog+storage configured."""
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=PluginRef(type="polaris", version="0.1.0", config={"uri": "http://polaris"}),
        storage=PluginRef(type="s3", version="1.0.0", config={"bucket": "test"}),
        ingestion=None,
        semantic=None,
    )


def _plugins_with_ingestion() -> ResolvedPlugins:
    """ResolvedPlugins with ingestion configured."""
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=PluginRef(type="dlt", version="0.1.0", config=None),
        semantic=None,
    )


def _plugins_with_semantic() -> ResolvedPlugins:
    """ResolvedPlugins with semantic configured."""
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=None,
        semantic=PluginRef(type="cube", version="0.1.0", config=None),
    )


def _plugins_with_lineage() -> ResolvedPlugins:
    """ResolvedPlugins with lineage_backend configured."""
    return ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="1.0.0", config=None),
        orchestrator=PluginRef(type="dagster", version="1.0.0", config=None),
        catalog=None,
        storage=None,
        ingestion=None,
        semantic=None,
        lineage_backend=PluginRef(type="marquez", version="0.1.0", config=None),
    )


# Each entry: (factory_import_path, factory_fn_name, configured_plugins_fn, resource_name)
_FACTORY_CASES: list[tuple[str, str, Any, str]] = [
    (
        "floe_orchestrator_dagster.resources.iceberg",
        "try_create_iceberg_resources",
        _plugins_with_iceberg,
        "iceberg",
    ),
    (
        "floe_orchestrator_dagster.resources.ingestion",
        "try_create_ingestion_resources",
        _plugins_with_ingestion,
        "ingestion",
    ),
    (
        "floe_orchestrator_dagster.resources.semantic",
        "try_create_semantic_resources",
        _plugins_with_semantic,
        "semantic",
    ),
    (
        "floe_orchestrator_dagster.resources.lineage",
        "try_create_lineage_resource",
        _plugins_with_lineage,
        "lineage",
    ),
]

_FACTORY_IDS = ["iceberg", "ingestion", "semantic", "lineage"]


@pytest.mark.requirement("AC-1")
@pytest.mark.parametrize(
    "module_path,fn_name,configured_plugins_fn,resource_name",
    _FACTORY_CASES,
    ids=_FACTORY_IDS,
)
def test_factory_reraises_on_configured_but_broken(
    module_path: str,
    fn_name: str,
    configured_plugins_fn: Any,
    resource_name: str,
) -> None:
    """All try_create_* functions MUST re-raise when configured but broken (AC-1).

    When a plugin IS configured in compiled_artifacts.json but fails to
    initialize, the exception MUST propagate — no silent swallowing.
    """
    import importlib

    mod = importlib.import_module(module_path)
    factory_fn = getattr(mod, fn_name)
    plugins = configured_plugins_fn()

    mock_registry = MagicMock()
    mock_registry.get.side_effect = ConnectionError("connection refused")

    # Lineage uses importlib module-level binding; others import inside functions
    patch_targets = ["floe_core.plugin_registry.get_registry"]
    mod_obj = importlib.import_module(module_path)
    if hasattr(mod_obj, "get_registry"):
        patch_targets.append(f"{module_path}.get_registry")

    with ExitStack() as stack:
        for t in patch_targets:
            stack.enter_context(patch(t, return_value=mock_registry))
        with pytest.raises(ConnectionError, match="connection refused"):
            factory_fn(plugins)


@pytest.mark.requirement("AC-2")
@pytest.mark.parametrize(
    "module_path,fn_name,configured_plugins_fn,resource_name",
    _FACTORY_CASES,
    ids=_FACTORY_IDS,
)
def test_factory_warns_on_unconfigured(
    module_path: str,
    fn_name: str,
    configured_plugins_fn: Any,
    resource_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """All try_create_* functions MUST log at WARNING for unconfigured plugins (AC-2).

    When a plugin is NOT configured, the factory MUST log at WARNING level
    with a structured message, not DEBUG.
    """
    import importlib

    mod = importlib.import_module(module_path)
    factory_fn = getattr(mod, fn_name)

    with caplog.at_level(logging.DEBUG):
        factory_fn(plugins=None)

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) >= 1, (
        f"{fn_name} did not emit a WARNING log when plugins=None. "
        f"Log records: {[(r.levelname, r.message) for r in caplog.records]}"
    )

    # Verify no DEBUG-level "skipping" messages remain
    debug_skipping = [
        r for r in caplog.records if r.levelno == logging.DEBUG and "skipping" in r.message.lower()
    ]
    assert len(debug_skipping) == 0, (
        f"{fn_name} still emits DEBUG 'skipping' messages: {[r.message for r in debug_skipping]}"
    )


@pytest.mark.requirement("AC-3")
@pytest.mark.parametrize(
    "module_path,fn_name,configured_plugins_fn,resource_name",
    _FACTORY_CASES,
    ids=_FACTORY_IDS,
)
def test_factory_uses_structured_log_keys(
    module_path: str,
    fn_name: str,
    configured_plugins_fn: Any,
    resource_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """All factories MUST use structured log keys: {resource}_not_configured (AC-3).

    Log messages for unconfigured plugins must follow the convention
    "{resource}_not_configured" (e.g., "iceberg_not_configured").
    """
    import importlib

    mod = importlib.import_module(module_path)
    factory_fn = getattr(mod, fn_name)

    expected_key = f"{resource_name}_not_configured"

    with caplog.at_level(logging.WARNING):
        factory_fn(plugins=None)

    messages = [r.message for r in caplog.records]
    assert any(expected_key in msg for msg in messages), (
        f"{fn_name} did not emit '{expected_key}' log message. Got: {messages}"
    )


@pytest.mark.requirement("AC-1")
@pytest.mark.parametrize(
    "module_path,fn_name,configured_plugins_fn,resource_name",
    _FACTORY_CASES,
    ids=_FACTORY_IDS,
)
def test_factory_returns_dict_for_unconfigured(
    module_path: str,
    fn_name: str,
    configured_plugins_fn: Any,
    resource_name: str,
) -> None:
    """All try_create_* functions MUST return dict when not configured (AC-1).

    Unconfigured factories return either {} or a dict with a NoOp resource
    (lineage always provides {"lineage": NoOp}).
    """
    import importlib

    mod = importlib.import_module(module_path)
    factory_fn = getattr(mod, fn_name)

    result = factory_fn(plugins=None)
    assert isinstance(result, dict), (
        f"{fn_name} returned {type(result)} instead of dict for unconfigured"
    )
