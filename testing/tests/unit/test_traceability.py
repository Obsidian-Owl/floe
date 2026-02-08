"""Unit tests for requirement traceability checker.

Tests for testing.traceability.checker module including RequirementCollector,
TraceabilityReport, and coverage calculation functions.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from testing.traceability.checker import (
    RequirementCollector,
    RequirementCoverage,
    TraceabilityReport,
    calculate_coverage,
    get_requirement_markers,
    load_spec_requirements,
)


class TestRequirementCoverage:
    """Tests for RequirementCoverage model."""

    @pytest.mark.requirement("9c-FR-018")
    def test_covered_with_tests(self) -> None:
        """Test covered returns True when tests exist."""
        coverage = RequirementCoverage(
            requirement_id="FR-001",
            tests=["test_foo", "test_bar"],
        )
        assert coverage.covered is True

    @pytest.mark.requirement("9c-FR-018")
    def test_not_covered_without_tests(self) -> None:
        """Test covered returns False when no tests."""
        coverage = RequirementCoverage(
            requirement_id="FR-001",
            tests=[],
        )
        assert coverage.covered is False

    @pytest.mark.requirement("9c-FR-018")
    def test_frozen_model(self) -> None:
        """Test RequirementCoverage is immutable."""
        coverage = RequirementCoverage(requirement_id="FR-001", tests=[])
        with pytest.raises(ValidationError):
            coverage.requirement_id = "FR-002"


class TestTraceabilityReport:
    """Tests for TraceabilityReport model."""

    @pytest.mark.requirement("9c-FR-018")
    def test_passes_threshold_at_100(self) -> None:
        """Test passes_threshold returns True at 100%."""
        report = TraceabilityReport(
            total_requirements=10,
            covered_requirements=10,
            coverage_percentage=100.0,
        )
        assert report.passes_threshold is True

    @pytest.mark.requirement("9c-FR-018")
    def test_fails_threshold_below_100(self) -> None:
        """Test passes_threshold returns False below 100%."""
        report = TraceabilityReport(
            total_requirements=10,
            covered_requirements=9,
            coverage_percentage=90.0,
        )
        assert report.passes_threshold is False

    @pytest.mark.requirement("9c-FR-018")
    def test_default_values(self) -> None:
        """Test TraceabilityReport has sensible defaults."""
        report = TraceabilityReport()  # type: ignore[call-arg]
        assert report.total_requirements == 0
        assert report.covered_requirements == 0
        assert report.coverage_percentage == pytest.approx(0.0)
        assert report.uncovered_requirements == []
        assert report.requirements == []
        assert report.tests_without_requirement == []


class TestRequirementCollector:
    """Tests for RequirementCollector dataclass."""

    @pytest.mark.requirement("9c-FR-018")
    def test_add_test_with_requirements(self) -> None:
        """Test adding a test with requirements."""
        collector = RequirementCollector()
        collector.add_test("test_foo", ["FR-001", "FR-002"])

        assert "FR-001" in collector.requirement_map
        assert "FR-002" in collector.requirement_map
        assert "test_foo" in collector.requirement_map["FR-001"]
        assert "test_foo" in collector.requirement_map["FR-002"]

    @pytest.mark.requirement("9c-FR-018")
    def test_add_test_without_requirements(self) -> None:
        """Test adding a test without requirements."""
        collector = RequirementCollector()
        collector.add_test("test_bar", [])

        assert "test_bar" in collector.tests_without_markers
        assert len(collector.requirement_map) == 0

    @pytest.mark.requirement("9c-FR-018")
    def test_multiple_tests_same_requirement(self) -> None:
        """Test multiple tests can cover same requirement."""
        collector = RequirementCollector()
        collector.add_test("test_foo", ["FR-001"])
        collector.add_test("test_bar", ["FR-001"])

        assert len(collector.requirement_map["FR-001"]) == 2
        assert "test_foo" in collector.requirement_map["FR-001"]
        assert "test_bar" in collector.requirement_map["FR-001"]


class TestGetRequirementMarkers:
    """Tests for get_requirement_markers function."""

    @pytest.mark.requirement("9c-FR-018")
    def test_extracts_single_marker(self) -> None:
        """Test extracting a single requirement marker."""
        item = MagicMock()
        marker = MagicMock()
        marker.args = ["FR-001"]
        item.iter_markers.return_value = [marker]

        result = get_requirement_markers(item)

        assert result == ["FR-001"]
        item.iter_markers.assert_called_once_with(name="requirement")

    @pytest.mark.requirement("9c-FR-018")
    def test_extracts_multiple_markers(self) -> None:
        """Test extracting multiple requirement markers."""
        item = MagicMock()
        marker1 = MagicMock()
        marker1.args = ["FR-001"]
        marker2 = MagicMock()
        marker2.args = ["FR-002"]
        item.iter_markers.return_value = [marker1, marker2]

        result = get_requirement_markers(item)

        assert result == ["FR-001", "FR-002"]

    @pytest.mark.requirement("9c-FR-018")
    def test_handles_no_markers(self) -> None:
        """Test handling items with no requirement markers."""
        item = MagicMock()
        item.iter_markers.return_value = []

        result = get_requirement_markers(item)

        assert result == []

    @pytest.mark.requirement("9c-FR-018")
    def test_handles_marker_with_multiple_args(self) -> None:
        """Test handling marker with multiple requirement args."""
        item = MagicMock()
        marker = MagicMock()
        marker.args = ["FR-001", "FR-002", "FR-003"]
        item.iter_markers.return_value = [marker]

        result = get_requirement_markers(item)

        assert result == ["FR-001", "FR-002", "FR-003"]


class TestCalculateCoverage:
    """Tests for calculate_coverage function."""

    @pytest.mark.requirement("9c-FR-018")
    def test_full_coverage(self) -> None:
        """Test calculating 100% coverage."""
        requirement_map = {
            "FR-001": ["test_a"],
            "FR-002": ["test_b"],
        }

        covered, total, percentage = calculate_coverage(requirement_map)

        assert covered == 2
        assert total == 2
        assert percentage == pytest.approx(100.0)

    @pytest.mark.requirement("9c-FR-018")
    def test_partial_coverage(self) -> None:
        """Test calculating partial coverage."""
        requirement_map = {
            "FR-001": ["test_a"],
            "FR-002": [],  # No tests
        }

        covered, total, percentage = calculate_coverage(requirement_map)

        assert covered == 1
        assert total == 2
        assert percentage == pytest.approx(50.0)

    @pytest.mark.requirement("9c-FR-018")
    def test_with_spec_requirements(self) -> None:
        """Test calculating coverage against spec requirements."""
        requirement_map = {
            "FR-001": ["test_a"],
        }
        spec_requirements = ["FR-001", "FR-002", "FR-003"]

        covered, total, percentage = calculate_coverage(
            requirement_map, spec_requirements
        )

        assert covered == 1
        assert total == 3
        assert percentage == pytest.approx(33.333, rel=0.01)

    @pytest.mark.requirement("9c-FR-018")
    def test_empty_requirements(self) -> None:
        """Test calculating coverage with no requirements."""
        requirement_map: dict[str, list[str]] = {}

        covered, total, percentage = calculate_coverage(requirement_map)

        assert covered == 0
        assert total == 0
        assert percentage == pytest.approx(0.0)


class TestLoadSpecRequirements:
    """Tests for load_spec_requirements function."""

    @pytest.mark.requirement("9c-FR-018")
    def test_loads_requirements_from_spec(self, tmp_path: Path) -> None:
        """Test loading requirements from spec file."""
        spec_content = """
        ## Functional Requirements

        - FR-001: First requirement
        - FR-002: Second requirement
        - NFR-001: Non-functional requirement
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(spec_content)

        result = load_spec_requirements(spec_file)

        assert "FR-001" in result
        assert "FR-002" in result
        assert "NFR-001" in result

    @pytest.mark.requirement("9c-FR-018")
    def test_loads_prefixed_requirements(self, tmp_path: Path) -> None:
        """Test loading prefixed requirements like 9c-FR-001."""
        spec_content = """
        - 9c-FR-001: Test requirement
        - 9c-FR-002: Another requirement
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(spec_content)

        result = load_spec_requirements(spec_file)

        assert "9c-FR-001" in result
        assert "9c-FR-002" in result

    @pytest.mark.requirement("9c-FR-018")
    def test_deduplicates_requirements(self, tmp_path: Path) -> None:
        """Test that duplicate requirements are removed."""
        spec_content = """
        - FR-001: First mention
        - FR-001: Second mention
        - FR-001: Third mention
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(spec_content)

        result = load_spec_requirements(spec_file)

        assert result.count("FR-001") == 1

    @pytest.mark.requirement("9c-FR-018")
    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        """Test returns empty list for missing file."""
        missing_file = tmp_path / "nonexistent.md"

        result = load_spec_requirements(missing_file)

        assert result == []

    @pytest.mark.requirement("9c-FR-018")
    def test_preserves_order(self, tmp_path: Path) -> None:
        """Test that requirement order is preserved."""
        spec_content = """
        - FR-003: Third
        - FR-001: First
        - FR-002: Second
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(spec_content)

        result = load_spec_requirements(spec_file)

        assert result == ["FR-003", "FR-001", "FR-002"]
