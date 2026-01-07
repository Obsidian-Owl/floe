# Code Quality Standards

This guide covers style guides, linting, and pre-commit configuration for floe.

---

## Style Guide

| Tool | Config | Purpose |
|------|--------|---------|
| **ruff** | pyproject.toml | Linting, formatting |
| **mypy** | pyproject.toml | Type checking |
| **pre-commit** | .pre-commit-config.yaml | Git hooks |

---

## pyproject.toml Configuration

```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
]
ignore = ["E501"]  # Line too long (handled by formatter)

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = "dagster.*"
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
filterwarnings = [
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
branch = true
source = ["floe_core", "floe_cli", "floe_dagster", "floe_dbt"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

---

## Pre-commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key

  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: mypy
        language: system
        types: [python]
        pass_filenames: false
        args: [floe_core, floe_cli, floe_dagster, floe_dbt]
```

---

## Documentation Standards

### Docstring Format

```python
def compile_spec(
    self,
    spec_path: Path,
    *,
    validate: bool = True,
) -> CompiledArtifacts:
    """Compile a floe.yaml specification to CompiledArtifacts.

    Args:
        spec_path: Path to the floe.yaml file.
        validate: Whether to validate the spec before compilation.
            Defaults to True.

    Returns:
        The compiled artifacts ready for runtime execution.

    Raises:
        ConfigurationError: If the spec is invalid.
        FileNotFoundError: If spec_path does not exist.

    Example:
        >>> compiler = Compiler()
        >>> artifacts = compiler.compile_spec(Path("floe.yaml"))
        >>> print(artifacts.compute.target)
        duckdb
    """
```

### README Requirements

Each package must have a README with:

1. **Description**: What the package does
2. **Installation**: How to install
3. **Quick Start**: Minimal example
4. **API Reference**: Link to docs
5. **Contributing**: Link to guidelines

---

## Running Quality Checks

```bash
# Run all linting
ruff check .

# Run with auto-fix
ruff check --fix .

# Format code
ruff format .

# Type checking
mypy floe_core floe_cli floe_dagster floe_dbt

# Run pre-commit on all files
pre-commit run --all-files
```

---

## Related

- [Testing Index](index.md)
- [CI/CD Pipeline](ci-cd.md)
- [Python Standards](/.claude/rules/python-standards.md)
