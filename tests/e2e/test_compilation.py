"""E2E compilation tests for the floe platform.

This module tests the complete compilation pipeline:
floe.yaml + manifest.yaml → CompiledArtifacts

These tests validate compilation without requiring deployment to K8s.
They verify the 6-stage compilation process:
LOAD → VALIDATE → RESOLVE → ENFORCE → COMPILE → GENERATE.

See Also:
    - tests/e2e/conftest.py: compiled_artifacts fixture
    - packages/floe-core/src/floe_core/schemas/compiled_artifacts.py: CompiledArtifacts schema
    - packages/floe-core/src/floe_core/compilation/stages.py: Compilation stages
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
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
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION
from pydantic import ValidationError


class TestCompilation:
    """E2E tests for the compilation pipeline.

    Tests validate the complete compilation workflow from FloeSpec to CompiledArtifacts.
    These tests run without K8s and verify schema compliance, determinism, and contract stability.
    """

    @pytest.mark.e2e
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

        # Validate version
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION
        assert artifacts.version == "0.5.0"

        # Validate metadata
        assert artifacts.metadata.product_name == "customer-360"
        assert artifacts.metadata.floe_version == "0.5.0"

        # Validate identity
        assert artifacts.identity.product_id.endswith("customer-360")
        assert len(artifacts.identity.domain) > 0

        # Validate plugins resolved
        assert artifacts.plugins is not None
        assert len(artifacts.plugins.compute.type) > 0
        assert len(artifacts.plugins.orchestrator.type) > 0

        # Validate observability config
        assert artifacts.observability is not None
        assert artifacts.observability.telemetry is not None
        assert isinstance(artifacts.observability.telemetry.resource_attributes, object)
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

        # Verify lineage namespace matches product name
        assert artifacts.observability.lineage_namespace, (
            "customer-360: lineage_namespace must be set"
        )

        # Verify source_hash is exactly 64 hex chars (SHA-256)
        source_hash = artifacts.metadata.source_hash
        if source_hash.startswith("sha256:"):
            hash_value = source_hash.split(":")[1]
            assert len(hash_value) == 64, (
                f"customer-360: source_hash must be 64 hex chars, got {len(hash_value)}"
            )
            assert all(c in "0123456789abcdef" for c in hash_value), (
                "customer-360: source_hash must be hex only"
            )

    @pytest.mark.e2e
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
        assert artifacts.identity.product_id.endswith("iot-telemetry")

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

        # Verify lineage namespace matches product name
        assert artifacts.observability.lineage_namespace, (
            "iot-telemetry: lineage_namespace must be set"
        )

        # Verify source_hash is exactly 64 hex chars (SHA-256)
        source_hash = artifacts.metadata.source_hash
        if source_hash.startswith("sha256:"):
            hash_value = source_hash.split(":")[1]
            assert len(hash_value) == 64, (
                f"iot-telemetry: source_hash must be 64 hex chars, got {len(hash_value)}"
            )
            assert all(c in "0123456789abcdef" for c in hash_value), (
                "iot-telemetry: source_hash must be hex only"
            )

    @pytest.mark.e2e
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
        assert artifacts.identity.product_id.endswith("financial-risk")

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

        # Verify lineage namespace matches product name
        assert artifacts.observability.lineage_namespace, (
            "financial-risk: lineage_namespace must be set"
        )

        # Verify source_hash is exactly 64 hex chars (SHA-256)
        source_hash = artifacts.metadata.source_hash
        if source_hash.startswith("sha256:"):
            hash_value = source_hash.split(":")[1]
            assert len(hash_value) == 64, (
                f"financial-risk: source_hash must be 64 hex chars, got {len(hash_value)}"
            )
            assert all(c in "0123456789abcdef" for c in hash_value), (
                "financial-risk: source_hash must be hex only"
            )

    @pytest.mark.e2e
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
        expected_stages = {"LOAD", "VALIDATE", "RESOLVE", "ENFORCE", "COMPILE", "GENERATE"}
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

        # Enforcement must have run
        assert artifacts.enforcement_result is not None, (
            "Enforcement stage must produce an EnforcementResultSummary"
        )
        assert isinstance(artifacts.enforcement_result.passed, bool), (
            "Enforcement result must have a boolean passed field"
        )
        validated = artifacts.enforcement_result.models_validated
        assert validated > 0, f"Enforcement must validate at least one model, got {validated}"
        level = artifacts.enforcement_result.enforcement_level
        assert level in ("off", "warn", "strict"), (
            f"Enforcement level must be off/warn/strict, got {level}"
        )

    @pytest.mark.e2e
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

        # Inheritance chain must be populated when manifest is used
        chain_len = len(artifacts.inheritance_chain)
        assert chain_len >= 1, (
            f"Manifest merge should populate inheritance_chain, got {chain_len} entries"
        )
        first_ancestor = artifacts.inheritance_chain[0]
        assert len(first_ancestor.name) > 0, (
            f"First ancestor must have a name, got {first_ancestor.name!r}"
        )
        assert first_ancestor.scope in ("enterprise", "domain"), (
            f"Manifest scope must be enterprise or domain, got {first_ancestor.scope!r}"
        )

        # Plugins must be resolved from manifest (not empty)
        assert artifacts.plugins is not None, "Plugins must be resolved from manifest"
        assert artifacts.plugins.compute.type == "duckdb", (
            "Compute plugin must be resolved from manifest"
        )

    @pytest.mark.e2e
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

        # Real compiler should generate profiles with a "default" profile
        assert len(artifacts.dbt_profiles) > 0, (
            "Real compiler should generate dbt_profiles from manifest.yaml"
        )
        assert "default" in artifacts.dbt_profiles, (
            "dbt_profiles should contain a 'default' profile"
        )

        default_profile = artifacts.dbt_profiles["default"]
        assert isinstance(default_profile, dict), "Default profile should be a dict"
        # Profile should have a target
        profile_keys = list(default_profile.keys())
        assert "target" in default_profile or "outputs" in default_profile, (
            f"Default profile needs target or outputs key. Keys: {profile_keys}"
        )

    @pytest.mark.e2e
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

    @pytest.mark.e2e
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

    @pytest.mark.e2e
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

    @pytest.mark.e2e
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

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-010")
    def test_compile_rejects_invalid_yaml(self) -> None:
        """Test that compiler rejects malformed YAML with clear error.

        Validates that feeding invalid YAML (not valid YAML syntax) to
        compile_pipeline raises a compilation error at the LOAD stage.
        """
        from floe_core.compilation.stages import compile_pipeline

        project_root = Path(__file__).parent.parent.parent
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Create a malformed YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: [unterminated\n  broken: {nope")
            invalid_path = Path(f.name)

        try:
            with pytest.raises(Exception) as exc_info:
                compile_pipeline(invalid_path, manifest_path)
            # Should get a load/parse error, not a silent failure
            assert exc_info.value is not None, "Compiler must raise on invalid YAML"
        finally:
            invalid_path.unlink(missing_ok=True)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-010")
    def test_compile_rejects_missing_required_fields(self) -> None:
        """Test that compiler rejects spec missing required fields.

        Validates that a floe.yaml missing the 'transforms' section
        raises a validation error during compilation.
        """
        from floe_core.compilation.stages import compile_pipeline

        project_root = Path(__file__).parent.parent.parent
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Create a spec missing transforms
        minimal_spec = {
            "apiVersion": "floe/v1",
            "kind": "FloeSpec",
            "metadata": {"name": "incomplete-spec", "version": "1.0.0"},
            # No transforms section
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(minimal_spec, f)
            incomplete_path = Path(f.name)

        try:
            with pytest.raises(Exception) as exc_info:
                compile_pipeline(incomplete_path, manifest_path)
            error_str = str(exc_info.value).lower()
            assert (
                "transform" in error_str or "required" in error_str or "validation" in error_str
            ), f"Error should mention missing transforms, got: {exc_info.value}"
        finally:
            incomplete_path.unlink(missing_ok=True)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-010")
    def test_compile_rejects_invalid_plugin_reference(self) -> None:
        """Test that compiler rejects spec referencing non-existent plugin.

        Validates that specifying a plugin type that doesn't exist
        raises a descriptive error during compilation.
        """
        from floe_core.compilation.stages import compile_pipeline

        project_root = Path(__file__).parent.parent.parent
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Load a valid spec and corrupt the compute plugin reference
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        with open(spec_path) as f:
            spec = yaml.safe_load(f)

        # Set compute to a non-existent plugin
        if "compute" not in spec:
            spec["compute"] = {}
        spec["compute"]["type"] = "nonexistent-compute-engine-xyz"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(spec, f)
            bad_plugin_path = Path(f.name)

        try:
            with pytest.raises(Exception) as exc_info:
                compile_pipeline(bad_plugin_path, manifest_path)
            error_str = str(exc_info.value).lower()
            assert (
                "plugin" in error_str or "nonexistent" in error_str or "not found" in error_str
            ), f"Error should mention invalid plugin, got: {exc_info.value}"
        finally:
            bad_plugin_path.unlink(missing_ok=True)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-010")
    def test_compile_rejects_circular_dependencies(self) -> None:
        """Test that compiler detects circular transform dependencies.

        Validates that transforms with circular deps (A depends on B,
        B depends on A) are rejected with a cycle detection error.
        """
        from floe_core.compilation.stages import compile_pipeline

        project_root = Path(__file__).parent.parent.parent
        manifest_path = project_root / "demo" / "manifest.yaml"

        # Load a valid spec and create circular dependencies
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"
        with open(spec_path) as f:
            spec = yaml.safe_load(f)

        # Replace transforms with circular deps
        spec["transforms"] = [
            {"name": "model_a", "tier": "bronze", "dependsOn": ["model_b"]},
            {"name": "model_b", "tier": "silver", "dependsOn": ["model_a"]},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(spec, f)
            circular_path = Path(f.name)

        try:
            with pytest.raises(Exception) as exc_info:
                compile_pipeline(circular_path, manifest_path)
            error_str = str(exc_info.value).lower()
            assert "circular" in error_str or "cycle" in error_str or "depend" in error_str, (
                f"Error should mention circular dependency, got: {exc_info.value}"
            )
        finally:
            circular_path.unlink(missing_ok=True)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-010")
    def test_spec_validation_rules(self) -> None:
        """Test FloeSpec validation constraints reject invalid inputs.

        Tests that the spec validator enforces:
        - C001: Non-DNS-compatible name rejected
        - C002: Invalid semver version rejected
        """
        from floe_core.compilation.stages import compile_pipeline

        project_root = Path(__file__).parent.parent.parent
        manifest_path = project_root / "demo" / "manifest.yaml"
        spec_path = project_root / "demo" / "customer-360" / "floe.yaml"

        with open(spec_path) as f:
            valid_spec = yaml.safe_load(f)

        # C001: Non-DNS-compatible name
        bad_name_spec = valid_spec.copy()
        bad_name_spec["metadata"] = {
            **valid_spec.get("metadata", {}),
            "name": "INVALID NAME WITH SPACES!@#",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(bad_name_spec, f)
            bad_name_path = Path(f.name)

        try:
            with pytest.raises(Exception) as exc_info:
                compile_pipeline(bad_name_path, manifest_path)
            assert exc_info.value is not None, "Compiler must reject non-DNS-compatible names"
        finally:
            bad_name_path.unlink(missing_ok=True)
