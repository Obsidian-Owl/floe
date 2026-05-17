"""Security-sensitive observability tests for K8s RBAC generation."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any
from unittest.mock import patch

import pytest
from floe_core.schemas.rbac import RoleConfig, RoleRule, ServiceAccountConfig

from floe_rbac_k8s.plugin import K8sRBACPlugin


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


def test_generate_service_account_records_resource_metadata_without_yaml_body() -> None:
    tracer = _Tracer()
    plugin = K8sRBACPlugin()
    config = ServiceAccountConfig(name="floe-job-runner", namespace="floe-jobs")

    with patch("floe_rbac_k8s.plugin.get_tracer", return_value=tracer):
        manifest = plugin.generate_service_account(config)

    attrs = tracer.spans[-1].attributes
    assert manifest["kind"] == "ServiceAccount"
    assert attrs["security.resource_kind"] == "ServiceAccount"
    assert attrs["security.namespace"] == "floe-jobs"
    assert attrs["security.status"] == "success"
    assert "security.duration_ms" in attrs
    assert "apiVersion" not in _attrs_text(tracer)
    assert "automountServiceAccountToken" not in _attrs_text(tracer)


def test_generate_role_does_not_emit_private_key_or_rule_body() -> None:
    tracer = _Tracer()
    plugin = K8sRBACPlugin()
    rule = RoleRule(resources=["secrets"], verbs=["get"], resource_names=["private-key-ref"])
    config = RoleConfig(name="floe-reader-role", namespace="floe-jobs", rules=[rule])

    with patch("floe_rbac_k8s.plugin.get_tracer", return_value=tracer):
        plugin.generate_role(config)

    attrs = tracer.spans[-1].attributes
    assert attrs["security.resource_kind"] == "Role"
    assert attrs["security.status"] == "success"
    assert "private-key-ref" not in _attrs_text(tracer)
    assert "rules" not in _attrs_text(tracer)


def test_generation_failures_are_classified() -> None:
    tracer = _Tracer()
    plugin = K8sRBACPlugin()

    with patch("floe_rbac_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(PermissionError):
            plugin._record_generation(
                operation="generate_role",
                policy_type="Role",
                resource_kind="Role",
                namespace="floe-jobs",
                action=lambda: (_ for _ in ()).throw(PermissionError("access denied")),
            )
    assert tracer.spans[-1].attributes["security.error_type"] == "access_denied"

    with patch("floe_rbac_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(FileNotFoundError):
            plugin._record_generation(
                operation="generate_role",
                policy_type="Role",
                resource_kind="Role",
                namespace="floe-jobs",
                action=lambda: (_ for _ in ()).throw(FileNotFoundError("missing")),
            )
    assert tracer.spans[-1].attributes["security.error_type"] == "not_found"

    with patch("floe_rbac_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(ValueError):
            plugin._record_generation(
                operation="generate_role",
                policy_type="Role",
                resource_kind="Role",
                namespace="floe-jobs",
                action=lambda: (_ for _ in ()).throw(ValueError("invalid")),
            )
    assert tracer.spans[-1].attributes["security.error_type"] == "validation"
