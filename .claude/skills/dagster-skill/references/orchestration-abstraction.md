# Orchestration Abstraction Patterns

## Design Principle

**Assets should be pure functions runnable in ANY orchestrator.**

```python
# ✅ GOOD: Pure function - orchestrator agnostic
def compute_metrics(orders_df, customers_df):
    return orders_df.join(customers_df).agg(...)

# ❌ BAD: Tightly coupled to Dagster
@asset
def metrics(context: AssetExecutionContext):
    context.log.info("Starting...")  # Dagster-specific
```

## Concept Mapping

| Dagster | Airflow | Prefect | Description |
|---------|---------|---------|-------------|
| `@asset` | `@task` | `@task` | Unit of work |
| Asset deps | `>>` operator | `.submit()` | Dependencies |
| `@schedule` | DAG schedule | Deployment schedule | Time triggers |
| `@sensor` | Sensor | Event handlers | Event triggers |
| `ConfigurableResource` | Connection/Variable | Block | External config |
| `Definitions` | DAG | Flow | Definition container |
| `materialize()` | `dag.run()` | `flow.run()` | Execution |
| Partition | Task params | Parameters | Data splitting |

## Abstraction Layer Implementation

### Core: Business Logic as Pure Functions

```python
# core/transforms.py - NO ORCHESTRATOR IMPORTS
import polars as pl

def calculate_customer_metrics(
    orders: pl.DataFrame,
    customers: pl.DataFrame,
) -> pl.DataFrame:
    """Pure function - testable, portable."""
    return (
        orders
        .join(customers, on="customer_id")
        .group_by("customer_id")
        .agg(
            pl.col("amount").sum().alias("total_spend"),
            pl.col("order_id").count().alias("order_count"),
        )
    )
```

### Dagster Implementation

```python
# orchestrators/dagster/assets.py
from dagster import asset
from core.transforms import calculate_customer_metrics

@asset
def customer_metrics(orders, customers):
    return calculate_customer_metrics(orders, customers)
```

### Airflow Implementation

```python
# orchestrators/airflow/dags/metrics_dag.py
from airflow.decorators import dag, task
from core.transforms import calculate_customer_metrics

@dag(schedule="@daily")
def metrics_pipeline():
    @task
    def compute_metrics(orders_path, customers_path):
        orders = pl.read_parquet(orders_path)
        customers = pl.read_parquet(customers_path)
        return calculate_customer_metrics(orders, customers)
    
    compute_metrics("s3://data/orders", "s3://data/customers")
```

### Prefect Implementation

```python
# orchestrators/prefect/flows/metrics_flow.py
from prefect import flow, task
from core.transforms import calculate_customer_metrics

@task
def load_data(path: str):
    return pl.read_parquet(path)

@flow
def metrics_flow():
    orders = load_data("s3://data/orders")
    customers = load_data("s3://data/customers")
    return calculate_customer_metrics(orders, customers)
```

## Resource Abstraction

### Interface Definition

```python
# core/resources.py
from abc import ABC, abstractmethod
from typing import Protocol

class CatalogClient(Protocol):
    """Protocol for catalog operations."""
    def load_table(self, name: str) -> "Table": ...
    def create_table(self, name: str, schema: "Schema") -> "Table": ...

class StorageClient(Protocol):
    """Protocol for storage operations."""
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> None: ...
```

### Dagster Implementation

```python
# orchestrators/dagster/resources.py
from dagster import ConfigurableResource
from core.resources import CatalogClient

class DagsterCatalogResource(ConfigurableResource, CatalogClient):
    uri: str
    warehouse: str
    
    def load_table(self, name: str):
        from pyiceberg.catalog import load_catalog
        catalog = load_catalog("rest", uri=self.uri, warehouse=self.warehouse)
        return catalog.load_table(name)
```

### Airflow Implementation

```python
# orchestrators/airflow/hooks/catalog_hook.py
from airflow.hooks.base import BaseHook
from core.resources import CatalogClient

class CatalogHook(BaseHook, CatalogClient):
    conn_name_attr = "catalog_conn_id"
    
    def load_table(self, name: str):
        conn = self.get_connection(self.catalog_conn_id)
        from pyiceberg.catalog import load_catalog
        return load_catalog("rest", uri=conn.host).load_table(name)
```

## dbt Integration Abstraction

### Dagster (dagster-dbt)

```python
from dagster_dbt import dbt_assets, DbtCliResource

@dbt_assets(manifest=manifest_path)
def dbt_models(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
```

### Airflow (cosmos)

```python
from cosmos import DbtDag, ProjectConfig

dbt_dag = DbtDag(
    project_config=ProjectConfig("path/to/dbt"),
    schedule="@daily",
    dag_id="dbt_pipeline",
)
```

### Prefect (prefect-dbt)

```python
from prefect import flow
from prefect_dbt import DbtCoreOperation

@flow
def dbt_flow():
    DbtCoreOperation(
        commands=["dbt build"],
        project_dir="path/to/dbt",
    ).run()
```

## Testing Strategy

### Unit Tests (Orchestrator-Agnostic)

```python
# tests/test_transforms.py
import polars as pl
from core.transforms import calculate_customer_metrics

def test_customer_metrics():
    orders = pl.DataFrame({"customer_id": [1], "amount": [100]})
    customers = pl.DataFrame({"customer_id": [1], "name": ["Alice"]})
    
    result = calculate_customer_metrics(orders, customers)
    
    assert result["total_spend"][0] == 100
```

### Integration Tests (Orchestrator-Specific)

```python
# tests/integration/test_dagster.py
from dagster import materialize
from orchestrators.dagster.assets import customer_metrics

def test_dagster_asset():
    result = materialize([customer_metrics], resources={...})
    assert result.success
```

## Migration Patterns

### Dagster → Airflow

```python
# Step 1: Extract business logic
def process_data(input_path: str) -> str:
    # Move logic here
    return output_path

# Step 2: Wrap in Airflow task
@task
def process_task(input_path: str):
    return process_data(input_path)
```

### Airflow → Dagster

```python
# Step 1: Identify task dependencies
# task_a >> task_b >> task_c

# Step 2: Convert to assets
@asset
def asset_a(): ...

@asset
def asset_b(asset_a): ...

@asset
def asset_c(asset_b): ...
```

## Best Practices

1. **Pure functions first** - Business logic with no orchestrator deps
2. **Protocol interfaces** - Define contracts for external resources
3. **Thin orchestrator layer** - Just wiring, no business logic
4. **Shared test fixtures** - Same test data across orchestrators
5. **Configuration abstraction** - Environment variables, not hardcoded

---

**Reference**: Patterns inspired by Clean Architecture principles applied to data engineering.
