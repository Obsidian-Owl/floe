"""Requirement traceability checker using pytest collection.

This module provides tools to collect @pytest.mark.requirement() markers
from tests and generate coverage reports against specification requirements.

Functions:
    collect_requirements: Gather requirement markers from pytest session
    calculate_coverage: Compute requirement coverage percentage
    generate_report: Create TraceabilityReport from collected data

Example:
    # Run traceability check
    python -m testing.traceability --all --threshold 100

    # In pytest conftest.py
    from testing.traceability.checker import collect_requirements

    def pytest_collection_finish(session):
        requirements = collect_requirements(session)
        print(f"Found {len(requirements)} requirements")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import pytest


class RequirementCoverage(BaseModel):
    """Coverage information for a single requirement.

    Attributes:
        requirement_id: The requirement identifier (e.g., "9c-FR-001").
        tests: List of test node IDs that cover this requirement.
        covered: Whether the requirement has at least one test.
    """

    model_config = ConfigDict(frozen=True)

    requirement_id: str = Field(..., description="Requirement identifier")
    tests: list[str] = Field(default_factory=list, description="Test node IDs")

    @property
    def covered(self) -> bool:
        """Check if requirement has at least one test."""
        return len(self.tests) > 0


class TraceabilityReport(BaseModel):
    """Complete traceability report for a test suite.

    Attributes:
        total_requirements: Total number of requirements found in spec.
        covered_requirements: Number of requirements with tests.
        uncovered_requirements: List of requirement IDs without tests.
        coverage_percentage: Percentage of requirements covered.
        requirements: Detailed coverage for each requirement.
        tests_without_requirement: Tests missing requirement markers.
    """

    model_config = ConfigDict(frozen=True)

    total_requirements: int = Field(0, ge=0)
    covered_requirements: int = Field(0, ge=0)
    uncovered_requirements: list[str] = Field(default_factory=list)
    coverage_percentage: float = Field(0.0, ge=0.0, le=100.0)
    requirements: list[RequirementCoverage] = Field(default_factory=list)
    tests_without_requirement: list[str] = Field(default_factory=list)

    @property
    def passes_threshold(self) -> bool:
        """Check if coverage meets 100% threshold."""
        return self.coverage_percentage >= 100.0


@dataclass
class RequirementCollector:
    """Collects requirement markers from pytest items.

    Attributes:
        requirement_map: Mapping of requirement ID to test node IDs.
        tests_without_markers: Tests that lack requirement markers.
    """

    requirement_map: dict[str, list[str]] = field(default_factory=dict)
    tests_without_markers: list[str] = field(default_factory=list)

    def add_test(self, test_id: str, requirements: list[str]) -> None:
        """Add a test and its requirements to the collection.

        Args:
            test_id: The pytest node ID (e.g., "tests/test_foo.py::test_bar").
            requirements: List of requirement IDs from markers.
        """
        if not requirements:
            self.tests_without_markers.append(test_id)
            return

        for req_id in requirements:
            if req_id not in self.requirement_map:
                self.requirement_map[req_id] = []
            self.requirement_map[req_id].append(test_id)


def collect_requirements(session: pytest.Session) -> dict[str, list[str]]:
    """Collect requirement markers from pytest session.

    Iterates through all collected test items and extracts requirement
    markers, building a mapping of requirement IDs to test node IDs.

    Args:
        session: The pytest session after collection.

    Returns:
        Dictionary mapping requirement IDs to lists of test node IDs.

    Example:
        def pytest_collection_finish(session):
            reqs = collect_requirements(session)
            for req_id, tests in reqs.items():
                print(f"{req_id}: {len(tests)} tests")
    """
    collector = RequirementCollector()

    for item in session.items:
        requirements = get_requirement_markers(item)
        collector.add_test(item.nodeid, requirements)

    return collector.requirement_map


def get_requirement_markers(item: pytest.Item) -> list[str]:
    """Extract requirement IDs from a pytest item's markers.

    Args:
        item: A pytest test item.

    Returns:
        List of requirement IDs from @pytest.mark.requirement() markers.
    """
    requirements: list[str] = []

    for marker in item.iter_markers(name="requirement"):
        if marker.args:
            requirements.extend(marker.args)

    return requirements


def collect_tests_without_markers(session: pytest.Session) -> list[str]:
    """Find tests that lack requirement markers.

    Args:
        session: The pytest session after collection.

    Returns:
        List of test node IDs missing requirement markers.
    """
    missing: list[str] = []

    for item in session.items:
        requirements = get_requirement_markers(item)
        if not requirements:
            missing.append(item.nodeid)

    return missing


def calculate_coverage(
    requirement_map: dict[str, list[str]],
    all_requirements: list[str] | None = None,
) -> tuple[int, int, float]:
    """Calculate requirement coverage statistics.

    Args:
        requirement_map: Mapping of requirement ID to test node IDs.
        all_requirements: Optional list of all requirements in spec.
            If provided, uncovered requirements are included in count.

    Returns:
        Tuple of (covered_count, total_count, percentage).
    """
    if all_requirements:
        total = len(all_requirements)
        covered = sum(1 for req in all_requirements if req in requirement_map)
    else:
        total = len(requirement_map)
        covered = sum(1 for tests in requirement_map.values() if tests)

    percentage = (covered / total * 100) if total > 0 else 0.0
    return covered, total, percentage


def generate_report(
    session: pytest.Session,
    spec_requirements: list[str] | None = None,
) -> TraceabilityReport:
    """Generate a complete traceability report.

    Args:
        session: The pytest session after collection.
        spec_requirements: Optional list of all requirements from spec.

    Returns:
        TraceabilityReport with coverage details.
    """
    requirement_map = collect_requirements(session)
    tests_without = collect_tests_without_markers(session)

    # Use spec requirements if provided, otherwise use collected
    all_requirements = spec_requirements or list(requirement_map.keys())

    covered, total, percentage = calculate_coverage(requirement_map, all_requirements)

    # Find uncovered requirements
    uncovered = [req for req in all_requirements if req not in requirement_map]

    # Build requirement coverage list
    coverage_list = [
        RequirementCoverage(
            requirement_id=req_id,
            tests=requirement_map.get(req_id, []),
        )
        for req_id in all_requirements
    ]

    return TraceabilityReport(
        total_requirements=total,
        covered_requirements=covered,
        uncovered_requirements=uncovered,
        coverage_percentage=percentage,
        requirements=coverage_list,
        tests_without_requirement=tests_without,
    )


def load_spec_requirements(spec_path: Path) -> list[str]:
    """Load requirement IDs from a spec.md file.

    Parses the spec file looking for requirement patterns like:
    - FR-001, FR-002, etc.
    - NFR-001, NFR-002, etc.
    - 9c-FR-001, etc.

    Args:
        spec_path: Path to the spec.md file.

    Returns:
        List of requirement IDs found in the spec.
    """
    import re

    if not spec_path.exists():
        return []

    content = spec_path.read_text()

    # Pattern matches: FR-001, NFR-001, 9c-FR-001, etc.
    pattern = r"\b(?:\d+[a-z]?-)?(?:FR|NFR)-\d{3}\b"
    matches = re.findall(pattern, content)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique.append(match)

    return unique


# Module exports
__all__ = [
    "RequirementCollector",
    "RequirementCoverage",
    "TraceabilityReport",
    "calculate_coverage",
    "collect_requirements",
    "collect_tests_without_markers",
    "generate_report",
    "get_requirement_markers",
    "load_spec_requirements",
]
