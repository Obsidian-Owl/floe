"""Structural validation: test_snapshot_expiry_enforcement retention config location.

Tests that the E2E test ``test_snapshot_expiry_enforcement`` in
``tests/e2e/test_data_pipeline.py`` checks for retention configuration in
``manifest.yaml`` (where ``data_retention_days: 1`` actually lives) instead
of asserting retention config exists in ``floe.yaml`` (where it does not).

AC-36.3: The test MUST:
  - Reference ``manifest.yaml`` for retention configuration
  - Parse manifest.yaml via ``yaml.safe_load``
  - Check for ``data_retention_days`` in the parsed manifest
  - NOT solely depend on floe.yaml for the retention assertion
  - Preserve Test 1 (values-demo.yaml snapshot check) intact

These are structural (source-parsing) tests. They inspect the Python source
of the function under test. They do NOT import or execute the E2E test.

Requirements:
    AC-36.3: Retention config location in manifest.yaml
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_TEST_FILE = REPO_ROOT / "tests" / "e2e" / "test_data_pipeline.py"


def _get_function_source(file_path: Path, func_name: str) -> str:
    """Extract the source text of a specific method from a Python file.

    Parses the file's AST, locates the function/method by name, and returns
    its raw source lines. Works for methods nested inside classes.

    Args:
        file_path: Path to the Python source file.
        func_name: Name of the function or method to extract.

    Returns:
        The raw source text of the function body.

    Raises:
        ValueError: If the function is not found in the file.
    """
    source = file_path.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                lines = source.splitlines()
                # node.lineno is 1-based, node.end_lineno is inclusive
                start = node.lineno - 1
                end = node.end_lineno if node.end_lineno else start + 1
                return "\n".join(lines[start:end])

    msg = f"Function {func_name!r} not found in {file_path}"
    raise ValueError(msg)


def _strip_comments_and_docstrings(source: str) -> str:
    """Remove comments and docstrings from Python source, leaving only executable code.

    This prevents a lazy implementer from passing structural tests by adding
    keywords in a comment (e.g., ``# TODO: check manifest.yaml data_retention_days``)
    without actually writing the code.

    Args:
        source: Raw Python source text.

    Returns:
        Source with comments and docstrings removed.
    """
    # Remove single-line comments (# ...)
    code_lines: list[str] = []
    for line in source.splitlines():
        # Strip inline comments but preserve strings containing #
        # Simple heuristic: remove everything after # that isn't inside quotes
        stripped = re.sub(r'#[^"\']*$', "", line)
        code_lines.append(stripped)
    code = "\n".join(code_lines)

    # Remove triple-quoted strings (docstrings)
    code = re.sub(r'"""[\s\S]*?"""', '""""""', code)
    code = re.sub(r"'''[\s\S]*?'''", "''''''", code)

    return code


@pytest.fixture(scope="module")
def snapshot_expiry_source() -> str:
    """Source text of test_snapshot_expiry_enforcement from the E2E file.

    Returns:
        The complete source text of the function.
    """
    assert E2E_TEST_FILE.exists(), (
        f"E2E test file not found at {E2E_TEST_FILE}. "
        "Cannot validate retention config location without the source."
    )
    return _get_function_source(E2E_TEST_FILE, "test_snapshot_expiry_enforcement")


@pytest.fixture(scope="module")
def snapshot_expiry_code(snapshot_expiry_source: str) -> str:
    """Executable code only (no comments/docstrings) from snapshot_expiry_enforcement.

    This fixture strips comments and docstrings so that structural tests
    validate actual code, not comments a lazy implementer might add.

    Returns:
        Source text with comments and docstrings removed.
    """
    return _strip_comments_and_docstrings(snapshot_expiry_source)


class TestReferencesManifestYaml:
    """Verify the test references manifest.yaml for retention configuration."""

    @pytest.mark.requirement("AC-36.3")
    def test_source_contains_manifest_yaml_reference(self, snapshot_expiry_code: str) -> None:
        """Executable code must reference ``manifest.yaml`` to read retention config.

        The retention configuration (``data_retention_days: 1``) lives in
        ``demo/manifest.yaml``, not in ``floe.yaml``. The test must reference
        manifest.yaml in executable code (not just in a comment or docstring).
        """
        has_manifest_ref = bool(re.search(r"manifest\.yaml|manifest", snapshot_expiry_code))
        assert has_manifest_ref, (
            "test_snapshot_expiry_enforcement does not reference 'manifest.yaml' "
            "in executable code (comments and docstrings excluded). "
            "Retention config (data_retention_days) is in manifest.yaml, not floe.yaml."
        )


class TestParsesManifestConfig:
    """Verify the test parses manifest.yaml and extracts retention config."""

    @pytest.mark.requirement("AC-36.3")
    def test_reads_and_parses_manifest_yaml(self, snapshot_expiry_code: str) -> None:
        """Executable code must read manifest.yaml AND parse it with yaml.safe_load.

        The test must load the manifest file content and parse it as YAML
        to access the ``data_retention_days`` field. A simple string search
        of floe.yaml is not acceptable. Comments and docstrings are excluded
        to prevent passing via ``# check manifest.yaml``.
        """
        has_manifest_ref = bool(re.search(r"manifest\.yaml", snapshot_expiry_code))
        has_yaml_load = bool(re.search(r"yaml\.safe_load", snapshot_expiry_code))

        assert has_manifest_ref and has_yaml_load, (
            "test_snapshot_expiry_enforcement must reference manifest.yaml AND "
            "parse it with yaml.safe_load in executable code. "
            f"Found manifest.yaml reference: {has_manifest_ref}, "
            f"found yaml.safe_load: {has_yaml_load}. Both are required."
        )

    @pytest.mark.requirement("AC-36.3")
    def test_checks_data_retention_days_in_manifest(self, snapshot_expiry_code: str) -> None:
        """Executable code must check for ``data_retention_days`` in manifest config.

        The manifest.yaml has ``data_retention_days: 1`` under the governance
        section. The test must access this specific field in executable code,
        not do a vague string search for "retention" in the stringified config.
        Comments and docstrings are excluded to prevent passing via a TODO comment.
        """
        has_data_retention_days = bool(re.search(r"data_retention_days", snapshot_expiry_code))
        assert has_data_retention_days, (
            "test_snapshot_expiry_enforcement does not check for "
            "'data_retention_days' in executable code. "
            "The manifest.yaml governance section contains "
            "'data_retention_days: 1' which must be explicitly verified."
        )


class TestDoesNotSolelyCheckFloeYaml:
    """Verify the retention assertion does NOT solely depend on floe.yaml."""

    @pytest.mark.requirement("AC-36.3")
    def test_retention_check_not_against_floe_yaml_only(self, snapshot_expiry_code: str) -> None:
        """The retention assertion must NOT check only floe.yaml.

        The broken code searches for "retention" / "snapshot" / "expiry"
        as substrings within str(floe_config). This pattern:
          1. Checks floe.yaml (which has no retention config)
          2. Uses vague string matching (str(config).lower())
          3. Fails because none of those keywords appear in floe.yaml

        The fix must check manifest.yaml instead. This test catches the
        specific broken pattern: a retention assertion whose only config
        source variable comes from reading floe.yaml. It also unconditionally
        requires manifest-based retention checking in executable code.
        """
        # Detect the broken pattern: retention/snapshot/expiry keywords checked
        # against a variable loaded exclusively from floe.yaml
        broken_floe_only_pattern = bool(
            re.search(
                r"floe_config.*(?:retention|snapshot|expiry)",
                snapshot_expiry_code,
                re.DOTALL,
            )
        )

        # Unconditionally require manifest-based retention checking in code
        has_manifest_based_check = bool(
            re.search(
                r"manifest.*(?:retention|data_retention)",
                snapshot_expiry_code,
                re.DOTALL,
            )
        )

        if broken_floe_only_pattern:
            assert has_manifest_based_check, (
                "test_snapshot_expiry_enforcement checks retention keywords against "
                "floe_config (loaded from floe.yaml) but does NOT check manifest.yaml. "
                "Retention config (data_retention_days) is in manifest.yaml, not floe.yaml. "
                "The retention assertion must use manifest config, not floe config."
            )
        else:
            # Even if the floe_config pattern was removed, manifest must be used
            assert has_manifest_based_check, (
                "test_snapshot_expiry_enforcement does not have manifest-based "
                "retention checking in executable code. The retention config "
                "(data_retention_days) lives in manifest.yaml and must be "
                "verified from there."
            )


class TestPreservesValuesDemo:
    """Verify Test 1 (values-demo.yaml snapshot check) is still intact."""

    @pytest.mark.requirement("AC-36.3")
    def test_values_demo_snapshot_check_preserved(self, snapshot_expiry_source: str) -> None:
        """Test 1 must still verify values-demo.yaml has snapshot configuration.

        The fix for AC-36.3 only changes Test 2 (retention config source).
        Test 1 -- which checks values-demo.yaml for snapshotKeepLast or
        similar snapshot configuration -- must remain intact.
        """
        has_values_demo_path = bool(re.search(r"values-demo\.yaml", snapshot_expiry_source))
        has_snapshot_keep_last = bool(re.search(r"snapshotKeepLast", snapshot_expiry_source))

        assert has_values_demo_path, (
            "test_snapshot_expiry_enforcement no longer references "
            "'values-demo.yaml'. Test 1 (snapshot config in demo values) "
            "must be preserved."
        )
        assert has_snapshot_keep_last, (
            "test_snapshot_expiry_enforcement no longer checks for "
            "'snapshotKeepLast'. Test 1 (snapshot config in demo values) "
            "must be preserved."
        )


class TestNoVagueStringSearch:
    """Verify the retention check uses structured access, not vague string matching."""

    @pytest.mark.requirement("AC-36.3")
    def test_no_stringified_config_retention_search(self, snapshot_expiry_source: str) -> None:
        """Retention must NOT be checked via ``"retention" in str(config).lower()``.

        The broken code converts the entire config dict to a string and checks
        for substring presence. This is fragile: it would match a key like
        "retention_policy_description" or even the word "retention" in a
        comment that happens to be in the YAML. The fix should access the
        parsed config structurally (e.g., ``config["governance"]["data_retention_days"]``
        or ``config.get("governance", {}).get("data_retention_days")``).

        This test specifically rejects the pattern:
            ``"retention" in str(some_var).lower()``
        when that variable is loaded from manifest.yaml. The broken code
        already uses this pattern against floe_config; a naive "fix" might
        just change the variable name from floe_config to manifest_config
        while keeping the same vague string search.
        """
        # Detect the vague pattern: '"retention" in str(X).lower()'
        # or '"snapshot" in str(X).lower()' or '"expiry" in str(X).lower()'
        # applied to the manifest config variable
        vague_manifest_pattern = bool(
            re.search(
                r"""["'](?:retention|expiry)["']\s+in\s+str\(.*manifest""",
                snapshot_expiry_source,
            )
        )
        assert not vague_manifest_pattern, (
            "test_snapshot_expiry_enforcement uses a vague "
            "'\"retention\" in str(manifest_config).lower()' pattern. "
            "This is the same broken approach as before, just pointed at a "
            "different file. Use structured access like "
            "manifest_config['governance']['data_retention_days'] instead."
        )
