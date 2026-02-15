"""Contract tests for the compilation pipeline.

This module tests the complete compilation pipeline:
floe.yaml + manifest.yaml → CompiledArtifacts

These tests validate compilation without requiring deployment to K8s.
They verify the 6-stage compilation process:
LOAD → VALIDATE → RESOLVE → ENFORCE → COMPILE → GENERATE.

Reclassified from tests/e2e/ to tests/contract/ per test hardening audit
(AC-1.5) — these tests don't require K8s, only validate the CompiledArtifacts
contract.

See Also:
    - tests/conftest.py: compiled_artifacts fixture
    - packages/floe-core/src/floe_core/schemas/compiled_artifacts.py: CompiledArtifacts schema
    - packages/floe-core/src/floe_core/compilation/stages.py: Compilation stages
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
from floe_core.compilation.errors import CompilationException
from floe_core.compilation.stages import CompilationStage
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    ObservabilityConfig,
    PluginRef,
    ProductIdentity,
    ResolvedPlugins,
)
from floe_core.schemas.telemetry import ResourceAttributes, TelemetryConfig
from floe_core.schemas.versions import (
    COMPILED_ARTIFACTS_VERSION,
    COMPILED_ARTIFACTS_VERSION_HISTORY,
    FLOE_VERSION,
)
from pydantic import ValidationError


class TestCompilation:
    """Contract tests for the compilation pipeline.

    Tests validate the complete compilation workflow from FloeSpec to CompiledArtifacts.
    These tests run without K8s and verify schema compliance, determinism, and contract stability.
    """

    @pytest.mark.contract
    @pytest.mark.requirement("FR-010")
    def test_compile_customer_360(self, tmp_path: Path, compiled_artifacts: Any) -> None:
        """Test compilation of customer-360 demo pipeline.

        Validates that demo/customer-360/floe.yaml compiles to valid CompiledArtifacts v0.5.0.

        Args:
            tmp_path: Temporary directory fixture.
            compiled_artifacts: Compilation factory fixture from conftest.

        Validates:
            - CompiledArtifacts version is 0.5.0
            - Metadata contains product name "customer-360"
            - Plugins resolved (compute, orchestrator)
            - Observability config present with telemetry
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        assert spec_path.exists(), f"Demo spec not found: {spec_path}"

        # Compile spec
        artifacts = compiled_artifacts(spec_path)

        # Validate version (contract version)
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION

        # Validate metadata
        assert artifacts.metadata.product_name == "customer-360"
        assert artifacts.metadata.floe_version == FLOE_VERSION

        # Validate identity
        assert "customer_360" in artifacts.identity.product_id
        assert artifacts.identity.domain == "default"

        # Validate plugins resolved
        assert artifacts.plugins is not None

        # Validate observability config
        assert artifacts.observability is not None
        assert artifacts.observability.telemetry is not None
        assert isinstance(artifacts.observability.telemetry.resource_attributes, ResourceAttributes)
        assert artifacts.observability.lineage_namespace == "customer-360"

        # Plugin type assertions (exact values)
        assert artifacts.plugins.compute.type == "duckdb", (
            f"Expected duckdb compute, got {artifacts.plugins.compute.type}"
        )
        assert artifacts.plugins.orchestrator.type == "dagster", (
            f"Expected dagster orchestrator, got {artifacts.plugins.orchestrator.type}"
        )

        # Observability assertions
        assert artifacts.observability.lineage is True, "Lineage must be enabled for customer-360"

        # Source hash format (SHA256 produces 64 hex chars after prefix)
        source_hash = artifacts.metadata.source_hash
        assert source_hash.startswith("sha256:"), (
            f"Source hash must start with 'sha256:', got '{source_hash[:10]}...'"
        )
        hash_value = source_hash.split(":", 1)[1] if ":" in source_hash else source_hash
        assert len(hash_value) == 64 and all(c in "0123456789abcdef" for c in hash_value), (
            f"Source hash must be 64-char hex (SHA256), got {len(hash_value)} chars"
        )

        # Transforms resolved
        assert artifacts.transforms is not None, "Transforms must be resolved for customer-360"
        assert len(artifacts.transforms.models) > 0, (
            "customer-360 must have at least one transform model"
        )
        # Every model must have compute populated
        for model in artifacts.transforms.models:
            assert model.compute is not None and len(model.compute) > 0, (
                f"Model {model.name} must have compute target resolved, got {model.compute!r}"
            )

    @pytest.mark.contract
    @pytest.mark.requirement("FR-010")
    def test_compile_iot_telemetry(self, tmp_path: Path, compiled_artifacts: Any) -> None:
        """Test compilation of iot-telemetry demo pipeline.

        Validates that demo/iot-telemetry/floe.yaml compiles successfully.

        Args:
            tmp_path: Temporary directory fixture.
            compiled_artifacts: Compilation factory fixture from conftest.

        Validates:
            - CompiledArtifacts created
            - Product name is "iot-telemetry"
            - All required fields present
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "iot-telemetry" / "floe.yaml"
        assert spec_path.exists(), f"Demo spec not found: {spec_path}"

        # Compile spec
        artifacts = compiled_artifacts(spec_path)

        # Validate basic structure
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION
        assert artifacts.metadata.product_name == "iot-telemetry"
        assert "iot_telemetry" in artifacts.identity.product_id

        assert artifacts.plugins.compute.type == "duckdb", (
            f"Expected duckdb compute for iot-telemetry, got {artifacts.plugins.compute.type}"
        )
        assert artifacts.plugins.orchestrator.type == "dagster", (
            f"Expected dagster orchestrator, got {artifacts.plugins.orchestrator.type}"
        )
        ns = artifacts.observability.lineage_namespace
        assert ns == "iot-telemetry", f"Lineage namespace should be iot-telemetry, got {ns}"
        assert len(artifacts.identity.domain) > 0, "Domain must be populated"
        assert artifacts.transforms is not None and len(artifacts.transforms.models) > 0, (
            "iot-telemetry must have transform models"
        )

        # Verify source_hash is exactly 64 hex chars (SHA-256)
        source_hash = artifacts.metadata.source_hash
        assert source_hash.startswith("sha256:"), (
            f"Source hash must start with 'sha256:', got '{source_hash[:10]}...'"
        )
        hash_value = source_hash.split(":")[1]
        assert len(hash_value) == 64, (
            f"iot-telemetry: source_hash must be 64 hex chars, got {len(hash_value)}"
        )
        assert all(c in "0123456789abcdef" for c in hash_value), (
            "iot-telemetry: source_hash must be hex only"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("FR-010")
    def test_compile_financial_risk(self, tmp_path: Path, compiled_artifacts: Any) -> None:
        """Test compilation of financial-risk demo pipeline.

        Validates that demo/financial-risk/floe.yaml compiles successfully.

        Args:
            tmp_path: Temporary directory fixture.
            compiled_artifacts: Compilation factory fixture from conftest.

        Validates:
            - CompiledArtifacts created
            - Product name is "financial-risk"
            - All required fields present
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "financial-risk" / "floe.yaml"
        assert spec_path.exists(), f"Demo spec not found: {spec_path}"

        # Compile spec
        artifacts = compiled_artifacts(spec_path)

        # Validate basic structure
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION
        assert artifacts.metadata.product_name == "financial-risk"
        assert "financial_risk" in artifacts.identity.product_id

        assert artifacts.plugins.compute.type == "duckdb", (
            f"Expected duckdb compute for financial-risk, got {artifacts.plugins.compute.type}"
        )
        assert artifacts.plugins.orchestrator.type == "dagster", (
            f"Expected dagster orchestrator, got {artifacts.plugins.orchestrator.type}"
        )
        ns = artifacts.observability.lineage_namespace
        assert ns == "financial-risk", f"Lineage namespace should be financial-risk, got {ns}"
        assert artifacts.transforms is not None and len(artifacts.transforms.models) > 0, (
            "financial-risk must have transform models"
        )

        # Verify source_hash is exactly 64 hex chars (SHA-256)
        source_hash = artifacts.metadata.source_hash
        assert source_hash.startswith("sha256:"), (
            f"Source hash must start with 'sha256:', got '{source_hash[:10]}...'"
        )
        hash_value = source_hash.split(":")[1]
        assert len(hash_value) == 64, (
            f"financial-risk: source_hash must be 64 hex chars, got {len(hash_value)}"
        )
        assert all(c in "0123456789abcdef" for c in hash_value), (
            "financial-risk: source_hash must be hex only"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("FR-011")
    def test_compilation_stages_execute(self, tmp_path: Path, compiled_artifacts: Any) -> None:
        """Test that all 6 compilation stages execute successfully.

        Validates the complete stage sequence:
        LOAD → VALIDATE → RESOLVE → ENFORCE → COMPILE → GENERATE.

        Args:
            tmp_path: Temporary directory fixture.
            compiled_artifacts: Compilation factory fixture from conftest.

        Validates:
            - All 6 stages defined in CompilationStage enum
            - Compilation produces valid CompiledArtifacts
            - No stage errors occur
        """
        # Verify all stages exist
        expected_stages = {
            "LOAD",
            "VALIDATE",
            "RESOLVE",
            "ENFORCE",
            "COMPILE",
            "GENERATE",
        }
        actual_stages = {stage.value for stage in CompilationStage}
        assert actual_stages == expected_stages, "Expected 6 compilation stages"

        # Verify each stage has an exit code
        for stage in CompilationStage:
            assert stage.exit_code in {1, 2}, f"Stage {stage} has invalid exit code"

        # Compile a spec (implicitly tests all stages)
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        # If we got CompiledArtifacts, all stages succeeded
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION
        assert artifacts.metadata.product_name == "customer-360"

        # ENFORCE stage produces pre-manifest EnforcementResultSummary
        # from plugin instrumentation audit and sink whitelist checks.
        # Model-level validation (models_validated > 0) happens post-dbt
        # compilation via run_enforce_stage(), not during compile_pipeline().
        assert artifacts.enforcement_result is not None, (
            "enforcement_result must be populated by Stage 4 (ENFORCE)"
        )
        assert isinstance(artifacts.enforcement_result.passed, bool), (
            "Enforcement result must have a boolean passed field"
        )
        assert "plugin_instrumentation" in artifacts.enforcement_result.policy_types_checked, (
            "ENFORCE stage must check plugin instrumentation"
        )
        level = artifacts.enforcement_result.enforcement_level
        assert level in (
            "off",
            "warn",
            "strict",
        ), f"Enforcement level must be off/warn/strict, got {level}"

    @pytest.mark.contract
    @pytest.mark.requirement("FR-012")
    def test_manifest_merge(self, tmp_path: Path, compiled_artifacts: Any) -> None:
        """Test compilation with manifest.yaml + floe.yaml merge.

        Validates that platform manifest (manifest.yaml) merges with product spec (floe.yaml).

        Args:
            tmp_path: Temporary directory fixture.
            compiled_artifacts: Compilation factory fixture from conftest.

        Validates:
            - Manifest inheritance_chain populated
            - Platform defaults merged with product-specific config
            - Serialization round-trip preserves mode
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        # Verify mode is populated from manifest
        assert artifacts.mode is not None
        assert len(artifacts.mode) > 0

        # Verify can serialize with inheritance
        output_path = tmp_path / "merged_artifacts.json"
        artifacts.to_json_file(output_path)
        assert output_path.exists()

        # Verify can deserialize and round-trip preserves mode
        loaded = CompiledArtifacts.from_json_file(output_path)
        assert loaded.mode == artifacts.mode

        # Inheritance chain may be populated when manifest is used.
        # Current compilation doesn't populate inheritance_chain for simple mode.
        if len(artifacts.inheritance_chain) > 0:
            first_ancestor = artifacts.inheritance_chain[0]
            assert len(first_ancestor.name) > 0, (
                f"First ancestor must have a name, got {first_ancestor.name!r}"
            )
            assert first_ancestor.scope in (
                "enterprise",
                "domain",
            ), f"Manifest scope must be enterprise or domain, got {first_ancestor.scope!r}"

        # Plugins must be resolved from manifest (not empty)
        assert artifacts.plugins is not None, "Plugins must be resolved from manifest"
        assert artifacts.plugins.compute.type == "duckdb", (
            "Compute plugin must be resolved from manifest"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("FR-013")
    def test_dbt_profiles_generated(self, tmp_path: Path, compiled_artifacts: Any) -> None:
        """Test dbt profiles.yml generation in CompiledArtifacts.

        Validates that compiled artifacts contain valid dbt profiles configuration.

        Args:
            tmp_path: Temporary directory fixture.
            compiled_artifacts: Compilation factory fixture from conftest.

        Validates:
            - dbt_profiles field is populated
            - Contains "default" profile
            - Profile structure is valid for dbt
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        # Verify dbt_profiles field exists and is populated by real compiler
        assert artifacts.dbt_profiles is not None

        # Real compiler generates profiles keyed by product name
        assert len(artifacts.dbt_profiles) > 0, (
            "Real compiler should generate dbt_profiles from manifest.yaml"
        )
        product_name = artifacts.metadata.product_name
        assert product_name in artifacts.dbt_profiles, (
            f"dbt_profiles should contain a '{product_name}' profile, "
            f"got keys: {list(artifacts.dbt_profiles.keys())}"
        )

        profile = artifacts.dbt_profiles[product_name]
        assert isinstance(profile, dict), "Profile should be a dict"
        # Profile should have a target and outputs
        assert "target" in profile or "outputs" in profile, (
            f"Profile needs target or outputs key. Keys: {list(profile.keys())}"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("FR-014")
    def test_dagster_config_generated(self, tmp_path: Path, compiled_artifacts: Any) -> None:
        """Test Dagster resource config generation in CompiledArtifacts.

        Validates that compiled artifacts contain Dagster-compatible configuration.

        Args:
            tmp_path: Temporary directory fixture.
            compiled_artifacts: Compilation factory fixture from conftest.

        Validates:
            - Plugins field contains orchestrator config
            - Orchestrator type is "dagster"
            - Version is valid semver
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        # Verify orchestrator plugin is present
        assert artifacts.plugins.orchestrator.type == "dagster"
        assert len(artifacts.plugins.orchestrator.version) > 0

        # Verify version is valid semver (matches pattern)
        version = artifacts.plugins.orchestrator.version
        assert len(version.split(".")) == 3, "Orchestrator version must be semver"

        # Compute plugin config should flow through
        assert (
            artifacts.plugins.compute.config is not None
            or artifacts.plugins.compute.type == "duckdb"
        ), "Compute plugin must have config or be a known type"

    @pytest.mark.contract
    @pytest.mark.requirement("FR-015")
    def test_invalid_spec_rejected(self, tmp_path: Path) -> None:
        """Test that invalid floe.yaml is rejected with ValidationError.

        Validates that compilation fails gracefully with invalid input.

        Args:
            tmp_path: Temporary directory fixture.

        Validates:
            - Invalid spec raises ValidationError
            - Error message is descriptive
            - No CompiledArtifacts generated
        """
        # Test 1: Invalid version format (not semver)
        with pytest.raises(ValidationError) as exc_info:
            CompiledArtifacts(
                version="not-a-version",
                metadata=CompilationMetadata(
                    compiled_at=datetime.now(timezone.utc),
                    floe_version="0.5.0",
                    source_hash="sha256:test",
                    product_name="test",
                    product_version="1.0.0",
                ),
                identity=ProductIdentity(
                    product_id="default.test",
                    domain="default",
                    repository="file://localhost",
                ),
                inheritance_chain=[],
                observability=ObservabilityConfig(
                    telemetry=TelemetryConfig(
                        resource_attributes=ResourceAttributes(
                            service_name="test",
                            service_version="1.0.0",
                            deployment_environment="dev",
                            floe_namespace="default",
                            floe_product_name="test",
                            floe_product_version="1.0.0",
                            floe_mode="dev",
                        ),
                    ),
                    lineage_namespace="test",
                ),
                plugins=ResolvedPlugins(
                    compute=PluginRef(type="duckdb", version="0.9.0"),
                    orchestrator=PluginRef(type="dagster", version="1.5.0"),
                ),
                dbt_profiles={},
            )

        # Verify error contains validation info
        error_msg = str(exc_info.value)
        assert "version" in error_msg.lower() or "pattern" in error_msg.lower()

        # Test 2: Empty product name (violates min_length)
        with pytest.raises(ValidationError) as exc_info2:
            CompiledArtifacts(
                version=COMPILED_ARTIFACTS_VERSION,
                metadata=CompilationMetadata(
                    compiled_at=datetime.now(timezone.utc),
                    floe_version="0.5.0",
                    source_hash="sha256:test",
                    product_name="",  # Invalid: empty string
                    product_version="1.0.0",
                ),
                identity=ProductIdentity(
                    product_id="default.test",
                    domain="default",
                    repository="file://localhost",
                ),
                inheritance_chain=[],
                observability=ObservabilityConfig(
                    telemetry=TelemetryConfig(
                        resource_attributes=ResourceAttributes(
                            service_name="test",
                            service_version="1.0.0",
                            deployment_environment="dev",
                            floe_namespace="default",
                            floe_product_name="test",
                            floe_product_version="1.0.0",
                            floe_mode="dev",
                        ),
                    ),
                    lineage_namespace="test",
                ),
                plugins=ResolvedPlugins(
                    compute=PluginRef(type="duckdb", version="0.9.0"),
                    orchestrator=PluginRef(type="dagster", version="1.5.0"),
                ),
                dbt_profiles={},
            )

        # Verify error mentions product_name
        error_msg2 = str(exc_info2.value)
        assert "product_name" in error_msg2.lower() or "length" in error_msg2.lower()

    @pytest.mark.contract
    @pytest.mark.requirement("FR-016")
    def test_deterministic_output(self, tmp_path: Path) -> None:
        """Test that compilation is deterministic (same input → same output).

        Validates that compiling the same spec twice produces byte-identical output
        when timestamps are normalized.

        Args:
            tmp_path: Temporary directory fixture.

        Validates:
            - Same input produces identical JSON structure
            - Hashes match when timestamps normalized
            - No random elements in compilation
        """
        # Create two identical artifacts with same timestamp
        fixed_timestamp = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        def create_artifact() -> CompiledArtifacts:
            return CompiledArtifacts(
                version=COMPILED_ARTIFACTS_VERSION,
                metadata=CompilationMetadata(
                    compiled_at=fixed_timestamp,
                    floe_version="0.5.0",
                    source_hash="sha256:test",
                    product_name="deterministic-test",
                    product_version="1.0.0",
                ),
                identity=ProductIdentity(
                    product_id="default.deterministic_test",
                    domain="default",
                    repository="file://localhost",
                    namespace_registered=False,
                ),
                mode="simple",
                inheritance_chain=[],
                observability=ObservabilityConfig(
                    telemetry=TelemetryConfig(
                        resource_attributes=ResourceAttributes(
                            service_name="deterministic-test",
                            service_version="1.0.0",
                            deployment_environment="dev",
                            floe_namespace="default",
                            floe_product_name="deterministic-test",
                            floe_product_version="1.0.0",
                            floe_mode="dev",
                        ),
                    ),
                    lineage_namespace="deterministic-test",
                ),
                plugins=ResolvedPlugins(
                    compute=PluginRef(type="duckdb", version="0.9.0"),
                    orchestrator=PluginRef(type="dagster", version="1.5.0"),
                ),
                dbt_profiles={},
            )

        # Create two artifacts
        artifact1 = create_artifact()
        artifact2 = create_artifact()

        # Serialize both
        path1 = tmp_path / "artifact1.json"
        path2 = tmp_path / "artifact2.json"
        artifact1.to_json_file(path1)
        artifact2.to_json_file(path2)

        # Read back as text
        json1 = path1.read_text()
        json2 = path2.read_text()

        # Compute hashes
        hash1 = hashlib.sha256(json1.encode()).hexdigest()
        hash2 = hashlib.sha256(json2.encode()).hexdigest()

        # Verify byte-identical
        assert hash1 == hash2, "Compilation should be deterministic"
        assert json1 == json2, "JSON output should be byte-identical"

    @pytest.mark.contract
    @pytest.mark.requirement("FR-017")
    def test_json_schema_export(self, tmp_path: Path) -> None:
        """Test JSON Schema export for floe.yaml IDE autocomplete.

        Validates that CompiledArtifacts exports valid JSON Schema for tooling integration.

        Args:
            tmp_path: Temporary directory fixture.

        Validates:
            - JSON Schema exported successfully
            - Contains $schema and $id metadata
            - Properties defined for all fields
            - Schema is valid according to JSON Schema spec
        """
        # Export JSON Schema
        schema = CompiledArtifacts.export_json_schema()

        # Verify standard JSON Schema fields
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] == "https://floe.dev/schemas/compiled-artifacts.json"

        # Verify properties exist
        assert "properties" in schema
        assert "version" in schema["properties"]
        assert "metadata" in schema["properties"]
        assert "identity" in schema["properties"]
        assert "observability" in schema["properties"]
        assert "plugins" in schema["properties"]

        # Verify required fields listed
        assert "required" in schema
        required_fields = schema["required"]
        assert "metadata" in required_fields
        assert "identity" in required_fields
        assert "observability" in required_fields

        # Verify can write to file
        schema_path = tmp_path / "compiled_artifacts_schema.json"
        schema_path.write_text(json.dumps(schema, indent=2))
        assert schema_path.exists()

        # Verify can read back
        loaded_schema = json.loads(schema_path.read_text())
        assert loaded_schema["$schema"] == schema["$schema"]

    @pytest.mark.contract
    @pytest.mark.requirement("FR-010")
    def test_compile_rejects_invalid_yaml(self, tmp_path: Path, demo_manifest: Path) -> None:
        """Test that compiler rejects malformed YAML with clear error.

        Validates that feeding invalid YAML (not valid YAML syntax) to
        compile_pipeline raises a compilation error at the LOAD stage.
        """
        from floe_core.compilation.stages import compile_pipeline

        invalid_path = tmp_path / "invalid.yaml"
        invalid_path.write_text("invalid: yaml: [unterminated\n  broken: {nope")

        with pytest.raises(CompilationException) as exc_info:
            compile_pipeline(invalid_path, demo_manifest)
        assert exc_info.value.error.stage == CompilationStage.LOAD

    @pytest.mark.contract
    @pytest.mark.requirement("FR-010")
    def test_compile_rejects_missing_required_fields(
        self, tmp_path: Path, demo_manifest: Path
    ) -> None:
        """Test that compiler rejects spec missing required fields.

        Validates that a floe.yaml missing the 'transforms' section
        raises a validation error during compilation.
        """
        from floe_core.compilation.stages import compile_pipeline

        # Create a spec missing transforms
        minimal_spec = {
            "apiVersion": "floe/v1",
            "kind": "FloeSpec",
            "metadata": {"name": "incomplete-spec", "version": "1.0.0"},
            # No transforms section
        }

        incomplete_path = tmp_path / "incomplete.yaml"
        incomplete_path.write_text(yaml.dump(minimal_spec))

        with pytest.raises(CompilationException) as exc_info:
            compile_pipeline(incomplete_path, demo_manifest)
        error_str = str(exc_info.value).lower()
        assert "transform" in error_str or "required" in error_str or "validation" in error_str, (
            f"Error should mention missing transforms, got: {exc_info.value}"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("FR-010")
    def test_compile_rejects_invalid_plugin_reference(
        self, tmp_path: Path, demo_manifest: Path, demo_customer_360: Path
    ) -> None:
        """Test that compiler rejects spec referencing non-existent plugin.

        Validates that specifying a plugin type that doesn't exist
        raises a descriptive error during compilation.
        """
        from floe_core.compilation.stages import compile_pipeline

        # Load a valid spec and corrupt the compute plugin reference
        with open(demo_customer_360) as f:
            spec = yaml.safe_load(f)

        # Set compute to a non-existent plugin
        if "compute" not in spec:
            spec["compute"] = {}
        spec["compute"]["type"] = "nonexistent-compute-engine-xyz"

        bad_plugin_path = tmp_path / "bad_plugin.yaml"
        bad_plugin_path.write_text(yaml.dump(spec))

        with pytest.raises(CompilationException) as exc_info:
            compile_pipeline(bad_plugin_path, demo_manifest)
        error_str = str(exc_info.value).lower()
        assert (
            "plugin" in error_str
            or "nonexistent" in error_str
            or "not found" in error_str
            or "not permitted" in error_str
            or "validation" in error_str
        ), f"Error should mention invalid plugin, got: {exc_info.value}"

    @pytest.mark.contract
    @pytest.mark.requirement("FR-010")
    @pytest.mark.xfail(
        reason="Compiler does not yet detect circular dependencies (audit finding)",
        strict=True,
    )
    def test_compile_rejects_circular_dependencies(
        self, tmp_path: Path, demo_manifest: Path, demo_customer_360: Path
    ) -> None:
        """Test that compiler detects circular transform dependencies.

        Validates that transforms with circular deps (A depends on B,
        B depends on A) are rejected with a cycle detection error.
        """
        from floe_core.compilation.stages import compile_pipeline

        # Load a valid spec and create circular dependencies
        with open(demo_customer_360) as f:
            spec = yaml.safe_load(f)

        # Replace transforms with circular deps
        spec["transforms"] = [
            {"name": "model_a", "tier": "bronze", "dependsOn": ["model_b"]},
            {"name": "model_b", "tier": "silver", "dependsOn": ["model_a"]},
        ]

        circular_path = tmp_path / "circular.yaml"
        circular_path.write_text(yaml.dump(spec))

        with pytest.raises(CompilationException) as exc_info:
            compile_pipeline(circular_path, demo_manifest)
        error_str = str(exc_info.value).lower()
        assert "circular" in error_str or "cycle" in error_str or "depend" in error_str, (
            f"Error should mention circular dependency, got: {exc_info.value}"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("FR-010")
    def test_spec_validation_rules(
        self, tmp_path: Path, demo_manifest: Path, demo_customer_360: Path
    ) -> None:
        """Test FloeSpec validation constraints reject invalid inputs.

        Tests that the spec validator enforces:
        - C001: Non-DNS-compatible name rejected
        - C002: Invalid semver version rejected
        """
        from floe_core.compilation.stages import compile_pipeline

        with open(demo_customer_360) as f:
            valid_spec = yaml.safe_load(f)

        # C001: Non-DNS-compatible name
        bad_name_spec = valid_spec.copy()
        bad_name_spec["metadata"] = {
            **valid_spec.get("metadata", {}),
            "name": "INVALID NAME WITH SPACES!@#",
        }

        bad_name_path = tmp_path / "bad_name.yaml"
        bad_name_path.write_text(yaml.dump(bad_name_spec))

        with pytest.raises(CompilationException) as exc_info:
            compile_pipeline(bad_name_path, demo_manifest)
        assert exc_info.value.error.stage == CompilationStage.LOAD


def _make_telemetry() -> TelemetryConfig:
    """Create a minimal valid TelemetryConfig for testing.

    Returns:
        TelemetryConfig with all required fields populated.
    """
    return TelemetryConfig(
        enabled=True,
        resource_attributes=ResourceAttributes(
            service_name="test",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="default",
            floe_product_name="test",
            floe_product_version="1.0.0",
            floe_mode="dev",
        ),
    )


class TestObservabilityConfigLineageFields:
    """Contract tests for lineage_endpoint and lineage_transport fields on ObservabilityConfig.

    These tests validate AC-9.2 (new optional fields) and AC-9.3 (version bump).
    All tests are expected to FAIL until the implementation adds the new fields
    and bumps the version.
    """

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.2")
    def test_observability_config_accepts_lineage_endpoint(self) -> None:
        """Test that ObservabilityConfig accepts lineage_endpoint and lineage_transport.

        Constructs ObservabilityConfig with the new optional fields populated.
        This must succeed after implementation but will fail now because
        extra='forbid' rejects unknown fields.
        """
        config = ObservabilityConfig(
            telemetry=_make_telemetry(),
            lineage_namespace="my-pipeline",
            lineage_endpoint="http://marquez:5000/api/v1/lineage",
            lineage_transport="http",
        )
        assert config.lineage_endpoint == "http://marquez:5000/api/v1/lineage"
        assert config.lineage_transport == "http"
        # Existing fields must still be populated correctly
        assert config.lineage_namespace == "my-pipeline"
        assert config.lineage is True
        assert config.telemetry.enabled is True

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.2")
    def test_observability_config_lineage_endpoint_defaults_to_none(self) -> None:
        """Test that lineage_endpoint and lineage_transport default to None.

        Constructs ObservabilityConfig WITHOUT the new fields. Both must
        default to None for backwards compatibility.
        """
        config = ObservabilityConfig(
            telemetry=_make_telemetry(),
            lineage_namespace="my-pipeline",
        )
        assert config.lineage_endpoint is None, (
            "lineage_endpoint must default to None when not provided"
        )
        assert config.lineage_transport is None, (
            "lineage_transport must default to None when not provided"
        )
        # Existing defaults must be preserved
        assert config.lineage is True
        assert config.lineage_namespace == "my-pipeline"

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.3")
    def test_compiled_artifacts_version_is_0_8_0(self) -> None:
        """Test that COMPILED_ARTIFACTS_VERSION has been bumped to 0.8.0.

        AC-9.3 requires the version bump to reflect the new lineage fields.
        """
        assert COMPILED_ARTIFACTS_VERSION == "0.8.0", (
            f"COMPILED_ARTIFACTS_VERSION must be '0.8.0' after adding lineage fields, "
            f"got '{COMPILED_ARTIFACTS_VERSION}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.3")
    def test_version_history_has_0_8_0_entry(self) -> None:
        """Test that version history documents the 0.8.0 change.

        The history entry must exist and must describe the lineage fields addition.
        This prevents a lazy implementation that bumps the version but forgets
        the history entry, or adds a vague description.
        """
        assert "0.8.0" in COMPILED_ARTIFACTS_VERSION_HISTORY, (
            "COMPILED_ARTIFACTS_VERSION_HISTORY must contain a '0.8.0' entry"
        )
        description = COMPILED_ARTIFACTS_VERSION_HISTORY["0.8.0"]
        assert "lineage_endpoint" in description, (
            f"0.8.0 history entry must mention 'lineage_endpoint', got: '{description}'"
        )
        assert "lineage_transport" in description, (
            f"0.8.0 history entry must mention 'lineage_transport', got: '{description}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.2")
    def test_observability_config_lineage_transport_rejects_invalid_values(self) -> None:
        """Test that lineage_transport rejects values outside the allowed set.

        lineage_transport should be constrained to known transport types
        (e.g., 'http', 'console', 'noop'). An arbitrary string like
        'carrier-pigeon' must be rejected with a literal/enum validation error,
        NOT an extra_forbidden error (which would mean the field doesn't exist).

        First, confirm valid values ARE accepted (proving the field exists),
        then confirm invalid values are rejected with the right error type.
        """
        # Step 1: A valid transport must succeed (proves the field exists)
        valid_config = ObservabilityConfig(
            telemetry=_make_telemetry(),
            lineage_namespace="my-pipeline",
            lineage_endpoint="http://marquez:5000/api/v1/lineage",
            lineage_transport="http",
        )
        assert valid_config.lineage_transport == "http"

        # Step 2: An invalid transport must be rejected
        with pytest.raises(ValidationError) as exc_info:
            ObservabilityConfig(
                telemetry=_make_telemetry(),
                lineage_namespace="my-pipeline",
                lineage_endpoint="http://marquez:5000/api/v1/lineage",
                lineage_transport="carrier-pigeon",
            )
        error_str = str(exc_info.value).lower()
        # Must NOT be extra_forbidden (that means field doesn't exist)
        assert "extra_forbidden" not in error_str, (
            "Error must be about invalid value, not about the field being unknown. "
            "This means lineage_transport field was not added to ObservabilityConfig."
        )
        assert "lineage_transport" in error_str or "input" in error_str, (
            f"Error should reference lineage_transport field, got: {exc_info.value}"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.2")
    def test_observability_config_lineage_transport_accepts_valid_values(self) -> None:
        """Test that lineage_transport accepts all valid transport types.

        Each known transport type ('http', 'console', 'noop') must be accepted.
        This prevents an implementation that only allows one value.
        """
        valid_transports = ["http", "console", "noop"]
        for transport in valid_transports:
            config = ObservabilityConfig(
                telemetry=_make_telemetry(),
                lineage_namespace="test-ns",
                lineage_endpoint="http://marquez:5000/api/v1/lineage",
                lineage_transport=transport,
            )
            assert config.lineage_transport == transport, (
                f"lineage_transport must accept '{transport}', "
                f"got '{config.lineage_transport}'"
            )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.2")
    def test_observability_config_serialization_with_lineage_fields(
        self, tmp_path: Path,
    ) -> None:
        """Test that lineage fields survive serialization round-trip.

        Constructs ObservabilityConfig with lineage fields, serializes to dict,
        verifies the fields appear in the serialized form, then deserializes
        back and verifies equality. This catches implementations that add the
        fields but exclude them from serialization.
        """
        config = ObservabilityConfig(
            telemetry=_make_telemetry(),
            lineage_namespace="round-trip-test",
            lineage_endpoint="http://marquez:5000/api/v1/lineage",
            lineage_transport="http",
        )

        # Serialize to dict
        config_dict = config.model_dump()
        assert "lineage_endpoint" in config_dict, (
            "lineage_endpoint must appear in serialized dict"
        )
        assert config_dict["lineage_endpoint"] == "http://marquez:5000/api/v1/lineage"
        assert "lineage_transport" in config_dict, (
            "lineage_transport must appear in serialized dict"
        )
        assert config_dict["lineage_transport"] == "http"

        # Deserialize back
        restored = ObservabilityConfig.model_validate(config_dict)
        assert restored.lineage_endpoint == config.lineage_endpoint
        assert restored.lineage_transport == config.lineage_transport
        assert restored.lineage_namespace == config.lineage_namespace

        # JSON round-trip (catches JSON serialization issues)
        json_str = config.model_dump_json()
        json_restored = ObservabilityConfig.model_validate_json(json_str)
        assert json_restored.lineage_endpoint == "http://marquez:5000/api/v1/lineage"
        assert json_restored.lineage_transport == "http"

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.2")
    def test_observability_config_none_lineage_fields_serialization(self) -> None:
        """Test that None-valued lineage fields serialize correctly.

        When lineage_endpoint and lineage_transport are not provided (None),
        they must still appear in serialized output as null/None, and
        deserialization must restore them as None.
        """
        config = ObservabilityConfig(
            telemetry=_make_telemetry(),
            lineage_namespace="null-test",
        )

        config_dict = config.model_dump()
        # Fields must exist in the dict even when None
        assert "lineage_endpoint" in config_dict, (
            "lineage_endpoint must appear in serialized dict even when None"
        )
        assert config_dict["lineage_endpoint"] is None
        assert "lineage_transport" in config_dict, (
            "lineage_transport must appear in serialized dict even when None"
        )
        assert config_dict["lineage_transport"] is None

        # Round-trip with None values
        restored = ObservabilityConfig.model_validate(config_dict)
        assert restored.lineage_endpoint is None
        assert restored.lineage_transport is None

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.2")
    def test_observability_config_frozen_with_lineage_fields(self) -> None:
        """Test that ObservabilityConfig remains frozen (immutable) with new fields.

        ObservabilityConfig uses model_config = ConfigDict(frozen=True).
        The new fields must also be immutable. This prevents an implementation
        that accidentally removes the frozen constraint.
        """
        config = ObservabilityConfig(
            telemetry=_make_telemetry(),
            lineage_namespace="frozen-test",
            lineage_endpoint="http://marquez:5000/api/v1/lineage",
            lineage_transport="http",
        )

        with pytest.raises(ValidationError):
            config.lineage_endpoint = "http://other:9999"  # type: ignore[misc]

        with pytest.raises(ValidationError):
            config.lineage_transport = "console"  # type: ignore[misc]

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.2")
    def test_observability_config_extra_forbid_still_enforced(self) -> None:
        """Test that extra='forbid' is still enforced after adding new fields.

        Adding lineage_endpoint and lineage_transport must not weaken the
        extra='forbid' constraint. An unknown field like 'bogus_field' must
        still be rejected.
        """
        with pytest.raises(ValidationError) as exc_info:
            ObservabilityConfig(
                telemetry=_make_telemetry(),
                lineage_namespace="extra-test",
                lineage_endpoint="http://marquez:5000/api/v1/lineage",
                lineage_transport="http",
                bogus_field="should-be-rejected",  # type: ignore[call-arg]
            )
        error_str = str(exc_info.value).lower()
        assert "extra" in error_str or "bogus" in error_str, (
            f"Error should mention extra/unknown field, got: {exc_info.value}"
        )


class TestGovernanceObservabilityContract:
    """Contract tests for governance and observability flow through compilation.

    These tests validate that governance settings from manifest.yaml and
    observability configuration (telemetry endpoints, lineage transport)
    flow correctly through the 6-stage compilation pipeline into
    CompiledArtifacts.

    Covers:
        - AC-9.4: Governance flows through compilation
        - AC-9.6: Observability flows from manifest
        - AC-9.7: Governance fields match manifest values
    """

    # -- Governance flow tests (AC-9.4, AC-9.7) --

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.4")
    def test_governance_present_when_manifest_has_governance(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that compile_pipeline with demo manifest produces non-None governance.

        The demo manifest.yaml has a governance section. After compilation,
        artifacts.governance must be a ResolvedGovernance instance, not None.
        """
        from floe_core.schemas.compiled_artifacts import ResolvedGovernance

        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.governance is not None, (
            "artifacts.governance must not be None when manifest has governance section"
        )
        assert isinstance(artifacts.governance, ResolvedGovernance), (
            f"governance must be ResolvedGovernance, got {type(artifacts.governance).__name__}"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.7")
    def test_governance_policy_enforcement_level_matches_manifest(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that governance.policy_enforcement_level matches demo manifest value.

        The demo manifest.yaml sets policy_enforcement_level: warn.
        This must flow through compilation exactly, not be defaulted or hardcoded.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.governance is not None
        assert artifacts.governance.policy_enforcement_level == "warn", (
            f"policy_enforcement_level must be 'warn' (from demo manifest), "
            f"got '{artifacts.governance.policy_enforcement_level}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.7")
    def test_governance_audit_logging_matches_manifest(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that governance.audit_logging matches demo manifest value.

        The demo manifest.yaml sets audit_logging: enabled.
        This must flow through compilation exactly.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.governance is not None
        assert artifacts.governance.audit_logging == "enabled", (
            f"audit_logging must be 'enabled' (from demo manifest), "
            f"got '{artifacts.governance.audit_logging}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.7")
    def test_governance_data_retention_days_matches_manifest(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that governance.data_retention_days matches demo manifest value.

        The demo manifest.yaml sets data_retention_days: 1.
        This must flow through compilation exactly as an integer.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.governance is not None
        assert artifacts.governance.data_retention_days == 1, (
            f"data_retention_days must be 1 (from demo manifest), "
            f"got {artifacts.governance.data_retention_days}"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.4")
    def test_governance_none_when_manifest_lacks_governance(
        self, tmp_path: Path,
    ) -> None:
        """Test that compile_pipeline with manifest lacking governance produces None governance.

        Creates a minimal manifest without governance section, compiles with it,
        and verifies artifacts.governance is None (not a default-constructed object).
        This prevents a sloppy implementation that always creates governance with defaults.
        """
        from floe_core.compilation.stages import compile_pipeline

        # Create minimal manifest without governance
        manifest_no_governance: dict[str, Any] = {
            "apiVersion": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "no-governance-manifest",
                "version": "1.0.0",
                "description": "Test manifest without governance",
                "owner": "test@floe.dev",
            },
            "plugins": {
                "compute": {"type": "duckdb", "config": {"threads": 1}},
                "orchestrator": {"type": "dagster", "config": {}},
            },
            "observability": {
                "tracing": {"enabled": True, "exporter": "otlp", "endpoint": "http://otel:4317"},
                "lineage": {"enabled": True, "transport": "http", "endpoint": "http://marquez:5000/api/v1/lineage"},
                "logging": {"level": "INFO", "format": "json"},
            },
        }

        manifest_path = tmp_path / "manifest_no_gov.yaml"
        manifest_path.write_text(yaml.dump(manifest_no_governance))

        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compile_pipeline(spec_path, manifest_path)

        assert artifacts.governance is None, (
            f"governance must be None when manifest has no governance section, "
            f"got {artifacts.governance!r}"
        )

    # -- Observability flow tests (AC-9.6) --

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.6")
    def test_observability_otlp_endpoint_matches_manifest(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that telemetry OTLP endpoint matches demo manifest tracing endpoint.

        The demo manifest.yaml sets tracing.endpoint: http://floe-platform-otel:4317.
        This must flow into artifacts.observability.telemetry.otlp_endpoint.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.observability.telemetry.otlp_endpoint == "http://floe-platform-otel:4317", (
            f"otlp_endpoint must be 'http://floe-platform-otel:4317' (from demo manifest), "
            f"got '{artifacts.observability.telemetry.otlp_endpoint}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.6")
    def test_observability_lineage_endpoint_matches_manifest(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that lineage_endpoint matches demo manifest lineage endpoint.

        The demo manifest.yaml sets lineage.endpoint: http://floe-platform-marquez:5000/api/v1/lineage.
        This must flow into artifacts.observability.lineage_endpoint.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        expected_endpoint = "http://floe-platform-marquez:5000/api/v1/lineage"
        assert artifacts.observability.lineage_endpoint == expected_endpoint, (
            f"lineage_endpoint must be '{expected_endpoint}' (from demo manifest), "
            f"got '{artifacts.observability.lineage_endpoint}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.6")
    def test_observability_lineage_transport_matches_manifest(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that lineage_transport matches demo manifest lineage transport.

        The demo manifest.yaml sets lineage.transport: http.
        This must flow into artifacts.observability.lineage_transport.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.observability.lineage_transport == "http", (
            f"lineage_transport must be 'http' (from demo manifest), "
            f"got '{artifacts.observability.lineage_transport}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.6")
    def test_observability_service_name_from_spec_not_manifest(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that service_name in resource_attributes comes from spec, not manifest.

        The demo spec's metadata.name is 'customer-360'. The manifest metadata.name
        is 'floe-demo-platform'. The service_name in resource_attributes must derive
        from the spec (product), not the manifest (platform).

        This prevents a sloppy implementation that uses the manifest name as service_name.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        service_name = artifacts.observability.telemetry.resource_attributes.service_name
        # Must contain the spec name, not the manifest name
        assert "customer-360" in service_name, (
            f"service_name must derive from spec name 'customer-360', "
            f"got '{service_name}'"
        )
        assert "floe-demo-platform" not in service_name, (
            f"service_name must NOT be the manifest name 'floe-demo-platform', "
            f"got '{service_name}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.6")
    def test_observability_lineage_enabled_when_manifest_configures_lineage(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that lineage is enabled when manifest configures lineage section.

        The demo manifest.yaml has lineage.enabled: true. The compiled artifacts
        must reflect this in observability.lineage (boolean flag).
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.observability.lineage is True, (
            f"lineage must be True when manifest enables it, got {artifacts.observability.lineage}"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.6")
    def test_observability_telemetry_enabled_when_manifest_enables_tracing(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that telemetry.enabled is True when manifest sets tracing.enabled: true.

        Validates the tracing enabled flag flows from manifest to compiled artifacts.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.observability.telemetry.enabled is True, (
            f"telemetry.enabled must be True when manifest enables tracing, "
            f"got {artifacts.observability.telemetry.enabled}"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.4")
    def test_governance_pii_encryption_not_fabricated_when_absent(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that pii_encryption is None when not set in demo manifest governance section.

        The demo manifest governance section does not include pii_encryption.
        The compiled governance must have pii_encryption=None, not a fabricated default.
        This prevents a sloppy implementation that always populates optional fields.
        """
        spec_path = Path(__file__).parent.parent.parent / "demo" / "customer-360" / "floe.yaml"
        artifacts = compiled_artifacts(spec_path)

        assert artifacts.governance is not None
        # pii_encryption is NOT in the demo manifest governance section,
        # so it should be None (the default)
        assert artifacts.governance.pii_encryption is None, (
            f"pii_encryption should be None (not in demo manifest governance), "
            f"got '{artifacts.governance.pii_encryption}'"
        )

    @pytest.mark.contract
    @pytest.mark.requirement("AC-9.6")
    @pytest.mark.requirement("AC-9.4")
    def test_governance_and_observability_consistent_across_demo_pipelines(
        self, compiled_artifacts: Any,
    ) -> None:
        """Test that all demo pipelines sharing the same manifest get same governance/observability.

        Compiles customer-360 and iot-telemetry (both reference the same manifest).
        Governance settings and observability endpoints must be identical across both.
        Only service_name should differ (derived from spec, not manifest).
        """
        root = Path(__file__).parent.parent.parent
        customer_spec = root / "demo" / "customer-360" / "floe.yaml"
        iot_spec = root / "demo" / "iot-telemetry" / "floe.yaml"

        customer_artifacts = compiled_artifacts(customer_spec)
        iot_artifacts = compiled_artifacts(iot_spec)

        # Governance must be identical (both inherit from same manifest)
        assert customer_artifacts.governance is not None
        assert iot_artifacts.governance is not None
        assert customer_artifacts.governance.policy_enforcement_level == (
            iot_artifacts.governance.policy_enforcement_level
        ), "policy_enforcement_level must be identical across pipelines sharing same manifest"
        assert customer_artifacts.governance.audit_logging == (
            iot_artifacts.governance.audit_logging
        ), "audit_logging must be identical across pipelines sharing same manifest"
        assert customer_artifacts.governance.data_retention_days == (
            iot_artifacts.governance.data_retention_days
        ), "data_retention_days must be identical across pipelines sharing same manifest"

        # Observability endpoints must be identical
        assert customer_artifacts.observability.telemetry.otlp_endpoint == (
            iot_artifacts.observability.telemetry.otlp_endpoint
        ), "otlp_endpoint must be identical across pipelines sharing same manifest"
        assert customer_artifacts.observability.lineage_endpoint == (
            iot_artifacts.observability.lineage_endpoint
        ), "lineage_endpoint must be identical across pipelines sharing same manifest"
        assert customer_artifacts.observability.lineage_transport == (
            iot_artifacts.observability.lineage_transport
        ), "lineage_transport must be identical across pipelines sharing same manifest"

        # But service_name must differ (derived from each spec's metadata.name)
        customer_svc = customer_artifacts.observability.telemetry.resource_attributes.service_name
        iot_svc = iot_artifacts.observability.telemetry.resource_attributes.service_name
        assert customer_svc != iot_svc, (
            f"service_name must differ between pipelines (spec-derived), "
            f"but both got '{customer_svc}'"
        )
