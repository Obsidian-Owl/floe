# Research: Policy Validation Enhancement (Epic 3B)

**Date**: 2026-01-20
**Branch**: `3b-policy-validation`

## Prior Decisions (from Agent-Memory)

> "The architecture decision regarding policy enforcement emphasizes that it should be a core module within floe-core and not a plugin. This decision is based on the need for compile-time enforcement..."

- **ADR-0015**: PolicyEnforcer is a CORE MODULE (not a plugin)
- **Rationale**: Organizational rules are configuration, not implementations
- **Epic 3A Complete**: NamingValidator, CoverageValidator, DocumentationValidator implemented

---

## Decision 1: Semantic Validator Architecture

### Decision
Add `SemanticValidator` following the same pattern as existing validators, placed in `floe_core/enforcement/validators/semantic.py`.

### Rationale
- Consistent with existing validator pattern (NamingValidator, CoverageValidator, DocumentationValidator)
- Operates on dbt manifest.json like other validators
- Uses same `Violation` result model

### Alternatives Considered
1. **External tool (dbt-checkpoint)**: Rejected - dbt-checkpoint validates artifact structure, not semantic model relationships
2. **Plugin-based validators**: Rejected (per ADR-0015) - validators are core, rules are configuration

### Implementation Notes
- Use manifest's `parent_map` and `child_map` for dependency traversal
- Detect cycles using Tarjan's or Kahn's algorithm
- FLOE-E301 (missing ref), FLOE-E302 (circular dep), FLOE-E303 (missing source)

---

## Decision 2: Custom Rules Configuration Schema

### Decision
Extend `GovernanceConfig` with `custom_rules: list[CustomRule]` using a discriminated union pattern.

### Schema Design
```yaml
governance:
  custom_rules:
    - type: require_tags_for_prefix
      prefix: "gold_"
      required_tags: ["tested", "documented"]
    - type: require_meta_field
      field: "owner"
      applies_to: "gold_*"  # glob pattern
    - type: require_tests_of_type
      test_types: ["not_null", "unique"]
      applies_to: "*"  # all models
```

### Rationale
- Declarative YAML > Python code for platform teams
- Discriminated union (`type` field) enables validation and type safety
- Glob patterns (`*`, `?`) for flexible model targeting

### Alternatives Considered
1. **OPA/Rego policies**: Rejected - adds dependency, learning curve
2. **Python rule classes**: Rejected - requires code changes for new rules
3. **JSON Schema custom keywords**: Rejected - limited expressiveness

### Implementation Notes
- `CustomRule` base model with `type` discriminator
- `CustomRuleValidator` iterates rules, applies to matching models
- FLOE-E4xx error codes (E400-E499 reserved)

---

## Decision 3: Severity Override Mechanism

### Decision
Add `policy_overrides` section to `GovernanceConfig` with pattern matching and expiration dates.

### Schema Design
```yaml
governance:
  policy_overrides:
    - pattern: "legacy_*"
      action: downgrade  # error -> warning
      reason: "Legacy models being migrated - tracked in JIRA-123"
      expires: "2026-06-01"
    - pattern: "test_*"
      action: exclude    # skip entirely
      reason: "Test fixtures exempt from policy"
```

### Rationale
- Real migrations require flexibility
- Expiration dates prevent technical debt accumulation
- `reason` field provides audit trail

### Alternatives Considered
1. **Model-level config (dbt meta)**: Rejected - scattered across models, hard to audit
2. **Inline skip markers**: Rejected - bypasses centralized governance

### Implementation Notes
- `PolicyOverride` Pydantic model with validation
- Override check happens BEFORE violation generation
- Expired overrides logged as warnings, ignored in enforcement

---

## Decision 4: Violation Context Enhancement

### Decision
Extend `Violation` model with optional context fields: `downstream_impact`, `first_detected`, `occurrences`.

### Schema Extension
```python
class Violation(BaseModel):
    # Existing fields...
    error_code: str
    message: str
    model_name: str
    severity: Literal["error", "warning"]

    # New context fields (optional)
    downstream_impact: list[str] | None = None  # affected models
    first_detected: datetime | None = None       # historical tracking
    occurrences: int | None = None               # repeat count
```

### Rationale
- Context helps prioritization without breaking existing code
- Optional fields maintain backward compatibility
- Downstream impact computed from manifest child_map

### Alternatives Considered
1. **Separate ViolationContext model**: Rejected - complicates API
2. **Rich error messages only**: Rejected - not machine-readable

### Implementation Notes
- `downstream_impact` computed lazily when `include_context=True`
- Historical tracking requires state file (optional, can be added later)
- Group violations by model in `EnforcementResult.violations_by_model`

---

## Decision 5: SARIF Export Format

### Decision
Implement SARIF 2.1.0 export using [GitHub Code Scanning schema subset](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning).

### SARIF Structure
```json
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [{
    "tool": {
      "driver": {
        "name": "floe-policy-enforcer",
        "version": "0.2.0",
        "rules": [
          {"id": "FLOE-E201", "name": "naming-violation", ...}
        ]
      }
    },
    "results": [
      {
        "ruleId": "FLOE-E201",
        "level": "error",
        "message": {"text": "Model 'stg_customers' violates medallion naming"},
        "locations": [{
          "physicalLocation": {
            "artifactLocation": {"uri": "models/staging/stg_customers.sql"}
          }
        }]
      }
    ]
  }]
}
```

### Rationale
- SARIF is the GitHub Code Scanning standard
- Enables automated PR annotations
- Widely supported by CI/CD tools

### Alternatives Considered
1. **Custom JSON format**: Rejected - no ecosystem integration
2. **JUnit XML**: Rejected - test results, not analysis findings
3. **CodeClimate format**: Rejected - less widespread than SARIF

### Implementation Notes
- Map Violation.error_code to SARIF rule.id
- Map Violation.severity to SARIF level (error/warning)
- File locations from dbt manifest patch_path
- HTML export uses Jinja2 template for readability

### References
- [SARIF 2.1.0 Schema](https://github.com/oasis-tcs/sarif-spec/blob/main/sarif-2.1/schema/sarif-schema-2.1.0.json)
- [GitHub SARIF Support](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning)

---

## Decision 6: Pipeline Integration Point

### Decision
Enforcement results stored in CompiledArtifacts via new `enforcement_result` field.

### Schema Extension
```python
class CompiledArtifacts(BaseModel):
    # Existing fields...

    # Epic 3B addition
    enforcement_result: EnforcementResultSummary | None = Field(
        default=None,
        description="Policy enforcement result summary (v0.3.0+)",
    )
```

### Rationale
- CompiledArtifacts is the sole cross-package contract (Constitution Principle IV)
- Downstream consumers (floe-dagster, floe-cli) can read enforcement status
- Summary only (not full violations) to keep artifacts small

### Alternatives Considered
1. **Separate enforcement.json file**: Rejected - fragments contract
2. **Full violations in artifacts**: Rejected - bloats file, violations go to SARIF

### Implementation Notes
- `EnforcementResultSummary` contains: passed, error_count, warning_count, policy_types
- Full violations exported to separate file (JSON/SARIF/HTML)
- `run_enforce_stage()` already exists, update to return summary for artifacts

---

## Technical Context Resolution

| Item | Resolution |
|------|------------|
| **Language/Version** | Python 3.10+ (matches floe-core) |
| **Primary Dependencies** | Pydantic v2, structlog, PyYAML, Jinja2 (HTML export) |
| **Storage** | N/A (enforcement is stateless) |
| **Testing** | pytest, K8s-native (Kind cluster) |
| **Target Platform** | Linux (CI), macOS (dev) |
| **Performance Goals** | <500ms for 500 models (SC-001) |
| **Constraints** | Must extend existing PolicyEnforcer without breaking API |

---

## Open Questions (None Remaining)

All NEEDS CLARIFICATION items resolved through research.
