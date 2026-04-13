"""Tests for iceberg-purge work unit: _purge_iceberg_namespace improvements.

Verifies that _purge_iceberg_namespace():
- Uses purge_table instead of drop_table (AC-1)
- Deletes S3 objects under the table prefix after purge (AC-2)
- Handles S3 pagination for >1000 objects (AC-3)
- Uses boto3 for S3 calls (AC-4)
- Catches all cleanup exceptions as non-fatal (AC-5)
- Preserves namespace drop at the end (AC-6)

These are unit tests using mocks -- no real Polaris/MinIO required.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DBT_UTILS_PATH = _REPO_ROOT / "tests" / "e2e" / "dbt_utils.py"
# Fail-fast guard — if the path is wrong, collection fails immediately instead
# of silently swallowing FileNotFoundError downstream (AC-2 fail-fast guard).
assert _DBT_UTILS_PATH.exists(), f"dbt_utils.py not found at {_DBT_UTILS_PATH}"

# ---------------------------------------------------------------------------
# Helpers: load the module under test
# ---------------------------------------------------------------------------


def _load_dbt_utils() -> Any:
    """Import dbt_utils from tests/e2e/dbt_utils.py.

    Uses importlib to load from a non-package path.
    Clears the catalog cache to avoid cross-test pollution.
    """
    spec = importlib.util.spec_from_file_location("dbt_utils", str(_DBT_UTILS_PATH))
    assert spec is not None, f"Could not find {_DBT_UTILS_PATH}"
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Clear catalog cache to ensure mock isolation
    mod._catalog_cache.clear()
    return mod


def _make_mock_catalog(tables: list[tuple[str, str]]) -> MagicMock:
    """Create a mock catalog that returns the given table identifiers.

    Args:
        tables: List of (namespace, table_name) tuples.

    Returns:
        MagicMock configured as a PyIceberg catalog.
    """
    catalog = MagicMock()
    catalog.list_tables.return_value = tables
    # Each table needs a location for S3 prefix derivation
    for ns, name in tables:
        table_mock = MagicMock()
        table_mock.metadata.location = f"s3://warehouse/{ns}/{name}"
        catalog.load_table.return_value = table_mock
    return catalog


# ===========================================================================
# AC-1: purge_table replaces drop_table
# ===========================================================================


class TestPurgeTableReplacesDropTable:
    """Verify purge_table is called instead of drop_table."""

    @pytest.mark.requirement("AC-1")
    def test_purge_table_called_for_each_table(self) -> None:
        """purge_table must be invoked once per table in the namespace."""
        mod = _load_dbt_utils()
        catalog = _make_mock_catalog([("ns1", "t1"), ("ns1", "t2")])

        with patch.object(mod, "_get_polaris_catalog", return_value=catalog):
            mod._purge_iceberg_namespace("ns1")

        # purge_table MUST be called, not drop_table
        assert catalog.purge_table.call_count == 2, "purge_table must be called once per table"
        catalog.purge_table.assert_any_call("ns1.t1")
        catalog.purge_table.assert_any_call("ns1.t2")

    @pytest.mark.requirement("AC-1")
    def test_drop_table_not_called(self) -> None:
        """drop_table must NOT be called -- purge_table replaces it."""
        mod = _load_dbt_utils()
        catalog = _make_mock_catalog([("ns1", "t1")])

        with patch.object(mod, "_get_polaris_catalog", return_value=catalog):
            mod._purge_iceberg_namespace("ns1")

        catalog.drop_table.assert_not_called()

    @pytest.mark.requirement("AC-1")
    def test_source_code_has_no_drop_table_in_purge_fn(self) -> None:
        """Static check: _purge_iceberg_namespace must not contain drop_table calls.

        This catches implementations that call purge_table AND drop_table,
        or that only partially migrate.
        """
        source = _DBT_UTILS_PATH.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_purge_iceberg_namespace":
                fn_source = ast.get_source_segment(source, node)
                assert fn_source is not None
                # Must contain purge_table
                assert "purge_table" in fn_source, "_purge_iceberg_namespace must call purge_table"
                # Must NOT contain drop_table (except in comments/docstrings)
                # Strip docstring and comments, then check
                fn_lines = fn_source.split("\n")
                code_lines = [
                    line for line in fn_lines if line.strip() and not line.strip().startswith("#")
                ]
                # Remove docstring content (lines between triple quotes)
                code_text = "\n".join(code_lines)
                # Remove triple-quoted strings
                code_no_docstrings = re.sub(r'""".*?"""', "", code_text, flags=re.DOTALL)
                code_no_docstrings = re.sub(r"'''.*?'''", "", code_no_docstrings, flags=re.DOTALL)
                assert "drop_table" not in code_no_docstrings, (
                    "_purge_iceberg_namespace must not call drop_table (use purge_table instead)"
                )
                break
        else:
            pytest.fail("_purge_iceberg_namespace function not found in source")


# ===========================================================================
# AC-2: S3 prefix deletion after catalog purge
# ===========================================================================


class TestS3PrefixDeletion:
    """Verify S3 objects under the table prefix are deleted after purge."""

    @pytest.mark.requirement("AC-2")
    def test_s3_delete_called_after_purge(self) -> None:
        """After purge_table, S3 objects under the table prefix must be deleted."""
        mod = _load_dbt_utils()
        tables = [("ns1", "t1")]
        catalog = _make_mock_catalog(tables)

        # Track call order to verify S3 deletion happens
        call_order: list[str] = []
        original_purge = catalog.purge_table

        def track_purge(fqn: str) -> None:
            call_order.append(f"purge:{fqn}")
            return original_purge(fqn)

        catalog.purge_table.side_effect = track_purge

        # Mock boto3 S3 client
        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"KeyCount": 1, "Contents": [{"Key": "ns1/t1/data/file1.parquet"}]},
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("boto3.client", return_value=mock_s3),
        ):
            mod._purge_iceberg_namespace("ns1")

        # Verify S3 operations were attempted
        mock_s3.get_paginator.assert_called_with("list_objects_v2")
        mock_s3.delete_objects.assert_called()

    @pytest.mark.requirement("AC-2")
    def test_s3_prefix_matches_table_location(self) -> None:
        """S3 deletion must target the correct prefix derived from table metadata."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "orders")]
        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/orders"
        catalog.load_table.return_value = table_mock

        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        paginate_calls: list[dict[str, Any]] = []

        def capture_paginate(**kwargs: Any) -> list[dict[str, Any]]:
            paginate_calls.append(kwargs)
            return [{"Contents": [{"Key": "ns1/orders/data/file1.parquet"}]}]

        mock_paginator.paginate.side_effect = capture_paginate
        mock_s3.get_paginator.return_value = mock_paginator

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("boto3.client", return_value=mock_s3),
        ):
            mod._purge_iceberg_namespace("ns1")

        # The S3 paginate call must reference the warehouse bucket
        # and the table's prefix path
        assert len(paginate_calls) >= 1, "S3 paginate must be called"
        assert paginate_calls[0]["Bucket"] == "warehouse", (
            "S3 cleanup must target the bucket from table metadata location"
        )
        assert paginate_calls[0]["Prefix"] == "ns1/orders", (
            "S3 cleanup must target the prefix from table metadata location"
        )

    @pytest.mark.requirement("AC-2")
    def test_multiple_tables_each_get_s3_cleanup(self) -> None:
        """Each table in the namespace must get its own S3 prefix cleanup."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "t1"), ("ns1", "t2"), ("ns1", "t3")]

        # Return different locations per table
        locations = {
            "ns1.t1": "s3://warehouse/ns1/t1",
            "ns1.t2": "s3://warehouse/ns1/t2",
            "ns1.t3": "s3://warehouse/ns1/t3",
        }

        def load_table_side_effect(fqn: str) -> MagicMock:
            table_mock = MagicMock()
            table_mock.metadata.location = locations.get(fqn, f"s3://warehouse/{fqn}")
            return table_mock

        catalog.load_table.side_effect = load_table_side_effect

        boto3_calls: list[dict[str, Any]] = []
        mock_s3 = MagicMock()
        mock_paginator = MagicMock()

        def capture_paginate(**kwargs: Any) -> list[dict[str, Any]]:
            boto3_calls.append(kwargs)
            prefix = kwargs.get("Prefix", "")
            return [{"Contents": [{"Key": f"{prefix}/data/file.parquet"}]}]

        mock_paginator.paginate.side_effect = capture_paginate
        mock_s3.get_paginator.return_value = mock_paginator

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("boto3.client", return_value=mock_s3),
        ):
            mod._purge_iceberg_namespace("ns1")

        # At minimum, S3 listing should happen for each table
        assert len(boto3_calls) >= 3, (
            f"Expected at least 3 S3 paginate calls (one per table), got {len(boto3_calls)}"
        )


# ===========================================================================
# AC-3: S3 deletion handles pagination
# ===========================================================================


class TestS3Pagination:
    """Verify S3 object listing handles pagination (>1000 objects)."""

    @pytest.mark.requirement("AC-3")
    def test_pagination_handles_multiple_pages(self) -> None:
        """boto3 paginator must iterate all pages returned by list_objects_v2."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "big_table")]
        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/big_table"
        catalog.load_table.return_value = table_mock

        # Simulate two pages of results from the paginator
        page1 = {
            "KeyCount": 1,
            "Contents": [{"Key": "ns1/big_table/data/file1.parquet"}],
        }
        page2 = {
            "KeyCount": 1,
            "Contents": [{"Key": "ns1/big_table/data/file2.parquet"}],
        }

        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [page1, page2]
        mock_s3.get_paginator.return_value = mock_paginator

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("boto3.client", return_value=mock_s3),
        ):
            mod._purge_iceberg_namespace("ns1")

        # Must have called delete_objects for each page with contents
        assert mock_s3.delete_objects.call_count == 2, (
            "Expected 2 delete_objects calls (one per page), "
            f"got {mock_s3.delete_objects.call_count}"
        )

        # Verify the paginator was used with correct bucket/prefix
        mock_paginator.paginate.assert_called_once_with(Bucket="warehouse", Prefix="ns1/big_table")

    @pytest.mark.requirement("AC-3")
    def test_source_uses_boto3_paginator(self) -> None:
        """Static check: S3 cleanup must use boto3 paginator for pagination."""
        source = _DBT_UTILS_PATH.read_text()
        tree = ast.parse(source)

        # Check _delete_s3_prefix or _purge_iceberg_namespace for paginator usage
        found_paginator = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in (
                "_delete_s3_prefix",
                "_purge_iceberg_namespace",
            ):
                fn_source = ast.get_source_segment(source, node)
                assert fn_source is not None
                if "get_paginator" in fn_source and "list_objects_v2" in fn_source:
                    found_paginator = True
                    break

        assert found_paginator, (
            "S3 cleanup must use boto3 get_paginator('list_objects_v2') for pagination"
        )


# ===========================================================================
# AC-4: S3 cleanup uses boto3 (AWS Signature V4)
# ===========================================================================


class TestBoto3S3Dependency:
    """Verify S3 cleanup uses boto3 for AWS Signature V4 compatibility."""

    @pytest.mark.requirement("AC-4")
    def test_source_imports_boto3(self) -> None:
        """dbt_utils.py must import boto3 for S3 cleanup."""
        source = _DBT_UTILS_PATH.read_text()
        assert "boto3" in source, "dbt_utils.py must import boto3 for S3 operations"

    @pytest.mark.requirement("AC-4")
    def test_source_does_not_import_httpx(self) -> None:
        """dbt_utils.py must not import httpx (replaced by boto3)."""
        source = _DBT_UTILS_PATH.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "httpx", (
                        "httpx import found -- S3 operations should use boto3"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module != "httpx", (
                    "httpx import found -- S3 operations should use boto3"
                )

    @pytest.mark.requirement("AC-4")
    def test_boto3_client_used_in_purge_function(self) -> None:
        """The _purge_iceberg_namespace function must use boto3.client for S3 calls."""
        source = _DBT_UTILS_PATH.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_purge_iceberg_namespace":
                fn_source = ast.get_source_segment(source, node)
                assert fn_source is not None
                assert "boto3" in fn_source, (
                    "_purge_iceberg_namespace must use boto3 for S3 cleanup"
                )
                break
        else:
            pytest.fail("_purge_iceberg_namespace function not found in source")


# ===========================================================================
# AC-5: Cleanup failures are non-fatal
# ===========================================================================


class TestCleanupNonFatal:
    """Verify that purge_table and S3 cleanup failures don't raise."""

    @pytest.mark.requirement("AC-5")
    def test_purge_table_exception_does_not_propagate(self) -> None:
        """If purge_table raises, execution continues to next table."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "t1"), ("ns1", "t2")]
        # First purge fails, second succeeds
        catalog.purge_table.side_effect = [
            RuntimeError("purge failed"),
            None,
        ]

        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/t1"
        catalog.load_table.return_value = table_mock

        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = []
        mock_s3.get_paginator.return_value = mock_paginator

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("boto3.client", return_value=mock_s3),
        ):
            # Must not raise
            mod._purge_iceberg_namespace("ns1")

        # Second table must still have purge_table attempted
        assert catalog.purge_table.call_count == 2, (
            "purge_table must be attempted for all tables even when one fails"
        )

    @pytest.mark.requirement("AC-5")
    def test_s3_cleanup_exception_does_not_propagate(self) -> None:
        """If S3 cleanup raises, namespace drop still happens.

        This test verifies that:
        1. purge_table is called (not drop_table)
        2. S3 cleanup is attempted (boto3.client is used)
        3. When S3 cleanup raises, the function still completes
        4. Namespace drop still happens after S3 failure
        """
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "t1")]
        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/t1"
        catalog.load_table.return_value = table_mock

        mock_s3 = MagicMock()
        # S3 paginator raises when called
        mock_s3.get_paginator.side_effect = ConnectionError("S3 unreachable")

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("boto3.client", return_value=mock_s3) as mock_boto3_client,
        ):
            # Must not raise
            mod._purge_iceberg_namespace("ns1")

        # purge_table must have been called (not drop_table)
        catalog.purge_table.assert_called_once_with("ns1.t1")
        catalog.drop_table.assert_not_called()
        # boto3.client must have been called (S3 cleanup was attempted)
        mock_boto3_client.assert_called()
        # Namespace drop must still be attempted despite S3 failure
        catalog.drop_namespace.assert_called_once_with("ns1")

    @pytest.mark.requirement("AC-5")
    def test_catalog_none_returns_immediately(self) -> None:
        """If catalog is None (unavailable), function returns without error."""
        mod = _load_dbt_utils()

        with patch.object(mod, "_get_polaris_catalog", return_value=None):
            # Must not raise
            mod._purge_iceberg_namespace("ns1")

    @pytest.mark.requirement("AC-5")
    def test_list_tables_exception_is_non_fatal(self) -> None:
        """If list_tables raises (namespace doesn't exist), function returns cleanly."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.side_effect = RuntimeError("namespace not found")

        with patch.object(mod, "_get_polaris_catalog", return_value=catalog):
            # Must not raise
            mod._purge_iceberg_namespace("ns1")


# ===========================================================================
# AC-6: Namespace drop preserved
# ===========================================================================


class TestNamespaceDropPreserved:
    """Verify namespace is dropped after all tables are purged."""

    @pytest.mark.requirement("AC-6")
    def test_namespace_dropped_after_all_tables(self) -> None:
        """drop_namespace must be called after all purge_table calls complete."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "t1"), ("ns1", "t2")]

        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/t1"
        catalog.load_table.return_value = table_mock

        call_sequence: list[str] = []

        def track_purge(fqn: str) -> None:
            call_sequence.append(f"purge_table:{fqn}")

        def track_drop_ns(ns: str) -> None:
            call_sequence.append(f"drop_namespace:{ns}")

        catalog.purge_table.side_effect = track_purge
        catalog.drop_namespace.side_effect = track_drop_ns

        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = []
        mock_s3.get_paginator.return_value = mock_paginator

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("boto3.client", return_value=mock_s3),
        ):
            mod._purge_iceberg_namespace("ns1")

        # Verify purge_table was actually called (not vacuously true)
        purge_indices = [i for i, c in enumerate(call_sequence) if c.startswith("purge_table:")]
        assert len(purge_indices) == 2, (
            f"Expected 2 purge_table calls, got {len(purge_indices)}. Sequence: {call_sequence}"
        )

        # Verify ordering: purge tables first, then drop namespace
        assert "drop_namespace:ns1" in call_sequence, "drop_namespace must be called"
        ns_drop_idx = call_sequence.index("drop_namespace:ns1")
        assert all(pi < ns_drop_idx for pi in purge_indices), (
            f"All purge_table calls must precede drop_namespace. Sequence: {call_sequence}"
        )

    @pytest.mark.requirement("AC-6")
    def test_namespace_dropped_even_when_no_tables(self) -> None:
        """Namespace drop happens even if there are no tables to purge."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = []

        with patch.object(mod, "_get_polaris_catalog", return_value=catalog):
            mod._purge_iceberg_namespace("ns1")

        catalog.drop_namespace.assert_called_once_with("ns1")

    @pytest.mark.requirement("AC-6")
    def test_namespace_drop_failure_is_non_fatal(self) -> None:
        """If drop_namespace raises, the function still returns cleanly."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = []
        catalog.drop_namespace.side_effect = RuntimeError("cannot drop")

        with patch.object(mod, "_get_polaris_catalog", return_value=catalog):
            # Must not raise
            mod._purge_iceberg_namespace("ns1")

    @pytest.mark.requirement("AC-6")
    def test_full_sequence_purge_then_s3_then_namespace(self) -> None:
        """Full call sequence: purge_table -> S3 delete -> drop_namespace."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "t1")]

        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/t1"
        catalog.load_table.return_value = table_mock

        call_sequence: list[str] = []

        def _track_purge(_fqn: str) -> None:
            call_sequence.append("purge_table")

        def _track_drop_ns(_ns: str) -> None:
            call_sequence.append("drop_namespace")

        catalog.purge_table.side_effect = _track_purge
        catalog.drop_namespace.side_effect = _track_drop_ns

        mock_s3 = MagicMock()
        mock_paginator = MagicMock()

        def s3_paginate(**_kwargs: Any) -> list[dict[str, Any]]:
            call_sequence.append("s3_list")
            return [{"Contents": [{"Key": "ns1/t1/data/file.parquet"}]}]

        mock_paginator.paginate.side_effect = s3_paginate
        mock_s3.get_paginator.return_value = mock_paginator

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("boto3.client", return_value=mock_s3),
        ):
            mod._purge_iceberg_namespace("ns1")

        # Expected order: purge -> s3 -> namespace drop
        assert "purge_table" in call_sequence, "purge_table must be called"
        assert "s3_list" in call_sequence, "S3 listing must be called"
        assert "drop_namespace" in call_sequence, "drop_namespace must be called"

        purge_idx = call_sequence.index("purge_table")
        s3_idx = call_sequence.index("s3_list")
        ns_idx = call_sequence.index("drop_namespace")

        assert purge_idx < s3_idx < ns_idx, (
            f"Expected purge_table < s3_list < drop_namespace, got sequence: {call_sequence}"
        )
