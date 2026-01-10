"""Contract tests for CompiledArtifacts with TelemetryConfig.

These tests validate that:
- CompiledArtifacts correctly includes TelemetryConfig in ObservabilityConfig
- TelemetryConfig is properly integrated into the schema
- JSON Schema export includes telemetry configuration
- Golden fixtures remain backward compatible

Contract tests focus on schema stability and cross-package integration.

Requirements Covered:
- T076: Add TelemetryConfig to CompiledArtifacts schema
- FR-001: TelemetryProvider configuration
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from floe_core.schemas import (
    CompilationMetadata,
    CompiledArtifacts,
    ObservabilityConfig,
    ProductIdentity,
)
from floe_core.telemetry.config import (
    BatchSpanProcessorConfig,
    LoggingConfig,
    ResourceAttributes,
    SamplingConfig,
    TelemetryConfig,
)

# Path to golden fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCompiledArtifactsTelemetryContract:
    """Contract tests for TelemetryConfig integration in CompiledArtifacts."""

    @pytest.fixture
    def sample_resource_attributes(self) -> ResourceAttributes:
        """Create sample ResourceAttributes for testing."""
        return ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )

    @pytest.fixture
    def sample_telemetry_config(
        self, sample_resource_attributes: ResourceAttributes
    ) -> TelemetryConfig:
        """Create sample TelemetryConfig for testing."""
        return TelemetryConfig(
            enabled=True,
            otlp_endpoint="http://otel-collector:4317",
            otlp_protocol="grpc",
            sampling=SamplingConfig(dev=1.0, staging=0.5, prod=0.1),
            resource_attributes=sample_resource_attributes,
            batch_processor=BatchSpanProcessorConfig(),
            logging=LoggingConfig(log_level="INFO", json_output=True),
            backend="console",
        )

    @pytest.fixture
    def sample_observability_config(
        self, sample_telemetry_config: TelemetryConfig
    ) -> ObservabilityConfig:
        """Create sample ObservabilityConfig for testing."""
        return ObservabilityConfig(
            telemetry=sample_telemetry_config,
            lineage=True,
            lineage_namespace="test-namespace",
        )

    @pytest.fixture
    def sample_compiled_artifacts(
        self, sample_observability_config: ObservabilityConfig
    ) -> CompiledArtifacts:
        """Create sample CompiledArtifacts for testing."""
        return CompiledArtifacts(
            version="0.1.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(tz=timezone.utc),
                floe_version="0.1.0",
                source_hash="sha256:abc123",
                product_name="test-product",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.test_product",
                domain="default",
                repository="github.com/test/test-product",
            ),
            mode="simple",
            observability=sample_observability_config,
        )

    @pytest.mark.requirement("T076")
    def test_observability_contains_telemetry_config(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Verify ObservabilityConfig contains TelemetryConfig."""
        assert hasattr(sample_compiled_artifacts.observability, "telemetry")
        assert isinstance(
            sample_compiled_artifacts.observability.telemetry, TelemetryConfig
        )

    @pytest.mark.requirement("T076")
    def test_telemetry_config_has_required_fields(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Verify TelemetryConfig has all required fields."""
        telemetry = sample_compiled_artifacts.observability.telemetry

        # Core fields
        assert hasattr(telemetry, "enabled")
        assert hasattr(telemetry, "otlp_endpoint")
        assert hasattr(telemetry, "otlp_protocol")
        assert hasattr(telemetry, "sampling")
        assert hasattr(telemetry, "resource_attributes")
        assert hasattr(telemetry, "authentication")

        # Added in contract v1.1.0
        assert hasattr(telemetry, "batch_processor")
        assert hasattr(telemetry, "logging")
        assert hasattr(telemetry, "backend")

    @pytest.mark.requirement("T076")
    def test_telemetry_config_values_preserved(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Verify TelemetryConfig values are correctly preserved."""
        telemetry = sample_compiled_artifacts.observability.telemetry

        assert telemetry.enabled is True
        assert telemetry.otlp_endpoint == "http://otel-collector:4317"
        assert telemetry.otlp_protocol == "grpc"
        assert telemetry.backend == "console"

    @pytest.mark.requirement("T076")
    def test_resource_attributes_preserved(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Verify ResourceAttributes are correctly preserved."""
        attrs = sample_compiled_artifacts.observability.telemetry.resource_attributes

        assert attrs.service_name == "test-service"
        assert attrs.service_version == "1.0.0"
        assert attrs.deployment_environment == "dev"
        assert attrs.floe_namespace == "test-namespace"
        assert attrs.floe_product_name == "test-product"
        assert attrs.floe_mode == "dev"

    @pytest.mark.requirement("T076")
    def test_sampling_config_preserved(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Verify SamplingConfig is correctly preserved."""
        sampling = sample_compiled_artifacts.observability.telemetry.sampling

        assert sampling.dev == pytest.approx(1.0)
        assert sampling.staging == pytest.approx(0.5)
        assert sampling.prod == pytest.approx(0.1)

    @pytest.mark.requirement("T076")
    def test_batch_processor_config_preserved(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Verify BatchSpanProcessorConfig is correctly preserved."""
        batch = sample_compiled_artifacts.observability.telemetry.batch_processor

        # Default values from BatchSpanProcessorConfig
        assert batch.max_queue_size == 2048
        assert batch.max_export_batch_size == 512
        assert batch.schedule_delay_millis == 5000
        assert batch.export_timeout_millis == 30000

    @pytest.mark.requirement("T076")
    def test_logging_config_preserved(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Verify LoggingConfig is correctly preserved."""
        logging = sample_compiled_artifacts.observability.telemetry.logging

        assert logging.log_level.upper() == "INFO"
        assert logging.json_output is True

    @pytest.mark.requirement("T076")
    def test_lineage_config_preserved(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Verify lineage configuration is preserved alongside telemetry."""
        obs = sample_compiled_artifacts.observability

        assert obs.lineage is True
        assert obs.lineage_namespace == "test-namespace"


class TestCompiledArtifactsJsonSchema:
    """Contract tests for JSON Schema export of CompiledArtifacts."""

    @pytest.mark.requirement("T076")
    def test_json_schema_includes_telemetry_config(self) -> None:
        """Verify JSON Schema includes TelemetryConfig definitions."""
        schema = CompiledArtifacts.model_json_schema()

        # Check that observability is in the schema
        assert "observability" in schema.get("required", []) or "observability" in schema.get(
            "properties", {}
        )

    @pytest.mark.requirement("T076")
    def test_json_schema_includes_telemetry_fields(self) -> None:
        """Verify JSON Schema includes all telemetry-related definitions."""
        schema = CompiledArtifacts.model_json_schema()

        # Check $defs contains our telemetry models
        defs = schema.get("$defs", {})

        # Core telemetry models should be referenced
        telemetry_models = [
            "TelemetryConfig",
            "ResourceAttributes",
            "SamplingConfig",
            "BatchSpanProcessorConfig",
            "LoggingConfig",
            "ObservabilityConfig",
        ]

        for model in telemetry_models:
            assert model in defs, f"{model} should be in JSON Schema $defs"

    @pytest.mark.requirement("T076")
    def test_compiled_artifacts_serialization_roundtrip(
        self,
    ) -> None:
        """Verify CompiledArtifacts can be serialized and deserialized."""
        original = CompiledArtifacts(
            version="0.1.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(tz=timezone.utc),
                floe_version="0.1.0",
                source_hash="sha256:test123",
                product_name="roundtrip-test",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.roundtrip",
                domain="default",
                repository="github.com/test/roundtrip",
            ),
            mode="simple",
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    enabled=True,
                    resource_attributes=ResourceAttributes(
                        service_name="roundtrip",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="test",
                        floe_product_name="roundtrip",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace="roundtrip",
            ),
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        restored = CompiledArtifacts.model_validate_json(json_str)

        # Verify key fields match
        assert restored.version == original.version
        assert restored.mode == original.mode
        assert restored.observability.telemetry.enabled == original.observability.telemetry.enabled
        assert (
            restored.observability.telemetry.resource_attributes.service_name
            == original.observability.telemetry.resource_attributes.service_name
        )


class TestGoldenCompiledArtifactsCompatibility:
    """Tests for backward compatibility with golden CompiledArtifacts fixtures.

    Golden fixtures represent artifacts created at a specific schema version.
    These tests ensure that schema evolution does not break existing artifacts.
    If a test fails, the schema change is potentially breaking.
    """

    @pytest.mark.requirement("T076")
    def test_v0_1_golden_compiled_artifacts_parses(self) -> None:
        """Contract: v0.1 golden CompiledArtifacts continues to parse correctly.

        This is a regression test ensuring backward compatibility.
        If this test fails, the schema change is potentially breaking.
        """
        fixture_path = FIXTURES_DIR / "v0.1_compiled_artifacts.json"
        assert fixture_path.exists(), f"Golden fixture not found: {fixture_path}"

        with fixture_path.open() as f:
            data = json.load(f)

        # Should parse without errors
        artifacts = CompiledArtifacts.model_validate(data)

        # Verify key fields are preserved
        assert artifacts.version == "0.1.0"
        assert artifacts.mode == "centralized"
        assert artifacts.identity.product_id == "analytics.golden_product"
        assert artifacts.identity.domain == "analytics"

    @pytest.mark.requirement("T076")
    def test_v0_1_golden_telemetry_config_preserved(self) -> None:
        """Contract: v0.1 golden TelemetryConfig is preserved.

        Verifies all telemetry-specific fields are correctly loaded.
        """
        fixture_path = FIXTURES_DIR / "v0.1_compiled_artifacts.json"
        with fixture_path.open() as f:
            data = json.load(f)

        artifacts = CompiledArtifacts.model_validate(data)

        # TelemetryConfig must be preserved
        telemetry = artifacts.observability.telemetry
        assert telemetry.enabled is True
        assert telemetry.otlp_endpoint == "http://otel-collector:4317"
        assert telemetry.otlp_protocol == "grpc"
        assert telemetry.backend == "jaeger"

        # Resource attributes preserved
        attrs = telemetry.resource_attributes
        assert attrs.service_name == "golden-product"
        assert attrs.service_version == "1.0.0"
        assert attrs.deployment_environment == "prod"
        assert attrs.floe_namespace == "analytics"

    @pytest.mark.requirement("T076")
    def test_v0_1_golden_nested_configs_preserved(self) -> None:
        """Contract: v0.1 golden nested configurations are preserved.

        Verifies sampling, batch processor, and logging configs.
        """
        fixture_path = FIXTURES_DIR / "v0.1_compiled_artifacts.json"
        with fixture_path.open() as f:
            data = json.load(f)

        artifacts = CompiledArtifacts.model_validate(data)

        # Sampling config preserved
        sampling = artifacts.observability.telemetry.sampling
        assert sampling.dev == pytest.approx(1.0)
        assert sampling.staging == pytest.approx(0.5)
        assert sampling.prod == pytest.approx(0.1)

        # BatchProcessor config preserved
        batch = artifacts.observability.telemetry.batch_processor
        assert batch.max_queue_size == 2048
        assert batch.max_export_batch_size == 512
        assert batch.schedule_delay_millis == 5000
        assert batch.export_timeout_millis == 30000

        # Logging config preserved
        logging_cfg = artifacts.observability.telemetry.logging
        assert logging_cfg.log_level.upper() == "INFO"
        assert logging_cfg.json_output is True

        # Inheritance chain preserved
        assert len(artifacts.inheritance_chain) == 1
        assert artifacts.inheritance_chain[0].name == "enterprise-manifest"
        assert artifacts.inheritance_chain[0].scope == "enterprise"

    @pytest.mark.requirement("T076")
    def test_v0_1_golden_compiled_artifacts_roundtrip(self) -> None:
        """Contract: v0.1 golden CompiledArtifacts survives roundtrip serialization.

        Tests that deserialize -> serialize -> deserialize produces equivalent data.
        """
        fixture_path = FIXTURES_DIR / "v0.1_compiled_artifacts.json"
        with fixture_path.open() as f:
            original_data = json.load(f)

        # Deserialize
        artifacts = CompiledArtifacts.model_validate(original_data)

        # Serialize back to dict
        exported = artifacts.model_dump(mode="json")

        # Key fields should match original
        assert exported["version"] == original_data["version"]
        assert exported["mode"] == original_data["mode"]
        assert exported["identity"]["product_id"] == original_data["identity"]["product_id"]
        assert (
            exported["observability"]["telemetry"]["backend"]
            == original_data["observability"]["telemetry"]["backend"]
        )
        assert (
            exported["observability"]["telemetry"]["resource_attributes"]["service_name"]
            == original_data["observability"]["telemetry"]["resource_attributes"]["service_name"]
        )
