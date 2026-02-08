"""CLI interface for requirement traceability checker.

Usage:
    python -m testing.traceability --all
    python -m testing.traceability --all --threshold 100
    python -m testing.traceability --report --spec specs/9c-testing-infra/spec.md
    python -m testing.traceability --json > coverage.json

Exit codes:
    0: Coverage meets threshold
    1: Coverage below threshold
    2: Error during execution
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Command line arguments (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="python -m testing.traceability",
        description="Check requirement traceability for tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check all tests for requirement markers
    python -m testing.traceability --all

    # Require 100% coverage
    python -m testing.traceability --all --threshold 100

    # Generate JSON report
    python -m testing.traceability --all --json > coverage.json

    # Check against spec requirements
    python -m testing.traceability --all --spec specs/9c-testing-infra/spec.md
        """,
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all tests in the project",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        metavar="PCT",
        help="Minimum coverage percentage required (default: 0)",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        metavar="PATH",
        help="Path to spec.md to load requirements from",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate detailed report",
    )
    parser.add_argument(
        "--test-path",
        type=Path,
        default=Path("tests"),
        metavar="PATH",
        help="Path to tests directory (default: tests)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args(args)


def run_pytest_collect(test_path: Path) -> dict[str, list[str]]:
    """Run pytest --collect-only to gather test information.

    Args:
        test_path: Path to tests directory.

    Returns:
        Dictionary mapping requirement IDs to test node IDs.
    """
    # Use pytest's collection to get test items
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(test_path),
            "--collect-only",
            "-q",
            "--no-header",
        ],
        capture_output=True,
        text=True,
    )

    # Parse output to get test node IDs
    test_ids: list[str] = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line and "::" in line and not line.startswith(("=", "-", " ")):
            test_ids.append(line)

    return {"_collected_tests": test_ids}


def collect_with_markers(test_path: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Collect tests with their requirement markers.

    Uses pytest's collection mechanism to extract requirement markers
    from all tests.

    Args:
        test_path: Path to tests directory.

    Returns:
        Tuple of (requirement_map, tests_without_markers).
    """
    # Import pytest here to avoid import errors when pytest not installed
    import pytest

    # Custom plugin to collect markers
    class MarkerCollector:
        def __init__(self) -> None:
            self.requirement_map: dict[str, list[str]] = {}
            self.tests_without_markers: list[str] = []

        def pytest_collection_finish(self, session: pytest.Session) -> None:
            from testing.traceability.checker import (
                collect_requirements,
                collect_tests_without_markers,
            )

            self.requirement_map = collect_requirements(session)
            self.tests_without_markers = collect_tests_without_markers(session)

    collector = MarkerCollector()

    # Run pytest in collection-only mode with our plugin
    pytest.main(
        [str(test_path), "--collect-only", "-q"],
        plugins=[collector],
    )

    return collector.requirement_map, collector.tests_without_markers


def load_spec_requirements(spec_path: Path | None) -> list[str] | None:
    """Load requirements from spec file if provided.

    Args:
        spec_path: Path to spec.md file.

    Returns:
        List of requirement IDs or None if not provided.
    """
    if spec_path is None:
        return None

    from testing.traceability.checker import load_spec_requirements as load_reqs

    return load_reqs(spec_path)


def format_report(
    requirement_map: dict[str, list[str]],
    tests_without_markers: list[str],
    spec_requirements: list[str] | None,
    threshold: float,
    verbose: bool = False,
) -> tuple[str, bool]:
    """Format the traceability report.

    Args:
        requirement_map: Mapping of requirement ID to test node IDs.
        tests_without_markers: Tests missing requirement markers.
        spec_requirements: Optional list of requirements from spec.
        threshold: Minimum coverage percentage required.
        verbose: Include detailed output.

    Returns:
        Tuple of (report_string, passes_threshold).
    """
    lines: list[str] = []

    # Calculate coverage
    all_requirements = spec_requirements or list(requirement_map.keys())
    total = len(all_requirements)
    covered = sum(1 for req in all_requirements if req in requirement_map)
    percentage = (covered / total * 100) if total > 0 else 0.0

    # Header
    lines.append("=" * 60)
    lines.append("REQUIREMENT TRACEABILITY REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    lines.append(f"Requirements Found: {total}")
    lines.append(f"Requirements Covered: {covered}")
    lines.append(f"Coverage: {percentage:.1f}%")
    lines.append(f"Threshold: {threshold:.1f}%")
    lines.append("")

    # Uncovered requirements
    uncovered = [req for req in all_requirements if req not in requirement_map]
    if uncovered:
        lines.append("UNCOVERED REQUIREMENTS:")
        for req in sorted(uncovered):
            lines.append(f"  - {req}")
        lines.append("")

    # Tests without markers
    if tests_without_markers:
        lines.append(
            f"TESTS WITHOUT REQUIREMENT MARKERS ({len(tests_without_markers)}):"
        )
        if verbose:
            for test in sorted(tests_without_markers):
                lines.append(f"  - {test}")
        else:
            lines.append(f"  (use -v to see all {len(tests_without_markers)} tests)")
        lines.append("")

    # Verbose: show covered requirements
    if verbose and requirement_map:
        lines.append("COVERED REQUIREMENTS:")
        for req_id in sorted(requirement_map.keys()):
            tests = requirement_map[req_id]
            lines.append(f"  {req_id}: {len(tests)} test(s)")
            for test in tests[:3]:  # Show first 3
                lines.append(f"    - {test}")
            if len(tests) > 3:
                lines.append(f"    ... and {len(tests) - 3} more")
        lines.append("")

    # Result
    passes = percentage >= threshold
    if passes:
        lines.append(f"RESULT: PASS (coverage {percentage:.1f}% >= {threshold:.1f}%)")
    else:
        lines.append(f"RESULT: FAIL (coverage {percentage:.1f}% < {threshold:.1f}%)")

    lines.append("=" * 60)

    return "\n".join(lines), passes


def format_json(
    requirement_map: dict[str, list[str]],
    tests_without_markers: list[str],
    spec_requirements: list[str] | None,
    threshold: float,
) -> str:
    """Format report as JSON.

    Args:
        requirement_map: Mapping of requirement ID to test node IDs.
        tests_without_markers: Tests missing requirement markers.
        spec_requirements: Optional list of requirements from spec.
        threshold: Minimum coverage percentage required.

    Returns:
        JSON string.
    """
    all_requirements = spec_requirements or list(requirement_map.keys())
    total = len(all_requirements)
    covered = sum(1 for req in all_requirements if req in requirement_map)
    percentage = (covered / total * 100) if total > 0 else 0.0
    uncovered = [req for req in all_requirements if req not in requirement_map]

    report = {
        "total_requirements": total,
        "covered_requirements": covered,
        "coverage_percentage": round(percentage, 2),
        "threshold": threshold,
        "passes": percentage >= threshold,
        "uncovered_requirements": uncovered,
        "tests_without_markers_count": len(tests_without_markers),
        "requirements": {
            req_id: requirement_map.get(req_id, []) for req_id in all_requirements
        },
    }

    return json.dumps(report, indent=2)


def main(args: list[str] | None = None) -> int:
    """Main entry point for traceability CLI.

    Args:
        args: Command line arguments.

    Returns:
        Exit code (0 = pass, 1 = fail, 2 = error).
    """
    parsed = parse_args(args)

    if not parsed.all and not parsed.report:
        print("Error: Must specify --all or --report", file=sys.stderr)
        return 2

    try:
        # Collect tests with markers
        requirement_map, tests_without = collect_with_markers(parsed.test_path)

        # Load spec requirements if provided
        spec_requirements = load_spec_requirements(parsed.spec)

        # Generate output
        if parsed.json:
            output = format_json(
                requirement_map,
                tests_without,
                spec_requirements,
                parsed.threshold,
            )
            print(output)
            # Still need to calculate pass/fail
            all_reqs = spec_requirements or list(requirement_map.keys())
            total = len(all_reqs)
            covered = sum(1 for req in all_reqs if req in requirement_map)
            percentage = (covered / total * 100) if total > 0 else 0.0
            passes = percentage >= parsed.threshold
        else:
            output, passes = format_report(
                requirement_map,
                tests_without,
                spec_requirements,
                parsed.threshold,
                parsed.verbose,
            )
            print(output)

        return 0 if passes else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if parsed.verbose:
            import traceback

            traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
