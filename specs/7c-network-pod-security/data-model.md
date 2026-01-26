# Data Model: Network and Pod Security (Epic 7C)

**Feature**: Network and Pod Security
**Epic**: 7C
**Date**: 2026-01-26

## Entity Overview

```
SecurityConfig (extended)
├── network_policies: NetworkPoliciesConfig
│   ├── enabled: bool
│   ├── default_deny: bool
│   ├── jobs_egress_allow: list[EgressAllowRule]
│   └── platform_egress_allow: list[EgressAllowRule]
└── (existing: rbac, pod_security, namespace_isolation)

NetworkPolicyConfig
├── name: str
├── namespace: str
├── pod_selector: dict[str, str]
├── policy_types: list[Literal["Ingress", "Egress"]]
├── ingress_rules: list[IngressRule]
└── egress_rules: list[EgressRule]

PodSecurityContextConfig (extended from 7B)
├── run_as_non_root: bool
├── run_as_user: int
├── run_as_group: int
├── fs_group: int
├── seccomp_profile: Literal["RuntimeDefault", "Unconfined"]
├── read_only_root_filesystem: bool
├── writable_paths: list[str]
└── capabilities_drop: list[str]
```

## Entity Definitions

### NetworkPoliciesConfig

**Purpose**: Top-level configuration for network policies in manifest.yaml

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| enabled | bool | No | True | Enable NetworkPolicy generation |
| default_deny | bool | No | True | Generate default-deny policies |
| jobs_egress_allow | list[EgressAllowRule] | No | [] | Additional egress rules for floe-jobs |
| platform_egress_allow | list[EgressAllowRule] | No | [] | Additional egress rules for floe-platform |
| ingress_controller_namespace | str | No | "ingress-nginx" | Namespace of ingress controller |

**Validation Rules**:
- If `enabled=False`, no NetworkPolicies are generated
- If `default_deny=True`, default-deny policies always generated first
- DNS egress always allowed regardless of configuration

**State Transitions**: None (configuration only)

### EgressAllowRule

**Purpose**: Single egress allowlist entry

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| name | str | Yes | - | Rule identifier (for documentation) |
| namespace | str | No | None | Target namespace (None = external) |
| port | int | Yes | - | Target port |
| protocol | Literal["TCP", "UDP"] | No | "TCP" | Protocol |
| cidr | str | No | None | CIDR block for external (e.g., "0.0.0.0/0") |

**Validation Rules**:
- If `namespace` is set, `cidr` must be None (namespace OR cidr, not both)
- Port must be 1-65535
- CIDR must be valid IPv4 CIDR notation

### NetworkPolicyConfig

**Purpose**: Configuration for generating a single K8s NetworkPolicy

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| name | str | Yes | - | Policy name (pattern: `^floe-[a-z0-9-]+$`) |
| namespace | str | Yes | - | Target namespace |
| pod_selector | dict[str, str] | No | {} | Empty = all pods in namespace |
| policy_types | list[str] | Yes | - | ["Ingress"], ["Egress"], or both |
| ingress_rules | list[IngressRule] | No | [] | Ingress allow rules |
| egress_rules | list[EgressRule] | No | [] | Egress allow rules |

**Validation Rules**:
- `name` must match pattern `^floe-[a-z0-9-]+$`
- `policy_types` must contain at least one of "Ingress" or "Egress"
- Empty `ingress_rules` with "Ingress" in policy_types = deny all ingress

**Methods**:
- `to_k8s_manifest() -> dict[str, Any]`: Generate K8s NetworkPolicy YAML

### IngressRule

**Purpose**: Single ingress rule in NetworkPolicy

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| from_namespace | str | No | None | Source namespace selector |
| from_pod_labels | dict[str, str] | No | {} | Source pod label selector |
| ports | list[PortRule] | No | [] | Allowed ports (empty = all ports) |

**Validation Rules**:
- At least one of `from_namespace` or `from_pod_labels` must be set
- If both set, both must match (AND logic)

### EgressRule

**Purpose**: Single egress rule in NetworkPolicy

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| to_namespace | str | No | None | Destination namespace selector |
| to_cidr | str | No | None | Destination CIDR block |
| ports | list[PortRule] | Yes | - | Allowed ports |

**Validation Rules**:
- Exactly one of `to_namespace` or `to_cidr` must be set
- `ports` must not be empty (explicit port specification required)

### PortRule

**Purpose**: Port specification for ingress/egress rules

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| port | int | Yes | - | Port number |
| protocol | Literal["TCP", "UDP"] | No | "TCP" | Protocol |

### PodSecurityContextConfig

**Purpose**: Configuration for pod and container security contexts

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| run_as_non_root | bool | No | True | Require non-root user |
| run_as_user | int | No | 1000 | UID for container process |
| run_as_group | int | No | 1000 | GID for container process |
| fs_group | int | No | 1000 | fsGroup for volume mounts |
| seccomp_profile | str | No | "RuntimeDefault" | Seccomp profile type |
| read_only_root_filesystem | bool | No | True | Read-only root filesystem |
| writable_paths | list[str] | No | ["/tmp", "/home/floe"] | Paths needing emptyDir mounts |
| allow_privilege_escalation | bool | No | False | Allow setuid/setgid |
| capabilities_drop | list[str] | No | ["ALL"] | Linux capabilities to drop |

**Validation Rules**:
- `run_as_user` must be >= 1 (non-root)
- `seccomp_profile` must be "RuntimeDefault" or "Unconfined"
- `writable_paths` must start with "/" (absolute paths)

**Methods**:
- `to_pod_security_context() -> dict[str, Any]`: Generate pod-level securityContext
- `to_container_security_context() -> dict[str, Any]`: Generate container-level securityContext
- `to_volume_mounts() -> list[dict[str, Any]]`: Generate emptyDir volume mounts

### NamespaceSecurityConfig

**Purpose**: Security configuration per namespace

**Fields**:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| namespace | str | Yes | - | Namespace name |
| pss_enforce | Literal["privileged", "baseline", "restricted"] | No | "restricted" | PSS enforce level |
| pss_audit | Literal["privileged", "baseline", "restricted"] | No | "restricted" | PSS audit level |
| pss_warn | Literal["privileged", "baseline", "restricted"] | No | "restricted" | PSS warn level |
| network_policies_enabled | bool | No | True | Generate NetworkPolicies for this namespace |

**Validation Rules**:
- `namespace` must match K8s namespace naming rules
- Audit and warn levels should be >= enforce level

**Methods**:
- `to_namespace_labels() -> dict[str, str]`: Generate PSS label dict

## Entity Relationships

```
manifest.yaml
└── security: SecurityConfig
    ├── rbac: RBACConfig (Epic 7B)
    ├── pod_security: PodSecurityLevelConfig (Epic 7B)
    ├── network_policies: NetworkPoliciesConfig (Epic 7C)
    │   ├── jobs_egress_allow: list[EgressAllowRule]
    │   └── platform_egress_allow: list[EgressAllowRule]
    └── namespace_isolation: str

NetworkPolicyManifestGenerator
├── input: SecurityConfig
├── input: list[NamespaceSecurityConfig]
└── output: dict[str, list[NetworkPolicyConfig]]
    ├── "floe-platform": [default-deny, allow-egress, allow-ingress]
    └── "floe-jobs": [default-deny, allow-egress]
```

## Default Configurations

### Default Jobs Namespace NetworkPolicies

```yaml
# Default-deny all traffic
- name: floe-jobs-default-deny
  namespace: floe-jobs
  pod_selector: {}
  policy_types: [Ingress, Egress]
  ingress_rules: []  # Deny all ingress
  egress_rules: []   # Deny all egress

# Allow required egress
- name: floe-jobs-allow-egress
  namespace: floe-jobs
  pod_selector: {}
  policy_types: [Egress]
  egress_rules:
    # DNS always allowed
    - to_namespace: kube-system
      ports: [{port: 53, protocol: UDP}]
    # Polaris catalog
    - to_namespace: floe-platform
      ports: [{port: 8181, protocol: TCP}]
    # OTel Collector
    - to_namespace: floe-platform
      ports: [{port: 4317, protocol: TCP}, {port: 4318, protocol: TCP}]
    # MinIO/S3
    - to_namespace: floe-platform
      ports: [{port: 9000, protocol: TCP}]
    # External HTTPS (cloud DWH)
    - to_cidr: "0.0.0.0/0"
      ports: [{port: 443, protocol: TCP}]
```

### Default Platform Namespace NetworkPolicies

```yaml
# Default-deny ingress
- name: floe-platform-default-deny
  namespace: floe-platform
  pod_selector: {}
  policy_types: [Ingress]
  ingress_rules: []

# Allow ingress from ingress controller
- name: floe-platform-allow-ingress
  namespace: floe-platform
  pod_selector: {}
  policy_types: [Ingress]
  ingress_rules:
    - from_namespace: ingress-nginx
      ports: []  # All ports (ingress controller routes to correct ports)
    - from_namespace: floe-platform  # Intra-namespace
      ports: []

# Allow required egress
- name: floe-platform-allow-egress
  namespace: floe-platform
  pod_selector: {}
  policy_types: [Egress]
  egress_rules:
    - to_namespace: kube-system
      ports: [{port: 53, protocol: UDP}]
    - to_namespace: floe-jobs  # Dagster creating jobs
      ports: []
    - to_cidr: "0.0.0.0/0"
      ports: [{port: 443, protocol: TCP}]
```

## Schema Extensions to SecurityConfig

```python
class SecurityConfig(BaseModel):
    """Extended SecurityConfig with network policies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Existing from Epic 7B
    rbac: RBACConfig = Field(default_factory=RBACConfig)
    pod_security: PodSecurityLevelConfig = Field(default_factory=PodSecurityLevelConfig)
    namespace_isolation: Literal["strict", "permissive"] = "strict"

    # New for Epic 7C
    network_policies: NetworkPoliciesConfig = Field(default_factory=NetworkPoliciesConfig)
```

## Output Artifacts

### target/network/ Directory Structure

```
target/network/
├── floe-platform-default-deny.yaml
├── floe-platform-allow-ingress.yaml
├── floe-platform-allow-egress.yaml
├── floe-jobs-default-deny.yaml
├── floe-jobs-allow-egress.yaml
├── floe-{domain}-domain-default-deny.yaml (per domain)
├── floe-{domain}-domain-allow-egress.yaml (per domain)
└── NETWORK-POLICY-SUMMARY.md
```

### GenerationResult

```python
@dataclass
class NetworkPolicyGenerationResult:
    success: bool
    files_generated: list[Path]
    network_policies_count: int
    namespaces: list[str]
    warnings: list[str]
    errors: list[str]
    audit_event: NetworkPolicyAuditEvent
```
