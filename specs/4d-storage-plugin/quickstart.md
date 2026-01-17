# Quickstart: IcebergTableManager (Epic 4D)

**Time to First Table**: 5 minutes (with prerequisites)

## Prerequisites

1. **Catalog Plugin configured** (Epic 4C - Polaris recommended)
2. **Storage Plugin configured** (S3/GCS/MinIO)
3. **Python 3.10+** with floe packages installed

## Installation

```bash
# Install floe-iceberg package
pip install floe-iceberg

# Or with all dependencies
pip install "floe-iceberg[dagster]"  # Includes Dagster IOManager
```

## Quick Start: Create and Write to a Table

### Step 1: Initialize IcebergTableManager

```python
from floe_core.plugin_registry import PluginRegistry, PluginType
from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig

# Get plugins from registry
registry = PluginRegistry()
catalog_plugin = registry.get(PluginType.CATALOG, "polaris")
storage_plugin = registry.get(PluginType.STORAGE, "s3")

# Initialize manager
manager = IcebergTableManager(
    catalog_plugin=catalog_plugin,
    storage_plugin=storage_plugin,
    config=IcebergTableManagerConfig(
        max_commit_retries=3,
        default_retention_days=7,
    ),
)
```

### Step 2: Define Table Schema

```python
from floe_iceberg.models import (
    TableConfig,
    TableSchema,
    SchemaField,
    FieldType,
    PartitionSpec,
    PartitionField,
    PartitionTransform,
)

# Define schema
schema = TableSchema(
    fields=[
        SchemaField(field_id=1, name="id", field_type=FieldType.LONG, required=True),
        SchemaField(field_id=2, name="name", field_type=FieldType.STRING),
        SchemaField(field_id=3, name="email", field_type=FieldType.STRING),
        SchemaField(field_id=4, name="created_at", field_type=FieldType.TIMESTAMP, required=True),
    ]
)

# Define partitioning (optional)
partition_spec = PartitionSpec(
    fields=[
        PartitionField(
            source_field_id=4,  # created_at
            partition_field_id=1000,
            name="created_day",
            transform=PartitionTransform.DAY,
        ),
    ]
)

# Create table config
config = TableConfig(
    namespace="bronze",
    table_name="customers",
    schema=schema,
    partition_spec=partition_spec,
)
```

### Step 3: Create Table

```python
# Create table (fails if exists)
table = manager.create_table(config)

# Or idempotent creation
table = manager.create_table(config, if_not_exists=True)

print(f"Created table: {config.identifier}")
```

### Step 4: Write Data

```python
import pyarrow as pa
from datetime import datetime
from floe_iceberg.models import WriteConfig, WriteMode, CommitStrategy

# Prepare data
data = pa.Table.from_pylist([
    {"id": 1, "name": "Alice", "email": "alice@example.com", "created_at": datetime.now()},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "created_at": datetime.now()},
])

# Write with default settings (append, fast commit)
snapshot = manager.write_data(
    table=table,
    data=data,
    config=WriteConfig(
        mode=WriteMode.APPEND,
        commit_strategy=CommitStrategy.FAST_APPEND,
        snapshot_properties={"source": "quickstart"},
    ),
)

print(f"Created snapshot {snapshot.snapshot_id} with {snapshot.added_records} records")
```

## Common Operations

### Read Table

```python
# Load existing table
table = manager.load_table("bronze.customers")

# Scan all data
arrow_table = table.scan().to_arrow()
print(f"Rows: {arrow_table.num_rows}")

# Scan with filter
filtered = table.scan(
    row_filter="name == 'Alice'"
).to_arrow()
```

### Overwrite Partition

```python
new_data = pa.Table.from_pylist([...])

snapshot = manager.write_data(
    table=table,
    data=new_data,
    config=WriteConfig(
        mode=WriteMode.OVERWRITE,
        overwrite_filter="created_day = '2026-01-17'",
    ),
)
```

### Evolve Schema

```python
from floe_iceberg.models import (
    SchemaEvolution,
    SchemaChange,
    SchemaChangeType,
)

evolution = SchemaEvolution(
    changes=[
        SchemaChange(
            change_type=SchemaChangeType.ADD_COLUMN,
            field=SchemaField(
                field_id=5,
                name="phone",
                field_type=FieldType.STRING,
                doc="Customer phone number",
            ),
        ),
        SchemaChange(
            change_type=SchemaChangeType.RENAME_COLUMN,
            old_name="name",
            new_name="full_name",
        ),
    ],
)

table = manager.evolve_schema(table, evolution)
```

### Time Travel

IcebergTableManager provides snapshot management; time-travel queries use PyIceberg's native scan API directly:

```python
# List snapshots via manager
snapshots = manager.list_snapshots(table)
for s in snapshots[:5]:
    print(f"{s.snapshot_id}: {s.operation} at {s.timestamp}")

# Query historical data at specific snapshot (PyIceberg native)
historical_data = table.scan(snapshot_id=snapshots[1].snapshot_id).to_arrow()

# Query by timestamp - find snapshot closest to target time
from datetime import datetime, timedelta
one_hour_ago = datetime.now() - timedelta(hours=1)
target_snapshot = next(
    (s for s in snapshots if s.timestamp <= one_hour_ago),
    snapshots[-1]  # Fallback to oldest if none match
)
data_at_time = table.scan(snapshot_id=target_snapshot.snapshot_id).to_arrow()

# Rollback to previous snapshot (creates new snapshot pointing to old state)
table = manager.rollback_to_snapshot(table, snapshots[1].snapshot_id)
```

**Note**: Time-travel queries (`table.scan(snapshot_id=...)`) are a PyIceberg feature used directly. IcebergTableManager provides `list_snapshots()` and `rollback_to_snapshot()` for snapshot management.

### Maintenance

```python
# Expire old snapshots (governance-aware)
expired = manager.expire_snapshots(table, older_than_days=7)
print(f"Expired {expired} snapshots")

# Compact small files
from floe_iceberg.models import CompactionStrategy, CompactionStrategyType

rewritten = manager.compact_table(
    table=table,
    strategy=CompactionStrategy(
        strategy_type=CompactionStrategyType.BIN_PACK,
        target_file_size_bytes=128 * 1024 * 1024,  # 128MB
    ),
)
print(f"Compacted {rewritten} files")
```

## Dagster Integration

### Configure IOManager

```python
from dagster import Definitions, asset
from floe_iceberg.io_manager import IcebergIOManager
from floe_iceberg.models import IcebergIOManagerConfig, WriteMode

@asset(io_manager_key="iceberg")
def customers_bronze() -> pa.Table:
    """Ingest raw customer data."""
    return pa.Table.from_pylist([...])

@asset(io_manager_key="iceberg")
def customers_silver(customers_bronze: pa.Table) -> pa.Table:
    """Transform customers."""
    return transform(customers_bronze)

defs = Definitions(
    assets=[customers_bronze, customers_silver],
    resources={
        "iceberg": IcebergIOManager(
            table_manager=manager,
            config=IcebergIOManagerConfig(
                namespace="bronze",
                default_write_mode=WriteMode.APPEND,
            ),
        ),
    },
)
```

### Partitioned Assets

```python
from dagster import DailyPartitionsDefinition

@asset(
    io_manager_key="iceberg",
    partitions_def=DailyPartitionsDefinition(start_date="2026-01-01"),
    metadata={
        "iceberg_write_mode": "overwrite",
        "iceberg_partition_column": "event_date",
    },
)
def daily_events(context) -> pa.Table:
    """Process events for a single day."""
    date = context.partition_key
    return fetch_and_transform(date)
```

## Troubleshooting

### CommitFailedException

**Symptom**: Write fails with concurrent modification error

**Solution**: IcebergTableManager retries automatically (default 3 times). If still failing:
1. Check for long-running transactions
2. Consider partitioning by writer ID
3. Increase `max_commit_retries`

### TableAlreadyExistsError

**Symptom**: `create_table()` fails because table exists

**Solution**: Use `if_not_exists=True` for idempotent creation:
```python
table = manager.create_table(config, if_not_exists=True)
```

### NoSuchNamespaceError

**Symptom**: Table creation fails - namespace not found

**Solution**: Create namespace first via CatalogPlugin:
```python
catalog_plugin.create_namespace("bronze", {"location": warehouse_uri})
```

### Schema Mismatch on Write

**Symptom**: `ValidationError` when writing data

**Solution**: Ensure PyArrow schema matches Iceberg schema:
```python
# Check table schema
print(table.schema())

# Evolve schema if needed
manager.evolve_schema(table, evolution)
```

## Next Steps

1. **Read the full API docs**: `specs/4d-storage-plugin/contracts/`
2. **Configure governance policies**: Epic 3A-3D for retention policies
3. **Set up monitoring**: OpenTelemetry spans are emitted automatically
4. **Explore time travel**: Query historical data for debugging
