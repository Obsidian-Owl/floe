# Quickstart: Policy Validation Enhancement (Epic 3B)

## Prerequisites

- Epic 3A PolicyEnforcer implemented and working
- floe-core package installed
- dbt project with manifest.json generated (`dbt compile`)

---

## 1. Configure Custom Rules

Add custom validation rules to your `manifest.yaml`:

```yaml
# manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: 1.0.0
  owner: platform-team@acme.com

governance:
  policy_enforcement_level: strict

  # Existing Epic 3A config
  naming:
    enforcement: strict
    pattern: medallion

  quality_gates:
    minimum_test_coverage: 80
    require_descriptions: true

  # NEW in Epic 3B: Custom rules
  custom_rules:
    # All gold_ models must have 'tested' and 'documented' tags
    - type: require_tags_for_prefix
      prefix: "gold_"
      required_tags: ["tested", "documented"]

    # All models must have an 'owner' meta field
    - type: require_meta_field
      field: "owner"
      applies_to: "*"

    # Primary key columns must have not_null and unique tests
    - type: require_tests_of_type
      test_types: ["not_null", "unique"]
      applies_to: "gold_*"

  # NEW in Epic 3B: Policy overrides
  policy_overrides:
    # Legacy models get warnings instead of errors
    - pattern: "legacy_*"
      action: downgrade
      reason: "Legacy models being migrated - JIRA-123"
      expires: "2026-06-01"

    # Test fixtures are exempt from all policies
    - pattern: "test_*"
      action: exclude
      reason: "Test fixtures exempt from policy"
```

---

## 2. Run Policy Enforcement

### Via CLI

```bash
# Compile and enforce (blocks on violations if strict)
floe compile

# Dry-run mode (report violations without blocking)
floe compile --dry-run

# Export violations to SARIF for GitHub Code Scanning
floe compile --output-format=sarif --output=enforcement.sarif
```

### Programmatically

```python
from pathlib import Path
from floe_core.compilation.loader import load_manifest
from floe_core.compilation.stages import run_enforce_stage
import json

# Load manifest and dbt manifest
manifest = load_manifest(Path("manifest.yaml"))
with open("target/manifest.json") as f:
    dbt_manifest = json.load(f)

# Run enforcement
result = run_enforce_stage(
    governance_config=manifest.governance,
    dbt_manifest=dbt_manifest,
    dry_run=False,
)

# Check results
if result.passed:
    print("All policies passed!")
else:
    print(f"Found {len(result.violations)} violations")
    for v in result.violations:
        print(f"  [{v.error_code}] {v.model_name}: {v.message}")
```

---

## 3. Export Violation Reports

### JSON Export

```python
from floe_core.enforcement.exporters import export_json

export_json(result, Path("enforcement.json"))
```

### SARIF Export (GitHub Code Scanning)

```python
from floe_core.enforcement.exporters import export_sarif

export_sarif(result, Path("enforcement.sarif"))
```

### GitHub Actions Integration

```yaml
# .github/workflows/ci.yml
- name: Run Policy Enforcement
  run: floe compile --output-format=sarif --output=enforcement.sarif

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: enforcement.sarif
```

### HTML Report

```python
from floe_core.enforcement.exporters import export_html

export_html(result, Path("enforcement.html"))
```

---

## 4. Understanding Violations

### Error Codes Reference

| Code | Type | Description |
|------|------|-------------|
| **FLOE-E201** | naming | Model name violates naming convention |
| **FLOE-E210** | coverage | Column test coverage below threshold |
| **FLOE-E211** | coverage | Model has no column tests |
| **FLOE-E220** | documentation | Model missing description |
| **FLOE-E221** | documentation | Column missing description |
| **FLOE-E301** | semantic | Model references non-existent model |
| **FLOE-E302** | semantic | Circular dependency detected |
| **FLOE-E303** | semantic | Model references undefined source |
| **FLOE-E400** | custom | Model missing required tags |
| **FLOE-E401** | custom | Model missing required meta field |
| **FLOE-E402** | custom | Model missing required test types |

### Violation Context

Violations include context to help prioritize fixes:

```python
for violation in result.violations:
    print(f"Model: {violation.model_name}")
    print(f"Error: {violation.error_code} - {violation.message}")
    print(f"Suggestion: {violation.suggestion}")

    # Epic 3B: Enhanced context
    if violation.downstream_impact:
        print(f"Affects {len(violation.downstream_impact)} downstream models:")
        for model in violation.downstream_impact[:5]:
            print(f"  - {model}")

    if violation.override_applied:
        print(f"Override applied: {violation.override_applied}")
```

---

## 5. Common Patterns

### Gradual Migration

Use overrides to migrate legacy models incrementally:

```yaml
governance:
  policy_enforcement_level: strict

  policy_overrides:
    # Phase 1: All legacy models get warnings (Jan 2026)
    - pattern: "legacy_*"
      action: downgrade
      reason: "Phase 1 migration"
      expires: "2026-03-01"

    # Phase 2: Only specific models exempt (Mar 2026)
    - pattern: "legacy_payments"
      action: downgrade
      reason: "Phase 2 migration - payments team"
      expires: "2026-06-01"
```

### Domain-Specific Rules

Apply rules only to certain model patterns:

```yaml
governance:
  custom_rules:
    # Only gold layer needs owner metadata
    - type: require_meta_field
      field: "owner"
      applies_to: "gold_*"

    # Only mart models need freshness tests
    - type: require_tests_of_type
      test_types: ["not_null"]
      applies_to: "mart_*"
```

### CI/CD Integration

```yaml
# Block PR merge on policy violations
- name: Policy Check
  run: |
    floe compile --output-format=sarif --output=enforcement.sarif
    # Non-zero exit if violations in strict mode

- name: Upload Results
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: enforcement.sarif
```

---

## Troubleshooting

### "FLOE-E302: Circular dependency detected"

Check the `details` field for the cycle path:

```python
for v in result.violations:
    if v.error_code == "FLOE-E302":
        print(f"Cycle: {' -> '.join(v.details['cycle_path'])}")
```

### Override not applying

1. Check pattern syntax (uses glob, not regex)
2. Check expiration date hasn't passed
3. Check `policy_types` includes the violation type

```yaml
# Wrong: regex syntax
- pattern: "legacy_.*"  # WRONG

# Correct: glob syntax
- pattern: "legacy_*"   # CORRECT
```

### Violations in dry-run but not blocking

Dry-run mode converts all errors to warnings. Use `--dry-run=false` (default) for strict enforcement.
