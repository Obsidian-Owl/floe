# DuckDB + Iceberg + Apache Polaris Reference

## Architecture Overview (floe-platform)

```
┌─────────────────────────────────────────────────────────────┐
│              Apache Polaris (REST Catalog)                   │
│         OAuth2 Authentication (Client Credentials)           │
│              ↕ Metadata Operations                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   DuckDB ←── ATTACH (inline creds) ──→ Polaris Catalog     │
│         ↓ Native Iceberg Reads/Writes                       │
│         ↓                                                    │
│   Iceberg Tables on S3 (LocalStack for local dev)           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**floe-platform Architecture Change**:
- ❌ Old: PyIceberg for writes (complex, separate tool)
- ✅ New: DuckDB native Iceberg writes via ATTACH (DuckDB 1.4+)

## DuckDB Iceberg Extension (Read & Write Operations)

### Setup
```python
import duckdb

conn = duckdb.connect("/tmp/floe.duckdb")  # File-based for extension persistence
conn.execute("INSTALL iceberg; LOAD iceberg;")
```

**floe-platform**: Extensions pre-installed in entrypoint.sh, no INSTALL/LOAD needed in plugin.

### Direct Table Scan (Without Catalog)
```python
# From S3
conn.sql("""
SELECT * FROM iceberg_scan('s3://bucket/table/metadata/v1.metadata.json')
""")

# With parameters
conn.sql("""
SELECT * FROM iceberg_scan(
    'path/to/table',
    allow_moved_paths = true,
    metadata_compression_codec = 'gzip'
)
""")
```

### Time Travel
```python
# By snapshot ID
conn.sql("""
SELECT * FROM iceberg_scan('path/to/table',
    snapshot_from_id = 3776207205136740581)
""")

# By timestamp
conn.sql("""
SELECT * FROM iceberg_scan('path/to/table',
    snapshot_from_timestamp = TIMESTAMP '2024-01-01 12:00:00')
""")
```

### Metadata Inspection
```python
conn.sql("SELECT * FROM iceberg_snapshots('path/to/table')")
conn.sql("SELECT * FROM iceberg_metadata('path/to/table')")
```

## Connecting to Polaris REST Catalog (floe-platform Pattern)

### Inline Credentials (Recommended for floe-platform)

```python
# packages/floe-dbt/src/floe_dbt/plugins/polaris.py

catalog_uri = "http://floe-infra-polaris:8181/api/catalog"
warehouse = "demo_catalog"
client_id = os.getenv("POLARIS_CLIENT_ID")
client_secret = os.getenv("POLARIS_CLIENT_SECRET")

oauth2_server_uri = f"{catalog_uri}/v1/oauth/tokens"

attach_sql = f"""
ATTACH IF NOT EXISTS '{warehouse}' AS polaris_catalog (
    TYPE ICEBERG,
    CLIENT_ID '{client_id}',
    CLIENT_SECRET '{client_secret}',
    OAUTH2_SERVER_URI '{oauth2_server_uri}',
    ENDPOINT '{catalog_uri}'
)
"""
conn.execute(attach_sql)

# Query tables
conn.sql("SELECT * FROM polaris_catalog.namespace.table_name")
conn.sql("SHOW ALL TABLES")
```

**Why Inline Credentials?**
- DuckDB secret manager initializes BEFORE plugin runs
- `CREATE SECRET` fails with "Secret Manager settings cannot be changed"
- Inline credentials bypass secret manager entirely
- Supported in DuckDB 1.4+

### Traditional Approach (Using Secrets - NOT used in floe-platform)

```python
# ❌ This fails in floe-platform due to secret manager timing
conn.execute("""
CREATE SECRET polaris_secret (
    TYPE iceberg,
    CLIENT_ID 'your_client_id',
    CLIENT_SECRET 'your_client_secret'
)
""")

conn.execute("""
ATTACH 'warehouse_name' AS ice (
    TYPE iceberg,
    ENDPOINT 'https://polaris.example.com/api/catalog',
    SECRET polaris_secret
)
""")
```

**Why This Fails**:
1. dbt-duckdb opens connection → Secret manager initializes
2. Plugin `configure_connection()` runs → Too late to CREATE SECRET
3. Error: "Secret Manager settings cannot be changed after the secret manager is used"

### Supported Operations (DuckDB 1.4+)

```sql
-- ✅ SUPPORTED
CREATE SCHEMA polaris_catalog.new_namespace;
CREATE TABLE polaris_catalog.ns.new_table (id INT, name VARCHAR);
INSERT INTO polaris_catalog.ns.new_table VALUES (1, 'test');
SELECT * FROM polaris_catalog.ns.new_table;
DROP TABLE polaris_catalog.ns.new_table;

-- Time travel
SELECT * FROM polaris_catalog.ns.t AT (VERSION => 123456);
SELECT * FROM polaris_catalog.ns.t AT (TIMESTAMP => TIMESTAMP '2024-01-01');

-- ❌ NOT SUPPORTED (as of DuckDB 1.4.3)
UPDATE polaris_catalog.ns.table SET col = 'value';
DELETE FROM polaris_catalog.ns.table WHERE id = 1;
MERGE INTO polaris_catalog.ns.table ...;
```

## floe-platform dbt Materialization

### Custom table.sql Materialization (Platform-Enforced)

```sql
-- dbt macro: macros/materializations/table.sql
{% materialization table, adapter='duckdb' %}
    {%- set target_relation = this -%}
    {%- set catalog_prefix = 'polaris_catalog.' -%}

    {%- set full_name = catalog_prefix ~ target_relation.schema ~ '.' ~ target_relation.identifier -%}

    {% call statement('main') -%}
        CREATE OR REPLACE TABLE {{ full_name }} AS
        {{ sql }}
    {%- endcall %}

    {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}
```

**What This Does**:
- Intercepts all `{{ config(materialized='table') }}`
- Prefixes with `polaris_catalog.` (attached catalog)
- Uses DuckDB native CREATE TABLE (Iceberg via ATTACH)
- Ensures catalog coordination (metadata + storage)

### Data Engineer Experience

```sql
-- demo/data_engineering/dbt/models/silver/stg_customers.sql
{{ config(
    materialized='table',
    schema='silver'
) }}

SELECT
    customer_id,
    customer_name,
    region
FROM {{ source('bronze', 'raw_customers') }}
```

**What Actually Executes**:
```sql
-- Platform transparently rewrites to:
CREATE OR REPLACE TABLE polaris_catalog.silver.stg_customers AS
SELECT
    customer_id,
    customer_name,
    region
FROM bronze.raw_customers
```

**Benefits**:
- ✅ Data engineer never sees catalog prefix
- ✅ Platform enforces catalog control
- ✅ DuckDB handles Iceberg write natively
- ✅ Polaris tracks metadata automatically

## PyIceberg (Optional - Not Primary in floe-platform)

### Installation
```bash
pip install "pyiceberg[pyarrow,s3]"
```

**floe-platform**: Installed for metadata operations (PolarisCatalog), but DuckDB handles data writes.

### Configuration (~/.pyiceberg.yaml or inline)
```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog("polaris", **{
    "type": "rest",
    "uri": "http://floe-infra-polaris:8181/api/catalog",
    "credential": "client_id:client_secret",
    "warehouse": "demo_catalog",
    "scope": "PRINCIPAL_ROLE:service_admin"
})

table = catalog.load_table("namespace.table_name")
```

### PolarisCatalog (floe-polaris Package)

```python
# packages/floe-polaris/src/floe_polaris/client.py
from floe_polaris.config import PolarisCatalogConfig
from floe_polaris.client import PolarisCatalog

catalog_config = PolarisCatalogConfig(
    uri="http://floe-infra-polaris:8181/api/catalog",
    warehouse="demo_catalog",
    client_id=os.getenv("POLARIS_CLIENT_ID"),
    client_secret=os.getenv("POLARIS_CLIENT_SECRET"),
    scope="PRINCIPAL_ROLE:service_admin",
    s3_endpoint="http://floe-infra-localstack:4566",
    s3_region="us-east-1",
    s3_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    s3_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    s3_path_style_access=True,
)

catalog = PolarisCatalog(catalog_config)

# Metadata operations
namespaces = catalog.list_namespaces()
tables = catalog.list_tables("bronze")
```

**Usage in floe-platform**: Plugin `initialize()` method creates PolarisCatalog for metadata operations, but actual data writes use DuckDB native Iceberg via ATTACH.

## Credential Management

### floe-platform Two-Tier Configuration

**platform.yaml** (Platform Engineer):
```yaml
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
      scope: "PRINCIPAL_ROLE:service_admin"
```

**K8s Secrets**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: polaris-client-id
stringData:
  value: "<your-client-id>"  # Generate via Polaris API
---
apiVersion: v1
kind: Secret
metadata:
  name: polaris-client-secret
stringData:
  value: "<your-client-secret>"  # Generate via Polaris API
```

**Environment Variables** (Injected by K8s):
```bash
POLARIS_CLIENT_ID=${POLARIS_CLIENT_ID}      # From K8s secret
POLARIS_CLIENT_SECRET=${POLARIS_CLIENT_SECRET}  # From K8s secret
```

**Plugin Usage**:
```python
client_id = self.config.get("client_id") or os.getenv("POLARIS_CLIENT_ID")
client_secret = self.config.get("client_secret") or os.getenv("POLARIS_CLIENT_SECRET")
```

### S3 Credentials (LocalStack for Local Dev)

```yaml
# platform.yaml
storage:
  bronze:
    type: s3
    endpoint: "http://floe-infra-localstack:4566"
    region: us-east-1
    bucket: iceberg-bronze
    path_style_access: true
    credentials:
      mode: static
      secret_ref: aws-credentials
```

**K8s Secret**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: aws-credentials
stringData:
  access_key_id: "test"      # LocalStack accepts any value
  secret_access_key: "test"
```

**Environment Variables**:
```bash
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
```

## Complete Read-Transform-Write Pattern (floe-platform)

```python
# demo/data_engineering/orchestration/assets/bronze.py
import dagster as dg
import pandas as pd
import duckdb

@dg.asset(group_name="bronze")
def raw_customers() -> pd.DataFrame:
    """Bronze layer: Load raw CSV data."""
    return pd.read_csv("data/customers.csv")

# dbt model: demo/data_engineering/dbt/models/silver/stg_customers.sql
# {{ config(materialized='table', schema='silver') }}
# SELECT customer_id, customer_name, region
# FROM {{ source('bronze', 'raw_customers') }}

# What actually executes:
# 1. Dagster materializes raw_customers to DuckDB (bronze.raw_customers)
# 2. dbt-duckdb plugin runs configure_connection()
#    → ATTACH polaris_catalog with inline credentials
# 3. dbt executes model with custom materialization
#    → CREATE TABLE polaris_catalog.silver.stg_customers AS SELECT ...
# 4. DuckDB writes to Iceberg via ATTACH (catalog-coordinated)
# 5. Polaris tracks metadata automatically
```

**Benefits**:
- ✅ Single tool (DuckDB) for reads and writes
- ✅ Catalog coordination via ATTACH
- ✅ No PyIceberg needed for writes
- ✅ Simpler architecture, fewer dependencies

## Common Errors and Solutions

### Error 1: "Secret Manager settings cannot be changed"

**Full Error**:
```
Invalid Input Error: Changing Secret Manager settings after the secret manager is used is not allowed!
```

**Root Cause**: Attempting `CREATE SECRET` after secret manager initialization.

**Solution**: Use inline credentials in ATTACH statement (see above).

### Error 2: "NotFoundException: Unable to find warehouse demo_catalog"

**Symptom**: ATTACH succeeds but queries fail.

**Root Cause**: Polaris warehouse not created via REST API.

**Solution**: Create warehouse using Polaris REST API or UI:
```bash
curl -X POST http://localhost:30181/api/management/v1/warehouses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"warehouse": {"name": "demo_catalog"}}'
```

### Error 3: "No ICEBERG secret by the name of 'polaris_secret'"

**Root Cause**: DuckDB Issue #18021 - persistent secrets not automatically loaded.

**Solution**: Use inline credentials (no secret creation needed).

### Error 4: "ICEBERG extension not found"

**Root Cause**: Extensions not pre-installed or using `:memory:` database.

**Solution**: Pre-install in entrypoint with file-based database (`/tmp/floe.duckdb`).

## Best Practices (floe-platform)

### DO ✅

- ✅ Use ATTACH with inline credentials (bypasses secret manager)
- ✅ Pre-install extensions in entrypoint (file-based database)
- ✅ Use DuckDB native Iceberg writes (simpler than PyIceberg)
- ✅ Use custom dbt materialization (enforces catalog prefix)
- ✅ Use environment variables from K8s secrets
- ✅ Create Polaris warehouse before ATTACH

### DON'T ❌

- ❌ Use CREATE SECRET in plugin (secret manager already initialized)
- ❌ Use `:memory:` database (extensions don't persist)
- ❌ Bypass ATTACH for direct S3 writes (loses catalog coordination)
- ❌ Use PyIceberg for routine writes (adds complexity)
- ❌ Hardcode credentials (use env vars from K8s secrets)

## References

- DuckDB Iceberg Extension: https://duckdb.org/docs/extensions/iceberg
- DuckDB Issue #18021: Lazy loading of persistent secrets
- Apache Polaris: https://polaris.apache.org/
- PyIceberg: https://py.iceberg.apache.org/
- floe-platform Polaris Plugin: packages/floe-dbt/src/floe_dbt/plugins/polaris.py
- floe-polaris Package: packages/floe-polaris/src/floe_polaris/
