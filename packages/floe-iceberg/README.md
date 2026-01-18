# floe-iceberg

IcebergTableManager utility for PyIceberg table operations in the floe data platform.

## Overview

`floe-iceberg` provides an internal utility class that wraps PyIceberg table operations,
offering a consistent API for table creation, schema evolution, writes, and snapshot management.

**Note**: IcebergTableManager is NOT a plugin - Iceberg is enforced (ADR-0005), not pluggable.

## Installation

```bash
pip install floe-iceberg

# With Dagster IOManager support
pip install "floe-iceberg[dagster]"
```

## Quick Start

```python
from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
from floe_iceberg.models import TableConfig, WriteConfig, WriteMode

# Initialize with plugin dependencies
manager = IcebergTableManager(
    catalog_plugin=catalog_plugin,
    storage_plugin=storage_plugin,
    config=IcebergTableManagerConfig(max_commit_retries=3),
)

# Create a table
table = manager.create_table(table_config)

# Write data
snapshot = manager.write_data(table, data, WriteConfig(mode=WriteMode.APPEND))
```

See [quickstart.md](../../specs/4d-storage-plugin/quickstart.md) for detailed examples.

## License

Apache-2.0
