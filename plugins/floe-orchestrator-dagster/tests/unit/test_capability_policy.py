"""Tests for alpha capability policy."""

from __future__ import annotations

import pytest
from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

from floe_orchestrator_dagster.capabilities import (
    AlphaCapabilityError,
    CapabilityPolicy,
)


def test_alpha_profile_requires_catalog_storage_and_lineage() -> None:
    policy = CapabilityPolicy.alpha()
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
        catalog=None,
        storage=None,
        lineage_backend=None,
    )

    with pytest.raises(AlphaCapabilityError, match="catalog"):
        policy.validate_required_plugins(plugins)


def test_non_alpha_profile_allows_unconfigured_lineage() -> None:
    policy = CapabilityPolicy.default()
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
        catalog=None,
        storage=None,
        lineage_backend=None,
    )

    policy.validate_required_plugins(plugins)


def test_alpha_profile_accepts_all_required_plugins() -> None:
    policy = CapabilityPolicy.alpha()
    plugins = ResolvedPlugins(
        compute=PluginRef(type="duckdb", version="0.9.0"),
        orchestrator=PluginRef(type="dagster", version="1.5.0"),
        catalog=PluginRef(type="polaris", version="0.1.0", config={}),
        storage=PluginRef(type="s3", version="1.0.0", config={}),
        lineage_backend=PluginRef(
            type="marquez",
            version="0.1.0",
            config={"url": "http://marquez:5000"},
        ),
    )

    policy.validate_required_plugins(plugins)
