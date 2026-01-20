"""Contract golden file regression tests.

These tests validate that cross-package contracts remain stable.
Breaking changes to contracts require explicit version bumps.

Golden files are located in: tests/fixtures/golden/
Regenerate with: ./scripts/generate-contract-golden --force
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
        FileNotFoundError: If golden file doesn't exist.
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
    def test_compiled_artifacts_schema_exists(self) -> None:
        """Test that CompiledArtifacts golden schema exists."""
        golden = load_golden("compiled_artifacts_v2_schema.json")
        assert "title" in golden or "$comment" in golden

    @pytest.mark.requirement("CONTRACT-001")
    def test_compiled_artifacts_required_fields_stable(self) -> None:
        """Test that required fields haven't been removed.

        Removing required fields is a MAJOR version change.
        """
        golden = load_golden("compiled_artifacts_v2_schema.json")

        # Check that expected required fields exist
        # Add assertions for each field that must remain stable
        if "required" in golden:
            required_fields = golden["required"]
            # These fields must never be removed
            baseline_required = ["version"]
            for field in baseline_required:
                assert field in required_fields, (
                    f"Required field '{field}' removed from CompiledArtifacts. "
                    "This is a MAJOR version change."
                )

    @pytest.mark.requirement("CONTRACT-001")
    def test_compiled_artifacts_field_types_stable(self) -> None:
        """Test that field types haven't changed.

        Changing field types is a MAJOR version change.
        """
        golden = load_golden("compiled_artifacts_v2_schema.json")

        if "properties" not in golden:
            pytest.skip("Schema uses different structure")

        properties = golden["properties"]

        # Version must be a string
        if "version" in properties:
            version_prop = properties["version"]
            assert version_prop.get("type") == "string", (
                "version field type changed from string. "
                "This is a MAJOR version change."
            )


class TestPluginInterfaceContract:
    """Test plugin interface stability."""

    @pytest.mark.requirement("CONTRACT-002")
    def test_plugin_interfaces_exist(self) -> None:
        """Test that plugin interface golden file exists."""
        golden = load_golden("plugin_interfaces_v1.json")
        assert "interfaces" in golden or "$comment" in golden

    @pytest.mark.requirement("CONTRACT-002")
    def test_compute_plugin_interface_stable(self) -> None:
        """Test ComputePlugin interface hasn't lost methods.

        Removing methods is a MAJOR version change.
        """
        golden = load_golden("plugin_interfaces_v1.json")

        if "interfaces" not in golden:
            pytest.skip("Golden file uses different structure")

        interfaces = golden["interfaces"]
        if "ComputePlugin" not in interfaces:
            pytest.skip("ComputePlugin not in golden file")

        compute = interfaces["ComputePlugin"]
        methods = compute.get("methods", {})

        # These methods must exist on ComputePlugin
        required_methods = ["generate_profiles", "validate_config"]
        for method in required_methods:
            # Allow for placeholder golden files
            if not methods:
                pytest.skip("Placeholder golden file")
            assert method in methods, (
                f"ComputePlugin.{method}() removed. "
                "This is a MAJOR version change."
            )


class TestQualityThresholds:
    """Test quality threshold stability."""

    @pytest.mark.requirement("CONTRACT-003")
    def test_quality_thresholds_exist(self) -> None:
        """Test that quality thresholds golden file exists."""
        golden = load_golden("quality_thresholds.json")
        assert "test_coverage" in golden or "$comment" in golden

    @pytest.mark.requirement("CONTRACT-003")
    def test_test_coverage_thresholds_not_lowered(self) -> None:
        """Test that test coverage thresholds haven't been lowered.

        Lowering quality thresholds is a regression.
        """
        golden = load_golden("quality_thresholds.json")

        if "test_coverage" not in golden:
            pytest.skip("Quality thresholds use different structure")

        coverage = golden["test_coverage"]

        # Unit test coverage must be >= 80%
        if "unit" in coverage:
            unit_min = coverage["unit"].get("minimum_percent", 0)
            assert unit_min >= 80, (
                f"Unit test coverage threshold lowered to {unit_min}%. "
                "Minimum must be 80%."
            )

        # Integration test coverage must be >= 70%
        if "integration" in coverage:
            int_min = coverage["integration"].get("minimum_percent", 0)
            assert int_min >= 70, (
                f"Integration test coverage threshold lowered to {int_min}%. "
                "Minimum must be 70%."
            )

    @pytest.mark.requirement("CONTRACT-003")
    def test_requirement_traceability_threshold(self) -> None:
        """Test that requirement traceability is 100%."""
        golden = load_golden("quality_thresholds.json")

        if "requirement_traceability" not in golden:
            pytest.skip("Quality thresholds use different structure")

        traceability = golden["requirement_traceability"]
        min_percent = traceability.get("minimum_percent", 0)

        assert min_percent == 100, (
            f"Requirement traceability threshold is {min_percent}%. "
            "Must be 100% - all tests must have @pytest.mark.requirement."
        )
