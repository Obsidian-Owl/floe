# IO Managers for Iceberg Storage

## Core Principle

**IO Managers abstract storage. ALL writes go through catalog.**

```
Asset Function → Return Data → IO Manager → Catalog API → Iceberg Tables
```

## dagster-iceberg IO Managers

### PyArrowIcebergIOManager (Primary)

```python
from dagster_iceberg.config import IcebergCatalogConfig
from dagster_iceberg.io_manager.arrow import PyArrowIcebergIOManager
import dagster as dg

@dg.asset
def my_table() -> pa.Table:
    """Returns PyArrow Table - IO manager handles storage."""
    return pa.table({"id": [1, 2, 3], "value": ["a", "b", "c"]})

io_manager = PyArrowIcebergIOManager(
    name="polaris_catalog",
    config=IcebergCatalogConfig(
        properties={
            "type": "rest",
            "uri": "http://polaris:8181/api/catalog",
            "credential": f"{client_id}:{client_secret}",
            "warehouse": "demo_catalog",
        }
    ),
    namespace="default",
)

defs = dg.Definitions(
    assets=[my_table],
    resources={"io_manager": io_manager},
)
```

### PandasIcebergIOManager

```python
from dagster_iceberg.io_manager.pandas import PandasIcebergIOManager
import pandas as pd

@dg.asset
def pandas_table() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

io_manager = PandasIcebergIOManager(
    name="catalog",
    config=IcebergCatalogConfig(properties={...}),
    namespace="analytics",
)
```

### SparkIcebergIOManager

```python
from dagster_iceberg.io_manager.spark import SparkIcebergIOManager

SPARK_CONFIG = {
    "spark.sql.catalog.polaris": "org.apache.iceberg.spark.SparkCatalog",
    "spark.sql.catalog.polaris.type": "rest",
    "spark.sql.catalog.polaris.uri": "http://polaris:8181/api/catalog",
}

io_manager = SparkIcebergIOManager(
    catalog_name="polaris",
    namespace="gold",
    spark_config=SPARK_CONFIG,
)
```

## Write Modes

### Append (Default)

```python
@dg.asset(metadata={"write_mode": "append"})
def incremental_data() -> pa.Table:
    """Appends new records to existing table."""
    return new_records
```

### Overwrite

```python
@dg.asset(metadata={"write_mode": "overwrite"})
def full_refresh() -> pa.Table:
    """Replaces all data in table."""
    return full_dataset
```

### Upsert (Merge)

```python
@dg.asset(
    metadata={
        "write_mode": "upsert",
        "upsert_key": ["id"],  # Merge key columns
    }
)
def scd_table() -> pa.Table:
    """Upserts based on key columns."""
    return updated_records
```

## Partitioned Assets

### Time-Based Partitioning

```python
from dagster import DailyPartitionsDefinition

daily_partitions = DailyPartitionsDefinition(start_date="2024-01-01")

@dg.asset(
    partitions_def=daily_partitions,
    metadata={"partition_expr": "date"},  # Partition column
)
def daily_events(context: dg.AssetExecutionContext) -> pa.Table:
    date = context.partition_key
    return fetch_events_for_date(date)
```

### Static Partitioning

```python
from dagster import StaticPartitionsDefinition

regions = StaticPartitionsDefinition(["us", "eu", "asia"])

@dg.asset(
    partitions_def=regions,
    metadata={"partition_expr": "region"},
)
def regional_data(context) -> pa.Table:
    region = context.partition_key
    return fetch_data_for_region(region)
```

## Custom IO Managers

### Base Implementation

```python
from dagster import IOManager, InputContext, OutputContext
from pyiceberg.catalog import load_catalog

class CustomIcebergIOManager(IOManager):
    def __init__(self, catalog_uri: str, warehouse: str, namespace: str):
        self.catalog = load_catalog(
            "rest",
            uri=catalog_uri,
            warehouse=warehouse,
        )
        self.namespace = namespace
    
    def handle_output(self, context: OutputContext, obj):
        """Write asset output to Iceberg."""
        table_name = f"{self.namespace}.{context.asset_key.path[-1]}"
        
        # Create or load table
        try:
            table = self.catalog.load_table(table_name)
        except:
            table = self.catalog.create_table(table_name, schema=infer_schema(obj))
        
        # Write via catalog (CRITICAL: never direct to storage)
        table.overwrite(obj)
        
        context.log.info(f"Wrote {len(obj)} rows to {table_name}")
    
    def load_input(self, context: InputContext):
        """Load upstream asset from Iceberg."""
        table_name = f"{self.namespace}.{context.asset_key.path[-1]}"
        table = self.catalog.load_table(table_name)
        return table.scan().to_arrow()
```

### Environment-Specific Factory

```python
import os
from dagster import IOManagerDefinition

def create_io_manager() -> IOManagerDefinition:
    env = os.getenv("DAGSTER_DEPLOYMENT", "local")
    
    if env == "local":
        return PyArrowIcebergIOManager(
            name="local_catalog",
            config=IcebergCatalogConfig(
                properties={
                    "type": "rest",
                    "uri": "http://localhost:8181/api/catalog",
                }
            ),
            namespace="default",
        )
    else:
        return PyArrowIcebergIOManager(
            name="prod_catalog",
            config=IcebergCatalogConfig(
                properties={
                    "type": "rest",
                    "uri": os.environ["POLARIS_URI"],
                    "credential": os.environ["POLARIS_CREDENTIAL"],
                }
            ),
            namespace="production",
        )
```

## Schema Management

### Asset-Specific Schemas

```python
@dg.asset(
    metadata={
        "schema_override": {
            "id": "int64",
            "name": "string",
            "amount": "decimal(18,2)",
        }
    }
)
def typed_table() -> pa.Table:
    return data
```

### Schema Evolution Handling

```python
@dg.asset(
    metadata={
        "schema_evolution": "permissive",  # Allow new columns
    }
)
def evolving_table() -> pa.Table:
    return data_with_new_columns
```

## Metadata and Properties

### Table Properties

```python
@dg.asset(
    metadata={
        "table_properties": {
            "write.format.default": "parquet",
            "write.parquet.compression-codec": "zstd",
            "history.expire.max-snapshot-age-ms": "604800000",  # 7 days
        }
    }
)
def configured_table() -> pa.Table:
    return data
```

### Runtime Metadata

```python
from dagster import Output, MetadataValue

@dg.asset
def table_with_metadata(context) -> Output[pa.Table]:
    data = compute_data()
    
    return Output(
        data,
        metadata={
            "row_count": MetadataValue.int(len(data)),
            "snapshot_id": MetadataValue.text(str(get_snapshot_id())),
        },
    )
```

## dbt + IO Manager Integration

**Note**: dbt assets don't typically use Dagster IO managers - dbt writes directly via adapter.

```python
# dbt writes via dbt-duckdb (with Iceberg ATTACH)
# IO manager is for pure Python assets

@dbt_assets(manifest=manifest_path)
def dbt_models(context, dbt: DbtCliResource):
    # dbt handles storage via profiles.yml
    yield from dbt.cli(["build"], context=context).stream()

@dg.asset(deps=[dbt_models])
def downstream_analysis() -> pa.Table:
    # This asset uses IO manager
    return analysis_result
```

## Troubleshooting

### "Schema mismatch" Error

```python
# Solution: Enable schema evolution
@dg.asset(metadata={"schema_evolution": "permissive"})
```

### "Table not found" on First Run

```python
# IO manager creates table automatically if doesn't exist
# Check namespace exists in catalog first
```

### Partition Column Not Found

```python
# Ensure partition_expr matches actual column name in data
@dg.asset(metadata={"partition_expr": "event_date"})  # Must exist
```

---

**Reference**: dagster-iceberg docs: https://docs.dagster.io/integrations/libraries/iceberg
