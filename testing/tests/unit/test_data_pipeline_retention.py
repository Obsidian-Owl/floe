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

import re
from pathlib import Path

import pytest

from testing.fixtures.source_parsing import get_function_source, strip_comments_and_docstrings

REPO_ROOT = Path(__file__).resolve().parents[3]
E2E_TEST_FILE = REPO_ROOT / "tests" / "e2e" / "test_data_pipeline.py"


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
    return get_function_source(E2E_TEST_FILE, "test_snapshot_expiry_enforcement")


@pytest.fixture(scope="module")
def snapshot_expiry_code(snapshot_expiry_source: str) -> str:
    """Executable code only (no comments/docstrings) from snapshot_expiry_enforcement.

    This fixture strips comments and docstrings so that structural tests
    validate actual code, not comments a lazy implementer might add.

    Returns:
        Source text with comments and docstrings removed.
    """
    return strip_comments_and_docstrings(snapshot_expiry_source)


@pytest.fixture(scope="module")
def data_retention_source() -> str:
    """Source text of test_data_retention_enforcement from the E2E file.

    Returns:
        The complete source text of the function.
    """
    assert E2E_TEST_FILE.exists(), (
        f"E2E test file not found at {E2E_TEST_FILE}. "
        "Cannot validate retention config location without the source."
    )
    return get_function_source(E2E_TEST_FILE, "test_data_retention_enforcement")


@pytest.fixture(scope="module")
def data_retention_code(data_retention_source: str) -> str:
    """Executable code only (no comments/docstrings) from test_data_retention_enforcement.

    Returns:
        Source text with comments and docstrings removed.
    """
    return strip_comments_and_docstrings(data_retention_source)


class TestReferencesManifestYaml:
    """Verify the test references manifest.yaml for retention configuration."""

    @pytest.mark.requirement("AC-36.3")
    def test_source_contains_manifest_yaml_reference(self, snapshot_expiry_code: str) -> None:
        """Executable code must reference ``manifest.yaml`` to read retention config.

        The retention configuration (``data_retention_days: 1``) lives in
        ``demo/manifest.yaml``, not in ``floe.yaml``. The test must reference
        manifest.yaml in executable code (not just in a comment or docstring).
        """
        manifest_pattern = r"manifest\.yaml|manifest_yaml|manifest_config|manifest_path"
        has_manifest_ref = bool(re.search(manifest_pattern, snapshot_expiry_code))
        assert has_manifest_ref, (
            "test_snapshot_expiry_enforcement does not reference 'manifest.yaml' "
            "(or manifest_yaml/manifest_config/manifest_path variable) "
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
        # against a variable loaded exclusively from floe.yaml.
        # Uses per-line matching (no DOTALL) to avoid false positives from
        # unrelated uses of floe_config and retention on distant lines.
        broken_floe_only_pattern = any(
            re.search(r"floe_config.*(?:retention|snapshot|expiry)", line)
            for line in snapshot_expiry_code.splitlines()
        )

        # Unconditionally require manifest-based retention checking in code.
        # Uses per-line matching to ensure manifest and retention co-occur
        # on the same line or in adjacent variable usage (not distant lines).
        has_manifest_based_check = any(
            re.search(r"manifest.*(?:retention|data_retention)", line)
            for line in snapshot_expiry_code.splitlines()
        )
        # Also accept structured access pattern across lines:
        # manifest_config.get("governance", {}).get("data_retention_days")
        if not has_manifest_based_check:
            has_manifest_based_check = (
                "manifest_config" in snapshot_expiry_code
                and "data_retention_days" in snapshot_expiry_code
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


class TestDataRetentionEnforcementPattern:
    """Validate test_data_retention_enforcement does not solely use floe.yaml string search.

    The ``test_data_retention_enforcement`` function has the same broken pattern
    as ``test_snapshot_expiry_enforcement``: it checks
    ``"retention" in str(floe_config).lower()`` against floe.yaml where no
    retention keywords exist. The test passes incidentally because the macro
    fallback (Test 2) finds retention macros. But the floe.yaml string search
    (Test 1) is dead code that always evaluates to False.

    These tests guard against regression — ensuring that if the macro fallback
    is ever removed, the floe.yaml pattern is not the sole retention check.
    """

    @pytest.mark.requirement("AC-36.3")
    def test_data_retention_has_non_floe_yaml_retention_check(
        self, data_retention_code: str
    ) -> None:
        """test_data_retention_enforcement must not solely rely on floe.yaml for retention.

        The function uses ``"retention" in str(floe_config).lower()`` which
        always returns False for customer-360's floe.yaml. The macro path
        fallback saves it, but the primary retention check is dead code.
        This test ensures at least one non-floe_config retention mechanism
        exists in executable code (e.g., dbt macro search or manifest.yaml).
        """
        # The macro-based retention search is the valid fallback
        has_macro_retention = bool(
            re.search(r"retention_macro_found|macro.*retention", data_retention_code)
        )
        # Or a manifest-based check (if refactored in future)
        has_manifest_check = bool(
            re.search(r"manifest.*retention|data_retention_days", data_retention_code)
        )

        assert has_macro_retention or has_manifest_check, (
            "test_data_retention_enforcement has no valid retention check beyond "
            "the broken 'retention in str(floe_config).lower()' pattern. "
            "It needs either a dbt macro search or manifest.yaml check."
        )

    @pytest.mark.requirement("AC-36.3")
    def test_data_retention_not_solely_floe_config_string_search(
        self, data_retention_code: str
    ) -> None:
        """The floe_config string search must NOT be the sole retention assertion.

        The broken pattern:
            has_retention_config = "retention" in str(floe_config).lower()
            assert has_retention_config  # <-- sole assertion, always False

        A correct implementation must have an alternative path (macro search
        or manifest check) that makes the final assertion pass independently
        of the floe_config string search.
        """
        # Check if the final assertion uses `or` with an alternative
        has_or_fallback = bool(
            re.search(
                r"assert\s+.*has_retention_config\s+or\s+\w+",
                data_retention_code,
            )
        )
        # Or the assertion doesn't reference has_retention_config at all
        # (meaning floe_config check was removed entirely)
        no_sole_floe_assertion = not bool(
            re.search(
                r"assert\s+has_retention_config\s*[,\n]",
                data_retention_code,
            )
        )

        assert has_or_fallback or no_sole_floe_assertion, (
            "test_data_retention_enforcement asserts 'has_retention_config' "
            "(from floe.yaml string search) as the sole condition. "
            "This always fails for customer-360. The assertion must include "
            "an alternative (e.g., 'assert has_retention_config or retention_macro_found')."
        )
