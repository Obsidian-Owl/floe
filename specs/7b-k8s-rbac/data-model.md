# Data Model: K8s RBAC Plugin System

**Feature**: Epic 7B - K8s RBAC Plugin System
**Date**: 2026-01-19

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RBACPlugin (ABC)                              │
│  Extends: PluginMetadata                                            │
│  Entry Point: floe.rbac                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ uses
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     RBACManifestGenerator                            │
│  Transforms: SecurityConfig → K8s RBAC YAML                         │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ produces
                                  ▼
     ┌──────────────┬──────────────┬──────────────┬──────────────┐
     │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌────────────────┐  ┌────────────┐  ┌─────────────────┐
│Namespace│  │Service   │  │      Role      │  │RoleBinding │  │PodSecurity      │
│Config   │  │Account   │  │     Config     │  │  Config    │  │  Config         │
│         │  │Config    │  │                │  │            │  │                 │
└─────────┘  └──────────┘  └────────────────┘  └────────────┘  └─────────────────┘
```

## Core Entities

### 1. RBACPlugin (ABC)

**Purpose**: Abstract base class for RBAC operations across different deployment targets.

**Location**: `packages/floe-core/src/floe_core/plugins/rbac.py`

**Inherits From**: `PluginMetadata`

```python
from abc import abstractmethod
from floe_core.plugin_metadata import PluginMetadata

class RBACPlugin(PluginMetadata):
    """Abstract base class for RBAC operations."""

    @abstractmethod
    def generate_service_account(
        self,
        config: ServiceAccountConfig
    ) -> dict[str, Any]:
        """Generate ServiceAccount manifest."""
        ...

    @abstractmethod
    def generate_role(
        self,
        config: RoleConfig
    ) -> dict[str, Any]:
        """Generate Role manifest."""
        ...

    @abstractmethod
    def generate_role_binding(
        self,
        config: RoleBindingConfig
    ) -> dict[str, Any]:
        """Generate RoleBinding manifest."""
        ...

    @abstractmethod
    def generate_namespace(
        self,
        config: NamespaceConfig
    ) -> dict[str, Any]:
        """Generate Namespace manifest with PSS labels."""
        ...

    def generate_pod_security_context(
        self,
        config: PodSecurityConfig
    ) -> dict[str, Any]:
        """Generate pod securityContext fragment."""
        ...
```

**Entry Point Registration**:
```toml
# pyproject.toml
[project.entry-points."floe.rbac"]
k8s = "floe_rbac_k8s:K8sRBACPlugin"
```

---

### 2. RBACManifestGenerator

**Purpose**: Core class that transforms floe configuration into Kubernetes RBAC YAML manifests.

**Location**: `packages/floe-core/src/floe_core/rbac/generator.py`

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class RBACManifestGenerator:
    """Generates RBAC manifests from floe configuration.

    Attributes:
        plugin: The RBACPlugin implementation to use.
        output_dir: Directory to write generated manifests.

    Example:
        >>> generator = RBACManifestGenerator(
        ...     plugin=K8sRBACPlugin(),
        ...     output_dir=Path("target/rbac")
        ... )
        >>> generator.generate(security_config, secret_refs)
    """

    plugin: RBACPlugin
    output_dir: Path = field(default_factory=lambda: Path("target/rbac"))

    def generate(
        self,
        security_config: SecurityConfig,
        secret_references: list[SecretReference]
    ) -> GenerationResult:
        """Generate all RBAC manifests."""
        ...

    def aggregate_permissions(
        self,
        secret_references: list[SecretReference]
    ) -> list[RoleRule]:
        """Aggregate permissions across all secret references."""
        ...

    def write_manifests(
        self,
        manifests: dict[str, list[dict]]
    ) -> list[Path]:
        """Write manifests to output directory."""
        ...
```

---

### 3. SecurityConfig (Pydantic Model)

**Purpose**: Configuration schema for security section of manifest.yaml.

**Location**: `packages/floe-core/src/floe_core/schemas/security.py`

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class RBACConfig(BaseModel):
    """RBAC configuration from manifest.yaml."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(default=True, description="Enable RBAC generation")
    job_service_account: Literal["auto", "manual"] = Field(
        default="auto",
        description="Service account creation mode"
    )
    cluster_scope: bool = Field(
        default=False,
        description="Enable ClusterRole/ClusterRoleBinding generation"
    )

class PodSecurityLevelConfig(BaseModel):
    """Pod Security Standard configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    jobs_level: Literal["privileged", "baseline", "restricted"] = Field(
        default="restricted",
        description="PSS level for floe-jobs namespace"
    )
    platform_level: Literal["privileged", "baseline", "restricted"] = Field(
        default="baseline",
        description="PSS level for floe-platform namespace"
    )

class SecurityConfig(BaseModel):
    """Security section of manifest.yaml."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rbac: RBACConfig = Field(default_factory=RBACConfig)
    pod_security: PodSecurityLevelConfig = Field(default_factory=PodSecurityLevelConfig)
    namespace_isolation: Literal["strict", "permissive"] = Field(
        default="strict",
        description="Namespace isolation mode"
    )
```

---

### 4. ServiceAccountConfig

**Purpose**: Pydantic model for ServiceAccount generation.

**Location**: `packages/floe-core/src/floe_core/schemas/rbac.py`

```python
from pydantic import BaseModel, ConfigDict, Field

class ServiceAccountConfig(BaseModel):
    """Configuration for generating a K8s ServiceAccount."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., pattern=r"^floe-[a-z0-9-]+$")
    namespace: str = Field(..., pattern=r"^[a-z0-9-]+$")
    automount_token: bool = Field(
        default=False,
        description="Whether to automount service account token"
    )
    labels: dict[str, str] = Field(default_factory=lambda: {
        "app.kubernetes.io/managed-by": "floe"
    })
    annotations: dict[str, str] = Field(default_factory=dict)

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Convert to K8s ServiceAccount manifest dict."""
        return {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
                "annotations": self.annotations,
            },
            "automountServiceAccountToken": self.automount_token,
        }
```

---

### 5. RoleConfig

**Purpose**: Pydantic model for Role generation.

```python
from pydantic import BaseModel, ConfigDict, Field

class RoleRule(BaseModel):
    """A single RBAC rule within a Role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    api_groups: list[str] = Field(default_factory=lambda: [""])
    resources: list[str] = Field(...)
    verbs: list[str] = Field(...)
    resource_names: list[str] | None = Field(default=None)

class RoleConfig(BaseModel):
    """Configuration for generating a K8s Role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., pattern=r"^floe-[a-z0-9-]+-role$")
    namespace: str = Field(..., pattern=r"^[a-z0-9-]+$")
    rules: list[RoleRule] = Field(...)
    labels: dict[str, str] = Field(default_factory=lambda: {
        "app.kubernetes.io/managed-by": "floe"
    })

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Convert to K8s Role manifest dict."""
        return {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "rules": [
                {
                    "apiGroups": rule.api_groups,
                    "resources": rule.resources,
                    "verbs": rule.verbs,
                    **({"resourceNames": rule.resource_names} if rule.resource_names else {})
                }
                for rule in self.rules
            ],
        }
```

---

### 6. RoleBindingConfig

**Purpose**: Pydantic model for RoleBinding generation.

```python
from pydantic import BaseModel, ConfigDict, Field

class RoleBindingSubject(BaseModel):
    """Subject (ServiceAccount) in a RoleBinding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["ServiceAccount"] = "ServiceAccount"
    name: str = Field(...)
    namespace: str = Field(...)

class RoleBindingConfig(BaseModel):
    """Configuration for generating a K8s RoleBinding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., pattern=r"^floe-[a-z0-9-]+-binding$")
    namespace: str = Field(..., pattern=r"^[a-z0-9-]+$")
    subjects: list[RoleBindingSubject] = Field(...)
    role_name: str = Field(...)
    labels: dict[str, str] = Field(default_factory=lambda: {
        "app.kubernetes.io/managed-by": "floe"
    })

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Convert to K8s RoleBinding manifest dict."""
        return {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "subjects": [
                {
                    "kind": s.kind,
                    "name": s.name,
                    "namespace": s.namespace,
                }
                for s in self.subjects
            ],
            "roleRef": {
                "kind": "Role",
                "name": self.role_name,
                "apiGroup": "rbac.authorization.k8s.io",
            },
        }
```

---

### 7. NamespaceConfig

**Purpose**: Pydantic model for Namespace generation with PSS labels.

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class NamespaceConfig(BaseModel):
    """Configuration for generating a K8s Namespace with PSS labels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., pattern=r"^floe-[a-z0-9-]+$")
    layer: Literal["3", "4"] = Field(..., description="Architecture layer (3=platform, 4=jobs)")
    pss_enforce: Literal["privileged", "baseline", "restricted"] = Field(default="restricted")
    pss_audit: Literal["privileged", "baseline", "restricted"] = Field(default="restricted")
    pss_warn: Literal["privileged", "baseline", "restricted"] = Field(default="restricted")
    labels: dict[str, str] = Field(default_factory=dict)

    def to_k8s_manifest(self) -> dict[str, Any]:
        """Convert to K8s Namespace manifest dict."""
        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": self.name,
                "labels": {
                    "app.kubernetes.io/part-of": "floe",
                    "app.kubernetes.io/managed-by": "floe",
                    "floe.dev/layer": self.layer,
                    "pod-security.kubernetes.io/enforce": self.pss_enforce,
                    "pod-security.kubernetes.io/audit": self.pss_audit,
                    "pod-security.kubernetes.io/warn": self.pss_warn,
                    **self.labels,
                },
            },
        }
```

---

### 8. PodSecurityConfig

**Purpose**: Pydantic model for pod and container security context.

```python
from pydantic import BaseModel, ConfigDict, Field

class PodSecurityConfig(BaseModel):
    """Configuration for pod/container security context generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_as_non_root: bool = Field(default=True)
    run_as_user: int = Field(default=1000)
    run_as_group: int = Field(default=1000)
    fs_group: int = Field(default=1000)
    read_only_root_filesystem: bool = Field(default=True)
    allow_privilege_escalation: bool = Field(default=False)
    seccomp_profile_type: Literal["RuntimeDefault", "Localhost", "Unconfined"] = Field(
        default="RuntimeDefault"
    )

    def to_pod_security_context(self) -> dict[str, Any]:
        """Generate pod-level securityContext."""
        return {
            "runAsNonRoot": self.run_as_non_root,
            "runAsUser": self.run_as_user,
            "runAsGroup": self.run_as_group,
            "fsGroup": self.fs_group,
            "seccompProfile": {
                "type": self.seccomp_profile_type,
            },
        }

    def to_container_security_context(self) -> dict[str, Any]:
        """Generate container-level securityContext."""
        return {
            "allowPrivilegeEscalation": self.allow_privilege_escalation,
            "readOnlyRootFilesystem": self.read_only_root_filesystem,
            "capabilities": {
                "drop": ["ALL"],
            },
        }
```

---

### 9. GenerationResult

**Purpose**: Dataclass for RBAC generation results.

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class GenerationResult:
    """Result of RBAC manifest generation."""

    success: bool
    files_generated: list[Path] = field(default_factory=list)
    service_accounts: int = 0
    roles: int = 0
    role_bindings: int = 0
    namespaces: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
```

---

## Entity Relationships

```
manifest.yaml
     │
     ▼
SecurityConfig ─────────────────────────────────────────────────────┐
     │                                                               │
     ├─► RBACConfig                                                  │
     │       ├─► enabled: bool                                       │
     │       ├─► job_service_account: Literal["auto", "manual"]     │
     │       └─► cluster_scope: bool                                 │
     │                                                               │
     ├─► PodSecurityLevelConfig                                      │
     │       ├─► jobs_level: PSS level                              │
     │       └─► platform_level: PSS level                          │
     │                                                               │
     └─► namespace_isolation: Literal["strict", "permissive"]       │
                                                                     │
                                                                     ▼
                                                          RBACManifestGenerator
                                                                     │
     ┌───────────────────────────────────────────────────────────────┤
     │                    │                    │                     │
     ▼                    ▼                    ▼                     ▼
NamespaceConfig    ServiceAccountConfig    RoleConfig        RoleBindingConfig
     │                    │                    │                     │
     ▼                    ▼                    ▼                     ▼
namespaces.yaml   serviceaccounts.yaml    roles.yaml       rolebindings.yaml
```

## Validation Rules

### ServiceAccountConfig
- `name` must match pattern `^floe-[a-z0-9-]+$`
- `namespace` must match pattern `^[a-z0-9-]+$`
- `automount_token` defaults to `false` (least privilege)

### RoleConfig
- `name` must match pattern `^floe-[a-z0-9-]+-role$`
- `rules` must not contain wildcard (`*`) in verbs, resources, or apiGroups
- `resource_names` should be set when referencing specific secrets

### RoleBindingConfig
- `name` must match pattern `^floe-[a-z0-9-]+-binding$`
- All subjects must reference existing ServiceAccounts (warning if not)

### NamespaceConfig
- `name` must match pattern `^floe-[a-z0-9-]+$`
- PSS labels are mandatory for all namespaces
- `layer` must be "3" or "4" (per four-layer architecture)

## State Transitions

This feature primarily generates static YAML manifests, so there are no complex state transitions.

The only state relevant is during **manifest application**:

```
Namespace State:
  NOT_EXISTS → CREATED (kubectl apply)
  EXISTS → UPDATED (kubectl apply with changes)
  EXISTS → CONFLICT (different owner label)

ServiceAccount State:
  NOT_EXISTS → CREATED
  EXISTS → UPDATED (if managed by floe)
  EXISTS → CONFLICT (if not managed by floe)
```

Conflict detection uses `app.kubernetes.io/managed-by: floe` label.
