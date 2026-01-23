# Quickstart: Tech Debt Resolution (Epic 12B)

This guide provides step-by-step instructions for implementing each tech debt resolution.

## Prerequisites

- Python 3.10+
- uv package manager
- floe development environment set up

```bash
# Verify environment
uv --version
python --version  # Should be 3.10+
make check        # All checks should pass
```

## Phase 1: Critical Issues (P0)

### Task 1.1: Break Circular Dependency (12B-ARCH-001)

**Current Cycle**: `schemas → telemetry → plugins → schemas`

**Step 1**: Create new telemetry schema file
```bash
# Create the new file
touch packages/floe-core/src/floe_core/schemas/telemetry.py
```

**Step 2**: Move TelemetryConfig to schemas/telemetry.py
```python
# packages/floe-core/src/floe_core/schemas/telemetry.py
"""Telemetry configuration schemas.

Moved from telemetry/config.py to break circular dependency.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr

# Move ALL classes from telemetry/config.py here:
# - ResourceAttributes
# - OTLPExporterConfig
# - SamplerConfig
# - TelemetryConfig
```

**Step 3**: Update telemetry/config.py to re-export
```python
# packages/floe-core/src/floe_core/telemetry/config.py
"""Telemetry configuration (re-exports for backward compatibility)."""
from floe_core.schemas.telemetry import (
    OTLPExporterConfig,
    ResourceAttributes,
    SamplerConfig,
    TelemetryConfig,
)

__all__ = [
    "OTLPExporterConfig",
    "ResourceAttributes",
    "SamplerConfig",
    "TelemetryConfig",
]
```

**Step 4**: Update compiled_artifacts.py import
```python
# packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
# Change:
# from floe_core.telemetry.config import TelemetryConfig
# To:
from floe_core.schemas.telemetry import TelemetryConfig
```

**Step 5**: Verify no circular imports
```bash
python -c "from floe_core.schemas import CompiledArtifacts; print('OK')"
python -m mypy --strict packages/floe-core/src/floe_core/schemas/
```

---

### Task 1.2: Remove Skipped Tests (12B-TEST-001)

**Location**: `packages/floe-iceberg/tests/unit/test_lifecycle.py`

**Step 1**: Implement drop_table() in IcebergTableManager
```python
# packages/floe-iceberg/src/floe_iceberg/manager.py

def drop_table(
    self,
    name: str,
    purge: bool = False,
) -> None:
    """Drop a table from the catalog.

    Args:
        name: Fully qualified table name (namespace.table)
        purge: If True, also delete data files. If False, only metadata.

    Raises:
        TableNotFoundError: If table does not exist
    """
    try:
        self._catalog.drop_table(name, purge=purge)
        logger.info("table_dropped", table=name, purge=purge)
    except NoSuchTableError as e:
        raise TableNotFoundError(f"Table not found: {name}") from e
```

**Step 2**: Remove @pytest.mark.skip decorators
```python
# test_lifecycle.py - Remove these:
# @pytest.mark.skip(reason="drop_table not implemented")
```

**Step 3**: Run tests
```bash
pytest packages/floe-iceberg/tests/unit/test_lifecycle.py -v
```

---

### Task 1.3: Refactor map_pyiceberg_error (12B-CX-001)

**Location**: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/errors.py:51`

**Step 1**: Create error handlers
```python
# At module level, before map_pyiceberg_error()

def _handle_unavailable(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogUnavailableError:
    return CatalogUnavailableError(
        message=str(error),
        catalog_uri=catalog_uri,
        operation=operation,
    )

def _handle_unauthorized(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogAuthError:
    return CatalogAuthError(
        message=str(error),
        catalog_uri=catalog_uri,
    )

# ... create handler for each error type

ERROR_HANDLERS: dict[type[Exception], Callable[..., CatalogError]] = {
    ServiceUnavailableError: _handle_unavailable,
    UnauthorizedError: _handle_unauthorized,
    # ... all 16 error types
}
```

**Step 2**: Refactor map_pyiceberg_error()
```python
def map_pyiceberg_error(
    error: Exception,
    catalog_uri: str | None = None,
    operation: str | None = None,
) -> CatalogError:
    """Map PyIceberg exceptions to floe catalog errors.

    Uses dispatch dictionary for O(1) lookup instead of if-elif chain.
    """
    handler = ERROR_HANDLERS.get(type(error), _handle_unknown)
    return handler(error, catalog_uri, operation)
```

**Step 3**: Verify complexity reduction
```bash
# Run complexity analysis
python -c "
import ast
import sys
from pathlib import Path

code = Path('plugins/floe-catalog-polaris/src/floe_catalog_polaris/errors.py').read_text()
tree = ast.parse(code)

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'map_pyiceberg_error':
        # Count branches
        branches = sum(1 for n in ast.walk(node) if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler)))
        print(f'Cyclomatic complexity: {branches + 1}')
"
```

---

### Task 1.4: Pin Dependencies (12B-DEP-001, 12B-DEP-002)

**Step 1**: Update pyproject.toml files
```bash
# Find all pyproject.toml files with pydantic
grep -r "pydantic>=" packages/*/pyproject.toml plugins/*/pyproject.toml
```

**Step 2**: Add upper bounds
```toml
# In each pyproject.toml:
dependencies = [
    "pydantic>=2.12.5,<3.0",      # Was: pydantic>=2.0
    "kubernetes>=35.0.0,<36.0",    # Was: kubernetes>=28.0.0
]
```

**Step 3**: Sync and verify
```bash
uv sync
pip-audit  # Should report 0 vulnerabilities
```

---

## Phase 2: High Priority (P1)

### Task 2.1: Reduce __init__.py Exports (12B-ARCH-002)

**Location**: `packages/floe-core/src/floe_core/__init__.py`

**Step 1**: Define explicit __all__
```python
# Keep only essential exports (~15)
__all__ = [
    # Core schemas
    "FloeSpec",
    "CompiledArtifacts",
    "PlatformManifest",
    # Compilation
    "compile_pipeline",
    "Compiler",
    # Plugin system
    "PluginRegistry",
    "get_registry",
    "PluginType",
    "PluginMetadata",
    # Errors
    "FloeError",
    "CompilationError",
    "PluginError",
    "ValidationError",
]
```

**Step 2**: Remove wildcard imports
```python
# Remove these:
# from floe_core.schemas import *
# from floe_core.plugins import *

# Replace with explicit imports
from floe_core.schemas import FloeSpec, CompiledArtifacts, PlatformManifest
```

---

## Verification Commands

After each phase, verify:

```bash
# Run all tests
make test

# Check for circular imports
python -m mypy --strict packages/floe-core/

# Verify no skipped tests
pytest --co -q 2>/dev/null | grep -c "skip" || echo "0 skipped"

# Run tech debt review
/tech-debt-review --all
```

## Common Issues

### Import Errors After TelemetryConfig Move

If you see `ImportError: cannot import name 'TelemetryConfig'`:
1. Ensure re-export in `telemetry/config.py`
2. Check for stale `.pyc` files: `find . -name "*.pyc" -delete`
3. Reinstall package: `uv sync --reinstall`

### Tests Fail After drop_table() Implementation

If `test_drop_table_raises_for_nonexistent_table` fails:
1. Verify `NoSuchTableError` import from pyiceberg
2. Ensure `TableNotFoundError` is defined in floe-iceberg errors

### Complexity Still High After Refactor

If cyclomatic complexity > 10 after dispatch refactor:
1. Check for remaining if-statements in handler functions
2. Move complex handlers to separate functions
3. Use match statement (Python 3.10+) for remaining type checks
