# Catalog-as-Control-Plane Architecture

## Why Catalog Control is CRITICAL

In a multi-engine data platform, the catalog acts as the **single source of truth** for:
- Table metadata (schema, partitions, properties)
- Transaction coordination (ACID across engines)
- Access control (row/column policies)
- Governance (classification, lineage)

**Without catalog control:**
- Engines write directly to storage → metadata conflicts
- Schema changes uncoordinated → query failures
- No transaction isolation → corrupt data
- No governance → compliance violations

## Architecture Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DATA OPERATIONS                                │
│                                                                       │
│  Dagster Asset    dbt Model       PyIceberg       Direct SQL          │
│  Materialization  Execution       Operation       (DuckDB/Spark)      │
│       │               │               │               │               │
└───────┼───────────────┼───────────────┼───────────────┼───────────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   ICEBERG REST CATALOG API                            │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    CATALOG OPERATIONS                            │ │
│  │                                                                  │ │
│  │  • createTable()     - Register new table                        │ │
│  │  • loadTable()       - Get table metadata + storage location     │ │
│  │  • commitTransaction() - ACID commit with conflict detection     │ │
│  │  • updateSchema()    - Coordinate schema evolution               │ │
│  │  • setAccessPolicy() - Apply governance rules                    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  Implementations:                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │   Polaris    │  │  AWS Glue    │  │Unity Catalog │                │
│  │(Open Source) │  │  (AWS)       │  │ (Databricks) │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        OBJECT STORAGE                                 │
│                                                                       │
│  S3 / Azure Blob / GCS                                                │
│  ├── metadata/                                                        │
│  │   └── v1.metadata.json  ← Catalog points here                     │
│  └── data/                                                            │
│      └── *.parquet         ← Engines write via catalog commit        │
└──────────────────────────────────────────────────────────────────────┘
```

## Catalog Types and Configuration

### Polaris (Recommended - Open Source)

```python
# floe-polaris client configuration
from floe_polaris import create_catalog, PolarisCatalogConfig

config = PolarisCatalogConfig(
    uri="http://polaris:8181/api/catalog",
    warehouse="demo_catalog",
    client_id="service_account",
    client_secret=SecretStr("secret"),
    scope="PRINCIPAL_ROLE:service_admin",
    token_refresh_enabled=True,
)
catalog = create_catalog(config)
```

### AWS Glue Catalog

```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog(
    "glue",
    **{
        "type": "glue",
        "aws-region": "us-east-1",
        "s3.region": "us-east-1",
    }
)
```

### DuckDB ATTACH (via Catalog)

```sql
-- DuckDB v1.4+ supports Iceberg REST catalogs
ATTACH 'demo_catalog' AS iceberg_db (
    TYPE ICEBERG,
    CLIENT_ID 'client_id',
    CLIENT_SECRET 'client_secret',
    OAUTH2_SERVER_URI 'http://polaris:8181/api/catalog/v1/oauth/tokens',
    ENDPOINT 'http://polaris:8181/api/catalog'
);

-- ALL operations go through catalog
CREATE TABLE iceberg_db.gold.metrics AS SELECT ...;
INSERT INTO iceberg_db.gold.metrics SELECT ...;
```

## ACID Transaction Flow

### Commit Sequence

```
1. Engine requests table metadata from catalog
2. Catalog returns current snapshot ID + storage location
3. Engine writes data files to storage (NOT visible yet)
4. Engine sends commit request to catalog with:
   - Base snapshot ID (optimistic lock)
   - New data file manifests
   - Schema changes (if any)
5. Catalog validates:
   - No conflicting concurrent commits
   - Schema compatibility
   - Access permissions
6. Catalog atomically updates metadata pointer
7. Data becomes visible to all engines
```

### Conflict Detection

```python
# PyIceberg transaction with retry
from pyiceberg.exceptions import CommitFailedException

max_retries = 3
for attempt in range(max_retries):
    try:
        table = catalog.load_table("gold.metrics")
        table.overwrite(new_data)
        break
    except CommitFailedException:
        if attempt == max_retries - 1:
            raise
        # Retry with fresh metadata
        continue
```

## Multi-Engine Interoperability

### Same Table, Multiple Engines

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   DuckDB    │     │    Spark    │     │  Snowflake  │
│  (reads)    │     │  (writes)   │     │  (queries)  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────┐
│              Polaris Catalog REST API                 │
│                                                       │
│  gold.metrics table:                                  │
│  - Schema: (customer_id INT, amount DECIMAL)         │
│  - Current snapshot: snap-123456                      │
│  - Storage: s3://warehouse/gold/metrics/             │
└──────────────────────────────────────────────────────┘
```

### Engine-Specific Patterns

**dbt-duckdb (transformation)**:
```sql
-- dbt model: models/gold/metrics.sql
{{ config(materialized='table') }}

SELECT customer_id, SUM(amount) as total
FROM {{ ref('silver_orders') }}
GROUP BY 1
```

**Spark (large-scale ETL)**:
```python
spark.sql("""
    INSERT OVERWRITE polaris_catalog.gold.metrics
    PARTITION (date)
    SELECT * FROM polaris_catalog.silver.orders
""")
```

**Snowflake (analytics)**:
```sql
-- Query via external Iceberg table
SELECT * FROM gold.metrics
WHERE date > CURRENT_DATE - 30;
```

## Schema Evolution Coordination

### Safe Evolution via Catalog

```python
# Schema changes coordinated through catalog
table = catalog.load_table("gold.metrics")

with table.update_schema() as update:
    update.add_column("region", StringType(), "Customer region")
    update.rename_column("amount", "total_amount")

# All engines see new schema on next metadata fetch
```

### Evolution Rules (Iceberg Spec)

| Operation | Safe? | Notes |
|-----------|-------|-------|
| Add nullable column | ✅ | Always safe |
| Add required column | ❌ | Breaks existing data |
| Widen type (int→long) | ✅ | Iceberg promotes automatically |
| Narrow type (long→int) | ❌ | Data loss possible |
| Rename column | ✅ | Uses column IDs, not names |
| Drop column | ✅ | Soft delete in metadata |

## Access Control Patterns

### Polaris RBAC Model

```
Principal (service_account)
    └── Principal Role (data_engineer)
            └── Catalog Role (gold_writer)
                    └── Privileges:
                        - TABLE_WRITE_DATA on gold.*
                        - TABLE_READ_DATA on silver.*
                        - NAMESPACE_CREATE on gold
```

### Row-Level Security (via Catalog)

```sql
-- Polaris row access policy
CREATE ROW ACCESS POLICY region_filter AS (region)
    RETURNS BOOLEAN
    LANGUAGE SQL
    AS 'region = CURRENT_ROLE_REGION()';

ALTER TABLE gold.metrics
    SET ROW ACCESS POLICY region_filter;
```

## Governance Integration

### Classification Propagation

```
dbt model meta:                    Dagster asset metadata:
┌─────────────────────┐            ┌─────────────────────┐
│ meta:               │            │ metadata={          │
│   classification:   │   ──────►  │   "classification": │
│     pii             │            │   "pii"             │
│   owner: data-team  │            │ }                   │
└─────────────────────┘            └─────────────────────┘
                                           │
                                           ▼
                                   ┌─────────────────────┐
                                   │ Polaris table       │
                                   │ properties:         │
                                   │   classification=pii│
                                   └─────────────────────┘
```

### Lineage Tracking

Catalog maintains:
- Table dependencies (source → target)
- Column-level lineage (via dbt docs)
- Access patterns (audit log)
- Schema history (snapshots)

## Floe-Runtime Integration Points

### 1. Platform Configuration

```yaml
# platform.yaml - credentials never in code
catalogs:
  default:
    type: polaris
    uri: "${POLARIS_URI}"
    warehouse: demo_catalog
    credentials:
      mode: oauth2
      client_id:
        secret_ref: polaris-client-id
      client_secret:
        secret_ref: polaris-client-secret
```

### 2. dbt-duckdb Plugin

```python
# Automatically ATTACHes DuckDB to Polaris
from floe_dbt.plugins import polaris_plugin

# Plugin injects ATTACH SQL before dbt model execution
# Data engineers never see credentials
```

### 3. Dagster IO Manager

```python
# IO manager writes via catalog, not direct to S3
from dagster_iceberg.io_manager.arrow import PyArrowIcebergIOManager

io_manager = PyArrowIcebergIOManager(
    name="polaris_catalog",
    config=IcebergCatalogConfig(
        properties={"type": "rest", "uri": catalog_uri}
    ),
    namespace="gold",
)
```

## Troubleshooting

### "Table not found" after creation

**Cause**: Engine cached stale metadata
**Fix**: Refresh metadata or use `table.refresh()`

### "Commit failed - conflict"

**Cause**: Concurrent writes from multiple engines
**Fix**: Implement retry logic or serialise writes

### "Schema mismatch"

**Cause**: Engine using old schema version
**Fix**: Reload table metadata before operations

### "Access denied"

**Cause**: Principal lacks catalog role privileges
**Fix**: Grant appropriate catalog role to principal

## Best Practices Summary

1. **ALL writes through catalog** - Never bypass for "quick" operations
2. **Use catalog transactions** - Don't commit directly to storage
3. **Coordinate schema changes** - Use catalog's schema evolution API
4. **Apply governance at catalog** - Row/column policies, not engine-level
5. **Monitor catalog health** - Single point of failure for platform
6. **Test multi-engine scenarios** - Verify all engines see consistent data

---

**Reference**: Apache Iceberg REST Catalog Spec: https://iceberg.apache.org/spec/#rest-catalog
