# Quickstart: Dagster Orchestrator Plugin

## Prerequisites

- Python 3.10+
- floe-core installed
- Dagster 1.10+ (1.12 recommended)

## Installation

```bash
# Install the plugin
pip install floe-orchestrator-dagster

# Or from source (development)
cd plugins/floe-orchestrator-dagster
pip install -e ".[dev]"
```

## Configuration

### manifest.yaml

```yaml
# Platform configuration (Platform Team)
orchestrator: dagster  # Plugin selection
```

### floe.yaml

```yaml
# Data product configuration (Data Team)
name: my-data-product
version: 1.0.0

transforms:
  - name: stg_customers
    compute: duckdb  # Per-model compute selection
  - name: fct_orders
    compute: spark   # Heavy workload on Spark
```

## Basic Usage

### 1. Compile Data Product

```bash
floe compile --output target/compiled_artifacts.json
```

### 2. Generate Dagster Definitions

```python
from floe_orchestrator_dagster import DagsterOrchestratorPlugin
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

# Load compiled artifacts
artifacts = CompiledArtifacts.from_json_file("target/compiled_artifacts.json")

# Create plugin instance
plugin = DagsterOrchestratorPlugin()

# Generate Dagster definitions
definitions = plugin.create_definitions(artifacts.model_dump())
```

### 3. Run Dagster

```python
# definitions.py (for Dagster webserver)
from floe_orchestrator_dagster import DagsterOrchestratorPlugin
from floe_core.schemas.compiled_artifacts import CompiledArtifacts

artifacts = CompiledArtifacts.from_json_file("target/compiled_artifacts.json")
plugin = DagsterOrchestratorPlugin()

defs = plugin.create_definitions(artifacts.model_dump())
```

```bash
# Start Dagster webserver
dagster dev -f definitions.py
```

## Plugin Discovery

The plugin registers automatically via entry points:

```python
from importlib.metadata import entry_points

# Discover all orchestrator plugins
eps = entry_points(group="floe.orchestrators")
for ep in eps:
    print(f"{ep.name}: {ep.value}")
# Output: dagster: floe_orchestrator_dagster:DagsterOrchestratorPlugin
```

## Scheduling Jobs

```python
# Create a daily schedule at 8 AM Eastern
plugin.schedule_job(
    job_name="daily_refresh",
    cron="0 8 * * *",
    timezone="America/New_York"
)
```

## Resource Configuration

```python
# Get resource requirements for different workload sizes
small = plugin.get_resource_requirements("small")
medium = plugin.get_resource_requirements("medium")
large = plugin.get_resource_requirements("large")

print(f"Large: {large.cpu_request} CPU, {large.memory_request} memory")
```

## Helm Deployment

```python
# Get Helm values for floe-dagster chart
helm_values = plugin.get_helm_values()

# Write to values file
import yaml
with open("values-dagster.yaml", "w") as f:
    yaml.dump(helm_values, f)
```

```bash
# Deploy to K8s
helm install dagster charts/floe-dagster -f values-dagster.yaml
```

## Connection Validation

```python
# Validate Dagster connectivity
result = plugin.validate_connection()

if result.success:
    print("Connected to Dagster")
else:
    print(f"Connection failed: {result.message}")
    for error in result.errors:
        print(f"  - {error}")
```

## OpenLineage Events

```python
from floe_core.plugins.orchestrator import Dataset

# Emit lineage event when job completes
plugin.emit_lineage_event(
    event_type="COMPLETE",
    job="dbt_run_customers",
    inputs=[Dataset(namespace="floe", name="raw.customers")],
    outputs=[Dataset(namespace="floe", name="staging.stg_customers")]
)
```

## Testing

```bash
# Run unit tests
pytest plugins/floe-orchestrator-dagster/tests/unit/

# Run integration tests (requires K8s)
pytest plugins/floe-orchestrator-dagster/tests/integration/
```

## Troubleshooting

### Plugin Not Found

```python
# Check if plugin is installed
from importlib.metadata import entry_points
eps = list(entry_points(group="floe.orchestrators"))
print(f"Found {len(eps)} orchestrator plugins: {[e.name for e in eps]}")
```

### Connection Validation Fails

1. Ensure Dagster webserver is running
2. Check network connectivity to Dagster GraphQL endpoint
3. Verify port configuration

### Schedule Not Executing

1. Validate cron expression: `croniter.croniter("0 8 * * *")`
2. Verify timezone: `import pytz; pytz.timezone("America/New_York")`
3. Check Dagster daemon is running
