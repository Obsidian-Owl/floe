# Data Model: Policy Enforcer Core (Epic 3A)

**Date**: 2026-01-19
**Branch**: `3a-policy-enforcer`

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            GovernanceConfig                                  │
│  (Extended from existing manifest.py)                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  + pii_encryption: Literal["required", "optional"] | None    (existing)     │
│  + audit_logging: Literal["enabled", "disabled"] | None      (existing)     │
│  + policy_enforcement_level: Literal["off", "warn", "strict"] (existing)    │
│  + data_retention_days: int | None                           (existing)     │
│  + naming: NamingConfig | None                               (NEW)          │
│  + quality_gates: QualityGatesConfig | None                  (NEW)          │
└─────────────────────────────────────────────────────────────────────────────┘
                │                                    │
                ▼                                    ▼
┌───────────────────────────┐     ┌─────────────────────────────────────────┐
│       NamingConfig        │     │         QualityGatesConfig              │
├───────────────────────────┤     ├─────────────────────────────────────────┤
│ + enforcement: Literal    │     │ + minimum_test_coverage: int (0-100)    │
│     ["off","warn","strict"]│    │ + require_descriptions: bool            │
│ + pattern: Literal        │     │ + require_column_descriptions: bool     │
│     ["medallion","kimball",│    │ + block_on_failure: bool                │
│      "custom"]            │     │ + layer_thresholds: LayerThresholds|None│
│ + custom_patterns:        │     └─────────────────────────────────────────┘
│     list[str] | None      │                        │
└───────────────────────────┘                        ▼
                                  ┌─────────────────────────────────────────┐
                                  │         LayerThresholds                 │
                                  ├─────────────────────────────────────────┤
                                  │ + bronze: int (0-100)                   │
                                  │ + silver: int (0-100)                   │
                                  │ + gold: int (0-100)                     │
                                  └─────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            PolicyEnforcer                                    │
│  (New core module at floe_core/enforcement/)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ + enforce(manifest: dict, config: GovernanceConfig) -> EnforcementResult    │
│ + validate_naming(manifest: dict, config: NamingConfig) -> list[Violation]  │
│ + validate_coverage(manifest: dict, config: QualityGatesConfig) -> list[V.] │
│ + validate_documentation(manifest: dict, config: QualityGatesConfig) -> [] │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EnforcementResult                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ + passed: bool                                                              │
│ + violations: list[Violation]                                               │
│ + summary: EnforcementSummary                                               │
│ + enforcement_level: Literal["off", "warn", "strict"]                       │
│ + manifest_version: str                                                     │
│ + timestamp: datetime                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Violation                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ + error_code: str (e.g., "FLOE-E201")                                       │
│ + severity: Literal["error", "warning"]                                     │
│ + policy_type: Literal["naming", "coverage", "documentation"]               │
│ + model_name: str                                                           │
│ + column_name: str | None                                                   │
│ + message: str                                                              │
│ + expected: str                                                             │
│ + actual: str                                                               │
│ + suggestion: str                                                           │
│ + documentation_url: str                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         EnforcementSummary                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ + total_models: int                                                         │
│ + models_validated: int                                                     │
│ + naming_violations: int                                                    │
│ + coverage_violations: int                                                  │
│ + documentation_violations: int                                             │
│ + duration_ms: float                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Entity Definitions

### GovernanceConfig (Extended)

**Location**: `packages/floe-core/src/floe_core/schemas/manifest.py`
**Type**: Pydantic BaseModel (extends existing)

| Field | Type | Default | Description | Validation |
|-------|------|---------|-------------|------------|
| pii_encryption | `Literal["required", "optional"] \| None` | None | PII encryption policy (existing) | - |
| audit_logging | `Literal["enabled", "disabled"] \| None` | None | Audit logging policy (existing) | - |
| policy_enforcement_level | `Literal["off", "warn", "strict"] \| None` | None | Global enforcement level (existing) | - |
| data_retention_days | `int \| None` | None | Data retention in days (existing) | ge=1 |
| naming | `NamingConfig \| None` | None | Naming convention config (NEW) | - |
| quality_gates | `QualityGatesConfig \| None` | None | Quality gate config (NEW) | - |

### NamingConfig (New)

**Location**: `packages/floe-core/src/floe_core/schemas/governance.py` (new file)
**Type**: Pydantic BaseModel

| Field | Type | Default | Description | Validation |
|-------|------|---------|-------------|------------|
| enforcement | `Literal["off", "warn", "strict"]` | "warn" | Enforcement level for naming | - |
| pattern | `Literal["medallion", "kimball", "custom"]` | "medallion" | Naming pattern type | - |
| custom_patterns | `list[str] \| None` | None | User regex patterns | Valid regex only |

**Business Rules**:
- If `pattern == "custom"`, `custom_patterns` MUST be provided
- If `pattern != "custom"`, `custom_patterns` is ignored
- Built-in patterns have predefined regex (medallion, kimball)

**Strength Ordering** (for inheritance):
- enforcement: strict (3) > warn (2) > off (1)

### QualityGatesConfig (New)

**Location**: `packages/floe-core/src/floe_core/schemas/governance.py`
**Type**: Pydantic BaseModel

| Field | Type | Default | Description | Validation |
|-------|------|---------|-------------|------------|
| minimum_test_coverage | `int` | 80 | Minimum % column coverage | ge=0, le=100 |
| require_descriptions | `bool` | False | Require model descriptions | - |
| require_column_descriptions | `bool` | False | Require column descriptions | - |
| block_on_failure | `bool` | True | Block compile on violation | - |
| layer_thresholds | `LayerThresholds \| None` | None | Per-layer coverage thresholds | - |

**Strength Ordering** (for inheritance):
- minimum_test_coverage: higher is stricter (numeric comparison)
- require_descriptions: true > false
- require_column_descriptions: true > false
- block_on_failure: true > false (cannot relax)

### LayerThresholds (New)

**Location**: `packages/floe-core/src/floe_core/schemas/governance.py`
**Type**: Pydantic BaseModel

| Field | Type | Default | Description | Validation |
|-------|------|---------|-------------|------------|
| bronze | `int` | 50 | Bronze layer threshold | ge=0, le=100 |
| silver | `int` | 80 | Silver layer threshold | ge=0, le=100 |
| gold | `int` | 100 | Gold layer threshold | ge=0, le=100 |

### PolicyEnforcer (New)

**Location**: `packages/floe-core/src/floe_core/enforcement/policy_enforcer.py`
**Type**: Python class (core module, NOT plugin)

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `enforce()` | manifest: dict, config: GovernanceConfig | EnforcementResult | Run all validators |
| `validate_naming()` | manifest: dict, config: NamingConfig | list[Violation] | Check naming conventions |
| `validate_coverage()` | manifest: dict, config: QualityGatesConfig | list[Violation] | Check test coverage |
| `validate_documentation()` | manifest: dict, config: QualityGatesConfig | list[Violation] | Check descriptions |

### EnforcementResult (New)

**Location**: `packages/floe-core/src/floe_core/enforcement/result.py`
**Type**: Pydantic BaseModel

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| passed | `bool` | - | True if no blocking violations |
| violations | `list[Violation]` | [] | All violations found |
| summary | `EnforcementSummary` | - | Statistics summary |
| enforcement_level | `Literal["off", "warn", "strict"]` | - | Effective level used |
| manifest_version | `str` | - | Manifest version validated |
| timestamp | `datetime` | - | When validation ran |

### Violation (New)

**Location**: `packages/floe-core/src/floe_core/enforcement/violation.py`
**Type**: Pydantic BaseModel

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| error_code | `str` | FLOE-EXXX format | "FLOE-E201" |
| severity | `Literal["error", "warning"]` | Based on enforcement level | "error" |
| policy_type | `Literal["naming", "coverage", "documentation"]` | Category | "naming" |
| model_name | `str` | dbt model name | "stg_payments" |
| column_name | `str \| None` | Column if applicable | "email" |
| message | `str` | Human-readable message | "Model name violates medallion convention" |
| expected | `str` | Expected value/pattern | "^(bronze\|silver\|gold)_.*$" |
| actual | `str` | Actual value | "stg_payments" |
| suggestion | `str` | Remediation hint | "Rename to bronze_payments, silver_payments, or gold_payments" |
| documentation_url | `str` | Link to docs | "https://floe.dev/docs/naming#medallion" |

## Error Code Catalog

| Code | Category | Description | Severity |
|------|----------|-------------|----------|
| FLOE-E201 | Naming | Model name violates naming convention | error |
| FLOE-E202 | Naming | Custom pattern regex is invalid | error |
| FLOE-E210 | Coverage | Model test coverage below threshold | error |
| FLOE-E211 | Coverage | Layer-specific coverage violation | error |
| FLOE-E220 | Documentation | Missing model description | error |
| FLOE-E221 | Documentation | Missing column description | error |
| FLOE-E222 | Documentation | Placeholder description detected | warning |
| FLOE-E230 | Inheritance | Policy weakening attempted | error |
| FLOE-E231 | Inheritance | Invalid layer threshold inheritance | error |

## State Transitions

Not applicable - PolicyEnforcer is stateless. Each invocation processes input and returns result.

## Integration Points

### Input: dbt manifest.json

PolicyEnforcer reads the compiled dbt manifest (JSON) to extract:
- Model names (for naming validation)
- Column definitions (for coverage calculation)
- Test references (for coverage calculation)
- Descriptions (for documentation validation)

### Output: EnforcementResult

PolicyEnforcer returns EnforcementResult which:
- Is logged with structlog for audit
- Is emitted as OTel span attributes
- Determines compilation success/failure in `compile_pipeline()`

### Integration with stages.py

```python
# Stage 4: ENFORCE - Policy enforcement
with create_span("compile.enforce", ...):
    enforcer = PolicyEnforcer()
    result = enforcer.enforce(dbt_manifest, governance_config)
    if not result.passed and governance_config.policy_enforcement_level == "strict":
        raise PolicyEnforcementError(result.violations)
```
