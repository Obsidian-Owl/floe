"""Unit tests for security hardening of DuckDBComputePlugin.

Tests validate fixes for:
- HIGH-1: Error/path leakage to OTel spans and connection result messages
- HIGH-2: Unvalidated database path (path traversal prevention)
- MEDIUM-3: SQL validation gaps (URI scheme, warehouse character set)
- MEDIUM-4: Unvalidated attach options dict merge (key allowlist)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from floe_core.compute_config import (
    CatalogConfig,
    ComputeConfig,
    ConnectionStatus,
)

from floe_compute_duckdb.plugin import (
    DuckDBComputePlugin,
    _sanitize_path_for_logging,
    _validate_catalog_uri,
    _validate_db_path,
    _validate_warehouse,
)


@pytest.fixture
def plugin() -> DuckDBComputePlugin:
    """Create a DuckDBComputePlugin instance."""
    return DuckDBComputePlugin()


@pytest.fixture
def mock_duckdb_success() -> MagicMock:
    """Create a mock duckdb module that succeeds."""
    mock_duckdb = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    mock_duckdb.connect.return_value = mock_conn
    return mock_duckdb


class TestDbPathValidation:
    """HIGH-2: Validate database path before connecting or generating profiles."""

    @pytest.mark.requirement("001-SEC-001")
    def test_memory_path_accepted(self) -> None:
        """Test :memory: is a valid database path."""
        _validate_db_path(":memory:")  # Should not raise

    @pytest.mark.requirement("001-SEC-001")
    def test_absolute_path_accepted(self) -> None:
        """Test absolute file path is accepted."""
        _validate_db_path("/data/analytics.duckdb")  # Should not raise

    @pytest.mark.requirement("001-SEC-001")
    def test_relative_path_accepted(self) -> None:
        """Test relative file path is accepted."""
        _validate_db_path("my_database.duckdb")  # Should not raise

    @pytest.mark.requirement("001-SEC-001")
    def test_path_traversal_rejected(self) -> None:
        """Test path containing '..' is rejected to prevent traversal."""
        with pytest.raises(ValueError, match="path traversal"):
            _validate_db_path("/data/../etc/passwd")

    @pytest.mark.requirement("001-SEC-001")
    def test_path_traversal_at_start_rejected(self) -> None:
        """Test path starting with '..' is rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            _validate_db_path("../../etc/passwd")

    @pytest.mark.requirement("001-SEC-001")
    def test_path_traversal_embedded_rejected(self) -> None:
        """Test path with embedded '..' segments is rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            _validate_db_path("/data/safe/../../etc/shadow")

    @pytest.mark.requirement("001-SEC-001")
    def test_generate_profile_rejects_traversal(self, plugin: DuckDBComputePlugin) -> None:
        """Test generate_dbt_profile rejects path traversal in db_path."""
        config = ComputeConfig(
            plugin="duckdb",
            connection={"path": "/data/../etc/passwd"},
        )

        with pytest.raises(ValueError, match="path traversal"):
            plugin.generate_dbt_profile(config)

    @pytest.mark.requirement("001-SEC-001")
    def test_validate_connection_rejects_traversal(self, plugin: DuckDBComputePlugin) -> None:
        """Test validate_connection rejects path traversal in db_path."""
        config = ComputeConfig(
            plugin="duckdb",
            connection={"path": "../../etc/shadow"},
        )

        with pytest.raises(ValueError, match="path traversal"):
            plugin.validate_connection(config)


class TestPathSanitizationForLogging:
    """HIGH-1: Sanitize paths before including in OTel spans and log messages."""

    @pytest.mark.requirement("001-SEC-002")
    def test_memory_path_unchanged(self) -> None:
        """Test :memory: is returned as-is."""
        assert _sanitize_path_for_logging(":memory:") == ":memory:"

    @pytest.mark.requirement("001-SEC-002")
    def test_absolute_path_returns_basename(self) -> None:
        """Test absolute path is reduced to basename only."""
        assert _sanitize_path_for_logging("/data/secret/analytics.duckdb") == "analytics.duckdb"

    @pytest.mark.requirement("001-SEC-002")
    def test_nested_path_returns_basename(self) -> None:
        """Test deeply nested path is reduced to basename."""
        assert _sanitize_path_for_logging("/a/b/c/d/e/db.duckdb") == "db.duckdb"


class TestErrorLeakagePrevention:
    """HIGH-1: Prevent raw error details from leaking to OTel spans and messages."""

    @pytest.mark.requirement("001-SEC-002")
    def test_error_message_not_in_connection_result(self, plugin: DuckDBComputePlugin) -> None:
        """Test that raw exception messages are not included in ConnectionResult."""
        mock_duckdb = MagicMock()
        sensitive_error = "FATAL: password authentication failed for user 'admin'"
        mock_duckdb.connect.side_effect = Exception(sensitive_error)

        with patch.dict("sys.modules", {"duckdb": mock_duckdb}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": ":memory:"},
            )
            result = plugin.validate_connection(config)

        assert result.status == ConnectionStatus.UNHEALTHY
        assert "password" not in result.message
        assert "admin" not in result.message
        assert sensitive_error not in result.message

    @pytest.mark.requirement("001-SEC-002")
    def test_error_warnings_empty(self, plugin: DuckDBComputePlugin) -> None:
        """Test that no raw error details leak into warnings list."""
        mock_duckdb = MagicMock()
        mock_duckdb.connect.side_effect = Exception("Internal server error at 10.0.0.5:5432")

        with patch.dict("sys.modules", {"duckdb": mock_duckdb}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": ":memory:"},
            )
            result = plugin.validate_connection(config)

        assert len(result.warnings) == 0

    @pytest.mark.requirement("001-SEC-002")
    def test_otel_span_uses_error_type_not_message(self, plugin: DuckDBComputePlugin) -> None:
        """Test OTel span records error type, not raw error message."""
        mock_duckdb = MagicMock()
        mock_duckdb.connect.side_effect = ConnectionError("secret connection string")

        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)

        with (
            patch.dict("sys.modules", {"duckdb": mock_duckdb}),
            patch(
                "floe_compute_duckdb.plugin.start_validation_span",
                return_value=mock_span,
            ),
            patch("floe_compute_duckdb.plugin.record_validation_duration"),
            patch("floe_compute_duckdb.plugin.record_validation_error"),
        ):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": ":memory:"},
            )
            plugin.validate_connection(config)

        # Should set error.type (class name), NOT error.message (raw string)
        mock_span.set_attribute.assert_any_call("error.type", "ConnectionError")
        # Verify error.message is NOT set
        error_message_calls = [
            call for call in mock_span.set_attribute.call_args_list if call[0][0] == "error.message"
        ]
        assert len(error_message_calls) == 0

    @pytest.mark.requirement("001-SEC-002")
    def test_otel_span_uses_db_system_not_db_path(
        self, plugin: DuckDBComputePlugin, mock_duckdb_success: MagicMock
    ) -> None:
        """Test OTel span uses db.system instead of db.path to avoid path leakage."""
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)

        with (
            patch.dict("sys.modules", {"duckdb": mock_duckdb_success}),
            patch(
                "floe_compute_duckdb.plugin.start_validation_span",
                return_value=mock_span,
            ),
            patch("floe_compute_duckdb.plugin.record_validation_duration"),
        ):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/secret/path/db.duckdb"},
            )
            plugin.validate_connection(config)

        # Should set db.system, NOT db.path
        mock_span.set_attribute.assert_any_call("db.system", "duckdb")
        db_path_calls = [
            call for call in mock_span.set_attribute.call_args_list if call[0][0] == "db.path"
        ]
        assert len(db_path_calls) == 0

    @pytest.mark.requirement("001-SEC-002")
    def test_healthy_message_does_not_leak_path(
        self, plugin: DuckDBComputePlugin, mock_duckdb_success: MagicMock
    ) -> None:
        """Test successful connection message doesn't include full path."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/secret/internal/db.duckdb"},
            )
            result = plugin.validate_connection(config)

        assert result.status == ConnectionStatus.HEALTHY
        assert "/secret/internal" not in result.message


class TestCatalogUriValidation:
    """MEDIUM-3: Validate catalog_uri scheme before embedding in SQL."""

    @pytest.mark.requirement("001-SEC-003")
    def test_http_scheme_accepted(self) -> None:
        """Test http:// URIs are accepted."""
        _validate_catalog_uri("http://polaris:8181/api/catalog")

    @pytest.mark.requirement("001-SEC-003")
    def test_https_scheme_accepted(self) -> None:
        """Test https:// URIs are accepted."""
        _validate_catalog_uri("https://polaris.example.com/api/catalog")

    @pytest.mark.requirement("001-SEC-003")
    def test_file_scheme_rejected(self) -> None:
        """Test file:// URIs are rejected (potential local file access)."""
        with pytest.raises(ValueError, match="Invalid catalog URI scheme"):
            _validate_catalog_uri("file:///etc/passwd")

    @pytest.mark.requirement("001-SEC-003")
    def test_ftp_scheme_rejected(self) -> None:
        """Test ftp:// URIs are rejected."""
        with pytest.raises(ValueError, match="Invalid catalog URI scheme"):
            _validate_catalog_uri("ftp://evil.example.com/data")

    @pytest.mark.requirement("001-SEC-003")
    def test_javascript_scheme_rejected(self) -> None:
        """Test javascript: URIs are rejected (XSS prevention)."""
        with pytest.raises(ValueError, match="Invalid catalog URI scheme"):
            _validate_catalog_uri("javascript:alert(1)")

    @pytest.mark.requirement("001-SEC-003")
    def test_no_scheme_rejected(self) -> None:
        """Test URIs without a scheme are rejected."""
        with pytest.raises(ValueError, match="Invalid catalog URI scheme"):
            _validate_catalog_uri("polaris:8181/api/catalog")

    @pytest.mark.requirement("001-SEC-003")
    def test_catalog_attachment_rejects_file_uri(self, plugin: DuckDBComputePlugin) -> None:
        """Test get_catalog_attachment_sql rejects file:// URI."""
        config = CatalogConfig(
            catalog_type="rest",
            catalog_name="test_catalog",
            catalog_uri="file:///etc/passwd",
        )

        with pytest.raises(ValueError, match="Invalid catalog URI scheme"):
            plugin.get_catalog_attachment_sql(config)


class TestWarehouseValidation:
    """MEDIUM-3: Validate warehouse character set."""

    @pytest.mark.requirement("001-SEC-003")
    def test_simple_warehouse_accepted(self) -> None:
        """Test simple identifier warehouse name is accepted."""
        _validate_warehouse("floe_warehouse")

    @pytest.mark.requirement("001-SEC-003")
    def test_s3_path_warehouse_accepted(self) -> None:
        """Test S3 path warehouse is accepted."""
        _validate_warehouse("s3://my-bucket/warehouse/path")

    @pytest.mark.requirement("001-SEC-003")
    def test_warehouse_with_sql_injection_rejected(self) -> None:
        """Test warehouse with SQL injection attempt is rejected."""
        with pytest.raises(ValueError, match="Invalid warehouse"):
            _validate_warehouse("floe'; DROP TABLE users; --")

    @pytest.mark.requirement("001-SEC-003")
    def test_warehouse_with_backticks_rejected(self) -> None:
        """Test warehouse with backtick injection is rejected."""
        with pytest.raises(ValueError, match="Invalid warehouse"):
            _validate_warehouse("warehouse`; DROP TABLE x")

    @pytest.mark.requirement("001-SEC-003")
    def test_catalog_attachment_rejects_bad_warehouse(self, plugin: DuckDBComputePlugin) -> None:
        """Test get_catalog_attachment_sql rejects warehouse with unsafe chars."""
        config = CatalogConfig(
            catalog_type="rest",
            catalog_name="test_catalog",
            catalog_uri="http://polaris:8181/api/catalog",
            warehouse="warehouse'; DROP TABLE x; --",
        )

        with pytest.raises(ValueError, match="Invalid warehouse"):
            plugin.get_catalog_attachment_sql(config)


class TestAttachOptionsAllowlist:
    """MEDIUM-4: Validate attach options keys against allowlist."""

    @pytest.mark.requirement("001-SEC-004")
    def test_allowed_option_keys_accepted(self, plugin: DuckDBComputePlugin) -> None:
        """Test that allowed option keys pass validation."""
        config = ComputeConfig(
            plugin="duckdb",
            connection={
                "path": ":memory:",
                "attach": [
                    {
                        "path": "iceberg:polaris",
                        "alias": "ice",
                        "type": "iceberg",
                        "options": {"read_only": "true", "schema": "public"},
                    }
                ],
            },
        )

        profile = plugin.generate_dbt_profile(config)
        attach_entry = profile["attach"][0]
        assert attach_entry["read_only"] == "true"
        assert attach_entry["schema"] == "public"

    @pytest.mark.requirement("001-SEC-004")
    def test_disallowed_option_key_rejected(self, plugin: DuckDBComputePlugin) -> None:
        """Test that disallowed option keys raise ValueError."""
        config = ComputeConfig(
            plugin="duckdb",
            connection={
                "path": ":memory:",
                "attach": [
                    {
                        "path": "iceberg:polaris",
                        "alias": "ice",
                        "options": {"malicious_key": "DROP TABLE users"},
                    }
                ],
            },
        )

        with pytest.raises(ValueError, match="Invalid attach option key.*malicious_key"):
            plugin.generate_dbt_profile(config)

    @pytest.mark.requirement("001-SEC-004")
    def test_empty_options_accepted(self, plugin: DuckDBComputePlugin) -> None:
        """Test that empty options dict is accepted."""
        config = ComputeConfig(
            plugin="duckdb",
            connection={
                "path": ":memory:",
                "attach": [
                    {
                        "path": "iceberg:polaris",
                        "alias": "ice",
                        "options": {},
                    }
                ],
            },
        )

        profile = plugin.generate_dbt_profile(config)
        assert len(profile["attach"]) == 1

    @pytest.mark.requirement("001-SEC-004")
    def test_no_options_accepted(self, plugin: DuckDBComputePlugin) -> None:
        """Test that attach without options is accepted."""
        config = ComputeConfig(
            plugin="duckdb",
            connection={
                "path": ":memory:",
                "attach": [
                    {
                        "path": "iceberg:polaris",
                        "alias": "ice",
                    }
                ],
            },
        )

        profile = plugin.generate_dbt_profile(config)
        assert len(profile["attach"]) == 1


class TestValidateConnectionReadOnly:
    """HIGH-2: validate_connection uses read_only for file paths, not :memory:."""

    @pytest.mark.requirement("001-SEC-001")
    def test_validate_connection_memory_not_read_only(
        self, plugin: DuckDBComputePlugin, mock_duckdb_success: MagicMock
    ) -> None:
        """Test :memory: connections use read_only=False (DuckDB requirement)."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": ":memory:"},
            )
            plugin.validate_connection(config)

        # :memory: cannot use read_only=True (DuckDB raises InvalidInputException)
        mock_duckdb_success.connect.assert_called_once_with(":memory:", read_only=False)

    @pytest.mark.requirement("001-SEC-001")
    def test_validate_connection_file_path_read_only(
        self, plugin: DuckDBComputePlugin, mock_duckdb_success: MagicMock
    ) -> None:
        """Test file-based paths use read_only=True for validation safety."""
        with patch.dict("sys.modules", {"duckdb": mock_duckdb_success}):
            config = ComputeConfig(
                plugin="duckdb",
                connection={"path": "/data/analytics.duckdb"},
            )
            plugin.validate_connection(config)

        mock_duckdb_success.connect.assert_called_once_with(
            "/data/analytics.duckdb", read_only=True
        )
