"""Stale backup detection tests for the dbt_e2e_profile fixture (WU-36).

Validates that the ``dbt_e2e_profile`` fixture in ``tests/e2e/conftest.py``
contains a stale ``.bak`` detection guard that runs BEFORE backup creation.
This prevents ``make compile-demo`` failures when a previous test session
crashed and left orphaned ``.bak`` files (with E2E profiles still in place
of the original ``profiles.yml``).

These are structural/unit tests that parse the fixture source code via AST
and text analysis -- no external services or K8s cluster required.

Requirements:
    AC-36.1: Stale .bak detection before backup creation
    AC-36.5: All 3 demo products covered by the guard
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_CONFTEST = REPO_ROOT / "tests" / "e2e" / "conftest.py"

# The canonical list of demo products that _DBT_DEMO_PRODUCTS must contain.
EXPECTED_DEMO_PRODUCTS = {"customer-360", "iot-telemetry", "financial-risk"}


def _get_fixture_source() -> str:
    """Extract the full source of the ``dbt_e2e_profile`` fixture function.

    Returns:
        The source text of the ``dbt_e2e_profile`` function body.

    Raises:
        AssertionError: If the fixture is not found in conftest.py.
    """
    content = E2E_CONFTEST.read_text()
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "dbt_e2e_profile":
            source = ast.get_source_segment(content, node)
            assert source is not None, "Could not extract source segment for dbt_e2e_profile"
            return source

    pytest.fail("dbt_e2e_profile fixture not found in tests/e2e/conftest.py")
    return ""  # pragma: no cover


def _get_guard_region(source: str) -> str:
    """Extract the stale backup guard region from the fixture source.

    The guard must be a top-level block of code (not inside any nested
    function definition) that appears between the variable declarations
    and the ``try:`` block. This function strips out nested ``def``
    bodies so that ``_restore_backups()`` does not cause false positives.

    Returns:
        Source text of the guard region with nested defs removed.
        Empty string if the region cannot be isolated.
    """
    # Find boundaries: after "backups: dict" and "profile_paths: dict",
    # before the "try:" block.
    backups_match = re.search(r"profile_paths:\s*dict\[.*?\]\s*=\s*\{\}", source)
    try_match = re.search(r"^\s+try:\s*$", source, re.MULTILINE)

    if backups_match is None or try_match is None:
        return ""

    region = source[backups_match.end() : try_match.start()]

    # Remove nested function definitions (like _restore_backups).
    # A nested def starts with "    def " and continues until the next
    # line at the same or lesser indentation (excluding blank lines).
    # We use AST to find nested FunctionDef nodes and blank them out.
    region_cleaned = _remove_nested_defs(region)

    return region_cleaned


def _remove_nested_defs(region: str) -> str:
    """Remove nested function definitions from a code region.

    Uses line-by-line analysis: when a ``def`` line is found, all
    subsequent lines that are more indented (or blank) are removed
    until a line at the same or lesser indentation is reached.

    Args:
        region: Source text that may contain nested function definitions.

    Returns:
        Source text with nested def bodies removed.
    """
    lines = region.split("\n")
    result: list[str] = []
    skip_indent: int | None = None

    for line in lines:
        stripped = line.lstrip()

        if skip_indent is not None:
            # We are inside a nested def -- skip until de-indentation
            if stripped == "":
                continue  # Blank line inside nested def
            current_indent = len(line) - len(stripped)
            if current_indent > skip_indent:
                continue  # Still inside the nested def
            # De-indented: stop skipping
            skip_indent = None

        if stripped.startswith("def "):
            # Start of a nested function definition
            skip_indent = len(line) - len(stripped)
            continue

        result.append(line)

    return "\n".join(result)


class TestStaleBackupGuardExists:
    """AC-36.1: Stale .bak detection guard exists before backup creation."""

    @pytest.mark.requirement("AC-36.1")
    def test_fixture_contains_bak_detection_loop(self) -> None:
        """Verify dbt_e2e_profile has a top-level loop checking for stale .bak files.

        The fixture must iterate over products and check whether
        ``profiles.yml.bak`` already exists BEFORE creating new backups.
        A stale ``.bak`` from a crashed session means the original
        ``profiles.yml`` was never restored.

        This loop must be at the fixture's top level (not inside the
        ``_restore_backups`` nested function), and it must reference
        ``_DBT_DEMO_PRODUCTS`` to cover all demo products.
        """
        source = _get_fixture_source()
        guard = _get_guard_region(source)

        has_bak_ref = ".bak" in guard
        has_loop = re.search(r"\bfor\b", guard) is not None
        has_products_ref = "_DBT_DEMO_PRODUCTS" in guard

        assert has_bak_ref and has_loop and has_products_ref, (
            "dbt_e2e_profile must contain a top-level loop over "
            "_DBT_DEMO_PRODUCTS that checks for stale .bak files "
            "BEFORE the try: block. "
            f"Found .bak ref: {has_bak_ref}, "
            f"found loop: {has_loop}, "
            f"found _DBT_DEMO_PRODUCTS ref: {has_products_ref}. "
            "The _restore_backups() nested function does NOT count -- "
            "it only runs on normal teardown, not crash recovery."
        )

    @pytest.mark.requirement("AC-36.1")
    def test_guard_checks_bak_file_existence(self) -> None:
        """Verify the guard tests whether a .bak file exists on disk.

        The guard must call ``.exists()`` or ``.is_file()`` on the
        backup path to detect stale backups. Without an existence
        check, the guard is a no-op that processes nothing.
        """
        source = _get_fixture_source()
        guard = _get_guard_region(source)

        has_exists_check = re.search(r"\w*bak\w*\.(?:exists|is_file)\(\)", guard) is not None

        assert has_exists_check, (
            "Stale backup guard must check .bak file existence via "
            ".exists() or .is_file() on the backup path variable. "
            "No such pattern found in the guard region (excluding "
            "the _restore_backups nested function)."
        )

    @pytest.mark.requirement("AC-36.1")
    def test_guard_restores_original_from_bak(self) -> None:
        """Verify the guard restores profiles.yml from the stale .bak file.

        Detection without restoration is useless. The guard must copy
        or move the ``.bak`` content back to ``profiles.yml`` (via
        ``rename``, ``replace``, or ``read_text``/``write_text``).
        """
        source = _get_fixture_source()
        guard = _get_guard_region(source)

        has_rename = "rename" in guard or "replace" in guard
        has_copy = "shutil" in guard and "copy" in guard
        has_read_write = "read_text" in guard and "write_text" in guard

        assert has_rename or has_copy or has_read_write, (
            "Stale backup guard must restore profiles.yml from the .bak "
            "file. Expected rename(), replace(), shutil.copy(), or "
            "read_text/write_text pattern in the guard region. "
            "Detection without restoration leaves E2E profiles in place "
            "and make compile-demo will still fail."
        )


class TestStaleBackupGuardCoverage:
    """AC-36.5: Guard covers all 3 demo products."""

    @pytest.mark.requirement("AC-36.5")
    def test_guard_iterates_over_dbt_demo_products(self) -> None:
        """Verify the stale backup guard iterates over _DBT_DEMO_PRODUCTS.

        The guard loop must use ``_DBT_DEMO_PRODUCTS`` (the same dict
        as the backup creation loop) to ensure all 3 products are
        covered. Hardcoding a subset would miss products.
        """
        source = _get_fixture_source()
        guard = _get_guard_region(source)

        # Must have a for loop that references _DBT_DEMO_PRODUCTS
        has_for_over_products = re.search(r"for\s+\w+.*_DBT_DEMO_PRODUCTS", guard) is not None

        assert has_for_over_products, (
            "Stale backup guard must have a 'for ... in _DBT_DEMO_PRODUCTS' "
            "loop to cover all demo products. No such loop found in the "
            "guard region. Hardcoding product names would drift from the "
            "canonical list."
        )

    @pytest.mark.requirement("AC-36.5")
    def test_dbt_demo_products_dict_contains_all_three(self) -> None:
        """Verify _DBT_DEMO_PRODUCTS in conftest.py lists all 3 demo products.

        The guard's correctness depends on the completeness of the
        ``_DBT_DEMO_PRODUCTS`` dict. If a product is missing from the
        dict, its stale .bak will never be detected.
        """
        content = E2E_CONFTEST.read_text()

        match = re.search(
            r"_DBT_DEMO_PRODUCTS.*?=\s*\{([^}]+)\}",
            content,
            re.DOTALL,
        )
        assert match is not None, "_DBT_DEMO_PRODUCTS dict not found in tests/e2e/conftest.py"

        dict_body = match.group(1)

        for product in sorted(EXPECTED_DEMO_PRODUCTS):
            assert f'"{product}"' in dict_body, (
                f"_DBT_DEMO_PRODUCTS is missing product '{product}'. "
                f"All 3 demo products must be listed: "
                f"{sorted(EXPECTED_DEMO_PRODUCTS)}"
            )

    @pytest.mark.requirement("AC-36.5")
    def test_guard_constructs_paths_for_demo_directory(self) -> None:
        """Verify the guard builds paths under the demo/ directory tree.

        The guard must construct paths like
        ``project_root / 'demo' / product_dir`` to locate the correct
        ``profiles.yml.bak`` files. Using a wrong base path would
        silently miss all stale backups.
        """
        source = _get_fixture_source()
        guard = _get_guard_region(source)

        has_demo_path = '"demo"' in guard or "'demo'" in guard
        assert has_demo_path, (
            "Stale backup guard must construct paths under the 'demo/' "
            "directory (e.g., project_root / 'demo' / product_dir). "
            "No 'demo' path reference found in the guard region. "
            "The _restore_backups() nested function does NOT count."
        )


class TestStaleBackupGuardOrdering:
    """Verify restore-then-backup ordering within the fixture."""

    @pytest.mark.requirement("AC-36.1")
    def test_guard_loop_appears_before_backup_creation_loop(self) -> None:
        """Verify the guard loop over _DBT_DEMO_PRODUCTS appears before backup creation.

        The fixture must have at least 2 loops over _DBT_DEMO_PRODUCTS:
        (1) the stale .bak detection guard, and (2) the backup creation
        loop inside the try: block. The guard must come first.
        """
        source = _get_fixture_source()

        loop_pattern = r"for\s+\w+.*_DBT_DEMO_PRODUCTS"
        loops = list(re.finditer(loop_pattern, source))

        assert len(loops) >= 2, (
            f"Expected at least 2 loops over _DBT_DEMO_PRODUCTS in "
            f"dbt_e2e_profile: one for stale .bak detection (guard) and "
            f"one for backup creation. Found {len(loops)} loop(s). "
            "The _restore_backups() nested function loops over "
            "backups.items(), not _DBT_DEMO_PRODUCTS, so it does not "
            "count."
        )

        guard_loop_pos = loops[0].start()
        backup_loop_pos = loops[1].start()

        assert guard_loop_pos < backup_loop_pos, (
            f"Stale backup guard loop (pos {guard_loop_pos}) must appear "
            f"before backup creation loop (pos {backup_loop_pos}). "
            "Guard after backup creation would overwrite stale .bak "
            "files with new backups, destroying original content."
        )

    @pytest.mark.requirement("AC-36.1")
    def test_guard_loop_is_outside_try_block(self) -> None:
        """Verify the guard loop is outside the try: block.

        The guard runs unconditionally before the try: block. If it
        were inside the try: block, a crash during the guard itself
        would trigger _restore_backups() which operates on the
        ``backups`` dict -- but the guard hasn't populated it yet.
        The guard must be standalone.
        """
        source = _get_fixture_source()

        try_match = re.search(r"^\s+try:\s*$", source, re.MULTILINE)
        assert try_match is not None, "Could not find try: block in dbt_e2e_profile fixture"
        try_pos = try_match.start()

        # Find the first loop over _DBT_DEMO_PRODUCTS (should be guard)
        guard_loop = re.search(r"for\s+\w+.*_DBT_DEMO_PRODUCTS", source)
        assert guard_loop is not None, "No loop over _DBT_DEMO_PRODUCTS found in dbt_e2e_profile"

        assert guard_loop.start() < try_pos, (
            f"The first _DBT_DEMO_PRODUCTS loop (pos {guard_loop.start()}) "
            f"must appear before the try: block (pos {try_pos}). "
            "The guard must be outside try: to run unconditionally."
        )

    @pytest.mark.requirement("AC-36.1")
    def test_try_block_still_contains_backup_creation(self) -> None:
        """Verify the try: block still contains backup/profile write logic.

        The guard addition must not remove the existing backup creation
        from the try: block. Both the guard AND the backup creation
        must exist.
        """
        source = _get_fixture_source()

        try_match = re.search(r"try:\s*\n(.*?)except\s+", source, re.DOTALL)
        assert try_match is not None, "Could not find try/except block in dbt_e2e_profile fixture"

        try_body = try_match.group(1)

        assert "write_text" in try_body, (
            "try: block must still contain write_text() calls for "
            "creating backups and writing E2E profiles. The stale "
            "backup guard must be ADDED, not replace the existing logic."
        )
        assert "_build_dbt_iceberg_profile" in try_body, (
            "try: block must still contain _build_dbt_iceberg_profile() "
            "call for writing E2E profiles. The guard must not remove "
            "existing backup creation logic."
        )


class TestStaleBackupGuardEdgeCases:
    """Edge cases for the stale backup guard."""

    @pytest.mark.requirement("AC-36.1")
    def test_guard_conditioned_on_bak_existence_not_profile(self) -> None:
        """Verify the guard is conditioned on .bak file existence.

        Scenario: A crash left .bak in place but profiles.yml was
        deleted or was never restored. The guard must trigger on
        ``.bak`` existence, not on ``profiles.yml`` existence.

        The guard's if-condition must check the bak path, not the
        profile path.
        """
        source = _get_fixture_source()
        guard = _get_guard_region(source)

        bak_exists = re.search(r"if\s+\w*bak\w*\.(?:exists|is_file)\(\)", guard)

        assert bak_exists is not None, (
            "Stale backup guard must use 'if bak_path.exists()' "
            "(or similar) as its trigger condition. The guard is "
            "about detecting stale .bak files, so the condition must "
            "check bak file existence. No such pattern found."
        )

    @pytest.mark.requirement("AC-36.1")
    def test_guard_cleans_up_bak_after_restore(self) -> None:
        """Verify the guard removes the .bak file after restoring.

        After restoring profiles.yml from .bak, the .bak must be
        removed so it is not re-detected as stale. Without cleanup,
        every session would repeat the restoration unnecessarily.

        Note: The current implementation uses ``bak_path.rename(profile_path)``
        which atomically moves the .bak to profiles.yml — serving as both
        restore AND cleanup in a single operation. This test accepts either
        an explicit ``unlink()`` (two-step: copy + delete) or ``rename()``
        (atomic move that inherently removes the source file).
        """
        source = _get_fixture_source()
        guard = _get_guard_region(source)

        # After restore, .bak must be cleaned up.
        # rename() inherently removes the source (.bak) file — it serves
        # as both restore and cleanup atomically.
        has_unlink = "unlink" in guard
        has_rename = "rename" in guard or "replace" in guard

        assert has_unlink or has_rename, (
            "Stale backup guard must remove the .bak file after "
            "restoring profiles.yml. Expected unlink() or rename()/replace() "
            "in the guard region. Without cleanup, every session would "
            "trigger unnecessary restoration."
        )

    @pytest.mark.requirement("AC-36.1")
    def test_guard_provides_observability(self) -> None:
        """Verify the guard logs or warns when a stale .bak is detected.

        Silent restoration is fragile. The guard should log a warning
        or emit a pytest warning so developers know crash recovery
        occurred. This aids debugging when profiles unexpectedly change.
        """
        source = _get_fixture_source()
        guard = _get_guard_region(source)

        has_log = re.search(r"(?:log|logger)\.\w+\(", guard) is not None
        has_warnings = "warnings.warn" in guard

        assert has_log or has_warnings, (
            "Stale backup guard should log or warn when a stale .bak "
            "is detected and restored. Silent restoration hides crash "
            "recovery from developers. Expected logger.warning() or "
            "warnings.warn() call in the guard region. "
            "Bare print() is not acceptable — use structured logging."
        )
