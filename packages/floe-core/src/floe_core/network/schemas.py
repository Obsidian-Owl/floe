"""Network policy schemas for Kubernetes NetworkPolicy generation.

This module defines Pydantic models for network policy configuration
including NetworkPolicies, egress/ingress rules, and pod security settings.

Contract: specs/7c-network-pod-security/data-model.md
"""

from __future__ import annotations

import re
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PortRule(BaseModel):
    """Port specification for ingress/egress rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    port: int = Field(..., ge=1, le=65535, description="Port number")
    protocol: Literal["TCP", "UDP"] = Field(default="TCP", description="Protocol (TCP or UDP)")


class EgressRule(BaseModel):
    """Single egress rule in NetworkPolicy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    to_namespace: str | None = Field(default=None, description="Destination namespace selector")
    to_cidr: str | None = Field(default=None, description="Destination CIDR block")
    ports: list[PortRule] = Field(..., min_length=1, description="Allowed ports")

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

    from_namespace: str | None = Field(default=None, description="Source namespace selector")
    from_pod_labels: dict[str, str] = Field(
        default_factory=dict, description="Source pod label selector"
    )
    ports: list[PortRule] = Field(
        default_factory=list, description="Allowed ports (empty = all ports)"
    )


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
    policy_types: list[Literal["Ingress", "Egress"]] = Field(
        ..., min_length=1, description="Policy types to enforce"
    )
    ingress_rules: list[IngressRule] = Field(
        default_factory=list, description="Ingress allow rules"
    )
    egress_rules: list[EgressRule] = Field(default_factory=list, description="Egress allow rules")

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
                "podSelector": ({"matchLabels": self.pod_selector} if self.pod_selector else {}),
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
                        "matchLabels": {"kubernetes.io/metadata.name": rule.from_namespace}
                    }
                }
            )
        if rule.from_pod_labels:
            from_selectors.append({"podSelector": {"matchLabels": rule.from_pod_labels}})

        if from_selectors:
            k8s_rule["from"] = from_selectors

        if rule.ports:
            k8s_rule["ports"] = [{"port": p.port, "protocol": p.protocol} for p in rule.ports]

        return k8s_rule

    def _egress_rule_to_k8s(self, rule: EgressRule) -> dict[str, Any]:
        """Convert EgressRule to K8s egress rule structure."""
        k8s_rule: dict[str, Any] = {"to": []}

        if rule.to_namespace:
            k8s_rule["to"].append(
                {
                    "namespaceSelector": {
                        "matchLabels": {"kubernetes.io/metadata.name": rule.to_namespace}
                    }
                }
            )
        elif rule.to_cidr:
            k8s_rule["to"].append({"ipBlock": {"cidr": rule.to_cidr}})

        k8s_rule["ports"] = [{"port": p.port, "protocol": p.protocol} for p in rule.ports]

        return k8s_rule


CIDR_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")


class EgressAllowRule(BaseModel):
    """Single egress allowlist entry for manifest.yaml configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Rule identifier for documentation")
    to_namespace: str | None = Field(
        default=None, description="Target namespace (mutually exclusive with to_cidr)"
    )
    to_cidr: str | None = Field(
        default=None, description="Target CIDR block (mutually exclusive with to_namespace)"
    )
    port: int = Field(..., ge=1, le=65535, description="Target port")
    protocol: Literal["TCP", "UDP"] = Field(default="TCP", description="Protocol")

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        """Ensure exactly one of to_namespace or to_cidr is set."""
        if (self.to_namespace is None) == (self.to_cidr is None):
            msg = "Exactly one of to_namespace or to_cidr must be set"
            raise ValueError(msg)
        if self.to_cidr is not None and not CIDR_PATTERN.match(self.to_cidr):
            msg = f"Invalid CIDR notation: {self.to_cidr}"
            raise ValueError(msg)
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
        default="ingress-nginx", description="Namespace where ingress controller is deployed"
    )
    jobs_egress_allow: list[EgressAllowRule] = Field(
        default_factory=list, description="Additional egress rules for floe-jobs namespace"
    )
    platform_egress_allow: list[EgressAllowRule] = Field(
        default_factory=list, description="Additional egress rules for floe-platform namespace"
    )
