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
from pathlib import Path

import pytest
import yaml


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

    @pytest.mark.requirement("4F-FR-001")
    def test_compiled_artifacts_ingestion_config_uses_dlt_snake_case_keys(self) -> None:
        """Serialized ingestion config uses the dlt plugin's snake_case contract."""
        import json

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
        from floe_ingestion_dlt.config import DltIngestionConfig

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
                    config={
                        "catalog_config": {"warehouse": "floe"},
                        "retry_config": {"max_retries": 4, "initial_delay_seconds": 1.5},
                        "sources": [
                            {
                                "name": "orders_csv",
                                "source_type": "filesystem",
                                "destination_table": "bronze.orders",
                                "write_mode": "append",
                                "schema_contract": "evolve",
                                "source_config": {
                                    "format": "csv",
                                    "path": "data/orders.csv",
                                },
                            }
                        ],
                    },
                ),
            ),
        )

        dumped = artifacts.model_dump(mode="json")
        sources = dumped["plugins"]["ingestion"]["config"]["sources"]

        assert sources == [
            {
                "name": "orders_csv",
                "source_type": "filesystem",
                "destination_table": "bronze.orders",
                "write_mode": "append",
                "schema_contract": "evolve",
                "source_config": {
                    "format": "csv",
                    "path": "data/orders.csv",
                },
            }
        ]
        assert isinstance(sources, list)
        assert all(isinstance(source, dict) for source in sources)
        assert {
            "source_type",
            "source_config",
            "destination_table",
            "write_mode",
            "schema_contract",
        }.issubset(sources[0])
        assert {
            "sourceType",
            "destinationTable",
            "writeMode",
            "schemaContract",
        }.isdisjoint(sources[0])
        assert "format" not in sources[0]
        assert "path" not in sources[0]
        json.dumps(sources)
        DltIngestionConfig.model_validate(dumped["plugins"]["ingestion"]["config"])

        reconstructed = CompiledArtifacts.model_validate(dumped)

        assert reconstructed.plugins.ingestion is not None
        assert reconstructed.plugins.ingestion.config is not None
        assert reconstructed.plugins.ingestion.config["sources"] == sources

    @pytest.mark.requirement("4F-FR-001")
    def test_customer_360_demo_declares_csv_dlt_ingestion_sources(self) -> None:
        """Customer 360 demo config compiles CSV sources into dlt ingestion config."""
        from floe_core.compilation.resolver import resolve_ingestion_config, resolve_plugins
        from floe_core.schemas.floe_spec import FloeSpec
        from floe_core.schemas.manifest import PlatformManifest
        from floe_ingestion_dlt.config import DltIngestionConfig

        root = Path(__file__).parent.parent.parent
        manifest_path = root / "demo" / "manifest.yaml"
        spec_path = root / "demo" / "customer-360" / "floe.yaml"

        manifest = yaml.safe_load(manifest_path.read_text())
        spec = yaml.safe_load(spec_path.read_text())

        ingestion_plugin = manifest["plugins"]["ingestion"]
        assert ingestion_plugin["type"] == "dlt"
        assert "catalog_config" not in ingestion_plugin["config"]
        assert ingestion_plugin["config"]["retry_config"] == {
            "max_retries": 3,
            "initial_delay_seconds": 1.0,
        }

        spec_sources = spec["ingestion"]["sources"]
        expected_sources = {
            "raw-customers": ("./seeds/raw_customers.csv", "bronze.raw_customers"),
            "raw-transactions": (
                "./seeds/raw_transactions.csv",
                "bronze.raw_transactions",
            ),
            "raw-support-tickets": (
                "./seeds/raw_support_tickets.csv",
                "bronze.raw_support_tickets",
            ),
        }
        sources_by_name = {source["name"]: source for source in spec_sources}
        assert set(sources_by_name) == set(expected_sources)

        for name, (path, destination_table) in expected_sources.items():
            source = sources_by_name[name]
            expected_source = {
                "sourceType": "filesystem",
                "format": "csv",
                "path": path,
                "destinationTable": destination_table,
                "writeMode": "replace",
                "schemaContract": "evolve",
            }
            assert expected_source.items() <= source.items()
            assert (spec_path.parent / path).exists()

        plugins = resolve_ingestion_config(
            FloeSpec.model_validate(spec),
            resolve_plugins(PlatformManifest.model_validate(manifest)),
        )

        assert plugins.ingestion is not None
        assert plugins.ingestion.type == "dlt"
        assert plugins.ingestion.config is not None
        assert "catalog_config" not in plugins.ingestion.config
        DltIngestionConfig.model_validate(plugins.ingestion.config)

        resolved_sources = {
            source["name"]: source for source in plugins.ingestion.config["sources"]
        }
        assert set(resolved_sources) == set(expected_sources)
        for name, (path, destination_table) in expected_sources.items():
            source = resolved_sources[name]
            expected_source = {
                "source_type": "filesystem",
                "destination_table": destination_table,
                "write_mode": "replace",
                "schema_contract": "evolve",
                "source_config": {"format": "csv", "path": path},
            }
            assert expected_source.items() <= source.items()


def test_compiled_artifacts_contract_includes_ingestion_deployment_binding() -> None:
    from floe_core.schemas.compiled_artifacts import (
        DeploymentConfig,
        DltIngestionBinding,
        IngestionDeploymentBinding,
    )

    deployment = DeploymentConfig(
        ingestion=IngestionDeploymentBinding(
            provider="dlt",
            dlt=DltIngestionBinding(
                plugin_name="dlt",
                destination="filesystem",
                table_format="iceberg",
                source_filesystem={"endpoint_url": "http://minio:9000"},
                destination_filesystem={"bucket_url": "s3://warehouse"},
                iceberg_catalog_env={"PYICEBERG_CATALOG__POLARIS__TYPE": "rest"},
                env_refs={"AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID"},
            ),
        )
    )

    payload = deployment.model_dump(mode="json")
    assert payload["ingestion"]["provider"] == "dlt"
    assert payload["ingestion"]["dlt"]["destination"] == "filesystem"
    assert payload["ingestion"]["dlt"]["table_format"] == "iceberg"


def test_demo_compile_has_no_ingestion_catalog_config_duplication() -> None:
    from floe_core.compilation.stages import compile_pipeline

    root = Path(__file__).resolve().parents[2]
    artifacts = compile_pipeline(
        root / "demo" / "customer-360" / "floe.yaml",
        root / "demo" / "manifest.yaml",
        emit_lineage=False,
    )

    assert artifacts.plugins.ingestion is not None
    assert artifacts.plugins.ingestion.config is not None
    assert "catalog_config" not in artifacts.plugins.ingestion.config
    assert artifacts.deployment is not None
    assert artifacts.deployment.ingestion is not None
