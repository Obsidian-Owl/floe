# Dagster API Reference

> **Version**: Dagster 1.x (2025)
> **Docs**: https://docs.dagster.io
> **Python**: 3.9 - 3.13

## Software-Defined Assets

### Basic Asset

```python
from dagster import asset

@asset
def my_table():
    return some_dataframe

@asset
def downstream_table(my_table):
    return transform(my_table)
```

### Multi-Asset

```python
from dagster import multi_asset, AssetOut

@multi_asset(
    outs={
        "table_a": AssetOut(),
        "table_b": AssetOut(),
    }
)
def compute_tables():
    return table_a, table_b
```

### Asset Configuration

```python
@asset(
    name="custom_name",
    key_prefix=["analytics"],
    group_name="marketing",
    compute_kind="python",
    description="My asset",
    metadata={"owner": "team@example.com"},
    deps=[upstream_asset],
    io_manager_key="iceberg_io",
    partitions_def=daily_partitions,
)
def configured_asset():
    return data
```

## Resources

### ConfigurableResource

```python
from dagster import ConfigurableResource

class DatabaseResource(ConfigurableResource):
    host: str
    port: int = 5432

    def query(self, sql: str):
        pass

@asset
def my_asset(database: DatabaseResource):
    return database.query("SELECT * FROM table")
```

### Environment Variables

```python
from dagster import EnvVar

class SecureResource(ConfigurableResource):
    api_key: str = EnvVar("API_KEY")
```

## IO Managers

```python
from dagster import IOManager, InputContext, OutputContext

class CustomIOManager(IOManager):
    def handle_output(self, context: OutputContext, obj):
        # Write
        pass

    def load_input(self, context: InputContext):
        # Read
        return data
```

## Schedules

```python
from dagster import schedule, RunRequest, ScheduleDefinition, define_asset_job

# Decorator
@schedule(cron_schedule="0 9 * * *", job=my_job)
def daily_schedule():
    return RunRequest()

# Definition
daily_job = define_asset_job("daily", selection=AssetSelection.all())
daily_schedule = ScheduleDefinition(job=daily_job, cron_schedule="0 0 * * *")
```

## Sensors

```python
from dagster import sensor, RunRequest, asset_sensor, AssetKey

@sensor(job=my_job)
def file_sensor(context):
    if file_exists():
        yield RunRequest()

@asset_sensor(asset_key=AssetKey("upstream"), job=downstream_job)
def asset_change_sensor(context):
    yield RunRequest()
```

## Partitions

```python
from dagster import (
    DailyPartitionsDefinition,
    MonthlyPartitionsDefinition,
    StaticPartitionsDefinition,
    MultiPartitionsDefinition,
)

daily = DailyPartitionsDefinition(start_date="2024-01-01")
monthly = MonthlyPartitionsDefinition(start_date="2024-01")
static = StaticPartitionsDefinition(["us", "eu", "asia"])
multi = MultiPartitionsDefinition({
    "date": daily,
    "region": static,
})

@asset(partitions_def=daily)
def partitioned_asset(context):
    date = context.partition_key
    return compute_for_date(date)
```

## Asset Selection

```python
from dagster import AssetSelection, define_asset_job

# By key
AssetSelection.keys("table_a", "table_b")

# By group
AssetSelection.groups("analytics")

# By prefix
AssetSelection.key_prefixes("raw")

# With graph traversal
AssetSelection.keys("table").upstream()
AssetSelection.keys("table").downstream()

# Create job
job = define_asset_job("my_job", selection=AssetSelection.groups("ml"))
```

## Definitions

```python
from dagster import Definitions

defs = Definitions(
    assets=[table_a, table_b],
    resources={
        "database": DatabaseResource(host="localhost"),
        "io_manager": MyIOManager(),
    },
    schedules=[daily_schedule],
    sensors=[file_sensor],
    jobs=[my_job],
)
```

## dbt Integration

```python
from dagster_dbt import DbtProject, DbtCliResource, dbt_assets

dbt_project = DbtProject(project_dir="./dbt")
dbt_project.prepare_if_dev()

@dbt_assets(manifest=dbt_project.manifest_path)
def my_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()

defs = Definitions(
    assets=[my_dbt_assets],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
```

## Testing

```python
from dagster import materialize

def test_asset():
    result = materialize([my_asset], resources={...})
    assert result.success
    output = result.output_for_node("my_asset")
```

## CLI Commands

```bash
dagster dev                    # Development server
dagster asset materialize      # Materialize assets
dagster asset list             # List assets
dagster job execute -j my_job  # Run job
```

## Metadata

```python
from dagster import Output, MetadataValue

@asset
def asset_with_metadata():
    df = compute()
    return Output(
        df,
        metadata={
            "row_count": MetadataValue.int(len(df)),
            "schema": MetadataValue.json(df.schema),
        },
    )
```

---

**Reference**: https://docs.dagster.io/api/python-api
