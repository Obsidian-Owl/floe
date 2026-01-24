"""Contract tests for manifest schema stability.

These tests ensure the PlatformManifest schema remains stable and
backward-compatible. Breaking changes should fail these tests.

Task: T015
Requirements: FR-001
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Path to golden fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestManifestSchemaContract:
    """Contract tests for PlatformManifest schema stability.

    These tests verify that the schema structure remains stable
    and that existing valid manifests continue to work.
    """

    @pytest.mark.requirement("001-FR-001")
    def test_required_fields_contract(self) -> None:
        """Contract: PlatformManifest requires api_version, kind, metadata, plugins.

        This test ensures that the required field set doesn't expand,
        which would break existing manifests.
        """
        from floe_core.schemas import PlatformManifest

        # Minimal manifest with only required fields MUST work
        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "test",
                "version": "1.0.0",
                "owner": "test",
            },
            plugins={},
        )
        assert manifest.api_version == "floe.dev/v1"
        assert manifest.kind == "Manifest"

    @pytest.mark.requirement("001-FR-001")
    def test_api_version_contract(self) -> None:
        """Contract: api_version must be 'floe.dev/v1'.

        This test ensures the API version format remains stable.
        New versions should be additive (floe.dev/v2), not changes.
        """
        from floe_core.schemas import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={"name": "test", "version": "1.0.0", "owner": "test"},
            plugins={},
        )
        assert manifest.api_version == "floe.dev/v1"

    @pytest.mark.requirement("001-FR-001")
    def test_metadata_fields_contract(self) -> None:
        """Contract: ManifestMetadata requires name, version, owner.

        This test ensures the metadata structure remains stable.
        """
        from floe_core.schemas import ManifestMetadata

        # Required fields MUST work
        metadata = ManifestMetadata(
            name="test-platform",
            version="1.0.0",
            owner="team@example.com",
        )
        assert metadata.name == "test-platform"
        assert metadata.version == "1.0.0"
        assert metadata.owner == "team@example.com"
        assert metadata.description is None  # Optional field

    @pytest.mark.requirement("001-FR-001")
    def test_plugins_config_categories_contract(self) -> None:
        """Contract: PluginsConfig has exactly 11 plugin categories.

        This test ensures the plugin category set remains stable.
        Adding new categories is fine; removing categories breaks contract.
        """
        from floe_core.schemas import PluginsConfig

        plugins = PluginsConfig()

        # All 12 categories MUST exist as fields
        # Per ADR-0035, observability is split into telemetry_backend and lineage_backend
        expected_categories = [
            "compute",
            "orchestrator",
            "catalog",
            "storage",
            "semantic_layer",
            "ingestion",
            "secrets",
            "telemetry_backend",
            "lineage_backend",
            "identity",
            "dbt",
            "quality",
        ]

        for category in expected_categories:
            assert hasattr(plugins, category), f"Missing category: {category}"

        # Most categories should be None by default (optional)
        optional_categories = [c for c in expected_categories if c != "dbt"]
        for category in optional_categories:
            assert getattr(plugins, category) is None, (
                f"Category '{category}' should be None by default"
            )

        # dbt is ENFORCED technology and defaults to 'core' (per Epic 5A)
        assert plugins.dbt is not None
        assert plugins.dbt.type == "core"

    @pytest.mark.requirement("001-FR-001")
    def test_plugin_selection_fields_contract(self) -> None:
        """Contract: PluginSelection has type, config, connection_secret_ref.

        This test ensures the plugin selection structure remains stable.
        """
        from floe_core.schemas import PluginSelection

        selection = PluginSelection(
            type="duckdb",
            config={"threads": 4},
            connection_secret_ref="db-secret",
        )
        assert selection.type == "duckdb"
        assert selection.config == {"threads": 4}
        assert selection.connection_secret_ref == "db-secret"

    @pytest.mark.requirement("001-FR-001")
    def test_governance_config_fields_contract(self) -> None:
        """Contract: GovernanceConfig has security policy fields.

        This test ensures the governance structure remains stable.
        """
        from floe_core.schemas import GovernanceConfig

        governance = GovernanceConfig(
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=90,
        )
        assert governance.pii_encryption == "required"
        assert governance.audit_logging == "enabled"
        assert governance.policy_enforcement_level == "strict"
        assert governance.data_retention_days == 90

    @pytest.mark.requirement("001-FR-001")
    def test_scope_values_contract(self) -> None:
        """Contract: scope accepts None, 'enterprise', 'domain'.

        This test ensures the scope values remain stable.
        """
        from floe_core.schemas import PlatformManifest

        base_args: dict[str, Any] = {
            "api_version": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {"name": "test", "version": "1.0.0", "owner": "test"},
            "plugins": {},
        }

        # scope=None (2-tier) MUST work
        manifest_2tier = PlatformManifest(**base_args, scope=None)
        assert manifest_2tier.scope is None

        # scope="enterprise" MUST work
        manifest_enterprise = PlatformManifest(**base_args, scope="enterprise")
        assert manifest_enterprise.scope == "enterprise"

        # scope="domain" with parent MUST work
        manifest_domain = PlatformManifest(
            **base_args,
            scope="domain",
            parent_manifest="oci://registry/manifest:v1",
        )
        assert manifest_domain.scope == "domain"


class TestManifestSchemaBackwardCompatibility:
    """Tests for backward compatibility of manifest loading."""

    @pytest.mark.requirement("001-FR-001")
    def test_dict_loading_contract(self) -> None:
        """Contract: PlatformManifest can be created from dict.

        This is critical for YAML loading compatibility.
        """
        from floe_core.schemas import PlatformManifest

        data: dict[str, Any] = {
            "api_version": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "test",
                "version": "1.0.0",
                "owner": "test",
            },
            "plugins": {},
        }
        manifest = PlatformManifest.model_validate(data)
        assert manifest.metadata.name == "test"

    @pytest.mark.requirement("001-FR-001")
    def test_nested_dict_loading_contract(self) -> None:
        """Contract: Nested structures load from dicts correctly."""
        from floe_core.schemas import PlatformManifest

        data: dict[str, Any] = {
            "api_version": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "test",
                "version": "1.0.0",
                "owner": "test",
            },
            "plugins": {
                "compute": {"type": "duckdb"},
            },
            "governance": {
                "pii_encryption": "required",
            },
        }
        manifest = PlatformManifest.model_validate(data)
        assert manifest.plugins.compute is not None
        assert manifest.plugins.compute.type == "duckdb"
        assert manifest.governance is not None
        assert manifest.governance.pii_encryption == "required"

    @pytest.mark.requirement("001-FR-001")
    @pytest.mark.requirement("001-FR-009")
    def test_json_schema_export_contract(self) -> None:
        """Contract: PlatformManifest can export JSON Schema.

        This is critical for IDE autocomplete support.
        Note: JSON Schema uses aliases (apiVersion) for Kubernetes compatibility.
        """
        from floe_core.schemas import PlatformManifest

        schema = PlatformManifest.model_json_schema()

        # Schema must have expected structure
        # Note: api_version uses alias 'apiVersion' in JSON Schema
        assert "properties" in schema
        assert "apiVersion" in schema["properties"]
        assert "kind" in schema["properties"]
        assert "metadata" in schema["properties"]
        assert "plugins" in schema["properties"]

        # Required fields must be marked (using alias name)
        assert "required" in schema
        assert "apiVersion" in schema["required"]
        assert "kind" in schema["required"]
        assert "metadata" in schema["required"]
        assert "plugins" in schema["required"]


class TestManifestSchemaExports:
    """Tests for public API exports from floe_core.schemas."""

    @pytest.mark.requirement("001-FR-001")
    def test_public_exports_contract(self) -> None:
        """Contract: Key models are exported from floe_core.schemas.

        This ensures the public API remains stable.
        """
        from floe_core import schemas

        # Core models MUST be exported
        assert hasattr(schemas, "PlatformManifest")
        assert hasattr(schemas, "ManifestMetadata")
        assert hasattr(schemas, "PluginsConfig")
        assert hasattr(schemas, "PluginSelection")
        assert hasattr(schemas, "GovernanceConfig")

        # Supporting types MUST be exported
        assert hasattr(schemas, "ManifestScope")
        assert hasattr(schemas, "SecretSource")
        assert hasattr(schemas, "SecretReference")
        assert hasattr(schemas, "MergeStrategy")

    @pytest.mark.requirement("001-FR-001")
    def test_all_exports_importable(self) -> None:
        """Contract: All __all__ exports are importable."""
        from floe_core.schemas import __all__

        for name in __all__:
            # Import should not raise
            module = __import__("floe_core.schemas", fromlist=[name])
            assert hasattr(module, name), f"Missing export: {name}"


class TestGoldenArtifactCompatibility:
    """Tests for backward compatibility with golden manifest fixtures.

    Golden fixtures represent manifests created at a specific schema version.
    These tests ensure that schema evolution does not break existing manifests.
    """

    @pytest.mark.requirement("001-FR-001")
    def test_v1_golden_manifest_parses(self) -> None:
        """Contract: v1.0 golden manifest continues to parse correctly.

        This is a regression test ensuring backward compatibility.
        If this test fails, the schema change is potentially breaking.
        """
        from floe_core.schemas import PlatformManifest

        fixture_path = FIXTURES_DIR / "v1.0_manifest.json"
        assert fixture_path.exists(), f"Golden fixture not found: {fixture_path}"

        with fixture_path.open() as f:
            data = json.load(f)

        # Should parse without errors
        manifest = PlatformManifest.model_validate(data)

        # Verify key fields are preserved
        assert manifest.api_version == "floe.dev/v1"
        assert manifest.kind == "Manifest"
        assert manifest.metadata.name == "golden-platform"
        assert manifest.scope == "enterprise"

    @pytest.mark.requirement("001-FR-001")
    def test_v1_golden_manifest_plugins_preserved(self) -> None:
        """Contract: v1.0 golden manifest plugin configurations are preserved."""
        from floe_core.schemas import PlatformManifest

        fixture_path = FIXTURES_DIR / "v1.0_manifest.json"
        with fixture_path.open() as f:
            data = json.load(f)

        manifest = PlatformManifest.model_validate(data)

        # Plugin selections must be preserved
        assert manifest.plugins.compute is not None
        assert manifest.plugins.compute.type == "duckdb"
        assert manifest.plugins.compute.config == {"threads": 4, "memory_limit": "8GB"}

        assert manifest.plugins.orchestrator is not None
        assert manifest.plugins.orchestrator.type == "dagster"

        assert manifest.plugins.catalog is not None
        assert manifest.plugins.catalog.type == "polaris"
        assert manifest.plugins.catalog.connection_secret_ref == "polaris-credentials"

    @pytest.mark.requirement("001-FR-001")
    def test_v1_golden_manifest_governance_preserved(self) -> None:
        """Contract: v1.0 golden manifest governance config is preserved."""
        from floe_core.schemas import PlatformManifest

        fixture_path = FIXTURES_DIR / "v1.0_manifest.json"
        with fixture_path.open() as f:
            data = json.load(f)

        manifest = PlatformManifest.model_validate(data)

        # Governance settings must be preserved
        assert manifest.governance is not None
        assert manifest.governance.pii_encryption == "required"
        assert manifest.governance.audit_logging == "enabled"
        assert manifest.governance.policy_enforcement_level == "strict"
        assert manifest.governance.data_retention_days == 90

    @pytest.mark.requirement("001-FR-001")
    def test_v1_golden_manifest_roundtrip(self) -> None:
        """Contract: v1.0 golden manifest survives roundtrip serialization."""
        from floe_core.schemas import PlatformManifest

        fixture_path = FIXTURES_DIR / "v1.0_manifest.json"
        with fixture_path.open() as f:
            original_data = json.load(f)

        manifest = PlatformManifest.model_validate(original_data)

        # Serialize back to dict (using aliases for JSON compatibility)
        exported = manifest.model_dump(mode="json", by_alias=True)

        # Key fields should match original (excluding None values)
        assert exported["apiVersion"] == original_data["apiVersion"]
        assert exported["kind"] == original_data["kind"]
        assert exported["metadata"]["name"] == original_data["metadata"]["name"]


class TestPluginRegistryCompleteness:
    """Tests for PLUGIN_REGISTRY completeness."""

    @pytest.mark.requirement("001-FR-006")
    def test_plugin_registry_has_all_12_categories(self) -> None:
        """Contract: PLUGIN_REGISTRY has entries for all 12 plugin categories.

        Per ADR-0035, the registry must have:
        - Original 10 categories
        - telemetry_backend (split from observability)
        - lineage_backend (split from observability)
        """
        from floe_core.schemas.plugins import PLUGIN_REGISTRY

        expected_categories = {
            "compute",
            "orchestrator",
            "catalog",
            "storage",
            "semantic_layer",
            "ingestion",
            "secrets",
            "telemetry_backend",
            "lineage_backend",
            "identity",
            "dbt",
            "quality",
        }

        assert set(PLUGIN_REGISTRY.keys()) == expected_categories, (
            f"PLUGIN_REGISTRY missing or has extra categories. "
            f"Expected: {expected_categories}, Got: {set(PLUGIN_REGISTRY.keys())}"
        )

    @pytest.mark.requirement("001-FR-006")
    def test_plugin_registry_categories_have_options(self) -> None:
        """Contract: Each PLUGIN_REGISTRY category has at least one option."""
        from floe_core.schemas.plugins import PLUGIN_REGISTRY

        for category, plugins in PLUGIN_REGISTRY.items():
            assert isinstance(plugins, list), f"{category} should be a list"
            assert len(plugins) >= 1, f"{category} should have at least one plugin option"
            for plugin in plugins:
                assert isinstance(plugin, str), f"{category} plugins should be strings"
                assert len(plugin) > 0, f"{category} has empty plugin name"
