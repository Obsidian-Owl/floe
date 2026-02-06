"""Contract tests for CompiledArtifacts.plugins.semantic round-trip.

These tests validate that the semantic plugin reference in CompiledArtifacts
can be serialized and deserialized correctly, ensuring cross-package
compatibility between floe-core and floe-semantic-cube.

This is a contract test (tests/contract/) because it validates the
CompiledArtifacts schema stability for the semantic field.

Requirements Covered:
    - SC-006: CompiledArtifacts.plugins.semantic round-trip integrity
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins


class TestSemanticPluginRefRoundTrip:
    """Contract tests for PluginRef with type='cube'."""

    @pytest.mark.requirement("SC-006")
    def test_plugin_ref_cube_type_accepted(self) -> None:
        """Test that PluginRef accepts type='cube' for semantic layer."""
        ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={"server_url": "http://cube:4000"},
        )
        assert ref.type == "cube"
        assert ref.version == "0.1.0"
        assert ref.config == {"server_url": "http://cube:4000"}

    @pytest.mark.requirement("SC-006")
    def test_serialize_deserialize_preserves_fields(self) -> None:
        """Test that JSON round-trip preserves all PluginRef fields."""
        ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={
                "server_url": "http://cube:4000",
                "database_name": "analytics",
                "health_check_timeout": 5.0,
            },
        )
        json_str = ref.model_dump_json()
        restored = PluginRef.model_validate_json(json_str)

        assert restored.type == ref.type
        assert restored.version == ref.version
        assert restored.config == ref.config

    @pytest.mark.requirement("SC-006")
    def test_cube_specific_config_round_trips(self) -> None:
        """Test that Cube-specific configuration survives round-trip."""
        cube_config: dict[str, Any] = {
            "server_url": "https://cube.prod.example.com",
            "database_name": "warehouse",
            "health_check_timeout": 10.0,
            "model_filter_tags": ["analytics", "cube"],
            "model_filter_schemas": ["gold"],
        }
        ref = PluginRef(type="cube", version="0.1.0", config=cube_config)
        data = ref.model_dump()
        restored = PluginRef.model_validate(data)
        assert restored.config == cube_config


class TestResolvedPluginsSemanticField:
    """Contract tests for ResolvedPlugins.semantic field."""

    @pytest.mark.requirement("SC-006")
    def test_semantic_none_by_default(self) -> None:
        """Test that semantic field defaults to None."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
        )
        assert plugins.semantic is None

    @pytest.mark.requirement("SC-006")
    def test_semantic_none_serializes_correctly(self) -> None:
        """Test that None semantic field serializes and deserializes."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            semantic=None,
        )
        data = plugins.model_dump()
        restored = ResolvedPlugins.model_validate(data)
        assert restored.semantic is None

    @pytest.mark.requirement("SC-006")
    def test_semantic_with_cube_ref(self) -> None:
        """Test that semantic field accepts a Cube PluginRef."""
        cube_ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={"server_url": "http://cube:4000"},
        )
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            semantic=cube_ref,
        )
        assert plugins.semantic is not None
        assert plugins.semantic.type == "cube"

    @pytest.mark.requirement("SC-006")
    def test_semantic_round_trip_in_resolved_plugins(self) -> None:
        """Test full round-trip of ResolvedPlugins with semantic set."""
        cube_ref = PluginRef(
            type="cube",
            version="0.1.0",
            config={"database_name": "analytics"},
        )
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            semantic=cube_ref,
        )
        json_str = plugins.model_dump_json()
        restored = ResolvedPlugins.model_validate_json(json_str)
        assert restored.semantic is not None
        assert restored.semantic.type == "cube"
        assert restored.semantic.config == {"database_name": "analytics"}
