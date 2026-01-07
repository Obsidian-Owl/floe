# Lakehouse Architecture Patterns (floe-platform)

## Design Principles

### 1. DuckDB as Ephemeral Compute
```python
# Pattern: Spin up, query, terminate
def process_data():
    with duckdb.connect("/tmp/floe.duckdb") as conn:
        conn.execute("INSTALL httpfs; LOAD httpfs;")
        result = conn.sql("SELECT * FROM 's3://bucket/*.parquet'").fetchdf()
        # Connection terminates, no state persists
    return result
```

**Benefits**:
- Zero maintenance (no database server)
- Cost-efficient (scales to zero)
- Concurrency isolation (each job gets fresh instance)
- Simple deployment (single binary)

**floe-platform Application**:
- Dagster run pods use ephemeral DuckDB connections
- Each pipeline run gets isolated compute
- File-based database (`/tmp/floe.duckdb`) for extension persistence only
- No shared state between runs

### 2. Catalog-First Architecture
```
Catalog (Polaris) = Single source of truth for metadata
Compute (DuckDB)  = Stateless, ephemeral query engine
Storage (Iceberg) = Durable, ACID-compliant tables on S3
```

**Why it matters**:
- Vendor neutrality (swap compute engines freely)
- Multi-engine access (DuckDB, Spark, Trino share data)
- ACID through catalog (coordinated atomic commits)

**floe-platform Implementation**:
- Custom dbt materialization enforces catalog prefix
- All writes go through `polaris_catalog.schema.table`
- DuckDB ATTACH provides catalog coordination
- Platform controls catalog access via two-tier configuration

### 3. Read-Transform-Write Pattern

```python
# DuckDB reads → transforms → writes (all via ATTACH)

def etl_pipeline():
    # READ with DuckDB (via ATTACH)
    conn = duckdb.connect("/tmp/floe.duckdb")
    conn.execute("""
        ATTACH 'warehouse' AS polaris_catalog (
            TYPE ICEBERG,
            CLIENT_ID '...',
            CLIENT_SECRET '...',
            OAUTH2_SERVER_URI '...',
            ENDPOINT '...'
        )
    """)

    transformed = conn.sql("""
        SELECT customer_id, SUM(amount) as total
        FROM polaris_catalog.bronze.orders
        GROUP BY customer_id
    """).arrow()

    # WRITE with DuckDB (via ATTACH - native Iceberg)
    conn.execute("""
        CREATE OR REPLACE TABLE polaris_catalog.silver.customer_totals AS
        SELECT * FROM transformed
    """)
```

**floe-platform Advantage**: Single tool (DuckDB) for reads and writes, simpler than DuckDB read + PyIceberg write.

## Dagster Orchestration Patterns

### Pattern A: Python Assets + dbt Transforms (floe-platform)

```python
# demo/data_engineering/orchestration/assets/bronze.py
import dagster as dg
import pandas as pd

@dg.asset(group_name="bronze", compute_kind="python")
def raw_customers() -> pd.DataFrame:
    """Bronze layer: Load raw CSV data."""
    return pd.read_csv("data/customers.csv")
```

```sql
-- demo/data_engineering/dbt/models/silver/stg_customers.sql
{{ config(materialized='table', schema='silver') }}

SELECT
    customer_id,
    customer_name,
    region
FROM {{ source('bronze', 'raw_customers') }}
WHERE customer_id IS NOT NULL
```

**Execution Flow**:
1. Dagster materializes `raw_customers` → DuckDB table `bronze.raw_customers`
2. Dagster triggers dbt run → dbt-duckdb plugin → ATTACH polaris_catalog
3. dbt executes model → Custom materialization → `CREATE TABLE polaris_catalog.silver.stg_customers AS SELECT ...`
4. DuckDB writes to Iceberg via ATTACH (catalog-coordinated)

### Pattern B: Partitioned Iceberg Assets

```python
@dg.asset(
    partitions_def=dg.DailyPartitionsDefinition(start_date="2024-01-01"),
    metadata={"partition_expr": "event_date"}
)
def daily_aggregates(context: dg.AssetExecutionContext) -> pa.Table:
    date = context.partition_key

    conn = duckdb.connect("/tmp/floe.duckdb")
    conn.execute("ATTACH 'warehouse' AS polaris_catalog (...)")

    return conn.sql(f"""
        SELECT event_date, COUNT(*) as events
        FROM polaris_catalog.bronze.events
        WHERE event_date = '{date}'
        GROUP BY event_date
    """).arrow()
```

**Benefits**:
- Partition-aware reads (efficient)
- Dagster tracks partition status
- Iceberg metadata handles partition pruning

### Pattern C: Medallion Architecture (Bronze/Silver/Gold)

```
┌─────────────────────────────────────────────────────────┐
│                  BRONZE LAYER                            │
│  Python assets → DuckDB → S3 (iceberg-bronze bucket)   │
│  Raw CSV/JSON → Parquet/Iceberg                         │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│                  SILVER LAYER                            │
│  dbt models → DuckDB → Polaris → S3 (iceberg-silver)   │
│  Cleaned, deduplicated, enriched                        │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│                   GOLD LAYER                             │
│  dbt models → DuckDB → Polaris → S3 (iceberg-gold)     │
│  Aggregated marts for analytics                         │
└─────────────────────────────────────────────────────────┘
```

**floe-platform platform.yaml**:
```yaml
storage:
  bronze:
    type: s3
    bucket: iceberg-bronze
    retention: 7 years  # Audit trail
  silver:
    type: s3
    bucket: iceberg-silver
    retention: 2 years  # Intermediate
  gold:
    type: s3
    bucket: iceberg-gold
    retention: 90 days  # Analytics
```

**Benefits**:
- Layer-specific access controls
- Differentiated retention policies
- Performance isolation (Bronze: high write, Gold: high read)
- Compliance (GDPR/CCPA data minimization)

## floe-platform Two-Tier Configuration

### Separation of Concerns

**floe.yaml** (Data Engineer - same across all environments):
```yaml
name: customer-analytics
version: "1.0.0"
storage: default      # Logical reference
catalog: default      # Logical reference
compute: default      # Logical reference

transforms:
  - name: stg_customers
    type: dbt
    schema: silver
```

**platform.yaml** (Platform Engineer - environment-specific):
```yaml
version: "1.1.0"

compute:
  default:
    type: duckdb
    properties:
      path: "/tmp/floe.duckdb"
      threads: 4

catalogs:
  default:
    type: polaris
    uri: "http://floe-infra-polaris:8181/api/catalog"
    warehouse: demo_catalog
    credentials:
      mode: oauth2
      client_id:
        secret_ref: polaris-client-id
      client_secret:
        secret_ref: polaris-client-secret

storage:
  default:
    type: s3
    endpoint: "http://floe-infra-localstack:4566"
    bucket: iceberg-bronze
    credentials:
      mode: static
      secret_ref: aws-credentials
```

**Benefits**:
- ✅ Data engineers never see credentials
- ✅ Same floe.yaml works across dev/staging/prod
- ✅ Platform engineers manage infrastructure centrally
- ✅ Security via K8s secrets

### Configuration Resolution Flow

```
floe.yaml (catalog: default)
    ↓
platform.yaml (catalogs.default → polaris config)
    ↓
K8s Secrets (polaris-client-id, polaris-client-secret)
    ↓
Environment Variables (POLARIS_CLIENT_ID, POLARIS_CLIENT_SECRET)
    ↓
DbtProfilesGenerator (generates profiles.yml)
    ↓
dbt-duckdb Plugin (reads {{ env_var('POLARIS_CLIENT_ID') }})
    ↓
ATTACH with inline credentials
```

## When to Use This Stack

✅ **Good Fit:**
- Data volume < 500GB per pipeline run
- Multiple query engines need access to same data
- ACID transactions required
- Dagster already used for orchestration
- Kubernetes deployment
- Separation of data/platform engineering

❌ **Poor Fit:**
- Data exceeds single-machine memory/disk
- Real-time streaming ingestion (<1s latency)
- Sub-second query latency at massive scale
- High-concurrency multi-writer workloads
- No orchestration framework

## Anti-Patterns

### ❌ Don't: Use DuckDB as Persistent Shared Database
```python
# BAD: Multiple services writing to same file
conn = duckdb.connect("/shared/database.duckdb")  # Write conflicts!
```
**Fix:** Use Iceberg for shared persistent storage, DuckDB for ephemeral compute.

### ❌ Don't: Bypass the Catalog
```python
# BAD: Direct S3 write without catalog
conn.execute("COPY result TO 's3://bucket/table/data.parquet'")
# Other engines won't see this data!
```
**Fix:** Always write through ATTACH (catalog coordination).

### ❌ Don't: Use CREATE SECRET in Plugin
```python
# BAD: Secret manager already initialized
def configure_connection(self, conn):
    conn.execute("CREATE SECRET polaris (...)")  # ❌ FAILS
```
**Fix:** Use inline credentials in ATTACH statement.

### ❌ Don't: Use :memory: Database in Container
```python
# BAD: Extensions don't persist
conn = duckdb.connect(":memory:")  # Each connection re-installs extensions
```
**Fix:** Use file-based database (`/tmp/floe.duckdb`) with pre-installation.

### ❌ Don't: Hardcode Credentials
```python
# BAD: Credentials in code - NEVER DO THIS
client_id = "..."  # EXPOSED - hardcoded credential!
```
**Fix:** Use environment variables from K8s secrets: `os.getenv("POLARIS_CLIENT_ID")`

### ❌ Don't: Skip dbt parse at Build Time
```dockerfile
# BAD: Skip dbt parse
RUN echo "Skipping dbt parse"
```
**Fix:** Run `dbt parse` at build time (generates manifest.json, no DB connection).

### ❌ Don't: Run dbt compile in Entrypoint
```bash
# BAD: Triggers secret manager errors
dbt compile
```
**Fix:** Skip `dbt compile` in entrypoint (use build-time manifest.json).

## Performance Guidelines (floe-platform K8s)

| Workload | Memory per Thread | floe-platform Allocation |
|----------|-------------------|--------------------------|
| Simple queries | 125 MB | 4Gi request (sufficient) |
| Aggregations | 1-2 GB | 12Gi limit (optimal) |
| Complex joins | 3-4 GB | 12Gi limit (optimal) |
| Optimal | 5 GB | 12Gi limit (research-backed) |

```yaml
# demo/platform-config/platform/local/platform.yaml
infrastructure:
  resource_profiles:
    transform:
      requests:
        cpu: "1000m"       # 1 core guaranteed
        memory: "4Gi"      # 4Gi guaranteed (ensures scheduling)
      limits:
        cpu: "8000m"       # 8 cores burstable
        memory: "12Gi"     # 12Gi max (DuckDB + PyArrow + dbt)
      env:
        DUCKDB_MEMORY_LIMIT: "8GB"  # 67% of 12Gi limit
        DUCKDB_THREADS: "4"
        DUCKDB_TEMP_DIRECTORY: "/tmp/duckdb"
```

**Rationale**:
- 4Gi request ensures pod scheduling
- 12Gi limit allows bursting for compute-intensive workloads
- DUCKDB_MEMORY_LIMIT prevents OOM (67% of container limit)
- 4 threads balances CPU/memory (5GB per thread optimal)

### DuckDB Configuration Best Practices

```python
# For network-bound workloads, increase threads
conn.execute("SET threads = 16")  # Beyond CPU count is OK

# Enable column pruning (automatic with SQL projection)
conn.sql("SELECT col1, col2 FROM huge_table")  # Only reads needed columns

# Use predicate pushdown (automatic with WHERE clause)
conn.sql("SELECT * FROM parquet WHERE partition_col = 'value'")

# Spill to disk for large aggregations
conn.execute("SET temp_directory = '/tmp/duckdb'")
```

## Observability and Debugging

### Compute Logs (floe-platform)

```yaml
# demo/platform-config/platform/local/platform.yaml
observability:
  compute_logs:
    enabled: true
    manager_type: s3
    bucket: dagster-compute-logs
    prefix: "compute-logs/"
    retention_days: 30
    local_dir: /tmp/dagster-compute-logs
    upload_interval: 30
```

**What This Captures**:
- stdout/stderr from Dagster runs
- DuckDB query output
- dbt compilation logs
- Plugin initialization logs
- Visible in Dagster UI for debugging

### Lineage Tracking

```yaml
# demo/platform-config/platform/local/platform.yaml
observability:
  lineage: true
  lineage_endpoint: "http://floe-infra-marquez:5000/api/v1/lineage"
```

**What This Tracks**:
- Dagster asset lineage
- dbt model dependencies
- Iceberg table reads/writes
- Data flow visualization in Marquez UI

### Tracing

```yaml
# demo/platform-config/platform/local/platform.yaml
observability:
  traces: true
  otlp_endpoint: "http://floe-infra-jaeger-collector:4317"
```

**What This Traces**:
- Dagster run execution
- dbt model compilation/execution
- DuckDB query performance
- Polaris catalog API calls
- Visible in Jaeger UI for performance analysis

## References

- floe-platform Architecture: references/floe-platform-integration.md
- DuckDB Core: references/duckdb-core.md
- Dagster Integration: references/dagster-integration.md
- Iceberg/Polaris: references/iceberg-polaris.md
- Platform Configuration Guide: docs/platform-config.md (floe-runtime repo)
- Pipeline Configuration Guide: docs/pipeline-config.md (floe-runtime repo)
