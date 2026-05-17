"""Security-sensitive observability tests for K8s network security plugin."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any
from unittest.mock import patch

import pytest

from floe_network_security_k8s.plugin import K8sNetworkSecurityPlugin


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


def _attrs_text(tracer: _Tracer) -> str:
    return repr([span.attributes for span in tracer.spans])


def test_default_deny_records_resource_metadata_without_yaml_body() -> None:
    tracer = _Tracer()
    plugin = K8sNetworkSecurityPlugin()

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        policies = plugin.generate_default_deny_policies("floe-jobs")

    attrs = tracer.spans[-1].attributes
    assert policies[0]["kind"] == "NetworkPolicy"
    assert attrs["security.resource_kind"] == "NetworkPolicy"
    assert attrs["security.namespace"] == "floe-jobs"
    assert attrs["security.policy_type"] == "NetworkPolicy"
    assert attrs["security.status"] == "success"
    assert "security.duration_ms" in attrs
    assert "apiVersion" not in _attrs_text(tracer)
    assert "policyTypes" not in _attrs_text(tracer)


def test_network_generation_does_not_emit_credential_like_policy_body() -> None:
    tracer = _Tracer()
    plugin = K8sNetworkSecurityPlugin()

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        rule = plugin.generate_k8s_api_egress_rule("10.0.0.1/32", strict_mode=True)

    assert rule["to"][0]["ipBlock"]["cidr"].startswith("10.0.0.1")
    text = _attrs_text(tracer)
    assert "10.0.0.1" not in text


def test_generation_failures_are_classified() -> None:
    tracer = _Tracer()
    plugin = K8sNetworkSecurityPlugin()

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(ValueError):
            plugin.generate_default_deny_policies("")
    assert tracer.spans[-1].attributes["security.error_type"] == "validation"

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(PermissionError):
            plugin._record_generation(
                operation="generate_network_policy",
                policy_type="NetworkPolicy",
                resource_kind="NetworkPolicy",
                namespace="floe-jobs",
                action=lambda: (_ for _ in ()).throw(PermissionError("access denied")),
            )
    assert tracer.spans[-1].attributes["security.error_type"] == "access_denied"

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(FileNotFoundError):
            plugin._record_generation(
                operation="generate_network_policy",
                policy_type="NetworkPolicy",
                resource_kind="NetworkPolicy",
                namespace="floe-jobs",
                action=lambda: (_ for _ in ()).throw(FileNotFoundError("missing")),
            )
    assert tracer.spans[-1].attributes["security.error_type"] == "not_found"

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(TimeoutError):
            plugin._record_generation(
                operation="generate_network_policy",
                policy_type="NetworkPolicy",
                resource_kind="NetworkPolicy",
                namespace="floe-jobs",
                action=lambda: (_ for _ in ()).throw(TimeoutError("api unavailable")),
            )
    assert tracer.spans[-1].attributes["security.error_type"] == "unavailable"
