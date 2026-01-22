# Testing Guide for floe

**Philosophy**: K8s-native testing for production parity
**Approach**: Local → CI → Staging → Production (all Kubernetes)
**Coverage Target**: >80% (enforced in CI)

---

## Quick Start

```bash
# Unit tests (fast, no K8s required)
make test-unit

# All tests in K8s (Kind cluster)
make test

# Full CI checks (lint, type, security, test)
make check

# Pre-PR test quality review
/speckit.test-review
```

---

## K8s-Native Testing

**All integration and E2E tests run in Kubernetes** (Kind cluster locally, managed K8s in CI/prod).

### Why K8s-Native?

| Benefit | Description |
|---------|-------------|
| **Production Parity** | Same environment locally, CI, staging, prod |
| **Service Discovery** | Tests use K8s DNS (`polaris.default.svc.cluster.local`) |
| **Resource Management** | K8s handles service lifecycle, networking, secrets |
| **Reproducibility** | Consistent behavior across all environments |

### Test Execution Environments

| Test Type | Execution Environment | Services Required |
|-----------|----------------------|-------------------|
| Unit | Host (`uv run pytest`) | None (mocks only) |
| Contract | Host (`uv run pytest`) | None |
| **Integration** | **Kind cluster (K8s)** | Polaris, PostgreSQL, S3 (LocalStack) |
| **E2E** | **Kind cluster (K8s)** | Full platform stack |

---

## Canonical Test Structure

### Package-Level Tests

```
packages/floe-<name>/
├── src/floe_<name>/          # Source code (src-layout)
├── tests/                    # NO __init__.py (namespace package)
│   ├── conftest.py           # Package fixtures
│   ├── unit/                 # Fast, isolated (host)
│   │   ├── conftest.py
│   │   └── test_*.py
│   ├── integration/          # Real services (K8s)
│   │   ├── conftest.py
│   │   └── test_*.py
│   └── e2e/                  # Full workflows (K8s)
│       └── test_*.py
└── pyproject.toml            # Must configure pythonpath
```

**Required pytest config** in `pyproject.toml` for src-layout packages:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]          # Required for pytest to find src/floe_<name>
```

### Root-Level Tests (Cross-Package)

```
tests/
├── conftest.py
├── contract/                 # MANDATORY: Cross-package contracts
│   ├── test_compiled_artifacts_schema.py
│   ├── test_core_to_dagster_contract.py
│   └── test_core_to_dbt_contract.py
└── e2e/                      # OPTIONAL: Full platform E2E
    └── test_demo_flow.py
```

**Rule**: Root tests ONLY for cross-package validation. Single-package tests go in `packages/*/tests/`.

### Test Tier Definitions

| Tier | Directory | Execution | Services | Markers |
|------|-----------|-----------|----------|---------|
| **Unit** | `tests/unit/` | Host (pytest, fast) | None (mocks) | None |
| **Contract** | `tests/contract/` | Host (pytest, fast) | None | `@pytest.mark.contract` |
| **Integration** | `tests/integration/` | Kind (K8s) | Real services | `@pytest.mark.integration`<br>`@pytest.mark.requirement()` |
| **E2E** | `tests/e2e/` | Kind (K8s) | Full platform | `@pytest.mark.e2e`<br>`@pytest.mark.requirement()` |

---

## Running Tests

### Local Development

```bash
# Unit tests only (fastest)
make test-unit

# All tests in K8s
make test

# Specific package
uv run pytest packages/floe-core/tests/unit/ -v

# Specific marker
uv run pytest -m contract -v
```

### CI/CD Pipeline

Tests run in stages:

1. **Lint & Type Check** (< 2 min)
   ```bash
   ruff check .
   mypy --strict packages/
   ```

2. **Unit Tests** (< 5 min, parallel by Python version)
   ```bash
   uv run pytest -m "not integration and not slow" --cov
   ```

3. **Contract Tests** (< 3 min)
   ```bash
   uv run pytest -m contract
   ```

4. **Integration Tests** (< 10 min, K8s)
   ```bash
   make test  # Kind cluster with services
   ```

---

## Pre-PR Test Review

Before creating a PR, validate test quality:

```bash
/speckit.test-review
```

**Validates**:
- ✅ Test quality (no skips, no hardcoded sleep, type hints, docstrings)
- ✅ Requirement traceability (100% marker coverage)
- ✅ Security checks (no hardcoded secrets)
- ✅ Contract regression (stable package interfaces)
- ✅ Architecture compliance (framework patterns, not pipeline tests)
- ✅ Directory structure (package vs root placement)

**Output**: Structured findings table with severity levels (CRITICAL, MAJOR, MINOR)

**See**: `.claude/commands/speckit.test-review.md`

---

## Requirement Traceability

### The @pytest.mark.requirement Marker

**Every integration test MUST link to a requirement** for full traceability:

```python
@pytest.mark.requirement("9c-FR-001")  # Epic-scoped format
@pytest.mark.integration
def test_create_catalog():
    """Test catalog creation with OAuth2 authentication.

    Covers:
    - 9c-FR-001: Integration tests require K8s-native fixtures
    """
    catalog = create_catalog(name="test", warehouse="warehouse")
    assert catalog is not None
```

### Requirement ID Format

Use Epic-scoped format: `{epic}-FR-{number}`

| Example | Source |
|---------|--------|
| `9c-FR-001` | `specs/9c-testing-infra/checklists/requirements.md` |
| `4a-FR-015` | `specs/4a-compute-plugin/checklists/requirements.md` |

### Traceability Reports

```bash
# Full traceability report
python -m testing.traceability --all

# Enforce 100% coverage (CI gate)
python -m testing.traceability --all --threshold 100

# JSON output for CI
python -m testing.traceability --all --format json
```

**Coverage Requirement**: 100% MANDATORY before feature completion.

---

## Tests FAIL, Never Skip

**Skipped tests hide problems. If a test can't run, FIX the underlying issue.**

```python
# ❌ FORBIDDEN
@pytest.mark.skip("Service not available")
def test_something():
    ...

# ❌ FORBIDDEN
def test_something():
    if not service_available():
        pytest.skip("Service not available")  # NO!
    ...

# ✅ CORRECT - Test FAILS if infrastructure missing
def test_something(service_client):
    """Test requires service - FAILS if not available."""
    response = service_client.query(...)
    assert response.status_code == 200
```

**Why This Matters**:
1. Skipped tests are invisible failures
2. Skips accumulate silently ("just one skip" becomes 50)
3. Skips hide infrastructure rot
4. False confidence ("all tests pass" when half are skipped)

**Acceptable Skip Uses** (rare):
1. `pytest.importorskip("optional_library")` - genuinely optional dependencies
2. `@pytest.mark.skipif(sys.platform == "win32")` - literal platform impossibility

**See**: `.claude/rules/testing-standards.md#tests-fail-never-skip`

---

## K8s Test Infrastructure

### Kind Cluster Configuration

**Local**: Kind (Kubernetes in Docker)
**CI**: Kind on GitHub Actions runners
**Staging/Prod**: Managed K8s clusters

```bash
# Create Kind cluster and deploy services (all-in-one)
make kind-up          # Runs testing/k8s/setup-cluster.sh

# Run tests
make test             # Unit tests + integration tests

# Cleanup
make kind-down        # Runs testing/k8s/cleanup-cluster.sh
```

**Note**: Services are deployed via raw K8s manifests in `testing/k8s/services/`, not Helm.
This avoids circular dependencies with Helm chart development.

### Test Services (Deployed via Raw K8s Manifests)

| Service | Purpose | Manifest |
|---------|---------|----------|
| PostgreSQL | Catalog metadata, orchestrator DB | `testing/k8s/services/postgres.yaml` |
| Polaris | Iceberg REST catalog | `testing/k8s/services/polaris.yaml` |
| MinIO | S3-compatible object storage | `testing/k8s/services/minio.yaml` |
| Dagster | Orchestration (webserver, daemon) | `testing/k8s/services/dagster.yaml` |

**Service Discovery**: Tests use K8s DNS (`polaris.floe-test.svc.cluster.local`)

### Development Workflow

```bash
# Start cluster and services (persistent)
make kind-up          # Creates cluster, deploys services

# Run unit tests only (fast, no K8s required)
make test-unit        # ~30 seconds

# Run all tests (unit + integration)
make test             # Requires Kind cluster

# Full CI checks locally
make check            # lint + typecheck + test

# Cleanup when done
make kind-down        # Destroys cluster and artifacts
```

---

## Test Fixtures and Base Classes

### BaseProfileGeneratorTests

> **Coming in Epic 5A (dbt Plugin)**: This base class will be delivered as part of the
> dbt plugin implementation. It provides automatic test inheritance for profile generators.
> The example below shows the intended usage pattern.

All dbt profile generator tests will inherit from this base class:

```python
from testing.base_classes.adapter_test_base import BaseProfileGeneratorTests

class TestDuckDBProfileGenerator(BaseProfileGeneratorTests):
    """Test suite for DuckDB profile generation."""

    @pytest.fixture
    def generator(self) -> ProfileGenerator:
        from floe_dbt.profiles.duckdb import DuckDBProfileGenerator
        return DuckDBProfileGenerator()

    @property
    def target_type(self) -> str:
        return "duckdb"

    @property
    def required_fields(self) -> set[str]:
        return {"type", "path", "threads"}

    def get_minimal_artifacts(self) -> dict[str, Any]:
        return {
            "version": "1.0.0",
            "compute": {
                "target": "duckdb",
                "properties": {"path": "warehouse/dev.duckdb"},
            },
            "transforms": [],
        }
```

**Inherited Tests** (automatic):
1. `test_implements_protocol` - Protocol compliance
2. `test_generate_returns_dict` - Return type validation
3. `test_generate_includes_target_name` - Target name present
4. `test_generate_has_correct_type` - Correct adapter type
5. `test_generate_has_required_fields` - Required fields present
6. `test_generate_uses_config_threads` - Thread configuration
7. `test_generate_custom_target_name` - Custom naming
8. `test_generate_with_different_environments` - Environment support

### IntegrationTestBase

Integration tests inherit from `IntegrationTestBase` for K8s-aware helpers:

```python
from testing.base_classes.integration_test_base import IntegrationTestBase

class TestPolarisIntegration(IntegrationTestBase):
    """Integration tests for Polaris catalog."""

    required_services = [("polaris", 8181), ("localstack", 4566)]

    @pytest.mark.requirement("4c-FR-001")
    @pytest.mark.integration
    def test_create_catalog(self) -> None:
        """Test catalog creation with Polaris."""
        # Auto-checks infrastructure
        self.check_infrastructure("polaris", 8181)

        # Generate unique namespace (isolation)
        namespace = self.generate_unique_namespace("test_polaris")

        # Context-aware hostname
        host = self.get_service_host("polaris")  # Returns K8s DNS name

        catalog = create_catalog(
            name=f"{namespace}_catalog",
            uri=f"http://{host}:8181/api/catalog"
        )
        assert catalog is not None
```

**Methods**:
- `check_infrastructure(service, port)` - Verify service availability
- `generate_unique_namespace(prefix)` - Create unique IDs
- `get_service_host(service)` - Get K8s DNS name

### BasePluginDiscoveryTests

All plugin discovery tests should inherit from this base class to get standard
entry point and metadata validation tests:

```python
from typing import Any, ClassVar

import pytest
from pydantic import SecretStr

from testing.base_classes import BasePluginDiscoveryTests


class TestMyPluginDiscovery(BasePluginDiscoveryTests):
    """Test suite for MyPlugin entry point discovery."""

    # Required class attributes
    entry_point_group: ClassVar[str] = "floe.computes"
    expected_name: ClassVar[str] = "my_plugin"
    expected_module_prefix: ClassVar[str] = "floe_my_plugin"
    expected_class_name: ClassVar[str] = "MyPlugin"

    @property
    def expected_plugin_abc(self) -> type[Any]:
        """Return the expected ABC for type checking."""
        from floe_core.plugins.compute import ComputePlugin
        return ComputePlugin

    def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
        """Create plugin with required configuration.

        Override this if your plugin requires config to instantiate.
        """
        from floe_my_plugin import MyPluginConfig

        config = MyPluginConfig(
            api_key=SecretStr("test-key"),
        )
        return plugin_class(config=config)

    # Add plugin-specific tests below the base class tests
    @pytest.mark.requirement("MY-FR-001")
    def test_plugin_has_specific_methods(self) -> None:
        """Test plugin has domain-specific methods."""
        # ...
```

**Inherited Tests** (automatic):
1. `test_entry_point_is_registered` - Entry point exists in group
2. `test_exactly_one_entry_point` - No duplicate registrations
3. `test_entry_point_module_path` - Correct module reference
4. `test_plugin_loads_successfully` - Plugin class loads via entry point
5. `test_plugin_can_be_instantiated` - Plugin can be created
6. `test_instantiated_plugin_has_correct_name` - Name matches
7. `test_plugin_has_required_metadata_attributes` - PluginMetadata present
8. `test_plugin_metadata_values_not_none` - Metadata values populated
9. `test_plugin_inherits_from_expected_abc` - ABC compliance
10. `test_plugin_instance_is_abc_instance` - Instance type check
11. `test_plugin_has_lifecycle_methods` - startup/shutdown/health_check

### BaseHealthCheckTests

All plugin health check tests should inherit from this base class:

```python
from typing import Any

import pytest

from testing.base_classes import BaseHealthCheckTests


class TestMyPluginHealthCheck(BaseHealthCheckTests):
    """Test suite for MyPlugin health checks."""

    @pytest.fixture
    def unconnected_plugin(self) -> Any:
        """Return an uninitialized plugin instance."""
        from floe_my_plugin import MyPlugin, MyPluginConfig

        config = MyPluginConfig(host="localhost", port=8080)
        return MyPlugin(config=config)

    @pytest.fixture
    def connected_plugin(self, unconnected_plugin: Any) -> Any:
        """Return an initialized/connected plugin instance."""
        unconnected_plugin.startup()
        yield unconnected_plugin
        unconnected_plugin.shutdown()

    # Add plugin-specific health check tests below
    @pytest.mark.requirement("MY-FR-010")
    def test_health_check_reports_backend_version(
        self, connected_plugin: Any
    ) -> None:
        """Test health check includes backend version in details."""
        result = connected_plugin.health_check()
        assert "backend_version" in result.details
```

**Inherited Tests** (automatic):
1. `test_health_check_exists` - Method exists and callable
2. `test_health_check_returns_health_status` - Returns HealthStatus model
3. `test_health_check_reports_healthy_when_connected` - HEALTHY state
4. `test_health_check_reports_unhealthy_when_not_connected` - UNHEALTHY state
5. `test_health_check_includes_response_time` - response_time_ms in details
6. `test_health_check_completes_within_one_second` - Performance check
7. `test_health_check_includes_checked_at_timestamp` - Timestamp present
8. `test_health_check_accepts_timeout_parameter` - Timeout handling
9. `test_health_check_rejects_invalid_timeout_*` - Boundary validation
10. `test_health_check_does_not_raise_when_unhealthy` - Error handling
11. `test_health_check_includes_message` - Non-empty message

### Parametrized Test Patterns

Use `pytest.mark.parametrize` to reduce test duplication when testing
multiple scenarios with the same structure:

```python
import pytest


class TestDryRunMode:
    """Tests for dry-run mode behavior."""

    @pytest.mark.requirement("US7")
    @pytest.mark.parametrize(
        ("dry_run", "expected_passed", "expected_severity"),
        [
            pytest.param(True, True, "warning", id="dry_run_passes_with_warnings"),
            pytest.param(False, False, "error", id="normal_fails_with_errors"),
        ],
    )
    def test_dry_run_mode_behavior(
        self,
        strict_governance_config: GovernanceConfig,
        manifest_with_violation: dict[str, Any],
        dry_run: bool,
        expected_passed: bool,
        expected_severity: str,
    ) -> None:
        """Test dry-run vs normal mode behavior with violations.

        When dry_run=True: result.passed=True, violations are warnings
        When dry_run=False: result.passed=False, violations are errors
        """
        from floe_core.enforcement import PolicyEnforcer

        enforcer = PolicyEnforcer(governance_config=strict_governance_config)
        result = enforcer.enforce(manifest_with_violation, dry_run=dry_run)

        assert result.passed is expected_passed
        assert len(result.violations) > 0

        for violation in result.violations:
            assert violation.severity == expected_severity
```

**Guidelines**:
- Use `pytest.param(..., id="descriptive_name")` for readable test names
- Extract common fixtures to conftest.py
- Keep parameter tuples aligned for readability
- Document what each parameter combination tests

### Fixture Factory Patterns

Use fixture factories in `conftest.py` to create reusable, configurable test data:

```python
# packages/floe-core/tests/unit/enforcement/conftest.py
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_core.schemas.manifest import GovernanceConfig


@pytest.fixture
def strict_naming_governance_config() -> "GovernanceConfig":
    """Provide strict governance config with medallion naming enforcement."""
    from floe_core.schemas.governance import NamingConfig
    from floe_core.schemas.manifest import GovernanceConfig

    return GovernanceConfig(
        policy_enforcement_level="strict",
        naming=NamingConfig(
            pattern="medallion",
            enforcement="strict",
        ),
    )


@pytest.fixture
def dbt_manifest_with_naming_violation() -> dict[str, Any]:
    """Provide dbt manifest with a medallion naming violation."""
    return {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.my_project.bad_model_name": {
                "name": "bad_model_name",
                "resource_type": "model",
                "columns": {},
            },
        },
    }


@pytest.fixture
def dbt_manifest_compliant() -> dict[str, Any]:
    """Provide dbt manifest that is fully compliant with medallion naming."""
    return {
        "metadata": {"dbt_version": "1.8.0"},
        "nodes": {
            "model.my_project.bronze_orders": {
                "name": "bronze_orders",
                "resource_type": "model",
                "description": "Raw order data from source system",
                "columns": {},
            },
        },
    }
```

**Guidelines**:
- Place shared fixtures in the nearest `conftest.py`
- Use `TYPE_CHECKING` imports to avoid circular dependencies
- Return fully-configured objects, not builders
- Document what makes each fixture unique (e.g., "with violation", "compliant")
- Use descriptive fixture names that indicate the test scenario

---

## pytest Markers

Available markers (defined in `pyproject.toml`):

| Marker | Description | Example |
|--------|-------------|---------||
| `slow` | Tests taking > 1 second | `@pytest.mark.slow` |
| `integration` | Require external services (K8s) | `@pytest.mark.integration` |
| `contract` | Cross-package validation | `@pytest.mark.contract` |
| `e2e` | End-to-end pipeline tests | `@pytest.mark.e2e` |
| `requirement` | Links test to requirement | `@pytest.mark.requirement("9c-FR-001")` |

### Running by Marker

```bash
# Skip slow tests
uv run pytest -m "not slow" -v

# Only integration tests
uv run pytest -m integration -v

# Only contract tests
uv run pytest -m contract -v

# Exclude integration and slow
uv run pytest -m "not integration and not slow" -v
```

---

## Adding New Tests

### 1. Unit Test (Fast, Mocked)

```python
# packages/floe-core/tests/unit/test_compiler.py

def test_compile_minimal_spec():
    """Test compilation with minimal FloeSpec."""
    spec = FloeSpec(name="test", version="1.0.0")
    artifacts = compile_spec(spec)
    assert artifacts.version == "1.0.0"
```

### 2. Contract Test (Cross-Package)

```python
# tests/contract/test_compiled_artifacts_schema.py

@pytest.mark.contract
def test_schema_backward_compatible():
    """Verify schema changes are backward compatible."""
    current = CompiledArtifacts.model_json_schema()
    # Compare with baseline schema...
    assert current["properties"]["version"] is not None
```

### 3. Integration Test (K8s, Real Services)

```python
# packages/floe-polaris/tests/integration/test_catalog.py

from testing.base_classes.integration_test_base import IntegrationTestBase

class TestPolarisIntegration(IntegrationTestBase):
    """Integration tests for Polaris catalog."""

    required_services = [("polaris", 8181)]

    @pytest.mark.requirement("REQ-042")
    @pytest.mark.integration
    def test_create_catalog(self):
        """Test catalog creation succeeds with valid input."""
        self.check_infrastructure("polaris", 8181)
        namespace = self.generate_unique_namespace("test")

        catalog = create_catalog(
            name=f"{namespace}_catalog",
            warehouse="warehouse"
        )
        assert catalog is not None
```

---

## Coverage Requirements

**Minimum**: 80% coverage required (enforced in CI)

```bash
# Generate coverage report
uv run pytest --cov=packages/floe-core --cov-report=html

# View in browser
open htmlcov/index.html
```

**Coverage Targets**:
- Unit tests: >80%
- Integration tests: >70%
- Overall: >80%

---

## Troubleshooting

### Kind Cluster Issues

```bash
# Check cluster status
kind get clusters

# View cluster logs
kubectl cluster-info
kubectl get pods -A

# Recreate cluster
kind delete cluster
kind create cluster --config testing/k8s/kind-config.yaml
```

### Service Not Ready

```bash
# Check service health
kubectl get pods
kubectl describe pod <pod-name>
kubectl logs <pod-name>

# Wait for service
kubectl wait --for=condition=ready pod -l app=polaris --timeout=120s
```

### Test Failures in CI but Not Locally

**Likely Cause**: Environment differences

**Solution**:
1. Ensure Kind cluster config matches CI
2. Check service versions match
3. Verify resource limits sufficient
4. Review CI logs for specific errors

---

## References

- **Migration Plan**: `docs/plan/MIGRATION-ROADMAP.md` (Epic 2: K8s-Native Testing)
- **Test Organization Rules**: `.claude/rules/test-organization.md`
- **Testing Standards**: `.claude/rules/testing-standards.md`
- **Pre-PR Review Command**: `.claude/commands/speckit.test-review.md`
- **Kind Configuration**: `testing/k8s/kind-config.yaml`
- **Helm Values**: `testing/k8s/values-test.yaml`

---

**Remember**: All integration and E2E tests run in Kubernetes for production parity. Use `/speckit.test-review` before every PR.
