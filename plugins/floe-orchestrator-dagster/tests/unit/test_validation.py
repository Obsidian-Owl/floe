"""Unit tests for connection validation in DagsterOrchestratorPlugin.

These tests verify the validate_connection() method handles various
connection scenarios correctly using mocked HTTP responses.

Note: @pytest.mark.requirement markers are used for traceability to spec.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from floe_core.plugins.orchestrator import ValidationResult

if TYPE_CHECKING:
    from collections.abc import Generator

    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


@pytest.fixture
def mock_httpx_client():
    """Factory fixture for mocked httpx.Client."""
    @contextmanager
    def _make(status_code: int = 200, side_effect: Exception | None = None) -> Generator[MagicMock, None, None]:
        with patch("httpx.Client") as mock_cls:
            mock_response = MagicMock(status_code=status_code)
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            if side_effect:
                mock_client.post.side_effect = side_effect
            else:
                mock_client.post.return_value = mock_response
            mock_cls.return_value = mock_client
            yield mock_client
    return _make


class TestValidateConnectionSuccess:
    """Test successful connection validation.

    Validates FR-010: System MUST validate connectivity to Dagster service.
    """

    @pytest.mark.requirement("FR-010")
    def test_validate_connection_returns_validation_result(
        self, dagster_plugin: DagsterOrchestratorPlugin, mock_httpx_client
    ) -> None:
        """Test validate_connection returns ValidationResult type."""
        with mock_httpx_client():
            result = dagster_plugin.validate_connection("http://localhost:3000")
            assert isinstance(result, ValidationResult)

    @pytest.mark.requirement("FR-010")
    def test_validate_connection_success_status(
        self, dagster_plugin: DagsterOrchestratorPlugin, mock_httpx_client
    ) -> None:
        """Test validate_connection returns success=True on 200 response."""
        with mock_httpx_client():
            result = dagster_plugin.validate_connection("http://localhost:3000")
            assert result.success is True

    def test_validate_connection_success_message(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection returns appropriate success message."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert "Successfully connected" in result.message

    def test_validate_connection_success_no_errors(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection returns empty errors list on success."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert result.errors == []

    def test_validate_connection_posts_to_graphql_endpoint(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection posts to /graphql endpoint."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            dagster_plugin.validate_connection("http://localhost:3000")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://localhost:3000/graphql"

    def test_validate_connection_sends_typename_query(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection sends __typename introspection query."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            dagster_plugin.validate_connection("http://localhost:3000")

            call_args = mock_client.post.call_args
            assert call_args[1]["json"] == {"query": "{ __typename }"}


class TestValidateConnectionHTTPErrors:
    """Test connection validation with HTTP errors.

    Validates FR-011: System MUST return actionable error messages.
    """

    def test_validate_connection_http_404(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test validate_connection handles 404 Not Found."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert result.success is False
            assert "404" in result.message

    def test_validate_connection_http_500(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test validate_connection handles 500 Internal Server Error."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert result.success is False
            assert "500" in result.message

    def test_validate_connection_http_error_has_actionable_message(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test HTTP errors include actionable guidance."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert len(result.errors) == 1
            assert "Ensure Dagster webserver is running" in result.errors[0]


class TestValidateConnectionTimeout:
    """Test connection validation timeout handling.

    Validates FR-012: System MUST complete validation within timeout.
    """

    def test_validate_connection_timeout_returns_failure(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection handles timeout gracefully."""
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000", timeout=1.0)

            assert result.success is False

    def test_validate_connection_timeout_message_includes_duration(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test timeout error message includes configured timeout duration."""
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000", timeout=5.0)

            assert "5.0" in result.message

    def test_validate_connection_timeout_has_actionable_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test timeout error includes actionable guidance."""
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert len(result.errors) == 1
            assert "network connectivity" in result.errors[0].lower()

    def test_validate_connection_uses_configured_timeout(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection passes timeout to HTTP client."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            dagster_plugin.validate_connection("http://localhost:3000", timeout=15.0)

            mock_client_class.assert_called_once_with(timeout=15.0)


class TestValidateConnectionConnectError:
    """Test connection validation with connection errors.

    Validates FR-011: System MUST return actionable error messages.
    """

    def test_validate_connection_connect_error_returns_failure(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection handles connection refused."""
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert result.success is False

    def test_validate_connection_connect_error_message(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test connection error has descriptive message."""
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert "Failed to connect" in result.message

    def test_validate_connection_connect_error_has_actionable_guidance(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test connection error includes URL in guidance."""
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://dagster.example.com:3000")

            assert len(result.errors) == 1
            assert "http://dagster.example.com:3000" in result.errors[0]


class TestValidateConnectionURLHandling:
    """Test connection validation URL handling."""

    def test_validate_connection_default_url(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection uses localhost:3000 as default."""
        with patch("httpx.Client") as mock_client_class:
            with patch.dict("os.environ", {}, clear=True):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client.post.return_value = mock_response
                mock_client_class.return_value = mock_client

                dagster_plugin.validate_connection()

                call_args = mock_client.post.call_args
                assert call_args[0][0] == "http://localhost:3000/graphql"

    def test_validate_connection_env_url(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test validate_connection uses DAGSTER_URL from environment."""
        with patch("httpx.Client") as mock_client_class:
            with patch.dict("os.environ", {"DAGSTER_URL": "http://dagster.local:8080"}):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client.post.return_value = mock_response
                mock_client_class.return_value = mock_client

                dagster_plugin.validate_connection()

                call_args = mock_client.post.call_args
                assert call_args[0][0] == "http://dagster.local:8080/graphql"

    def test_validate_connection_explicit_url_overrides_env(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test explicit URL parameter overrides environment variable."""
        with patch("httpx.Client") as mock_client_class:
            with patch.dict("os.environ", {"DAGSTER_URL": "http://dagster.local:8080"}):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client = MagicMock()
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client.post.return_value = mock_response
                mock_client_class.return_value = mock_client

                dagster_plugin.validate_connection("http://explicit.url:9000")

                call_args = mock_client.post.call_args
                assert call_args[0][0] == "http://explicit.url:9000/graphql"

    def test_validate_connection_strips_trailing_slash(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection handles URLs with trailing slash."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            dagster_plugin.validate_connection("http://localhost:3000/")

            call_args = mock_client.post.call_args
            # Should not have double slash
            assert call_args[0][0] == "http://localhost:3000/graphql"


class TestValidateConnectionDefaultTimeout:
    """Test connection validation default timeout behavior."""

    def test_validate_connection_default_timeout_is_10_seconds(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test default timeout is 10 seconds."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            dagster_plugin.validate_connection("http://localhost:3000")

            mock_client_class.assert_called_once_with(timeout=10.0)


class TestValidateConnectionUnexpectedError:
    """Test connection validation with unexpected errors."""

    def test_validate_connection_unexpected_error_returns_failure(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection handles unexpected exceptions."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = RuntimeError("Unexpected error")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert result.success is False

    def test_validate_connection_unexpected_error_message(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test unexpected error message is informative."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = RuntimeError("Unexpected error")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert "Unexpected error" in result.message

    def test_validate_connection_unexpected_error_in_errors_list(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test unexpected error details are in errors list."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = RuntimeError("Something went wrong")
            mock_client_class.return_value = mock_client

            result = dagster_plugin.validate_connection("http://localhost:3000")

            assert len(result.errors) == 1
            assert "Something went wrong" in result.errors[0]
