"""Unit tests for audit logging decorator.

Tests for audit_secret_access decorator and helper functions.

Task: Coverage improvement for 7a-identity-secrets
Requirements: FR-060
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.audit.decorator import (
    _extract_secret_path,
    _get_attr_safe,
    audit_secret_access,
)
from floe_core.schemas.audit import AuditOperation


class TestGetAttrSafe:
    """Tests for _get_attr_safe() helper function."""

    @pytest.mark.requirement("FR-060")
    def test_returns_none_for_none_attr(self) -> None:
        """Test that None attr returns None."""
        obj = MagicMock()
        result = _get_attr_safe(obj, None)
        assert result is None

    @pytest.mark.requirement("FR-060")
    def test_returns_attr_value_as_string(self) -> None:
        """Test that attribute value is converted to string."""
        obj = MagicMock()
        obj.name = "test-plugin"
        result = _get_attr_safe(obj, "name")
        assert result == "test-plugin"

    @pytest.mark.requirement("FR-060")
    def test_returns_none_for_missing_attr(self) -> None:
        """Test that missing attribute returns None."""
        obj = MagicMock(spec=[])  # No attributes
        result = _get_attr_safe(obj, "nonexistent")
        assert result is None

    @pytest.mark.requirement("FR-060")
    def test_returns_none_for_none_value(self) -> None:
        """Test that None attribute value returns None."""
        obj = MagicMock()
        obj.namespace = None
        result = _get_attr_safe(obj, "namespace")
        assert result is None

    @pytest.mark.requirement("FR-060")
    def test_handles_exception_gracefully(self) -> None:
        """Test that exceptions are handled and None returned."""

        class BrokenObject:
            @property
            def bad_attr(self) -> str:
                raise RuntimeError("Broken property")

        obj = BrokenObject()
        result = _get_attr_safe(obj, "bad_attr")
        assert result is None

    @pytest.mark.requirement("FR-060")
    def test_converts_non_string_to_string(self) -> None:
        """Test that non-string values are converted to strings."""
        obj = MagicMock()
        obj.port = 5432
        result = _get_attr_safe(obj, "port")
        assert result == "5432"


class TestExtractSecretPath:
    """Tests for _extract_secret_path() helper function."""

    @pytest.mark.requirement("FR-060")
    def test_extracts_from_kwargs(self) -> None:
        """Test extracting secret path from kwargs."""

        def my_func(self: Any, key: str) -> None:
            pass

        result = _extract_secret_path(my_func, (), {"key": "db-password"}, "key")
        assert result == "db-password"

    @pytest.mark.requirement("FR-060")
    def test_extracts_from_positional_args(self) -> None:
        """Test extracting secret path from positional args."""

        def my_func(self: Any, key: str, value: str) -> None:
            pass

        result = _extract_secret_path(my_func, ("db-password", "secret"), {}, "key")
        assert result == "db-password"

    @pytest.mark.requirement("FR-060")
    def test_extracts_from_second_positional(self) -> None:
        """Test extracting from non-first positional arg."""

        def my_func(self: Any, name: str, path: str) -> None:
            pass

        result = _extract_secret_path(my_func, ("foo", "/secrets/db"), {}, "path")
        assert result == "/secrets/db"

    @pytest.mark.requirement("FR-060")
    def test_fallback_to_first_arg(self) -> None:
        """Test fallback to first arg when arg_name not found."""

        def my_func(self: Any, *args: Any) -> None:
            pass

        result = _extract_secret_path(my_func, ("fallback-value",), {}, "nonexistent")
        assert result == "fallback-value"

    @pytest.mark.requirement("FR-060")
    def test_returns_unknown_when_no_args(self) -> None:
        """Test that 'unknown' is returned when no args available."""

        def my_func(self: Any) -> None:
            pass

        result = _extract_secret_path(my_func, (), {}, "key")
        assert result == "unknown"

    @pytest.mark.requirement("FR-060")
    def test_kwargs_takes_precedence(self) -> None:
        """Test that kwargs takes precedence over positional args."""

        def my_func(self: Any, key: str) -> None:
            pass

        result = _extract_secret_path(my_func, ("positional-key",), {"key": "kwarg-key"}, "key")
        assert result == "kwarg-key"


class TestAuditSecretAccessDecorator:
    """Tests for audit_secret_access decorator."""

    @pytest.mark.requirement("FR-060")
    def test_logs_success_on_normal_return(self) -> None:
        """Test that successful calls are logged as success."""

        class MockPlugin:
            name = "test-plugin"
            namespace = "default"

            @audit_secret_access(AuditOperation.GET)
            def get_secret(self, key: str) -> str:
                return "secret-value"

        plugin = MockPlugin()

        with patch("floe_core.audit.decorator.get_audit_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            result = plugin.get_secret("db-password")

            assert result == "secret-value"
            mock_logger.log_success.assert_called_once()
            call_kwargs = mock_logger.log_success.call_args[1]
            assert call_kwargs["secret_path"] == "db-password"
            assert call_kwargs["operation"] == AuditOperation.GET
            assert call_kwargs["plugin_type"] == "test-plugin"
            assert call_kwargs["namespace"] == "default"

    @pytest.mark.requirement("FR-060")
    def test_logs_denied_on_permission_error(self) -> None:
        """Test that PermissionError is logged as denied."""

        class MockPlugin:
            name = "test-plugin"
            namespace = "default"

            @audit_secret_access(AuditOperation.GET)
            def get_secret(self, key: str) -> str:
                raise PermissionError("Access denied")

        plugin = MockPlugin()

        with patch("floe_core.audit.decorator.get_audit_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            with pytest.raises(PermissionError):
                plugin.get_secret("admin-secret")

            mock_logger.log_denied.assert_called_once()
            call_kwargs = mock_logger.log_denied.call_args[1]
            assert call_kwargs["secret_path"] == "admin-secret"
            assert call_kwargs["reason"] == "Access denied"

    @pytest.mark.requirement("FR-060")
    def test_logs_error_on_other_exception(self) -> None:
        """Test that other exceptions are logged as errors."""

        class MockPlugin:
            name = "test-plugin"
            namespace = "default"

            @audit_secret_access(AuditOperation.GET)
            def get_secret(self, key: str) -> str:
                raise ConnectionError("Backend unavailable")

        plugin = MockPlugin()

        with patch("floe_core.audit.decorator.get_audit_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            with pytest.raises(ConnectionError):
                plugin.get_secret("db-password")

            mock_logger.log_error.assert_called_once()
            call_kwargs = mock_logger.log_error.call_args[1]
            assert call_kwargs["secret_path"] == "db-password"
            assert call_kwargs["error"] == "Backend unavailable"

    @pytest.mark.requirement("FR-060")
    def test_custom_secret_path_arg(self) -> None:
        """Test custom secret_path_arg parameter."""

        class MockPlugin:
            name = "test-plugin"
            namespace = "default"

            @audit_secret_access(AuditOperation.SET, secret_path_arg="secret_name")
            def set_secret(self, secret_name: str, value: str) -> None:
                pass

        plugin = MockPlugin()

        with patch("floe_core.audit.decorator.get_audit_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            plugin.set_secret("custom-secret", "value")

            call_kwargs = mock_logger.log_success.call_args[1]
            assert call_kwargs["secret_path"] == "custom-secret"

    @pytest.mark.requirement("FR-060")
    def test_no_namespace_attr(self) -> None:
        """Test decorator when namespace_attr is None."""

        class MockPlugin:
            name = "test-plugin"

            @audit_secret_access(AuditOperation.GET, namespace_attr=None)
            def get_secret(self, key: str) -> str:
                return "value"

        plugin = MockPlugin()

        with patch("floe_core.audit.decorator.get_audit_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            plugin.get_secret("key")

            call_kwargs = mock_logger.log_success.call_args[1]
            assert call_kwargs["namespace"] is None

    @pytest.mark.requirement("FR-060")
    def test_uses_system_requester_when_not_available(self) -> None:
        """Test that 'system' is used when requester_id not available."""

        class MockPlugin:
            name = "test-plugin"
            namespace = "default"
            # No requester_id attribute

            @audit_secret_access(AuditOperation.GET)
            def get_secret(self, key: str) -> str:
                return "value"

        plugin = MockPlugin()

        with patch("floe_core.audit.decorator.get_audit_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            plugin.get_secret("key")

            call_kwargs = mock_logger.log_success.call_args[1]
            assert call_kwargs["requester_id"] == "system"

    @pytest.mark.requirement("FR-060")
    def test_uses_custom_requester_id(self) -> None:
        """Test that custom requester_id is used when available."""

        class MockPlugin:
            name = "test-plugin"
            namespace = "default"
            requester_id = "dagster-worker"

            @audit_secret_access(AuditOperation.GET)
            def get_secret(self, key: str) -> str:
                return "value"

        plugin = MockPlugin()

        with patch("floe_core.audit.decorator.get_audit_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            plugin.get_secret("key")

            call_kwargs = mock_logger.log_success.call_args[1]
            assert call_kwargs["requester_id"] == "dagster-worker"

    @pytest.mark.requirement("FR-060")
    def test_preserves_function_metadata(self) -> None:
        """Test that functools.wraps preserves function metadata."""

        class MockPlugin:
            name = "test-plugin"
            namespace = "default"

            @audit_secret_access(AuditOperation.GET)
            def get_secret(self, key: str) -> str:
                """Get a secret by key."""
                return "value"

        assert MockPlugin.get_secret.__name__ == "get_secret"
        assert MockPlugin.get_secret.__doc__ == "Get a secret by key."
