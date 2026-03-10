"""Tests for AC-2: OTel TracerProvider recursion eliminated.

Validates that ``reset_telemetry()`` (and all test fixtures) set
``trace._TRACER_PROVIDER = None`` instead of ``ProxyTracerProvider()``.

The bug: ``ProxyTracerProvider.get_tracer()`` reads ``_TRACER_PROVIDER``
to find the "real" provider.  When ``_TRACER_PROVIDER`` IS a
``ProxyTracerProvider``, it recurses infinitely, raising ``RecursionError``.

Two test categories:

**Structural** (source-parsing, per P28/P29):
    Inspect source files to verify the fix was applied at all 6 locations
    that previously used ``ProxyTracerProvider()`` and that no such
    assignment to ``_TRACER_PROVIDER`` exists anywhere in the codebase.
    (The 7th reset site, ``test_e2e_fixture_wiring.py`` teardown, uses
    ``SdkTracerProvider()`` — not buggy, covered by codebase-wide scan.)

**Behavioral**:
    After calling the production ``reset_telemetry()``, verify
    ``trace.get_tracer()`` does NOT raise ``RecursionError``.

Requirements Covered:
    AC-2: OTel TracerProvider recursion eliminated

See Also:
    - packages/floe-core/src/floe_core/telemetry/initialization.py
    - benchmarks/conftest.py
    - tests/unit/test_e2e_fixture_wiring.py
    - packages/floe-core/tests/unit/test_telemetry_initialization.py
    - packages/floe-core/tests/unit/test_telemetry/conftest.py
    - packages/floe-core/tests/unit/test_reset_telemetry.py
"""

from __future__ import annotations

import re
from collections.abc import Generator
from pathlib import Path

import pytest
from opentelemetry import trace

from testing.fixtures.source_parsing import strip_comments_and_docstrings

REPO_ROOT = Path(__file__).resolve().parents[2]

# The 6 files that previously assigned ProxyTracerProvider() to _TRACER_PROVIDER.
# The 7th reset site (test_e2e_fixture_wiring.py teardown) uses SdkTracerProvider()
# and was never buggy — it's covered by the codebase-wide scan in
# TestNoProxyAssignmentCodebaseWide.
AFFECTED_FILES: list[Path] = [
    REPO_ROOT / "packages" / "floe-core" / "src" / "floe_core" / "telemetry" / "initialization.py",
    REPO_ROOT / "benchmarks" / "conftest.py",
    REPO_ROOT / "tests" / "unit" / "test_e2e_fixture_wiring.py",
    REPO_ROOT / "packages" / "floe-core" / "tests" / "unit" / "test_telemetry_initialization.py",
    REPO_ROOT / "packages" / "floe-core" / "tests" / "unit" / "test_telemetry" / "conftest.py",
    REPO_ROOT / "packages" / "floe-core" / "tests" / "unit" / "test_reset_telemetry.py",
]

# The production file -- the one that needs an inline comment explaining the rationale.
PRODUCTION_FILE = (
    REPO_ROOT / "packages" / "floe-core" / "src" / "floe_core" / "telemetry" / "initialization.py"
)

# Regex that matches the buggy pattern in executable code:
#   trace._TRACER_PROVIDER = ProxyTracerProvider()
# Allows whitespace variations.
PROXY_ASSIGNMENT_PATTERN = re.compile(
    r"trace\._TRACER_PROVIDER\s*=\s*ProxyTracerProvider\s*\(\s*\)"
)

# Regex that matches the fixed pattern:
#   trace._TRACER_PROVIDER = None
NONE_ASSIGNMENT_PATTERN = re.compile(r"trace\._TRACER_PROVIDER\s*=\s*None")

# Directories to scan for the codebase-wide check.
SCAN_DIRS: list[str] = ["packages", "benchmarks", "tests"]


# ---------------------------------------------------------------------------
# Structural tests: No ProxyTracerProvider() assignment in any of the 6 files
# ---------------------------------------------------------------------------


class TestNoProxyAssignmentInAffectedFiles:
    """Verify none of the 6 affected files assign ProxyTracerProvider() to _TRACER_PROVIDER."""

    @pytest.mark.requirement("AC-2")
    @pytest.mark.parametrize(
        "file_path",
        AFFECTED_FILES,
        ids=[str(p.relative_to(REPO_ROOT)) for p in AFFECTED_FILES],
    )
    def test_file_has_no_proxy_assignment(self, file_path: Path) -> None:
        """Each affected file must NOT assign ProxyTracerProvider() to _TRACER_PROVIDER.

        Uses comment-stripped code (P29) so that a comment mentioning
        ProxyTracerProvider() does not cause a false positive.
        """
        assert file_path.exists(), f"File not found: {file_path}"
        raw_source = file_path.read_text()
        code = strip_comments_and_docstrings(raw_source)

        matches = PROXY_ASSIGNMENT_PATTERN.findall(code)
        assert len(matches) == 0, (
            f"Found {len(matches)} occurrence(s) of "
            f"'trace._TRACER_PROVIDER = ProxyTracerProvider()' in "
            f"executable code of {file_path.relative_to(REPO_ROOT)}. "
            f"Must use 'trace._TRACER_PROVIDER = None' instead to avoid "
            f"infinite recursion in ProxyTracerProvider.get_tracer()."
        )


# ---------------------------------------------------------------------------
# Structural test: No ProxyTracerProvider() assignment ANYWHERE in codebase
# ---------------------------------------------------------------------------


class TestNoProxyAssignmentCodebaseWide:
    """Verify no file in packages/, benchmarks/, tests/ assigns ProxyTracerProvider()."""

    @pytest.mark.requirement("AC-2")
    def test_grep_returns_zero_matches(self) -> None:
        """Scan all .py files under packages/, benchmarks/, tests/ for the buggy pattern.

        The acceptance criterion states:
            grep -rn "_TRACER_PROVIDER = ProxyTracerProvider()" packages/ benchmarks/ tests/
        must return zero matches.

        This test implements that check using Python (not subprocess) so it
        works without shell access, and strips comments/docstrings (P29).
        """
        violations: list[str] = []
        # Exclude this test file itself -- the pattern string appears in
        # assertion error messages and is not a real violation.
        self_path = Path(__file__).resolve()

        for scan_dir_name in SCAN_DIRS:
            scan_dir = REPO_ROOT / scan_dir_name
            if not scan_dir.exists():
                continue

            for py_file in scan_dir.rglob("*.py"):
                if py_file.resolve() == self_path:
                    continue
                raw_source = py_file.read_text()
                code = strip_comments_and_docstrings(raw_source)

                for match in PROXY_ASSIGNMENT_PATTERN.finditer(code):
                    # Find approximate line number in original source for reporting.
                    # Count newlines in code up to match start.
                    line_num = code[: match.start()].count("\n") + 1
                    violations.append(
                        f"  {py_file.relative_to(REPO_ROOT)}:~{line_num}: {match.group(0)}"
                    )

        assert len(violations) == 0, (
            f"Found {len(violations)} file(s) with "
            f"'trace._TRACER_PROVIDER = ProxyTracerProvider()' in executable code:\n"
            + "\n".join(violations)
            + "\n\nAll must use 'trace._TRACER_PROVIDER = None' to avoid "
            "infinite recursion."
        )


# ---------------------------------------------------------------------------
# Structural test: All 6 locations use = None
# ---------------------------------------------------------------------------


class TestAllLocationsUseNone:
    """Verify each affected file that touches _TRACER_PROVIDER sets it to None."""

    @pytest.mark.requirement("AC-2")
    @pytest.mark.parametrize(
        "file_path",
        AFFECTED_FILES,
        ids=[str(p.relative_to(REPO_ROOT)) for p in AFFECTED_FILES],
    )
    def test_file_uses_none_assignment(self, file_path: Path) -> None:
        """Each affected file must assign None to trace._TRACER_PROVIDER.

        The fix replaces ProxyTracerProvider() with None. This test
        confirms the replacement was actually made, not just that the old
        pattern was removed (which could happen by deleting the line entirely
        without adding the None assignment).

        Uses comment-stripped code to avoid false positives from comments.
        """
        assert file_path.exists(), f"File not found: {file_path}"
        raw_source = file_path.read_text()
        code = strip_comments_and_docstrings(raw_source)

        matches = NONE_ASSIGNMENT_PATTERN.findall(code)
        assert len(matches) > 0, (
            f"No 'trace._TRACER_PROVIDER = None' found in executable code of "
            f"{file_path.relative_to(REPO_ROOT)}. "
            f"The fix must replace 'ProxyTracerProvider()' with 'None', "
            f"not remove the assignment entirely."
        )


# ---------------------------------------------------------------------------
# Structural test: Production file has inline comment explaining rationale
# ---------------------------------------------------------------------------


class TestProductionSiteHasRationaleComment:
    """Verify the production reset_telemetry() site explains WHY None, not ProxyTracerProvider."""

    @pytest.mark.requirement("AC-2")
    def test_initialization_py_has_inline_rationale_comment(self) -> None:
        """The production site must have an inline comment explaining the None choice.

        AC-2 requires: 'The production site (initialization.py:175) has an
        inline comment explaining the rationale (why None, not
        ProxyTracerProvider)'.

        The comment must appear near the _TRACER_PROVIDER = None assignment.
        We check for the comment in the raw source (NOT comment-stripped)
        within a window around the assignment line.
        """
        assert PRODUCTION_FILE.exists(), f"Production file not found: {PRODUCTION_FILE}"
        raw_source = PRODUCTION_FILE.read_text()
        lines = raw_source.splitlines()

        # Find the line(s) with _TRACER_PROVIDER = None
        assignment_line_indices: list[int] = []
        for i, line in enumerate(lines):
            if NONE_ASSIGNMENT_PATTERN.search(line):
                assignment_line_indices.append(i)

        assert len(assignment_line_indices) > 0, (
            "No 'trace._TRACER_PROVIDER = None' found in "
            f"{PRODUCTION_FILE.relative_to(REPO_ROOT)}. "
            "Cannot verify inline comment without the assignment."
        )

        # Look for a comment within 5 lines before or on the assignment line
        # that explains the rationale (mentions recursion, ProxyTracerProvider,
        # or explains why None is used).
        rationale_keywords = [
            "recursion",
            "recursi",  # catches "recursive"
            "ProxyTracerProvider",
            "infinite loop",
            "infinite",
        ]

        for idx in assignment_line_indices:
            # Check a window: 5 lines before through the assignment line itself
            window_start = max(0, idx - 5)
            window_end = min(len(lines), idx + 2)
            window_text = "\n".join(lines[window_start:window_end])

            has_rationale = any(
                keyword.lower() in window_text.lower() for keyword in rationale_keywords
            )

            if has_rationale:
                return  # Found at least one valid rationale comment

        # None of the assignment sites had a rationale comment
        pytest.fail(
            f"The 'trace._TRACER_PROVIDER = None' assignment in "
            f"{PRODUCTION_FILE.relative_to(REPO_ROOT)} "
            f"does not have a nearby comment explaining the rationale. "
            f"AC-2 requires an inline comment explaining why None is used "
            f"instead of ProxyTracerProvider() (to avoid infinite recursion). "
            f"Expected one of these keywords near the assignment: "
            f"{rationale_keywords}"
        )


# ---------------------------------------------------------------------------
# Behavioral test: No RecursionError after reset_telemetry()
# ---------------------------------------------------------------------------


class TestNoRecursionAfterReset:
    """Verify that trace.get_tracer() does not recurse after reset_telemetry()."""

    @pytest.fixture(autouse=True)
    def _restore_otel_state(self) -> Generator[None, None, None]:
        """Capture and restore OTel global state around each behavioral test.

        Behavioral tests modify trace._TRACER_PROVIDER and _SET_ONCE — this
        fixture ensures no pollution leaks to subsequent tests.

        Yields:
            None after capturing state.
        """
        original_done = getattr(getattr(trace, "_TRACER_PROVIDER_SET_ONCE", None), "_done", None)
        original_provider = getattr(trace, "_TRACER_PROVIDER", None)
        yield
        if hasattr(trace, "_TRACER_PROVIDER_SET_ONCE") and original_done is not None:
            trace._TRACER_PROVIDER_SET_ONCE._done = original_done
        if hasattr(trace, "_TRACER_PROVIDER"):
            trace._TRACER_PROVIDER = original_provider

    @pytest.mark.requirement("AC-2")
    def test_get_tracer_after_reset_does_not_raise_recursion_error(self) -> None:
        """After reset_telemetry(), trace.get_tracer() must NOT raise RecursionError.

        This is the core behavioral test for AC-2. The bug:
        1. reset_telemetry() sets trace._TRACER_PROVIDER = ProxyTracerProvider()
        2. ProxyTracerProvider.get_tracer() reads trace._TRACER_PROVIDER
        3. Since IT IS the _TRACER_PROVIDER, it calls itself -> infinite recursion

        The fix sets _TRACER_PROVIDER = None, which makes get_tracer()
        return a NoOp tracer instead of recursing.

        We call reset_telemetry() then get_tracer() and assert no
        RecursionError is raised.
        """
        from floe_core.telemetry.initialization import reset_telemetry
        from opentelemetry import trace

        # Reset OTel state to a clean slate first
        if hasattr(trace, "_TRACER_PROVIDER_SET_ONCE"):
            trace._TRACER_PROVIDER_SET_ONCE._done = False
        if hasattr(trace, "_TRACER_PROVIDER"):
            trace._TRACER_PROVIDER = None

        # Now call reset_telemetry() -- this is the function under test
        reset_telemetry()

        # This is the call that triggers infinite recursion with the bug
        try:
            tracer = trace.get_tracer("test-after-reset")
        except RecursionError:
            pytest.fail(
                "trace.get_tracer() raised RecursionError after reset_telemetry(). "
                "This happens when reset_telemetry() sets "
                "trace._TRACER_PROVIDER = ProxyTracerProvider(). "
                "It must set trace._TRACER_PROVIDER = None instead."
            )

        # The tracer should be usable (even if it's a NoOp)
        assert tracer is not None, (
            "trace.get_tracer() returned None after reset_telemetry(). "
            "Expected a valid tracer (even NoOp)."
        )

    @pytest.mark.requirement("AC-2")
    def test_create_span_after_reset_does_not_raise_recursion_error(self) -> None:
        """After reset_telemetry(), creating a span must NOT raise RecursionError.

        This extends the behavioral test to cover the full span creation path,
        which is the actual use case that triggers the bug in production.
        """
        from floe_core.telemetry.initialization import reset_telemetry
        from opentelemetry import trace

        # Reset to clean slate
        if hasattr(trace, "_TRACER_PROVIDER_SET_ONCE"):
            trace._TRACER_PROVIDER_SET_ONCE._done = False
        if hasattr(trace, "_TRACER_PROVIDER"):
            trace._TRACER_PROVIDER = None

        reset_telemetry()

        # Creating a span goes through get_tracer() -> start_span()
        try:
            tracer = trace.get_tracer("test-span-creation")
            with tracer.start_as_current_span("test-span") as span:
                # The span should exist (even if NoOp)
                assert span is not None
        except RecursionError:
            pytest.fail(
                "Creating a span raised RecursionError after reset_telemetry(). "
                "This confirms the ProxyTracerProvider recursion bug. "
                "reset_telemetry() must set trace._TRACER_PROVIDER = None."
            )

    @pytest.mark.requirement("AC-2")
    def test_get_tracer_after_reset_returns_functional_tracer(self) -> None:
        """After reset_telemetry(), the returned tracer must be able to create spans.

        A sloppy fix might prevent RecursionError but return a broken tracer.
        We verify the tracer can start a span and the span has a valid context.
        """
        from floe_core.telemetry.initialization import reset_telemetry
        from opentelemetry import trace

        # Reset to clean slate
        if hasattr(trace, "_TRACER_PROVIDER_SET_ONCE"):
            trace._TRACER_PROVIDER_SET_ONCE._done = False
        if hasattr(trace, "_TRACER_PROVIDER"):
            trace._TRACER_PROVIDER = None

        reset_telemetry()

        tracer = trace.get_tracer("test-functional")
        with tracer.start_as_current_span("functional-test") as span:
            ctx = span.get_span_context()
            # The context must exist and be valid (even if it's a NoOp context)
            assert ctx is not None, "Span context is None after reset_telemetry()"
            # A NoOp span has trace_id=0, which is acceptable after reset.
            # The key point is it doesn't crash.
            assert isinstance(ctx.trace_id, int), f"trace_id is not an int: {type(ctx.trace_id)}"
