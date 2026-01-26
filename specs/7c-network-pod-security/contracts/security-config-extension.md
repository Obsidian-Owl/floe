# Contract: SecurityConfig Extension for Network Policies

**Version**: 1.1.0
**Epic**: 7C
**Date**: 2026-01-26

## Overview

This contract defines the extension to `SecurityConfig` schema to support NetworkPolicy generation.

## Schema Extension

### Current SecurityConfig (Epic 7B)

```python
class SecurityConfig(BaseModel):
    """Security configuration from manifest.yaml."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rbac: RBACConfig = Field(default_factory=RBACConfig)
    pod_security: PodSecurityLevelConfig = Field(default_factory=PodSecurityLevelConfig)
    namespace_isolation: Literal["strict", "permissive"] = "strict"
```

### Extended SecurityConfig (Epic 7C)

```python
class SecurityConfig(BaseModel):
    """Security configuration from manifest.yaml (v1.1.0)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Existing (Epic 7B)
    rbac: RBACConfig = Field(default_factory=RBACConfig)
    pod_security: PodSecurityLevelConfig = Field(default_factory=PodSecurityLevelConfig)
    namespace_isolation: Literal["strict", "permissive"] = "strict"

    # New (Epic 7C)
    network_policies: NetworkPoliciesConfig = Field(default_factory=NetworkPoliciesConfig)
```

## NetworkPoliciesConfig Schema

```python
class NetworkPoliciesConfig(BaseModel):
    """Network policy configuration for manifest.yaml security section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable NetworkPolicy generation"
    )
    default_deny: bool = Field(
        default=True,
        description="Generate default-deny policies for all namespaces"
    )
    allow_external_https: bool = Field(
        default=True,
        description="Allow egress to external HTTPS (port 443)"
    )
    ingress_controller_namespace: str = Field(
        default="ingress-nginx",
        description="Namespace where ingress controller is deployed"
    )
    jobs_egress_allow: list[EgressAllowRule] = Field(
        default_factory=list,
        description="Additional egress rules for floe-jobs namespace"
    )
    platform_egress_allow: list[EgressAllowRule] = Field(
        default_factory=list,
        description="Additional egress rules for floe-platform namespace"
    )
```

## EgressAllowRule Schema

```python
class EgressAllowRule(BaseModel):
    """Single egress allowlist entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description="Rule identifier for documentation"
    )
    to_namespace: str | None = Field(
        default=None,
        description="Target namespace (mutually exclusive with to_cidr)"
    )
    to_cidr: str | None = Field(
        default=None,
        pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$",
        description="Target CIDR block (mutually exclusive with to_namespace)"
    )
    port: int = Field(
        ...,
        ge=1,
        le=65535,
        description="Target port"
    )
    protocol: Literal["TCP", "UDP"] = Field(
        default="TCP",
        description="Protocol"
    )

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        """Ensure exactly one of to_namespace or to_cidr is set."""
        if (self.to_namespace is None) == (self.to_cidr is None):
            raise ValueError("Exactly one of to_namespace or to_cidr must be set")
        return self
```

## manifest.yaml Example

```yaml
# manifest.yaml
version: "1.0"
name: my-platform

security:
  # Existing (Epic 7B)
  rbac:
    enabled: true
    job_service_account: auto
  pod_security:
    jobs_level: restricted
    platform_level: baseline
  namespace_isolation: strict

  # New (Epic 7C)
  network_policies:
    enabled: true
    default_deny: true
    allow_external_https: true
    ingress_controller_namespace: ingress-nginx
    jobs_egress_allow:
      - name: "snowflake-access"
        to_cidr: "0.0.0.0/0"
        port: 443
        protocol: TCP
    platform_egress_allow:
      - name: "vault-access"
        to_namespace: vault
        port: 8200
        protocol: TCP
```

## Default Values Contract

When `network_policies` is not specified, these defaults apply:

| Field | Default | Rationale |
|-------|---------|-----------|
| enabled | true | Security by default |
| default_deny | true | Zero-trust networking |
| allow_external_https | true | Jobs need cloud DWH access |
| ingress_controller_namespace | "ingress-nginx" | Most common ingress |
| jobs_egress_allow | [] | No additional rules by default |
| platform_egress_allow | [] | No additional rules by default |

## Built-in Egress Rules (Not Configurable)

These egress rules are ALWAYS generated (cannot be disabled):

| Rule | From | To | Port | Rationale |
|------|------|-----|------|-----------|
| DNS | all | kube-system | 53/UDP | Required for service discovery |
| Polaris | floe-jobs | floe-platform | 8181/TCP | Catalog access |
| OTel gRPC | floe-jobs | floe-platform | 4317/TCP | Trace export |
| OTel HTTP | floe-jobs | floe-platform | 4318/TCP | Metrics export |
| MinIO | floe-jobs | floe-platform | 9000/TCP | Object storage |

## Backward Compatibility

- Adding `network_policies` field is MINOR version (additive)
- Default value ensures no breaking change for existing configs
- Existing `security` blocks without `network_policies` continue to work

## JSON Schema Export

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "NetworkPoliciesConfig",
  "type": "object",
  "properties": {
    "enabled": {"type": "boolean", "default": true},
    "default_deny": {"type": "boolean", "default": true},
    "allow_external_https": {"type": "boolean", "default": true},
    "ingress_controller_namespace": {"type": "string", "default": "ingress-nginx"},
    "jobs_egress_allow": {
      "type": "array",
      "items": {"$ref": "#/$defs/EgressAllowRule"}
    },
    "platform_egress_allow": {
      "type": "array",
      "items": {"$ref": "#/$defs/EgressAllowRule"}
    }
  },
  "additionalProperties": false,
  "$defs": {
    "EgressAllowRule": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "to_namespace": {"type": "string"},
        "to_cidr": {"type": "string", "pattern": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}/\\d{1,2}$"},
        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
        "protocol": {"type": "string", "enum": ["TCP", "UDP"], "default": "TCP"}
      },
      "required": ["name", "port"],
      "additionalProperties": false
    }
  }
}
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2026-01-26 | Added network_policies field to SecurityConfig |
| 1.0.0 | 2026-01-19 | Initial SecurityConfig (Epic 7B) |
