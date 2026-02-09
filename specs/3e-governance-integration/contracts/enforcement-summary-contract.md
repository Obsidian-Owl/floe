# Contract: EnforcementResultSummary Extension

**Version**: 0.4.0 (MINOR bump)
**Change Type**: Additive fields
**Backward Compatible**: Yes

## Schema Change

### EnforcementResultSummary

```python
# packages/floe-core/src/floe_core/schemas/compiled_artifacts.py

class EnforcementResultSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Existing fields (unchanged)
    passed: bool
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    policy_types_checked: list[str]
    models_validated: int = Field(ge=0)
    enforcement_level: Literal["off", "warn", "strict"]

    # NEW in Epic 3E (all optional/defaulted)
    rbac_principal: str | None = Field(
        default=None,
        description="Authenticated principal name if RBAC enabled"
    )
    secrets_scanned: int = Field(
        default=0,
        ge=0,
        description="Number of files scanned for secrets"
    )
```

## Impact on CompiledArtifacts

`CompiledArtifacts.enforcement_result` field (type: `EnforcementResultSummary | None`) now carries additional fields. Since the field itself is already optional and the new fields have defaults, this is fully backward compatible.

## Compatibility Proof

1. `rbac_principal` defaults to `None` — existing summaries without RBAC are unchanged
2. `secrets_scanned` defaults to `0` — existing summaries without scanning are unchanged
3. `policy_types_checked: list[str]` already accommodates new types dynamically
4. Serialization/deserialization is backward compatible (missing fields use defaults)

## CompiledArtifacts Version Bump

The `COMPILED_ARTIFACTS_VERSION` in `schemas/versions.py` must be bumped from current to next MINOR version to signal the schema extension.

## Verification Tests

```python
def test_enforcement_summary_backward_compatible():
    """Old-style summaries still parse."""
    summary = EnforcementResultSummary(
        passed=True,
        error_count=0,
        warning_count=0,
        policy_types_checked=["naming"],
        models_validated=5,
        enforcement_level="warn",
    )
    assert summary.rbac_principal is None
    assert summary.secrets_scanned == 0

def test_enforcement_summary_with_3e_fields():
    """New 3E fields are accepted."""
    summary = EnforcementResultSummary(
        passed=True,
        error_count=0,
        warning_count=2,
        policy_types_checked=["naming", "rbac", "secret_scanning"],
        models_validated=5,
        enforcement_level="warn",
        rbac_principal="alice@example.com",
        secrets_scanned=42,
    )
    assert summary.rbac_principal == "alice@example.com"
    assert summary.secrets_scanned == 42
```
