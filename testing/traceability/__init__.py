"""Requirement traceability for test coverage analysis.

This module provides tools to link tests to requirements and verify that all
requirements have associated tests. It enforces the @pytest.mark.requirement()
marker on all integration tests.

Components:
    checker: Pytest collection hook for gathering requirement markers
    TraceabilityReport: Pydantic model for coverage reports

Usage:
    # Mark tests with requirements
    @pytest.mark.requirement("9c-FR-001")
    def test_create_catalog() -> None:
        ...

    # Run traceability check
    python -m testing.traceability --all --threshold 100

CLI:
    python -m testing.traceability --all          # Check all tests
    python -m testing.traceability --report       # Generate report
    python -m testing.traceability --threshold 80 # Set coverage threshold
"""

from __future__ import annotations

# Phase 5 exports - Traceability checker
from testing.traceability.checker import (
    RequirementCollector,
    RequirementCoverage,
    TraceabilityReport,
    calculate_coverage,
    collect_requirements,
    collect_tests_without_markers,
    generate_report,
    get_requirement_markers,
    load_spec_requirements,
)

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
