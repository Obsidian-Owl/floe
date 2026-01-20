"""Integration tests for enforcement report export formats.

Tests the integration of report exporters (JSON, SARIF, HTML) with the
enforcement pipeline. These tests validate end-to-end export behavior including:
- Export to all supported formats (JSON, SARIF, HTML)
- File creation with proper content
- Round-trip verification (export then validate structure)
- Directory creation for nested output paths

Task: T066
Requirements: FR-020 (JSON), FR-021 (SARIF), FR-022 (HTML), FR-023 (Directory creation)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


class TestJsonExportIntegration:
    """Integration tests for JSON export format.

    Task: T066
    Requirement: FR-020 (JSON export)
    """

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_creates_valid_json_file(
        self,
        tmp_path: Path,
    ) -> None:
        """JSON export MUST create a valid JSON file with EnforcementResult schema.

        Validates that export_json:
        1. Creates a file at the specified path
        2. File contains valid JSON
        3. JSON matches EnforcementResult schema
        """
        from floe_core.enforcement.exporters import export_json
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        # Create enforcement result with violations
        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="bad_model",
                    message="Model name violates naming convention",
                    expected="^(bronze|silver|gold)_.*$",
                    actual="bad_model",
                    suggestion="Rename to bronze_bad_model",
                    documentation_url="https://floe.dev/docs/naming",
                ),
            ],
            summary=EnforcementSummary(
                total_models=10,
                models_validated=10,
                naming_violations=1,
            ),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        output_path = tmp_path / "enforcement.json"

        # Export to JSON
        export_json(result, output_path)

        # Verify file exists and contains valid JSON
        assert output_path.exists()
        content = json.loads(output_path.read_text())

        # Verify schema fields
        assert content["passed"] is False
        assert len(content["violations"]) == 1
        assert content["violations"][0]["error_code"] == "FLOE-E201"
        assert content["enforcement_level"] == "strict"
        assert content["manifest_version"] == "1.8.0"

    @pytest.mark.requirement("003b-FR-020")
    def test_export_json_roundtrip_validation(
        self,
        tmp_path: Path,
    ) -> None:
        """JSON export MUST produce output that can be re-parsed into EnforcementResult.

        Validates round-trip: EnforcementResult -> JSON -> EnforcementResult.
        """
        from floe_core.enforcement.exporters import export_json
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
        )

        original = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(
                total_models=50,
                models_validated=50,
            ),
            enforcement_level="warn",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        output_path = tmp_path / "roundtrip.json"
        export_json(original, output_path)

        # Parse back
        content = json.loads(output_path.read_text())
        restored = EnforcementResult(**content)

        assert restored.passed == original.passed
        assert restored.enforcement_level == original.enforcement_level
        assert restored.summary.total_models == original.summary.total_models


class TestSarifExportIntegration:
    """Integration tests for SARIF export format.

    Task: T066
    Requirement: FR-021 (SARIF export)
    """

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_creates_valid_sarif_file(
        self,
        tmp_path: Path,
    ) -> None:
        """SARIF export MUST create a valid SARIF 2.1.0 file.

        Validates that export_sarif:
        1. Creates a file at the specified path
        2. File contains valid SARIF JSON
        3. SARIF version is 2.1.0
        4. Contains tool and results sections
        """
        from floe_core.enforcement.exporters import export_sarif
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="bad_model",
                    message="Model name violates naming convention",
                    expected="^(bronze|silver|gold)_.*$",
                    actual="bad_model",
                    suggestion="Rename to bronze_bad_model",
                    documentation_url="https://floe.dev/docs/naming",
                ),
                Violation(
                    error_code="FLOE-E220",
                    severity="warning",
                    policy_type="documentation",
                    model_name="undocumented_model",
                    message="Model missing description",
                    expected="non-empty description",
                    actual="",
                    suggestion="Add description to model",
                    documentation_url="https://floe.dev/docs/documentation",
                ),
            ],
            summary=EnforcementSummary(
                total_models=10,
                models_validated=10,
                naming_violations=1,
                documentation_violations=1,
            ),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        output_path = tmp_path / "enforcement.sarif"

        # Export to SARIF
        export_sarif(result, output_path)

        # Verify file exists and contains valid SARIF
        assert output_path.exists()
        content = json.loads(output_path.read_text())

        # Verify SARIF 2.1.0 schema
        assert content["$schema"].endswith("sarif-schema-2.1.0.json")
        assert content["version"] == "2.1.0"
        assert len(content["runs"]) == 1

        run = content["runs"][0]
        assert run["tool"]["driver"]["name"] == "floe-policy-enforcer"
        assert len(run["results"]) == 2

        # Verify result severity mapping
        severities = {r["level"] for r in run["results"]}
        assert "error" in severities
        assert "warning" in severities

    @pytest.mark.requirement("003b-FR-021")
    def test_export_sarif_includes_rule_definitions(
        self,
        tmp_path: Path,
    ) -> None:
        """SARIF export MUST include rule definitions for FLOE error codes.

        Validates that SARIF output contains rules section with help URLs.
        """
        from floe_core.enforcement.exporters import export_sarif
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="bad_model",
                    message="Model name violates naming convention",
                    expected="pattern",
                    actual="bad_model",
                    suggestion="Fix it",
                    documentation_url="https://floe.dev/docs/naming",
                ),
            ],
            summary=EnforcementSummary(total_models=1, models_validated=1),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        output_path = tmp_path / "with-rules.sarif"
        export_sarif(result, output_path)

        content = json.loads(output_path.read_text())
        rules = content["runs"][0]["tool"]["driver"].get("rules", [])

        # Should have at least one rule definition
        assert len(rules) >= 1
        rule = rules[0]
        assert rule["id"] == "FLOE-E201"
        assert "helpUri" in rule


class TestHtmlExportIntegration:
    """Integration tests for HTML export format.

    Task: T066
    Requirement: FR-022 (HTML export)
    """

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_creates_valid_html_file(
        self,
        tmp_path: Path,
    ) -> None:
        """HTML export MUST create a valid HTML file with report content.

        Validates that export_html:
        1. Creates a file at the specified path
        2. File contains valid HTML structure
        3. Includes summary statistics
        4. Includes violation details
        """
        from floe_core.enforcement.exporters import export_html
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="bad_model",
                    message="Model name violates naming convention",
                    expected="^(bronze|silver|gold)_.*$",
                    actual="bad_model",
                    suggestion="Rename to bronze_bad_model",
                    documentation_url="https://floe.dev/docs/naming",
                ),
            ],
            summary=EnforcementSummary(
                total_models=10,
                models_validated=10,
                naming_violations=1,
            ),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        output_path = tmp_path / "enforcement.html"

        # Export to HTML
        export_html(result, output_path)

        # Verify file exists
        assert output_path.exists()
        content = output_path.read_text()

        # Verify HTML structure
        assert "<!DOCTYPE html>" in content or "<html" in content
        assert "</html>" in content

        # Verify report content
        assert "FLOE-E201" in content
        assert "bad_model" in content
        assert "naming" in content.lower()

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_shows_pass_status(
        self,
        tmp_path: Path,
    ) -> None:
        """HTML export MUST clearly show pass/fail status.

        Validates that HTML includes visible pass/fail indication.
        """
        from floe_core.enforcement.exporters import export_html
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
        )

        # Test passing result
        passing_result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=10, models_validated=10),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        pass_path = tmp_path / "passing.html"
        export_html(passing_result, pass_path)
        pass_content = pass_path.read_text().lower()

        # Should indicate success
        assert "pass" in pass_content or "success" in pass_content or "✓" in pass_content


class TestDirectoryCreation:
    """Integration tests for output directory creation.

    Task: T066
    Requirement: FR-023 (Directory creation)
    """

    @pytest.mark.requirement("003b-FR-023")
    def test_export_creates_nested_directories(
        self,
        tmp_path: Path,
    ) -> None:
        """Export functions MUST create nested directories if they don't exist.

        Validates that exporting to a deeply nested path creates all directories.
        """
        from floe_core.enforcement.exporters import ensure_output_dir, export_json
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
        )

        result = EnforcementResult(
            passed=True,
            violations=[],
            summary=EnforcementSummary(total_models=1, models_validated=1),
            enforcement_level="warn",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        # Deeply nested path that doesn't exist
        nested_path = tmp_path / "a" / "b" / "c" / "d" / "enforcement.json"

        # Use ensure_output_dir before export
        ensure_output_dir(nested_path)
        export_json(result, nested_path)

        # Verify file was created in nested directory
        assert nested_path.exists()
        assert nested_path.parent.exists()

    @pytest.mark.requirement("003b-FR-023")
    def test_ensure_output_dir_is_idempotent(
        self,
        tmp_path: Path,
    ) -> None:
        """ensure_output_dir MUST be idempotent (safe to call multiple times).

        Validates that calling ensure_output_dir multiple times doesn't fail.
        """
        from floe_core.enforcement.exporters import ensure_output_dir

        path = tmp_path / "reports" / "enforcement.json"

        # Call multiple times
        result1 = ensure_output_dir(path)
        result2 = ensure_output_dir(path)
        result3 = ensure_output_dir(path)

        # All should succeed and return the same parent
        assert result1 == result2 == result3
        assert result1.exists()


class TestAllFormatsEndToEnd:
    """End-to-end tests for all export formats together.

    Task: T066
    Requirement: FR-020, FR-021, FR-022
    """

    @pytest.mark.requirement("003b-FR-020")
    @pytest.mark.requirement("003b-FR-021")
    @pytest.mark.requirement("003b-FR-022")
    def test_export_all_formats_from_same_result(
        self,
        tmp_path: Path,
    ) -> None:
        """All export formats MUST work from the same EnforcementResult.

        Validates that JSON, SARIF, and HTML can all be exported from
        a single enforcement result without interference.
        """
        from floe_core.enforcement.exporters import (
            ensure_output_dir,
            export_html,
            export_json,
            export_sarif,
        )
        from floe_core.enforcement.result import (
            EnforcementResult,
            EnforcementSummary,
            Violation,
        )

        # Create a comprehensive result
        result = EnforcementResult(
            passed=False,
            violations=[
                Violation(
                    error_code="FLOE-E201",
                    severity="error",
                    policy_type="naming",
                    model_name="model_a",
                    message="Naming violation",
                    expected="pattern",
                    actual="model_a",
                    suggestion="Rename",
                    documentation_url="https://floe.dev/docs",
                ),
                Violation(
                    error_code="FLOE-E210",
                    severity="warning",
                    policy_type="coverage",
                    model_name="model_b",
                    message="Coverage violation",
                    expected="80%",
                    actual="50%",
                    suggestion="Add tests",
                    documentation_url="https://floe.dev/docs",
                ),
                Violation(
                    error_code="FLOE-E220",
                    severity="warning",
                    policy_type="documentation",
                    model_name="model_c",
                    message="Missing docs",
                    expected="description",
                    actual="empty",
                    suggestion="Add docs",
                    documentation_url="https://floe.dev/docs",
                ),
            ],
            summary=EnforcementSummary(
                total_models=100,
                models_validated=100,
                naming_violations=1,
                coverage_violations=1,
                documentation_violations=1,
            ),
            enforcement_level="strict",
            manifest_version="1.8.0",
            timestamp=datetime.now(timezone.utc),
        )

        # Export to all formats
        json_path = tmp_path / "reports" / "enforcement.json"
        sarif_path = tmp_path / "reports" / "enforcement.sarif"
        html_path = tmp_path / "reports" / "enforcement.html"

        ensure_output_dir(json_path)
        export_json(result, json_path)
        export_sarif(result, sarif_path)
        export_html(result, html_path)

        # Verify all files exist
        assert json_path.exists()
        assert sarif_path.exists()
        assert html_path.exists()

        # Verify JSON has 3 violations
        json_content = json.loads(json_path.read_text())
        assert len(json_content["violations"]) == 3

        # Verify SARIF has 3 results
        sarif_content = json.loads(sarif_path.read_text())
        assert len(sarif_content["runs"][0]["results"]) == 3

        # Verify HTML mentions all error codes
        html_content = html_path.read_text()
        assert "FLOE-E201" in html_content
        assert "FLOE-E210" in html_content
        assert "FLOE-E220" in html_content
