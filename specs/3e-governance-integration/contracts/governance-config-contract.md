# Contract: GovernanceConfig Schema Extension

**Version**: 0.4.0 (MINOR bump from 0.3.0)
**Change Type**: Additive — 3 new optional fields
**Backward Compatible**: Yes

## Schema Change

### New Fields on GovernanceConfig

```python
# packages/floe-core/src/floe_core/schemas/manifest.py

class GovernanceConfig(BaseModel):
    # ... existing fields unchanged ...

    # NEW in Epic 3E
    rbac: RBACConfig | None = Field(default=None)
    secret_scanning: SecretScanningConfig | None = Field(default=None)
    network_policies: NetworkPoliciesConfig | None = Field(default=None)
```

### New Sub-Models

```python
class RBACConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool = False
    required_role: str | None = None
    allow_principal_fallback: bool = True

class SecretPattern(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(..., min_length=1)
    pattern: str = Field(..., min_length=1)
    severity: Literal["error", "warning"] = "error"

class SecretScanningConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool = False
    exclude_patterns: list[str] = Field(default_factory=list)
    custom_patterns: list[SecretPattern] | None = None
    severity: Literal["error", "warning"] = "error"

class NetworkPoliciesConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    enabled: bool = False
    default_deny: bool = True
    custom_egress_rules: list[dict[str, Any]] = Field(default_factory=list)
```

## Compatibility Proof

1. All 3 new fields have `default=None` — existing manifests without these fields parse without error
2. All sub-model fields have defaults — partial configs are valid
3. `extra="forbid"` prevents typos from being silently accepted
4. `frozen=True` ensures immutability

## Verification Test

```python
def test_governance_config_backward_compatible():
    """Existing manifests without 3E fields still parse."""
    old_config = GovernanceConfig(
        policy_enforcement_level="warn",
        naming=NamingConfig(enforcement="warn"),
    )
    assert old_config.rbac is None
    assert old_config.secret_scanning is None
    assert old_config.network_policies is None
```
