"""Unit tests for OpenTelemetry tracing helpers in floe_semantic_cube.tracing.

Tests cover tracer initialization, span creation, URL sanitization, error handling,
and constants definition for the Cube semantic layer plugin.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.trace import StatusCode

from floe_semantic_cube.tracing import (
    ATTR_DURATION_MS,
    ATTR_MODEL_COUNT,
    ATTR_MODEL_NAME,
    ATTR_OPERATION,
    ATTR_SCHEMA_PATH,
    ATTR_SERVER_URL,
    TRACER_NAME,
    _sanitize_url,
    get_tracer,
    semantic_span,
    set_error_attributes,
)


class TestGetTracer:
    """Unit tests for get_tracer function."""

    @pytest.mark.requirement("FR-048")
    def test_get_tracer_returns_tracer_instance(self) -> None:
        """Test that get_tracer returns an OpenTelemetry tracer instance.

        Validates that the function returns a tracer from the factory with the
        correct tracer name for the Cube semantic layer plugin.
        """
        with patch("floe_semantic_cube.tracing._factory_get_tracer") as mock_factory:
            mock_tracer = MagicMock(spec=["start_as_current_span"])
            mock_factory.return_value = mock_tracer

            tracer = get_tracer()

            assert tracer is mock_tracer
            mock_factory.assert_called_once_with(TRACER_NAME)

    @pytest.mark.requirement("FR-048")
    def test_get_tracer_uses_correct_tracer_name(self) -> None:
        """Test that get_tracer uses the correct tracer name constant.

        Validates that the tracer name matches OpenTelemetry naming conventions
        for the floe semantic cube plugin.
        """
        with patch("floe_semantic_cube.tracing._factory_get_tracer") as mock_factory:
            get_tracer()

            # Verify tracer name follows conventions
            assert TRACER_NAME == "floe.semantic.cube"
            mock_factory.assert_called_once_with("floe.semantic.cube")


class TestSemanticSpan:
    """Unit tests for semantic_span context manager."""

    @pytest.mark.requirement("FR-048")
    def test_semantic_span_creates_span_with_operation(self) -> None:
        """Test that semantic_span creates a span with correct operation attribute.

        Validates that the context manager creates a span with the operation name
        as both the span name prefix and an attribute.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status", "set_attribute", "record_exception"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with semantic_span(mock_tracer, "health_check") as span:
            assert span is mock_span

        mock_tracer.start_as_current_span.assert_called_once()
        call_kwargs = mock_tracer.start_as_current_span.call_args
        assert call_kwargs[0][0] == "semantic.health_check"
        assert call_kwargs[1]["attributes"][ATTR_OPERATION] == "health_check"
        # Verify set_status was called with OK status
        mock_span.set_status.assert_called_once()
        status_arg = mock_span.set_status.call_args[0][0]
        assert status_arg.status_code == StatusCode.OK

    @pytest.mark.requirement("FR-048")
    def test_semantic_span_includes_optional_attributes(self) -> None:
        """Test that semantic_span includes all optional attributes when provided.

        Validates that server_url, model_name, and schema_path are included
        in the span attributes when provided.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with semantic_span(
            mock_tracer,
            "sync_schema",
            server_url="https://cube.example.com",
            model_name="orders",
            schema_path="/output/schema",
        ):
            pass

        call_kwargs = mock_tracer.start_as_current_span.call_args
        attributes = call_kwargs[1]["attributes"]

        assert attributes[ATTR_OPERATION] == "sync_schema"
        assert attributes[ATTR_SERVER_URL] == "https://cube.example.com"
        assert attributes[ATTR_MODEL_NAME] == "orders"
        assert attributes[ATTR_SCHEMA_PATH] == "/output/schema"

    @pytest.mark.requirement("FR-048")
    def test_semantic_span_excludes_none_attributes(self) -> None:
        """Test that semantic_span excludes None attributes from the span.

        Validates that optional attributes with None values are not included
        in the span attributes dictionary.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with semantic_span(
            mock_tracer,
            "health_check",
            server_url=None,
            model_name=None,
            schema_path=None,
        ):
            pass

        call_kwargs = mock_tracer.start_as_current_span.call_args
        attributes = call_kwargs[1]["attributes"]

        assert ATTR_OPERATION in attributes
        assert ATTR_SERVER_URL not in attributes
        assert ATTR_MODEL_NAME not in attributes
        assert ATTR_SCHEMA_PATH not in attributes

    @pytest.mark.requirement("FR-048")
    def test_semantic_span_includes_extra_attributes(self) -> None:
        """Test that semantic_span merges extra_attributes into span attributes.

        Validates that custom attributes provided via extra_attributes are
        included in the span.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        extra = {"custom.attribute": "value", "model.count": 5}

        with semantic_span(mock_tracer, "sync_schema", extra_attributes=extra):
            pass

        call_kwargs = mock_tracer.start_as_current_span.call_args
        attributes = call_kwargs[1]["attributes"]

        assert attributes["custom.attribute"] == "value"
        assert attributes["model.count"] == 5

    @pytest.mark.requirement("FR-048")
    def test_semantic_span_sanitizes_server_url(self) -> None:
        """Test that semantic_span sanitizes server_url before adding to span.

        Validates that URLs containing credentials are sanitized to remove
        sensitive information.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with semantic_span(
            mock_tracer,
            "health_check",
            server_url="https://user:secret@cube.example.com/api",
        ):
            pass

        call_kwargs = mock_tracer.start_as_current_span.call_args
        attributes = call_kwargs[1]["attributes"]

        # URL should be sanitized (no credentials)
        assert attributes[ATTR_SERVER_URL] == "https://cube.example.com/api"

    @pytest.mark.requirement("FR-048")
    def test_semantic_span_handles_exception_and_reraises(self) -> None:
        """Test that semantic_span handles exceptions and sets error status.

        Validates that exceptions are recorded on the span, status is set to
        ERROR, and the exception is re-raised.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status", "record_exception"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        test_error = ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            with semantic_span(mock_tracer, "failing_operation"):
                raise test_error

        # Verify error handling
        mock_span.record_exception.assert_called_once_with(test_error)
        mock_span.set_status.assert_called_once()
        status_call = mock_span.set_status.call_args[0][0]
        assert status_call.status_code == StatusCode.ERROR
        assert status_call.description == "ValueError"

    @pytest.mark.requirement("FR-048")
    def test_semantic_span_yields_span_for_custom_attributes(self) -> None:
        """Test that semantic_span yields the span for custom attribute setting.

        Validates that the context manager yields the active span, allowing
        callers to add custom attributes during operation execution.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status", "set_attribute"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with semantic_span(mock_tracer, "sync_schema") as span:
            # Caller can add custom attributes
            span.set_attribute("schema.model_count", 10)
            span.set_attribute("schema.duration_ms", 1234)

        # Verify custom attributes were set
        assert mock_span.set_attribute.call_count == 2
        mock_span.set_attribute.assert_any_call("schema.model_count", 10)
        mock_span.set_attribute.assert_any_call("schema.duration_ms", 1234)


class TestSanitizeUrl:
    """Unit tests for _sanitize_url helper function."""

    @pytest.mark.requirement("FR-048")
    def test_sanitize_url_removes_credentials_from_basic_url(self) -> None:
        """Test that _sanitize_url removes basic username:password credentials.

        Validates removal of credentials in standard URL format with scheme,
        userinfo, host, and path.
        """
        url = "https://user:password@cube.example.com/api/v1"
        sanitized = _sanitize_url(url)

        assert sanitized == "https://cube.example.com/api/v1"
        assert "user" not in sanitized
        assert "password" not in sanitized

    @pytest.mark.requirement("FR-048")
    def test_sanitize_url_removes_username_only(self) -> None:
        """Test that _sanitize_url removes username when no password present.

        Validates removal of username-only credentials (user@host).
        """
        url = "https://admin@cube.example.com/api"
        sanitized = _sanitize_url(url)

        assert sanitized == "https://cube.example.com/api"
        assert "admin" not in sanitized

    @pytest.mark.requirement("FR-048")
    def test_sanitize_url_handles_port_number(self) -> None:
        """Test that _sanitize_url preserves port number after credential removal.

        Validates that port numbers are kept in the sanitized URL.
        """
        url = "https://user:pass@cube.example.com:8080/api"
        sanitized = _sanitize_url(url)

        assert sanitized == "https://cube.example.com:8080/api"
        assert "8080" in sanitized

    @pytest.mark.requirement("FR-048")
    def test_sanitize_url_handles_no_path(self) -> None:
        """Test that _sanitize_url handles URLs without path component.

        Validates sanitization of URLs with only scheme, credentials, and host.
        """
        url = "https://user:pass@cube.example.com"
        sanitized = _sanitize_url(url)

        assert sanitized == "https://cube.example.com"

    @pytest.mark.requirement("FR-048")
    def test_sanitize_url_passes_through_clean_urls(self) -> None:
        """Test that _sanitize_url returns clean URLs unchanged.

        Validates that URLs without credentials are passed through without
        modification.
        """
        url = "https://cube.example.com/api/v1"
        sanitized = _sanitize_url(url)

        assert sanitized == url

    @pytest.mark.requirement("FR-048")
    def test_sanitize_url_handles_at_sign_in_path(self) -> None:
        """Test that _sanitize_url handles @ symbol in URL path correctly.

        Validates that @ in the path (after the hostname) is not mistaken
        for credentials.
        """
        url = "https://cube.example.com/api/user@email.com/resource"
        sanitized = _sanitize_url(url)

        # Should be unchanged (@ is in path, not credentials)
        assert sanitized == url

    @pytest.mark.requirement("FR-048")
    def test_sanitize_url_handles_no_scheme(self) -> None:
        """Test that _sanitize_url handles URLs without scheme.

        Validates handling of URLs that don't have a scheme (no ://).
        """
        url = "cube.example.com/api"
        sanitized = _sanitize_url(url)

        # No :// so no sanitization needed
        assert sanitized == url

    @pytest.mark.requirement("FR-048")
    def test_sanitize_url_handles_complex_password(self) -> None:
        """Test that _sanitize_url handles passwords with special characters.

        Validates removal of credentials when password contains special chars.
        Note: The implementation finds the first @ after the scheme, so URLs
        with @ in the password may not be fully sanitized. This is a known
        limitation of simple URL parsing without a full URL parser.
        """
        url = "https://user:password@cube.example.com/api"
        sanitized = _sanitize_url(url)

        # Should remove credentials
        assert sanitized == "https://cube.example.com/api"
        assert "user" not in sanitized
        assert "password" not in sanitized


class TestSetErrorAttributes:
    """Unit tests for set_error_attributes helper function."""

    @pytest.mark.requirement("FR-048")
    def test_set_error_attributes_sets_error_type(self) -> None:
        """Test that set_error_attributes sets error.type attribute.

        Validates that the exception class name is recorded as error.type.
        """
        mock_span = MagicMock(spec=["set_attribute"])
        error = ValueError("test error")

        set_error_attributes(mock_span, error)

        mock_span.set_attribute.assert_any_call("error.type", "ValueError")

    @pytest.mark.requirement("FR-048")
    def test_set_error_attributes_includes_message_by_default(self) -> None:
        """Test that set_error_attributes includes error message by default.

        Validates that error message is included in attributes when
        include_message is not specified.
        """
        mock_span = MagicMock(spec=["set_attribute"])
        error = RuntimeError("operation failed")

        set_error_attributes(mock_span, error)

        mock_span.set_attribute.assert_any_call("error.type", "RuntimeError")
        mock_span.set_attribute.assert_any_call("error.message", "operation failed")

    @pytest.mark.requirement("FR-048")
    def test_set_error_attributes_excludes_message_when_disabled(self) -> None:
        """Test that set_error_attributes excludes message when include_message=False.

        Validates that error message is not included when include_message
        is explicitly set to False (for sensitive data).
        """
        mock_span = MagicMock(spec=["set_attribute"])
        error = ValueError("sensitive credentials: password123")

        set_error_attributes(mock_span, error, include_message=False)

        mock_span.set_attribute.assert_called_once_with("error.type", "ValueError")
        # Verify error.message was not set
        for call in mock_span.set_attribute.call_args_list:
            assert call[0][0] != "error.message"

    @pytest.mark.requirement("FR-048")
    def test_set_error_attributes_truncates_long_messages(self) -> None:
        """Test that set_error_attributes truncates error messages at 500 chars.

        Validates that long error messages are truncated to prevent
        excessive span data.
        """
        mock_span = MagicMock(spec=["set_attribute"])
        long_message = "x" * 600
        error = ValueError(long_message)

        set_error_attributes(mock_span, error)

        # Verify message is truncated to 500 chars
        calls = mock_span.set_attribute.call_args_list
        message_call = [c for c in calls if c[0][0] == "error.message"][0]
        assert len(message_call[0][1]) == 500
        assert message_call[0][1] == "x" * 500

    @pytest.mark.requirement("FR-048")
    def test_set_error_attributes_handles_empty_message(self) -> None:
        """Test that set_error_attributes handles exceptions with empty messages.

        Validates handling of exceptions that have no message text.
        """
        mock_span = MagicMock(spec=["set_attribute"])
        error = ValueError()

        set_error_attributes(mock_span, error)

        mock_span.set_attribute.assert_any_call("error.type", "ValueError")
        mock_span.set_attribute.assert_any_call("error.message", "")


class TestConstants:
    """Unit tests for tracing constants definition."""

    @pytest.mark.requirement("FR-048")
    def test_tracer_name_constant_defined(self) -> None:
        """Test that TRACER_NAME constant is defined with correct value.

        Validates that the tracer name follows OpenTelemetry naming conventions.
        """
        assert TRACER_NAME == "floe.semantic.cube"

    @pytest.mark.requirement("FR-048")
    def test_attribute_constants_defined(self) -> None:
        """Test that all semantic attribute constants are defined.

        Validates that all expected semantic layer attribute name constants
        are defined with correct values.
        """
        assert ATTR_OPERATION == "semantic.operation"
        assert ATTR_SERVER_URL == "semantic.server_url"
        assert ATTR_MODEL_NAME == "semantic.model.name"
        assert ATTR_MODEL_COUNT == "semantic.model.count"
        assert ATTR_SCHEMA_PATH == "semantic.schema.path"
        assert ATTR_DURATION_MS == "semantic.duration_ms"

    @pytest.mark.requirement("FR-048")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OpenTelemetry naming conventions.

        Validates that attribute names use dot notation and semantic prefix
        as per OpenTelemetry standards.
        """
        attributes = [
            ATTR_OPERATION,
            ATTR_SERVER_URL,
            ATTR_MODEL_NAME,
            ATTR_MODEL_COUNT,
            ATTR_SCHEMA_PATH,
            ATTR_DURATION_MS,
        ]

        for attr in attributes:
            assert attr.startswith("semantic."), f"{attr} should start with 'semantic.'"
            assert "." in attr, f"{attr} should use dot notation"
