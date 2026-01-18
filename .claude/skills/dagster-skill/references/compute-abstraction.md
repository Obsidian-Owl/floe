# Compute Abstraction Layer

## Design Principle

**dbt owns SQL transformations. Dagster orchestrates execution. Compute is SWAPPABLE.**

```
┌─────────────────────────────────────────────────────────────┐
│                     dbt SQL Models                           │
│  (Same SQL runs on DuckDB, Spark, Snowflake via adapters)   │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
        ┌─────────┐     ┌─────────┐     ┌─────────┐
        │ DuckDB  │     │  Spark  │     │Snowflake│
        │ Default │     │  Scale  │     │ Analytics│
        └─────────┘     └─────────┘     └─────────┘
```

## Target Selection Strategy

| Use Case | Compute Target | Why |
|----------|---------------|-----|
| Development | DuckDB | Fast, local, zero infra |
| Unit tests | DuckDB | Sub-second feedback |
| < 10GB transforms | DuckDB | Cost-effective |
| 10GB - 1TB transforms | Spark | Distributed processing |
| > 1TB transforms | Spark | Only option at scale |
| BI/Analytics queries | Snowflake | Optimised for concurrency |
| ML feature serving | Snowflake/DuckDB | Low latency |

## DuckDB (Default)

### Configuration

```yaml
# dbt/profiles.yml
floe:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: :memory:  # Ephemeral compute
      extensions:
        - iceberg
      plugins:
        - module: floe_dbt.plugins.polaris
          config:
            catalog_uri: "{{ env_var('POLARIS_URI') }}"
```

### Dagster Integration

```python
from dagster_duckdb import DuckDBResource

@asset(kinds={"duckdb"})
def duckdb_analytics(duckdb: DuckDBResource):
    with duckdb.get_connection() as conn:
        # Catalog already attached by dbt plugin
        return conn.execute("""
            SELECT * FROM polaris.gold.metrics
        """).fetch_df()
```

### DuckDB + Iceberg via Catalog

```sql
-- DuckDB v1.4+ native Iceberg REST support
ATTACH 'demo_catalog' AS cat (
    TYPE ICEBERG,
    ENDPOINT 'http://polaris:8181/api/catalog',
    CLIENT_ID '${POLARIS_CLIENT_ID}',
    CLIENT_SECRET '${POLARIS_CLIENT_SECRET}'
);

-- CRUD operations via catalog
CREATE TABLE cat.gold.metrics AS SELECT ...;
INSERT INTO cat.gold.metrics SELECT ...;
UPDATE cat.gold.metrics SET x = y WHERE ...;
DELETE FROM cat.gold.metrics WHERE ...;

-- Time travel
SELECT * FROM cat.gold.metrics AT (TIMESTAMP => '2025-01-01');
```

## Spark (Scale)

### Configuration

```yaml
# dbt/profiles.yml
floe:
  outputs:
    spark:
      type: spark
      method: session
      schema: gold
      host: spark-thrift:10000
```

### Spark Session with Iceberg

```python
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("floe-etl")
    .config("spark.sql.catalog.polaris", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.polaris.type", "rest")
    .config("spark.sql.catalog.polaris.uri", "http://polaris:8181/api/catalog")
    .config("spark.sql.catalog.polaris.credential", f"{client_id}:{client_secret}")
    .config("spark.sql.catalog.polaris.warehouse", "demo_catalog")
    .config("spark.sql.defaultCatalog", "polaris")
    .getOrCreate()
)
```

### Dagster Integration

```python
from dagster import asset, ConfigurableResource
from pyspark.sql import SparkSession

class SparkResource(ConfigurableResource):
    master: str = "local[*]"
    catalog_uri: str

    def get_session(self) -> SparkSession:
        return (
            SparkSession.builder
            .master(self.master)
            .config("spark.sql.catalog.polaris.uri", self.catalog_uri)
            # ... other configs
            .getOrCreate()
        )

@asset(kinds={"spark"})
def large_scale_etl(spark: SparkResource):
    session = spark.get_session()
    session.sql("""
        INSERT OVERWRITE polaris.gold.large_table
        SELECT * FROM polaris.silver.source
    """)
```

## Snowflake (Analytics)

### Configuration

```yaml
# dbt/profiles.yml
floe:
  outputs:
    snowflake:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
      database: ANALYTICS
      schema: GOLD
      warehouse: COMPUTE_WH
```

### Snowflake + Polaris Iceberg

```sql
-- Create catalog integration
CREATE CATALOG INTEGRATION polaris_int
    CATALOG_SOURCE = POLARIS
    TABLE_FORMAT = ICEBERG
    REST_CONFIG = (
        CATALOG_URI = 'https://polaris.example.com/api/catalog'
        CATALOG_NAME = 'demo_catalog'
    )
    REST_AUTHENTICATION = (
        TYPE = OAUTH
        OAUTH_CLIENT_ID = 'client_id'
        OAUTH_CLIENT_SECRET = 'client_secret'
        OAUTH_ALLOWED_SCOPES = ('PRINCIPAL_ROLE:ALL')
    );

-- Query Polaris-managed Iceberg tables
SELECT * FROM gold.metrics;
```

### Dagster Integration

```python
from dagster_snowflake import SnowflakeResource

@asset(kinds={"snowflake"})
def snowflake_analytics(snowflake: SnowflakeResource):
    with snowflake.get_connection() as conn:
        conn.cursor().execute("""
            CREATE OR REPLACE TABLE gold.dashboard_metrics AS
            SELECT * FROM gold.metrics
            WHERE date > CURRENT_DATE - 30
        """)
```

## Environment-Based Target Selection

### Pattern: Resource Factory

```python
import os
from dagster import Definitions, EnvVar

def get_compute_resources() -> dict:
    env = os.getenv("DAGSTER_DEPLOYMENT", "local")

    if env == "local":
        return {
            "dbt": DbtCliResource(
                project_dir=dbt_project,
                target="dev",  # DuckDB
            ),
        }
    elif env == "production":
        return {
            "dbt": DbtCliResource(
                project_dir=dbt_project,
                target="spark",  # Spark for large jobs
            ),
        }

defs = Definitions(
    assets=[...],
    resources=get_compute_resources(),
)
```

### Pattern: Asset-Level Target Override

```python
@asset(
    op_tags={"dagster/compute_kind": "spark"},
    metadata={"compute_target": "spark"},
)
def large_scale_aggregation():
    """Force Spark execution regardless of default."""
    ...
```

## Testing Compute Targets

### Local Testing (DuckDB)

```python
def test_transformation_logic():
    # DuckDB provides instant feedback
    import duckdb
    conn = duckdb.connect()
    result = conn.execute("""
        WITH test_data AS (SELECT 1 as id)
        -- Paste dbt model SQL here
        SELECT * FROM test_data
    """).fetchdf()
    assert len(result) == 1
```

### Integration Testing (Target-Specific)

```python
import pytest

@pytest.fixture
def spark_session():
    """Fixture for Spark integration tests."""
    # Use local Spark for CI
    return SparkSession.builder.master("local[2]").getOrCreate()

@pytest.fixture
def duckdb_conn():
    """Fixture for DuckDB tests."""
    return duckdb.connect(":memory:")
```

## Performance Comparison

| Operation | DuckDB | Spark | Snowflake |
|-----------|--------|-------|-----------|
| Startup | <1s | 30-60s | N/A (serverless) |
| 1M row scan | <1s | 5-10s | 2-5s |
| 100M row join | 10-30s | 30-60s | 15-30s |
| 1B row agg | OOM | 5-15min | 3-10min |
| Concurrency | 1 | High | Very High |
| Cost | Free | Compute | Per-query |

## Migration Patterns

### DuckDB → Spark (Scale Out)

```python
# Same dbt model, different target
# models/gold/metrics.sql stays unchanged

# Just switch profile target
dbt run --target spark --select gold.metrics
```

### Spark → Snowflake (Analytics)

```sql
-- Create external table pointing to same Iceberg
CREATE OR REPLACE ICEBERG TABLE gold.metrics
    EXTERNAL_VOLUME = 'iceberg_vol'
    CATALOG = 'polaris_catalog';

-- Query existing data immediately
SELECT * FROM gold.metrics;
```

## Best Practices

1. **Default to DuckDB** - Free, fast, covers 90% of use cases
2. **Scale to Spark** - When data exceeds DuckDB memory limits
3. **Use Snowflake for BI** - Optimised for concurrent analytics
4. **Same SQL everywhere** - dbt abstracts compute differences
5. **Test locally first** - DuckDB catches errors instantly
6. **Profile before scaling** - Often DuckDB is fast enough

---

**Reference**: dbt adapter docs: https://docs.getdbt.com/docs/supported-data-platforms
