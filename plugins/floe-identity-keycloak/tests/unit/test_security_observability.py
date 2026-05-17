"""Security-sensitive observability tests for Keycloak identity plugin."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest
from floe_core.plugin_metadata import HealthState
from pydantic import SecretStr

from floe_identity_keycloak.config import KeycloakIdentityConfig
from floe_identity_keycloak.plugin import KeycloakIdentityPlugin


class _Span:
    def __init__(self, name: str, attributes: dict[str, Any] | None) -> None:
        self.name = name
        self.attributes = dict(attributes or {})

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: Any) -> None:
        self.status = status


class _SpanContext(AbstractContextManager[_Span]):
    def __init__(self, span: _Span) -> None:
        self._span = span

    def __enter__(self) -> _Span:
        return self._span

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _Tracer:
    def __init__(self) -> None:
        self.spans: list[_Span] = []

    def start_as_current_span(self, name: str, **kwargs: Any) -> _SpanContext:
        span = _Span(name, kwargs.get("attributes"))
        self.spans.append(span)
        return _SpanContext(span)


def _plugin() -> KeycloakIdentityPlugin:
    plugin = KeycloakIdentityPlugin(
        KeycloakIdentityConfig(
            server_url="https://keycloak.example.com",
            realm="floe",
            client_id="floe-client",
            client_secret=SecretStr("client-secret-value"),
        )
    )
    plugin._started = True
    plugin._client = Mock()
    return plugin


def _attrs_text(tracer: _Tracer) -> str:
    return repr([span.attributes for span in tracer.spans])


@pytest.mark.requirement("OBS-KEYCLOAK-SECURITY-001")
def test_authenticate_records_token_operation_without_credentials_or_token() -> None:
    tracer = _Tracer()
    plugin = _plugin()
    token = "eyJhbGciOi-sensitive-access-token"  # pragma: allowlist secret
    plugin._client.post.return_value = Mock(
        status_code=200,
        json=Mock(return_value={"access_token": token, "refresh_token": "refresh-token"}),
    )

    with patch("floe_identity_keycloak.plugin.get_tracer", return_value=tracer):
        assert (
            plugin.authenticate(
                {
                    "username": "person@example.com",
                    "password": "leaked-password",  # pragma: allowlist secret
                }
            )
            == token
        )

    attrs = tracer.spans[-1].attributes
    assert tracer.spans[-1].name == "identity.authenticate"
    assert attrs["identity.operation_type"] == "auth"
    assert attrs["identity.outcome"] == "success"
    text = _attrs_text(tracer)
    assert "person@example.com" not in text
    assert "leaked-password" not in text  # pragma: allowlist secret
    assert token not in text
    assert "refresh-token" not in text  # pragma: allowlist secret


@pytest.mark.requirement("OBS-KEYCLOAK-SECURITY-002")
def test_get_user_info_records_outcome_without_profile_or_pii_claims() -> None:
    tracer = _Tracer()
    plugin = _plugin()
    plugin._client.get.return_value = Mock(
        status_code=200,
        json=Mock(
            return_value={
                "sub": "subject-123",
                "email": "person@example.com",
                "name": "Private Person",
                "preferred_username": "private-person",
            }
        ),
    )

    with patch("floe_identity_keycloak.plugin.get_tracer", return_value=tracer):
        result = plugin.get_user_info("bearer-sensitive-token")  # pragma: allowlist secret

    assert result is not None
    attrs = tracer.spans[-1].attributes
    assert tracer.spans[-1].name == "identity.get_user_info"
    assert attrs["identity.operation_type"] == "user_info"
    assert attrs["identity.outcome"] == "success"
    text = _attrs_text(tracer)
    assert "person@example.com" not in text
    assert "Private Person" not in text
    assert "private-person" not in text
    assert "bearer-sensitive-token" not in text  # pragma: allowlist secret


@pytest.mark.requirement("OBS-KEYCLOAK-SECURITY-003")
def test_identity_failures_are_classified() -> None:
    tracer = _Tracer()
    plugin = _plugin()

    plugin._client.post.return_value = Mock(status_code=401, json=Mock(return_value={}))
    with patch("floe_identity_keycloak.plugin.get_tracer", return_value=tracer):
        assert plugin.authenticate({}) is None
    assert tracer.spans[-1].attributes["identity.error_type"] == "access_denied"

    plugin._client.get.return_value = Mock(status_code=404, json=Mock(return_value={}))
    with patch("floe_identity_keycloak.plugin.get_tracer", return_value=tracer):
        assert plugin.get_user_info("token") is None
    assert tracer.spans[-1].attributes["identity.error_type"] == "not_found"

    plugin._client.get.side_effect = httpx.TimeoutException("backend unavailable")
    with patch("floe_identity_keycloak.plugin.get_tracer", return_value=tracer):
        assert plugin.get_user_info("token") is None
    assert tracer.spans[-1].attributes["identity.error_type"] == "unavailable"

    with patch("floe_identity_keycloak.plugin.get_tracer", return_value=tracer):
        with pytest.raises(ValueError):
            plugin.authenticate({"username": "", "password": "x"})
    assert tracer.spans[-1].attributes["identity.error_type"] == "validation"


@pytest.mark.requirement("OBS-KEYCLOAK-SECURITY-004")
def test_health_check_sanitizes_provider_error_message() -> None:
    plugin = _plugin()
    plugin._client.get.side_effect = httpx.ConnectError(
        "https://keycloak.example.com/realms/floe?token=raw-token "
        "password=raw-password private_key=raw-key person@example.com"
    )

    status = plugin.health_check()

    assert status.state == HealthState.UNHEALTHY
    assert status.message == "Keycloak connection failed: unavailable"
    assert "raw-token" not in status.message
    assert "raw-password" not in status.message
    assert "raw-key" not in status.message
    assert "keycloak.example.com" not in status.message
    assert "person@example.com" not in status.message
