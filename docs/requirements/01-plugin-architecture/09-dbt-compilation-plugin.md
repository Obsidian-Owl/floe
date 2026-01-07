# REQ-086 to REQ-095: DBT Runtime Plugin

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This requirement group defines the **DBTPlugin** interface that abstracts dbt compilation and execution across local (dbt-core) and remote (dbt Cloud, dbt Fusion) runtimes.

**Architectural Foundation**: ADR-0043 (dbt Compilation Abstraction Layer)

**Core Principle**: Support both open-source and commercial dbt offerings without compromising composability (ADR-0037).

**Execution Paradigms**:
- **Local/Embedded**: dbt-core via `dbtRunner` Python API (in-process, filesystem artifacts)
- **Remote/Managed**: dbt Cloud via REST API (K8s pods, S3 artifacts)
- **Future**: dbt Fusion via Rust bindings (performance-optimized, local)

---

## Requirements

### REQ-086: DBTPlugin Interface Definition **[New]**

**Requirement**: System MUST define `DBTPlugin` abstract base class in `floe-core/src/floe_core/plugin_interfaces.py` with the following abstract methods:

```python
@abstractmethod
def compile_project(
    self,
    project_dir: Path,
    profiles_dir: Path,
    target: str,
) -> Path:
    """Compile dbt project and return path to manifest.json."""
    pass

@abstractmethod
def run_models(
    self,
    project_dir: Path,
    profiles_dir: Path,
    target: str,
    select: str | None = None,
    exclude: str | None = None,
    full_refresh: bool = False,
) -> DBTRunResult:
    """Execute dbt run command."""
    pass

@abstractmethod
def run_tests(
    self,
    project_dir: Path,
    profiles_dir: Path,
    target: str,
    select: str | None = None,
) -> DBTRunResult:
    """Execute dbt test command."""
    pass

@abstractmethod
def get_manifest(self, project_dir: Path) -> dict[str, Any]:
    """Retrieve dbt manifest.json (filesystem or API)."""
    pass

@abstractmethod
def get_run_results(self, project_dir: Path) -> dict[str, Any]:
    """Retrieve dbt run_results.json."""
    pass

@abstractmethod
def supports_parallel_execution(self) -> bool:
    """Indicate whether runtime supports parallel execution."""
    pass

@abstractmethod
def get_runtime_metadata(self) -> dict[str, Any]:
    """Return runtime-specific metadata for observability."""
    pass
```

**Rationale**: Provides stable interface contract despite dbt-core's "liable to change" dbtRunner API.

**Acceptance Criteria**:
- [ ] `DBTPlugin` class defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 7 abstract methods declared with type hints
- [ ] Docstrings follow Google-style format (Args, Returns, Raises, Examples)
- [ ] `DBTRunResult` Pydantic model defined with required fields:
  - `success: bool`
  - `manifest_path: Path`
  - `run_results_path: Path`
  - `catalog_path: Path | None`
  - `execution_time_seconds: float`
  - `models_run: int`
  - `tests_run: int`
  - `failures: int`
  - `metadata: dict[str, Any]`

**Enforcement**:
- mypy --strict validates type hints
- Contract tests verify ABC compliance (REQ-094)

**Constraints**:
- MUST inherit from ABC (abstract base class)
- MUST NOT import dbt-core or dbt Cloud libraries (plugin-agnostic)
- MUST define entry point group: `floe.dbt`

**Traceability**: ADR-0043 (dbt Compilation Abstraction Layer), ADR-0037 (Composability Principle)

---

### REQ-087: LocalDBTPlugin Implementation **[New]**

**Requirement**: System MUST provide `LocalDBTPlugin` implementation in `plugins/floe-dbt-local/` that wraps dbt-core `dbtRunner` API.

**Rationale**: Enables open-source dbt-core execution path with zero cost.

**Acceptance Criteria**:
- [ ] Package `plugins/floe-dbt-local/` created with standard structure
- [ ] `LocalDBTPlugin` class inherits from `DBTPlugin`
- [ ] All abstract methods implemented using `dbtRunner().invoke()`
- [ ] Entry point registered: `[project.entry-points."floe.dbt"]`
  ```toml
  local = "floe_dbt_local:LocalDBTPlugin"
  ```
- [ ] `compile_project()` returns `Path("target/manifest.json")`
- [ ] `run_models()` parses `run_results.json` and returns `DBTRunResult`
- [ ] `supports_parallel_execution()` returns `False` (dbtRunner not thread-safe)
- [ ] `get_runtime_metadata()` returns:
  ```python
  {
      "type": "local",
      "dbt_version": "<dbt-core version>",
      "python_version": "<sys.version>",
  }
  ```

**Enforcement**:
- Integration tests compile and run sample dbt project
- Contract tests verify ABC compliance
- pytest-timeout enforces 60s max compilation time

**Constraints**:
- MUST handle dbtRunner exceptions and wrap in `DBTCompilationError`, `DBTExecutionError`
- MUST log all dbt output to structured logs (OpenTelemetry)
- MUST NOT use subprocess or shell=True (use dbtRunner only)

**Dependencies**:
- `dbt-core>=1.8.0,<2.0.0` (PyPI)
- `dbt-duckdb>=1.8.0` (default adapter)

**Test Coverage**: `plugins/floe-dbt-local/tests/integration/test_local_runtime.py`

**Traceability**: ADR-0043 Section "LocalDBTPlugin Implementation"

---

### REQ-088: DBTCloudPlugin Implementation **[New]**

**Requirement**: System MUST provide `DBTCloudPlugin` implementation in `plugins/floe-dbt-cloud/` that wraps dbt Cloud Admin API and Discovery API.

**Rationale**: Enables commercial dbt Cloud execution with remote job scheduling and metadata access.

**Acceptance Criteria**:
- [ ] Package `plugins/floe-dbt-cloud/` created
- [ ] `DBTCloudPlugin` class inherits from `DBTPlugin`
- [ ] Constructor accepts:
  - `account_id: str`
  - `api_token: SecretStr` (from SecretsPlugin)
  - `base_url: str = "https://cloud.getdbt.com/api/v2"`
- [ ] Entry point registered: `[project.entry-points."floe.dbt"]`
  ```toml
  cloud = "floe_dbt_cloud:DBTCloudPlugin"
  ```
- [ ] `compile_project()` triggers dbt Cloud job via Admin API POST `/accounts/{account_id}/jobs/{job_id}/run/`
- [ ] `run_models()` triggers run job with optional `steps_override` for select/exclude
- [ ] Job polling uses Admin API GET `/accounts/{account_id}/runs/{run_id}/` with exponential backoff
- [ ] Artifacts retrieved via Admin API GET `/accounts/{account_id}/runs/{run_id}/artifacts/{path}`
- [ ] Artifacts cached in `.floe/dbt-cloud-cache/{run_id}/` for offline access
- [ ] `get_manifest()` fetches via Discovery API (GraphQL) for rich metadata:
  ```graphql
  query GetManifest($environmentId: Int!) {
    environment(id: $environmentId) {
      applied {
        manifest
      }
    }
  }
  ```
- [ ] `supports_parallel_execution()` returns `True` (remote isolation)

**Enforcement**:
- Integration tests use dbt Cloud sandbox account
- Mock API responses for unit tests (httpx-mock)
- Retry logic with 3 attempts, exponential backoff (2s, 4s, 8s)

**Constraints**:
- MUST use httpx client with connection pooling and timeouts
- MUST validate API responses with Pydantic models
- MUST NOT hardcode job IDs (configure via manifest.yaml)
- FORBIDDEN: Direct Git operations (dbt Cloud handles Git sync)

**Configuration Schema** (manifest.yaml):
```yaml
plugins:
  dbt_runtime: cloud
  dbt_runtime_config:
    cloud:
      account_id: "12345"
      api_token_ref: "dbt-cloud-api-token"  # SecretsPlugin reference
      job_ids:
        compile: 67890
        run: 67891
        test: 67892
```

**Dependencies**:
- `httpx>=0.27.0` (async HTTP client)
- `pydantic>=2.0.0` (API response validation)

**Test Coverage**: `plugins/floe-dbt-cloud/tests/integration/test_cloud_runtime.py`

**Traceability**: ADR-0043 Section "DBTCloudPlugin Implementation"

---

### REQ-089: DBTFusionPlugin Placeholder **[New]**

**Requirement**: System MUST provide `DBTFusionPlugin` stub in `plugins/floe-dbt-fusion/` with all methods raising `NotImplementedError`.

**Rationale**: Prepares integration path for dbt Fusion (Rust-based runtime) when Python bindings become available.

**Acceptance Criteria**:
- [ ] Package `plugins/floe-dbt-fusion/` created
- [ ] `DBTFusionPlugin` class inherits from `DBTPlugin`
- [ ] All abstract methods raise:
  ```python
  raise NotImplementedError(
      "dbt Fusion Python bindings not yet available. "
      "Track progress: https://github.com/dbt-labs/dbt-fusion/issues/10"
  )
  ```
- [ ] Entry point registered but plugin discovery logs warning:
  ```
  WARNING: DBTFusionPlugin not yet implemented. Use 'local' or 'cloud' runtime.
  ```

**Enforcement**:
- Contract tests skip DBTFusionPlugin (`@pytest.mark.skip`)
- Documentation clearly states "Future implementation"

**Constraints**:
- MUST NOT attempt to load Rust bindings (not yet available)
- README.md MUST link to dbt Fusion GitHub repository

**Traceability**: ADR-0043 Section "DBTFusionPlugin (Future Path)"

---

### REQ-090: OrchestratorPlugin Integration **[Evolution]**

**Requirement**: System MUST update `OrchestratorPlugin.create_assets_from_artifacts()` method signature to accept `dbt_runtime_plugin: DBTPlugin` parameter.

**Rationale**: Decouples orchestration from dbt execution method (local vs cloud).

**BEFORE (Hardcoded)**:
```python
# ❌ FORBIDDEN - Direct dbtRunner usage
from dbt.cli.main import dbtRunner

@asset
def customers():
    dbt = dbtRunner()
    dbt.invoke(["run", "--select", "customers"])
```

**AFTER (Plugin-Based)**:
```python
# ✅ CORRECT - Via DBTPlugin
@asset
def customers(context):
    dbt_runtime = context.resources.dbt_runtime  # Injected by OrchestratorPlugin
    result = dbt_runtime.run_models(
        project_dir=Path("/opt/dbt/project"),
        profiles_dir=Path("/opt/dbt/profiles"),
        target="dev",
        select="customers",
    )
    context.log_metadata({"models_run": result.models_run})
```

**Acceptance Criteria**:
- [ ] `create_assets_from_artifacts()` signature updated in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] DagsterOrchestratorPlugin injects `dbt_runtime` as Dagster resource
- [ ] All dbt invocations use `dbt_runtime.run_models()` instead of `dbtRunner()`
- [ ] Assets consume `DBTRunResult` (standardized) not dbtRunner result objects

**Enforcement**:
- Contract tests verify Dagster assets receive `dbt_runtime` resource
- Integration tests validate end-to-end dbt execution via plugin

**Constraints**:
- OrchestratorPlugin MUST NOT import dbt-core or dbt Cloud libraries directly
- MUST resolve `dbt_runtime` plugin from PluginRegistry

**Traceability**: ADR-0043 Section "OrchestratorPlugin Integration"

---

### REQ-091: Configuration Schema Extension **[New]**

**Requirement**: System MUST extend `manifest.yaml` schema to support dbt runtime selection.

**Schema Addition**:
```yaml
# manifest.yaml
plugins:
  dbt_runtime: local  # or cloud, fusion

  dbt_runtime_config:
    # Local runtime configuration
    local:
      dbt_version: "1.8.0"
      python_version: "3.11"
      parallel_execution: false  # dbtRunner limitation

    # Cloud runtime configuration
    cloud:
      account_id: "12345"
      api_token_ref: "dbt-cloud-api-token"  # SecretReference
      base_url: "https://cloud.getdbt.com/api/v2"
      job_ids:
        compile: 67890
        run: 67891
        test: 67892
      poll_interval_seconds: 5
      timeout_seconds: 3600

    # Fusion runtime configuration (placeholder)
    fusion:
      rust_bindings_path: "/opt/dbt-fusion/libdbt.so"
```

**Acceptance Criteria**:
- [ ] Pydantic model `DBTRuntimeConfig` defined in `floe-core/src/floe_core/schemas.py`
- [ ] Validation ensures `plugins.dbt_runtime` is one of: `["local", "cloud", "fusion"]`
- [ ] Validation ensures corresponding config section exists (e.g., if `dbt_runtime: cloud`, `dbt_runtime_config.cloud` MUST be present)
- [ ] `api_token_ref` resolves via SecretsPlugin (REQ-076-080)
- [ ] Compiler validates runtime availability (e.g., error if `cloud` selected but no API token)

**Enforcement**:
- Pydantic validation at compile-time
- PolicyEnforcer checks dbt runtime prerequisites (REQ-200)

**Constraints**:
- MUST NOT hardcode secrets (use SecretReference pattern)
- Data engineers CANNOT override dbt runtime (platform team decision)

**Traceability**: ADR-0043 Section "Configuration Schema"

---

### REQ-092: Artifact Caching Strategy **[New]**

**Requirement**: System MUST implement artifact caching for remote dbt runtimes to enable offline access.

**Cache Structure**:
```
.floe/dbt-cloud-cache/
├── {run_id}/
│   ├── manifest.json
│   ├── run_results.json
│   ├── catalog.json
│   └── metadata.json  # Cache timestamp, account_id, job_id
```

**Rationale**: dbt Cloud artifacts should be accessible even when network is unavailable (e.g., local development).

**Acceptance Criteria**:
- [ ] `DBTCloudPlugin.get_manifest()` checks cache before API request
- [ ] Cache TTL: 24 hours (configurable via `manifest.yaml`)
- [ ] Cache invalidation on explicit `floe compile --no-cache` flag
- [ ] Cache metadata includes:
  ```json
  {
    "cached_at": "2025-01-06T10:00:00Z",
    "run_id": "12345",
    "account_id": "67890",
    "job_id": "11111",
    "artifacts": ["manifest.json", "run_results.json", "catalog.json"]
  }
  ```
- [ ] `.gitignore` includes `.floe/dbt-cloud-cache/`

**Enforcement**:
- Integration tests verify cache behavior (hit/miss)
- Test cache expiration logic

**Constraints**:
- Cache MUST be local only (no shared cache across developers)
- MUST NOT cache when `FLOE_DISABLE_CACHE=true` environment variable set

**Traceability**: ADR-0043 Section "DBTCloudPlugin Implementation"

---

### REQ-093: Parallel Execution Safety **[New]**

**Requirement**: System MUST prevent concurrent dbt executions when using LocalDBTPlugin.

**Rationale**: dbtRunner is NOT thread-safe per dbt documentation.

**Implementation Pattern**:
```python
import threading

class LocalDBTPlugin(DBTPlugin):
    _execution_lock = threading.Lock()

    def run_models(self, ...) -> DBTRunResult:
        with self._execution_lock:
            # Acquire lock - blocks if another run in progress
            result = self.dbt.invoke([...])
        return result
```

**Acceptance Criteria**:
- [ ] `LocalDBTPlugin` implements `threading.Lock()` for all dbt invocations
- [ ] `supports_parallel_execution()` returns `False`
- [ ] OrchestratorPlugin respects `supports_parallel_execution()` flag:
  - If `False`: Serialize dbt asset execution (max_workers=1)
  - If `True`: Allow parallel execution (max_workers=N)
- [ ] Integration test validates lock behavior (attempt concurrent runs, verify serialization)

**Enforcement**:
- Contract test: `test_local_runtime_serializes_execution()`
- Load test: 10 concurrent dbt runs, verify no crashes

**Constraints**:
- Lock MUST be class-level (shared across instances)
- MUST timeout after 3600s (1 hour) with `DBTExecutionTimeout` error

**Traceability**: ADR-0043 Section "Implementation Patterns" (dbtRunner limitations)

---

### REQ-094: Plugin Compliance Tests **[New]**

**Requirement**: System MUST define compliance test suite for `DBTPlugin` implementations.

**Test Suite**: `tests/contract/test_dbt_runtime_plugin.py`

```python
import pytest
from floe_core.plugin_interfaces import DBTPlugin
from floe_core.plugin_registry import PluginRegistry

@pytest.mark.parametrize("runtime", ["local", "cloud"])
def test_dbt_runtime_plugin_compliance(runtime: str):
    """Verify DBTPlugin implementations satisfy ABC."""
    registry = PluginRegistry()
    plugin = registry.get_plugin("dbt", runtime)

    # ABC compliance
    assert isinstance(plugin, DBTPlugin)

    # All abstract methods callable
    assert callable(plugin.compile_project)
    assert callable(plugin.run_models)
    assert callable(plugin.run_tests)
    assert callable(plugin.get_manifest)
    assert callable(plugin.get_run_results)
    assert callable(plugin.supports_parallel_execution)
    assert callable(plugin.get_runtime_metadata)

    # Type hints present
    import inspect
    sig = inspect.signature(plugin.compile_project)
    assert sig.return_annotation == Path

@pytest.mark.integration
def test_dbt_runtime_compile_and_run(tmp_path: Path):
    """Integration test: compile and run dbt project."""
    project_dir = setup_test_dbt_project(tmp_path)
    profiles_dir = setup_test_profiles(tmp_path)

    for runtime in ["local"]:  # Cloud requires API credentials
        plugin = PluginRegistry().get_plugin("dbt", runtime)

        # Compile
        manifest_path = plugin.compile_project(
            project_dir=project_dir,
            profiles_dir=profiles_dir,
            target="dev",
        )
        assert manifest_path.exists()

        # Run
        result = plugin.run_models(
            project_dir=project_dir,
            profiles_dir=profiles_dir,
            target="dev",
        )
        assert result.success
        assert result.models_run > 0
        assert result.manifest_path.exists()
```

**Acceptance Criteria**:
- [ ] Contract tests cover all 7 abstract methods
- [ ] Integration tests compile and run sample dbt project
- [ ] Tests run in K8s (Kind cluster) per ADR-0017
- [ ] Test coverage > 90% for plugin interfaces

**Enforcement**:
- CI pipeline runs contract tests on every PR
- SonarQube quality gate requires >80% coverage

**Traceability**: ADR-0043 Section "Testing Strategy"

---

### REQ-095: Documentation and Migration Guide **[New]**

**Requirement**: System MUST provide comprehensive documentation for dbt runtime plugin usage.

**Documentation Files**:
1. **docs/architecture/plugin-architecture.md** - DBTPlugin ABC reference
2. **docs/guides/dbt-runtime-selection.md** - Platform team guide (NEW)
3. **plugins/floe-dbt-local/README.md** - Local runtime setup
4. **plugins/floe-dbt-cloud/README.md** - Cloud runtime setup (credentials, job IDs)
5. **MIGRATION.md** - Migration from hardcoded dbtRunner to DBTPlugin

**Migration Guide Template**:
```markdown
# Migrating from Hardcoded dbtRunner to DBTPlugin

## Before (Epic 2 - MVP)

```python
from dbt.cli.main import dbtRunner

@asset
def customers():
    dbt = dbtRunner()
    dbt.invoke(["run", "--select", "customers"])
```

## After (Epic 3 - Plugin Architecture)

```python
@asset
def customers(context):
    dbt_runtime = context.resources.dbt_runtime
    result = dbt_runtime.run_models(
        project_dir=Path("/opt/dbt/project"),
        profiles_dir=Path("/opt/dbt/profiles"),
        target="dev",
        select="customers",
    )
    context.log_metadata({"models_run": result.models_run})
```

## Platform Configuration

**manifest.yaml**:
```yaml
plugins:
  dbt_runtime: local  # Start with local for backward compatibility
```

## Rollout Strategy

1. Epic 3: Extract LocalDBTPlugin (drop-in replacement)
2. Epic 8: Add DBTCloudPlugin (opt-in for teams with dbt Cloud licenses)
3. Future: DBTFusionPlugin when Rust bindings available
```

**Acceptance Criteria**:
- [ ] All documentation files created
- [ ] Migration guide tested against real codebase
- [ ] Examples use actual manifest.yaml snippets
- [ ] Troubleshooting section covers common errors:
  - "dbtRunner not found" → Install dbt-core
  - "dbt Cloud API 401 Unauthorized" → Check api_token_ref
  - "Concurrent execution error" → Verify supports_parallel_execution()

**Enforcement**:
- Lychee link checker validates all documentation links
- Documentation review required for PR approval

**Traceability**: ADR-0043 Section "Migration Strategy"

---

## Domain Acceptance Criteria

Domain 01 Plugin Architecture (dbt Compilation) is complete when:

- [ ] REQ-086: DBTPlugin ABC defined in floe-core
- [ ] REQ-087: LocalDBTPlugin implemented and tested
- [ ] REQ-088: DBTCloudPlugin implemented and tested
- [ ] REQ-089: DBTFusionPlugin stub created
- [ ] REQ-090: OrchestratorPlugin updated to use DBTPlugin
- [ ] REQ-091: manifest.yaml schema extended
- [ ] REQ-092: Artifact caching strategy implemented
- [ ] REQ-093: Parallel execution safety enforced
- [ ] REQ-094: Compliance tests pass with >90% coverage
- [ ] REQ-095: Documentation and migration guide complete
- [ ] All contract tests pass (`tests/contract/test_dbt_runtime_plugin.py`)
- [ ] All integration tests pass (LocalDBTPlugin + DBTCloudPlugin)
- [ ] ADR-0043 backreferences these requirements

## Epic Mapping

**Epic 3: Plugin Interface Extraction**
- REQ-086: DBTPlugin ABC definition
- REQ-087: LocalDBTPlugin implementation (drop-in replacement for hardcoded dbtRunner)
- REQ-090: OrchestratorPlugin integration
- REQ-091: Configuration schema (local runtime only)
- REQ-093: Parallel execution safety
- REQ-094: Contract tests
- REQ-095: Documentation (local runtime)

**Epic 8: Production Hardening**
- REQ-088: DBTCloudPlugin implementation
- REQ-091: Configuration schema (cloud runtime)
- REQ-092: Artifact caching
- REQ-095: Documentation (cloud runtime, migration guide)

**Future**
- REQ-089: DBTFusionPlugin (when Python bindings available)

---

## Files to Create/Update

**Create**:
- `floe-core/src/floe_core/plugin_interfaces.py` - Add `DBTPlugin` ABC, `DBTRunResult` model
- `plugins/floe-dbt-local/` - LocalDBTPlugin implementation
- `plugins/floe-dbt-cloud/` - DBTCloudPlugin implementation
- `plugins/floe-dbt-fusion/` - DBTFusionPlugin stub
- `tests/contract/test_dbt_runtime_plugin.py` - Compliance tests
- `docs/guides/dbt-runtime-selection.md` - Platform team guide

**Update**:
- `floe-core/src/floe_core/schemas.py` - Add `DBTRuntimeConfig` Pydantic model
- `floe-dagster/src/floe_dagster/assets.py` - Use DBTPlugin instead of dbtRunner
- `docs/architecture/plugin-architecture.md` - Add DBTPlugin section
- `docs/plan/requirements/01-plugin-architecture/README.md` - Update plugin count (11 → 12)
- `MIGRATION.md` - Add dbtRunner → DBTPlugin migration guide

---

## Notes

- **Backward Compatibility**: LocalDBTPlugin is drop-in replacement for existing hardcoded dbtRunner usage
- **Breaking Changes**: NONE for Epic 3 (hardcoded→plugin migration invisible to users)
- **Commercial Support**: DBTCloudPlugin is opt-in (requires dbt Cloud license)
- **Future-Proofing**: DBTFusionPlugin entry point reserved (stub implementation until Rust bindings available)
- **Design Decision**: Intentionally NOT supporting dbt Semantic Layer APIs (Cube.dev handles consumption per ADR-0001)
