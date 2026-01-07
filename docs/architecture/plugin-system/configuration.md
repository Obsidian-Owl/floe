# Plugin Configuration and CLI

This document describes plugin CLI commands and how to create custom plugins.

## Plugin CLI Commands

```bash
# List installed plugins
floe plugins list

# Output:
Installed plugins:
  orchestrators:
    - dagster (1.0.0) [default]
    - airflow (1.0.0)
  computes:
    - duckdb (1.0.0) [default]
    - snowflake (1.0.0)
    - spark (1.0.0)
  catalogs:
    - polaris (1.0.0) [default]
    - glue (1.0.0)
  dbt:
    - local (1.0.0) [default]
    - fusion (1.0.0)
  semantic_layers:
    - cube (1.0.0) [default]
    - none (1.0.0)
  ingestion:
    - dlt (1.0.0) [default]
    - airbyte (1.0.0)

# List available (installable) plugins
floe plugins available
```

## Creating a Custom Plugin

### 1. Create Package Structure

```bash
mkdir floe-compute-trino
cd floe-compute-trino
```

### 2. Implement Interface

```python
# src/floe_compute_trino/plugin.py
from floe_core.interfaces.compute import ComputePlugin, ComputeConfig

class TrinoComputePlugin(ComputePlugin):
    name = "trino"
    version = "1.0.0"
    is_self_hosted = True

    metadata = PluginMetadata(
        name="trino",
        version="1.0.0",
        floe_api_version="1.0",
        description="Trino compute plugin for floe",
        author="Your Name",
    )

    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        return {
            "type": "trino",
            "method": "none",
            "host": config.properties.get("host", "trino.default.svc.cluster.local"),
            "port": config.properties.get("port", 8080),
            "catalog": config.properties.get("catalog", "iceberg"),
            "schema": config.properties.get("schema", "default"),
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-trino>=1.7.0"]

    # ... implement other methods
```

### 3. Register Entry Point

```toml
# pyproject.toml
[project.entry-points."floe.computes"]
trino = "floe_compute_trino:TrinoComputePlugin"
```

### 4. Add Helm Chart (if needed)

```yaml
# chart/Chart.yaml
apiVersion: v2
name: floe-compute-trino
version: 1.0.0
description: Trino compute for floe

# chart/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trino-coordinator
# ...
```

### 5. Install and Use

```bash
uv add floe-compute-trino

# platform-manifest.yaml
plugins:
  compute:
    type: trino
    config:
      host: trino.example.com
```

## Related Documents

- [Plugin Architecture Overview](index.md)
- [Plugin Interfaces](interfaces.md)
- [Integration Patterns](integration-patterns.md)
