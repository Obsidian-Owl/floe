# Research: Manifest Schema

**Feature**: 001-manifest-schema
**Date**: 2026-01-09
**Purpose**: Resolve technical decisions and best practices for manifest schema implementation

## Research Questions

### 1. Pydantic v2 Schema Patterns for Configuration

**Decision**: Use Pydantic v2 with strict validation and frozen models

**Rationale**:
- `ConfigDict(strict=True, extra="forbid")` catches typos and invalid fields at parse time
- `frozen=True` ensures immutability after validation (thread-safe, hashable)
- `field_validator` with `mode="before"` enables preprocessing (e.g., normalize scope values)
- JSON Schema export via `model_json_schema()` enables IDE autocomplete

**Alternatives Considered**:
- Pydantic v1: Rejected - deprecated syntax, no `model_config`
- dataclasses: Rejected - no runtime validation, no JSON Schema export
- attrs: Rejected - less ecosystem support for YAML/JSON Schema

**Implementation Pattern**:
```python
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

class PlatformManifest(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",  # Reject unknown fields (but warn in practice via custom validator)
        frozen=True,     # Immutable after validation
    )

    api_version: Literal["floe.dev/v1"] = Field(default="floe.dev/v1", alias="apiVersion")
    kind: Literal["Manifest"] = Field(default="Manifest")
    metadata: ManifestMetadata
    scope: Literal["enterprise", "domain"] | None = None
    # ...
```

---

### 2. Three-Tier Inheritance Merge Strategy

**Decision**: Use explicit merge strategies per field (OVERRIDE, EXTEND, FORBID)

**Rationale**:
- Different fields require different merge behavior
- Security policies must be FORBID (immutable)
- Plugin lists use EXTEND by default, OVERRIDE with explicit marker
- Clear semantics prevent ambiguity

**Merge Strategies**:

| Field | Strategy | Behavior |
|-------|----------|----------|
| `plugins.*` | OVERRIDE | Child completely replaces parent selection |
| `approved_plugins` | FORBID | Enterprise only, inherited but not modifiable |
| `governance.pii_encryption` | FORBID | Can only strengthen (required > optional) |
| `governance.audit_logging` | FORBID | Can only strengthen (enabled > disabled) |
| `governance.policy_enforcement_level` | FORBID | Can only strengthen (strict > warn > off) |
| `governance.data_retention_days` | EXTEND | Child can specify stricter (higher value) |
| `metadata` | OVERRIDE | Child metadata replaces parent |

**Implementation Pattern**:
```python
from enum import Enum

class MergeStrategy(Enum):
    OVERRIDE = "override"   # Child replaces parent
    EXTEND = "extend"       # Child adds to parent
    FORBID = "forbid"       # Parent immutable, child inherits only

FIELD_MERGE_STRATEGIES = {
    "plugins": MergeStrategy.OVERRIDE,
    "approved_plugins": MergeStrategy.FORBID,
    "governance.pii_encryption": MergeStrategy.FORBID,
    # ...
}
```

---

### 3. Security Policy Immutability Enforcement

**Decision**: Implement policy comparison with "only strengthen" validation

**Rationale**:
- Enterprise sets baseline security (pii_encryption=required, audit_logging=enabled)
- Domains can match or strengthen but never weaken
- Compile-time validation prevents runtime security bypasses

**Policy Strength Ordering**:
```python
PII_ENCRYPTION_STRENGTH = {"optional": 0, "required": 1}
AUDIT_LOGGING_STRENGTH = {"disabled": 0, "enabled": 1}
POLICY_LEVEL_STRENGTH = {"off": 0, "warn": 1, "strict": 2}

def validate_security_policy_not_weakened(
    parent: GovernanceConfig,
    child: GovernanceConfig
) -> list[str]:
    """Return list of violations if child weakens parent."""
    violations = []

    if child.pii_encryption and parent.pii_encryption:
        if PII_ENCRYPTION_STRENGTH[child.pii_encryption] < PII_ENCRYPTION_STRENGTH[parent.pii_encryption]:
            violations.append(
                f"Cannot weaken pii_encryption: parent={parent.pii_encryption}, child={child.pii_encryption}"
            )
    # ... similar for other fields
    return violations
```

---

### 4. Plugin Selection Validation Against Registry

**Decision**: Validate at schema load time against plugin registry entry points

**Rationale**:
- Entry points are discovered via `importlib.metadata.entry_points()`
- Validation ensures selected plugins exist before compilation
- Provides helpful error messages listing available alternatives

**Implementation Pattern**:
```python
from importlib.metadata import entry_points

def get_available_plugins(category: str) -> list[str]:
    """Get available plugins for a category from entry points."""
    eps = entry_points(group=f"floe.{category}")
    return [ep.name for ep in eps]

def validate_plugin_selection(category: str, selected: str) -> None:
    """Raise ValidationError if plugin not available."""
    available = get_available_plugins(category)
    if selected not in available:
        raise ValueError(
            f"Plugin '{selected}' not found for {category}. "
            f"Available: {', '.join(available)}"
        )
```

---

### 5. Secret Reference Format and Validation

**Decision**: Use structured SecretReference with source type and key

**Rationale**:
- Supports multiple secret backends (K8s Secrets, ESO, Vault)
- Validation ensures format correctness without resolution
- Runtime resolution via SecretsPlugin at execution time

**SecretReference Schema**:
```python
class SecretSource(Enum):
    ENV = "env"           # Environment variable
    K8S = "kubernetes"    # Kubernetes Secret
    VAULT = "vault"       # HashiCorp Vault
    ESO = "external-secrets"  # External Secrets Operator

class SecretReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: SecretSource = SecretSource.K8S
    name: str = Field(..., pattern=r"^[a-z0-9-]+$")
    key: str | None = None  # Optional key within secret

    def to_env_var_syntax(self) -> str:
        """Convert to dbt env_var syntax for profiles.yml."""
        return f"{{{{ env_var('{self.name.upper()}') }}}}"
```

---

### 6. JSON Schema Export for IDE Autocomplete

**Decision**: Export JSON Schema via Pydantic's `model_json_schema()` with custom ref handling

**Rationale**:
- VS Code, PyCharm, and other IDEs support JSON Schema for YAML autocomplete
- Pydantic v2 generates JSON Schema 2020-12 compatible output
- Custom `$schema` reference enables editor detection

**Implementation Pattern**:
```python
import json
from pathlib import Path

def export_json_schema(output_path: Path) -> None:
    """Export manifest JSON Schema for IDE autocomplete."""
    schema = PlatformManifest.model_json_schema()

    # Add $schema for editor recognition
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://floe.dev/schemas/manifest.schema.json"

    output_path.write_text(json.dumps(schema, indent=2))
```

**manifest.yaml usage**:
```yaml
# yaml-language-server: $schema=https://floe.dev/schemas/manifest.schema.json
apiVersion: floe.dev/v1
kind: Manifest
# ... autocomplete works here
```

---

### 7. Forward Compatibility with Unknown Fields

**Decision**: Warn on unknown fields but don't reject (extra="allow" with warning)

**Rationale**:
- Enables older clients to load manifests with new fields from newer versions
- Warning alerts users to potential typos or version mismatch
- Prevents breaking changes when adding optional fields

**Implementation Pattern**:
```python
import warnings
from pydantic import model_validator

class PlatformManifest(BaseModel):
    model_config = ConfigDict(extra="allow")  # Accept unknown fields

    @model_validator(mode="after")
    def warn_unknown_fields(self) -> "PlatformManifest":
        """Warn about unknown fields for forward compatibility."""
        known_fields = set(self.model_fields.keys())
        all_fields = set(self.__dict__.keys())
        unknown = all_fields - known_fields - {"__pydantic_extra__"}

        if unknown:
            warnings.warn(
                f"Unknown fields in manifest (may be from newer version): {unknown}",
                UserWarning
            )
        return self
```

---

### 8. Scope Field Constraints Validation

**Decision**: Use model_validator to enforce scope-dependent constraints

**Rationale**:
- scope=enterprise: parent_manifest must be None
- scope=domain: parent_manifest must be set
- scope=None: 2-tier mode, parent_manifest must be None
- Cross-field validation via Pydantic model_validator

**Implementation Pattern**:
```python
from pydantic import model_validator

class PlatformManifest(BaseModel):
    scope: Literal["enterprise", "domain"] | None = None
    parent_manifest: str | None = None

    @model_validator(mode="after")
    def validate_scope_constraints(self) -> "PlatformManifest":
        """Validate scope-dependent field constraints."""
        if self.scope == "enterprise" and self.parent_manifest is not None:
            raise ValueError("Enterprise manifest cannot have parent_manifest")

        if self.scope == "domain" and self.parent_manifest is None:
            raise ValueError("Domain manifest must specify parent_manifest")

        if self.scope is None and self.parent_manifest is not None:
            raise ValueError("2-tier manifest (scope=None) cannot have parent_manifest")

        return self
```

---

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| pydantic | >=2.0,<3.0 | Schema validation, JSON Schema export |
| pydantic-settings | >=2.0 | Environment variable handling |
| PyYAML | >=6.0 | YAML parsing |
| structlog | >=23.0 | Structured logging |

## Open Questions (Resolved)

All NEEDS CLARIFICATION items from Technical Context have been resolved through the spec clarification process:

1. **2-tier vs 3-tier mode**: Both supported via scope field (None, "enterprise", "domain")
2. **Environment handling**: Runtime via FLOE_ENV, no compile-time env_overrides
3. **Security policy immutability**: Enforced - children cannot weaken parent policies

## References

- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core)
- ADR-0038: Data Mesh Architecture
- ADR-0037: Composability Principle
- REQ-100 to REQ-115: Unified Manifest Schema Requirements
