"""Static analysis tests for test-e2e.sh manifest config wiring (AC-2).

This test suite verifies that test-e2e.sh sources the manifest extractor
and uses its output as defaults instead of hardcoded values. Tests read the
script as text and check for required patterns.

This test suite covers:
- AC-2.1: eval line exists sourcing extract-manifest-config.py
- AC-2.2: MINIO_BUCKET defaults to ${MANIFEST_BUCKET}
- AC-2.3: POLARIS_CATALOG defaults to ${MANIFEST_WAREHOUSE}
- AC-2.4: POLARIS_CLIENT_ID defaults to ${MANIFEST_OAUTH_CLIENT_ID}
- AC-2.5: Catalog JSON uses MANIFEST_REGION (not hardcoded 'us-east-1')
- AC-2.6: Catalog JSON uses MANIFEST_PATH_STYLE_ACCESS (not hardcoded 'true')
- AC-2.7: No remaining hardcoded defaults for replaced values
- AC-2.8: Env var override pattern preserved

Done when all fail before implementation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load script content once
# ---------------------------------------------------------------------------
SCRIPT_PATH: Path = Path(__file__).parent.parent / "test-e2e.sh"
_script_content: str = SCRIPT_PATH.read_text()
_script_lines: list[str] = _script_content.splitlines()


def _find_line_index(pattern: str) -> int | None:
    """Return the 0-based index of the first line matching regex pattern."""
    regex = re.compile(pattern)
    for i, line in enumerate(_script_lines):
        if regex.search(line):
            return i
    return None


def _find_all_lines(pattern: str) -> list[tuple[int, str]]:
    """Return all (0-based index, line) tuples matching regex pattern."""
    regex = re.compile(pattern)
    return [(i, line) for i, line in enumerate(_script_lines) if regex.search(line)]


# ---------------------------------------------------------------------------
# AC-2.1: eval line exists after SCRIPT_DIR detection
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-002")
class TestEvalManifestExtractorPresent:
    """Verify test-e2e.sh evals the manifest extractor early in execution."""

    def test_eval_line_exists(self) -> None:
        """Script must contain an eval line that runs extract-manifest-config.py.

        The exact pattern: eval "$(python3 ... extract-manifest-config.py ...)"
        or eval "$(uv run python3 ... extract-manifest-config.py ...)".
        """
        eval_pattern = r'eval\s+"\$\(.*python3?\s+.*extract-manifest-config\.py'
        match = _find_line_index(eval_pattern)
        assert match is not None, (
            "test-e2e.sh must contain an eval line that sources extract-manifest-config.py output"
        )

    def test_eval_line_after_script_dir(self) -> None:
        """The eval must appear after SCRIPT_DIR is set (needs SCRIPT_DIR for path).

        This prevents the eval from referencing SCRIPT_DIR before it is defined.
        """
        script_dir_idx = _find_line_index(r"SCRIPT_DIR=")
        assert script_dir_idx is not None, "SCRIPT_DIR assignment must exist"

        eval_pattern = r'eval\s+"\$\(.*extract-manifest-config\.py'
        eval_idx = _find_line_index(eval_pattern)
        assert eval_idx is not None, "eval line must exist"
        assert eval_idx > script_dir_idx, (
            f"eval line (line {eval_idx + 1}) must appear after "
            f"SCRIPT_DIR (line {script_dir_idx + 1})"
        )

    def test_eval_line_before_minio_bucket(self) -> None:
        """The eval must appear before MINIO_BUCKET is set (provides defaults)."""
        eval_pattern = r'eval\s+"\$\(.*extract-manifest-config\.py'
        eval_idx = _find_line_index(eval_pattern)
        assert eval_idx is not None, "eval line must exist"

        bucket_idx = _find_line_index(r"MINIO_BUCKET=")
        assert bucket_idx is not None, "MINIO_BUCKET assignment must exist"
        assert eval_idx < bucket_idx, (
            f"eval line (line {eval_idx + 1}) must appear before "
            f"MINIO_BUCKET (line {bucket_idx + 1}) so defaults are available"
        )


# ---------------------------------------------------------------------------
# AC-2.2: MINIO_BUCKET defaults to ${MANIFEST_BUCKET}
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-002")
class TestMinioBucketDefault:
    """Verify MINIO_BUCKET uses manifest-derived default."""

    def test_minio_bucket_uses_manifest_bucket(self) -> None:
        """MINIO_BUCKET default must reference MANIFEST_BUCKET variable.

        Expected pattern: MINIO_BUCKET="${MINIO_BUCKET:-${MANIFEST_BUCKET}}"
        or equivalent.
        """
        pattern = r"MINIO_BUCKET=.*\$\{MINIO_BUCKET:-\$\{?MANIFEST_BUCKET\}?"
        match = _find_line_index(pattern)
        assert match is not None, (
            "MINIO_BUCKET must default to ${MANIFEST_BUCKET}, not a hardcoded value"
        )

    def test_minio_bucket_not_hardcoded_floe_iceberg(self) -> None:
        """MINIO_BUCKET must NOT use 'floe-iceberg' as its default.

        The old pattern MINIO_BUCKET="${MINIO_BUCKET:-floe-iceberg}"
        must be replaced.
        """
        pattern = r"MINIO_BUCKET=.*:-floe-iceberg"
        match = _find_line_index(pattern)
        assert match is None, (
            f"MINIO_BUCKET still uses hardcoded 'floe-iceberg' as default "
            f"(line {match + 1 if match is not None else '?'}). "
            "Must use ${MANIFEST_BUCKET} instead."
        )


# ---------------------------------------------------------------------------
# AC-2.3: POLARIS_CATALOG defaults to ${MANIFEST_WAREHOUSE}
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-002")
class TestPolarisCatalogDefault:
    """Verify POLARIS_CATALOG uses manifest-derived default."""

    def test_polaris_catalog_uses_manifest_warehouse(self) -> None:
        """POLARIS_CATALOG default must reference MANIFEST_WAREHOUSE variable."""
        pattern = r"POLARIS_CATALOG=.*\$\{POLARIS_CATALOG:-\$\{?MANIFEST_WAREHOUSE\}?"
        match = _find_line_index(pattern)
        assert match is not None, (
            "POLARIS_CATALOG must default to ${MANIFEST_WAREHOUSE}, not a hardcoded value"
        )

    def test_polaris_catalog_not_hardcoded_floe_e2e(self) -> None:
        """POLARIS_CATALOG must NOT use 'floe-e2e' as its default."""
        pattern = r"POLARIS_CATALOG=.*:-floe-e2e"
        match = _find_line_index(pattern)
        assert match is None, (
            f"POLARIS_CATALOG still uses hardcoded 'floe-e2e' as default "
            f"(line {match + 1 if match is not None else '?'}). "
            "Must use ${MANIFEST_WAREHOUSE} instead."
        )


# ---------------------------------------------------------------------------
# AC-2.4: POLARIS_CLIENT_ID defaults to ${MANIFEST_OAUTH_CLIENT_ID}
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-002")
class TestPolarisClientIdDefault:
    """Verify POLARIS_CLIENT_ID uses manifest-derived default."""

    def test_polaris_client_id_uses_manifest_var(self) -> None:
        """POLARIS_CLIENT_ID default must reference MANIFEST_OAUTH_CLIENT_ID."""
        pattern = r"POLARIS_CLIENT_ID=.*\$\{POLARIS_CLIENT_ID:-\$\{?MANIFEST_OAUTH_CLIENT_ID\}?"
        match = _find_line_index(pattern)
        assert match is not None, (
            "POLARIS_CLIENT_ID must default to ${MANIFEST_OAUTH_CLIENT_ID}, not a hardcoded value"
        )

    def test_polaris_client_id_not_hardcoded_demo_admin(self) -> None:
        """POLARIS_CLIENT_ID must NOT use 'demo-admin' as its default."""
        pattern = r"POLARIS_CLIENT_ID=.*:-demo-admin"
        match = _find_line_index(pattern)
        assert match is None, (
            f"POLARIS_CLIENT_ID still uses hardcoded 'demo-admin' as default "
            f"(line {match + 1 if match is not None else '?'}). "
            "Must use ${MANIFEST_OAUTH_CLIENT_ID} instead."
        )


# ---------------------------------------------------------------------------
# AC-2.5: Catalog JSON uses MANIFEST_REGION (not hardcoded 'us-east-1')
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-002")
class TestCatalogJsonRegion:
    """Verify catalog creation JSON uses MANIFEST_REGION env var."""

    def test_catalog_json_references_manifest_region(self) -> None:
        """The catalog creation Python snippet must read MANIFEST_REGION.

        It should use os.environ.get('MANIFEST_REGION', ...) or similar,
        not a hardcoded 'us-east-1' literal.
        """
        # Find the catalog JSON creation block (python3 -c "..." that builds
        # the catalog payload)
        catalog_block_start = _find_line_index(r"CATALOG_JSON=.*python3\s+-c")
        assert catalog_block_start is not None, "Could not find CATALOG_JSON python3 -c block"

        # Extract the block: from CATALOG_JSON= to the closing quote
        # Look for MANIFEST_REGION reference in that block
        block_lines: list[str] = []
        for line in _script_lines[catalog_block_start:]:
            block_lines.append(line)
            # The block ends with the closing of the python inline script
            if line.strip().startswith('"') and "POLARIS_CATALOG" in line:
                break
            if line.strip() == '")':
                break

        block_text = "\n".join(block_lines)
        assert "MANIFEST_REGION" in block_text, (
            "Catalog creation JSON must reference MANIFEST_REGION env var. "
            "Found hardcoded values instead."
        )

    def test_catalog_json_no_hardcoded_region_in_properties(self) -> None:
        """The catalog properties must NOT have hardcoded 'us-east-1'.

        Both 's3.region' and 'table-default.s3.region' must use the
        MANIFEST_REGION variable.
        """
        catalog_block_start = _find_line_index(r"CATALOG_JSON=.*python3\s+-c")
        assert catalog_block_start is not None

        # Collect all lines in the catalog JSON block that set region
        region_lines = []
        in_block = False
        for i, line in enumerate(_script_lines[catalog_block_start:], start=catalog_block_start):
            if i == catalog_block_start:
                in_block = True
            if in_block:
                if "'s3.region'" in line or "'table-default.s3.region'" in line:
                    region_lines.append((i + 1, line.strip()))
                # End of the inline python block
                if line.strip().startswith('"') and i > catalog_block_start + 5:
                    break

        # Each region line must NOT contain the literal 'us-east-1'
        for lineno, line_text in region_lines:
            assert "us-east-1" not in line_text, (
                f"Line {lineno} has hardcoded 'us-east-1': {line_text!r}. "
                "Must use MANIFEST_REGION env var."
            )

    def test_storage_config_no_hardcoded_region(self) -> None:
        """storageConfigInfo.region must NOT use hardcoded 'us-east-1'.

        The storageConfigInfo block also has a 'region' field that must
        use the MANIFEST_REGION variable.
        """
        catalog_block_start = _find_line_index(r"CATALOG_JSON=.*python3\s+-c")
        assert catalog_block_start is not None

        # Find the storageConfigInfo section
        storage_lines = []
        in_storage = False
        for i, line in enumerate(_script_lines[catalog_block_start:], start=catalog_block_start):
            if "storageConfigInfo" in line:
                in_storage = True
            if in_storage:
                storage_lines.append((i + 1, line.strip()))
                if line.strip().startswith("}"):
                    break

        region_hardcoded = any(
            "'region'" in text and "us-east-1" in text for _, text in storage_lines
        )
        assert not region_hardcoded, (
            "storageConfigInfo.region has hardcoded 'us-east-1'. Must use MANIFEST_REGION env var."
        )


# ---------------------------------------------------------------------------
# AC-2.6: Catalog JSON uses MANIFEST_PATH_STYLE_ACCESS
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-002")
class TestCatalogJsonPathStyleAccess:
    """Verify catalog creation JSON uses MANIFEST_PATH_STYLE_ACCESS env var."""

    def test_catalog_json_references_manifest_path_style(self) -> None:
        """The catalog creation block must read MANIFEST_PATH_STYLE_ACCESS."""
        catalog_block_start = _find_line_index(r"CATALOG_JSON=.*python3\s+-c")
        assert catalog_block_start is not None

        block_lines: list[str] = []
        for line in _script_lines[catalog_block_start:]:
            block_lines.append(line)
            if line.strip().startswith('"') and "POLARIS_CATALOG" in line:
                break
            if line.strip() == '")':
                break

        block_text = "\n".join(block_lines)
        assert "MANIFEST_PATH_STYLE_ACCESS" in block_text, (
            "Catalog creation JSON must reference MANIFEST_PATH_STYLE_ACCESS "
            "env var. Found hardcoded values instead."
        )

    def test_path_style_properties_not_hardcoded(self) -> None:
        """'s3.path-style-access' must NOT be hardcoded to 'true'.

        Both 's3.path-style-access' and 'table-default.s3.path-style-access'
        must use the MANIFEST_PATH_STYLE_ACCESS variable.
        """
        catalog_block_start = _find_line_index(r"CATALOG_JSON=.*python3\s+-c")
        assert catalog_block_start is not None

        path_style_lines = []
        for i, line in enumerate(_script_lines[catalog_block_start:], start=catalog_block_start):
            stripped = line.strip()
            if "path-style-access" in stripped and "'" in stripped:
                # Check if this is a property line with a hardcoded value
                # Pattern: 's3.path-style-access': 'true'
                if re.search(r"'.*path-style-access':\s*'true'", stripped):
                    path_style_lines.append((i + 1, stripped))
            # End of block
            if stripped.startswith('"') and i > catalog_block_start + 5:
                break

        assert len(path_style_lines) == 0, (
            f"Found {len(path_style_lines)} hardcoded path-style-access='true' "
            f"line(s): {path_style_lines}. Must use MANIFEST_PATH_STYLE_ACCESS."
        )

    def test_storage_config_path_style_not_hardcoded(self) -> None:
        """storageConfigInfo.pathStyleAccess must NOT use hardcoded True.

        Must reference MANIFEST_PATH_STYLE_ACCESS.
        """
        catalog_block_start = _find_line_index(r"CATALOG_JSON=.*python3\s+-c")
        assert catalog_block_start is not None

        in_storage = False
        for i, line in enumerate(_script_lines[catalog_block_start:], start=catalog_block_start):
            if "storageConfigInfo" in line:
                in_storage = True
            if in_storage and "pathStyleAccess" in line:
                # Check for hardcoded True (Python boolean)
                if re.search(r"'pathStyleAccess':\s*True\b", line):
                    pytest.fail(
                        f"Line {i + 1}: storageConfigInfo.pathStyleAccess is "
                        f"hardcoded to True. Must use MANIFEST_PATH_STYLE_ACCESS."
                    )
                break


# ---------------------------------------------------------------------------
# AC-2.7: No remaining hardcoded defaults
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-002")
class TestNoRemainingHardcodedDefaults:
    """Verify old hardcoded defaults are fully replaced."""

    def test_no_floe_iceberg_as_default_value(self) -> None:
        """'floe-iceberg' must not appear as a bash default value.

        It may appear in comments or log messages, but not in
        ${VAR:-floe-iceberg} patterns.
        """
        # Match bash default-value syntax: :-floe-iceberg
        pattern = r':-floe-iceberg["\}]'
        matches = _find_all_lines(pattern)
        assert len(matches) == 0, (
            f"Found 'floe-iceberg' used as default value in "
            f"{len(matches)} location(s): "
            f"{[(m[0] + 1, m[1].strip()) for m in matches]}"
        )

    def test_no_floe_e2e_as_default_value(self) -> None:
        """'floe-e2e' must not appear as a bash default value."""
        pattern = r':-floe-e2e["\}]'
        matches = _find_all_lines(pattern)
        assert len(matches) == 0, (
            f"Found 'floe-e2e' used as default value in "
            f"{len(matches)} location(s): "
            f"{[(m[0] + 1, m[1].strip()) for m in matches]}"
        )

    def test_no_demo_admin_as_default_value(self) -> None:
        """'demo-admin' must not appear as a bash default value."""
        pattern = r':-demo-admin["\}]'
        matches = _find_all_lines(pattern)
        assert len(matches) == 0, (
            f"Found 'demo-admin' used as default value in "
            f"{len(matches)} location(s): "
            f"{[(m[0] + 1, m[1].strip()) for m in matches]}"
        )


# ---------------------------------------------------------------------------
# AC-2.8: Environment variable overrides still work
# ---------------------------------------------------------------------------


@pytest.mark.requirement("ARC-002")
class TestEnvVarOverridePreserved:
    """Verify the override pattern allows user-specified values."""

    def test_minio_bucket_allows_override(self) -> None:
        """MINIO_BUCKET must use ${MINIO_BUCKET:-...} pattern (not bare assignment).

        This ensures MINIO_BUCKET=custom ./test-e2e.sh still works.
        """
        pattern = r'MINIO_BUCKET="\$\{MINIO_BUCKET:-'
        match = _find_line_index(pattern)
        assert match is not None, (
            "MINIO_BUCKET must use ${MINIO_BUCKET:-default} pattern "
            "to allow environment variable overrides"
        )

    def test_polaris_catalog_allows_override(self) -> None:
        """POLARIS_CATALOG must use ${POLARIS_CATALOG:-...} pattern."""
        pattern = r'POLARIS_CATALOG="\$\{POLARIS_CATALOG:-'
        match = _find_line_index(pattern)
        assert match is not None, (
            "POLARIS_CATALOG must use ${POLARIS_CATALOG:-default} pattern "
            "to allow environment variable overrides"
        )

    def test_polaris_client_id_allows_override(self) -> None:
        """POLARIS_CLIENT_ID must use ${POLARIS_CLIENT_ID:-...} pattern."""
        pattern = r'POLARIS_CLIENT_ID="\$\{POLARIS_CLIENT_ID:-'
        match = _find_line_index(pattern)
        assert match is not None, (
            "POLARIS_CLIENT_ID must use ${POLARIS_CLIENT_ID:-default} pattern "
            "to allow environment variable overrides"
        )
