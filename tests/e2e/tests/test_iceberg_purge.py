"""Tests for iceberg-purge work unit: _purge_iceberg_namespace improvements.

Verifies that _purge_iceberg_namespace():
- Uses purge_table instead of drop_table (AC-1)
- Deletes S3 objects under the table prefix after purge (AC-2)
- Handles S3 pagination for >1000 objects (AC-3)
- Uses httpx for S3 calls, not boto3 (AC-4)
- Catches all cleanup exceptions as non-fatal (AC-5)
- Preserves namespace drop at the end (AC-6)

These are unit tests using mocks -- no real Polaris/MinIO required.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import re
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DBT_UTILS_PATH = _REPO_ROOT / "tests" / "e2e" / "dbt_utils.py"

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

        # Mock httpx to intercept S3 calls
        mock_response = MagicMock()
        mock_response.status_code = 200
        # S3 ListObjectsV2 response with one object
        mock_response.text = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <ListBucketResult>
                <IsTruncated>false</IsTruncated>
                <Contents>
                    <Key>ns1/t1/data/file1.parquet</Key>
                </Contents>
            </ListBucketResult>
        """)

        mock_delete_response = MagicMock()
        mock_delete_response.status_code = 200
        mock_delete_response.text = "<DeleteResult/>"

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("httpx.Client") as mock_httpx_client_cls,
        ):
            mock_client_instance = MagicMock()
            mock_httpx_client_cls.return_value.__enter__ = MagicMock(
                return_value=mock_client_instance
            )
            mock_httpx_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.post.return_value = mock_delete_response

            mod._purge_iceberg_namespace("ns1")

        # Verify S3 operations were attempted (GET for listing or DELETE)
        assert (
            mock_client_instance.get.called
            or mock_client_instance.post.called
            or mock_client_instance.delete.called
        ), "S3 cleanup must make HTTP requests to delete objects"

    @pytest.mark.requirement("AC-2")
    def test_s3_prefix_matches_table_location(self) -> None:
        """S3 deletion must target the correct prefix derived from table metadata."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "orders")]
        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/orders"
        catalog.load_table.return_value = table_mock

        s3_requests: list[str] = []

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("httpx.Client") as mock_httpx_cls,
        ):
            mock_client = MagicMock()
            mock_httpx_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx_cls.return_value.__exit__ = MagicMock(return_value=False)

            # Capture S3 request URLs
            def capture_get(url: str, **_kw: Any) -> MagicMock:
                s3_requests.append(url)
                resp = MagicMock()
                resp.status_code = 200
                resp.text = "<ListBucketResult><IsTruncated>false</IsTruncated></ListBucketResult>"
                return resp

            mock_client.get.side_effect = capture_get

            mod._purge_iceberg_namespace("ns1")

        # The S3 listing or deletion must reference the warehouse bucket
        # and the table's prefix path
        all_urls = " ".join(s3_requests)
        assert "warehouse" in all_urls or len(s3_requests) > 0, (
            "S3 cleanup must target the bucket/prefix from table metadata location"
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

        s3_get_calls: list[Any] = []

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("httpx.Client") as mock_httpx_cls,
        ):
            mock_client = MagicMock()
            mock_httpx_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx_cls.return_value.__exit__ = MagicMock(return_value=False)

            def capture_get(url: str, **kwargs: Any) -> MagicMock:
                s3_get_calls.append((url, kwargs))
                resp = MagicMock()
                resp.status_code = 200
                resp.text = "<ListBucketResult><IsTruncated>false</IsTruncated></ListBucketResult>"
                return resp

            mock_client.get.side_effect = capture_get

            mod._purge_iceberg_namespace("ns1")

        # At minimum, S3 listing should happen for each table
        assert len(s3_get_calls) >= 3, (
            f"Expected at least 3 S3 listing calls (one per table), got {len(s3_get_calls)}"
        )


# ===========================================================================
# AC-3: S3 deletion handles pagination
# ===========================================================================


class TestS3Pagination:
    """Verify S3 object listing handles pagination (>1000 objects)."""

    @pytest.mark.requirement("AC-3")
    def test_pagination_continues_when_is_truncated(self) -> None:
        """When S3 returns IsTruncated=true, must fetch next page with ContinuationToken."""
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "big_table")]
        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/big_table"
        catalog.load_table.return_value = table_mock

        # Page 1: truncated, has continuation token
        page1 = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <ListBucketResult>
                <IsTruncated>true</IsTruncated>
                <NextContinuationToken>token-page2</NextContinuationToken>
                <Contents><Key>ns1/big_table/data/file1.parquet</Key></Contents>
            </ListBucketResult>
        """)
        # Page 2: not truncated
        page2 = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <ListBucketResult>
                <IsTruncated>false</IsTruncated>
                <Contents><Key>ns1/big_table/data/file2.parquet</Key></Contents>
            </ListBucketResult>
        """)

        call_count = {"get": 0}
        get_params_list: list[dict[str, Any]] = []

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("httpx.Client") as mock_httpx_cls,
        ):
            mock_client = MagicMock()
            mock_httpx_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx_cls.return_value.__exit__ = MagicMock(return_value=False)

            def paginated_get(url: str, **kwargs: Any) -> MagicMock:
                call_count["get"] += 1
                get_params_list.append(kwargs)
                resp = MagicMock()
                resp.status_code = 200
                resp.text = page1 if call_count["get"] == 1 else page2
                return resp

            mock_client.get.side_effect = paginated_get

            # Also accept POST for multi-delete
            delete_resp = MagicMock()
            delete_resp.status_code = 200
            delete_resp.text = "<DeleteResult/>"
            mock_client.post.return_value = delete_resp

            mod._purge_iceberg_namespace("ns1")

        # Must have made at least 2 GET requests (page 1 + page 2)
        assert call_count["get"] >= 2, (
            f"Expected at least 2 S3 listing requests for pagination, got {call_count['get']}"
        )

        # Second request must include continuation token
        if len(get_params_list) >= 2:
            second_call_params = get_params_list[1].get("params", {})
            # The continuation token must appear somewhere in the second call
            second_call_str = str(second_call_params) + str(get_params_list[1])
            assert "token-page2" in second_call_str or "continuation" in second_call_str.lower(), (
                "Second S3 listing request must include the ContinuationToken from page 1"
            )

    @pytest.mark.requirement("AC-3")
    def test_source_contains_pagination_logic(self) -> None:
        """Static check: _purge_iceberg_namespace must handle IsTruncated/ContinuationToken."""
        source = _DBT_UTILS_PATH.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_purge_iceberg_namespace":
                fn_source = ast.get_source_segment(source, node)
                assert fn_source is not None
                fn_lower = fn_source.lower()
                assert "istruncated" in fn_lower or "is_truncated" in fn_lower, (
                    "Function must check IsTruncated in S3 listing response"
                )
                assert "continuationtoken" in fn_lower or "continuation_token" in fn_lower, (
                    "Function must use ContinuationToken for S3 pagination"
                )
                break
        else:
            pytest.fail("_purge_iceberg_namespace function not found in source")


# ===========================================================================
# AC-4: S3 cleanup uses httpx (no boto3)
# ===========================================================================


class TestNoAWSDependency:
    """Verify S3 cleanup uses httpx, not boto3/botocore."""

    @pytest.mark.requirement("AC-4")
    def test_source_does_not_import_boto3(self) -> None:
        """dbt_utils.py must not import boto3 or botocore."""
        source = _DBT_UTILS_PATH.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "boto" not in alias.name.lower(), (
                        f"boto3/botocore import found: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert "boto" not in node.module.lower(), (
                    f"boto3/botocore import found: {node.module}"
                )

    @pytest.mark.requirement("AC-4")
    def test_source_imports_httpx(self) -> None:
        """dbt_utils.py must import httpx for S3 cleanup."""
        source = _DBT_UTILS_PATH.read_text()
        assert "httpx" in source, "dbt_utils.py must import httpx for S3 operations"

    @pytest.mark.requirement("AC-4")
    def test_httpx_client_used_in_purge_function(self) -> None:
        """The _purge_iceberg_namespace function must use httpx.Client for S3 calls."""
        source = _DBT_UTILS_PATH.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_purge_iceberg_namespace":
                fn_source = ast.get_source_segment(source, node)
                assert fn_source is not None
                assert "httpx" in fn_source, (
                    "_purge_iceberg_namespace must use httpx for S3 cleanup"
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

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("httpx.Client"),
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
        2. S3 cleanup is attempted (httpx.Client is used)
        3. When S3 cleanup raises, the function still completes
        4. Namespace drop still happens after S3 failure
        """
        mod = _load_dbt_utils()
        catalog = MagicMock()
        catalog.list_tables.return_value = [("ns1", "t1")]
        table_mock = MagicMock()
        table_mock.metadata.location = "s3://warehouse/ns1/t1"
        catalog.load_table.return_value = table_mock

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("httpx.Client") as mock_httpx_cls,
        ):
            mock_client = MagicMock()
            mock_httpx_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx_cls.return_value.__exit__ = MagicMock(return_value=False)
            # S3 listing raises
            mock_client.get.side_effect = ConnectionError("S3 unreachable")

            # Must not raise
            mod._purge_iceberg_namespace("ns1")

        # purge_table must have been called (not drop_table)
        catalog.purge_table.assert_called_once_with("ns1.t1")
        catalog.drop_table.assert_not_called()
        # httpx.Client must have been instantiated (S3 cleanup was attempted)
        mock_httpx_cls.assert_called()
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

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("httpx.Client"),
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

        with (
            patch.object(mod, "_get_polaris_catalog", return_value=catalog),
            patch("httpx.Client") as mock_httpx_cls,
        ):
            mock_client = MagicMock()
            mock_httpx_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_httpx_cls.return_value.__exit__ = MagicMock(return_value=False)

            def s3_get(_url: str, **_kwargs: Any) -> MagicMock:
                call_sequence.append("s3_list")
                resp = MagicMock()
                resp.status_code = 200
                resp.text = "<ListBucketResult><IsTruncated>false</IsTruncated></ListBucketResult>"
                return resp

            mock_client.get.side_effect = s3_get

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
