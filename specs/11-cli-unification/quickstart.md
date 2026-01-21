# Developer Quickstart: CLI Unification

**Epic**: 11 (CLI Unification)
**Date**: 2026-01-20

## Prerequisites

- Python 3.10+
- uv package manager
- Kind (for K8s integration tests)

## Setup

```bash
# Clone and checkout branch
git checkout 11-cli-unification

# Install dependencies
uv sync

# Verify CLI works
uv run floe --help
```

## Development Workflow

### 1. Making CLI Changes

CLI code is in `packages/floe-core/src/floe_core/cli/`:

```
cli/
├── main.py              # Root Click group
├── platform/            # Platform team commands
├── rbac/                # RBAC management
├── artifact/            # Artifact operations
└── data/                # Data team stubs
```

### 2. Adding a New Command

```python
# packages/floe-core/src/floe_core/cli/platform/mycommand.py
from __future__ import annotations

import click

@click.command()
@click.option("--option", required=True, help="Option description")
def mycommand(option: str) -> None:
    """Short description of command."""
    click.echo(f"Running with {option}")
```

Register in group:

```python
# packages/floe-core/src/floe_core/cli/platform/__init__.py
from .mycommand import mycommand

platform.add_command(mycommand)
```

### 3. Running Tests

```bash
# Unit tests (fast)
uv run pytest packages/floe-core/tests/unit/cli/ -v

# Integration tests (requires K8s)
make test-integration

# Golden file regression tests
uv run pytest tests/contract/test_cli_output_contracts.py -v
```

### 4. Testing CLI Manually

```bash
# Help
uv run floe --help
uv run floe platform --help
uv run floe rbac --help

# Compile
uv run floe platform compile --spec floe.yaml --manifest manifest.yaml

# RBAC
uv run floe rbac generate --config manifest.yaml --dry-run
```

## Common Tasks

### Adding an Option

```python
@click.option(
    "--my-option",
    type=click.Path(exists=True),
    required=False,
    default="default_value",
    help="Description of option"
)
```

### Error Handling

```python
import sys
import click

def handle_error(message: str, exit_code: int = 1) -> None:
    """Output error to stderr and exit."""
    click.echo(f"Error: {message}", err=True)
    sys.exit(exit_code)

# Usage
if not path.exists():
    handle_error(f"File not found: {path}")
```

### Testing with CliRunner

```python
from click.testing import CliRunner
from floe_core.cli.main import cli

def test_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "platform" in result.output
```

## Key Files

| File | Purpose |
|------|---------|
| `cli/main.py` | Root Click group, version flag |
| `cli/platform/compile.py` | Main compile command |
| `cli/rbac/__init__.py` | RBAC command group |
| `tests/unit/cli/test_main.py` | CLI unit tests |
| `tests/contract/test_cli_output_contracts.py` | Golden file tests |

## Debugging

### Verbose Output

```bash
# Set log level
FLOE_LOG_LEVEL=DEBUG uv run floe platform compile ...
```

### Click Debug

```bash
# Show Click internals
uv run python -c "from floe_core.cli.main import cli; cli(standalone_mode=False)"
```

## Reference

- [Click Documentation](https://click.palletsprojects.com/)
- [ADR-0047: CLI Architecture](../../docs/architecture/adr/0047-cli-architecture.md)
- [spec.md](./spec.md) - Feature specification
- [plan.md](./plan.md) - Implementation plan
