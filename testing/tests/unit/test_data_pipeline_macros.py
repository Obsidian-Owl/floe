"""Structural validation: test_data_retention_enforcement macro path resolution.

Tests that the E2E test ``test_data_retention_enforcement`` in
``tests/e2e/test_data_pipeline.py`` resolves macro paths dynamically from
``dbt_project.yml``'s ``macro-paths`` config instead of hardcoding
``project_dir / "macros"``.

AC-36.2: The test MUST:
  - Read ``dbt_project.yml`` to discover macro directories
  - Handle relative paths (e.g., ``"../macros"``) via ``Path.resolve()``
  - Iterate ALL entries in ``macro-paths``, not just ``[0]``
  - NOT hardcode ``project_dir / "macros"`` as the sole macro search path

These are structural (source-parsing) tests. They inspect the Python source
of the function under test. They do NOT import or execute the E2E test.

Requirements:
    AC-36.2: Macro path resolution from dbt_project.yml
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from testing.fixtures.source_parsing import get_function_source, strip_comments_and_docstrings

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_TEST_FILE = REPO_ROOT / "tests" / "e2e" / "test_data_pipeline.py"


@pytest.fixture(scope="module")
def retention_test_source() -> str:
    """Source text of test_data_retention_enforcement from the E2E file.

    Returns:
        The complete source text of the function.
    """
    assert E2E_TEST_FILE.exists(), (
        f"E2E test file not found at {E2E_TEST_FILE}. "
        "Cannot validate macro path resolution without the source."
    )
    return get_function_source(E2E_TEST_FILE, "test_data_retention_enforcement")


@pytest.fixture(scope="module")
def retention_test_code(retention_test_source: str) -> str:
    """Executable code only (no comments/docstrings) from test_data_retention_enforcement.

    Returns:
        Source text with comments and docstrings removed.
    """
    return strip_comments_and_docstrings(retention_test_source)


class TestNoHardcodedMacrosDir:
    """Verify the test does NOT hardcode ``project_dir / "macros"`` as the sole path."""

    @pytest.mark.requirement("AC-36.2")
    def test_no_hardcoded_macros_path_as_sole_source(self, retention_test_code: str) -> None:
        """Source must NOT use ``project_dir / "macros"`` as the only macro directory.

        The broken pattern is:
            macros_dir = project_dir / "macros"
            assert macros_dir.exists()
            for macro_file in macros_dir.glob(...)

        A correct implementation reads dbt_project.yml's macro-paths config,
        which may point to ``../macros`` or multiple directories. It must NOT
        fall back to a single hardcoded path without also reading the config.

        Uses comment-stripped code to prevent bypassing via a comment containing
        ``dbt_project.yml``.
        """
        # Pattern: assignment of project_dir / "macros" used as the only
        # macro directory (not augmented by dbt_project.yml reading).
        # Uses comment-stripped code so a comment like
        # "# dbt_project.yml is the config" doesn't satisfy the check.
        has_hardcoded_macros = bool(
            re.search(r'project_dir\s*/\s*["\']macros["\']', retention_test_code)
        )
        reads_dbt_project_yml = bool(re.search(r"dbt_project\.yml", retention_test_code))

        # If it hardcodes project_dir/"macros" but never reads dbt_project.yml
        # in executable code, it's using the broken pattern.
        assert not (has_hardcoded_macros and not reads_dbt_project_yml), (
            'test_data_retention_enforcement hardcodes `project_dir / "macros"` '
            "without reading dbt_project.yml's macro-paths config in executable code. "
            "It must resolve macro paths from the dbt project configuration."
        )


class TestReadsDbtProjectYml:
    """Verify the test reads and parses dbt_project.yml for macro path config."""

    @pytest.mark.requirement("AC-36.2")
    def test_references_dbt_project_yml(self, retention_test_source: str) -> None:
        """Source must reference ``dbt_project.yml`` to read macro-paths config.

        Without reading the dbt project config, the test cannot know where
        macros are actually located (they may be at ``../macros`` or any
        other relative path).
        """
        assert "dbt_project.yml" in retention_test_source, (
            "test_data_retention_enforcement does not reference 'dbt_project.yml'. "
            "It must read the dbt project config to discover macro-paths."
        )

    @pytest.mark.requirement("AC-36.2")
    def test_parses_dbt_project_yaml_not_just_floe(self, retention_test_source: str) -> None:
        """Source must parse dbt_project.yml YAML, not just floe.yaml.

        The current broken code uses yaml.safe_load only for floe.yaml.
        A correct implementation must ALSO load dbt_project.yml to extract
        macro-paths. We verify that dbt_project.yml is referenced AND that
        yaml.safe_load is used in proximity (both must appear, and specifically
        the dbt_project.yml content must be parsed).
        """
        # Both conditions required: references dbt_project.yml AND parses it
        has_dbt_project_ref = bool(re.search(r"dbt_project\.yml", retention_test_source))
        has_yaml_load = bool(re.search(r"yaml\.safe_load|yaml\.load", retention_test_source))
        # The fix must read dbt_project.yml AND parse it. If it only has
        # yaml.safe_load for floe.yaml but no dbt_project.yml reference,
        # this test fails.
        assert has_dbt_project_ref and has_yaml_load, (
            "test_data_retention_enforcement must read AND parse dbt_project.yml "
            "to extract macro-paths. "
            f"Found dbt_project.yml reference: {has_dbt_project_ref}, "
            f"found yaml.safe_load: {has_yaml_load}. Both are required."
        )


class TestExtractsMacroPaths:
    """Verify the test extracts macro-paths from the parsed dbt project config."""

    @pytest.mark.requirement("AC-36.2")
    def test_accesses_macro_paths_key(self, retention_test_source: str) -> None:
        """Source must access ``macro-paths`` or ``macro_paths`` from parsed config.

        The dbt_project.yml uses ``macro-paths`` as the key for macro
        directories. The test must extract this value to know where to search.
        """
        # Accept both hyphenated (YAML key) and underscored (Python variable)
        has_macro_paths_access = bool(re.search(r"macro[-_]paths", retention_test_source))
        assert has_macro_paths_access, (
            "test_data_retention_enforcement does not access 'macro-paths' "
            "or 'macro_paths' from the parsed config. It must extract the "
            "macro-paths list from dbt_project.yml to resolve macro directories."
        )


class TestResolvesRelativePaths:
    """Verify the test resolves relative paths like ``../macros``."""

    @pytest.mark.requirement("AC-36.2")
    def test_uses_path_resolve(self, retention_test_source: str) -> None:
        """Source must use ``Path.resolve()`` or equivalent for relative path handling.

        The demo project uses ``macro-paths: ["../macros"]``, which is
        relative to the dbt project directory. Without ``resolve()`` (or
        equivalent normalization), ``..`` segments would not be handled
        correctly, and the resolved path could be wrong or non-existent.
        """
        # Accept .resolve() or os.path.realpath or os.path.abspath
        has_resolve = bool(
            re.search(
                r"\.resolve\(\)|os\.path\.realpath|os\.path\.abspath",
                retention_test_source,
            )
        )
        assert has_resolve, (
            "test_data_retention_enforcement does not use .resolve() or "
            "equivalent path normalization. Relative macro-paths like "
            "'../macros' require Path.resolve() to produce correct absolute paths."
        )


class TestIteratesAllMacroPaths:
    """Verify the test iterates ALL macro-paths entries, not just one."""

    @pytest.mark.requirement("AC-36.2")
    def test_loops_over_macro_paths_not_just_files(self, retention_test_source: str) -> None:
        """Source must iterate over macro PATH entries, not just macro files.

        ``macro-paths`` is a list (e.g., ``["../macros", "project_macros"]``).
        The test must check ALL path entries, not just ``macro_paths[0]``.

        The broken code has ``for macro_file in macros_dir.glob(...)`` which
        iterates files within ONE hardcoded directory. The fix must iterate
        over the macro-paths LIST itself. We distinguish these by requiring
        both: (a) access to macro-paths/macro_paths, and (b) a for loop
        that iterates over that variable.
        """
        # Must reference macro-paths or macro_paths (the config key/variable)
        has_macro_paths_var = bool(re.search(r"macro[-_]paths", retention_test_source))
        # Must have a for loop iterating over the paths list.
        # Patterns we accept:
        #   for macro_path in macro_paths:
        #   for mp in macro_paths:
        #   for p in dbt_config.get("macro-paths", ...):
        #   for macro_dir in macro_paths:
        # We require the loop variable to NOT be "macro_file" (that's the
        # old pattern iterating files within a single dir).
        has_path_iteration_loop = bool(
            re.search(
                r"for\s+(?!macro_file)\w+\s+in\s+\S*macro[-_]paths",
                retention_test_source,
            )
        )
        # Also reject hardcoded index access like macro_paths[0]
        has_single_index = bool(re.search(r"macro.*paths\[0\]", retention_test_source))

        assert has_macro_paths_var and has_path_iteration_loop, (
            "test_data_retention_enforcement must iterate over the macro-paths "
            "list from dbt_project.yml config (not just glob files within a "
            "single hardcoded directory). Expected a loop like "
            "'for macro_path in macro_paths:'. "
            f"Found macro_paths variable: {has_macro_paths_var}, "
            f"found path iteration loop: {has_path_iteration_loop}"
        )
        assert not has_single_index, (
            "test_data_retention_enforcement uses macro_paths[0] to access "
            "only the first entry. It must iterate ALL entries in the list."
        )


class TestRetentionMacroSearch:
    """Verify the test still searches .sql files for retention/expire keywords."""

    @pytest.mark.requirement("AC-36.2")
    def test_searches_sql_files_for_retention_keywords(self, retention_test_source: str) -> None:
        """Source must search ``.sql`` files for retention or expire keywords.

        The macro resolution change must not break the actual macro content
        search. The test should still glob for ``*.sql`` files and check
        their content for retention-related keywords.
        """
        has_sql_glob = bool(re.search(r"\.glob\([^)]*\.sql", retention_test_source))
        has_retention_keyword_search = bool(
            re.search(r'["\']retention["\']', retention_test_source)
        )
        has_expire_keyword_search = bool(re.search(r'["\']expire["\']', retention_test_source))

        assert has_sql_glob, (
            "test_data_retention_enforcement must glob for .sql files to find retention macros."
        )
        assert has_retention_keyword_search or has_expire_keyword_search, (
            "test_data_retention_enforcement must search for 'retention' "
            "or 'expire' keywords in macro .sql files."
        )
