"""Unit tests for HTML exporter (US5).

TDD tests for export_html() function. Tests verify:
- HTML contains violation summary section (FR-022)
- HTML contains inline statistics tables (no JavaScript)
- HTML contains detailed violation list
- HTML is valid and readable

Task: T053
Requirements: FR-022 (HTML export format)

TDD Pattern: These tests are written FIRST and should FAIL until
T058 implements the HTML exporter.
"""

from __future__ import annotations

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
    """Create sample violations for HTML testing."""
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
            downstream_impact=["dim_customers", "fct_orders"],
        ),
        Violation(
            error_code="FLOE-E220",
            severity="warning",
            policy_type="documentation",
            model_name="bronze_orders",
            message="Model 'bronze_orders' is missing description",
            expected="Model should have a description",
            actual="No description provided",
            suggestion="Add description to model schema",
            documentation_url="https://floe.dev/docs/enforcement/documentation",
        ),
    ]


@pytest.fixture
def sample_enforcement_result(sample_violations: list[Violation]) -> EnforcementResult:
    """Create a sample enforcement result for HTML testing."""
    return EnforcementResult(
        passed=False,
        violations=sample_violations,
        summary=EnforcementSummary(
            total_models=15,
            models_validated=15,
            naming_violations=1,
            coverage_violations=0,
            documentation_violations=1,
            semantic_violations=0,
            custom_rule_violations=0,
            overrides_applied=0,
            duration_ms=175.5,
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
# T053: Tests for HTML Export (FR-022)
# ==============================================================================


class TestHtmlExporter:
    """Tests for HTML export functionality.

    FR-022: HTML output MUST include violation summary, charts (inline),
    and detailed violation list.
    """

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_creates_valid_html_file(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export_html creates a valid HTML file.

        Given: An EnforcementResult with violations
        When: export_html is called
        Then: A valid HTML file is created
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content or "<html" in content

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_has_proper_structure(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML has proper structure with head and body.

        Given: An EnforcementResult
        When: export_html is called
        Then: Output has html, head, body elements
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        assert "<html" in content
        assert "<head>" in content
        assert "<body>" in content
        assert "</html>" in content

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_has_title(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML has appropriate title.

        Given: An EnforcementResult
        When: export_html is called
        Then: Page has title element with floe enforcement info
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        assert "<title>" in content
        assert "Enforcement" in content or "Policy" in content or "floe" in content.lower()

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_contains_summary_section(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML contains violation summary section.

        Given: An EnforcementResult
        When: export_html is called
        Then: HTML contains summary with pass/fail status
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should indicate failure status
        assert "Failed" in content or "FAILED" in content or "fail" in content.lower()

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_contains_statistics_table(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML contains statistics table.

        Given: An EnforcementResult with summary
        When: export_html is called
        Then: HTML contains table with violation counts
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should contain table elements
        assert "<table" in content
        # Should contain statistics
        assert "15" in content  # total_models
        assert "175" in content or "176" in content  # duration_ms (rounded)

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_contains_violation_details(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML contains detailed violation list.

        Given: An EnforcementResult with violations
        When: export_html is called
        Then: HTML contains each violation with details
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should contain violation error codes
        assert "FLOE-E201" in content
        assert "FLOE-E220" in content
        # Should contain model names
        assert "stg_customers" in content
        assert "bronze_orders" in content
        # Should contain messages
        assert "violates medallion naming convention" in content
        assert "missing description" in content

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_contains_suggestions(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML includes remediation suggestions.

        Given: An EnforcementResult with violations having suggestions
        When: export_html is called
        Then: HTML contains the suggestions
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        assert "Rename model to bronze_customers" in content
        assert "Add description to model schema" in content

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_no_javascript(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML has no JavaScript dependencies.

        Given: An EnforcementResult
        When: export_html is called
        Then: HTML has no <script> tags (inline CSS only)
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should have no script tags
        assert "<script" not in content.lower()

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_has_inline_styles(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML has inline CSS styles.

        Given: An EnforcementResult
        When: export_html is called
        Then: HTML has <style> block with CSS
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should have style block
        assert "<style>" in content or "style=" in content

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_shows_severity_with_visual_indicator(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that violations show severity with visual distinction.

        Given: An EnforcementResult with error and warning violations
        When: export_html is called
        Then: HTML distinguishes error vs warning visually
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should distinguish severity (error/warning text or CSS class)
        assert "error" in content.lower()
        assert "warning" in content.lower()

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_shows_downstream_impact(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML shows downstream impact for violations.

        Given: A violation with downstream_impact
        When: export_html is called
        Then: HTML shows affected downstream models
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should show downstream models
        assert "dim_customers" in content
        assert "fct_orders" in content

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_handles_empty_violations(
        self,
        empty_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML handles empty violations case.

        Given: An EnforcementResult with no violations
        When: export_html is called
        Then: HTML shows passing status
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(empty_enforcement_result, output_path)

        content = output_path.read_text()
        # Should indicate success
        assert "Passed" in content or "PASSED" in content or "pass" in content.lower() or "success" in content.lower()

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_includes_documentation_links(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML includes documentation links for violations.

        Given: Violations with documentation URLs
        When: export_html is called
        Then: HTML has clickable links to documentation
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should have links
        assert "<a " in content.lower() and "href" in content.lower()
        assert "https://floe.dev/docs/enforcement/" in content

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_creates_parent_directories(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export creates parent directories if needed.

        Given: An output path with non-existent parent directories
        When: export_html is called
        Then: Parent directories are created and file is written
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "reports" / "html" / "result.html"
        export_html(sample_enforcement_result, output_path)

        assert output_path.exists()

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_shows_timestamp(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that HTML shows the enforcement timestamp.

        Given: An EnforcementResult with timestamp
        When: export_html is called
        Then: HTML shows when enforcement was run
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        export_html(sample_enforcement_result, output_path)

        content = output_path.read_text()
        # Should show date
        assert "2026" in content or "Jan" in content or "January" in content

    @pytest.mark.requirement("003b-FR-022")
    def test_export_html_returns_path(
        self,
        sample_enforcement_result: EnforcementResult,
        tmp_path: Path,
    ) -> None:
        """Test that export_html returns the output path.

        Given: An EnforcementResult
        When: export_html is called
        Then: The function returns the output path
        """
        from floe_core.enforcement.exporters.html_exporter import export_html

        output_path = tmp_path / "enforcement.html"
        result = export_html(sample_enforcement_result, output_path)

        assert result == output_path
