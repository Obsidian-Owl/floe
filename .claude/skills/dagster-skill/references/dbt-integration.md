# dbt Integration with Dagster - Complete Reference

## Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DAGSTER ORCHESTRATION                     │
│  @dbt_assets → DbtCliResource → dbt CLI → manifest.json     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      dbt CORE                                │
│  profiles.yml → adapters (duckdb/snowflake/spark)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              CATALOG (Polaris/Glue/Unity)                   │
│  Iceberg REST API → metadata → storage locations            │
└─────────────────────────────────────────────────────────────┘
```

## DbtProject

```python
from pathlib import Path
from dagster_dbt import DbtProject

dbt_project = DbtProject(
    project_dir=Path("./dbt"),           # dbt project root
    profiles_dir=Path("./dbt"),          # profiles.yml location
    target="dev",                         # dbt target
    packaged_project_dir=Path("./dist"), # Production builds
    state_path=Path("./state"),          # Slim CI state
)

# Hot-reload manifest in development
dbt_project.prepare_if_dev()

# Access manifest
manifest_path = dbt_project.manifest_path
```

## DbtCliResource

```python
from dagster_dbt import DbtCliResource

dbt = DbtCliResource(
    project_dir=dbt_project,
    profiles_dir=dbt_project.project_dir,
    target="dev",
    global_config_flags=["--no-use-colors"],
)

# Commands
dbt.cli(["compile"], context=context).stream()
dbt.cli(["run", "--select", "tag:daily"], context=context).stream()
dbt.cli(["test"], context=context).stream()
dbt.cli(["build"], context=context).stream()  # run + test
```

## @dbt_assets Decorator

```python
from dagster import AssetExecutionContext
from dagster_dbt import dbt_assets, DbtCliResource

@dbt_assets(
    manifest=dbt_project.manifest_path,
    select="fqn:*",                    # dbt selection syntax
    exclude="tag:deprecated",          # Exclude patterns
    io_manager_key="iceberg_io",       # Custom IO manager
    partitions_def=daily_partitions,   # Partitioning
    dagster_dbt_translator=translator, # Custom translator
    project=dbt_project,               # Code references
)
def my_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
```

## DagsterDbtTranslator

### Complete Override Example

```python
from dagster import AssetKey
from dagster_dbt import DagsterDbtTranslator, DagsterDbtTranslatorSettings

class FloeDbTranslator(DagsterDbtTranslator):
    def __init__(self):
        super().__init__(
            settings=DagsterDbtTranslatorSettings(
                enable_code_references=True,
                enable_source_tests_as_checks=True,
            )
        )
    
    def get_asset_key(self, dbt_resource_props: dict) -> AssetKey:
        """Map dbt model to Dagster asset key."""
        return AssetKey([
            dbt_resource_props.get("schema", "public"),
            dbt_resource_props["name"],
        ])
    
    def get_group_name(self, dbt_resource_props: dict) -> str | None:
        """Group assets by dbt folder."""
        fqn = dbt_resource_props.get("fqn", [])
        return fqn[1] if len(fqn) > 2 else None
    
    def get_description(self, dbt_resource_props: dict) -> str | None:
        return dbt_resource_props.get("description")
    
    def get_metadata(self, dbt_resource_props: dict) -> dict:
        meta = dbt_resource_props.get("meta", {})
        return {
            "classification": meta.get("classification"),
            "owner": meta.get("owner"),
        }
    
    def get_tags(self, dbt_resource_props: dict) -> dict[str, str]:
        return {tag: "" for tag in dbt_resource_props.get("tags", [])}
    
    def get_owners(self, dbt_resource_props: dict) -> list[str]:
        meta = dbt_resource_props.get("meta", {})
        owner = meta.get("owner")
        return [owner] if owner else []
```

### dbt Resource Properties Available

```python
{
    "name": "my_model",
    "unique_id": "model.my_project.my_model",
    "fqn": ["my_project", "staging", "my_model"],
    "schema": "staging",
    "database": "analytics",
    "description": "Model description",
    "tags": ["daily", "critical"],
    "meta": {"owner": "team@example.com", "classification": "pii"},
    "config": {"materialized": "table", "unique_key": "id"},
    "columns": {...},
    "depends_on": {...},
    "resource_type": "model",  # or source, seed, snapshot
}
```

## Partitioned dbt Assets

### Daily Partitions with dbt vars

```python
from dagster import DailyPartitionsDefinition

daily_partitions = DailyPartitionsDefinition(start_date="2024-01-01")

@dbt_assets(
    manifest=dbt_project.manifest_path,
    partitions_def=daily_partitions,
    select="tag:incremental",
)
def incremental_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    partition_date = context.partition_key
    yield from dbt.cli(
        ["build", "--vars", f'{{"run_date": "{partition_date}"}}'],
        context=context,
    ).stream()
```

### dbt Incremental Model

```sql
-- models/marts/daily_orders.sql
{{ config(materialized='incremental', unique_key='order_id') }}

SELECT * FROM {{ ref('stg_orders') }}
{% if is_incremental() %}
WHERE order_date = '{{ var("run_date") }}'::date
{% endif %}
```

## dbt Selection Patterns

```python
from dagster import define_asset_job
from dagster_dbt import build_dbt_asset_selection

# By tag
staging_selection = build_dbt_asset_selection(
    [dbt_assets], dbt_select="tag:staging"
)

# By folder
marts_selection = build_dbt_asset_selection(
    [dbt_assets], dbt_select="path:models/marts"
)

# With downstream
critical_path = build_dbt_asset_selection(
    [dbt_assets],
    dbt_select="tag:critical+",  # + = downstream
    dbt_exclude="tag:deprecated",
)

# Include non-dbt assets
full_pipeline = staging_selection.downstream()

# Create job
staging_job = define_asset_job("staging_refresh", selection=staging_selection)
```

## Row Count Metadata

```python
@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_assets_with_row_counts(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from (
        dbt.cli(["build"], context=context)
        .stream()
        .fetch_row_counts()  # Adds row_count metadata
    )
```

## Slim CI with State

```python
dbt_project = DbtProject(
    project_dir=Path("./dbt"),
    state_path=Path("./artifacts/previous_run"),
)

@dbt_assets(manifest=dbt_project.manifest_path)
def modified_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(
        ["build", "--select", "state:modified+"],
        context=context,
    ).stream()
```

## dbt + Iceberg via dbt-duckdb

### profiles.yml

```yaml
floe:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: :memory:
      extensions:
        - iceberg
      plugins:
        - module: floe_dbt.plugins.polaris
          config:
            catalog_uri: "{{ env_var('POLARIS_URI') }}"
            warehouse: "demo_catalog"
```

### Plugin ATTACH (automatic)

```sql
-- Executed by plugin before dbt models run
ATTACH 'demo_catalog' AS polaris_catalog (
    TYPE ICEBERG,
    CLIENT_ID '${POLARIS_CLIENT_ID}',
    CLIENT_SECRET '${POLARIS_CLIENT_SECRET}',
    ENDPOINT '${POLARIS_URI}'
);
```

### dbt Model (writes via catalog)

```sql
-- models/gold/metrics.sql
{{ config(materialized='table', schema='gold') }}

SELECT customer_id, SUM(amount) as total
FROM {{ ref('silver_orders') }}
GROUP BY 1
```

## Upstream/Downstream Assets

### Python Asset Before dbt

```python
@asset(compute_kind="python")
def raw_customers(context: AssetExecutionContext) -> None:
    """Python asset that dbt sources reference."""
    data = fetch_from_api()
    write_to_catalog("raw.customers", data)

# In dbt sources.yml:
# sources:
#   - name: raw
#     tables:
#       - name: customers
```

### Python Asset After dbt

```python
@asset(deps=[my_dbt_assets])
def ml_features(context: AssetExecutionContext):
    """Downstream of dbt models."""
    df = read_from_catalog("gold.metrics")
    return compute_features(df)
```

## Testing

### Unit Test dbt Project

```python
def test_dbt_compiles():
    from dbt.cli.main import dbtRunner
    runner = dbtRunner()
    result = runner.invoke(["compile", "--project-dir", "dbt"])
    assert result.success

def test_dbt_assets_load():
    from dagster import materialize
    result = materialize([my_dbt_assets], resources={...})
    assert result.success
```

---

**References**:
- [dagster-dbt API](https://docs.dagster.io/_apidocs/libraries/dagster-dbt)
- [dbt Selection Syntax](https://docs.getdbt.com/reference/node-selection/syntax)
- [dbt-duckdb](https://github.com/duckdb/dbt-duckdb)
