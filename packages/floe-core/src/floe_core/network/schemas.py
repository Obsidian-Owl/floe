"""Network policy schemas for Kubernetes NetworkPolicy generation.

This module defines Pydantic models for network policy configuration
including NetworkPolicies, egress/ingress rules, and pod security settings.

Contract: specs/7c-network-pod-security/data-model.md
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_MAX_NAMESPACE_LENGTH = 63


def _validate_namespace(namespace: str) -> str:
    """Validate Kubernetes namespace name (RFC 1123 DNS label)."""
    if len(namespace) > _MAX_NAMESPACE_LENGTH:
        raise ValueError(
            f"Namespace too long: {len(namespace)} > {_MAX_NAMESPACE_LENGTH}"
        )
    if not _NAMESPACE_PATTERN.match(namespace):
        raise ValueError(f"Invalid namespace: {namespace}")
    return namespace


def _validate_label_key(key: str) -> str:
    """Validate Kubernetes label key."""
    if not key:
        raise ValueError("Label key cannot be empty")
    if len(key) > 253:
        raise ValueError(f"Label key too long: {len(key)} > 253")
    if key.startswith("-") or key.endswith("-"):
        raise ValueError(f"Invalid label key: {key}")
    return key


def _validate_label_value(value: str) -> str:
    """Validate Kubernetes label value."""
    if len(value) > 63:
        raise ValueError(f"Label value too long: {len(value)} > 63")
    if value and not re.match(r"^[a-zA-Z0-9]([-a-zA-Z0-9_.]*[a-zA-Z0-9])?$", value):
        raise ValueError(f"Invalid label value: {value}")
    return value


def _validate_cidr_format(cidr: str) -> str:
    """Validate CIDR notation using ipaddress module.

    Args:
        cidr: CIDR notation string (e.g., "10.0.0.0/8")

    Returns:
        The validated CIDR string

    Raises:
        ValueError: If CIDR is invalid.
    """
    try:
        ipaddress.ip_network(cidr, strict=False)
    except ValueError as e:
        raise ValueError(f"Invalid CIDR: {cidr}") from e
    return cidr


class PortRule(BaseModel):
    """Port specification for ingress/egress rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    port: int = Field(..., ge=1, le=65535, description="Port number")
    protocol: Literal["TCP", "UDP"] = Field(
        default="TCP", description="Protocol (TCP or UDP)"
    )


class EgressRule(BaseModel):
    """Single egress rule in NetworkPolicy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    to_namespace: str | None = Field(
        default=None, description="Destination namespace selector"
    )
    to_cidr: str | None = Field(default=None, description="Destination CIDR block")
    ports: tuple[PortRule, ...] = Field(..., min_length=1, description="Allowed ports")

    @field_validator("to_namespace", mode="after")
    @classmethod
    def validate_to_namespace(cls, v: str | None) -> str | None:
        """Validate namespace format if provided."""
        if v is not None:
            return _validate_namespace(v)
        return v

    @field_validator("to_cidr", mode="after")
    @classmethod
    def validate_to_cidr(cls, v: str | None) -> str | None:
        """Validate CIDR format if provided."""
        if v is not None:
            return _validate_cidr_format(v)
        return v

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        """Ensure exactly one of to_namespace or to_cidr is set."""
        if (self.to_namespace is None) == (self.to_cidr is None):
            msg = "Exactly one of to_namespace or to_cidr must be set"
            raise ValueError(msg)
        return self


class IngressRule(BaseModel):
    """Single ingress rule in NetworkPolicy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_namespace: str | None = Field(
        default=None, description="Source namespace selector"
    )
    from_pod_labels: dict[str, str] = Field(
        default_factory=dict, description="Source pod label selector"
    )
    ports: tuple[PortRule, ...] = Field(
        default_factory=tuple, description="Allowed ports (empty = all ports)"
    )

    @field_validator("from_namespace", mode="after")
    @classmethod
    def validate_from_namespace(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_namespace(v)
        return v

    @field_validator("from_pod_labels", mode="after")
    @classmethod
    def validate_from_pod_labels(cls, v: dict[str, str]) -> dict[str, str]:
        for key, value in v.items():
            _validate_label_key(key)
            _validate_label_value(value)
        return v


class NetworkPolicyConfig(BaseModel):
    """Configuration for generating a single K8s NetworkPolicy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ..., pattern=r"^floe-[a-z0-9-]+$", description="Policy name (must match floe-*)"
    )
    namespace: str = Field(..., description="Target namespace")
    pod_selector: dict[str, str] = Field(
        default_factory=dict, description="Empty = all pods in namespace"
    )
    policy_types: tuple[Literal["Ingress", "Egress"], ...] = Field(
        ..., min_length=1, description="Policy types to enforce"
    )
    ingress_rules: tuple[IngressRule, ...] = Field(
        default_factory=tuple, description="Ingress allow rules"
    )
    egress_rules: tuple[EgressRule, ...] = Field(
        default_factory=tuple, description="Egress allow rules"
    )

    @field_validator("namespace", mode="after")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        return _validate_namespace(v)

    @field_validator("pod_selector", mode="after")
    @classmethod
    def validate_pod_selector(cls, v: dict[str, str]) -> dict[str, str]:
        for key, value in v.items():
            _validate_label_key(key)
            _validate_label_value(value)
        return v

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Generate K8s NetworkPolicy manifest."""
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/managed-by": "floe",
                    "floe.dev/component": "network-security",
                },
            },
            "spec": {
                "podSelector": (
                    {"matchLabels": self.pod_selector} if self.pod_selector else {}
                ),
                "policyTypes": list(self.policy_types),
            },
        }

        if "Ingress" in self.policy_types:
            manifest["spec"]["ingress"] = [
                self._ingress_rule_to_k8s(rule) for rule in self.ingress_rules
            ]

        if "Egress" in self.policy_types:
            manifest["spec"]["egress"] = [
                self._egress_rule_to_k8s(rule) for rule in self.egress_rules
            ]

        return manifest

    def _ingress_rule_to_k8s(self, rule: IngressRule) -> dict[str, Any]:
        """Convert IngressRule to K8s ingress rule structure."""
        k8s_rule: dict[str, Any] = {}

        from_selectors: list[dict[str, Any]] = []
        if rule.from_namespace:
            from_selectors.append(
                {
                    "namespaceSelector": {
                        "matchLabels": {
                            "kubernetes.io/metadata.name": rule.from_namespace
                        }
                    }
                }
            )
        if rule.from_pod_labels:
            from_selectors.append(
                {"podSelector": {"matchLabels": rule.from_pod_labels}}
            )

        if from_selectors:
            k8s_rule["from"] = from_selectors

        if rule.ports:
            k8s_rule["ports"] = [
                {"port": p.port, "protocol": p.protocol} for p in rule.ports
            ]

        return k8s_rule

    def _egress_rule_to_k8s(self, rule: EgressRule) -> dict[str, Any]:
        """Convert EgressRule to K8s egress rule structure."""
        k8s_rule: dict[str, Any] = {"to": []}

        if rule.to_namespace:
            k8s_rule["to"].append(
                {
                    "namespaceSelector": {
                        "matchLabels": {
                            "kubernetes.io/metadata.name": rule.to_namespace
                        }
                    }
                }
            )
        elif rule.to_cidr:
            k8s_rule["to"].append({"ipBlock": {"cidr": rule.to_cidr}})

        k8s_rule["ports"] = [
            {"port": p.port, "protocol": p.protocol} for p in rule.ports
        ]

        return k8s_rule


class EgressAllowRule(BaseModel):
    """Single egress allowlist entry for manifest.yaml configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Rule identifier for documentation")
    to_namespace: str | None = Field(
        default=None, description="Target namespace (mutually exclusive with to_cidr)"
    )
    to_cidr: str | None = Field(
        default=None,
        description="Target CIDR block (mutually exclusive with to_namespace)",
    )
    port: int = Field(..., ge=1, le=65535, description="Target port")
    protocol: Literal["TCP", "UDP"] = Field(default="TCP", description="Protocol")

    @field_validator("to_namespace", mode="after")
    @classmethod
    def validate_to_namespace(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_namespace(v)
        return v

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        """Ensure exactly one of to_namespace or to_cidr is set."""
        if (self.to_namespace is None) == (self.to_cidr is None):
            msg = "Exactly one of to_namespace or to_cidr must be set"
            raise ValueError(msg)
        if self.to_cidr is not None:
            _validate_cidr_format(self.to_cidr)
        return self


class NetworkPoliciesConfig(BaseModel):
    """Network policy configuration for manifest.yaml security section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=True, description="Enable NetworkPolicy generation")
    default_deny: bool = Field(
        default=True, description="Generate default-deny policies for all namespaces"
    )
    allow_external_https: bool = Field(
        default=True, description="Allow egress to external HTTPS (port 443)"
    )
    ingress_controller_namespace: str = Field(
        default="ingress-nginx",
        description="Namespace where ingress controller is deployed",
    )
    jobs_egress_allow: tuple[EgressAllowRule, ...] = Field(
        default_factory=tuple,
        description="Additional egress rules for floe-jobs namespace",
    )
    platform_egress_allow: tuple[EgressAllowRule, ...] = Field(
        default_factory=tuple,
        description="Additional egress rules for floe-platform namespace",
    )

    @field_validator("ingress_controller_namespace", mode="after")
    @classmethod
    def validate_ingress_controller_namespace(cls, v: str) -> str:
        return _validate_namespace(v)
