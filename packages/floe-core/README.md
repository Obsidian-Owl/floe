# floe-core

Core plugin registry and interfaces for the floe data platform.

## Installation

```bash
uv pip install floe-core
```

## Features

- Plugin discovery via entry points
- Type-safe plugin registration
- Version compatibility checking
- Configuration validation with Pydantic
- Health check support

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/floe_core

# Linting
ruff check src/floe_core
```
