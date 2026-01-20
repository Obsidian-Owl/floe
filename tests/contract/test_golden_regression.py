"""Contract golden file regression tests.

These tests validate that cross-package contracts remain stable.
Breaking changes to contracts require explicit version bumps.

Golden files are located in: tests/fixtures/golden/
Regenerate with: ./scripts/generate-contract-golden --force

IMPORTANT: These tests should FAIL loudly when structure is wrong.
No early returns, no silent passes. If something is missing, FAIL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden"


def load_golden(filename: str) -> dict[str, Any]:
    """Load a golden file.

    Args:
        filename: Name of the golden file to load.

    Returns:
        Parsed JSON content.

    Raises:
        pytest.fail: If golden file doesn't exist.
    """
    filepath = GOLDEN_DIR / filename
    if not filepath.exists():
        pytest.fail(
            f"Golden file not found: {filepath}\n"
            "Run './scripts/generate-contract-golden' to create baseline."
        )
    return json.loads(filepath.read_text())


class TestCompiledArtifactsContract:
    """Test CompiledArtifacts schema stability."""

    @pytest.mark.requirement("CONTRACT-001")
    def test_compiled_artifacts_schema_structure(self) -> None:
        """Test that CompiledArtifacts golden schema has expected structure."""
        golden = load_golden("compiled_artifacts_v2_schema.json")

        # Schema MUST have these fields - no excuses
        assert "$comment" in golden, (
            "Schema missing '$comment' metadata. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )
        assert "title" in golden, (
            "Schema missing 'title' field. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )
        assert golden["title"] == "CompiledArtifacts", (
            f"Schema title is '{golden['title']}', expected 'CompiledArtifacts'. "
            "This indicates schema corruption or wrong file."
        )

    @pytest.mark.requirement("CONTRACT-001")
    def test_compiled_artifacts_required_fields_stable(self) -> None:
        """Test that required fields haven't been removed.

        Removing required fields is a MAJOR version change.
        """
        golden = load_golden("compiled_artifacts_v2_schema.json")

        # required section MUST exist
        assert "required" in golden, (
            "Schema missing 'required' section. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )

        required_fields = golden["required"]

        # These fields must never be removed
        baseline_required = ["version"]
        for field in baseline_required:
            assert field in required_fields, (
                f"Required field '{field}' removed from CompiledArtifacts. "
                "This is a MAJOR version change."
            )

    @pytest.mark.requirement("CONTRACT-001")
    def test_compiled_artifacts_properties_stable(self) -> None:
        """Test that property types haven't changed.

        Changing field types is a MAJOR version change.
        """
        golden = load_golden("compiled_artifacts_v2_schema.json")

        # properties section MUST exist
        assert "properties" in golden, (
            "Schema missing 'properties' section. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )

        properties = golden["properties"]

        # version field MUST exist and be string type
        assert "version" in properties, (
            "Schema missing 'version' property. "
            "This is a breaking change."
        )
        assert properties["version"].get("type") == "string", (
            f"version field type is '{properties['version'].get('type')}', expected 'string'. "
            "This is a MAJOR version change."
        )

        # metadata, dbt_profiles, dagster_config MUST exist
        expected_properties = ["metadata", "dbt_profiles", "dagster_config"]
        for prop in expected_properties:
            assert prop in properties, (
                f"Schema missing '{prop}' property. "
                "This is a breaking change."
            )


class TestPluginInterfaceContract:
    """Test plugin interface stability."""

    @pytest.mark.requirement("CONTRACT-002")
    def test_plugin_interfaces_structure(self) -> None:
        """Test that plugin interface golden file has expected structure."""
        golden = load_golden("plugin_interfaces_v1.json")

        # MUST have these fields
        assert "$comment" in golden, (
            "Golden file missing '$comment' metadata. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )
        assert "interfaces" in golden, (
            "Golden file missing 'interfaces' section. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )

    @pytest.mark.requirement("CONTRACT-002")
    def test_all_plugin_interfaces_exist(self) -> None:
        """Test that all expected plugin interfaces are defined."""
        golden = load_golden("plugin_interfaces_v1.json")

        assert "interfaces" in golden, "Missing 'interfaces' section"
        interfaces = golden["interfaces"]

        # All four plugin interfaces MUST exist
        required_interfaces = [
            "ComputePlugin",
            "OrchestratorPlugin",
            "CatalogPlugin",
            "StoragePlugin",
        ]
        for interface in required_interfaces:
            assert interface in interfaces, (
                f"Missing '{interface}' from plugin interfaces. "
                "This is a breaking change."
            )

    @pytest.mark.requirement("CONTRACT-002")
    def test_compute_plugin_methods_stable(self) -> None:
        """Test ComputePlugin interface hasn't lost methods."""
        golden = load_golden("plugin_interfaces_v1.json")
        interfaces = golden["interfaces"]

        assert "ComputePlugin" in interfaces, "Missing ComputePlugin"
        compute = interfaces["ComputePlugin"]

        assert "methods" in compute, (
            "ComputePlugin missing 'methods' key. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )

        methods = compute["methods"]
        required_methods = ["generate_profiles", "validate_config"]
        for method in required_methods:
            assert method in methods, (
                f"ComputePlugin.{method}() removed. "
                "This is a MAJOR version change."
            )

    @pytest.mark.requirement("CONTRACT-002")
    def test_orchestrator_plugin_methods_stable(self) -> None:
        """Test OrchestratorPlugin interface hasn't lost methods."""
        golden = load_golden("plugin_interfaces_v1.json")
        interfaces = golden["interfaces"]

        assert "OrchestratorPlugin" in interfaces, "Missing OrchestratorPlugin"
        orchestrator = interfaces["OrchestratorPlugin"]

        assert "methods" in orchestrator, (
            "OrchestratorPlugin missing 'methods' key. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )

        methods = orchestrator["methods"]
        required_methods = ["create_assets", "create_schedules"]
        for method in required_methods:
            assert method in methods, (
                f"OrchestratorPlugin.{method}() removed. "
                "This is a MAJOR version change."
            )

    @pytest.mark.requirement("CONTRACT-002")
    def test_catalog_plugin_methods_stable(self) -> None:
        """Test CatalogPlugin interface hasn't lost methods."""
        golden = load_golden("plugin_interfaces_v1.json")
        interfaces = golden["interfaces"]

        assert "CatalogPlugin" in interfaces, "Missing CatalogPlugin"
        catalog = interfaces["CatalogPlugin"]

        assert "methods" in catalog, (
            "CatalogPlugin missing 'methods' key. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )

        methods = catalog["methods"]
        required_methods = ["create_namespace", "load_table"]
        for method in required_methods:
            assert method in methods, (
                f"CatalogPlugin.{method}() removed. "
                "This is a MAJOR version change."
            )

    @pytest.mark.requirement("CONTRACT-002")
    def test_storage_plugin_methods_stable(self) -> None:
        """Test StoragePlugin interface hasn't lost methods."""
        golden = load_golden("plugin_interfaces_v1.json")
        interfaces = golden["interfaces"]

        assert "StoragePlugin" in interfaces, "Missing StoragePlugin"
        storage = interfaces["StoragePlugin"]

        assert "methods" in storage, (
            "StoragePlugin missing 'methods' key. "
            "Regenerate with ./scripts/generate-contract-golden --force"
        )

        methods = storage["methods"]
        required_methods = ["read_table", "write_table"]
        for method in required_methods:
            assert method in methods, (
                f"StoragePlugin.{method}() removed. "
                "This is a MAJOR version change."
            )


class TestQualityThresholds:
    """Test quality threshold stability."""

    @pytest.mark.requirement("CONTRACT-003")
    def test_quality_thresholds_structure(self) -> None:
        """Test that quality thresholds golden file has expected structure."""
        golden = load_golden("quality_thresholds.json")

        # MUST have these sections
        required_sections = [
            "test_coverage",
            "requirement_traceability",
            "code_quality",
            "security",
            "architecture",
        ]
        for section in required_sections:
            assert section in golden, (
                f"Quality thresholds missing '{section}' section. "
                "Regenerate with ./scripts/generate-contract-golden --force"
            )

    @pytest.mark.requirement("CONTRACT-003")
    def test_test_coverage_thresholds_not_lowered(self) -> None:
        """Test that test coverage thresholds haven't been lowered."""
        golden = load_golden("quality_thresholds.json")
        coverage = golden["test_coverage"]

        # Unit test threshold MUST exist and be >= 80%
        assert "unit" in coverage, "Missing 'unit' coverage threshold"
        unit_min = coverage["unit"].get("minimum_percent", 0)
        assert unit_min >= 80, (
            f"Unit test coverage threshold lowered to {unit_min}%. "
            "Minimum must be 80%."
        )

        # Integration test threshold MUST exist and be >= 70%
        assert "integration" in coverage, "Missing 'integration' coverage threshold"
        int_min = coverage["integration"].get("minimum_percent", 0)
        assert int_min >= 70, (
            f"Integration test coverage threshold lowered to {int_min}%. "
            "Minimum must be 70%."
        )

    @pytest.mark.requirement("CONTRACT-003")
    def test_requirement_traceability_is_100_percent(self) -> None:
        """Test that requirement traceability is 100%."""
        golden = load_golden("quality_thresholds.json")
        traceability = golden["requirement_traceability"]

        min_percent = traceability.get("minimum_percent", 0)
        assert min_percent == 100, (
            f"Requirement traceability threshold is {min_percent}%. "
            "Must be 100% - all tests must have @pytest.mark.requirement."
        )

    @pytest.mark.requirement("CONTRACT-003")
    def test_security_thresholds_are_zero_tolerance(self) -> None:
        """Test that security thresholds don't allow critical/high issues."""
        golden = load_golden("quality_thresholds.json")
        security = golden["security"]

        assert security.get("allowed_critical_issues", 1) == 0, (
            "Security threshold allows critical issues. Must be 0."
        )
        assert security.get("allowed_high_issues", 1) == 0, (
            "Security threshold allows high issues. Must be 0."
        )

    @pytest.mark.requirement("CONTRACT-003")
    def test_architecture_violations_not_allowed(self) -> None:
        """Test that architecture violations are not allowed."""
        golden = load_golden("quality_thresholds.json")
        architecture = golden["architecture"]

        assert architecture.get("allowed_violations", 1) == 0, (
            "Architecture threshold allows violations. Must be 0."
        )
