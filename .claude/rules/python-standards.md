# Python Development Standards

## Type Safety (MANDATORY)

**YOU MUST include type hints on ALL functions, methods, and variables:**

```python
from __future__ import annotations  # REQUIRED at top of every .py file

from typing import Any
from pathlib import Path

def process_data(
    input_path: Path,
    config: dict[str, Any],
    strict: bool = True
) -> dict[str, Any]:
    """Process data with strict type checking.

    Args:
        input_path: Path to input file
        config: Configuration dictionary
        strict: Enable strict validation

    Returns:
        Processed data dictionary

    Raises:
        ValidationError: If validation fails
    """
    result: dict[str, Any] = {}
    # ...
    return result
```

**Requirements:**
- `from __future__ import annotations` at top of every file
- Modern generics: `list[str]`, `dict[str, int]` (not `List[str]`, `Dict[str, int]`)
- Run `mypy --strict` on all code
- No `Any` types except when interfacing with untyped third-party libraries

## Code Quality Tools

**Enforcement via pre-commit hooks** (see `.pre-commit-config.yaml`):
- Black (formatting, 100 char line length)
- Ruff (linting + import sorting)
- Bandit (security scanning)
- mypy (type checking)

## Code Organization

```python
"""Module docstring explaining purpose."""

from __future__ import annotations  # REQUIRED

# Standard library imports
import logging
from pathlib import Path
from typing import Any

# Third-party imports
from pydantic import BaseModel, Field

# Local imports
from floe_core.schemas import FloeSpec
from floe_core.errors import CompilationError

# Module constants
DEFAULT_VERSION = "1.0.0"
MAX_RETRIES = 3

# Logger setup
logger = logging.getLogger(__name__)


class MyClass:
    """Class with clear docstrings."""

    def __init__(self, value: str) -> None:
        """Initialize class.

        Args:
            value: Initial value
        """
        self.value = value
```

## Testing (REFERENCE)

**See `.claude/rules/testing-standards.md` for**:
- Tests FAIL never skip (MANDATORY)
- Type hints in tests
- Requirement traceability
- Coverage requirements (>80%)
- Test isolation patterns

**See `TESTING.md` for**:
- K8s-native testing (all tests run in K8s via Kind)
- IntegrationTestBase API
- Polling utilities
- Test execution commands

## Documentation: Google-Style Docstrings

```python
def compile_spec(
    spec: FloeSpec,
    target: str | None = None,
    strict: bool = True
) -> CompiledArtifacts:
    """Compile FloeSpec into CompiledArtifacts.

    Args:
        spec: Validated FloeSpec from floe.yaml
        target: Optional compute target override
        strict: Enable strict validation mode

    Returns:
        CompiledArtifacts containing dbt profiles and Dagster config

    Raises:
        ValidationError: If spec validation fails
        CompilationError: If compilation fails

    Examples:
        >>> spec = FloeSpec.parse_file("floe.yaml")
        >>> artifacts = compile_spec(spec)
        >>> artifacts.dbt_profiles["default"]["target"]
        'dev'
    """
    pass
```

## Dependency Management (REFERENCE)

**Rules**:
- Pin exact versions in production (`package==1.2.3`)
- Use version ranges in libraries (`package>=1.2,<2.0`)
- Update dependencies within 7 days of CVE disclosure
- Pure Python only (no compiled extensions)

**See**: Security scanning via `pip-audit`, `safety check` (pre-commit hooks)

## Pre-Commit Checklist

Before committing, verify:
- [ ] All type hints present (`mypy --strict` passes)
- [ ] Black formatting applied (100 char)
- [ ] Ruff linting + import sorting passes
- [ ] Bandit security scan passes
- [ ] Tests pass with > 80% coverage
- [ ] No secrets in code
