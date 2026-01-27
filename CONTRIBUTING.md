# Contributing to floe

Thank you for your interest in contributing to floe! This document provides guidelines and information for contributors.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Docker Desktop** or **OrbStack**
- **uv** package manager: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Kind** (for K8s-native testing)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/Obsidian-Owl/floe.git
cd floe

# Install dependencies
uv sync

# Install git hooks (runs both bd and pre-commit)
make setup-hooks

# Run quality checks
make check
```

### Running Tests

```bash
# Fast unit tests (no infrastructure required)
make test-unit

# Full test suite (requires K8s/Kind)
make test

# K8s-native integration tests
make test-k8s
```

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/Obsidian-Owl/floe/issues) for bug reports and feature requests
- Search existing issues before creating a new one
- Include reproduction steps for bugs
- For security vulnerabilities, please email security@obsidianowl.com instead of creating a public issue

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Follow our code standards** (see below)
3. **Add tests** for new functionality
4. **Update documentation** if needed
5. **Ensure all checks pass**: `make check`
6. **Submit a PR** with a clear description

### Branch Naming

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/improvements

## Code Standards

### Type Safety (Mandatory)

All code must include type hints and pass `mypy --strict`:

```python
from __future__ import annotations

def process_data(input_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Process data with strict type checking."""
    ...
```

### Code Quality

- **Formatting**: Black (100 char line length), enforced by Ruff
- **Linting**: Ruff
- **Type checking**: mypy --strict
- **Security**: Bandit scanning

Run all checks:
```bash
make check
```

### Testing Requirements

- **Coverage**: >80% for new code
- **Requirement traceability**: All tests linked to requirements via `@pytest.mark.requirement()`
- **No skipped tests**: Tests must fail, not skip, when infrastructure is unavailable
- **K8s-native**: Integration tests run in Kubernetes (Kind cluster)

See [TESTING.md](TESTING.md) for detailed testing guidelines.

### Documentation

- **Docstrings**: Google-style for all public functions
- **Type hints**: In function signatures (not repeated in docstrings)
- **ADRs**: For architectural decisions, add to `docs/architecture/adr/`

### Security

- **Never hardcode secrets** - Use `SecretStr` and environment variables
- **No dangerous constructs** - No code injection vectors or unsafe deserialization
- **Validate all input** - Use Pydantic for data validation

See [.claude/rules/security.md](.claude/rules/security.md) for detailed security guidelines.

## Architecture Guidelines

### Layer Boundaries

floe uses a four-layer architecture. Respect layer boundaries:

| Layer | Owner | Can Modify |
|-------|-------|------------|
| 1: Foundation | floe Maintainers | Schemas, validation engine |
| 2: Configuration | Platform Engineers | Plugin selection, governance |
| 3: Services | Platform Engineers | Infrastructure services |
| 4: Data | Data Engineers | Pipeline logic, transforms |

**Key rule**: Configuration flows downward only. Data layer cannot modify platform layer.

### Component Ownership

- **dbt** owns all SQL - Never parse/validate SQL in Python
- **Dagster** owns orchestration - Never run SQL directly
- **Iceberg** owns storage format - Use PyIceberg for table operations
- **CompiledArtifacts** is the sole contract between packages

### CLI Command Registration

The floe CLI uses [Click](https://click.palletsprojects.com/) with a hierarchical command structure. Follow this pattern when adding new commands:

**Directory Structure:**
```
packages/floe-core/src/floe_core/cli/
├── main.py                 # Root CLI, registers all groups
├── utils.py                # Shared utilities (ExitCode, info, error_exit)
├── <group>/                # Command group directory
│   ├── __init__.py         # Group definition, registers commands
│   └── <command>.py        # Individual command implementation
```

**Step 1: Create the command** (`cli/<group>/<command>.py`):
```python
import click

@click.command(
    name="mycommand",
    help="""\b
Short description.

Detailed help text with examples:
    $ floe mygroup mycommand --option value
""",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option("--option", "-o", type=str, help="Option description.")
def mycommand(option: str | None) -> None:
    """Command implementation."""
    pass
```

**Step 2: Create/update the group** (`cli/<group>/__init__.py`):
```python
import click
from floe_core.cli.<group>.mycommand import mycommand

@click.group(name="mygroup", help="Group description.")
def mygroup() -> None:
    pass

mygroup.add_command(mycommand)

__all__ = ["mygroup"]
```

**Step 3: Register the group** (`cli/main.py`):
```python
from floe_core.cli.<group> import mygroup

cli.add_command(mygroup)
```

**Help Text Requirements:**
- Use `\b` to preserve formatting in Click help strings
- Include at least 2 practical examples
- Document environment variables that affect the command
- List exit codes for commands that have non-zero exits

**Reference implementations:**
- Group: `cli/artifact/__init__.py`
- Command: `cli/artifact/sign.py`, `cli/artifact/verify.py`

See [CLAUDE.md](CLAUDE.md) for complete development guidelines.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Snowflake compute plugin
fix: resolve connection pooling issue
docs: update architecture diagrams
refactor: simplify plugin discovery
test: add contract tests for CompiledArtifacts
chore: update dependencies
```

## Review Process

1. **Automated checks** must pass (CI pipeline)
2. **Code review** by at least one maintainer
3. **Test coverage** verified
4. **Documentation** updated if needed
5. **Squash merge** to main

## Getting Help

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/Obsidian-Owl/floe/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Obsidian-Owl/floe/discussions)

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
