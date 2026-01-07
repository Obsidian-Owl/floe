# Slowly Changing Dimensions (SCD) Patterns

This guide covers Slowly Changing Dimension (SCD) patterns for dimension tables in floe, with dbt implementation examples on Iceberg.

---

## Overview

Dimension tables contain descriptive attributes that change over time (e.g., customer address, product price, employee department). SCD patterns define how to handle these changes while preserving historical context where needed.

### SCD Type Summary

| Type | Name | History | Storage | Use Case |
|------|------|---------|---------|----------|
| **Type 0** | Fixed | No changes | Minimal | Immutable attributes |
| **Type 1** | Overwrite | No history | Minimal | Current value only |
| **Type 2** | Add Row | Full history | Growing | Audit, time-travel |
| **Type 3** | Add Column | Limited history | Moderate | Previous value only |

> **floe Support:** Type 1 and Type 2 are fully supported with dbt macros. Type 0 and Type 3 are supported manually.

---

## Type 1: Overwrite (No History)

Type 1 simply overwrites the existing value. No history is preserved.

### When to Use

- Current value is all that matters
- Historical changes are not analytically relevant
- Storage efficiency is priority
- GDPR "right to be forgotten" requirements

### Example

```
Before update:
┌────────────────┬──────────────┬─────────────┐
│ customer_id    │ name         │ email       │
├────────────────┼──────────────┼─────────────┤
│ C001           │ John Doe     │ john@old.com│
└────────────────┴──────────────┴─────────────┘

After update (customer changed email):
┌────────────────┬──────────────┬─────────────┐
│ customer_id    │ name         │ email       │
├────────────────┼──────────────┼─────────────┤
│ C001           │ John Doe     │ john@new.com│
└────────────────┴──────────────┴─────────────┘
```

### dbt Implementation

```sql
-- models/dimensions/dim_customer.sql
{{
  config(
    materialized='incremental',
    unique_key='customer_id',
    incremental_strategy='merge',
    merge_update_columns=['name', 'email', 'address', 'updated_at']
  )
}}

SELECT
    customer_id,
    name,
    email,
    address,
    CURRENT_TIMESTAMP AS updated_at
FROM {{ ref('stg_customers') }}
```

### Quality Gate

```yaml
# models/dimensions/dim_customer.yml
version: 2

models:
  - name: dim_customer
    meta:
      floe:
        layer: dimensions
        scd_type: 1
    columns:
      - name: customer_id
        tests:
          - not_null
          - unique
```

---

## Type 2: Add Row with Effective Dating (Full History)

Type 2 creates a new row for each change, with effective dates tracking when each version was valid.

### When to Use

- Full audit trail required
- Time-travel analysis ("what was the value on date X?")
- Regulatory compliance (finance, healthcare)
- Attribution analysis (which version drove the outcome?)

### Schema

```
┌────────────┬────────────┬─────────────┬──────────────┬──────────────┬───────────┐
│ surrogate  │ customer   │ email       │ effective    │ effective    │ is        │
│ _key       │ _id        │             │ _from        │ _to          │ _current  │
├────────────┼────────────┼─────────────┼──────────────┼──────────────┼───────────┤
│ 1          │ C001       │ john@old.com│ 2023-01-01   │ 2024-06-15   │ false     │
│ 2          │ C001       │ john@new.com│ 2024-06-15   │ 9999-12-31   │ true      │
└────────────┴────────────┴─────────────┴──────────────┴──────────────┴───────────┘
```

### Key Columns

| Column | Description |
|--------|-------------|
| `surrogate_key` | Unique identifier for each version (fact tables reference this) |
| `effective_from` | Date this version became active |
| `effective_to` | Date this version expired (9999-12-31 for current) |
| `is_current` | Boolean flag for current record (query optimization) |

### dbt Implementation with dbt Snapshots

dbt snapshots are the recommended approach for Type 2 dimensions:

```sql
-- snapshots/snap_customer.sql
{% snapshot snap_customer %}

{{
    config(
      target_schema='snapshots',
      unique_key='customer_id',
      strategy='check',
      check_cols=['email', 'address', 'phone'],
      invalidate_hard_deletes=True
    )
}}

SELECT
    customer_id,
    name,
    email,
    address,
    phone,
    CURRENT_TIMESTAMP AS loaded_at
FROM {{ source('raw', 'customers') }}

{% endsnapshot %}
```

This creates a table with dbt's built-in SCD2 columns:
- `dbt_scd_id` - surrogate key
- `dbt_valid_from` - effective from
- `dbt_valid_to` - effective to (null for current)
- `dbt_updated_at` - when the snapshot ran

### Query Patterns

**Get Current Value:**

```sql
SELECT *
FROM {{ ref('snap_customer') }}
WHERE dbt_valid_to IS NULL
```

**Point-in-Time Query:**

```sql
SELECT *
FROM {{ ref('snap_customer') }}
WHERE '2024-03-15' >= dbt_valid_from
  AND ('2024-03-15' < dbt_valid_to OR dbt_valid_to IS NULL)
```

**Iceberg Time Travel (Alternative):**

With Iceberg tables, you can also use native time travel:

```sql
-- Query table as of specific timestamp
SELECT * FROM dim_customer
  FOR SYSTEM_TIME AS OF TIMESTAMP '2024-03-15 00:00:00'
```

### dbt Incremental Alternative (Manual SCD2)

For more control, implement SCD2 manually:

```sql
-- models/dimensions/dim_customer_scd2.sql
{{
  config(
    materialized='incremental',
    unique_key='surrogate_key',
    incremental_strategy='merge'
  )
}}

WITH source AS (
    SELECT
        customer_id,
        name,
        email,
        address,
        CURRENT_TIMESTAMP AS loaded_at
    FROM {{ ref('stg_customers') }}
),

{% if is_incremental() %}

-- Identify changed records
changed AS (
    SELECT
        s.customer_id,
        s.name,
        s.email,
        s.address,
        s.loaded_at
    FROM source s
    LEFT JOIN {{ this }} t
        ON s.customer_id = t.customer_id
        AND t.is_current = TRUE
    WHERE t.customer_id IS NULL  -- New records
       OR s.email != t.email     -- Changed records
       OR s.address != t.address
),

-- Expire old current records
expired AS (
    SELECT
        t.surrogate_key,
        t.customer_id,
        t.name,
        t.email,
        t.address,
        t.effective_from,
        c.loaded_at AS effective_to,
        FALSE AS is_current
    FROM {{ this }} t
    INNER JOIN changed c ON t.customer_id = c.customer_id
    WHERE t.is_current = TRUE
)

SELECT * FROM expired
UNION ALL
SELECT
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'loaded_at']) }} AS surrogate_key,
    customer_id,
    name,
    email,
    address,
    loaded_at AS effective_from,
    TIMESTAMP '9999-12-31' AS effective_to,
    TRUE AS is_current
FROM changed

{% else %}

-- Initial load
SELECT
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'loaded_at']) }} AS surrogate_key,
    customer_id,
    name,
    email,
    address,
    loaded_at AS effective_from,
    TIMESTAMP '9999-12-31' AS effective_to,
    TRUE AS is_current
FROM source

{% endif %}
```

### Quality Gates for SCD2

```yaml
# models/dimensions/dim_customer_scd2.yml
version: 2

models:
  - name: dim_customer_scd2
    meta:
      floe:
        layer: dimensions
        scd_type: 2
    tests:
      # Ensure only one current record per business key
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - customer_id
            - is_current
          where: "is_current = TRUE"
    columns:
      - name: surrogate_key
        tests:
          - not_null
          - unique
      - name: customer_id
        tests:
          - not_null
      - name: effective_from
        tests:
          - not_null
      - name: is_current
        tests:
          - not_null
```

---

## Type 3: Add Column (Limited History)

Type 3 adds columns to store previous values. Only one historical value is preserved.

### When to Use

- Only need to compare current vs. previous
- Schema changes are acceptable
- Limited historical depth required

### Example

```
┌────────────────┬──────────────┬────────────────┬─────────────────┐
│ customer_id    │ email        │ previous_email │ email_changed_at│
├────────────────┼──────────────┼────────────────┼─────────────────┤
│ C001           │ john@new.com │ john@old.com   │ 2024-06-15      │
└────────────────┴──────────────┴────────────────┴─────────────────┘
```

### dbt Implementation

```sql
-- models/dimensions/dim_customer_scd3.sql
{{
  config(
    materialized='incremental',
    unique_key='customer_id',
    incremental_strategy='merge',
    merge_update_columns=['email', 'previous_email', 'email_changed_at', 'updated_at']
  )
}}

WITH source AS (
    SELECT
        customer_id,
        name,
        email
    FROM {{ ref('stg_customers') }}
)

{% if is_incremental() %}

SELECT
    s.customer_id,
    s.name,
    s.email,
    CASE
        WHEN s.email != t.email THEN t.email
        ELSE t.previous_email
    END AS previous_email,
    CASE
        WHEN s.email != t.email THEN CURRENT_TIMESTAMP
        ELSE t.email_changed_at
    END AS email_changed_at,
    CURRENT_TIMESTAMP AS updated_at
FROM source s
LEFT JOIN {{ this }} t ON s.customer_id = t.customer_id

{% else %}

SELECT
    customer_id,
    name,
    email,
    NULL AS previous_email,
    NULL AS email_changed_at,
    CURRENT_TIMESTAMP AS updated_at
FROM source

{% endif %}
```

---

## Integration with Medallion Architecture

SCD patterns integrate with medallion layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BRONZE (Raw)                                                                │
│  • No SCD handling - raw extract                                            │
│  • bronze_customers: direct from source                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SILVER (Cleaned, SCD Applied)                                               │
│  • SCD logic applied here                                                   │
│  • silver_customers: SCD Type 2 with effective dates                        │
│  • Deduplication, validation                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  GOLD (Business-Ready)                                                       │
│  • Current view for easy consumption                                        │
│  • gold_customers: filtered to is_current = TRUE                            │
│  • Or: current + historical for time-travel                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
models/
├── staging/
│   └── stg_customers.sql           # Bronze → Staging (clean)
├── dimensions/
│   ├── dim_customer.sql            # SCD Type 1 or 2
│   └── dim_customer.yml            # Tests + SCD metadata
└── marts/
    └── gold_customer_current.sql   # Current view for BI
```

---

## Integration with Kimball Pattern

For Kimball dimensional models, dimensions are the natural place for SCD:

```yaml
# manifest.yaml
data_architecture:
  pattern: kimball

  layers:
    dimensions:
      prefix: "dim_"
      quality_gates:
        required_tests: [not_null_pk, unique_pk, scd_validation]
        scd_types_allowed: [1, 2]  # No Type 3 for consistency
```

### Fact Table References

Fact tables should reference the dimension's surrogate key (for SCD2):

```sql
-- models/facts/fact_orders.sql
SELECT
    o.order_id,
    o.order_date,
    o.amount,
    dc.surrogate_key AS customer_key,  -- References SCD2 dimension
    dp.surrogate_key AS product_key
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ ref('dim_customer_scd2') }} dc
    ON o.customer_id = dc.customer_id
    AND o.order_date >= dc.effective_from
    AND o.order_date < dc.effective_to
LEFT JOIN {{ ref('dim_product') }} dp
    ON o.product_id = dp.product_id
```

---

## Iceberg-Specific Considerations

### Merge-on-Read vs Copy-on-Write

For SCD Type 1 updates, configure Iceberg table properties:

```sql
-- For frequent small updates (Type 1)
ALTER TABLE dim_customer SET TBLPROPERTIES (
    'write.merge.mode' = 'merge-on-read',
    'write.update.mode' = 'merge-on-read'
);

-- For batch updates (Type 2 inserts)
ALTER TABLE dim_customer_scd2 SET TBLPROPERTIES (
    'write.merge.mode' = 'copy-on-write'
);
```

### Partition Strategy

For large SCD2 tables, partition by effective date:

```sql
{{
  config(
    materialized='incremental',
    partition_by=['year(effective_from)'],
    ...
  )
}}
```

---

## Quality Gates for SCD

Add these tests to your dimension models:

```yaml
# macros/tests/test_scd_valid_dates.sql
{% test scd_valid_dates(model, from_column, to_column) %}

SELECT *
FROM {{ model }}
WHERE {{ from_column }} > {{ to_column }}
   OR {{ from_column }} IS NULL

{% endtest %}

# macros/tests/test_scd_no_gaps.sql
{% test scd_no_gaps(model, key_column, from_column, to_column) %}

WITH ordered AS (
    SELECT
        {{ key_column }},
        {{ from_column }},
        {{ to_column }},
        LEAD({{ from_column }}) OVER (
            PARTITION BY {{ key_column }}
            ORDER BY {{ from_column }}
        ) AS next_from
    FROM {{ model }}
)
SELECT *
FROM ordered
WHERE {{ to_column }} != next_from
  AND next_from IS NOT NULL

{% endtest %}
```

Usage:

```yaml
models:
  - name: dim_customer_scd2
    tests:
      - scd_valid_dates:
          from_column: effective_from
          to_column: effective_to
      - scd_no_gaps:
          key_column: customer_id
          from_column: effective_from
          to_column: effective_to
```

---

## Choosing the Right SCD Type

| Factor | Type 1 | Type 2 |
|--------|--------|--------|
| **History Needed?** | No | Yes |
| **Audit Requirements?** | None | Regulatory |
| **Query Complexity** | Simple | Moderate |
| **Storage Growth** | Stable | Growing |
| **GDPR Deletion** | Simple | Complex |
| **BI Tool Support** | All | Most |

### Decision Tree

```
Do you need historical values?
│
├── No → Type 1 (Overwrite)
│
└── Yes → Do you need full history or just previous value?
          │
          ├── Full history → Type 2 (Add Row)
          │
          └── Just previous → Type 3 (Add Column)
```

---

## References

- [Kimball Group: Slowly Changing Dimensions](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-1/)
- [dbt Snapshots Documentation](https://docs.getdbt.com/docs/build/snapshots)
- [Apache Iceberg Merge Operations](https://iceberg.apache.org/docs/latest/spark-writes/#merge-into)
- [ADR-0021: Data Architecture Patterns](../architecture/adr/0021-data-architecture-patterns.md)
