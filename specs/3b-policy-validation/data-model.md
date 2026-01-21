# Data Model: Policy Validation Enhancement (Epic 3B)

**Date**: 2026-01-20
**Branch**: `3b-policy-validation`

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GovernanceConfig                                  │
│  (Extended from Epic 3A)                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  + custom_rules: list[CustomRule]                                           │
│  + policy_overrides: list[PolicyOverride]                                   │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│   CustomRule    │  │ PolicyOverride  │  │ PolicyEnforcer      │
│  (New Entity)   │  │  (New Entity)   │  │ (Extended)          │
├─────────────────┤  ├─────────────────┤  ├─────────────────────┤
│ type: str       │  │ pattern: str    │  │ + semantic_validator│
│ applies_to: str │  │ action: str     │  │ + custom_validator  │
│ parameters: {}  │  │ reason: str     │  │ + apply_overrides() │
└─────────────────┘  │ expires: date   │  └─────────────────────┘
                     └─────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Violation (Extended)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  + downstream_impact: list[str] | None                                       │
│  + first_detected: datetime | None                                           │
│  + occurrences: int | None                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EnforcementResult (Extended)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  + violations_by_model: dict[str, list[Violation]]                           │
│  + semantic_violations: int                                                  │
│  + custom_rule_violations: int                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Entity Definitions

### CustomRule (New)

Represents a user-defined validation rule configured in manifest.yaml.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `str` | Yes | Rule type discriminator (require_tags_for_prefix, require_meta_field, require_tests_of_type) |
| `applies_to` | `str` | No | Glob pattern for model selection (default: "*") |
| `parameters` | `dict[str, Any]` | Yes | Type-specific parameters |

**Subtypes (Discriminated Union):**

1. **RequireTagsForPrefix**
   - `prefix: str` - Model name prefix (e.g., "gold_")
   - `required_tags: list[str]` - Tags that must be present

2. **RequireMetaField**
   - `field: str` - Meta field name (e.g., "owner")
   - `required: bool` - Whether field must have non-empty value

3. **RequireTestsOfType**
   - `test_types: list[str]` - Required test types (not_null, unique, etc.)
   - `min_columns: int` - Minimum columns with these tests (default: 1)

**Validation Rules:**
- V1: `type` must be one of the supported rule types
- V2: `applies_to` must be a valid glob pattern
- V3: Type-specific parameters must match the schema for that type

---

### PolicyOverride (New)

Represents an exception to normal policy enforcement for migration/legacy support.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pattern` | `str` | Yes | Glob pattern matching model names (e.g., "legacy_*") |
| `action` | `Literal["downgrade", "exclude"]` | Yes | downgrade=error→warning, exclude=skip validation |
| `reason` | `str` | Yes | Audit trail explaining why override exists |
| `expires` | `date \| None` | No | Expiration date (ISO-8601, override ignored after) |
| `policy_types` | `list[str] \| None` | No | Limit to specific policies (default: all) |

**Validation Rules:**
- V1: `pattern` must be a valid glob pattern
- V2: `reason` must be non-empty (audit requirement)
- V3: `expires` must be in the future at configuration time (warning if not)
- V4: `policy_types` values must be valid: naming, coverage, documentation, semantic, custom

---

### Violation (Extended)

Existing entity extended with context fields for Epic 3B.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error_code` | `str` | Yes | Unique error identifier (FLOE-Exxx) |
| `policy_type` | `str` | Yes | Policy category (naming, coverage, documentation, semantic, custom) |
| `model_name` | `str` | Yes | Model that violated the policy |
| `message` | `str` | Yes | Human-readable violation description |
| `suggestion` | `str` | Yes | Actionable fix suggestion |
| `severity` | `Literal["error", "warning"]` | Yes | Violation severity |
| `column_name` | `str \| None` | No | Column name (for column-level violations) |
| `file_path` | `str \| None` | No | File path (from dbt patch_path) |
| **`downstream_impact`** | `list[str] \| None` | No | **NEW**: Models affected by this model |
| **`first_detected`** | `datetime \| None` | No | **NEW**: When first seen (for tracking) |
| **`occurrences`** | `int \| None` | No | **NEW**: Number of times detected |
| **`override_applied`** | `str \| None` | No | **NEW**: Override pattern if severity was modified |

**New Error Codes (Epic 3B):**

| Code | Policy Type | Description |
|------|-------------|-------------|
| FLOE-E301 | semantic | Model references non-existent model via ref() |
| FLOE-E302 | semantic | Circular dependency detected in model DAG |
| FLOE-E303 | semantic | Model references undefined source |
| FLOE-E400 | custom | Model missing required tags (require_tags_for_prefix) |
| FLOE-E401 | custom | Model missing required meta field (require_meta_field) |
| FLOE-E402 | custom | Model missing required test types (require_tests_of_type) |

---

### EnforcementResult (Extended)

Existing entity extended with Epic 3B fields.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `passed` | `bool` | Yes | Overall pass/fail status |
| `violations` | `list[Violation]` | Yes | All violations found |
| `summary` | `EnforcementSummary` | Yes | Aggregated statistics |
| `enforcement_level` | `str` | Yes | Applied enforcement level |
| `timestamp` | `datetime` | Yes | When enforcement ran |
| `manifest_version` | `str` | Yes | dbt manifest version |
| **`violations_by_model`** | `dict[str, list[Violation]]` | No | **NEW**: Computed property (not stored) - groups violations by model_name |

---

### EnforcementSummary (Extended)

Extended with Epic 3B fields.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `total_models` | `int` | Yes | Total models in manifest |
| `models_validated` | `int` | Yes | Models actually validated |
| `naming_violations` | `int` | Yes | Count of naming violations |
| `coverage_violations` | `int` | Yes | Count of coverage violations |
| `documentation_violations` | `int` | Yes | Count of documentation violations |
| **`semantic_violations`** | `int` | Yes | **NEW**: Count of semantic violations |
| **`custom_rule_violations`** | `int` | Yes | **NEW**: Count of custom rule violations |
| `duration_ms` | `float` | Yes | Enforcement duration in milliseconds |
| **`overrides_applied`** | `int` | No | **NEW**: Count of overrides applied |

---

### EnforcementResultSummary (New)

Lightweight summary for inclusion in CompiledArtifacts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `passed` | `bool` | Yes | Overall pass/fail status |
| `error_count` | `int` | Yes | Number of error-severity violations |
| `warning_count` | `int` | Yes | Number of warning-severity violations |
| `policy_types_checked` | `list[str]` | Yes | Which policies were enforced |
| `models_validated` | `int` | Yes | Number of models checked |
| `enforcement_level` | `str` | Yes | Applied enforcement level |

**Notes:**
- This summary goes into CompiledArtifacts (contract update to v0.3.0)
- Full violations exported separately (SARIF/JSON/HTML)

---

### ValidationReport (New)

Export-ready representation for reporting.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format` | `Literal["json", "sarif", "html"]` | Yes | Export format |
| `result` | `EnforcementResult` | Yes | Full enforcement result |
| `metadata` | `ReportMetadata` | Yes | Report generation metadata |

---

### ReportMetadata (New)

Metadata for exported reports.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `generated_at` | `datetime` | Yes | Report generation timestamp |
| `tool_name` | `str` | Yes | Always "floe-policy-enforcer" |
| `tool_version` | `str` | Yes | floe version |
| `manifest_path` | `str` | Yes | Path to dbt manifest |
| `config_path` | `str` | Yes | Path to platform manifest |

---

## State Transitions

### Violation Severity Flow

```
Model validated
      │
      ▼
┌─────────────┐     Pattern matches     ┌───────────────────┐
│  Violation  │ ───────────────────────►│  Check Overrides  │
│  generated  │                         │                   │
└─────────────┘                         └─────────┬─────────┘
                                                  │
                         ┌────────────────────────┼────────────────────────┐
                         │                        │                        │
                         ▼                        ▼                        ▼
                ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
                │  action=exclude │      │ action=downgrade│      │   No override   │
                │  Skip entirely  │      │  error→warning  │      │ Keep severity   │
                └─────────────────┘      └─────────────────┘      └─────────────────┘
```

### Enforcement Level Impact

| Level | Error Violations | Warning Violations | Result |
|-------|-----------------|-------------------|--------|
| off | Not generated | Not generated | passed=True |
| warn | Generated as warnings | Generated as warnings | passed=True |
| strict | Generated as errors | Generated as warnings | passed=False if errors |

---

## Relationships

```
GovernanceConfig (1) ──────────► (0..*) CustomRule
GovernanceConfig (1) ──────────► (0..*) PolicyOverride
PolicyEnforcer (1) ◄──────────── (1) GovernanceConfig

PolicyEnforcer (1) ──────────► (1) SemanticValidator
PolicyEnforcer (1) ──────────► (1) CustomRuleValidator
PolicyEnforcer (1) ──────────► (1..*) Violation

EnforcementResult (1) ──────► (0..*) Violation
EnforcementResult (1) ──────► (1) EnforcementSummary

CompiledArtifacts (1) ──────► (0..1) EnforcementResultSummary
```

---

## Contract Version Impact

**CompiledArtifacts v0.3.0** (Minor version bump - additive):
- Add optional `enforcement_result: EnforcementResultSummary | None`
- Backward compatible (existing v0.2.0 artifacts still valid)

**Violation Schema** (Internal, not versioned):
- Add optional fields (downstream_impact, first_detected, occurrences, override_applied)
- Backward compatible (existing code ignores new fields)
