# Research: Policy Enforcer Core (Epic 3A)

**Date**: 2026-01-19
**Branch**: `3a-policy-enforcer`

## Prior Decisions (from Agent Memory)

- **PolicyEnforcer is CORE MODULE, not plugin**: Per ADR-0015, policy enforcement is configuration-driven, not implementation-variable. Organizational rules (naming conventions, coverage thresholds) are not pluggable.
- **Test coverage uses COLUMN-LEVEL calculation**: Clarified during /speckit.clarify - uses `columns_with_at_least_one_test / total_columns` matching industry-standard dbt-coverage tool.

## Research Topics

### 1. Compilation Pipeline Integration Point

**Decision**: Integrate PolicyEnforcer at Stage 4 (ENFORCE) of the existing 6-stage pipeline.

**Rationale**: The compilation pipeline in `floe_core/compilation/stages.py` already defines a placeholder for ENFORCE stage:
```python
# Stage 4: ENFORCE - Policy enforcement
with create_span("compile.enforce", ...):
    # Placeholder for governance enforcement (future epic)
```

**Evidence**: Lines 232-245 of `stages.py` show the ENFORCE stage is ready for PolicyEnforcer integration.

**Alternatives Rejected**:
- Adding a new stage → Would require version bump to CompiledArtifacts, break existing integrations
- Embedding in VALIDATE stage → Conflates Pydantic schema validation with policy enforcement; harder to debug

### 2. GovernanceConfig Schema Extension

**Decision**: Extend existing `GovernanceConfig` in `manifest.py` with new nested models for naming and quality gates.

**Rationale**: GovernanceConfig already exists with security fields (pii_encryption, audit_logging, policy_enforcement_level). Adding naming/quality_gates as nested models maintains backward compatibility.

**Current Schema** (manifest.py:53-118):
```python
class GovernanceConfig(BaseModel):
    pii_encryption: Literal["required", "optional"] | None
    audit_logging: Literal["enabled", "disabled"] | None
    policy_enforcement_level: Literal["off", "warn", "strict"] | None
    data_retention_days: int | None
```

**Proposed Extension**:
```python
class NamingConfig(BaseModel):
    enforcement: Literal["off", "warn", "strict"] = "warn"
    pattern: Literal["medallion", "kimball", "custom"] = "medallion"
    custom_patterns: list[str] | None = None

class QualityGatesConfig(BaseModel):
    minimum_test_coverage: int = 80  # percentage
    require_descriptions: bool = False
    require_column_descriptions: bool = False
    block_on_failure: bool = True

class GovernanceConfig(BaseModel):
    # Existing fields...
    naming: NamingConfig | None = None
    quality_gates: QualityGatesConfig | None = None
```

### 3. Policy Strength Ordering for New Fields

**Decision**: Extend existing `validation.py` strength constants to include naming and coverage thresholds.

**Rationale**: `validation.py` already defines `POLICY_LEVEL_STRENGTH` and `validate_security_policy_not_weakened()`. The same pattern applies to:
- `naming.enforcement`: strict (3) > warn (2) > off (1) [reuse existing constant]
- `minimum_test_coverage`: higher percentage is stricter (numeric comparison)
- `require_descriptions`: true > false (boolean strengthening)

### 4. dbt Manifest Parsing

**Decision**: Parse dbt `manifest.json` (compiled by dbt) to extract model metadata for validation.

**Rationale**: dbt manifest contains all model names, columns, tests, and descriptions in a single JSON file. This avoids parsing raw SQL or YAML.

**Key Manifest Fields**:
```json
{
  "nodes": {
    "model.project.customers": {
      "name": "customers",
      "columns": {"id": {...}, "email": {...}},
      "description": "Customer master data",
      "meta": {}
    }
  }
}
```

**Coverage Calculation**:
- Parse `manifest.json` nodes for models
- For each model, count columns with tests from `manifest.json` child_map
- Formula: `(columns_with_tests / total_columns) * 100`

### 5. Naming Pattern Regex Definitions

**Decision**: Define built-in regex patterns for medallion and kimball architectures.

**Patterns**:
| Pattern | Regex | Examples |
|---------|-------|----------|
| medallion | `^(bronze\|silver\|gold)_[a-z][a-z0-9_]*$` | `bronze_orders`, `silver_customers`, `gold_revenue` |
| kimball | `^(dim\|fact\|bridge\|hub\|link\|sat)_[a-z][a-z0-9_]*$` | `dim_customer`, `fact_orders`, `bridge_order_product` |
| custom | User-defined list of regex patterns | Any valid regex |

**Layer Detection** (for layer-specific thresholds):
- If model name matches `^bronze_.*$` → bronze layer
- If model name matches `^silver_.*$` → silver layer
- If model name matches `^gold_.*$` → gold layer

### 6. Error Code Schema

**Decision**: Use FLOE-EXXX format for policy violations.

**Error Code Ranges**:
| Range | Category | Examples |
|-------|----------|----------|
| FLOE-E200-E209 | Naming violations | FLOE-E201: Invalid model name |
| FLOE-E210-E219 | Coverage violations | FLOE-E210: Insufficient test coverage |
| FLOE-E220-E229 | Documentation violations | FLOE-E220: Missing model description |
| FLOE-E230-E239 | Policy inheritance violations | FLOE-E230: Policy weakening attempted |

### 7. Dry-Run Mode Implementation

**Decision**: Add `--dry-run` flag to `floe compile` CLI that sets enforcement level to `warn` temporarily.

**Rationale**: Dry-run mode should show what would fail without blocking. Setting `enforcement: warn` achieves this cleanly without special casing.

**Implementation**:
```python
def compile_pipeline(..., dry_run: bool = False):
    if dry_run:
        # Override enforcement level for preview
        effective_governance = governance.model_copy(
            update={"naming": NamingConfig(enforcement="warn"), ...}
        )
```

## Architecture Alignment Verification

### Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Technology Ownership | ✅ Pass | PolicyEnforcer validates dbt manifest metadata, does NOT parse SQL |
| II. Plugin-First | ✅ Pass | PolicyEnforcer is CORE MODULE (per ADR-0015), not a plugin |
| III. Enforced vs Pluggable | ✅ Pass | Policy enforcement is ENFORCED standard, not pluggable |
| IV. Contract-Driven | ✅ Pass | GovernanceConfig is Pydantic model; no FloeSpec passing |
| V. K8s-Native Testing | ✅ Pass | Integration tests will use Kind cluster |
| VI. Security First | ✅ Pass | No shell execution; Pydantic validation for all input |
| VII. Four-Layer Architecture | ✅ Pass | PolicyEnforcer runs at Layer 2 (Configuration) |
| VIII. Observability | ✅ Pass | Will emit OTel spans and structlog events |

## Risk Assessment

### Identified Risks

1. **dbt manifest compatibility**: Different dbt versions may have different manifest schemas
   - **Mitigation**: Test against dbt 1.7, 1.8, 1.9 manifests; use defensive JSON parsing

2. **Custom regex DoS**: User-provided regex could be exponential (ReDoS)
   - **Mitigation**: Validate regex before compiling; set timeout on regex matching

3. **Large project performance**: 500+ models might slow compilation
   - **Mitigation**: Parallel validation per model; early exit on first error in strict mode

## References

- ADR-0015: Policy Enforcement as Core Module
- ADR-0016: Platform Enforcement Architecture
- `packages/floe-core/src/floe_core/compilation/stages.py` - ENFORCE stage placeholder
- `packages/floe-core/src/floe_core/schemas/validation.py` - Policy strength constants
- `packages/floe-core/src/floe_core/schemas/manifest.py` - GovernanceConfig schema
