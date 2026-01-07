# ADR-0032: Semantic Layer Compute Plugin Integration

## Status

Accepted

## Context

The semantic layer (Cube) needs to query data from Iceberg tables via a compute engine. However, Cube does not have a native Iceberg connector. This creates a design question:

1. **Direct Database Connections**: Cube maintains its own database connections
2. **Compute Plugin Delegation**: Cube delegates to the active compute plugin

### Problem with Direct Connections

If Cube maintains its own database connections:

- **Configuration duplication**: Separate credentials and connection config
- **Inconsistent compute**: Different engine than transformations
- **Broken plugin model**: Semantic layer bypasses compute abstraction
- **Extra infrastructure**: May require additional query engine (Trino)

### Requirements

- **Unified compute**: Same engine for transforms and semantic queries
- **Plugin consistency**: Follow established plugin architecture
- **DuckDB-first**: Default compute engine should work with semantic layer
- **Extensible**: Support Snowflake, Databricks, Trino as compute plugins are added

## Decision

The SemanticLayerPlugin delegates database connections to the active ComputePlugin. The semantic layer generates Cube configuration based on the compute plugin's connection details.

### Key Principles

1. **Compute plugin owns connections**: All database access through ComputePlugin
2. **Semantic layer generates schema**: Cube schema from dbt manifest + compute config
3. **DuckDB-first**: Default compute works out of the box
4. **Plugin interface extension**: Add `get_cube_datasource_config()` to ComputePlugin

## Consequences

### Positive

- **Unified compute**: Same engine for all data access
- **No extra infrastructure**: No separate Trino cluster for semantic layer
- **Consistent credentials**: Secrets managed in one place
- **Plugin architecture**: Clean separation of concerns
- **DuckDB-first**: Works with default open-source stack

### Negative

- **Compute coupling**: Semantic layer depends on compute plugin
- **Limited Cube features**: Some Cube-specific optimizations may not apply
- **Query routing**: All queries go through single compute engine

### Neutral

- Cube Store still provides caching layer
- Future: Add dedicated Trino plugin for high-concurrency semantic queries

---

## Architecture

### Compute Plugin Delegation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SEMANTIC LAYER ARCHITECTURE                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Cube Semantic Layer                           │    │
│  │                                                                      │    │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │    │
│  │  │ Data Model     │  │ Security       │  │ Caching               │ │    │
│  │  │ (from dbt)     │  │ (row-level)    │  │ (Cube Store)          │ │    │
│  │  └───────┬────────┘  └───────┬────────┘  └───────────┬────────────┘ │    │
│  │          │                   │                       │              │    │
│  │          └───────────────────┴───────────────────────┘              │    │
│  │                              │                                      │    │
│  │                              ▼                                      │    │
│  │                    ┌───────────────────┐                            │    │
│  │                    │ Query Execution   │                            │    │
│  │                    │ (via Compute)     │                            │    │
│  │                    └─────────┬─────────┘                            │    │
│  └──────────────────────────────┼──────────────────────────────────────┘    │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Compute Plugin                                │    │
│  │                                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │    │
│  │  │   DuckDB    │  │  Snowflake  │  │   Spark     │  │   Trino    │  │    │
│  │  │  (default)  │  │  (plugin)   │  │  (plugin)   │  │ (future)   │  │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘  │    │
│  │         │                │                │               │         │    │
│  └─────────┼────────────────┼────────────────┼───────────────┼─────────┘    │
│            │                │                │               │              │
│            ▼                ▼                ▼               ▼              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Iceberg Catalog (Polaris)                       │    │
│  │                                                                      │    │
│  │     gold.customers    gold.orders    silver.events    ...           │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation

### ComputePlugin Interface Extension

```python
# floe_core/interfaces/compute.py
from abc import ABC, abstractmethod
from typing import Optional

class ComputePlugin(ABC):
    """Interface for compute targets (DuckDB, Snowflake, Spark, etc.)."""

    name: str
    version: str

    @abstractmethod
    def generate_dbt_profile(self) -> dict:
        """Generate dbt profile configuration."""
        pass

    @abstractmethod
    def get_connection_string(self) -> str:
        """Get connection string for programmatic access."""
        pass

    @abstractmethod
    def get_cube_datasource_config(self) -> dict:
        """Generate Cube datasource configuration.

        Returns:
            Dict with Cube-specific database driver config.
            Keys depend on database type (duckdb, snowflake, postgres, etc.)
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate compute target is reachable."""
        pass
```

### DuckDB Compute Plugin

```python
# plugins/floe-compute-duckdb/plugin.py
class DuckDBComputePlugin(ComputePlugin):
    """DuckDB compute plugin with Cube integration."""

    name = "duckdb"
    version = "1.0.0"

    def __init__(self, database_path: str = ":memory:", catalog_config: dict = None):
        self.database_path = database_path
        self.catalog_config = catalog_config or {}

    def get_cube_datasource_config(self) -> dict:
        """Generate Cube configuration for DuckDB."""
        config = {
            "type": "duckdb",
            "database": self.database_path,
        }

        # If using Iceberg catalog, add attachment SQL
        if self.catalog_config:
            config["initSql"] = self._generate_catalog_attachment_sql()

        return config

    def _generate_catalog_attachment_sql(self) -> str:
        """Generate SQL to attach Iceberg catalog."""
        endpoint = self.catalog_config.get("endpoint")
        return f"""
            LOAD iceberg;
            ATTACH 'ice' AS ice (
                TYPE ICEBERG,
                ENDPOINT '{endpoint}',
                ACCESS_DELEGATION_MODE 'vended_credentials'
            );
        """

    def get_connection_string(self) -> str:
        return f"duckdb:///{self.database_path}"
```

### Snowflake Compute Plugin

```python
# plugins/floe-compute-snowflake/plugin.py
class SnowflakeComputePlugin(ComputePlugin):
    """Snowflake compute plugin with Cube integration."""

    name = "snowflake"
    version = "1.0.0"

    def __init__(
        self,
        account: str,
        warehouse: str,
        database: str,
        schema: str,
        user: str = None,
        private_key_path: str = None,
    ):
        self.account = account
        self.warehouse = warehouse
        self.database = database
        self.schema = schema
        self.user = user
        self.private_key_path = private_key_path

    def get_cube_datasource_config(self) -> dict:
        """Generate Cube configuration for Snowflake."""
        return {
            "type": "snowflake",
            "account": self.account,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
            "username": "{{ env_var('SNOWFLAKE_USER') }}",
            "password": "{{ env_var('SNOWFLAKE_PASSWORD') }}",
        }

    def get_connection_string(self) -> str:
        return f"snowflake://{self.account}/{self.database}/{self.schema}?warehouse={self.warehouse}"
```

### SemanticLayerPlugin Interface

```python
# floe_core/interfaces/semantic_layer.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from floe_core.interfaces.compute import ComputePlugin

class SemanticLayerPlugin(ABC):
    """Interface for semantic layer (Cube, etc.)."""

    name: str
    version: str

    @abstractmethod
    def generate_config(self, compute_plugin: "ComputePlugin") -> dict:
        """Generate semantic layer configuration.

        Args:
            compute_plugin: Active compute plugin for datasource config

        Returns:
            Complete semantic layer configuration
        """
        pass

    @abstractmethod
    def sync_from_dbt_manifest(self, manifest_path: str) -> list[dict]:
        """Generate semantic layer models from dbt manifest.

        Args:
            manifest_path: Path to dbt manifest.json

        Returns:
            List of semantic layer model definitions
        """
        pass

    @abstractmethod
    def get_security_context(self, user_context: dict) -> dict:
        """Generate security context for row-level security.

        Args:
            user_context: User attributes for RLS

        Returns:
            Security context for query filtering
        """
        pass
```

### Cube Semantic Layer Plugin

```python
# plugins/floe-semantic-cube/plugin.py
import json
import yaml
from pathlib import Path

class CubeSemanticLayerPlugin(SemanticLayerPlugin):
    """Cube semantic layer with compute plugin integration."""

    name = "cube"
    version = "1.0.0"

    def generate_config(self, compute_plugin: ComputePlugin) -> dict:
        """Generate Cube configuration from compute plugin."""
        datasource_config = compute_plugin.get_cube_datasource_config()

        return {
            "contextToAppId": "{{ securityContext.tenant_id }}",
            "scheduledRefreshContexts": self._get_refresh_contexts(),
            "driverFactory": self._get_driver_factory(datasource_config),
        }

    def _get_driver_factory(self, datasource_config: dict) -> dict:
        """Generate Cube driver factory configuration."""
        db_type = datasource_config.get("type", "duckdb")

        if db_type == "duckdb":
            return {
                "type": "duckdb",
                "database": datasource_config.get("database", ":memory:"),
                "initSql": datasource_config.get("initSql"),
            }
        elif db_type == "snowflake":
            return {
                "type": "snowflake",
                "account": datasource_config["account"],
                "warehouse": datasource_config["warehouse"],
                "database": datasource_config["database"],
                "schema": datasource_config["schema"],
            }
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def sync_from_dbt_manifest(self, manifest_path: str) -> list[dict]:
        """Generate Cube models from dbt manifest."""
        with open(manifest_path) as f:
            manifest = json.load(f)

        cube_models = []
        for node_id, node in manifest.get("nodes", {}).items():
            if node["resource_type"] != "model":
                continue

            # Only expose gold layer models
            if not node["name"].startswith("gold_"):
                continue

            cube_model = self._dbt_node_to_cube(node)
            cube_models.append(cube_model)

        return cube_models

    def _dbt_node_to_cube(self, node: dict) -> dict:
        """Convert dbt node to Cube model."""
        columns = node.get("columns", {})

        dimensions = []
        measures = []

        for col_name, col_info in columns.items():
            col_type = col_info.get("data_type", "string").lower()

            if col_type in ("int", "integer", "bigint", "float", "double", "decimal"):
                # Numeric columns become measures
                measures.append({
                    "name": col_name,
                    "type": "sum",
                    "sql": col_name,
                })
            else:
                # Other columns become dimensions
                dim_type = "time" if "date" in col_type or "timestamp" in col_type else "string"
                dimensions.append({
                    "name": col_name,
                    "type": dim_type,
                    "sql": col_name,
                    "primaryKey": col_name == node.get("meta", {}).get("primary_key"),
                })

        return {
            "name": node["name"],
            "sql_table": f"{node['schema']}.{node['name']}",
            "dimensions": dimensions,
            "measures": measures,
        }

    def get_security_context(self, user_context: dict) -> dict:
        """Generate Cube security context for row-level security."""
        return {
            "tenant_id": user_context.get("tenant_id"),
            "user_id": user_context.get("user_id"),
            "roles": user_context.get("roles", []),
        }
```

---

## Configuration

### Platform Manifest

```yaml
# manifest.yaml
plugins:
  compute:
    type: duckdb  # or snowflake, spark
    config:
      database: ":memory:"
      catalog:
        type: polaris
        endpoint: http://polaris:8181/api/catalog

  semantic_layer:
    type: cube
    config:
      port: 4000
      # Datasource derived from compute plugin
      expose_layers:
        - gold  # Only expose gold layer to semantic queries
```

### Generated Cube Configuration

```javascript
// cube.js (generated by floe compile)
module.exports = {
  contextToAppId: ({ securityContext }) => securityContext.tenant_id,

  driverFactory: () => ({
    type: 'duckdb',
    database: ':memory:',
    initSql: `
      LOAD iceberg;
      ATTACH 'ice' AS ice (
        TYPE ICEBERG,
        ENDPOINT 'http://polaris:8181/api/catalog',
        ACCESS_DELEGATION_MODE 'vended_credentials'
      );
    `,
  }),

  scheduledRefreshContexts: async () => [
    { securityContext: { tenant_id: 'default' } },
  ],
};
```

### Generated Cube Schema

```yaml
# schema/gold_customers.yml (generated from dbt manifest)
cubes:
  - name: gold_customers
    sql_table: ice.gold.customers

    dimensions:
      - name: customer_id
        type: string
        sql: customer_id
        primary_key: true

      - name: customer_name
        type: string
        sql: customer_name

      - name: created_at
        type: time
        sql: created_at

    measures:
      - name: total_orders
        type: count
        sql: order_id

      - name: total_revenue
        type: sum
        sql: order_amount
```

---

## Implementation Priority

### Phase 1: MVP (DuckDB)

1. Add `get_cube_datasource_config()` to DuckDBComputePlugin
2. Implement basic Cube schema generation from dbt manifest
3. Generate Cube configuration with DuckDB driver
4. Test end-to-end: dbt model -> Iceberg -> Cube query

### Phase 2: Enhanced (Snowflake, Databricks)

1. Add `get_cube_datasource_config()` to SnowflakeComputePlugin
2. Add support for Snowflake Iceberg tables
3. Implement Databricks SQL compute plugin

### Phase 3: Future (Trino)

1. Create TrinoComputePlugin for high-concurrency workloads
2. Add Trino Helm chart to platform
3. Document Trino deployment for semantic layer optimization

---

## Testing

### Unit Tests

```python
def test_duckdb_cube_config():
    """Test DuckDB compute plugin generates valid Cube config."""
    plugin = DuckDBComputePlugin(
        database_path=":memory:",
        catalog_config={"endpoint": "http://polaris:8181"}
    )
    config = plugin.get_cube_datasource_config()

    assert config["type"] == "duckdb"
    assert "LOAD iceberg" in config["initSql"]
    assert "polaris:8181" in config["initSql"]

def test_snowflake_cube_config():
    """Test Snowflake compute plugin generates valid Cube config."""
    plugin = SnowflakeComputePlugin(
        account="xxx.us-east-1",
        warehouse="COMPUTE_WH",
        database="ANALYTICS",
        schema="GOLD",
    )
    config = plugin.get_cube_datasource_config()

    assert config["type"] == "snowflake"
    assert config["warehouse"] == "COMPUTE_WH"
```

### Integration Tests

```python
def test_cube_queries_iceberg_via_duckdb():
    """Test Cube can query Iceberg tables through DuckDB."""
    # Setup
    compute = DuckDBComputePlugin(catalog_config=polaris_config)
    semantic = CubeSemanticLayerPlugin()

    # Generate Cube config
    cube_config = semantic.generate_config(compute)

    # Execute query
    result = cube_client.query("SELECT count(*) FROM gold_customers")
    assert result["data"][0]["count"] > 0
```

---

## References

- [Cube Documentation](https://cube.dev/docs/)
- [Cube DuckDB Driver](https://cube.dev/docs/product/configuration/data-sources/duckdb)
- [Cube Snowflake Driver](https://cube.dev/docs/product/configuration/data-sources/snowflake)
- [ADR-0001: Cube Semantic Layer](0001-cube-semantic-layer.md) - Original Cube decision
- [ADR-0010: Target-Agnostic Compute](0010-target-agnostic-compute.md) - Compute abstraction
- [Interfaces: ComputePlugin](../interfaces/compute-plugin.md) - Plugin interface
