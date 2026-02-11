"""Unit tests for OpenTelemetry tracing helpers in floe_identity_keycloak.tracing.

Tests cover tracer initialization, span creation, attribute setting, error
handling, and credential sanitization for the Keycloak identity plugin.

Requirements Covered:
    - 6C-FR-020: Plugin-level tracing with identity_span context manager
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.trace import StatusCode

from floe_identity_keycloak.tracing import (
    ATTR_MULTI_TENANT,
    ATTR_OPERATION,
    ATTR_REALM,
    ATTR_TOKEN_TYPE,
    TRACER_NAME,
    get_tracer,
    identity_span,
)


class TestGetTracer:
    """Unit tests for get_tracer function."""

    @pytest.mark.requirement("6C-FR-020")
    def test_get_tracer_returns_tracer(self) -> None:
        """Test that get_tracer returns an OpenTelemetry tracer instance.

        Validates that the function returns a tracer from the factory with the
        correct tracer name for the Keycloak identity plugin.
        """
        with patch("floe_identity_keycloak.tracing._factory_get_tracer") as mock_factory:
            mock_tracer = MagicMock(spec=["start_as_current_span"])
            mock_factory.return_value = mock_tracer

            tracer = get_tracer()

            assert tracer is mock_tracer
            mock_factory.assert_called_once_with(TRACER_NAME)


class TestIdentitySpan:
    """Unit tests for identity_span context manager."""

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_creates_span_with_correct_name(self) -> None:
        """Test that identity_span creates a span named 'identity.{operation}'.

        Validates that the span name follows the 'identity.<operation>' convention
        and that the operation attribute is set correctly.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status", "set_attribute"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with identity_span(mock_tracer, "authenticate") as span:
            assert span is mock_span

        mock_tracer.start_as_current_span.assert_called_once()
        call_args = mock_tracer.start_as_current_span.call_args
        assert call_args[0][0] == "identity.authenticate"
        assert call_args[1]["attributes"][ATTR_OPERATION] == "authenticate"

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_sets_realm_attribute(self) -> None:
        """Test that identity_span includes the realm attribute when provided.

        Validates that the 'identity.realm' attribute is set in the span
        attributes when a realm value is passed.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with identity_span(mock_tracer, "validate_token", realm="floe-prod"):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        attributes = call_args[1]["attributes"]
        assert attributes[ATTR_REALM] == "floe-prod"

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_sets_multi_tenant_attribute(self) -> None:
        """Test that identity_span includes multi_tenant attribute when True.

        Validates that the 'identity.multi_tenant' attribute is set to True
        when multi_tenant=True is passed to the context manager.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with identity_span(
            mock_tracer, "validate_token_for_realm", realm="sales", multi_tenant=True
        ):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        attributes = call_args[1]["attributes"]
        assert attributes[ATTR_MULTI_TENANT] is True

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_excludes_multi_tenant_when_false(self) -> None:
        """Test that identity_span excludes multi_tenant when False (default).

        Validates that the 'identity.multi_tenant' attribute is NOT present
        when multi_tenant is False (default behavior).
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with identity_span(mock_tracer, "authenticate", realm="floe"):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        attributes = call_args[1]["attributes"]
        assert ATTR_MULTI_TENANT not in attributes

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_no_credentials_in_attributes(self) -> None:
        """Test that identity_span does not leak credentials into attributes.

        Validates that no token, password, secret, or PII values appear in
        span attributes. Only operational metadata should be present.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with identity_span(
            mock_tracer,
            "authenticate",
            realm="floe",
            extra_attributes={"identity.grant_type": "client_credentials"},
        ):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        attributes = call_args[1]["attributes"]

        # Ensure no sensitive keys that would hold actual secrets
        # Note: "token" in "identity.token_type" is metadata, not a real token.
        # We check that no key suggests it holds a secret *value*.
        forbidden_key_terms = {"password", "secret", "credential", "api_key"}
        for key in attributes:
            key_lower = key.lower()
            for term in forbidden_key_terms:
                assert term not in key_lower, (
                    f"Attribute key '{key}' contains forbidden term '{term}'"
                )

        # Ensure no attribute values look like actual secrets
        forbidden_value_patterns = {"bearer ", "eyj", "sk-", "ghp_", "xoxb-"}
        for value in attributes.values():
            if isinstance(value, str):
                value_lower = value.lower()
                for pattern in forbidden_value_patterns:
                    assert pattern not in value_lower, (
                        f"Attribute value '{value}' looks like a secret (matched '{pattern}')"
                    )

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_error_sanitized(self) -> None:
        """Test that identity_span sanitizes error messages containing credentials.

        Validates that when an exception with sensitive data is raised inside
        the span, the error message recorded in attributes is sanitized
        to redact credential values.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status", "set_attribute"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        # Raise with a message containing a credential pattern
        error_msg = "Connection failed: password=supersecret123 at host"  # pragma: allowlist secret

        with pytest.raises(RuntimeError, match="Connection failed"):
            with identity_span(mock_tracer, "authenticate", realm="floe"):
                raise RuntimeError(error_msg)

        # Verify the exception.message attribute was sanitized
        set_attr_calls = mock_span.set_attribute.call_args_list
        message_attrs = [c for c in set_attr_calls if c[0][0] == "exception.message"]
        assert len(message_attrs) == 1

        recorded_message = message_attrs[0][0][1]
        assert "supersecret123" not in recorded_message  # pragma: allowlist secret
        assert "<REDACTED>" in recorded_message

        # Verify exception.type is also set
        type_attrs = [c for c in set_attr_calls if c[0][0] == "exception.type"]
        assert len(type_attrs) == 1
        assert type_attrs[0][0][1] == "RuntimeError"

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_ok_status_on_success(self) -> None:
        """Test that identity_span sets OK status when no exception is raised.

        Validates that the span status is set to StatusCode.OK on successful
        completion of the context manager block.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status", "set_attribute"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with identity_span(mock_tracer, "validate_token", realm="floe"):
            pass

        mock_span.set_status.assert_called_once()
        status_arg = mock_span.set_status.call_args[0][0]
        assert status_arg.status_code == StatusCode.OK

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_error_status_on_exception(self) -> None:
        """Test that identity_span sets ERROR status when an exception is raised.

        Validates that the span status is set to StatusCode.ERROR and the
        description contains the exception class name.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status", "set_attribute"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        with pytest.raises(ValueError, match="bad input"):
            with identity_span(mock_tracer, "authenticate"):
                raise ValueError("bad input")

        mock_span.set_status.assert_called_once()
        status_arg = mock_span.set_status.call_args[0][0]
        assert status_arg.status_code == StatusCode.ERROR
        assert status_arg.description == "ValueError"

    @pytest.mark.requirement("6C-FR-020")
    def test_identity_span_extra_attributes_merged(self) -> None:
        """Test that extra_attributes are merged into span attributes.

        Validates that custom attributes provided via extra_attributes
        are included alongside the standard identity attributes.
        """
        mock_tracer = MagicMock(spec=["start_as_current_span"])
        mock_span = MagicMock(spec=["set_status"])
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

        extra = {"identity.grant_type": "client_credentials", "custom.flag": True}

        with identity_span(mock_tracer, "authenticate", extra_attributes=extra):
            pass

        call_args = mock_tracer.start_as_current_span.call_args
        attributes = call_args[1]["attributes"]

        assert attributes["identity.grant_type"] == "client_credentials"
        assert attributes["custom.flag"] is True
        assert attributes[ATTR_OPERATION] == "authenticate"


class TestConstants:
    """Unit tests for tracing constants definition."""

    @pytest.mark.requirement("6C-FR-020")
    def test_tracer_name_constant(self) -> None:
        """Test that TRACER_NAME is defined with correct value.

        Validates that the tracer name follows OpenTelemetry naming conventions
        for the Keycloak identity plugin.
        """
        assert TRACER_NAME == "floe.identity.keycloak"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_defined(self) -> None:
        """Test that all identity attribute constants are defined with correct values.

        Validates that all expected identity attribute name constants follow
        the 'identity.*' naming convention.
        """
        assert ATTR_OPERATION == "identity.operation"
        assert ATTR_REALM == "identity.realm"
        assert ATTR_MULTI_TENANT == "identity.multi_tenant"
        assert ATTR_TOKEN_TYPE == "identity.token_type"

    @pytest.mark.requirement("6C-FR-020")
    def test_attribute_constants_follow_otel_conventions(self) -> None:
        """Test that attribute constants follow OpenTelemetry naming conventions.

        Validates that attribute names use dot notation and the 'identity.'
        prefix as per the project's OTel attribute naming standard.
        """
        attributes = [ATTR_OPERATION, ATTR_REALM, ATTR_MULTI_TENANT, ATTR_TOKEN_TYPE]

        for attr in attributes:
            assert attr.startswith("identity."), f"{attr} should start with 'identity.'"
            assert "." in attr, f"{attr} should use dot notation"
