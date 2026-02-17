## Test Organization Rules

## Decision Tree: Package vs Root

**START HERE**: Where should I put my test?

### Question 1: Does your test import from MULTIPLE packages?

```
Does your test import from floe-core AND floe-dagster?
Does your test import from floe-polaris AND floe-iceberg?
Does your test validate integration between two or more packages?
```

- **YES** → Root-level (`tests/contract/` or `tests/e2e/`)
- **NO** → Continue to Question 2

### Question 2: Does your test validate a CONTRACT between packages?

```
Does your test validate that CompiledArtifacts schema is stable?
Does your test validate that floe-dagster can consume floe-core output?
Does your test validate plugin ABCs (interfaces)?
Does your test check backwards compatibility of artifacts?
```

- **YES** → Root-level `tests/contract/test_X_to_Y_contract.py`
- **NO** → Continue to Question 3

### Question 3: Does your test validate a full WORKFLOW across the platform?

```
Does your test run: floe compile → floe deploy → floe run → validate output?
Does your test validate the complete demo pipeline end-to-end?
Does your test require ALL services running (Polaris, Dagster, S3, etc.)?
```

- **YES** → Root-level `tests/e2e/test_X_flow.py`
- **NO** → Continue to Question 4

### Question 4: What package is your test for?

```
Is your test for floe-polaris ONLY?
Is your test for floe-core ONLY?
Is your test for floe-dagster ONLY?
```

- **YES** → Package-level `{package}/tests/{tier}/test_*.py` (floe-core/, plugins/floe-compute-*, etc.)
- **UNCLEAR** → If you're still unsure, default to package-level and ask during PR review

## Test Tier Selection

**Question**: Does my test need real external services (PostgreSQL, Polaris, S3)?

### Unit Tests (`tests/unit/`)

**When to use:**
- Test does NOT need external services
- Fast (<1s per test)
- Uses mocks/fakes for dependencies
- Run on host (no Docker/K8s required)

**Example:**
```python
# floe-core/tests/unit/test_compiler.py
def test_compile_minimal_spec() -> None:
    """Test compiler with minimal valid spec."""
    spec = FloeSpec(name="test", version="1.0.0")
    artifacts = compile_spec(spec)
    assert artifacts.version == "2.0.0"
```

### Contract Tests (`tests/contract/` - ROOT ONLY)

**When to use:**
- Validate Pydantic schemas (CompiledArtifacts, plugin ABCs)
- Validate plugin interfaces
- NO real execution, only schema/interface validation
- Fast (<5s total for all contract tests)
- Run on host (no Docker/K8s required)

**Example:**
```python
# tests/contract/test_core_to_dagster_contract.py
def test_dagster_can_consume_compiled_artifacts() -> None:
    """Test that floe-dagster can load CompiledArtifacts from floe-core."""
    # floe-core produces
    artifacts = CompiledArtifacts(...)

    # floe-dagster consumes
    assets = create_assets(artifacts)
    assert len(assets) > 0
```

### Integration Tests (`tests/integration/`)

**When to use:**
- Test needs REAL external services
- Real Polaris catalog
- Real S3 buckets (LocalStack)
- Real database connections
- Runs in K8s (Kind cluster)
- Inherits from `IntegrationTestBase`

**Example:**
```python
# plugins/floe-catalog-polaris/tests/integration/test_catalog.py
from testing.base_classes.integration_test_base import IntegrationTestBase

class TestPolarisCatalog(IntegrationTestBase):
    """Integration tests for Polaris catalog."""

    required_services = [("polaris", 8181), ("localstack", 4566)]

    @pytest.mark.requirement("004-FR-001")
    def test_create_catalog(self) -> None:
        """Test catalog creation with real Polaris instance."""
        self.check_infrastructure("polaris", 8181)
        namespace = self.generate_unique_namespace("test_polaris")

        catalog = create_catalog(name=f"{namespace}_catalog")
        assert catalog is not None
```

### E2E Tests (`tests/e2e/`)

**When to use:**
- Full workflow validation
- Compile → Deploy → Execute → Validate
- All services running
- Slowest (<5 min)
- Runs in K8s (Kind cluster)

**Example:**
```python
# tests/e2e/test_demo_flow.py
@pytest.mark.requirement("E2E-001")
def test_complete_pipeline_flow() -> None:
    """Test complete pipeline from spec to execution."""
    # Compile
    artifacts = compile_floe_spec("demo/floe.yaml")

    # Deploy
    deploy_to_dagster(artifacts)

    # Execute
    run_id = trigger_pipeline()

    # Validate
    assert run_status(run_id) == "SUCCESS"
```

## Integration Test Responsibility

### When to Write Integration Tests

**MANDATORY integration tests for:**
- Any feature touching external services (Polaris, S3, PostgreSQL)
- Cross-package contracts (floe-core → floe-dagster)
- Plugin implementations (real service validation)
- "Wire X to Y" tasks (verify the wiring works)

**Decision tree for integration tests:**
1. Does feature touch an external service? → **Integration test required**
2. Does feature cross package boundaries? → **Contract test (may need integration)**
3. Is this a plugin implementation? → **Plugin compliance integration test**
4. Is this internal to one package? → **Unit test sufficient**

### Integration Test Location

| Scope | Location | Example |
|-------|----------|---------|
| Single package + service | `packages/X/tests/integration/` | Polaris catalog operations |
| Cross-package | `tests/integration/` (root) | floe-core + floe-dagster |
| Full workflow | `tests/e2e/` (root) | compile → deploy → run |

### Required Base Classes

```python
# For service integration
from testing.base_classes import IntegrationTestBase

class TestMyFeature(IntegrationTestBase):
    """Integration tests for feature X."""

    required_services = [("polaris", 8181), ("localstack", 4566)]

    @pytest.mark.requirement("XXX-FR-001")
    def test_feature_with_real_service(self) -> None:
        """Test feature with actual external service."""
        self.check_infrastructure("polaris", 8181)
        namespace = self.generate_unique_namespace("test_feature")
        # ... test implementation
```

### E2E Test Pattern

E2E tests validate complete workflows across the entire platform:

```python
# tests/e2e/test_compile_deploy_run.py
from __future__ import annotations

import pytest
from testing.base_classes import IntegrationTestBase


class TestFullPipelineWorkflow(IntegrationTestBase):
    """E2E tests validating the complete floe workflow."""

    required_services = [
        ("dagster", 3000),
        ("polaris", 8181),
        ("localstack", 4566),
    ]

    @pytest.mark.e2e
    @pytest.mark.requirement("E2E-001")
    def test_full_pipeline_workflow(self) -> None:
        """Compile spec → Deploy to Dagster → Run → Validate output."""
        # 1. Compile
        artifacts = compile_floe_spec("demo/floe.yaml")
        assert artifacts.version

        # 2. Deploy
        deploy_to_dagster(artifacts)

        # 3. Execute
        run_id = trigger_pipeline("demo_pipeline")

        # 4. Validate
        status = poll_for_completion(run_id, timeout=300)
        assert status == "SUCCESS"
```

### Integration Test Checklist

Before marking a task complete, verify integration tests if applicable:

- [ ] External service interaction tested with real service
- [ ] Cross-package contracts have contract tests
- [ ] Plugin implementations pass compliance tests
- [ ] Test inherits from `IntegrationTestBase`
- [ ] Test has `@pytest.mark.requirement()` marker
- [ ] Test uses unique namespace (no test pollution)

## Package vs Root Placement Rules

### Package-Level Tests

**Core packages:** `floe-core/tests/`, `floe-cli/tests/`, `floe-dbt/tests/`, `floe-iceberg/tests/`
**Plugin packages:** `plugins/floe-{category}-{tech}/tests/`

**Rule**: Tests that import from ONLY ONE package

**Structure:**
```
plugins/floe-catalog-polaris/
├── src/
│   └── floe_polaris/
└── tests/
    ├── conftest.py  # Package-specific fixtures
    ├── unit/
    │   ├── conftest.py
    │   └── test_catalog.py  # Tests floe_polaris.catalog module
    ├── integration/
    │   ├── conftest.py
    │   └── test_catalog_integration.py  # Tests with real Polaris
    └── e2e/  # Package-specific workflows (rare)
        └── test_polaris_workflow.py
```

**Example:**
```python
# ✅ CORRECT - Package-level (single package import)
# packages/floe-core/tests/unit/test_compiler.py
from floe_core.compiler import compile_spec  # ONLY imports from floe-core

def test_compile_minimal_spec() -> None:
    spec = FloeSpec(...)
    artifacts = compile_spec(spec)
    assert artifacts.version == "2.0.0"
```

### Root-Level Tests (`tests/`)

**Rule**: Tests that import from MULTIPLE packages OR validate cross-package contracts

**Structure:**
```
tests/
├── conftest.py  # Root fixtures (shared across packages)
├── contract/  # Cross-package contract tests (MANDATORY)
│   ├── conftest.py
│   ├── test_compiled_artifacts_schema.py  # Schema stability
│   ├── test_core_to_dagster_contract.py   # floe-core + floe-dagster
│   └── test_core_to_dbt_contract.py       # floe-core + floe-dbt
└── e2e/  # Full platform E2E tests (OPTIONAL)
    ├── conftest.py
    └── test_demo_flow.py  # All packages together
```

**Example:**
```python
# ✅ CORRECT - Root-level (multi-package imports)
# tests/contract/test_core_to_dagster_contract.py
from floe_core.compiler import compile_spec  # Import from floe-core
from floe_dagster.assets import create_assets  # Import from floe-dagster

def test_dagster_can_consume_compiled_artifacts() -> None:
    """Test floe-core → floe-dagster integration."""
    artifacts = compile_spec(FloeSpec(...))
    assets = create_assets(artifacts)
    assert len(assets) > 0
```

## Anti-Patterns (FORBIDDEN)

### ❌ Anti-Pattern 1: Cross-Package Tests in Package Directories

```python
# ❌ WRONG - In floe-core/tests/unit/test_core_and_dagster.py
from floe_core.compiler import compile_spec  # floe-core
from floe_dagster.assets import create_assets  # floe-dagster (WRONG!)

def test_integration():
    artifacts = compile_spec(...)
    assets = create_assets(artifacts)  # Testing TWO packages!
```

**Fix**: Move to `tests/contract/test_core_to_dagster_contract.py`

### ❌ Anti-Pattern 2: Integration Tests in Unit Directories

```python
# ❌ WRONG - In plugins/floe-catalog-polaris/tests/unit/test_catalog_integration.py
import requests  # External dependency!

def test_catalog_creation():
    response = requests.post("http://polaris:8181/catalog")  # REAL SERVICE CALL!
    assert response.status_code == 200
```

**Fix**: Move to `plugins/floe-catalog-polaris/tests/integration/test_catalog.py`

### ❌ Anti-Pattern 3: Contract Tests in Package Directories

```python
# ❌ WRONG - In floe-core/tests/contract/test_compiled_artifacts.py
def test_compiled_artifacts_schema():
    """This should be at ROOT level, not package level."""
    ...
```

**Fix**: Move to `tests/contract/test_compiled_artifacts_schema.py` (ROOT)

### ❌ Anti-Pattern 4: Single-Package Test in Root

```python
# ❌ WRONG - In tests/integration/test_polaris_catalog.py
from floe_polaris.catalog import create_catalog  # ONLY floe-polaris

def test_create_catalog():
    catalog = create_catalog(name="test")
    assert catalog is not None
```

**Fix**: Move to `plugins/floe-catalog-polaris/tests/integration/test_catalog.py`

## Naming Conventions (ENFORCED)

### Test Files

- ✅ `test_*.py` (pytest discovery)
- ❌ `*_test.py` (not pytest default)

### Test Functions

- ✅ `def test_create_catalog():`
- ✅ `def test_create_catalog_invalid_name():`
- ✅ `async def test_async_operation():`
- ❌ `def it_creates_catalog():` (not pytest)

### Test Classes (optional grouping)

- ✅ `class TestCatalogOperations:`
- ✅ `class TestOAuth2Authentication:`
- ❌ `class CatalogTest:` (confusing)

## Directory Structure Validation

These checks are enforced by `/sw-verify`:

### DIR-001: No `__init__.py` in test directories

```
❌ floe-core/tests/__init__.py
✅ floe-core/tests/conftest.py
```

**Why**: pytest `--import-mode=importlib` causes namespace collisions

### DIR-002: Tests in correct tier directory

```
❌ plugins/floe-catalog-polaris/tests/unit/test_catalog_integration.py  # Integration in unit/
✅ plugins/floe-catalog-polaris/tests/integration/test_catalog_integration.py
```

**Detection**: Check for markers vs directory mismatch

### DIR-003: Integration tests inherit from IntegrationTestBase

```
❌ class TestPolarisCatalog:  # In tests/integration/
✅ class TestPolarisCatalog(IntegrationTestBase):
```

**Why**: Context-aware service resolution, namespace generation

### DIR-004: No service imports in unit tests

```python
# In tests/unit/:
❌ from docker import DockerClient
❌ from pyiceberg.catalog import load_catalog
❌ import requests
✅ from unittest.mock import Mock
✅ from floe_core.schemas import FloeSpec
```

**Detection**: AST import analysis for unit test files

### DIR-005: Package vs root test placement

```
# Package-level: Tests ONLY that package
✅ floe-core/tests/unit/test_compiler.py
✅ plugins/floe-catalog-polaris/tests/integration/test_catalog.py

# Root-level: Tests MULTIPLE packages
✅ tests/contract/test_core_to_dagster_contract.py
✅ tests/e2e/test_demo_flow.py

# WRONG: Single-package test in root
❌ tests/integration/test_polaris_catalog.py  # Move to plugins/floe-catalog-polaris/tests/integration/
```

**Detection**: Heuristic - check imports in root-level tests

### DIR-006: Contract tests exist

```
✅ tests/contract/test_compiled_artifacts_schema.py
✅ tests/contract/test_core_to_dagster_contract.py
✅ tests/contract/test_core_to_dbt_contract.py
```

**Why**: Contracts are regression baseline

## References

**Python Monorepo Best Practices**:
- [Python Monorepo: Structure and Tooling (Tweag)](https://www.tweag.io/blog/2023-04-04-python-monorepo-1/)
- [Python Monorepos (Graphite)](https://graphite.dev/guides/python-monorepos)
- [Building a Monorepo with Python (Earthly)](https://earthly.dev/blog/python-monorepo/)

**K8s Testing Patterns**:
- [Kubetest Documentation](https://kubetest.readthedocs.io/)
- [Testing Kubernetes Applications with Pytest + Testkube](https://testkube.io/blog/testing-kubernetes-applications-with-pytest-and-testkube-a-complete-guide)
- [Typical Directory Structure for Python Tests](https://gist.github.com/tasdikrahman/2bdb3fb31136a3768fac)
