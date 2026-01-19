# floe-orchestrator-dagster

Dagster orchestrator plugin for the floe data platform.

## Overview

This plugin provides Dagster integration for floe, enabling:

- Generation of Dagster Definitions from CompiledArtifacts
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
from floe_orchestrator_dagster import DagsterOrchestratorPlugin

plugin = DagsterOrchestratorPlugin()

# Generate Dagster definitions from compiled artifacts
definitions = plugin.create_definitions(compiled_artifacts)

# Get Helm values for deployment
helm_values = plugin.get_helm_values()
```

## Requirements

- Python 3.10+
- Dagster 1.10+
- floe-core 0.1.0+

## License

Apache-2.0
