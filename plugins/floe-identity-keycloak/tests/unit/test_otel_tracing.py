"""Unit tests for OpenTelemetry tracing integration in Keycloak plugin methods.

Task: T072
Requirements: OB-005 (OpenTelemetry tracing for authentication operations)

These tests verify that plugin methods (authenticate, validate_token,
validate_token_for_realm) correctly use the identity_span context manager
from the tracing module and work with NoOp tracers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr


class TestOTelTracingAvailability:
    """Tests for OTel tracing availability detection."""

    @pytest.mark.requirement("OB-005")
    def test_tracing_works_without_otel(self) -> None:
        """Test that plugin works when OpenTelemetry is not installed."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            # Should work even without OTel
            assert plugin._started is True
        finally:
            plugin.shutdown()


class TestAuthenticateTracing:
    """Tests for authenticate() method tracing."""

    @pytest.mark.requirement("OB-005")
    def test_authenticate_creates_span_when_otel_available(self) -> None:
        """Test that authenticate creates a span when OTel is available."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            # Mock the tracer
            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=None)

            # Mock HTTP response
            with patch.object(plugin._client, "post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"access_token": "test-token"}
                mock_post.return_value = mock_response

                with patch("floe_identity_keycloak.plugin.get_tracer", return_value=mock_tracer):
                    token = plugin.authenticate({})

                    assert token == "test-token"
                    mock_tracer.start_as_current_span.assert_called_once()
        finally:
            plugin.shutdown()

    @pytest.mark.requirement("OB-005")
    def test_authenticate_sets_span_attributes(self) -> None:
        """Test that authenticate sets proper span attributes."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="test-realm",
            client_id="my-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=None)

            with patch.object(plugin._client, "post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"access_token": "test-token"}
                mock_post.return_value = mock_response

                with patch("floe_identity_keycloak.plugin.get_tracer", return_value=mock_tracer):
                    plugin.authenticate({})

                    # Verify span was created with identity.authenticate name
                    call_args = mock_tracer.start_as_current_span.call_args
                    assert call_args[0][0] == "identity.authenticate"

                    # Verify initial attributes contain realm and grant_type
                    attributes = call_args[1]["attributes"]
                    assert attributes.get("identity.realm") == "test-realm"
                    assert attributes.get("identity.grant_type") == "client_credentials"

                    # Verify auth success attribute set on span
                    set_attribute_calls = mock_span.set_attribute.call_args_list
                    set_attrs = {call[0][0]: call[0][1] for call in set_attribute_calls}
                    assert set_attrs.get("identity.auth.success") is True
        finally:
            plugin.shutdown()


class TestValidateTokenTracing:
    """Tests for validate_token() method tracing."""

    @pytest.mark.requirement("OB-005")
    def test_validate_token_creates_span(self) -> None:
        """Test that validate_token creates a span when OTel is available."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=None)

            # Mock token validator
            mock_validator_result = MagicMock()
            mock_validator_result.valid = False
            mock_validator_result.error = "Invalid token"
            mock_validator_result.user_info = None

            with patch.object(
                plugin._token_validator, "validate", return_value=mock_validator_result
            ):
                with patch("floe_identity_keycloak.plugin.get_tracer", return_value=mock_tracer):
                    result = plugin.validate_token("invalid-token")

                    assert result.valid is False
                    mock_tracer.start_as_current_span.assert_called_once()

                    # Check span name uses new identity prefix
                    call_args = mock_tracer.start_as_current_span.call_args
                    assert call_args[0][0] == "identity.validate_token"
        finally:
            plugin.shutdown()


class TestValidateTokenForRealmTracing:
    """Tests for validate_token_for_realm() method tracing."""

    @pytest.mark.requirement("OB-005")
    def test_validate_token_for_realm_sets_multi_tenant_attribute(self) -> None:
        """Test that validate_token_for_realm sets multi_tenant attribute."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="default-realm",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=None)

            # Mock realm validator
            mock_validator = MagicMock()
            mock_result = MagicMock()
            mock_result.valid = False
            mock_result.error = "Invalid"
            mock_result.user_info = None
            mock_validator.validate.return_value = mock_result

            with patch.object(
                plugin, "_get_or_create_realm_validator", return_value=mock_validator
            ):
                with patch("floe_identity_keycloak.plugin.get_tracer", return_value=mock_tracer):
                    plugin.validate_token_for_realm("token", "other-realm")

                    # Verify span attributes include realm and multi_tenant
                    call_args = mock_tracer.start_as_current_span.call_args
                    attributes = call_args[1]["attributes"]

                    assert attributes.get("identity.realm") == "other-realm"
                    assert attributes.get("identity.multi_tenant") is True
        finally:
            plugin.shutdown()


class TestTracingWithNoOpTracer:
    """Tests for graceful operation with NoOpTracer (when OTel not configured).

    Note: The SafeTracerFactory always returns a tracer (NoOpTracer if OTel init fails).
    These tests verify functionality works regardless of tracing configuration.
    """

    @pytest.mark.requirement("OB-005")
    def test_authenticate_works_with_noop_tracer(self) -> None:
        """Test that authenticate works with NoOpTracer (no tracing configured)."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            with patch.object(plugin._client, "post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"access_token": "test-token"}
                mock_post.return_value = mock_response

                # No need to patch get_tracer - the real factory handles this gracefully
                token = plugin.authenticate({})

                assert token == "test-token"
        finally:
            plugin.shutdown()

    @pytest.mark.requirement("OB-005")
    def test_validate_token_works_with_noop_tracer(self) -> None:
        """Test that validate_token works with NoOpTracer (no tracing configured)."""
        from floe_identity_keycloak import (
            KeycloakIdentityConfig,
            KeycloakIdentityPlugin,
        )

        config = KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="test-client",
            client_secret=SecretStr("test-secret"),
        )

        plugin = KeycloakIdentityPlugin(config=config)
        plugin.startup()

        try:
            mock_validator_result = MagicMock()
            mock_validator_result.valid = False
            mock_validator_result.error = "Test error"
            mock_validator_result.user_info = None

            with patch.object(
                plugin._token_validator, "validate", return_value=mock_validator_result
            ):
                # No need to patch get_tracer - the real factory handles this gracefully
                result = plugin.validate_token("test-token")

                assert result.valid is False
                assert result.error == "Test error"
        finally:
            plugin.shutdown()
