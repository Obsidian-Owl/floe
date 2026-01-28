# floe-quality-gx

Great Expectations data quality plugin for the floe data platform.

## Overview

This plugin implements the `QualityPlugin` ABC using [Great Expectations](https://greatexpectations.io/)
for data quality validation, supporting compile-time configuration validation and runtime quality checks.

## Features

- Compile-time configuration validation
- Runtime quality check execution
- Quality scoring with dimension weights
- OpenLineage event emission for failures
- Support for DuckDB, PostgreSQL, and Snowflake dialects

## Installation

```bash
pip install floe-quality-gx
```

## Quick Start

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

# Get the Great Expectations plugin
registry = get_registry()
gx_plugin = registry.get(PluginType.QUALITY, "great_expectations")

# Run quality checks
result = gx_plugin.run_checks(
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
    provider: great_expectations
    quality_gates:
      gold:
        min_test_coverage: 100
        required_tests: [not_null, unique]
```

## Development

```bash
# Install in development mode
uv pip install -e ".[dev]"

# Run tests
pytest tests/unit/ -v

# Type checking
mypy src/

# Linting
ruff check src/
```

## License

Apache 2.0
