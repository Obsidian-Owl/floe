"""Tests for AC-4: OTel test assertions match production attribute prefixes.

Validates that ``test_trace_content_validation`` in ``test_observability.py``
checks for actual production attribute prefixes (``compile.*``,
``governance.*``, ``enforcement.*``, ``floe.*``) instead of only ``floe.*``
via substring matching.

Production code uses these prefixes:
    - ``compile.*``     (6 attrs in stages.py)
    - ``governance.*``  (5 attrs in integrator.py)
    - ``enforcement.*`` (5 attrs in stages.py)
    - ``floe.*``        (8 core attrs in conventions.py)

The original code used ``"floe" in k.lower()`` which is a substring match
that would miss ``compile.*``, ``governance.*``, and ``enforcement.*``
entirely, giving false confidence that only ``floe.*`` matters.

The fix must:
    1. Use ``.startswith()`` with specific prefixes, not substring ``in``
    2. Reference all four production prefixes
    3. Include a ``TODO(#144)`` comment for future ``floe.{domain}.*`` migration

Test categories:
    **Structural** (source-parsing, per P28/P29):
        Inspect ``test_observability.py`` to verify the fix was applied.

Requirements Covered:
    AC-4: OTel test assertions match production attribute prefixes

See Also:
    - tests/e2e/test_observability.py (test_trace_content_validation)
    - packages/floe-core/src/floe_core/compilation/stages.py
    - packages/floe-core/src/floe_core/governance/integrator.py
    - packages/floe-core/src/floe_core/telemetry/conventions.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from testing.fixtures.source_parsing import (
    get_function_source,
    strip_comments_and_docstrings,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

OBSERVABILITY_TEST_FILE = REPO_ROOT / "tests" / "e2e" / "test_observability.py"

# The four production attribute prefixes that MUST be checked.
REQUIRED_PRODUCTION_PREFIXES: list[str] = [
    "compile.",
    "governance.",
    "enforcement.",
    "floe.",
]

# Substring-matching patterns that are FORBIDDEN in executable code.
# These catch lazy implementations that use `"floe" in k.lower()` or
# `"floe" in k` instead of proper `.startswith()` prefix matching.
FORBIDDEN_SUBSTRING_PATTERNS: list[re.Pattern[str]] = [
    # "floe" in k.lower()
    re.compile(r'"floe"\s+in\s+\w+\.lower\(\)'),
    # "floe" in k
    re.compile(r'"floe"\s+in\s+\w+(?!\.lower)'),
    # 'floe' in k.lower()
    re.compile(r"'floe'\s+in\s+\w+\.lower\(\)"),
    # 'floe' in k
    re.compile(r"'floe'\s+in\s+\w+(?!\.lower)"),
]


class TestNoSubstringMatchingForFloe:
    """Verify test_trace_content_validation does NOT use substring matching for 'floe'.

    The original code used ``"floe" in k.lower()`` which is a substring match.
    This catches any attribute key containing "floe" anywhere, which:
    - Is overly broad (would match "refloe", "sunfloe", etc.)
    - Only checks for floe-prefixed attributes, missing compile.*, governance.*, enforcement.*
    - Gives false confidence that the single-prefix check is sufficient
    """

    @pytest.mark.requirement("AC-4")
    def test_no_substring_floe_match_in_executable_code(self) -> None:
        """Executable code must NOT use 'floe' in k or 'floe' in k.lower() for attribute matching.

        The fix replaces substring matching with explicit .startswith() calls
        for each production prefix. This test reads the function source, strips
        comments and docstrings (P29), and checks that no substring matching
        pattern exists in the executable code.
        """
        assert OBSERVABILITY_TEST_FILE.exists(), (
            f"test_observability.py not found at {OBSERVABILITY_TEST_FILE}"
        )

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")
        executable_code = strip_comments_and_docstrings(func_source)

        violations: list[str] = []
        for pattern in FORBIDDEN_SUBSTRING_PATTERNS:
            matches = pattern.findall(executable_code)
            if matches:
                violations.append(f"  Pattern {pattern.pattern!r} matched: {matches}")

        assert len(violations) == 0, (
            "test_trace_content_validation uses substring matching for 'floe' "
            "in executable code. This is a weak assertion that misses "
            "production prefixes like compile.*, governance.*, enforcement.*.\n"
            "Violations:\n" + "\n".join(violations) + "\n"
            "Fix: Replace substring 'in' checks with .startswith() prefix matching "
            "for each production domain prefix."
        )

    @pytest.mark.requirement("AC-4")
    def test_no_floe_only_list_comprehension_filter(self) -> None:
        """The attribute filter must NOT be a single-prefix list comprehension on 'floe'.

        Catches the exact pattern:
            floe_attributes = [k for k in all_tag_keys if "floe" in k.lower()]

        A lazy fix might change to .startswith("floe") but still only check
        one prefix. This test verifies the old single-prefix pattern is gone.
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")
        executable_code = strip_comments_and_docstrings(func_source)

        # Match: [k for k in <var> if "floe" in k...]
        # or:    [k for k in <var> if k.startswith("floe")]
        # These are single-prefix filters that miss compile.*, governance.*, etc.
        single_prefix_floe_only = re.compile(
            r"\[\s*\w+\s+for\s+\w+\s+in\s+\w+\s+if\s+"
            r'(?:"floe"|\'floe\')\s+in\s+\w+'
        )
        matches = single_prefix_floe_only.findall(executable_code)
        assert len(matches) == 0, (
            "test_trace_content_validation still uses a single-prefix "
            f"'floe'-only list comprehension filter: {matches}\n"
            "The fix must check for ALL production prefixes: "
            f"{REQUIRED_PRODUCTION_PREFIXES}"
        )


class TestProductionPrefixesReferenced:
    """Verify test_trace_content_validation references all production attribute prefixes.

    Production code emits attributes with compile.*, governance.*, enforcement.*,
    and floe.* prefixes. The test must check for ALL of them, not just floe.*.
    """

    @pytest.mark.requirement("AC-4")
    @pytest.mark.parametrize(
        "prefix",
        ["compile.", "governance.", "enforcement."],
        ids=["compile-prefix", "governance-prefix", "enforcement-prefix"],
    )
    def test_non_floe_prefix_referenced_in_executable_code(self, prefix: str) -> None:
        """Each non-floe production prefix must appear in executable code of the test.

        The fix must reference compile., governance., and enforcement. prefixes
        in the attribute-checking logic (not just in comments or docstrings).

        Uses comment/docstring stripping (P29) so a comment like
        '# TODO: check compile. prefix' does not satisfy the test.

        Args:
            prefix: The production attribute prefix to check for.
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")
        executable_code = strip_comments_and_docstrings(func_source)

        # The prefix string must appear in executable code -- as a string literal
        # used in the attribute filtering logic (e.g., in a startswith call or
        # a collection of prefixes).
        assert f'"{prefix}"' in executable_code or f"'{prefix}'" in executable_code, (
            f"Production prefix {prefix!r} not found as a string literal in "
            f"executable code of test_trace_content_validation.\n"
            f"Production code emits attributes with this prefix. "
            f"The test must check for it alongside 'floe.' to catch "
            f"real attribute coverage.\n"
            f"Fix: Add {prefix!r} to the set of prefixes checked in "
            f"the attribute validation logic."
        )

    @pytest.mark.requirement("AC-4")
    def test_all_four_prefixes_present_in_executable_code(self) -> None:
        """All four production prefixes must appear in executable code.

        This test verifies that ALL required prefixes are present, not just
        a subset. A lazy implementation might add compile. but forget
        governance. or enforcement.*.
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")
        executable_code = strip_comments_and_docstrings(func_source)

        missing: list[str] = []
        for prefix in REQUIRED_PRODUCTION_PREFIXES:
            if f'"{prefix}"' not in executable_code and f"'{prefix}'" not in executable_code:
                missing.append(prefix)

        assert len(missing) == 0, (
            f"Missing production prefixes in executable code of "
            f"test_trace_content_validation: {missing}\n"
            f"All four prefixes must be checked: {REQUIRED_PRODUCTION_PREFIXES}\n"
            f"Production code emits attributes with all of these prefixes."
        )


class TestStartswithUsedForPrefixMatching:
    """Verify the fix uses .startswith() for prefix matching, not substring 'in'.

    Prefix matching via .startswith() is exact and unambiguous:
        k.startswith("compile.")  -- matches "compile.model_count" but not "recompile.x"

    Substring matching via 'in' is sloppy:
        "floe" in k  -- matches "refloe", "sunfloe_thing", etc.
    """

    @pytest.mark.requirement("AC-4")
    def test_startswith_used_in_attribute_matching(self) -> None:
        """The attribute matching logic must use .startswith() for prefix checks.

        This verifies the fix uses proper prefix matching. A sloppy fix
        might use substring 'in' checks which are weaker.
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")
        executable_code = strip_comments_and_docstrings(func_source)

        # .startswith() must appear in the executable code
        assert "startswith" in executable_code, (
            "test_trace_content_validation does not use .startswith() for "
            "attribute prefix matching in its executable code.\n"
            "The fix must use .startswith() to match production prefixes "
            "exactly (e.g., k.startswith('compile.')) instead of substring "
            "'in' matching which is ambiguous.\n"
            "Fix: Use any(k.startswith(p) for p in PREFIXES) or similar."
        )

    @pytest.mark.requirement("AC-4")
    def test_startswith_used_with_domain_prefix(self) -> None:
        """At least one .startswith() call must reference a production domain prefix.

        This prevents a sloppy fix that adds a random .startswith("x") call
        to satisfy the previous test while still using substring matching
        for the actual attribute check.
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")
        executable_code = strip_comments_and_docstrings(func_source)

        # At least one startswith call must reference a production prefix
        has_domain_startswith = False
        for prefix in REQUIRED_PRODUCTION_PREFIXES:
            # Match patterns like: .startswith("compile.") or .startswith('compile.')
            pattern = re.compile(rf'\.startswith\(\s*["\']' + re.escape(prefix) + r'["\']')
            if pattern.search(executable_code):
                has_domain_startswith = True
                break

        # Also check for tuple/list form: .startswith(("compile.", "governance.", ...))
        # or any(k.startswith(p) for p in ...)
        if not has_domain_startswith:
            # Check for the tuple form where startswith gets a tuple of prefixes
            # that contains at least one production prefix
            tuple_pattern = re.compile(r"\.startswith\(\s*\(")
            if tuple_pattern.search(executable_code):
                # If startswith((...)) is used, check that at least one
                # production prefix appears inside it
                for prefix in REQUIRED_PRODUCTION_PREFIXES:
                    if f'"{prefix}"' in executable_code or f"'{prefix}'" in executable_code:
                        has_domain_startswith = True
                        break

        # Also check for generator/comprehension form:
        # any(k.startswith(p) for p in prefixes_var)
        if not has_domain_startswith:
            any_startswith_pattern = re.compile(
                r"any\(\s*\w+\.startswith\(\s*\w+\s*\)\s+for\s+\w+\s+in\s+"
            )
            if any_startswith_pattern.search(executable_code):
                # Verify the prefix collection contains production prefixes
                for prefix in REQUIRED_PRODUCTION_PREFIXES:
                    if f'"{prefix}"' in executable_code or f"'{prefix}'" in executable_code:
                        has_domain_startswith = True
                        break

        assert has_domain_startswith, (
            "No .startswith() call references a production domain prefix "
            f"({REQUIRED_PRODUCTION_PREFIXES}) in executable code of "
            f"test_trace_content_validation.\n"
            "The fix must use .startswith() with production prefixes "
            "for exact attribute matching. Example:\n"
            "  any(k.startswith(p) for p in ('compile.', 'governance.', "
            "'enforcement.', 'floe.'))"
        )


class TestTodoCommentExists:
    """Verify a TODO(#144) comment is present for the future floe.{domain}.* migration.

    The current fix preserves backward compatibility by checking multiple
    prefix families. Issue #144 tracks the future migration to a unified
    floe.{domain}.* namespace. A TODO comment must be present to ensure
    the migration is not forgotten.
    """

    @pytest.mark.requirement("AC-4")
    def test_todo_144_present_in_file(self) -> None:
        """The file must contain a TODO(#144) comment referencing the migration.

        This uses raw source (not comment-stripped) because we specifically
        WANT to find the comment. The check is for the specific issue number
        to prevent generic TODO comments from satisfying the test.
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        raw_source = OBSERVABILITY_TEST_FILE.read_text()

        # Match TODO(#144) -- the specific issue tracking the migration
        assert "TODO(#144)" in raw_source, (
            "test_observability.py does not contain a TODO(#144) comment.\n"
            "AC-4 requires a TODO(#144) referencing the future migration "
            "to a unified floe.{domain}.* prefix namespace.\n"
            "Fix: Add a comment like:\n"
            "  # TODO(#144): migrate to floe.{domain}.* prefix namespace"
        )

    @pytest.mark.requirement("AC-4")
    def test_todo_144_near_attribute_prefix_logic(self) -> None:
        """The TODO(#144) comment must be near the attribute prefix checking logic.

        A sloppy fix might put the TODO at the top of the file as a module-level
        comment, far from the actual logic it references. The TODO must appear
        within the test_trace_content_validation function or within 10 lines of
        the prefix-matching code.
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")

        # The TODO must appear within the function source
        assert "TODO(#144)" in func_source, (
            "TODO(#144) is not within the test_trace_content_validation function.\n"
            "The comment must be near the attribute prefix checking logic, "
            "not at the module level or in another function.\n"
            "Fix: Add the TODO(#144) comment inside test_trace_content_validation, "
            "adjacent to the prefix matching code."
        )


class TestAssertionStrengthNotWeakened:
    """Verify the fix maintains strong assertions, not vague existence checks.

    A lazy fix might replace the original assertion with something like:
        assert len(all_tag_keys) > 0  # "any attribute exists"

    The fix must verify specific domain attributes exist with exact prefix
    matching, not just that "some attributes" are present.
    """

    @pytest.mark.requirement("AC-4")
    def test_no_vague_any_attribute_check(self) -> None:
        """The fix must NOT use vague 'any attribute exists' assertions.

        Catches weak patterns like:
            assert len(all_tag_keys) > 0
            assert all_tag_keys  (truthy check)
            assert len(domain_attrs) >= 0  (always true)
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")
        executable_code = strip_comments_and_docstrings(func_source)

        # Check that the fix doesn't replace the assertion with a trivially-true check.
        # The assertion must still verify specific attributes were found.
        # We verify by confirming that domain-specific prefixes appear in the
        # assertion error message or the filtering logic, proving the assertion
        # is checking for specific domains.
        has_domain_specific_assertion = False
        for prefix in ["compile.", "governance.", "enforcement."]:
            if f'"{prefix}"' in executable_code or f"'{prefix}'" in executable_code:
                has_domain_specific_assertion = True
                break

        assert has_domain_specific_assertion, (
            "test_trace_content_validation does not reference any non-floe "
            "production prefix (compile., governance., enforcement.) in its "
            "executable code. This suggests the assertion was weakened to a "
            "vague 'any attribute exists' check instead of verifying specific "
            "domain attribute prefixes."
        )

    @pytest.mark.requirement("AC-4")
    def test_assertion_references_multiple_domain_prefixes(self) -> None:
        """The assertion logic must reference multiple production prefix families.

        A sloppy fix might keep the old single-variable assertion
        (``assert len(floe_attributes) > 0``) which only validates one
        prefix family. The fixed assertion must demonstrate awareness of
        multiple domain prefixes in its assertion or filtering logic.

        This test counts how many distinct production prefixes appear as
        string literals in the executable code. At least 3 of the 4
        (compile., governance., enforcement., floe.) must be present.
        """
        assert OBSERVABILITY_TEST_FILE.exists()

        func_source = get_function_source(OBSERVABILITY_TEST_FILE, "test_trace_content_validation")
        executable_code = strip_comments_and_docstrings(func_source)

        found_prefixes: list[str] = []
        for prefix in REQUIRED_PRODUCTION_PREFIXES:
            if f'"{prefix}"' in executable_code or f"'{prefix}'" in executable_code:
                found_prefixes.append(prefix)

        assert len(found_prefixes) >= 3, (
            f"test_trace_content_validation references only "
            f"{len(found_prefixes)} of 4 production prefixes in its "
            f"executable code: {found_prefixes}\n"
            f"At least 3 of {REQUIRED_PRODUCTION_PREFIXES} must appear "
            f"as string literals in the attribute-checking logic to ensure "
            f"the assertion covers production-emitted attributes from all "
            f"domains (compile, governance, enforcement, floe)."
        )
