# floe-quality-dbt

dbt-expectations data quality plugin for the floe data platform.

## Overview

This plugin implements the `QualityPlugin` ABC using [dbt-expectations](https://github.com/calogica/dbt-expectations)
for data quality validation, executing quality checks as dbt tests via the DBTPlugin interface.

## Features

- Compile-time configuration validation
- Runtime quality check execution via dbt test
- Quality scoring with dimension weights
- OpenLineage event emission for failures
- Integration with existing dbt projects

## Installation

```bash
pip install floe-quality-dbt
```

With dbt dependencies:

```bash
pip install floe-quality-dbt[dbt]
```

## Quick Start

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

# Get the dbt-expectations plugin
registry = get_registry()
dbt_plugin = registry.get(PluginType.QUALITY, "dbt_expectations")

# Run quality checks
result = dbt_plugin.run_checks(
    suite_name="customers_quality",
    data_source="staging.customers",
)

if result.passed:
    print("All quality checks passed!")
else:
    print(f"Failed checks: {len([c for c in result.checks if not c.passed])}")
```

## Configuration

Configure the plugin in your `manifest.yaml`:

```yaml
plugins:
  quality:
    provider: dbt_expectations
    quality_gates:
      gold:
        min_test_coverage: 100
        required_tests: [not_null, unique]
```

## Development

```bash
# Install in development mode
uv pip install -e ".[dev,dbt]"

# Run tests
pytest tests/unit/ -v

# Type checking
mypy src/

# Linting
ruff check src/
```

## License

Apache 2.0
