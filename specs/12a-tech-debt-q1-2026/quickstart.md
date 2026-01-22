# Quickstart: January 2026 Tech Debt Reduction

**Date**: 2026-01-22
**Epic**: 12A (Tech Debt Q1 2026)

## Prerequisites

- Python 3.10+
- uv package manager
- Kind cluster (for integration tests)
- Access to floe monorepo

## Development Setup

```bash
# Clone and checkout feature branch
git checkout 12a-tech-debt-q1-2026

# Install dependencies
uv sync

# Run baseline audit
/tech-debt-review --all
# Expected: Debt Score 68, Critical 5, High 12
```

## Implementation Order

### Week 1: Architecture & Performance (P0)

**Task 1: Break Circular Dependency**
```bash
# Files to modify:
# - packages/floe-core/src/floe_core/rbac/generator.py
# - packages/floe-core/src/floe_core/cli/rbac/generate.py

# Verification:
python -c "import floe_core; import floe_rbac_k8s"
# Expected: No ImportError
```

**Task 2: Fix N+1 in OCI Client**
```bash
# Files to modify:
# - packages/floe-core/src/floe_core/oci/client.py

# Create benchmark test:
pytest packages/floe-core/tests/unit/oci/test_client_performance.py -v
# Expected: list() with 100 tags < 6s
```

### Week 2: Complexity Reduction (P1)

**Task 3: Refactor diff_command()**
```bash
# Create golden tests first:
pytest packages/floe-core/tests/unit/cli/rbac/test_diff_golden.py -v

# Verify complexity after:
radon cc packages/floe-core/src/floe_core/cli/rbac/diff.py -s
# Expected: diff_command CC ≤ 10
```

**Task 4: Split IcebergTableManager**
```bash
# New files to create:
# - packages/floe-iceberg/src/floe_iceberg/_lifecycle.py
# - packages/floe-iceberg/src/floe_iceberg/_schema_manager.py
# - packages/floe-iceberg/src/floe_iceberg/_snapshot_manager.py
# - packages/floe-iceberg/src/floe_iceberg/_compaction_manager.py

# Verify public API unchanged:
pytest packages/floe-iceberg/tests/unit/test_manager.py -v
```

### Week 3: Testing Improvements (P1)

**Task 5: Remove pytest.skip() Violations**
```bash
# File to modify:
# - plugins/floe-orchestrator-dagster/tests/integration/test_iceberg_io_manager.py

# Verify no skips:
rg "pytest.skip" plugins/floe-orchestrator-dagster/tests/
# Expected: No matches
```

**Task 6: Add OCI Test Coverage**
```bash
# New files to create:
# - packages/floe-core/tests/unit/oci/test_errors.py
# - packages/floe-core/tests/unit/oci/test_metrics.py

# Verify coverage:
pytest packages/floe-core/tests/unit/oci/ --cov=floe_core.oci --cov-report=term
# Expected: >80% coverage
```

**Task 7: Create Base Test Classes**
```bash
# New files to create:
# - testing/base_classes/plugin_metadata_tests.py
# - testing/base_classes/plugin_lifecycle_tests.py
# - testing/base_classes/plugin_discovery_tests.py

# Migrate 3 plugins and verify:
pytest plugins/floe-compute-duckdb/tests/ -v
pytest plugins/floe-catalog-polaris/tests/ -v
pytest plugins/floe-orchestrator-dagster/tests/ -v
```

### Week 4: Cleanup (P3)

**Task 8: Remove Unused Dependencies**
```bash
# File to modify:
# - plugins/floe-orchestrator-dagster/pyproject.toml

# Remove croniter and pytz, then verify:
uv sync
pytest plugins/floe-orchestrator-dagster/tests/ -v
```

## Verification Commands

```bash
# Full debt audit (run at end)
/tech-debt-review --all
# Expected: Debt Score 80+, Critical 0, High ≤3

# Complexity check
radon cc packages/ -s -a
# Expected: Average CC < 5, Max CC ≤ 15

# Skip count
rg "pytest.skip" --type py tests/ plugins/
# Expected: 0 matches

# Type checking
mypy --strict packages/floe-core/src/floe_core/oci/
mypy --strict packages/floe-iceberg/src/floe_iceberg/
# Expected: 0 errors

# All tests pass
make test-unit
# Expected: All pass
```

## Common Issues

### Issue: Import cycle detected
```
ImportError: cannot import name 'K8sRBACPlugin' from partially initialized module
```
**Solution**: Use registry lookup instead of direct import
```python
# Wrong
from floe_rbac_k8s import K8sRBACPlugin

# Correct
from floe_core.plugin_registry import registry
plugin = registry.get("rbac", "k8s")
```

### Issue: Performance benchmark flaky
```
AssertionError: Expected < 6s, got 7.2s
```
**Solution**: Use relative improvement (5x) not absolute threshold
```python
# Wrong
assert duration < 6.0

# Correct
assert duration < baseline / 5  # 5x improvement
```

### Issue: Test fails when infrastructure missing
```
FAILED: Polaris not available at localhost:8181
```
**Solution**: This is correct behavior. Start infrastructure:
```bash
make deploy-local
```

## Code Patterns

### Registry Lookup (Anti-Circular)
```python
from floe_core.plugin_registry import registry

def get_rbac_plugin() -> RBACPlugin:
    """Get RBAC plugin via registry (avoids circular import)."""
    return registry.get("rbac")
```

### Parallel Fetching
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_all(urls: list[str], max_workers: int = 10) -> dict[str, bytes]:
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch, url): url for url in urls}
        return {futures[f]: f.result() for f in as_completed(futures)}
```

### Facade Pattern
```python
class IcebergTableManager:
    def __init__(self, catalog: Catalog) -> None:
        self._lifecycle = _IcebergTableLifecycle(catalog)
        self._schema = _IcebergSchemaManager(catalog)
        # ... other internal classes

    def create(self, name: str, schema: Schema) -> Table:
        return self._lifecycle.create(name, schema)
```

### Base Test Class Usage
```python
from testing.base_classes.plugin_metadata_tests import BasePluginMetadataTests

class TestDuckDBPluginMetadata(BasePluginMetadataTests):
    @pytest.fixture
    def plugin_class(self):
        from floe_compute_duckdb import DuckDBComputePlugin
        return DuckDBComputePlugin
```
