"""Verification tests for required_services call-site migration.

These tests enforce that the codebase has been fully migrated from
tuple-format ``required_services`` declarations (e.g. ``[("polaris", 8181)]``)
to string-format (e.g. ``["polaris"]``), and that ``check_infrastructure``
calls no longer pass hardcoded port numbers.

The tests use ``subprocess.run`` with ``grep`` to scan the source tree.
Files that intentionally test backward compatibility are excluded from
the scan.
"""

from __future__ import annotations

import subprocess

import pytest

# Files that legitimately contain tuple-format for backward-compat testing.
_EXCLUDED_FILES: frozenset[str] = frozenset(
    {
        "test_port_resolution.py",
        "test_migration_verification.py",
    }
)


def _filter_matches(raw_output: str) -> list[str]:
    """Remove lines matching excluded filenames from grep output.

    Args:
        raw_output: Raw stdout from a grep invocation, possibly empty.

    Returns:
        List of non-excluded match lines, stripped of trailing whitespace.
    """
    if not raw_output.strip():
        return []
    lines: list[str] = []
    for line in raw_output.strip().splitlines():
        if any(excluded in line for excluded in _EXCLUDED_FILES):
            continue
        lines.append(line.rstrip())
    return lines


class TestMigrationVerification:
    """Verify that the tuple-to-string migration is complete across the repo."""

    @pytest.mark.requirement("env-resilient-AC-1")
    def test_no_tuple_format_required_services(self) -> None:
        """Assert zero tuple-format required_services declarations remain.

        Scans testing/, packages/, plugins/, and tests/ for lines like
        ``required_services = [("service", port)]`` — the old format.
        Backward-compat test files are excluded.
        """
        result = subprocess.run(
            [
                "grep",
                "-rn",
                r'required_services.*=.*\[.*("',
                "--include=*.py",
                "testing/",
                "packages/",
                "plugins/",
                "tests/",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        matches = _filter_matches(result.stdout)
        assert matches == [], (
            f"Found {len(matches)} tuple-format required_services declaration(s) "
            f"that must be migrated to string-format:\n" + "\n".join(f"  {m}" for m in matches)
        )

    @pytest.mark.requirement("env-resilient-AC-2")
    def test_no_hardcoded_port_check_infrastructure(self) -> None:
        """Assert zero hardcoded-port check_infrastructure calls remain.

        Scans for patterns like ``self.check_infrastructure("svc", 8181)``
        where the second argument is a numeric literal.  After migration,
        all call sites should use ``self.check_infrastructure("svc")``
        and let port resolution handle the port lookup.
        """
        result = subprocess.run(
            [
                "grep",
                "-rn",
                r'self\.check_infrastructure(".*",\s*[0-9]',
                "--include=*.py",
                "tests/",
                "packages/",
                "plugins/",
                "testing/",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        matches = _filter_matches(result.stdout)
        assert matches == [], (
            f"Found {len(matches)} hardcoded-port check_infrastructure call(s) "
            f"that must be migrated to string-only format:\n" + "\n".join(f"  {m}" for m in matches)
        )

    @pytest.mark.requirement("env-resilient-AC-9")
    def test_docstring_examples_use_string_format(self) -> None:
        """Assert docstring examples in testing modules use string-format.

        The four key modules whose docstrings serve as usage examples
        must show the new string-format ``required_services = ["polaris"]``
        rather than the deprecated tuple-format.
        """
        target_files = [
            "testing/__init__.py",
            "testing/base_classes/__init__.py",
            "testing/base_classes/integration_test_base.py",
            "testing/base_classes/adapter_test_base.py",
        ]
        result = subprocess.run(
            [
                "grep",
                "-n",
                r'required_services.*=.*\[.*("',
                *target_files,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        matches = _filter_matches(result.stdout)
        assert matches == [], (
            f"Found {len(matches)} tuple-format docstring example(s) in testing "
            f"modules that must be updated to string-format:\n"
            + "\n".join(f"  {m}" for m in matches)
        )
