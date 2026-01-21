"""Unit tests for SARIF exporter (US5).

TDD tests for export_sarif() function. Tests verify:
- Output conforms to SARIF 2.1.0 schema (FR-021)
- Violations mapped to SARIF results correctly
- Rule definitions included for all FLOE-Exxx codes
- GitHub Code Scanning compatibility

Task: T052
Requirements: FR-021 (SARIF 2.1.0 export format)

TDD Pattern: These tests are written FIRST and should FAIL until
T055 implements the SARIF exporter.

SARIF 2.1.0 Reference: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from floe_core.enforcement.result import (
    EnforcementResult,
    EnforcementSummary,
    Violation,
)

if TYPE_CHECKING:
    pass


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def sample_violations() -> list[Violation]:
    """Create sample violations covering different policy types."""
    return [
        Violation(
            error_code="FLOE-E201",
            severity="error",
            policy_type="naming",
            model_name="stg_customers",
            message="Model 'stg_customers' violates medallion naming convention",
            expected="Pattern: bronze_*, silver_*, gold_*",
            actual="stg_customers",
            suggestion="Rename model to bronze_customers",
            documentation_url="https://floe.dev/docs/enforcement/naming",
        ),
        Violation(
            error_code="FLOE-E210",
            severity="warning",
            policy_type="coverage",
            model_name="bronze_orders",
            column_name="order_id",
            message="Column 'order_id' lacks required test coverage",
            expected="Test coverage >= 80%",
            actual="Test coverage is 50%",
            suggestion="Add not_null and unique tests",
            documentation_url="https://floe.dev/docs/enforcement/coverage",
        ),
        Violation(
            error_code="FLOE-E301",
            severity="error",
            policy_type="semantic",
            model_name="silver_products",
            message="Referenced model 'stg_inventory' does not exist",
            expected="Model should exist in manifest",
            actual="Model 'stg_inventory' not found",
            suggestion="Create stg_inventory or fix the ref()",
            documentation_url="https://floe.dev/docs/enforcement/semantic",
        ),
    ]


@pytest.fixture
def sample_enforcement_result(sample_violations: list[Violation]) -> EnforcementResult:
    """Create a sample enforcement result with multiple violations."""
    return EnforcementResult(
        passed=False,
        violations=sample_violations,
        summary=EnforcementSummary(
            total_models=20,
            models_validated=20,
            naming_violations=1,
            coverage_violations=1,
            documentation_violations=0,
            semantic_violations=1,
            custom_rule_violations=0,
            overrides_applied=0,
            duration_ms=200.0,
        ),
        enforcement_level="strict",
        manifest_version="1.8.0",
        timestamp=datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def empty_enforcement_result() -> EnforcementResult:
    """Create a passing enforcement result with no violations."""
    return EnforcementResult(
        passed=True,
        violations=[],
        summary=EnforcementSummary(
            total_models=10,
            models_validated=10,
        ),
        enforcement_level="strict",
        manifest_version="1.8.0",
        timestamp=datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
    )


# ==============================================================================
# T052: Tests for SARIF Export (FR-021)
# ==============================================================================


class TestSarifExporter:
    """Tests for SARIF 2.1.0 export functionality.

    FR-021: SARIF output MUST conform to SARIF 2.1.0 schema for
    GitHub Code Scanning integration.
    """

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_creates_valid_sarif_file(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export_sarif creates a valid SARIF file.

        Given: An EnforcementResult with violations
        When: export_sarif is called
        Then: A valid SARIF JSON file is created
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        assert output_path.exists()
        with output_path.open() as f:
            data = json.load(f)
        assert isinstance(data, dict)

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_has_correct_schema_version(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that SARIF output has correct schema version.

        Given: An EnforcementResult
        When: export_sarif is called
        Then: Output has $schema pointing to SARIF 2.1.0
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        assert "$schema" in data
        assert "2.1.0" in data["$schema"]
        assert data["version"] == "2.1.0"

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_has_runs_array(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that SARIF output has runs array with single run.

        Given: An EnforcementResult
        When: export_sarif is called
        Then: Output has runs array with one run entry
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        assert "runs" in data
        assert isinstance(data["runs"], list)
        assert len(data["runs"]) == 1

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_has_tool_definition(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that SARIF output includes tool definition.

        Given: An EnforcementResult
        When: export_sarif is called
        Then: Run has tool.driver with floe information
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        run = data["runs"][0]
        assert "tool" in run
        assert "driver" in run["tool"]
        driver = run["tool"]["driver"]
        assert driver["name"] == "floe-policy-enforcer"
        assert "version" in driver
        assert "informationUri" in driver

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_includes_rule_definitions(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that SARIF includes rule definitions for error codes.

        Given: An EnforcementResult with multiple violation types
        When: export_sarif is called
        Then: tool.driver.rules contains definitions for each error code
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        rules = data["runs"][0]["tool"]["driver"]["rules"]
        rule_ids = {rule["id"] for rule in rules}

        # Should include rules for violations in result
        assert "FLOE-E201" in rule_ids
        assert "FLOE-E210" in rule_ids
        assert "FLOE-E301" in rule_ids

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_rule_has_required_fields(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that SARIF rules have required fields.

        Given: An EnforcementResult
        When: export_sarif is called
        Then: Each rule has id, name, shortDescription, helpUri
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        rules = data["runs"][0]["tool"]["driver"]["rules"]
        for rule in rules:
            assert "id" in rule
            assert "name" in rule
            assert "shortDescription" in rule
            assert "text" in rule["shortDescription"]
            assert "helpUri" in rule

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_maps_violations_to_results(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that violations are mapped to SARIF results.

        Given: An EnforcementResult with 3 violations
        When: export_sarif is called
        Then: run.results contains 3 result entries
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        results = data["runs"][0]["results"]
        assert len(results) == 3

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_result_has_required_fields(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that each SARIF result has required fields.

        Given: An EnforcementResult with violations
        When: export_sarif is called
        Then: Each result has ruleId, level, message, locations
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        results = data["runs"][0]["results"]
        for result in results:
            assert "ruleId" in result
            assert "level" in result
            assert "message" in result
            assert "text" in result["message"]
            assert "locations" in result

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_maps_severity_to_level(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that violation severity maps to SARIF level correctly.

        Given: Violations with error and warning severity
        When: export_sarif is called
        Then: error -> "error", warning -> "warning" in SARIF
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        results = data["runs"][0]["results"]
        levels_by_rule = {r["ruleId"]: r["level"] for r in results}

        # FLOE-E201 is error severity
        assert levels_by_rule["FLOE-E201"] == "error"
        # FLOE-E210 is warning severity
        assert levels_by_rule["FLOE-E210"] == "warning"

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_location_uses_model_path(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that location uses model path in artifact location.

        Given: A violation for model 'stg_customers'
        When: export_sarif is called
        Then: Location references the model as artifact
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        # Find the FLOE-E201 result (stg_customers model)
        result = next(r for r in data["runs"][0]["results"] if r["ruleId"] == "FLOE-E201")
        location = result["locations"][0]

        assert "physicalLocation" in location
        assert "artifactLocation" in location["physicalLocation"]
        artifact = location["physicalLocation"]["artifactLocation"]
        assert "uri" in artifact
        assert "stg_customers" in artifact["uri"]

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_handles_empty_violations(
        self,
        empty_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that SARIF handles empty violations case.

        Given: An EnforcementResult with no violations
        When: export_sarif is called
        Then: results is empty array, but structure is valid
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(empty_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        assert data["runs"][0]["results"] == []

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_creates_parent_directories(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export creates parent directories if needed.

        Given: An output path with non-existent parent directories
        When: export_sarif is called
        Then: Parent directories are created and file is written
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "reports" / "sarif" / "result.sarif"
        export_sarif(sample_enforcement_result, output_path)

        assert output_path.exists()

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_includes_invocation_info(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that SARIF includes invocation information.

        Given: An EnforcementResult
        When: export_sarif is called
        Then: Run has invocations array with execution info
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        export_sarif(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        run = data["runs"][0]
        assert "invocations" in run
        assert len(run["invocations"]) == 1

        invocation = run["invocations"][0]
        assert "executionSuccessful" in invocation
        # Failed because we have violations
        assert invocation["executionSuccessful"] is False

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_returns_path(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export_sarif returns the output path.

        Given: An EnforcementResult
        When: export_sarif is called
        Then: The function returns the output path
        """
        from floe_core.enforcement.exporters.sarif_exporter import export_sarif

        output_path = tmp_path / "enforcement.sarif"
        result = export_sarif(sample_enforcement_result, output_path)

        assert result == output_path
