# Plugin Integration Patterns

This document describes integration patterns between plugins.

## Compute-Catalog Integration

Some compute engines require explicit SQL statements to connect to the Iceberg catalog before dbt models can execute. The `get_catalog_attachment_sql()` method handles this.

### DuckDB Catalog Integration Example

DuckDB v1.4+ has native Iceberg REST catalog support. The DuckDB plugin generates ATTACH statements that connect to Polaris before model execution:

```python
# floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
from floe_core.interfaces.compute import ComputePlugin, ComputeConfig
from floe_core.interfaces.catalog import CatalogConfig

class DuckDBComputePlugin(ComputePlugin):
    name = "duckdb"
    version = "1.0.0"
    is_self_hosted = True

    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        return {
            "type": "duckdb",
            "path": config.properties.get("path", "/data/floe.duckdb"),
            "extensions": ["iceberg", "httpfs"],
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-duckdb>=1.9.0"]

    def get_catalog_attachment_sql(
        self, catalog_config: CatalogConfig
    ) -> list[str]:
        """Generate DuckDB SQL to attach to Polaris Iceberg catalog.

        These statements are added as dbt on-run-start hooks.
        DuckDB will use the catalog for all table operations.
        """
        return [
            "LOAD iceberg;",
            """CREATE SECRET IF NOT EXISTS polaris_secret (
                TYPE iceberg,
                CLIENT_ID '{{ env_var("POLARIS_CLIENT_ID") }}',
                CLIENT_SECRET '{{ env_var("POLARIS_CLIENT_SECRET") }}'
            );""",
            f"""ATTACH IF NOT EXISTS '{catalog_config.warehouse}' AS ice (
                TYPE iceberg,
                ENDPOINT '{{{{ env_var("POLARIS_URI") }}}}'
            );"""
        ]

    # ... other methods
```

The floe-dbt package uses these statements to generate dbt project configuration:

```yaml
# Generated dbt_project.yml
on-run-start:
  - "LOAD iceberg;"
  - "CREATE SECRET IF NOT EXISTS polaris_secret (...)"
  - "ATTACH IF NOT EXISTS '...' AS ice (TYPE iceberg, ...)"
```

Models then write directly to the attached Iceberg catalog:

```sql
-- models/gold/customers.sql
{{ config(materialized='iceberg_table') }}

SELECT * FROM {{ ref('silver_customers') }}
-- Creates table: ice.gold.customers
```

## Related Documents

- [Plugin Architecture Overview](index.md)
- [Plugin Interfaces](interfaces.md)
- [Configuration and CLI](configuration.md)
