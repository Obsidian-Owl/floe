# Contract: Violation.policy_type Extension

**Version**: 0.4.0 (MINOR bump)
**Change Type**: Additive Literal extension
**Backward Compatible**: Yes

## Schema Change

### Violation.policy_type

```python
# packages/floe-core/src/floe_core/enforcement/result.py

# Before (v0.3.0):
policy_type: Literal["naming", "coverage", "documentation", "semantic", "custom", "data_contract"]

# After (v0.4.0):
policy_type: Literal[
    "naming", "coverage", "documentation", "semantic", "custom", "data_contract",
    "rbac", "secret_scanning", "network_policy",
]
```

### VALID_POLICY_TYPES

```python
# packages/floe-core/src/floe_core/schemas/governance.py

VALID_POLICY_TYPES = frozenset({
    "naming", "coverage", "documentation", "semantic", "custom", "data_contract",
    "rbac", "secret_scanning", "network_policy",
})
```

### EnforcementSummary Counters

```python
# packages/floe-core/src/floe_core/enforcement/result.py

class EnforcementSummary(BaseModel):
    # ... existing counters ...
    rbac_violations: int = Field(default=0, ge=0)
    secret_violations: int = Field(default=0, ge=0)
    network_policy_violations: int = Field(default=0, ge=0)
```

## Compatibility Proof

1. **Literal extension is additive** — existing validators produce only existing types; new types come from new validators
2. **New counters default to 0** — existing summary creation produces 0 for new counters
3. **VALID_POLICY_TYPES is a superset** — existing policy overrides still validate
4. **JSON schema widens** — consumers that accept the old enum accept the new enum

## Breaking Change Risk

- Code that exhaustively matches `policy_type` with `if/elif` chains will miss new types
- Risk is LOW because `EnforcementSummary` uses dedicated counters, and the `violations_by_model` property groups generically

## Verification Tests

```python
def test_existing_policy_types_still_valid():
    """All existing policy types remain in the Literal."""
    for pt in ["naming", "coverage", "documentation", "semantic", "custom", "data_contract"]:
        v = Violation(error_code="E001", severity="error", policy_type=pt, ...)
        assert v.policy_type == pt

def test_new_policy_types_accepted():
    """New 3E policy types are accepted."""
    for pt in ["rbac", "secret_scanning", "network_policy"]:
        v = Violation(error_code="E501", severity="error", policy_type=pt, ...)
        assert v.policy_type == pt

def test_valid_policy_types_superset():
    """VALID_POLICY_TYPES contains all types."""
    from floe_core.enforcement.result import Violation
    literal_types = set(Violation.model_fields["policy_type"].metadata[0].__args__)
    assert VALID_POLICY_TYPES == literal_types
```
