"""Unit tests for JSON exporter (US5).

TDD tests for export_json() function. Tests verify:
- Output matches EnforcementResult JSON schema (FR-020)
- All violations serialized correctly
- Metadata fields populated
- Empty violations case handled

Task: T051
Requirements: FR-020 (JSON export format)

TDD Pattern: These tests are written FIRST and should FAIL until
T054 implements the JSON exporter.
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
def sample_violation() -> Violation:
    """Create a sample violation for testing."""
    return Violation(
        error_code="FLOE-E201",
        severity="error",
        policy_type="naming",
        model_name="stg_customers",
        message="Model 'stg_customers' violates medallion naming convention",
        expected="Pattern: bronze_*, silver_*, gold_*",
        actual="stg_customers",
        suggestion="Rename model to bronze_customers or silver_customers",
        documentation_url="https://floe.dev/docs/enforcement/naming",
        downstream_impact=["dim_customers", "fct_orders"],
    )


@pytest.fixture
def sample_enforcement_result(sample_violation: Violation) -> EnforcementResult:
    """Create a sample enforcement result with violations."""
    return EnforcementResult(
        passed=False,
        violations=[sample_violation],
        summary=EnforcementSummary(
            total_models=10,
            models_validated=10,
            naming_violations=1,
            coverage_violations=0,
            documentation_violations=0,
            semantic_violations=0,
            custom_rule_violations=0,
            overrides_applied=0,
            duration_ms=150.5,
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
            naming_violations=0,
            coverage_violations=0,
            documentation_violations=0,
            semantic_violations=0,
            custom_rule_violations=0,
            overrides_applied=0,
            duration_ms=50.0,
        ),
        enforcement_level="strict",
        manifest_version="1.8.0",
        timestamp=datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
    )


# ==============================================================================
# T051: Tests for JSON Export (FR-020)
# ==============================================================================


class TestJsonExporter:
    """Tests for JSON export functionality.

    FR-020: System MUST support `--output-format=json` with output
    matching EnforcementResult JSON schema.
    """

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_creates_valid_json_file(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export_json creates a valid JSON file.

        Given: An EnforcementResult with violations
        When: export_json is called
        Then: A valid JSON file is created at the specified path
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "enforcement.json"
        export_json(sample_enforcement_result, output_path)

        assert output_path.exists()
        # Should be valid JSON
        with output_path.open() as f:
            data = json.load(f)
        assert isinstance(data, dict)

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_matches_enforcement_result_schema(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that JSON output matches EnforcementResult schema.

        Given: An EnforcementResult
        When: export_json is called
        Then: Output has all required fields from EnforcementResult
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "enforcement.json"
        export_json(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        # Verify top-level fields
        assert "passed" in data
        assert data["passed"] is False
        assert "violations" in data
        assert "summary" in data
        assert "enforcement_level" in data
        assert data["enforcement_level"] == "strict"
        assert "manifest_version" in data
        assert data["manifest_version"] == "1.8.0"
        assert "timestamp" in data

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_serializes_violations_correctly(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that violations are serialized with all fields.

        Given: An EnforcementResult with violations
        When: export_json is called
        Then: Each violation has all required fields
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "enforcement.json"
        export_json(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        violations = data["violations"]
        assert len(violations) == 1

        violation = violations[0]
        assert violation["error_code"] == "FLOE-E201"
        assert violation["severity"] == "error"
        assert violation["policy_type"] == "naming"
        assert violation["model_name"] == "stg_customers"
        assert violation["message"] == "Model 'stg_customers' violates medallion naming convention"
        assert violation["expected"] == "Pattern: bronze_*, silver_*, gold_*"
        assert violation["actual"] == "stg_customers"
        assert violation["suggestion"] == "Rename model to bronze_customers or silver_customers"
        assert violation["documentation_url"] == "https://floe.dev/docs/enforcement/naming"
        assert violation["downstream_impact"] == ["dim_customers", "fct_orders"]

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_serializes_summary_correctly(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that summary statistics are serialized correctly.

        Given: An EnforcementResult with summary
        When: export_json is called
        Then: Summary has all statistics fields
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "enforcement.json"
        export_json(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        summary = data["summary"]
        assert summary["total_models"] == 10
        assert summary["models_validated"] == 10
        assert summary["naming_violations"] == 1
        assert summary["coverage_violations"] == 0
        assert summary["documentation_violations"] == 0
        assert summary["semantic_violations"] == 0
        assert summary["custom_rule_violations"] == 0
        assert summary["overrides_applied"] == 0
        assert summary["duration_ms"] == pytest.approx(150.5)

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_handles_empty_violations(
        self,
        empty_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export handles empty violations case.

        Given: An EnforcementResult with no violations
        When: export_json is called
        Then: violations is an empty list, passed is True
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "enforcement.json"
        export_json(empty_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        assert data["passed"] is True
        assert data["violations"] == []

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_creates_parent_directories(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export creates parent directories if needed.

        Given: An output path with non-existent parent directories
        When: export_json is called
        Then: Parent directories are created and file is written
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "reports" / "enforcement" / "result.json"
        export_json(sample_enforcement_result, output_path)

        assert output_path.exists()
        assert output_path.parent.is_dir()

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_uses_pretty_formatting(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that JSON output is pretty-formatted for readability.

        Given: An EnforcementResult
        When: export_json is called
        Then: Output is indented (not minified)
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "enforcement.json"
        export_json(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Pretty formatted JSON has newlines and indentation
        assert "\n" in content
        assert "  " in content  # Indentation present

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_handles_datetime_serialization(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that datetime fields are serialized as ISO-8601.

        Given: An EnforcementResult with timestamp
        When: export_json is called
        Then: timestamp is serialized as ISO-8601 string
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "enforcement.json"
        export_json(sample_enforcement_result, output_path)

        with output_path.open() as f:
            data = json.load(f)

        # Timestamp should be ISO-8601 string
        timestamp = data["timestamp"]
        assert isinstance(timestamp, str)
        # Should be parseable back to datetime
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed.year == 2026
        assert parsed.month == 1
        assert parsed.day == 20

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_returns_path(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export_json returns the output path.

        Given: An EnforcementResult
        When: export_json is called
        Then: The function returns the output path
        """
        from floe_core.enforcement.exporters.json_exporter import export_json

        output_path = tmp_path / "enforcement.json"
        result = export_json(sample_enforcement_result, output_path)

        assert result == output_path
