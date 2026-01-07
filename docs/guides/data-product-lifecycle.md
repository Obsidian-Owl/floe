# Data Product Lifecycle Guide

This guide describes the complete lifecycle of a data product in floe, from initialization to production operation.

## Overview

A data product moves through five phases:

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   INIT      │──►│  DEVELOP    │──►│  VALIDATE   │──►│  COMPILE    │──►│    RUN      │
│             │   │             │   │             │   │             │   │             │
│ floe init   │   │ Edit models │   │ floe validate│  │ floe compile│   │ floe run    │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

## Phase 1: Initialization

### Create Data Product

```bash
# Simple mode (no platform manifest)
floe init my-product

# Centralized mode (with platform manifest)
floe init my-product --platform oci://registry.example.com/platform:v1.0.0

# Data Mesh mode (with domain manifest)
floe init my-product --domain oci://registry.example.com/sales-domain:v1.0.0
```

### Generated Structure

```
my-product/
├── floe.yaml          # Data product definition
├── datacontract.yaml          # Optional: explicit data contract
├── models/
│   ├── bronze/
│   │   └── .gitkeep
│   ├── silver/
│   │   └── .gitkeep
│   └── gold/
│       └── .gitkeep
├── tests/
│   └── .gitkeep
└── README.md
```

### floe.yaml

```yaml
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: my-product
  version: "1.0.0"
  owner: data-team@example.com
  domain: sales
  repository: github.com/acme/my-product  # Required for identity

platform:
  ref: oci://registry.example.com/platform:v1.0.0

transforms:
  - type: dbt
    path: models/

schedule:
  cron: "0 6 * * *"
  timezone: UTC

# Data Mesh mode only:
output_ports:
  - name: customers
    table: gold.my_product.customers
    sla:
      freshness: "6h"
      availability: "99.9%"
```

## Phase 2: Development

### Write dbt Models

```sql
-- models/bronze/bronze_raw_customers.sql
{{ config(materialized='table') }}

SELECT
    id,
    email,
    created_at,
    _loaded_at
FROM {{ source('salesforce', 'accounts') }}
```

```sql
-- models/silver/silver_customers.sql
{{ config(
    materialized='incremental',
    unique_key='customer_id'
) }}

SELECT
    id AS customer_id,
    LOWER(TRIM(email)) AS email,
    created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {{ ref('bronze_raw_customers') }}
WHERE email IS NOT NULL
{% if is_incremental() %}
    AND _loaded_at > (SELECT MAX(_loaded_at) FROM {{ this }})
{% endif %}
```

### Add Tests

```yaml
# models/silver/schema.yml
version: 2

models:
  - name: silver_customers
    description: Cleaned and deduplicated customer data
    columns:
      - name: customer_id
        description: Unique customer identifier
        tests:
          - not_null
          - unique
      - name: email
        description: Customer email address
        tests:
          - not_null
        meta:
          classification: pii
```

### Define Data Contract (Optional)

```yaml
# datacontract.yaml
apiVersion: v3.0.2
kind: DataContract
name: my-product-customers
version: 1.0.0

owner: data-team@example.com

models:
  customers:
    elements:
      customer_id:
        type: string
        primaryKey: true
      email:
        type: string
        format: email
        classification: pii

slaProperties:
  freshness:
    value: "PT6H"
    element: updated_at
  availability:
    value: "99.9%"
```

## Phase 3: Validation

### Run Validation

```bash
$ floe validate

[1/4] Validating floe.yaml
      ✓ Schema valid
      ✓ Platform reference resolved

[2/4] Validating dbt project
      ✓ Models compile
      ✓ Sources defined
      ✓ Tests discovered: 5

[3/4] Validating data contracts
      ✓ datacontract.yaml valid (ODCS v3)
      ✓ Contract matches output ports

[4/4] Checking platform compliance
      ✓ Naming conventions: bronze_, silver_, gold_
      ✓ Quality gates: test coverage 80% (required: 80%)
      ✓ Classification: PII fields marked

Validation PASSED
```

### Validation Checks

| Check | Description |
|-------|-------------|
| Schema | floe.yaml matches Pydantic schema |
| Platform | Manifest reference resolves |
| dbt | Models compile without errors |
| Naming | Models follow naming conventions |
| Quality | Test coverage meets minimum |
| Classification | PII fields properly marked |
| Contract | datacontract.yaml valid ODCS format |

## Phase 4: Compilation

### Compile Artifacts

```bash
$ floe compile

[1/7] Loading platform artifacts
      ✓ Platform: acme-platform v1.2.3
      ✓ Compute: duckdb (enforced)

[2/7] Validating product identity
      Product ID: sales.my_product
      Repository: github.com/acme/my-product
      ✓ Namespace available, registering...
      ✓ Product registered in catalog

[3/7] Resolving inheritance
      ✓ Enterprise → Domain → Product

[4/7] Compiling dbt project
      ✓ manifest.json generated
      ✓ 12 models compiled

[5/7] Processing data contracts
      ✓ Auto-generated contract from ports
      ✓ Merged with explicit datacontract.yaml
      ✓ Contract version: 1.0.0
      ✓ Contract registered: sales.my_product/customers:1.0.0

[6/7] Generating orchestration
      ✓ Dagster definitions created

[7/7] Writing artifacts
      ✓ .floe/artifacts.json

Compilation COMPLETE
```

### Identity Registration

During compilation, the product namespace is registered in the Iceberg catalog:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PRODUCT IDENTITY REGISTRATION                           │
│                                                                              │
│  1. Generate Product ID                                                      │
│     └── product_id = f"{domain}.{name}" → "sales.my_product"                │
│                                                                              │
│  2. Check Catalog                                                            │
│     └── catalog.validate_product_identity(product_id, repository)            │
│                                                                              │
│  3. Registration Decision                                                    │
│     ├── AVAILABLE → Register namespace with floe.product.* properties       │
│     ├── VALID → Update product version metadata                              │
│     └── CONFLICT → FAIL: "Namespace owned by different repository"          │
│                                                                              │
│  4. Contract Registration                                                    │
│     └── catalog.register_contract(product_id, contract, version, hash)       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Identity Conflict Error:**

```bash
$ floe compile

[2/7] Validating product identity
      ✗ ERROR: Namespace 'sales.my_product' owned by different repository
              Owner: github.com/acme/other-repo
              Expected: github.com/acme/my-product

      Resolution: Choose a different product name or contact
                 the namespace owner: other-team@acme.com

Compilation FAILED
```

The `repository` field in `floe.yaml` is used to verify ownership:

```yaml
metadata:
  name: my-product
  domain: sales
  repository: github.com/acme/my-product  # Required for identity
```

### Compiled Artifacts

```json
// .floe/artifacts.json
{
  "version": "0.1.0",
  "metadata": {
    "compiled_at": "2026-01-03T10:00:00Z",
    "product_name": "my-product",
    "product_version": "1.0.0"
  },
  "mode": "centralized",
  "plugins": {
    "compute": { "type": "duckdb" },
    "orchestrator": { "type": "dagster" }
  },
  "transforms": [...],
  "data_contracts": [
    {
      "name": "my-product-customers",
      "version": "1.0.0",
      "models": [...],
      "sla": {
        "freshness_hours": 6.0,
        "availability_percent": 99.9
      }
    }
  ]
}
```

## Phase 5: Execution

### Run Pipeline

```bash
$ floe run

[1/4] Starting runtime
      ✓ ContractMonitor initialized
      ✓ Dagster code server started

[2/4] Executing transforms
      ▶ bronze_raw_customers (2m 15s)
        ├── Rows: 150,000
        └── OpenLineage: COMPLETE
      ▶ silver_customers (4m 30s)
        ├── Rows: 148,500
        └── OpenLineage: COMPLETE

[3/4] Running quality checks
      ✓ not_null: customer_id (pass)
      ✓ unique: customer_id (pass)
      ✓ not_null: email (pass)

[4/4] Validating contracts
      ✓ freshness: 0.1h (SLA: 6h)
      ✓ schema: no drift
      ✓ availability: 100%

Pipeline COMPLETE (6m 45s)
```

### Runtime Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              RUNTIME EXECUTION                                │
│                                                                              │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                  │
│  │  Dagster    │──────│  dbt run    │──────│  Quality    │                  │
│  │ Scheduler   │      │  (models)   │      │  Tests      │                  │
│  └─────────────┘      └──────┬──────┘      └──────┬──────┘                  │
│                              │                    │                          │
│                              ▼                    ▼                          │
│                      ┌───────────────────────────────────────┐              │
│                      │         OpenLineage Events            │              │
│                      │                                       │              │
│                      │  START ─► RUNNING ─► COMPLETE/FAIL    │              │
│                      └───────────────────────────────────────┘              │
│                                       │                                      │
│                                       ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     ContractMonitor (Continuous)                     │   │
│  │                                                                      │   │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │   │
│  │   │ Freshness   │   │ Schema      │   │ Quality     │              │   │
│  │   │ Check (15m) │   │ Drift (1h)  │   │ Check (6h)  │              │   │
│  │   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘              │   │
│  │          │                 │                 │                      │   │
│  │          └─────────────────┴─────────────────┘                      │   │
│  │                            │                                         │   │
│  │                            ▼                                         │   │
│  │          ┌─────────────────────────────────┐                        │   │
│  │          │  Violations → OpenLineage FAIL  │                        │   │
│  │          │            → Prometheus Metrics │                        │   │
│  │          └─────────────────────────────────┘                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Table Lifecycle

### When Tables Are Created

| Event | Table Action |
|-------|--------------|
| First `floe run` | Iceberg tables created in catalog |
| Model change | Table updated (incremental or replace) |
| Schema change | Table altered or recreated |
| Delete model | Table retained (manual cleanup) |

### Catalog Registration

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   floe      │──────│   Polaris   │──────│   Object    │
│   compile   │      │   Catalog   │      │   Storage   │
└─────────────┘      └─────────────┘      └─────────────┘
      │                    │                    │
      │ Register           │ Vend               │ Store
      │ namespace          │ credentials        │ data
      │                    │                    │
      ▼                    ▼                    ▼
 sales.my_product     Temp S3 creds     s3://bucket/sales/my_product/
```

### Schema Evolution

```yaml
# datacontract.yaml - version bump required for breaking changes
version: 1.0.0 → 2.0.0  # If removing/changing columns

# Non-breaking (MINOR bump)
- Add optional column
- Relax nullability

# Breaking (MAJOR bump)
- Remove column
- Change type
- Add required column
```

## Error Recovery

### Compile Failure

```bash
$ floe compile
ERROR: Model silver_payments violates naming convention

$ # Fix naming
$ mv models/silver/stg_payments.sql models/silver/silver_payments.sql

$ floe compile
✓ Compilation COMPLETE
```

### Run Failure

```bash
$ floe run
ERROR: Transform silver_customers failed

[View logs]
sqlalchemy.exc.OperationalError: connection refused

$ # Fix connection, retry
$ floe run --retry-failed
```

### Contract Violation

```bash
$ floe run
WARNING: Contract violation detected

  Contract: my-product-customers
  Type: freshness_violation
  Message: Data is 8 hours old, SLA is 6 hours

  Continuing (alert_only mode)
```

## Best Practices

1. **Version early**: Set `metadata.version` from the start
2. **Test everything**: Aim for 100% test coverage on gold models
3. **Document contracts**: Use descriptions in datacontract.yaml
4. **Start lenient**: Use `alert_only` before `block` enforcement
5. **Monitor from day one**: Set up dashboards early

## Related Documents

- [Data Contracts Architecture](../architecture/data-contracts.md)
- [Platform Enforcement](../architecture/platform-enforcement.md)
- [ADR-0030: Namespace-Based Identity](../architecture/adr/0030-namespace-identity.md)
- [Contract Monitoring Guide](./contract-monitoring.md)
- [Contract Versioning Guide](./contract-versioning.md)
- [Compiled Artifacts](../contracts/compiled-artifacts.md)
