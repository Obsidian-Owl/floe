"""Security-sensitive observability tests for K8s secrets plugin."""

from __future__ import annotations

import base64
from contextlib import AbstractContextManager
from typing import Any
from unittest.mock import Mock, patch

import pytest

from floe_secrets_k8s.errors import SecretAccessDeniedError, SecretBackendUnavailableError
from floe_secrets_k8s.plugin import K8sSecretsPlugin


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


def _plugin_with_api(api_exception_type: type[Exception]) -> K8sSecretsPlugin:
    plugin = K8sSecretsPlugin()
    plugin._client = Mock()
    plugin._client.rest = Mock()
    plugin._client.rest.ApiException = api_exception_type
    plugin._api = Mock()
    return plugin


def _api_exception(api_exception_type: type[Exception], status: int, message: str) -> Exception:
    class ApiException(api_exception_type):
        pass

    exc = ApiException(message)
    exc.status = status
    return exc


def _attrs_text(tracer: _Tracer) -> str:
    return repr([span.attributes for span in tracer.spans])


def test_get_secret_records_success_without_secret_value() -> None:
    tracer = _Tracer()
    plugin = _plugin_with_api(type("ApiException", (Exception,), {}))
    secret_value = "plain-secret-value-token"  # pragma: allowlist secret
    encoded = base64.b64encode(secret_value.encode()).decode()
    plugin._api.read_namespaced_secret.return_value = Mock(data={"value": encoded})

    with patch("floe_secrets_k8s.plugin.get_tracer", return_value=tracer):
        assert plugin.get_secret("catalog-ref") == secret_value

    attrs = tracer.spans[-1].attributes
    assert tracer.spans[-1].name == "secrets.get_secret"
    assert attrs["secrets.operation_type"] == "get"
    assert attrs["secrets.outcome"] == "success"
    assert attrs["secrets.found"] is True
    assert secret_value not in _attrs_text(tracer)


def test_get_secret_classifies_access_denied_without_sensitive_reference() -> None:
    tracer = _Tracer()
    api_exception_type = type("ApiException", (Exception,), {})
    plugin = _plugin_with_api(api_exception_type)
    exc = _api_exception(
        api_exception_type,
        403,
        "forbidden token=leaked-session-token password=leaked-password",  # pragma: allowlist secret
    )
    plugin._api.read_namespaced_secret.side_effect = exc

    with patch("floe_secrets_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(SecretAccessDeniedError):
            plugin.get_secret(
                "db-password/private_key=leaked-private-key"  # pragma: allowlist secret
            )

    attrs = tracer.spans[-1].attributes
    assert attrs["secrets.outcome"] == "failure"
    assert attrs["secrets.error_type"] == "access_denied"
    text = _attrs_text(tracer)
    assert "leaked-session-token" not in text  # pragma: allowlist secret
    assert "leaked-password" not in text  # pragma: allowlist secret
    assert "leaked-private-key" not in text  # pragma: allowlist secret
    assert "secrets.key_name" not in attrs


def test_get_secret_classifies_not_found_unavailable_and_validation() -> None:
    tracer = _Tracer()
    api_exception_type = type("ApiException", (Exception,), {})
    plugin = _plugin_with_api(api_exception_type)

    plugin._api.read_namespaced_secret.side_effect = _api_exception(
        api_exception_type, 404, "not found"
    )
    with patch("floe_secrets_k8s.plugin.get_tracer", return_value=tracer):
        assert plugin.get_secret("catalog-ref") is None
    assert tracer.spans[-1].attributes["secrets.error_type"] == "not_found"

    plugin._api.read_namespaced_secret.side_effect = _api_exception(
        api_exception_type, 503, "unavailable"
    )
    with patch("floe_secrets_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(SecretBackendUnavailableError):
            plugin.get_secret("catalog-ref")
    assert tracer.spans[-1].attributes["secrets.error_type"] == "unavailable"

    with patch("floe_secrets_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(ValueError):
            plugin.get_secret("")
    assert tracer.spans[-1].attributes["secrets.error_type"] == "validation"
