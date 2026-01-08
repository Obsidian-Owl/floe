# floe.yaml Schema Reference

This document provides the complete schema reference for `floe.yaml` configuration files.

---

## Overview

`floe.yaml` is the configuration file for floe data products. It defines:

- Platform reference (enforced configuration)
- Transforms (dbt models)
- Ingestion sources
- Schedules
- Environment overrides

### Minimal Example

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-analytics
  version: "1.0.0"
  domain: sales

platform:
  ref: oci://registry.example.com/platform:v1.0.0

transforms:
  - type: dbt
    path: models/
```

---

## Schema Structure

```
FloeSpec
├── apiVersion: string (required)
├── kind: string (required)
├── metadata: MetadataSpec (required)
├── platform: PlatformRef (required)
├── transforms: TransformSpec[] (required)
│   ├── type: string (required)
│   ├── path: string (required)
│   ├── compute: string (optional) ← Select from platform's approved list
│   └── profiles_dir: string (optional)
├── ingestion: IngestionSpec[] (optional)
├── schedule: ScheduleSpec (optional)
├── environments: EnvironmentOverride[] (optional)
└── quality: QualitySpec (optional)
```

---

## Root Fields

### apiVersion

**Type:** `string`
**Required:** Yes
**Pattern:** `floe.dev/v[0-9]+`

The API version for the floe.yaml schema.

```yaml
apiVersion: floe.dev/v1
```

### kind

**Type:** `string`
**Required:** Yes
**Enum:** `DataProduct`

The resource kind. Currently only `DataProduct` is supported.

```yaml
kind: DataProduct
```

---

## MetadataSpec

### metadata.name

**Type:** `string`
**Required:** Yes
**Pattern:** `^[a-z][a-z0-9-]*$`
**Max Length:** 63

The unique name of the data product within its domain.

```yaml
metadata:
  name: customer-360
```

### metadata.version

**Type:** `string`
**Required:** Yes
**Pattern:** `^[0-9]+\.[0-9]+\.[0-9]+$`

Semantic version of the data product.

```yaml
metadata:
  version: "1.2.3"
```

### metadata.domain

**Type:** `string`
**Required:** Yes
**Pattern:** `^[a-z][a-z0-9-]*$`

The domain that owns this data product. Used for namespace prefixing.

```yaml
metadata:
  domain: sales
```

### metadata.description

**Type:** `string`
**Required:** No
**Max Length:** 1000

Human-readable description of the data product.

```yaml
metadata:
  description: "Unified customer view across all touchpoints"
```

### metadata.owner

**Type:** `string`
**Required:** No
**Format:** Email

Team or person responsible for this data product.

```yaml
metadata:
  owner: sales-analytics@acme.com
```

### metadata.labels

**Type:** `map[string]string`
**Required:** No

Key-value labels for organization and filtering.

```yaml
metadata:
  labels:
    team: analytics
    cost-center: sales
    environment: production
```

---

## PlatformRef

### platform.ref

**Type:** `string`
**Required:** Yes
**Format:** OCI URI

Reference to the platform manifest OCI artifact.

```yaml
platform:
  ref: oci://ghcr.io/acme/platform:v1.0.0
```

### platform.cache

**Type:** `boolean`
**Required:** No
**Default:** `true`

Whether to cache the platform artifact locally.

```yaml
platform:
  ref: oci://ghcr.io/acme/platform:v1.0.0
  cache: true
```

---

## TransformSpec

### transforms[].type

**Type:** `string`
**Required:** Yes
**Enum:** `dbt`

The transform type. Currently only `dbt` is supported.

```yaml
transforms:
  - type: dbt
```

### transforms[].path

**Type:** `string`
**Required:** Yes

Path to the transform source files, relative to `floe.yaml`.

```yaml
transforms:
  - type: dbt
    path: models/
```

### transforms[].profiles_dir

**Type:** `string`
**Required:** No
**Default:** `.floe/profiles`

Path to generated dbt profiles directory.

```yaml
transforms:
  - type: dbt
    path: models/
    profiles_dir: .dbt/
```

### transforms[].compute

**Type:** `string`
**Required:** No
**Default:** Platform's default compute

Select the compute engine for this transform from the platform's approved list. This enables multi-compute pipelines where different steps can use different compute engines.

**Validation:** Must be a compute name from `manifest.yaml` `plugins.compute.approved[]`.

```yaml
# manifest.yaml (Platform Team)
plugins:
  compute:
    approved:
      - name: duckdb
        config: { threads: 8 }
      - name: spark
        config: { cluster: "spark-thrift.svc" }
    default: duckdb

# floe.yaml (Data Engineers)
transforms:
  # Heavy processing on Spark cluster
  - type: dbt
    path: models/staging/
    compute: spark  # Select from approved list

  # Analytical metrics on DuckDB
  - type: dbt
    path: models/marts/
    compute: duckdb

  # Simple transforms use default
  - type: dbt
    path: models/seeds/
    # compute: (uses platform default → duckdb)
```

**Environment Parity:** Each transform uses the SAME compute across all environments (dev/staging/prod). This is NOT for per-environment compute selection (which would cause environment drift).

```
Step 1: dev=Spark, staging=Spark, prod=Spark     ✓ No drift
Step 2: dev=DuckDB, staging=DuckDB, prod=DuckDB  ✓ No drift
```

---

## IngestionSpec

### ingestion[].name

**Type:** `string`
**Required:** Yes
**Pattern:** `^[a-z][a-z0-9_]*$`

Unique name for the ingestion pipeline.

```yaml
ingestion:
  - name: github_events
```

### ingestion[].type

**Type:** `string`
**Required:** Yes
**Enum:** `dlt`, `airbyte`

The ingestion plugin type.

```yaml
ingestion:
  - name: github_events
    type: dlt
```

### ingestion[].destination

**Type:** `string`
**Required:** Yes
**Format:** `{namespace}.{table}`

Target Iceberg table for ingested data.

```yaml
ingestion:
  - name: github_events
    type: dlt
    destination: bronze.github_events
```

### ingestion[].dlt

**Type:** `DltConfig`
**Required:** When `type: dlt`

Configuration specific to dlt ingestion.

```yaml
ingestion:
  - name: github_events
    type: dlt
    destination: bronze.github_events
    dlt:
      source: dlt.sources.github.github_reactions
      resource: issues
      write_disposition: merge
      incremental:
        cursor_column: updated_at
```

#### dlt.source

**Type:** `string`
**Required:** Yes

Python import path to the dlt source.

#### dlt.resource

**Type:** `string`
**Required:** No

Specific resource within the source.

#### dlt.write_disposition

**Type:** `string`
**Enum:** `append`, `replace`, `merge`
**Default:** `append`

How to write data to the destination.

#### dlt.incremental

**Type:** `IncrementalConfig`
**Required:** No

Configuration for incremental loading.

### ingestion[].airbyte

**Type:** `AirbyteConfig`
**Required:** When `type: airbyte`

Configuration for external Airbyte connections.

```yaml
ingestion:
  - name: salesforce_sync
    type: airbyte
    destination: bronze.salesforce
    airbyte:
      connection_id: "abc123-def456"
```

### ingestion[].secret_refs

**Type:** `map[string]string`
**Required:** No

References to Kubernetes secrets for credentials.

```yaml
ingestion:
  - name: github_events
    type: dlt
    secret_refs:
      github_token: github-api-token
```

---

## ScheduleSpec

### schedule.cron

**Type:** `string`
**Required:** No
**Format:** Cron expression

Cron schedule for running the pipeline.

```yaml
schedule:
  cron: "0 */6 * * *"  # Every 6 hours
```

### schedule.timezone

**Type:** `string`
**Required:** No
**Default:** `UTC`

Timezone for the schedule.

```yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/New_York
```

### schedule.enabled

**Type:** `boolean`
**Required:** No
**Default:** `true`

Whether the schedule is active.

```yaml
schedule:
  cron: "0 6 * * *"
  enabled: false  # Disable scheduling
```

---

## EnvironmentOverride

### environments[].name

**Type:** `string`
**Required:** Yes
**Enum:** `development`, `staging`, `production`

Environment name to override.

```yaml
environments:
  - name: development
```

### environments[].transforms

**Type:** `TransformOverride`
**Required:** No

Transform-specific overrides for this environment. **Note:** Per-environment compute selection is NOT allowed (would cause environment drift). Use `transforms[].compute` instead for per-transform compute selection.

```yaml
environments:
  - name: development
    transforms:
      # Per-environment overrides (e.g., reduced parallelism)
      threads: 4

# ❌ FORBIDDEN: Per-environment compute (causes drift)
# environments:
#   - name: development
#     transforms:
#       compute: duckdb  # Different compute per env = drift
#   - name: production
#     transforms:
#       compute: snowflake  # "Works in dev, fails in prod"
```

### environments[].schedule

**Type:** `ScheduleOverride`
**Required:** No

Schedule overrides for this environment.

```yaml
environments:
  - name: development
    schedule:
      enabled: false  # No scheduling in dev
```

---

## QualitySpec

### quality.minimum_coverage

**Type:** `integer`
**Required:** No
**Default:** From platform manifest
**Range:** 0-100

Minimum test coverage percentage.

```yaml
quality:
  minimum_coverage: 80
```

### quality.required_tests

**Type:** `string[]`
**Required:** No
**Default:** From platform manifest

Tests required for all models.

```yaml
quality:
  required_tests:
    - not_null
    - unique
```

---

## Complete Example

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-360
  version: "3.2.1"
  domain: sales
  description: "Unified customer view across all touchpoints"
  owner: sales-analytics@acme.com
  labels:
    team: analytics
    cost-center: sales

platform:
  ref: oci://ghcr.io/acme/platform:v1.0.0

transforms:
  # Heavy processing on Spark (large datasets)
  - type: dbt
    path: models/staging/
    compute: spark  # Select from platform's approved list

  # Analytical metrics on DuckDB (smaller result set)
  - type: dbt
    path: models/marts/
    compute: duckdb

  # Seeds use platform default (no compute specified)
  - type: dbt
    path: models/seeds/

ingestion:
  - name: salesforce_accounts
    type: dlt
    destination: bronze.salesforce_accounts
    dlt:
      source: dlt.sources.salesforce.salesforce_source
      resource: accounts
      write_disposition: merge
      incremental:
        cursor_column: last_modified_date
    secret_refs:
      salesforce_token: salesforce-api-token

  - name: zendesk_tickets
    type: dlt
    destination: bronze.zendesk_tickets
    dlt:
      source: dlt.sources.zendesk.zendesk_support
      resource: tickets
      write_disposition: append

schedule:
  cron: "0 */6 * * *"
  timezone: UTC

environments:
  - name: development
    schedule:
      enabled: false

  - name: production
    quality:
      minimum_coverage: 100

quality:
  minimum_coverage: 80
  required_tests:
    - not_null
    - unique
```

---

## JSON Schema

The complete JSON Schema for `floe.yaml` is generated from Pydantic models:

```bash
# Export JSON Schema
floe schema export --format json > floe-yaml-schema.json

# Validate a floe.yaml file
floe validate floe.yaml
```

### JSON Schema Location

```
packages/floe-core/src/floe_core/schemas/
├── floe_spec.py          # Pydantic models
├── floe_yaml_schema.json # Generated JSON Schema
└── __init__.py
```

### IDE Integration

Configure your IDE to use the JSON Schema for validation:

**VS Code (settings.json):**
```json
{
  "yaml.schemas": {
    "https://floe.dev/schemas/floe-yaml-v1.json": ["floe.yaml", "floe.yml"]
  }
}
```

**JetBrains IDEs:**
```
Settings > Languages & Frameworks > Schemas and DTDs > JSON Schema Mappings
Add: https://floe.dev/schemas/floe-yaml-v1.json → floe.yaml
```

---

## Validation Rules

Beyond schema validation, the following rules are enforced at compile time:

| Rule | Description | Error |
|------|-------------|-------|
| `domain_namespace_match` | Domain must match catalog namespace | `DomainMismatchError` |
| `version_semver` | Version must be valid semver | `InvalidVersionError` |
| `transform_path_exists` | Transform path must exist | `PathNotFoundError` |
| `platform_ref_resolvable` | Platform OCI ref must be pullable | `PlatformNotFoundError` |
| `secret_refs_exist` | Secret refs must exist in cluster | `SecretNotFoundError` |
| `naming_convention` | Model names must match platform pattern | `NamingViolationError` |
| `compute_in_approved_list` | Transform compute must be in platform's approved list | `InvalidComputeError` |

---

## Defaults

| Field | Default Value | Source |
|-------|---------------|--------|
| `platform.cache` | `true` | Built-in |
| `transforms[].profiles_dir` | `.floe/profiles` | Built-in |
| `transforms[].compute` | `plugins.compute.default` | Platform manifest |
| `schedule.timezone` | `UTC` | Built-in |
| `schedule.enabled` | `true` | Built-in |
| `quality.*` | Platform manifest | Inherited |

---

## References

- [Platform Manifest Schema](../contracts/index.md)
- [ADR-0016: Platform Enforcement Architecture](../architecture/adr/0016-platform-enforcement-architecture.md)
- [ADR-0018: Opinionation Boundaries](../architecture/adr/0018-opinionation-boundaries.md)
- [Pydantic Documentation](https://docs.pydantic.dev/)
