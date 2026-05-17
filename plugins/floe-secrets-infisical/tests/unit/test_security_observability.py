"""Security-sensitive observability tests for Infisical secrets plugin."""

from __future__ import annotations

import sys
from contextlib import AbstractContextManager
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from floe_secrets_infisical.config import InfisicalSecretsConfig
from floe_secrets_infisical.errors import (
    InfisicalAccessDeniedError,
    InfisicalBackendUnavailableError,
)
from floe_secrets_infisical.plugin import InfisicalSecretsPlugin


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


def _plugin() -> InfisicalSecretsPlugin:
    plugin = InfisicalSecretsPlugin(
        InfisicalSecretsConfig(
            client_id="client-id",
            client_secret=SecretStr("client-secret-value"),
            project_id="project",
            secret_path="/safe/path",
        )
    )
    plugin._authenticated = True
    plugin._client = Mock()
    return plugin


def _attrs_text(tracer: _Tracer) -> str:
    return repr([span.attributes for span in tracer.spans])


def _fake_infisical_client_module() -> object:
    def _options(**kwargs: Any) -> dict[str, Any]:
        return kwargs

    return SimpleNamespace(GetSecretOptions=_options)


def test_get_secret_records_success_without_secret_value() -> None:
    tracer = _Tracer()
    plugin = _plugin()
    secret_value = "infisical-secret-value-token"  # pragma: allowlist secret
    plugin._client.getSecret.return_value = Mock(secret_value=secret_value)

    with (
        patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer),
        patch.dict(sys.modules, {"infisical_client": _fake_infisical_client_module()}),
    ):
        assert plugin.get_secret("catalog-ref") == secret_value

    attrs = tracer.spans[-1].attributes
    assert tracer.spans[-1].name == "secrets.get_secret"
    assert attrs["secrets.operation_type"] == "get"
    assert attrs["secrets.outcome"] == "success"
    assert attrs["secrets.found"] is True
    assert secret_value not in _attrs_text(tracer)


def test_get_secret_classifies_access_denied_without_sensitive_reference() -> None:
    tracer = _Tracer()
    plugin = _plugin()
    plugin._client.getSecret.side_effect = RuntimeError(
        "403 forbidden access_token=leaked-token "  # pragma: allowlist secret
        "password=leaked-password"  # pragma: allowlist secret
    )

    with (
        patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer),
        patch.dict(sys.modules, {"infisical_client": _fake_infisical_client_module()}),
    ):
        with pytest.raises(InfisicalAccessDeniedError):
            plugin.get_secret(
                "db-password/private_key=leaked-private-key"  # pragma: allowlist secret
            )

    attrs = tracer.spans[-1].attributes
    assert attrs["secrets.outcome"] == "failure"
    assert attrs["secrets.error_type"] == "access_denied"
    assert "secrets.key_name" not in attrs
    text = _attrs_text(tracer)
    assert "leaked-token" not in text  # pragma: allowlist secret
    assert "leaked-password" not in text  # pragma: allowlist secret
    assert "leaked-private-key" not in text  # pragma: allowlist secret


def test_get_secret_access_denied_sanitizes_audit_and_public_exception() -> None:
    tracer = _Tracer()
    plugin = _plugin()
    plugin._audit_logger = Mock()
    plugin._client.getSecret.side_effect = RuntimeError(
        "401 unauthorized access_token=leaked-token "  # pragma: allowlist secret
        "password=leaked-password"  # pragma: allowlist secret
    )

    with (
        patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer),
        patch.dict(sys.modules, {"infisical_client": _fake_infisical_client_module()}),
    ):
        with pytest.raises(InfisicalAccessDeniedError) as exc_info:
            plugin.get_secret(
                "db-password/private_key=leaked-private-key"  # pragma: allowlist secret
            )

    attrs = tracer.spans[-1].attributes
    assert attrs["secrets.error_type"] == "access_denied"
    plugin._audit_logger.log_denied.assert_called_once()
    audit_kwargs = plugin._audit_logger.log_denied.call_args.kwargs
    assert audit_kwargs["secret_path"] == "<redacted>"
    assert audit_kwargs["reason"] == "access denied (401)"
    text = f"{audit_kwargs!r} {exc_info.value!s}"
    assert "leaked-token" not in text  # pragma: allowlist secret
    assert "leaked-password" not in text  # pragma: allowlist secret
    assert "leaked-private-key" not in text  # pragma: allowlist secret


def test_get_secret_classifies_not_found_unavailable_and_validation() -> None:
    tracer = _Tracer()
    plugin = _plugin()

    plugin._client.getSecret.side_effect = RuntimeError("404 not found")
    with (
        patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer),
        patch.dict(sys.modules, {"infisical_client": _fake_infisical_client_module()}),
    ):
        assert plugin.get_secret("catalog-ref") is None
    assert tracer.spans[-1].attributes["secrets.error_type"] == "not_found"

    plugin._client.getSecret.side_effect = RuntimeError("503 connection timeout")
    with (
        patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer),
        patch.dict(sys.modules, {"infisical_client": _fake_infisical_client_module()}),
    ):
        with pytest.raises(InfisicalBackendUnavailableError):
            plugin.get_secret("catalog-ref")
    assert tracer.spans[-1].attributes["secrets.error_type"] == "unavailable"

    with patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer):
        with pytest.raises(ValueError):
            plugin.get_secret("")
    assert tracer.spans[-1].attributes["secrets.error_type"] == "validation"


def test_set_secret_classifies_access_denied_and_unavailable_known_errors() -> None:
    tracer = _Tracer()
    plugin = _plugin()

    with (
        patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer),
        patch.object(
            plugin,
            "_create_or_update_secret",
            side_effect=InfisicalAccessDeniedError(
                secret_key="db-password",  # pragma: allowlist secret
                reason="403 password=leaked-password",  # pragma: allowlist secret
            ),
        ),
    ):
        with pytest.raises(InfisicalAccessDeniedError) as exc_info:
            plugin.set_secret(
                "db-password/private_key=leaked-private-key",  # pragma: allowlist secret
                "set-secret-value",  # pragma: allowlist secret
            )

    attrs = tracer.spans[-1].attributes
    assert attrs["secrets.operation_type"] == "set"
    assert attrs["secrets.outcome"] == "failure"
    assert attrs["secrets.error_type"] == "access_denied"
    text = f"{_attrs_text(tracer)} {exc_info.value!s}"
    assert "leaked-password" not in text  # pragma: allowlist secret
    assert "leaked-private-key" not in text  # pragma: allowlist secret

    with (
        patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer),
        patch.object(
            plugin,
            "_create_or_update_secret",
            side_effect=InfisicalBackendUnavailableError(
                reason="503 token=leaked-token"  # pragma: allowlist secret
            ),
        ),
    ):
        with pytest.raises(InfisicalBackendUnavailableError) as exc_info:
            plugin.set_secret("catalog-ref", "set-secret-value")  # pragma: allowlist secret

    attrs = tracer.spans[-1].attributes
    assert attrs["secrets.operation_type"] == "set"
    assert attrs["secrets.outcome"] == "failure"
    assert attrs["secrets.error_type"] == "unavailable"
    text = f"{_attrs_text(tracer)} {exc_info.value!s}"
    assert "set-secret-value" not in text  # pragma: allowlist secret
    assert "leaked-token" not in text  # pragma: allowlist secret


def test_set_secret_access_denied_sanitizes_log_audit_and_public_exception() -> None:
    tracer = _Tracer()
    plugin = _plugin()
    plugin._audit_logger = Mock()

    with (
        patch("floe_secrets_infisical.plugin.get_tracer", return_value=tracer),
        patch("floe_secrets_infisical.plugin.logger") as logger,
        patch.object(
            plugin,
            "_create_or_update_secret",
            side_effect=RuntimeError(
                "unauthorized access_token=leaked-token "  # pragma: allowlist secret
                "password=leaked-password"  # pragma: allowlist secret
            ),
        ),
    ):
        with pytest.raises(InfisicalAccessDeniedError) as exc_info:
            plugin.set_secret(
                "db-password/private_key=leaked-private-key",  # pragma: allowlist secret
                "set-secret-value",  # pragma: allowlist secret
            )

    attrs = tracer.spans[-1].attributes
    assert attrs["secrets.error_type"] == "access_denied"
    plugin._audit_logger.log_denied.assert_called_once()
    audit_kwargs = plugin._audit_logger.log_denied.call_args.kwargs
    assert audit_kwargs["secret_path"] == "<redacted>"
    assert audit_kwargs["reason"] == "access denied"
    logger.debug.assert_not_called()
    text = f"{audit_kwargs!r} {exc_info.value!s}"
    assert "leaked-token" not in text  # pragma: allowlist secret
    assert "leaked-password" not in text  # pragma: allowlist secret
    assert "leaked-private-key" not in text  # pragma: allowlist secret
    assert "set-secret-value" not in text  # pragma: allowlist secret
