# Contract Versioning Guide

This guide explains how to version data contracts and manage their lifecycle in floe.

## Overview

Data contracts version independently from data products using semantic versioning. This allows contracts to evolve while maintaining backward compatibility for consumers.

## Semantic Versioning

Contracts follow [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH

Example: 2.1.0
         │ │ │
         │ │ └── Patch: documentation, metadata changes
         │ └──── Minor: backward-compatible additions
         └────── Major: breaking changes
```

## Version Bump Rules

### MAJOR Version (Breaking Changes)

Increment MAJOR when changes break backward compatibility:

| Change | Example | Consumer Impact |
|--------|---------|-----------------|
| Remove column | Delete `email` field | Queries fail |
| Change type | `id: int` → `id: string` | Type errors |
| Make optional required | `phone` now required | Nulls rejected |
| Add required column | New `ssn` required | Insert fails |
| Relax SLA | Freshness 4h → 8h | SLA degradation |

```yaml
# Before: version: 1.2.0
models:
  customers:
    elements:
      email:
        type: string
        required: true

# After: version: 2.0.0 (MAJOR bump - removed required field)
models:
  customers:
    elements:
      # email removed!
```

### MINOR Version (Additions)

Increment MINOR for backward-compatible additions:

| Change | Example | Consumer Impact |
|--------|---------|-----------------|
| Add optional column | New `nickname` field | None (optional) |
| Make required optional | `phone` now optional | Less strict |
| Stricter SLA | Freshness 6h → 4h | Better service |

```yaml
# Before: version: 1.2.0
models:
  customers:
    elements:
      name:
        type: string

# After: version: 1.3.0 (MINOR bump - new optional field)
models:
  customers:
    elements:
      name:
        type: string
      nickname:
        type: string
        required: false   # Optional, so backward compatible
```

### PATCH Version (Metadata)

Increment PATCH for changes that don't affect data:

| Change | Example |
|--------|---------|
| Update description | Documentation fix |
| Add/change tags | New categorization |
| Change classification | Mark as PII |
| Update owner | Team transfer |

```yaml
# Before: version: 1.2.0
# After: version: 1.2.1 (PATCH bump - documentation only)
models:
  customers:
    elements:
      email:
        type: string
        description: "Primary email"  # Updated description
```

## Version Validation

### Compile-Time Check

The compiler validates version bumps automatically:

```bash
$ floe compile

ERROR: Contract version bump invalid

  Contract: my-customers
  Previous: 1.2.0
  Proposed: 1.2.1

  Breaking changes detected:
    - Removed column: email

  Required: MAJOR version bump (2.0.0)

  See: https://docs.floe.dev/contract-versioning
```

### CLI Validation

```bash
# Check if version bump is valid
floe contract validate-version \
  --old datacontract.yaml.bak \
  --new datacontract.yaml

# Output:
# Breaking changes detected:
#   - Removed column: email
#
# Suggested version: 2.0.0 (current: 1.2.1)
```

## Deprecation Workflow

### Deprecation States

```
ACTIVE ────► DEPRECATED ────► SUNSET ────► RETIRED
           (30 days min)    (7 days)
```

| State | Behavior |
|-------|----------|
| `active` | Normal operation |
| `deprecated` | Warnings emitted, new consumers warned |
| `sunset` | Errors for new consumers, existing warned |
| `retired` | Contract removed |

### How to Deprecate

1. **Announce deprecation:**

```yaml
# datacontract.yaml
status: deprecated

deprecation:
  announced: "2026-01-03"
  sunset_date: "2026-02-03"
  replacement: customers-v2
  migration_guide: https://wiki.example.com/migrate-customers-v2
  reason: "Replacing with unified customer model"
```

2. **Notify consumers:**

The ContractMonitor emits deprecation warnings:

```json
{
  "violationType": "deprecation_warning",
  "message": "Contract my-customers is deprecated. Sunset: 2026-02-03. Migrate to: customers-v2"
}
```

3. **At sunset date:**

Change status to `sunset`:

```yaml
status: sunset
```

New consumers get errors. Existing consumers get urgent warnings.

4. **After sunset period:**

Remove the contract (or mark as `retired`).

## Major Version Strategy

### Table Namespacing

For major version changes, use new table namespaces:

```
# Version 1.x tables
gold.customers_v1

# Version 2.x tables (breaking change)
gold.customers_v2
```

This allows:
- Old consumers to continue reading v1
- New consumers to adopt v2
- Parallel operation during migration

### Migration Path

```yaml
# v1 contract - deprecated
apiVersion: v3.0.2
kind: DataContract
name: customers-v1
version: 1.5.0
status: deprecated
deprecation:
  replacement: customers-v2
  migration_guide: https://wiki.example.com/migrate-v2

# v2 contract - active
apiVersion: v3.0.2
kind: DataContract
name: customers-v2
version: 2.0.0
status: active
```

## Inheritance and Versioning

### Three-Tier Model

```
Enterprise Contract (v1.0.0)
        │
        ├── Minimum freshness: 24h
        │
        ▼
Domain Contract (v1.0.0)
        │
        ├── Domain freshness: 6h (stricter)
        │
        ▼
Product Contract (v2.1.0)  ← Independent version
        │
        └── Product freshness: 4h (even stricter)
```

**Key rules:**
- Child contracts have independent versions
- Child contracts can only STRENGTHEN parent requirements
- Parent version changes don't automatically bump child versions

### Inheritance Validation

```bash
$ floe compile

ERROR: Contract inheritance violation

  Parent: enterprise-base (v1.0.0)
    - freshness: 24h (minimum)

  Child: my-customers (v1.0.0)
    - freshness: 48h (WEAKER - violates inheritance)

  Child contracts cannot weaken parent requirements.
```

## Best Practices

### 1. Plan Breaking Changes

Before making breaking changes:
1. Document the change rationale
2. Identify all consumers
3. Create migration guide
4. Set deprecation timeline (minimum 30 days)

### 2. Use Feature Flags for Schema Changes

```yaml
# Add new optional field first
elements:
  new_field:
    type: string
    required: false  # Optional initially

# Later, make required in new major version
elements:
  new_field:
    type: string
    required: true
```

### 3. Communicate Changes

```markdown
## Contract Change Notification

**Contract:** customers-v1
**Change:** Deprecation announced
**Sunset Date:** 2026-02-03
**Replacement:** customers-v2

### Migration Steps
1. Update queries to use new schema
2. Handle new required fields
3. Update to v2 contract reference

### Breaking Changes in v2
- `email` renamed to `primary_email`
- `phone` split into `phone_country` and `phone_number`
- `updated_at` now required

### Timeline
- Jan 3: Deprecation announced
- Jan 17: Migration guide published
- Feb 3: Sunset (v1 warnings become errors)
- Feb 10: v1 retired
```

### 4. Keep Changelog

```yaml
# In datacontract.yaml or separate CHANGELOG.md

# Changelog
#
# ## 2.0.0 - 2026-02-01
# ### Breaking
# - Removed `legacy_id` column
# - Changed `id` type from int to string
#
# ## 1.3.0 - 2026-01-15
# ### Added
# - New optional `nickname` column
#
# ## 1.2.1 - 2026-01-10
# ### Fixed
# - Updated description for `email` field
```

### 5. Test Before Release

```bash
# Validate contract against live data
floe contract test datacontract.yaml --connection staging

# Check version bump validity
floe contract validate-version --old v1 --new v2

# Dry-run compile
floe compile --dry-run
```

## Common Scenarios

### Adding a Required Field

**Wrong approach:**
```yaml
# This breaks consumers!
version: 1.3.0  # Minor bump is wrong

elements:
  ssn:
    type: string
    required: true  # New required field
```

**Correct approach:**
```yaml
# Step 1: Add as optional (minor bump)
version: 1.3.0
elements:
  ssn:
    type: string
    required: false

# Step 2: After consumers update, make required (major bump)
version: 2.0.0
elements:
  ssn:
    type: string
    required: true
```

### Renaming a Column

```yaml
# Step 1: Add new column, deprecate old (minor)
version: 1.3.0
elements:
  email:  # Old
    type: string
    description: "DEPRECATED: Use primary_email"
  primary_email:  # New
    type: string

# Step 2: Remove old column (major)
version: 2.0.0
elements:
  primary_email:
    type: string
```

## Related Documents

- [Data Contracts Architecture](../architecture/data-contracts.md)
- [ADR-0029: Contract Lifecycle Management](../architecture/adr/0029-contract-lifecycle-management.md)
- [datacontract.yaml Reference](../contracts/datacontract-yaml-reference.md)
- [Contract Monitoring Guide](./contract-monitoring.md)
