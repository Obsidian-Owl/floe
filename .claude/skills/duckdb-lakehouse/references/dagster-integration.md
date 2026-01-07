# Dagster + DuckDB Integration Reference

## Installation
```bash
pip install dagster dagster-duckdb dagster-duckdb-pandas dagster-dbt
```

**floe-platform**: Installed via `pyproject.toml` in packages/floe-dagster.

## DuckDB Resource

Use when you need full SQL control within assets.

### Basic Setup
```python
from dagster_duckdb import DuckDBResource
import dagster as dg

@dg.asset(kinds={"duckdb"})
def raw_data(duckdb: DuckDBResource):
    with duckdb.get_connection() as conn:
        conn.execute("""
            CREATE OR REPLACE TABLE raw_data AS
            SELECT * FROM read_csv_auto('data/input.csv')
        """)

@dg.asset(deps=["raw_data"])
def transformed_data(duckdb: DuckDBResource):
    with duckdb.get_connection() as conn:
        conn.execute("""
            CREATE TABLE transformed_data AS
            SELECT id, SUM(amount) as total
            FROM raw_data GROUP BY id
        """)

defs = dg.Definitions(
    assets=[raw_data, transformed_data],
    resources={"duckdb": DuckDBResource(database="/tmp/warehouse.duckdb")}
)
```

### Resource with Configuration
```python
from dagster import EnvVar

duckdb_resource = DuckDBResource(
    database=EnvVar("DUCKDB_DATABASE"),
    connection_config={"arrow_large_buffer_size": True}
)
```

## DuckDB I/O Manager

Use when working with DataFrames and want automatic table storage.

### Pandas I/O Manager
```python
from dagster_duckdb_pandas import DuckDBPandasIOManager
import pandas as pd

@dg.asset
def customers() -> pd.DataFrame:
    return pd.read_csv("customers.csv")

@dg.asset
def customer_summary(customers: pd.DataFrame) -> pd.DataFrame:
    return customers.groupby("region")["revenue"].sum().reset_index()

defs = dg.Definitions(
    assets=[customers, customer_summary],
    resources={
        "io_manager": DuckDBPandasIOManager(
            database="/tmp/warehouse.duckdb",
            schema="analytics"
        )
    }
)
```

### Schema Specification (Priority Order)
1. `metadata={"schema": "my_schema"}` (highest)
2. `schema="my_schema"` in I/O manager config
3. `key_prefix=["my_schema"]`
4. `"public"` (default)

```python
# Using key_prefix
@dg.asset(key_prefix=["sales"])
def orders() -> pd.DataFrame:  # Creates: sales.orders
    ...

# Using metadata
@dg.asset(metadata={"schema": "analytics"})
def metrics() -> pd.DataFrame:  # Creates: analytics.metrics
    ...
```

### Column Selection
```python
@dg.asset(
    ins={
        "source": dg.AssetIn(
            key="large_table",
            metadata={"columns": ["id", "name"]}  # Only loads these
        )
    }
)
def filtered_data(source: pd.DataFrame) -> pd.DataFrame:
    return source
```

## Partitioned Assets

### Static Partitions
```python
@dg.asset(
    partitions_def=dg.StaticPartitionsDefinition(["US", "EU", "APAC"]),
    metadata={"partition_expr": "region"}
)
def regional_data(context: dg.AssetExecutionContext) -> pd.DataFrame:
    region = context.partition_key
    return load_data_for_region(region)

# I/O Manager generates: SELECT * FROM regional_data WHERE region IN ('US')
```

### Time-Based Partitions
```python
@dg.asset(
    partitions_def=dg.DailyPartitionsDefinition(start_date="2024-01-01"),
    metadata={"partition_expr": "TO_TIMESTAMP(event_date)"}
)
def daily_events(context: dg.AssetExecutionContext) -> pd.DataFrame:
    date = context.partition_key
    return load_events(date)
```

### Multi-Dimensional Partitions
```python
@dg.asset(
    partitions_def=dg.MultiPartitionsDefinition({
        "date": dg.DailyPartitionsDefinition(start_date="2024-01-01"),
        "region": dg.StaticPartitionsDefinition(["US", "EU"])
    }),
    metadata={
        "partition_expr": {
            "date": "TO_TIMESTAMP(event_date)",
            "region": "region_code"
        }
    }
)
def partitioned_events(context: dg.AssetExecutionContext) -> pd.DataFrame:
    keys = context.partition_key.keys_by_dimension
    return load_events(keys["date"], keys["region"])
```

## floe-platform: dbt Integration

### Auto-Discovery from dbt Project

```python
# demo/data_engineering/orchestration/definitions.py
from pathlib import Path
from dagster import Definitions
from dagster_dbt import DbtCliResource, load_assets_from_dbt_project
from floe_dagster.translator import FloeTranslator

DBT_PROJECT_DIR = Path(__file__).parent.parent / "dbt"

dbt_assets = load_assets_from_dbt_project(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
    key_prefix=["dbt"],
    dagster_dbt_translator=FloeTranslator(),  # Custom metadata
)

defs = Definitions(
    assets=dbt_assets,
    resources={
        "dbt": DbtCliResource(
            project_dir=str(DBT_PROJECT_DIR),
            profiles_dir=str(DBT_PROJECT_DIR),
        )
    }
)
```

**How It Works**:
1. `dbt parse` at build time → generates `target/manifest.json` (no DB connection)
2. Dagster reads manifest.json → creates Dagster assets
3. Dagster runs `dbt run` → dbt-duckdb plugin → ATTACH catalog → executes models

**Key Points**:
- No database connection needed for discovery
- Actual execution triggers plugin initialization
- Custom FloeTranslator adds floe-specific metadata

### Custom Translator

```python
# packages/floe-dagster/src/floe_dagster/translator.py
from dagster_dbt import DagsterDbtTranslator

class FloeTranslator(DagsterDbtTranslator):
    def get_asset_key(self, dbt_resource_props):
        """Use dbt schema + model name for asset key."""
        return dg.AssetKey([
            dbt_resource_props["schema_name"],
            dbt_resource_props["name"]
        ])

    def get_group_name(self, dbt_resource_props):
        """Group by layer (bronze/silver/gold)."""
        schema = dbt_resource_props["schema_name"]
        if schema in ("bronze", "silver", "gold"):
            return schema
        return "default"
```

## Jobs and Scheduling

```python
# Job definition
update_job = dg.define_asset_job(
    name="update_job",
    selection=dg.AssetSelection.assets("customer_summary"),
    op_retry_policy=dg.RetryPolicy(max_retries=3)
)

# Schedule
daily_schedule = dg.ScheduleDefinition(
    job=update_job,
    cron_schedule="0 6 * * *"  # 6 AM daily
)

defs = dg.Definitions(
    assets=[...],
    jobs=[update_job],
    schedules=[daily_schedule],
    resources={...}
)
```

## Error Handling

### DuckDB Concurrency
DuckDB allows only one writer at a time. The I/O manager uses `backoff()` with 10 retries.

```python
# Manual backoff for resource usage
from dagster._utils.backoff import backoff
import duckdb

@dg.asset
def resilient_asset() -> None:
    conn = backoff(
        fn=duckdb.connect,
        retry_on=(RuntimeError, duckdb.IOException),
        kwargs={"database": "/tmp/warehouse.duckdb"},
        max_retries=10
    )
    conn.execute("INSERT INTO ...")
    conn.close()
```

### Best Practice: Use DuckDBResource (handles backoff internally)
```python
@dg.asset
def better_asset(duckdb: DuckDBResource) -> None:
    with duckdb.get_connection() as conn:
        conn.execute("INSERT INTO ...")
```

## Multiple I/O Managers

```python
from dagster_duckdb_pandas import DuckDBPandasIOManager
from dagster_aws.s3.io_manager import s3_pickle_io_manager

@dg.asset(io_manager_key="warehouse")
def table_data() -> pd.DataFrame:
    ...

@dg.asset(io_manager_key="blob")
def large_artifact():
    ...

defs = dg.Definitions(
    assets=[table_data, large_artifact],
    resources={
        "warehouse": DuckDBPandasIOManager(database="/tmp/warehouse.duckdb"),
        "blob": s3_pickle_io_manager
    }
)
```

## floe-platform K8s Resource Management

### Compute Logs Storage

```yaml
# demo/platform-config/platform/local/platform.yaml
observability:
  compute_logs:
    enabled: true
    manager_type: s3
    storage_ref: default
    bucket: dagster-compute-logs
    prefix: "compute-logs/"
    retention_days: 30
    local_dir: /tmp/dagster-compute-logs
    upload_interval: 30
```

**What This Does**:
- Captures stdout/stderr from Dagster runs
- Uploads to S3 (LocalStack in local environment)
- Visible in Dagster UI for debugging
- Auto-cleanup after 30 days

### Resource Limits

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
        memory: "12Gi"     # 12Gi max (research-backed for PyArrow + DuckDB + dbt)
      env:
        DUCKDB_MEMORY_LIMIT: "8GB"  # 67% of 12Gi limit
        DUCKDB_THREADS: "4"
        DUCKDB_TEMP_DIRECTORY: "/tmp/duckdb"
```

**Applied to Dagster Run Pods**:
- Guarantees resources for scheduling
- Allows bursting for compute-intensive workloads
- Prevents OOM with memory limits

## Common Patterns in floe-platform

### Pattern A: Python Assets (Bronze Layer)
```python
# demo/data_engineering/orchestration/assets/bronze.py
import dagster as dg
import pandas as pd

@dg.asset(
    group_name="bronze",
    compute_kind="python"
)
def raw_customers() -> pd.DataFrame:
    return pd.read_csv("data/customers.csv")
```

### Pattern B: dbt Assets (Silver/Gold Layers)
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
WHERE customer_id IS NOT NULL
```

**Dagster Auto-Discovers**:
- Asset key: `["dbt", "silver", "stg_customers"]`
- Group: `silver` (via FloeTranslator)
- Depends on: `raw_customers` (via dbt source)

### Pattern C: Mixed Python + dbt Pipeline
```python
# Dagster lineage:
# raw_customers (Python) → stg_customers (dbt) → customer_summary (dbt)

# Python asset materializes to DuckDB
@dg.asset(io_manager_key="duckdb")
def raw_customers() -> pd.DataFrame:
    ...

# dbt reads from DuckDB, writes to Iceberg via ATTACH
# {{ source('bronze', 'raw_customers') }}
# → SELECT FROM bronze.raw_customers (DuckDB)
# → CREATE TABLE polaris_catalog.silver.stg_customers AS SELECT ... (Iceberg)
```

## References

- Dagster DuckDB Integration: https://docs.dagster.io/_apidocs/libraries/dagster-duckdb
- Dagster dbt Integration: https://docs.dagster.io/integrations/dbt
- floe-platform Dagster Translator: packages/floe-dagster/src/floe_dagster/translator.py
- floe-platform Definitions: demo/data_engineering/orchestration/definitions.py
