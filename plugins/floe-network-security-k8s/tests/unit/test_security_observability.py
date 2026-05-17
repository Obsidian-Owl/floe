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


@pytest.mark.requirement("OBS-NETWORK-SECURITY-001")
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


@pytest.mark.requirement("OBS-NETWORK-SECURITY-002")
def test_network_generation_does_not_emit_credential_like_policy_body() -> None:
    tracer = _Tracer()
    plugin = K8sNetworkSecurityPlugin()

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        rule = plugin.generate_k8s_api_egress_rule("10.0.0.1/32", strict_mode=True)

    assert rule["to"][0]["ipBlock"]["cidr"].startswith("10.0.0.1")
    text = _attrs_text(tracer)
    assert "10.0.0.1" not in text


@pytest.mark.requirement("OBS-NETWORK-SECURITY-003")
def test_public_security_context_methods_emit_success_spans_without_bodies() -> None:
    tracer = _Tracer()
    plugin = K8sNetworkSecurityPlugin()

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        dns_rule = plugin.generate_dns_egress_rule()
        pod_context = plugin.generate_pod_security_context(config={})
        container_context = plugin.generate_container_security_context(config={})
        volumes, mounts = plugin.generate_writable_volumes(["/tmp/cache"])

    assert dns_rule["ports"][0]["port"] == 53
    assert pod_context["seccompProfile"]["type"] == "RuntimeDefault"
    assert container_context["capabilities"]["drop"] == ["ALL"]
    assert volumes[0]["name"] == "writable-tmp-cache"
    assert mounts[0]["mountPath"] == "/tmp/cache"
    assert [span.name for span in tracer.spans[-4:]] == [
        "security.generate_dns_egress_rule",
        "security.generate_pod_security_context",
        "security.generate_container_security_context",
        "security.generate_writable_volumes",
    ]
    for span in tracer.spans[-4:]:
        assert span.attributes["security.status"] == "success"
        assert "security.duration_ms" in span.attributes
    text = _attrs_text(tracer)
    assert "seccompProfile" not in text
    assert "/tmp/cache" not in text


@pytest.mark.requirement("OBS-NETWORK-SECURITY-004")
def test_remaining_public_generation_methods_emit_success_spans_without_bodies() -> None:
    tracer = _Tracer()
    plugin = K8sNetworkSecurityPlugin()

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        platform_rules = plugin.generate_platform_egress_rules()
        ingress_rule = plugin.generate_ingress_controller_rule(namespace="ingress-nginx")
        jobs_rule = plugin.generate_jobs_ingress_rule()
        intra_rule = plugin.generate_intra_namespace_rule("floe-jobs")
        external_rule = plugin.generate_external_https_egress_rule(enabled=True)
        disabled_external_rule = plugin.generate_external_https_egress_rule(enabled=False)
        custom_rule = plugin.generate_custom_egress_rule(cidr="10.0.0.0/8", port=443)
        custom_rules = plugin.generate_custom_egress_rules(
            namespace="floe-platform",
            ports=[443, 8181],
        )
        pss_labels = plugin.generate_pss_labels(level="restricted")
        namespace_manifest = plugin.generate_namespace_manifest(
            name="floe-jobs",
            pss_level="restricted",
            additional_labels={"team": "platform"},
        )

    assert len(platform_rules) == 4
    assert ingress_rule["ports"][0]["port"] == 80
    assert jobs_rule["ports"][0]["port"] == 8181
    assert intra_rule["from"][0]["podSelector"] == {}
    assert external_rule is not None
    assert disabled_external_rule is None
    assert custom_rule["ports"][0]["port"] == 443
    assert len(custom_rules["ports"]) == 2
    assert pss_labels["pod-security.kubernetes.io/enforce"] == "restricted"
    assert namespace_manifest["kind"] == "Namespace"

    span_names = [span.name for span in tracer.spans]
    for operation in [
        "generate_platform_egress_rules",
        "generate_ingress_controller_rule",
        "generate_jobs_ingress_rule",
        "generate_intra_namespace_rule",
        "generate_external_https_egress_rule",
        "generate_custom_egress_rule",
        "generate_custom_egress_rules",
        "generate_pss_labels",
        "generate_namespace_manifest",
    ]:
        assert f"security.{operation}" in span_names

    for span in tracer.spans:
        attrs = span.attributes
        assert attrs["security.status"] == "success"
        assert "security.resource_kind" in attrs
        assert "security.policy_type" in attrs
        assert "security.duration_ms" in attrs

    text = _attrs_text(tracer)
    assert "10.0.0.0" not in text
    assert "floe-platform" not in text
    assert "pod-security.kubernetes.io" not in text
    assert "team" not in text
    assert "apiVersion" not in text


@pytest.mark.requirement("OBS-NETWORK-SECURITY-005")
def test_public_custom_and_pss_validation_failures_are_classified() -> None:
    tracer = _Tracer()
    plugin = K8sNetworkSecurityPlugin()

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(ValueError):
            plugin.generate_custom_egress_rule(cidr="not-a-cidr")
    assert tracer.spans[-1].name == "security.generate_custom_egress_rule"
    assert tracer.spans[-1].attributes["security.error_type"] == "validation"

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(ValueError):
            plugin.generate_pss_labels(level="invalid")  # type: ignore[arg-type]
    assert tracer.spans[-1].name == "security.generate_pss_labels"
    assert tracer.spans[-1].attributes["security.error_type"] == "validation"
    assert "not-a-cidr" not in _attrs_text(tracer)
    assert "invalid" not in _attrs_text(tracer)


@pytest.mark.requirement("OBS-NETWORK-SECURITY-006")
def test_public_writable_volumes_failures_are_classified() -> None:
    tracer = _Tracer()
    plugin = K8sNetworkSecurityPlugin()

    with patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer):
        with pytest.raises(ValueError):
            plugin.generate_writable_volumes(["/var/run/docker.sock"])
    assert tracer.spans[-1].attributes["security.error_type"] == "validation"

    with (
        patch("floe_network_security_k8s.plugin.get_tracer", return_value=tracer),
        patch.object(
            plugin,
            "_path_to_volume_name",
            side_effect=TimeoutError("api unavailable token=leaked"),  # pragma: allowlist secret
        ),
    ):
        with pytest.raises(TimeoutError):
            plugin.generate_writable_volumes(["/tmp/cache"])
    assert tracer.spans[-1].attributes["security.error_type"] == "unavailable"
    assert "leaked" not in _attrs_text(tracer)  # pragma: allowlist secret


@pytest.mark.requirement("OBS-NETWORK-SECURITY-007")
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
