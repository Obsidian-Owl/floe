"""Contract test: no hardcoded credentials in executable Python code.

Scans all Python files in test and testing directories for hardcoded
credential patterns (minioadmin, demo-secret, demo-admin) and fails
if any are found in executable code (not comments, not docstrings,
not the credentials module itself).

Requirements:
    AC-6: Contract test enforces no hardcoded credentials in executable code
    AC-1: All credentials derive from manifest.yaml or environment variables
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
"""Absolute path to the repository root."""

CREDENTIAL_PATTERNS: frozenset[str] = frozenset(
    {
        "minioadmin",
        "demo-secret",
        "demo-admin",
    }
)
"""Hardcoded credential values that MUST NOT appear in executable code."""

SCAN_DIRECTORIES: tuple[str, ...] = (
    "tests",
    "testing",
    "plugins",
    "packages",
)
"""Top-level directories to scan for Python files."""

EXCLUDED_FILES: frozenset[str] = frozenset(
    {
        # The credentials module itself (single source of truth)
        "testing/fixtures/credentials.py",
        # Tests that validate the credentials module output
        "testing/tests/unit/test_credentials.py",
        "testing/tests/unit/test_minio_fixture.py",
        # CI script tests that reference values as test expectations
        "testing/ci/tests/test_extract_manifest_config.py",
        "testing/ci/tests/test_e2e_sh_manifest_wiring.py",
        # E2E wiring / structural tests
        "tests/e2e/tests/test_conftest_manifest_wiring.py",
        "tests/e2e/test_dbt_e2e_profile.py",
        "tests/e2e/test_governance_enforcement_e2e.py",
        "tests/e2e/test_platform_bootstrap.py",
        # This test file itself (contains patterns as string literals)
        "tests/contract/test_no_hardcoded_credentials.py",
        # Integration conftest files with credentials in module docstrings
        "plugins/floe-orchestrator-dagster/tests/integration/conftest.py",
        "packages/floe-iceberg/tests/integration/conftest.py",
    }
)
"""Files excluded from scanning (credentials module, test expectations)."""

PRAGMA_ALLOWLIST = "pragma: allowlist secret"
"""Bandit suppression pragma that exempts a line from scanning."""


# ---------------------------------------------------------------------------
# Scanner helpers
# ---------------------------------------------------------------------------


def _is_comment_line(line: str) -> bool:
    """Return True if the line is a comment (ignoring leading whitespace).

    Args:
        line: A single line of source code.

    Returns:
        True when the stripped line starts with ``#``.
    """
    stripped = line.strip()
    return stripped.startswith("#")


def _relative_to_repo(path: Path) -> str:
    """Return the path relative to the repo root as a POSIX string.

    For paths outside the repo (e.g., tmp_path in tests), returns
    the absolute POSIX path so that exclusion checks simply fail
    to match (correctly treating the file as non-excluded).

    Args:
        path: Absolute path to a file.

    Returns:
        POSIX-style relative path string, or absolute if outside repo.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _collect_python_files() -> list[Path]:
    """Collect all Python files under the scan directories.

    Returns:
        Sorted list of absolute ``Path`` objects for ``.py`` files.
    """
    files: list[Path] = []
    for directory in SCAN_DIRECTORIES:
        scan_root = REPO_ROOT / directory
        if not scan_root.is_dir():
            continue
        files.extend(sorted(scan_root.rglob("*.py")))
    return files


def _should_skip_file(path: Path) -> bool:
    """Return True if the file is in the exclusion list.

    Args:
        path: Absolute path to a Python file.

    Returns:
        True if the file is excluded from credential scanning.
    """
    rel = _relative_to_repo(path)
    return rel in EXCLUDED_FILES


Violation = tuple[str, int, str, str]
"""(relative_path, line_number, line_content, matched_pattern)."""


def scan_file_for_credentials(path: Path) -> list[Violation]:
    """Scan a single Python file for hardcoded credential patterns.

    Skips comment-only lines and lines containing the bandit pragma
    ``pragma: allowlist secret``.

    Args:
        path: Absolute path to the Python file.

    Returns:
        List of violations found in the file.
    """
    violations: list[Violation] = []
    rel = _relative_to_repo(path)

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return violations

    for line_no, line in enumerate(lines, start=1):
        # Skip comment-only lines
        if _is_comment_line(line):
            continue

        # Skip lines with bandit pragma
        if PRAGMA_ALLOWLIST in line:
            continue

        # Check for each credential pattern (case-sensitive)
        line_lower = line.lower()
        for pattern in CREDENTIAL_PATTERNS:
            if pattern in line_lower:
                violations.append((rel, line_no, line.strip(), pattern))

    return violations


def scan_all_files() -> list[Violation]:
    """Scan all Python files for hardcoded credential patterns.

    Returns:
        List of all violations across all scanned files.
    """
    all_violations: list[Violation] = []
    for path in _collect_python_files():
        if _should_skip_file(path):
            continue
        all_violations.extend(scan_file_for_credentials(path))
    return all_violations


def _format_violations(violations: list[Violation]) -> str:
    """Format violations into a human-readable report.

    Args:
        violations: List of violation tuples.

    Returns:
        Multi-line string report of all violations.
    """
    lines = [
        "",
        f"Found {len(violations)} hardcoded credential(s) in executable code:",
        "=" * 72,
    ]
    for rel_path, line_no, content, pattern in violations:
        lines.append(f"  {rel_path}:{line_no}")
        lines.append(f"    Pattern: {pattern!r}")
        lines.append(f"    Line:    {content}")
        lines.append("")
    lines.append(
        "Fix: Import credentials from testing.fixtures.credentials instead of hardcoding values."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestNoHardcodedCredentials:
    """Contract tests ensuring no hardcoded credentials in test code.

    These tests enforce that all credential values flow from the centralized
    credentials module (testing/fixtures/credentials.py), manifest.yaml,
    or environment variables -- never from hardcoded literals in test files.
    """

    @pytest.mark.requirement("AC-6")
    def test_no_hardcoded_credentials_in_executable_code(self) -> None:
        """Scan all Python test files for hardcoded credential patterns.

        Walks Python files in tests/, testing/, plugins/*/tests/, and
        packages/*/tests/. Fails if any hardcoded credential values are
        found in executable code (comments and the credentials module
        are excluded).
        """
        violations = scan_all_files()

        assert violations == [], _format_violations(violations)

    @pytest.mark.requirement("AC-6")
    def test_scanner_finds_files_to_scan(self) -> None:
        """Verify the scanner finds a non-trivial number of Python files.

        Guards against a degenerate scanner that vacuously passes by
        scanning zero files.
        """
        files = _collect_python_files()
        assert len(files) > 50, (
            f"Scanner only found {len(files)} Python files -- expected "
            f"many more. Check SCAN_DIRECTORIES: {SCAN_DIRECTORIES}"
        )

    @pytest.mark.requirement("AC-6")
    def test_excluded_files_exist(self) -> None:
        """Verify all excluded files actually exist on disk.

        If an excluded file is deleted or renamed, the exclusion is stale
        and must be updated -- otherwise a new file with the same name
        could silently bypass scanning.
        """
        for rel_path in sorted(EXCLUDED_FILES):
            full_path = REPO_ROOT / rel_path
            assert full_path.exists(), (
                f"Excluded file does not exist: {rel_path}\n"
                f"Remove it from EXCLUDED_FILES or update the path."
            )


class TestScannerDetection:
    """Regression tests verifying the scanner catches known bad patterns.

    These tests create temporary Python files with hardcoded credentials
    and verify the scanner logic correctly identifies them. This tests
    the test itself -- ensuring it is not vacuously passing.
    """

    @pytest.mark.requirement("AC-6")
    def test_scanner_catches_minioadmin(self, tmp_path: Path) -> None:
        """Verify scanner detects 'minioadmin' in executable code."""
        bad_file = tmp_path / "bad_test.py"
        bad_file.write_text(
            textwrap.dedent("""\
                access_key = "minioadmin"
                secret_key = "minioadmin"
            """),
            encoding="utf-8",
        )
        # Use the file scanner directly (bypasses repo-relative exclusion)
        violations = scan_file_for_credentials(bad_file)
        assert len(violations) == 2, f"Expected 2 violations for minioadmin, got {len(violations)}"
        matched_patterns = {v[3] for v in violations}
        assert matched_patterns == {"minioadmin"}

    @pytest.mark.requirement("AC-6")
    def test_scanner_catches_demo_secret(self, tmp_path: Path) -> None:
        """Verify scanner detects 'demo-secret' in executable code."""
        bad_file = tmp_path / "bad_test.py"
        bad_file.write_text(
            'client_secret = "demo-secret"\n',
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(bad_file)
        assert len(violations) == 1
        assert violations[0][3] == "demo-secret"

    @pytest.mark.requirement("AC-6")
    def test_scanner_catches_demo_admin(self, tmp_path: Path) -> None:
        """Verify scanner detects 'demo-admin' in executable code."""
        bad_file = tmp_path / "bad_test.py"
        bad_file.write_text(
            'client_id = "demo-admin"\n',
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(bad_file)
        assert len(violations) == 1
        assert violations[0][3] == "demo-admin"

    @pytest.mark.requirement("AC-6")
    def test_scanner_ignores_comment_lines(self, tmp_path: Path) -> None:
        """Verify scanner does NOT flag credentials in comments."""
        safe_file = tmp_path / "safe_test.py"
        safe_file.write_text(
            textwrap.dedent("""\
                # default credential is minioadmin
                #   demo-secret is used for Polaris
                    # demo-admin is the client ID
                x = 1  # unrelated code
            """),
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(safe_file)
        assert violations == [], f"Comments should not be flagged, but got: {violations}"

    @pytest.mark.requirement("AC-6")
    def test_scanner_ignores_pragma_allowlist(self, tmp_path: Path) -> None:
        """Verify scanner skips lines with 'pragma: allowlist secret'."""
        safe_file = tmp_path / "safe_test.py"
        safe_file.write_text(
            'password = "minioadmin"  # pragma: allowlist secret\n',
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(safe_file)
        assert violations == [], f"Pragma-annotated lines should be skipped, but got: {violations}"

    @pytest.mark.requirement("AC-6")
    def test_scanner_catches_credential_in_fstring(self, tmp_path: Path) -> None:
        """Verify scanner detects credentials inside f-strings."""
        bad_file = tmp_path / "bad_test.py"
        bad_file.write_text(
            'url = f"s3://minioadmin:minioadmin@localhost:9000"\n',
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(bad_file)
        # minioadmin appears twice in the f-string line
        assert len(violations) == 1, (
            "Each pattern should be reported once per line, not per occurrence"
        )
        assert violations[0][3] == "minioadmin"

    @pytest.mark.requirement("AC-6")
    def test_scanner_catches_credential_in_dict_literal(self, tmp_path: Path) -> None:
        """Verify scanner detects credentials in dict literals."""
        bad_file = tmp_path / "bad_test.py"
        bad_file.write_text(
            textwrap.dedent("""\
                config = {
                    "access_key": "minioadmin",
                    "secret_key": "minioadmin",
                    "client_id": "demo-admin",
                    "client_secret": "demo-secret",
                }
            """),
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(bad_file)
        assert len(violations) == 4, (
            f"Expected 4 violations (one per credential line), got {len(violations)}: {violations}"
        )
        matched_patterns = {v[3] for v in violations}
        assert matched_patterns == {"minioadmin", "demo-admin", "demo-secret"}

    @pytest.mark.requirement("AC-6")
    def test_scanner_catches_case_insensitive(self, tmp_path: Path) -> None:
        """Verify scanner catches credentials regardless of casing."""
        bad_file = tmp_path / "bad_test.py"
        bad_file.write_text(
            textwrap.dedent("""\
                key1 = "MINIOADMIN"
                key2 = "MiniOAdmin"
                key3 = "Demo-Secret"
                key4 = "DEMO-ADMIN"
            """),
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(bad_file)
        assert len(violations) == 4, f"Expected 4 case-insensitive matches, got {len(violations)}"

    @pytest.mark.requirement("AC-6")
    def test_scanner_does_not_flag_inline_comment_at_end(self, tmp_path: Path) -> None:
        """Verify scanner flags credential even if comment follows on same line.

        A line like ``x = "minioadmin"  # some comment`` is executable code
        that happens to have a trailing comment. The credential is in the
        executable part, so it MUST be flagged.
        """
        bad_file = tmp_path / "bad_test.py"
        bad_file.write_text(
            'x = "minioadmin"  # some comment\n',
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(bad_file)
        assert len(violations) == 1, (
            "Credential on executable line with trailing comment must be flagged"
        )

    @pytest.mark.requirement("AC-6")
    def test_scanner_reports_correct_line_numbers(self, tmp_path: Path) -> None:
        """Verify scanner reports accurate line numbers for violations."""
        bad_file = tmp_path / "bad_test.py"
        bad_file.write_text(
            textwrap.dedent("""\
                import os
                x = 1
                y = 2
                password = "minioadmin"
                z = 3
            """),
            encoding="utf-8",
        )
        violations = scan_file_for_credentials(bad_file)
        assert len(violations) == 1
        _, line_no, _, _ = violations[0]
        assert line_no == 4, f"Expected violation on line 4, got line {line_no}"

    @pytest.mark.requirement("AC-6")
    def test_scanner_handles_empty_file(self, tmp_path: Path) -> None:
        """Verify scanner handles empty files without error."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("", encoding="utf-8")
        violations = scan_file_for_credentials(empty_file)
        assert violations == []

    @pytest.mark.requirement("AC-6")
    def test_scanner_handles_binary_characters(self, tmp_path: Path) -> None:
        """Verify scanner gracefully handles files with decode errors."""
        binary_file = tmp_path / "binary.py"
        binary_file.write_bytes(b"\x80\x81\x82minioadmin\xff\xfe")
        # Should not raise -- returns empty or catches UnicodeDecodeError
        violations = scan_file_for_credentials(binary_file)
        # We don't assert on content since behavior depends on encoding
        # The key contract is: no crash
        assert isinstance(violations, list)

    @pytest.mark.requirement("AC-6")
    def test_excluded_file_is_not_scanned(self) -> None:
        """Verify _should_skip_file correctly identifies excluded paths."""
        for rel_path in EXCLUDED_FILES:
            full_path = REPO_ROOT / rel_path
            assert _should_skip_file(full_path), f"Expected {rel_path} to be skipped but it was not"

    @pytest.mark.requirement("AC-6")
    def test_non_excluded_file_is_scanned(self) -> None:
        """Verify _should_skip_file does NOT skip arbitrary files."""
        arbitrary = REPO_ROOT / "tests" / "contract" / "test_compilation.py"
        assert not _should_skip_file(arbitrary), "Non-excluded files must not be skipped"
