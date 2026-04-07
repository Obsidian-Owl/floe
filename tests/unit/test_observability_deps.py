"""Structural tests: pytest-html and pytest-json-report in workspace deps.

Validates that the workspace ``pyproject.toml`` includes ``pytest-html`` and
``pytest-json-report`` as dependencies so that the test runner Dockerfile
(which runs ``uv sync --frozen``) installs them automatically.

These are source-parsing tests: they read the actual TOML file and assert
on the dependency list.  They run in <1s with no infrastructure.

Requirements Covered:
    - AC-1: pytest-html and pytest-json-report are workspace dependencies
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKSPACE_TOML = _REPO_ROOT / "pyproject.toml"

# Package names we expect in the dependency list (case-insensitive per PEP 503)
_PYTEST_HTML = "pytest-html"
_PYTEST_JSON_REPORT = "pytest-json-report"

# Pattern to match a single dependency entry like:
#   "pytest-html>=4.0",
# Captures the package name (before any version specifier or extras bracket).
_DEP_NAME_RE = re.compile(r'"([a-zA-Z0-9](?:[a-zA-Z0-9._-]*[a-zA-Z0-9])?)')


def _extract_deps_block(toml_content: str) -> str:
    """Extract the top-level dependencies array content from pyproject.toml.

    Handles nested brackets (e.g. ``bandit[toml]``) by tracking bracket depth
    rather than using a naive ``[^\\]]*`` pattern.

    Args:
        toml_content: Raw content of ``pyproject.toml``.

    Returns:
        The text between the opening ``[`` and closing ``]`` of the
        ``dependencies = [...]`` block.

    Raises:
        ValueError: If the dependencies block cannot be found.
    """
    marker = re.search(r"^dependencies\s*=\s*\[", toml_content, re.MULTILINE)
    if marker is None:
        msg = "Could not find 'dependencies = [' in pyproject.toml"
        raise ValueError(msg)

    start = marker.end()  # position right after the opening [
    depth = 1
    pos = start
    while pos < len(toml_content) and depth > 0:
        ch = toml_content[pos]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        pos += 1

    if depth != 0:
        msg = "Unclosed 'dependencies = [' bracket in pyproject.toml"
        raise ValueError(msg)

    return toml_content[start : pos - 1]


def _parse_dependency_names(toml_content: str) -> list[str]:
    """Extract normalised dependency names from the [project] dependencies array.

    PEP 503 normalisation: lowercase, replace [-_.] with ``-``.

    Args:
        toml_content: Raw content of ``pyproject.toml``.

    Returns:
        Sorted list of normalised dependency names found in the array.

    Raises:
        ValueError: If the dependencies block cannot be found.
    """
    deps_block = _extract_deps_block(toml_content)
    names: list[str] = []
    for dep_match in _DEP_NAME_RE.finditer(deps_block):
        raw_name = dep_match.group(1)
        # PEP 503 normalisation
        normalised = re.sub(r"[-_.]+", "-", raw_name).lower()
        names.append(normalised)

    return sorted(set(names))


# ===================================================================
# 1. pytest-html is a workspace dependency
# ===================================================================


class TestPytestHtmlDependency:
    """Verify pytest-html is listed in workspace pyproject.toml dependencies."""

    @pytest.mark.requirement("AC-1")
    def test_pytest_html_in_dependencies(self) -> None:
        """pyproject.toml dependencies array MUST include pytest-html.

        Without this dependency, the test runner Dockerfile will not
        have pytest-html available after ``uv sync --frozen``, and
        HTML report generation will fail.
        """
        content = _WORKSPACE_TOML.read_text()
        dep_names = _parse_dependency_names(content)

        assert _PYTEST_HTML in dep_names, (
            f"'{_PYTEST_HTML}' is not listed in the workspace "
            f"pyproject.toml dependencies. Add it to the dependencies "
            f"array in {_WORKSPACE_TOML.relative_to(_REPO_ROOT)}. "
            f"Current deps: {dep_names}"
        )

    @pytest.mark.requirement("AC-1")
    def test_pytest_html_has_version_constraint(self) -> None:
        """pytest-html dependency MUST have a minimum version constraint.

        A bare ``pytest-html`` without a version pin is fragile.
        We require at least ``>=X.Y`` to prevent installation of
        ancient incompatible versions.
        """
        content = _WORKSPACE_TOML.read_text()
        # Look for pytest-html with a version specifier (>=, ==, ~=, etc.)
        version_pattern = re.compile(r'"pytest-html\s*[><=!~]', re.IGNORECASE)
        assert version_pattern.search(content), (
            "pytest-html dependency must have a version constraint "
            "(e.g., 'pytest-html>=4.0'). A bare package name without "
            "version pin is not acceptable."
        )


# ===================================================================
# 2. pytest-json-report is a workspace dependency
# ===================================================================


class TestPytestJsonReportDependency:
    """Verify pytest-json-report is listed in workspace pyproject.toml dependencies."""

    @pytest.mark.requirement("AC-1")
    def test_pytest_json_report_in_dependencies(self) -> None:
        """pyproject.toml dependencies array MUST include pytest-json-report.

        Without this dependency, the test runner Dockerfile will not
        have pytest-json-report available after ``uv sync --frozen``,
        and JSON report generation will fail.
        """
        content = _WORKSPACE_TOML.read_text()
        dep_names = _parse_dependency_names(content)

        assert _PYTEST_JSON_REPORT in dep_names, (
            f"'{_PYTEST_JSON_REPORT}' is not listed in the workspace "
            f"pyproject.toml dependencies. Add it to the dependencies "
            f"array in {_WORKSPACE_TOML.relative_to(_REPO_ROOT)}. "
            f"Current deps: {dep_names}"
        )

    @pytest.mark.requirement("AC-1")
    def test_pytest_json_report_has_version_constraint(self) -> None:
        """pytest-json-report dependency MUST have a minimum version constraint.

        A bare ``pytest-json-report`` without a version pin is fragile.
        """
        content = _WORKSPACE_TOML.read_text()
        version_pattern = re.compile(r'"pytest-json-report\s*[><=!~]', re.IGNORECASE)
        assert version_pattern.search(content), (
            "pytest-json-report dependency must have a version constraint "
            "(e.g., 'pytest-json-report>=1.5'). A bare package name without "
            "version pin is not acceptable."
        )


# ===================================================================
# 3. Dependencies are in the correct section
# ===================================================================


class TestDependencyPlacement:
    """Verify deps are in main dependencies, not optional-dependencies."""

    @pytest.mark.requirement("AC-1")
    def test_pytest_html_not_only_in_optional(self) -> None:
        """pytest-html MUST be in [project].dependencies, not only in optional.

        If it were only in [project.optional-dependencies], the Dockerfile's
        ``uv sync --frozen`` (without --extra) would NOT install it.
        """
        content = _WORKSPACE_TOML.read_text()
        dep_names = _parse_dependency_names(content)

        assert _PYTEST_HTML in dep_names, (
            f"'{_PYTEST_HTML}' must be in [project].dependencies "
            f"(not only in [project.optional-dependencies]) so that "
            f"'uv sync --frozen' installs it in the Dockerfile."
        )

    @pytest.mark.requirement("AC-1")
    def test_pytest_json_report_not_only_in_optional(self) -> None:
        """pytest-json-report MUST be in [project].dependencies, not only in optional.

        Same rationale as pytest-html: ``uv sync --frozen`` only
        installs main dependencies by default.
        """
        content = _WORKSPACE_TOML.read_text()
        dep_names = _parse_dependency_names(content)

        assert _PYTEST_JSON_REPORT in dep_names, (
            f"'{_PYTEST_JSON_REPORT}' must be in [project].dependencies "
            f"(not only in [project.optional-dependencies]) so that "
            f"'uv sync --frozen' installs it in the Dockerfile."
        )


# ===================================================================
# 4. Both deps present simultaneously (not one-or-the-other)
# ===================================================================


class TestBothDepsPresent:
    """Verify BOTH reporting dependencies are present, not just one."""

    @pytest.mark.requirement("AC-1")
    def test_both_reporting_deps_present(self) -> None:
        """Both pytest-html AND pytest-json-report MUST be present.

        A partial implementation that adds only one of the two is
        insufficient. AC-1 requires both.
        """
        content = _WORKSPACE_TOML.read_text()
        dep_names = _parse_dependency_names(content)

        missing: list[str] = []
        for pkg in [_PYTEST_HTML, _PYTEST_JSON_REPORT]:
            if pkg not in dep_names:
                missing.append(pkg)

        assert missing == [], (
            f"Both pytest-html and pytest-json-report must be in "
            f"workspace dependencies. Missing: {missing}"
        )
