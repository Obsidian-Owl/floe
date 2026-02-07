# Quickstart: DltIngestionPlugin (Epic 4F)

**Time to First Ingestion**: 5 minutes (with prerequisites)

## Prerequisites

1. **Catalog Plugin configured** (Epic 4C - Polaris REST catalog)
2. **Storage Plugin configured** (Epic 4D - Iceberg via MinIO/S3)
3. **Python 3.11+** with floe packages installed
4. **dlt source package** for your data source (e.g., `dlt[rest_api]`)

## Installation

```bash
# Install the dlt ingestion plugin
pip install floe-ingestion-dlt

# Install dlt with Iceberg destination support
pip install "dlt[iceberg]"

# Install source-specific packages
pip install "dlt[rest_api]"      # For REST API sources
pip install "dlt[sql_database]"  # For SQL database sources
pip install "dlt[filesystem]"    # For file sources (S3/GCS)
```

## Quick Start: Ingest Data from REST API

### Step 1: Configure the Plugin

```python
from floe_ingestion_dlt import DltIngestionPlugin, DltIngestionConfig
from floe_ingestion_dlt.config import IngestionSourceConfig

# Define ingestion config
config = DltIngestionConfig(
    sources=[
        IngestionSourceConfig(
            name="github_issues",
            source_type="rest_api",
            source_config={
                "base_url": "https://api.github.com",
                "resources": ["repos/myorg/myrepo/issues"],
            },
            destination_table="bronze.github_issues",
            write_mode="append",
            schema_contract="evolve",
            cursor_field="updated_at",
        ),
    ],
    catalog_config={
        "uri": "http://polaris:8181/api/catalog",
        "warehouse": "floe_warehouse",
    },
)
```

### Step 2: Create and Run Plugin

```python
from floe_core.plugins.ingestion import IngestionConfig

# Initialize plugin
plugin = DltIngestionPlugin(config=config)
plugin.startup()

# Create pipeline for a source
ingestion_config = IngestionConfig(
    source_type="rest_api",
    source_config={
        "base_url": "https://api.github.com",
        "resources": ["repos/myorg/myrepo/issues"],
    },
    destination_table="bronze.github_issues",
    write_mode="append",
    schema_contract="evolve",
)

pipeline = plugin.create_pipeline(ingestion_config)

# Run pipeline
result = plugin.run(pipeline)

print(f"Success: {result.success}")
print(f"Rows loaded: {result.rows_loaded}")
print(f"Duration: {result.duration_seconds:.2f}s")

# Cleanup
plugin.shutdown()
```

### Step 3: Verify Data in Iceberg

```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog("polaris", type="rest", uri="http://polaris:8181/api/catalog")
table = catalog.load_table("bronze.github_issues")

# Scan to verify data landed
arrow_table = table.scan().to_arrow()
print(f"Total rows: {arrow_table.num_rows}")
print(f"Columns: {arrow_table.column_names}")
```

## Common Operations

### Incremental Loading

```python
# First run loads all data
result_1 = plugin.run(pipeline)
print(f"Initial load: {result_1.rows_loaded} rows")

# Second run loads only new/updated records
result_2 = plugin.run(pipeline)
print(f"Incremental: {result_2.rows_loaded} rows")  # Only new rows
```

### Write Modes

```python
# Append (default) - additive loading
config_append = IngestionConfig(
    source_type="rest_api",
    source_config={...},
    destination_table="bronze.events",
    write_mode="append",
)

# Replace - full refresh
config_replace = IngestionConfig(
    source_type="sql_database",
    source_config={"connection_string": "..."},
    destination_table="bronze.dim_products",
    write_mode="replace",
)

# Merge - upsert with primary key
config_merge = IngestionConfig(
    source_type="rest_api",
    source_config={...},
    destination_table="bronze.customers",
    write_mode="merge",
)
```

### Schema Contracts

```python
# Evolve (default) - automatically add new columns
config_evolve = IngestionConfig(
    source_type="rest_api",
    source_config={...},
    destination_table="bronze.flexible_source",
    schema_contract="evolve",
)

# Freeze - reject schema changes
config_freeze = IngestionConfig(
    source_type="rest_api",
    source_config={...},
    destination_table="bronze.stable_source",
    schema_contract="freeze",
)

# Discard - drop non-conforming values
config_discard = IngestionConfig(
    source_type="rest_api",
    source_config={...},
    destination_table="bronze.filtered_source",
    schema_contract="discard_value",
)
```

### Error Handling

```python
from floe_ingestion_dlt.errors import (
    IngestionError,
    SourceConnectionError,
    DestinationWriteError,
    SchemaContractViolation,
)

try:
    pipeline = plugin.create_pipeline(config)
    result = plugin.run(pipeline)
except SourceConnectionError as e:
    print(f"Source unreachable: {e} (type={e.source_type})")
except SchemaContractViolation as e:
    print(f"Schema change rejected: {e}")
except DestinationWriteError as e:
    print(f"Iceberg write failed: {e}")
except IngestionError as e:
    print(f"Ingestion error ({e.category}): {e}")
```

### Custom Retry Configuration

```python
from floe_ingestion_dlt.config import RetryConfig

config = DltIngestionConfig(
    sources=[...],
    catalog_config={...},
    retry_config=RetryConfig(
        max_retries=5,           # More retries for flaky APIs
        initial_delay_seconds=2.0,  # Longer initial backoff
    ),
)
```

## Orchestrator Integration

The ingestion plugin is orchestrator-agnostic. Orchestrator wiring lives in the orchestrator plugin. For Dagster:

```python
# This happens automatically in the Dagster orchestrator plugin.
# Each source becomes a Dagster asset:
#   ingestion__github_issues__issues
#   ingestion__salesforce__contacts
#
# Configured via CompiledArtifacts.plugins.ingestion:
#   PluginRef(type="dlt", version="0.1.0", config={...})
```

## Health Check

```python
status = plugin.health_check()
print(f"State: {status.state}")  # HEALTHY or UNHEALTHY
print(f"Message: {status.message}")
```

## Troubleshooting

### ImportError: dlt source package not installed

**Symptom**: `startup()` raises ImportError

**Solution**: Install the required dlt source package:
```bash
pip install "dlt[rest_api]"      # For REST API sources
pip install "dlt[sql_database]"  # For SQL databases
pip install "dlt[filesystem]"    # For file sources
```

### SourceConnectionError

**Symptom**: `create_pipeline()` fails with source unreachable

**Solution**:
1. Verify source credentials in environment variables
2. Check network connectivity to the source
3. Verify API endpoint URL in `source_config`

### SchemaContractViolation

**Symptom**: `run()` fails with schema change rejected

**Solution**:
1. If using `freeze` contract, update Iceberg table schema first
2. Switch to `evolve` contract for flexible sources
3. Use `discard_value` to silently drop non-conforming values

### DestinationWriteError

**Symptom**: `run()` fails writing to Iceberg

**Solution**:
1. Verify Polaris catalog is reachable: `curl http://polaris:8181/api/catalog/v1/config`
2. Verify MinIO/S3 storage is accessible
3. Check namespace exists in Polaris catalog
4. Verify write permissions

### Rate Limiting

**Symptom**: Pipeline fails with 429 errors

**Solution**: dlt handles rate limiting automatically for supported sources. If still failing:
1. Increase `retry_config.max_retries`
2. Increase `retry_config.initial_delay_seconds`
3. Configure source-specific rate limits in `source_config`

## Next Steps

1. **Configure in floe.yaml**: Define ingestion sources in your floe manifest
2. **Set up orchestrator**: Let the orchestrator plugin create execution units automatically
3. **Monitor with OTel**: Ingestion spans appear in your observability backend
4. **Add more sources**: Each source in `sources[]` becomes an independent execution unit
5. **Epic 4G**: Reverse ETL (SinkConnector) will add egress capabilities to this plugin
