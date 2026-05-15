# floe-dbt-core

> **Alpha release notice:** This `v0.1.0-alpha.1` package is for isolated evaluation only. Do not use Floe alpha packages with production data, production credentials, regulated workloads, customer-facing SLAs, or production-scale loads. Floe is distributed under Apache-2.0 on an "AS IS" basis; see the repository `LICENSE` for full terms.

DBT plugin for floe using dbt-core Python API.

## Overview

This plugin provides `DBTCorePlugin`, which wraps dbt-core's `dbtRunner` for:
- Local development
- CI/CD pipelines
- Single-threaded execution

**Note**: dbtRunner is NOT thread-safe. For parallel execution, use `floe-dbt-fusion`.

## Installation

```bash
pip install floe-dbt-core
```

## Usage

The plugin is automatically discovered via entry points:

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

registry = get_registry()
dbt_plugin = registry.get(PluginType.DBT, "core")

# Compile project
manifest_path = dbt_plugin.compile_project(
    project_dir=Path("my_project"),
    profiles_dir=Path("my_project"),
    target="dev"
)

# Run models
result = dbt_plugin.run_models(
    project_dir=Path("my_project"),
    profiles_dir=Path("my_project"),
    target="dev",
    select="tag:daily"
)
```

## Features

- Full dbt-core integration via dbtRunner
- SQLFluff linting with dialect awareness
- OpenTelemetry instrumentation
- Structured error handling with file/line preservation

## License

Apache-2.0
