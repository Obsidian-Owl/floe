"""Contract tests for CompiledArtifacts.plugins.ingestion round-trip.

These tests validate that CompiledArtifacts can include ingestion plugin
references and that the schema round-trips correctly through serialization.

This is a contract test (tests/contract/) because it validates the integration
between floe-core (CompiledArtifacts) and ingestion plugins.

Requirements Covered:
- 4F-FR-001: CompiledArtifacts supports ingestion plugin reference
- 4F-FR-001: PluginRef schema for ingestion plugins
- 4F-FR-001: Serialization/deserialization round-trip
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestIngestionPluginRefContract:
    """Contract tests for ingestion field in CompiledArtifacts.

    These tests verify that CompiledArtifacts can include an ingestion
    plugin reference via ResolvedPlugins.ingestion.
    """

    @pytest.mark.requirement("4F-FR-001")
    def test_plugins_config_has_ingestion_field(self) -> None:
        """Verify ResolvedPlugins has ingestion attribute.

        The ingestion field should be a PluginRef or None.
        """
        from floe_core.schemas.compiled_artifacts import ResolvedPlugins

        # ResolvedPlugins should have ingestion field
        assert hasattr(ResolvedPlugins, "model_fields")
        assert "ingestion" in ResolvedPlugins.model_fields

    @pytest.mark.requirement("4F-FR-001")
    def test_ingestion_field_is_optional(self) -> None:
        """Verify ingestion field defaults to None.

        Ingestion is optional — products without ingestion pipelines
        should not require this field.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        # Create ResolvedPlugins without ingestion
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
        )

        # ingestion should be None by default
        assert plugins.ingestion is None

    @pytest.mark.requirement("4F-FR-001")
    def test_ingestion_field_accepts_plugin_ref(self) -> None:
        """Verify ingestion field accepts a PluginRef.

        When an ingestion plugin is configured, ResolvedPlugins should
        accept it as a PluginRef.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        # Create ResolvedPlugins with ingestion
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            ingestion=PluginRef(
                type="dlt",
                version="0.1.0",
                config={"sources": []},
            ),
        )

        # Verify ingestion plugin ref
        assert plugins.ingestion is not None
        assert plugins.ingestion.type == "dlt"
        assert plugins.ingestion.version == "0.1.0"
        assert plugins.ingestion.config == {"sources": []}

    @pytest.mark.requirement("4F-FR-001")
    def test_ingestion_plugin_ref_round_trip(self) -> None:
        """Verify PluginRef with ingestion serializes and deserializes correctly.

        model_dump() and reconstruction from dict should preserve the
        ingestion plugin reference.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        # Create ResolvedPlugins with ingestion
        original = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            ingestion=PluginRef(
                type="dlt",
                version="0.1.0",
                config={"sources": [{"type": "postgres"}]},
            ),
        )

        # Serialize
        dumped = original.model_dump()

        # Reconstruct
        reconstructed = ResolvedPlugins.model_validate(dumped)

        # Verify equality
        assert reconstructed.ingestion is not None
        assert original.ingestion is not None
        assert reconstructed.ingestion.type == original.ingestion.type
        assert reconstructed.ingestion.version == original.ingestion.version
        assert reconstructed.ingestion.config == original.ingestion.config

    @pytest.mark.requirement("4F-FR-001")
    def test_ingestion_none_round_trip(self) -> None:
        """Verify ResolvedPlugins with ingestion=None serializes correctly.

        When ingestion is None, it should remain None after round-trip.
        """
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        # Create ResolvedPlugins without ingestion
        original = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.1.0", config={}),
            orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
            ingestion=None,
        )

        # Serialize
        dumped = original.model_dump()

        # Reconstruct
        reconstructed = ResolvedPlugins.model_validate(dumped)

        # Verify ingestion is still None
        assert reconstructed.ingestion is None

    @pytest.mark.requirement("4F-FR-001")
    def test_compiled_artifacts_with_ingestion(self) -> None:
        """Verify CompiledArtifacts can include ingestion plugin reference.

        Full CompiledArtifacts object with ingestion should serialize
        and deserialize correctly.
        """
        from floe_core.schemas.compiled_artifacts import (
            CompilationMetadata,
            CompiledArtifacts,
            ManifestRef,
            ObservabilityConfig,
            PluginRef,
            ProductIdentity,
            ResolvedPlugins,
        )
        from floe_core.schemas.telemetry import ResourceAttributes, TelemetryConfig

        # Create CompiledArtifacts with ingestion plugin
        artifacts = CompiledArtifacts(
            version="2.0.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(timezone.utc),
                floe_version="0.1.0",
                source_hash="abc123",
                product_name="test",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="test.product",
                domain="test",
                repository="https://github.com/test/product",
            ),
            mode="simple",
            inheritance_chain=[
                ManifestRef(
                    name="test",
                    version="1.0.0",
                    scope="enterprise",
                    ref="oci://test",
                )
            ],
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    enabled=True,
                    resource_attributes=ResourceAttributes(
                        service_name="test",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="test",
                        floe_product_name="test",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace="test",
            ),
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.1.0", config={}),
                orchestrator=PluginRef(type="dagster", version="0.1.0", config={}),
                ingestion=PluginRef(
                    type="dlt",
                    version="0.1.0",
                    config={"sources": [{"type": "rest_api"}]},
                ),
            ),
        )

        # Verify ingestion plugin is included
        assert artifacts.plugins is not None
        assert artifacts.plugins.ingestion is not None
        assert artifacts.plugins.ingestion.type == "dlt"

        # Serialize
        dumped = artifacts.model_dump()

        # Reconstruct
        reconstructed = CompiledArtifacts.model_validate(dumped)

        # Verify ingestion plugin persists
        assert reconstructed.plugins is not None
        assert reconstructed.plugins.ingestion is not None
        assert reconstructed.plugins.ingestion.type == "dlt"
        assert reconstructed.plugins.ingestion.version == "0.1.0"
