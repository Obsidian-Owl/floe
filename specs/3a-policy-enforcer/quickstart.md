# Quickstart: Policy Enforcer Core (Epic 3A)

**Date**: 2026-01-19
**Branch**: `3a-policy-enforcer`

## Overview

This quickstart demonstrates how to configure and use the PolicyEnforcer to validate dbt models against governance policies.

## Prerequisites

- floe-core package installed
- dbt project with compiled manifest.json
- Platform manifest.yaml with governance configuration

## 1. Configure Governance in manifest.yaml

```yaml
# manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: 1.0.0
  owner: platform-team@acme.com

plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster

governance:
  # Global enforcement level (strict blocks compilation on violations)
  policy_enforcement_level: strict

  # Naming conventions
  naming:
    enforcement: strict
    pattern: medallion  # bronze_*, silver_*, gold_*

  # Quality gates
  quality_gates:
    minimum_test_coverage: 80  # Percentage (column-level)
    require_descriptions: true
    require_column_descriptions: false
    block_on_failure: true

    # Optional: Per-layer thresholds
    layer_thresholds:
      bronze: 50
      silver: 80
      gold: 100
```

## 2. Run Policy Enforcement

Policy enforcement happens automatically during `floe compile`:

```bash
# Compile with policy enforcement
floe compile

# Or with dry-run mode (preview violations without blocking)
floe compile --dry-run
```

## 3. Example Output

### Successful Compilation

```
[1/6] LOAD: Parsing floe.yaml and manifest.yaml...
[2/6] VALIDATE: Schema validation...
[3/6] RESOLVE: Plugin resolution...
[4/6] ENFORCE: Policy enforcement...
  ✓ Naming conventions: 15/15 models pass
  ✓ Test coverage: 15/15 models pass (avg 87%)
  ✓ Documentation: 15/15 models have descriptions
[5/6] COMPILE: Generating dbt profiles...
[6/6] GENERATE: Writing compiled_artifacts.json...

Compilation successful!
```

### Failed Compilation (Strict Mode)

```
[1/6] LOAD: Parsing floe.yaml and manifest.yaml...
[2/6] VALIDATE: Schema validation...
[3/6] RESOLVE: Plugin resolution...
[4/6] ENFORCE: Policy enforcement...

ERROR: Policy enforcement failed (3 violations)

FLOE-E201 [naming] stg_payments
  Model name 'stg_payments' violates medallion naming convention
  Expected: ^(bronze|silver|gold)_[a-z][a-z0-9_]*$
  Suggestion: Rename to bronze_payments, silver_payments, or gold_payments
  Docs: https://floe.dev/docs/naming#medallion

FLOE-E210 [coverage] gold_revenue
  Test coverage 60% (6/10 columns) below threshold 100%
  Expected: >= 100% (gold layer)
  Suggestion: Add tests for columns: amount, currency, tax, discount
  Docs: https://floe.dev/docs/testing#coverage

FLOE-E220 [documentation] bronze_orders
  Missing model description
  Expected: Non-empty description field in schema.yml
  Suggestion: Add description in models/bronze/schema.yml
  Docs: https://floe.dev/docs/documentation#models

Compilation FAILED (governance.policy_enforcement_level: strict)
```

## 4. Programmatic Usage

```python
from floe_core.enforcement import PolicyEnforcer
from floe_core.schemas.manifest import GovernanceConfig
from floe_core.schemas.governance import NamingConfig, QualityGatesConfig

# Load dbt manifest
import json
with open("target/manifest.json") as f:
    dbt_manifest = json.load(f)

# Create governance config
governance_config = GovernanceConfig(
    policy_enforcement_level="strict",
    naming=NamingConfig(enforcement="strict", pattern="medallion"),
    quality_gates=QualityGatesConfig(minimum_test_coverage=80),
)

# Run enforcement
enforcer = PolicyEnforcer(governance_config=governance_config)
result = enforcer.enforce(dbt_manifest)

# Check result
if result.passed:
    print(f"All {result.summary.models_validated} models pass policy checks")
else:
    for violation in result.violations:
        print(f"{violation.error_code}: {violation.message}")
```

## 5. Custom Naming Patterns

For organizations with custom naming conventions:

```yaml
governance:
  naming:
    enforcement: strict
    pattern: custom
    custom_patterns:
      - "^raw_.*$"      # Raw layer
      - "^clean_.*$"    # Clean layer
      - "^agg_.*$"      # Aggregated layer
      - "^rpt_.*$"      # Report layer
```

## 6. Policy Inheritance (3-Tier Mode)

Enterprise manifest defines baseline policies:

```yaml
# enterprise-manifest.yaml
scope: enterprise
governance:
  policy_enforcement_level: warn
  quality_gates:
    minimum_test_coverage: 60
```

Domain manifest can STRENGTHEN (never weaken):

```yaml
# domain-manifest.yaml
scope: domain
parent_manifest: oci://registry.example.com/enterprise:v1
governance:
  policy_enforcement_level: strict  # ✓ Strengthens warn → strict
  quality_gates:
    minimum_test_coverage: 80  # ✓ Strengthens 60 → 80
```

Attempting to weaken fails:

```yaml
# INVALID - would fail validation
governance:
  quality_gates:
    minimum_test_coverage: 40  # ✗ Cannot weaken 60 → 40
```

Error:
```
FLOE-E230 [inheritance] quality_gates.minimum_test_coverage
  Cannot weaken policy from 60 to 40
  Child manifests can only maintain or strengthen parent policies.
```

## 7. Troubleshooting

### "No governance config found"

Add `governance` section to manifest.yaml. Default enforcement is `warn`.

### "Custom patterns required"

When using `pattern: custom`, you MUST provide `custom_patterns` list.

### "Invalid regex pattern"

Check regex syntax. Common issues:
- Escaping: Use `\\` for literal backslash
- Anchors: Use `^` and `$` for full match

### Performance slow with many models

PolicyEnforcer processes models in parallel. For 500+ models:
- Ensure dbt manifest is cached
- Consider filtering models with dbt tags

## Next Steps

- Configure governance policies in your manifest.yaml
- Run `floe compile --dry-run` to preview violations
- Fix violations and run `floe compile` in strict mode
- Integrate into CI/CD pipeline for automated enforcement
