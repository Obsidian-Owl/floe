# Research: CLI Unification

**Epic**: 11 (CLI Unification)
**Date**: 2026-01-20

## Prior Decisions (from Agent Memory)

- CLI architecture uses opinionation boundaries pattern (ENFORCED vs PLUGGABLE)
- floe follows standard CLI patterns from dbt, Dagster, Prefect (all use Click)

## Research Findings

### R1: Click Framework Best Practices

**Decision**: Use Click>=8.1.0 as CLI framework

**Rationale**:
- Already used in floe-cli (RBAC commands)
- Better nested command group support than argparse
- Native type annotations via decorators
- Rich ecosystem (click-completion, click-log, rich-click)
- Consistent with dbt-core, Dagster CLI patterns

**Alternatives Considered**:
- **argparse** (current floe-core): Rejected - worse UX, manual nested groups
- **typer**: Rejected - adds Pydantic dependency layer, less mature
- **fire**: Rejected - auto-inference is unpredictable for complex CLIs

### R2: Click Group Patterns

**Decision**: Use Click command groups with lazy loading

**Pattern**:
```python
@click.group()
def cli():
    """floe - Data Platform Framework"""
    pass

@cli.group()
def platform():
    """Platform Team commands"""
    pass

@platform.command()
def compile():
    """Compile FloeSpec to CompiledArtifacts"""
    pass
```

**Rationale**:
- Clean hierarchical structure matches target architecture
- Lazy loading prevents import overhead for unused commands
- Each command file can be developed independently

### R3: RBAC Migration Strategy

**Decision**: Direct migration with golden file regression testing

**Rationale**:
- RBAC commands are well-tested in floe-cli
- Click bindings change, business logic stays same
- Golden files capture exact output for regression testing

**Migration Steps**:
1. Capture baseline outputs from floe-cli RBAC commands
2. Move Python modules (keep business logic intact)
3. Update Click decorators to use new group structure
4. Verify output matches golden files

### R4: Error Handling Pattern

**Decision**: Plain text stderr with non-zero exit codes

**Rationale**:
- Standard Unix convention
- CI/CD integration (exit codes)
- Human readable in terminal
- Machine parseable (consistent format)

**Pattern**:
```python
import sys
import click

def handle_error(message: str, exit_code: int = 1) -> None:
    """Output error to stderr and exit."""
    click.echo(f"Error: {message}", err=True)
    sys.exit(exit_code)
```

### R5: Optional Dependencies

**Decision**: Graceful degradation with helpful error messages

**Rationale**:
- kubernetes package is large, only needed for audit/diff
- Rich is optional for enhanced output (colors, tables, progress bars)
- Users should know how to install missing dependencies

**Rich Handling Pattern**:
```python
# CLI MUST function without Rich installed
try:
    from rich.console import Console
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

def echo_output(message: str, style: str | None = None) -> None:
    """Output message with optional Rich formatting."""
    if HAS_RICH and style:
        console.print(message, style=style)
    else:
        click.echo(message)
```

**Kubernetes Handling Pattern**:
```python
def require_kubernetes():
    """Check for kubernetes package availability."""
    try:
        import kubernetes
    except ImportError:
        handle_error(
            "kubernetes package required for this command.\n"
            "Install with: pip install floe-core[kubernetes]"
        )
```

### R6: Testing Strategy

**Decision**: Click CliRunner + golden file snapshots

**Rationale**:
- CliRunner provides isolated CLI testing
- Golden files capture output format for regression
- Integration tests verify K8s operations

**Test Structure**:
```python
from click.testing import CliRunner

def test_help_output():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "platform" in result.output
    assert "rbac" in result.output
```

### R7: Entry Point Resolution

**Decision**: Single entry point in floe-core, remove floe-cli entry point

**Problem**: Both packages register `floe` entry point:
- floe-core: `floe = "floe_core.cli:main"`
- floe-cli: `floe = "floe_cli.main:cli"`

**Solution**:
1. Keep floe-core entry point
2. Remove floe-cli entry point (deprecate package)
3. Verify single `floe` command after installation

### R8: Version Display

**Decision**: Use importlib.metadata for version

**Pattern**:
```python
from importlib.metadata import version

def get_version():
    return version("floe-core")
```

**Rationale**:
- Standard Python 3.10+ approach
- No hardcoded version strings
- Single source of truth (pyproject.toml)

## Resolved Clarifications

All technical unknowns have been resolved through research:

| Question | Resolution |
|----------|------------|
| CLI framework | Click>=8.1.0 |
| RBAC migration approach | Direct migration with golden files |
| Error output format | Plain text stderr, non-zero exit codes |
| Optional dependencies | Graceful error with install instructions |
| Entry point conflict | Single entry point in floe-core |

## References

- [Click Documentation](https://click.palletsprojects.com/)
- [dbt CLI Architecture](https://github.com/dbt-labs/dbt-core)
- [ADR-0047: CLI Architecture](../../docs/architecture/adr/0047-cli-architecture.md)
