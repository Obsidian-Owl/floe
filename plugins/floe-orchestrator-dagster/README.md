# floe-orchestrator-dagster

Dagster orchestrator plugin for the floe data platform.

## Overview

This plugin provides Dagster integration for floe, enabling:

- Runtime loading of Dagster Definitions from compiled product projects
- Creation of software-defined assets from dbt transforms
- Helm values for K8s deployment of Dagster services
- OpenLineage event emission for data lineage tracking
- Cron-based job scheduling with timezone support

## Installation

```bash
pip install floe-orchestrator-dagster
```

## Usage

```python
from pathlib import Path

from floe_orchestrator_dagster.loader import load_product_definitions

# Runtime definitions are loaded through the generated definitions.py shim,
# or directly through the loader when embedding in tests/tools.
definitions = load_product_definitions(
    product_name="customer-360",
    project_dir=Path("/path/to/product"),
)
```

The product directory must contain `compiled_artifacts.json`,
`profiles.yml`, and `target/manifest.json` from the same compile/runtime
context. Direct `DagsterOrchestratorPlugin.create_definitions()` calls only
validate artifacts and require the loader path for usable runtime definitions.

```python
from floe_orchestrator_dagster import DagsterOrchestratorPlugin

plugin = DagsterOrchestratorPlugin()

# Get Helm values for deployment
helm_values = plugin.get_helm_values()
```

## Requirements

- Python 3.10+
- Dagster 1.10+
- floe-core 0.1.0+

## License

Apache-2.0
