# ADR-0043: dbt Compilation Environment Abstraction

## Status

Accepted

## Context

floe requires a **production-grade dbt execution strategy** that supports both open-source and commercial dbt offerings without compromising composability principles (ADR-0037).

### Problem Statement

The current architecture assumes **local dbt-core execution** via `dbtRunner` (Python API, v1.5+). This creates several challenges for production deployments:

1. **Commercial dbt Limitations**: No support for dbt Cloud API execution (remote K8s pods, job scheduling)
2. **Metadata Access**: dbt-core has no metadata API; requires manual manifest.json parsing
3. **Scalability**: dbtRunner is NOT safe for parallel execution in the same process ([dbt docs](https://docs.getdbt.com/reference/programmatic-invocations))
4. **API Stability**: dbtRunner result objects are "not fully contracted and liable to change" ([dbt programmatic invocations](https://docs.getdbt.com/reference/programmatic-invocations))
5. **Future-Proofing**: No path to support dbt Fusion (Rust-based runtime, in development)

### dbt Landscape (2025-2026)

Research ([Datacoves](https://datacoves.com/post/dbt-core-key-differences), [dbt Cloud API docs](https://docs.getdbt.com/docs/dbt-cloud-apis/overview), [dltHub](https://dlthub.com/blog/dbt-runners-usage)) reveals three dbt execution paradigms:

| Offering | Execution Model | APIs | Pricing | Key Features |
|----------|----------------|------|---------|--------------|
| **dbt Core** (OSS) | Local in-process (dbtRunner) | None (manifest.json only) | Free | Programmatic Python API, local execution |
| **dbt Fusion** (OSS, Beta) | Rust-based CLI binary | CLI subprocess (PyO3 bindings planned) | Free | 30x faster parsing, built-in SQL validation, thread-safe ([Public Beta May 2025](https://docs.getdbt.com/blog/dbt-fusion-engine)) |
| **dbt Cloud** (Commercial) | Remote K8s pods | Admin API, Discovery API, Semantic Layer API | ~$100/dev/month (Team plan) | Job scheduling, metadata API, artifact storage |

**Critical Insight**: dbt-core, dbt Fusion, and dbt Cloud represent **different COMPILATION environments**, not execution engines:
- **dbt compiles SQL** (Jinja → SQL transpilation) - the WAREHOUSE executes SQL
- **dbt-core**: Local Python library, filesystem artifacts, synchronous dbtRunner API
- **dbt Fusion**: Local Rust binary, CLI subprocess, built-in static analysis
- **dbt Cloud**: Remote K8s service, REST API, asynchronous job execution

### Architectural Constraints

**ADR-0009 (dbt Owns SQL)** establishes:
> "Floe does not parse, transpile, or manage SQL dependencies. dbt owns ALL SQL transformation."

**ADR-0037 (Composability Principle)** requires:
> "Plugin architecture > configuration switches. If multiple implementations exist OR may exist, use plugin interface."

**ADR-0001 (Cube Semantic Layer)** decision:
> floe uses Cube.dev (not dbt Semantic Layer) for consumption APIs.

**Implication**: We need **dbt runtime abstraction** (OSS + commercial) but NOT dbt Semantic Layer APIs (handled by Cube).

---

## Decision

Introduce **DBTPlugin** as the **12th plugin type** in floe's plugin architecture.

**Entry Point**: `floe.dbt`

**Purpose**: Abstract dbt compilation environment (WHERE and HOW dbt compiles Jinja → SQL) across local (dbt-core, dbt Fusion) and remote (dbt Cloud) invocation methods.

**Naming Rationale**: "Compilation" not "Runtime" - floe manages:
- **Orchestration runtime**: OrchestratorPlugin (Dagster, Airflow, Step Functions, etc.)
- **Execution runtime**: ComputePlugin (Snowflake, DuckDB, BigQuery - where SQL executes)
- **Compilation**: dbt ONLY compiles Jinja → SQL. It does NOT manage runtime.

**Scope**:
- ✅ dbt project compilation (Jinja → SQL transpilation, manifest.json generation)
- ✅ SQL linting and validation (dialect-aware static analysis)
- ✅ SQL submission to warehouse (dbt submits compiled SQL, warehouse executes)
- ✅ Artifact retrieval (manifest.json, run_results.json, catalog.json)
- ✅ Metadata access (model timing, test results, lineage)
- ❌ SQL execution (warehouse responsibility, not dbt)
- ❌ Semantic Layer APIs (handled by Cube via ADR-0001)

---

## Plugin Interface Design

### DBTPlugin ABC

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from floe_core.schemas import ComputeConfig, DBTProjectConfig


class LintSeverity(Enum):
    """SQL linting severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class LintIssue(BaseModel):
    """Individual SQL linting issue."""
    file_path: str
    line: int
    column: int
    severity: LintSeverity
    rule_code: str
    message: str


class ProjectLintResult(BaseModel):
    """Project-wide SQL linting results."""
    total_issues: int
    errors: int
    warnings: int
    infos: int
    issues: list[LintIssue]
    passed: bool  # True if no errors (warnings allowed)


class DBTCompilationResult(BaseModel):
    """Standardized dbt compilation result (NOT execution - warehouse executes SQL)."""

    success: bool
    manifest_path: Path
    run_results_path: Path
    catalog_path: Path | None = None
    execution_time_seconds: float  # Time for dbt to compile + submit SQL
    models_run: int  # Models compiled and submitted to warehouse
    tests_run: int
    failures: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class DBTPlugin(ABC):
    """Abstract base class for dbt compilation environment implementations.

    Abstracts WHERE and HOW dbt compiles Jinja → SQL across:
    - Local: dbt-core (dbtRunner), dbt Fusion (CLI subprocess)
    - Remote: dbt Cloud (REST API)

    CRITICAL: dbt is a COMPILER, not an execution engine.
    - dbt compiles Jinja → SQL
    - dbt submits SQL to warehouse
    - Warehouse EXECUTES SQL (not dbt!)

    This plugin abstracts the COMPILATION environment, not execution runtime.
    """

    @abstractmethod
    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path:
        """Compile dbt project and return path to manifest.json.

        Args:
            project_dir: Path to dbt project root
            profiles_dir: Path to directory containing profiles.yml
            target: dbt target name (from profiles.yml)

        Returns:
            Path to compiled manifest.json

        Raises:
            DBTCompilationError: If compilation fails
        """
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
    ) -> DBTCompilationResult:
        """Execute dbt run command.

        Args:
            project_dir: Path to dbt project root
            profiles_dir: Path to directory containing profiles.yml
            target: dbt target name
            select: Model selection syntax (e.g., "tag:daily")
            exclude: Model exclusion syntax
            full_refresh: Force full table rebuilds

        Returns:
            Standardized run result with artifact paths
        """
        pass

    @abstractmethod
    def run_tests(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTCompilationResult:
        """Execute dbt test command.

        Args:
            project_dir: Path to dbt project root
            profiles_dir: Path to directory containing profiles.yml
            target: dbt target name
            select: Test selection syntax

        Returns:
            Standardized test result with artifact paths
        """
        pass

    @abstractmethod
    def get_manifest(
        self,
        project_dir: Path,
    ) -> dict[str, Any]:
        """Retrieve dbt manifest.json.

        For local runtimes: Read from filesystem
        For remote runtimes: Fetch via API

        Args:
            project_dir: Path to dbt project root

        Returns:
            Parsed manifest.json dictionary
        """
        pass

    @abstractmethod
    def get_run_results(
        self,
        project_dir: Path,
    ) -> dict[str, Any]:
        """Retrieve dbt run_results.json.

        Args:
            project_dir: Path to dbt project root

        Returns:
            Parsed run_results.json dictionary
        """
        pass

    @abstractmethod
    def supports_parallel_execution(self) -> bool:
        """Indicate whether this runtime supports parallel execution.

        Returns:
            True if safe to run multiple dbt commands concurrently
            False if execution must be serialized

        Note:
            - dbt-core (dbtRunner): Returns False (not thread-safe)
            - dbt Cloud API: Returns True (remote isolation)
        """
        pass

    @abstractmethod
    def get_runtime_metadata(self) -> dict[str, Any]:
        """Return runtime-specific metadata for observability.

        Returns:
            Dictionary with runtime type, version, configuration

        Examples:
            LocalDBTPlugin: {"type": "local", "dbt_version": "1.8.0"}
            DBTCloudPlugin: {"type": "cloud", "account_id": "12345"}
        """
        pass

    @abstractmethod
    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> ProjectLintResult:
        """Lint SQL files in dbt project with dialect-aware validation.

        Args:
            project_dir: Path to dbt project root
            profiles_dir: Path to directory containing profiles.yml
            target: dbt target name (determines SQL dialect)
            fix: Auto-fix issues if supported by linter

        Returns:
            ProjectLintResult with all detected issues

        Implementation Notes:
            - LocalDBTPlugin: Delegates to SQLFluff (external linter)
            - DBTFusionPlugin: Uses built-in static analysis (dbtf compile)
            - DBTCloudPlugin: TBD (research dbt Cloud linting API)

        Raises:
            DBTLintError: If linting process fails (not if SQL has issues)
        """
        pass

    @abstractmethod
    def supports_sql_linting(self) -> bool:
        """Indicate whether this compilation environment provides SQL linting.

        Returns:
            True if lint_project() is functional
            False if linting not available

        Examples:
            LocalDBTPlugin: True (via SQLFluff)
            DBTFusionPlugin: True (built-in static analysis)
            DBTCloudPlugin: TBD
        """
        pass
```

---

## Implementation Patterns

**Implementation Priority** (as of 2026-01-06):
1. **LocalDBTPlugin** (dbt-core + SQLFluff) - IMMEDIATE (Epic 3)
2. **DBTFusionPlugin** (dbt Fusion CLI + built-in linting) - IMMEDIATE (Epic 3)
3. **DBTCloudPlugin** (dbt Cloud API) - DEFERRED (Epic 8+)

---

### 1. LocalDBTPlugin (Open Source Path)

**Implementation**: Wraps dbt-core `dbtRunner` API + SQLFluff linting

```python
from dbt.cli.main import dbtRunner

class LocalDBTPlugin(DBTPlugin):
    """Local dbt-core execution via dbtRunner."""

    def __init__(self):
        self.dbt = dbtRunner()

    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str
    ) -> Path:
        """Compile using dbtRunner.invoke()."""
        result = self.dbt.invoke([
            "compile",
            "--project-dir", str(project_dir),
            "--profiles-dir", str(profiles_dir),
            "--target", target,
        ])

        if not result.success:
            raise DBTCompilationError(result.exception)

        return project_dir / "target" / "manifest.json"

    def run_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> DBTCompilationResult:
        """Execute dbt run via dbtRunner."""
        args = [
            "run",
            "--project-dir", str(project_dir),
            "--profiles-dir", str(profiles_dir),
            "--target", target,
        ]
        if select:
            args.extend(["--select", select])
        if exclude:
            args.extend(["--exclude", exclude])
        if full_refresh:
            args.append("--full-refresh")

        start_time = time.time()
        result = self.dbt.invoke(args)
        execution_time = time.time() - start_time

        run_results = self._parse_run_results(project_dir / "target" / "run_results.json")

        return DBTCompilationResult(
            success=result.success,
            manifest_path=project_dir / "target" / "manifest.json",
            run_results_path=project_dir / "target" / "run_results.json",
            catalog_path=project_dir / "target" / "catalog.json" if (project_dir / "target" / "catalog.json").exists() else None,
            execution_time_seconds=execution_time,
            models_run=len([r for r in run_results.get("results", []) if r["status"] == "success"]),
            tests_run=0,
            failures=len([r for r in run_results.get("results", []) if r["status"] == "error"]),
            metadata={"dbt_version": dbt_version},
        )

    def supports_parallel_execution(self) -> bool:
        """dbtRunner is NOT thread-safe per dbt documentation."""
        return False

    def get_runtime_metadata(self) -> dict[str, Any]:
        return {
            "type": "local",
            "dbt_version": dbt_version,
            "python_version": sys.version,
        }
```

**Characteristics**:
- ✅ Free and open-source
- ✅ Works offline
- ✅ No external dependencies
- ❌ NOT thread-safe (serial execution only)
- ❌ No metadata API (manual manifest parsing)
- ❌ Result objects may change across dbt versions

---

### 2. DBTCloudPlugin (Commercial Path)

**Implementation**: Uses dbt Cloud Admin API + Discovery API

```python
import httpx
from typing import Any

class DBTCloudPlugin(DBTPlugin):
    """Remote dbt Cloud execution via REST API."""

    def __init__(
        self,
        account_id: str,
        api_token: str,
        base_url: str = "https://cloud.getdbt.com/api/v2"
    ):
        self.account_id = account_id
        self.api_token = api_token
        self.base_url = base_url
        self.client = httpx.Client(
            headers={"Authorization": f"Token {api_token}"},
            timeout=300.0,
        )

    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str
    ) -> Path:
        """Trigger dbt Cloud job for compilation.

        Note: project_dir is ignored (dbt Cloud pulls from Git).
        """
        # Trigger compile job via Admin API
        job_id = self._get_compile_job_id()
        response = self.client.post(
            f"{self.base_url}/accounts/{self.account_id}/jobs/{job_id}/run/",
            json={"cause": "Triggered by floe"},
        )
        response.raise_for_status()
        run_id = response.json()["data"]["id"]

        # Poll until complete
        self._wait_for_run(run_id)

        # Download manifest artifact
        manifest_content = self._get_artifact(run_id, "manifest.json")

        # Cache locally (floe convention)
        cache_path = Path(f".floe/dbt-cloud-cache/{run_id}/manifest.json")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(manifest_content)

        return cache_path

    def run_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> DBTCompilationResult:
        """Trigger dbt Cloud run job."""
        job_id = self._get_run_job_id()

        # Build steps override (if select/exclude specified)
        steps_override = []
        if select or exclude or full_refresh:
            run_cmd = "dbt run"
            if select:
                run_cmd += f" --select {select}"
            if exclude:
                run_cmd += f" --exclude {exclude}"
            if full_refresh:
                run_cmd += " --full-refresh"
            steps_override = [run_cmd]

        # Trigger run
        start_time = time.time()
        response = self.client.post(
            f"{self.base_url}/accounts/{self.account_id}/jobs/{job_id}/run/",
            json={
                "cause": "Triggered by floe",
                "steps_override": steps_override if steps_override else None,
            },
        )
        response.raise_for_status()
        run_id = response.json()["data"]["id"]

        # Wait for completion
        self._wait_for_run(run_id)
        execution_time = time.time() - start_time

        # Fetch run results via Discovery API
        run_results = self._get_run_results_from_discovery_api(run_id)

        return DBTCompilationResult(
            success=run_results["status"] == "success",
            manifest_path=self._cache_artifact(run_id, "manifest.json"),
            run_results_path=self._cache_artifact(run_id, "run_results.json"),
            catalog_path=self._cache_artifact(run_id, "catalog.json"),
            execution_time_seconds=execution_time,
            models_run=run_results["models_run"],
            tests_run=0,
            failures=run_results["failures"],
            metadata={
                "run_id": run_id,
                "job_id": job_id,
                "account_id": self.account_id,
            },
        )

    def get_manifest(self, project_dir: Path) -> dict[str, Any]:
        """Fetch manifest via Discovery API (GraphQL)."""
        query = """
        query GetManifest($environmentId: Int!) {
          environment(id: $environmentId) {
            applied {
              manifest
            }
          }
        }
        """
        # Execute GraphQL query against Discovery API
        # ...
        return manifest_data

    def supports_parallel_execution(self) -> bool:
        """dbt Cloud API supports parallel job execution."""
        return True

    def get_runtime_metadata(self) -> dict[str, Any]:
        return {
            "type": "cloud",
            "account_id": self.account_id,
            "base_url": self.base_url,
        }
```

**Characteristics**:
- ✅ Remote execution (K8s pods, scalable)
- ✅ Thread-safe (parallel job execution)
- ✅ Metadata API (Discovery API for rich metadata)
- ✅ Artifact storage (S3-backed)
- ✅ Job scheduling (native cron support)
- ❌ Requires commercial license (~$100/dev/month)
- ❌ Requires network connectivity
- ❌ Git integration required (no local project_dir)

---

### 3. DBTFusionPlugin (Future Path)

**Implementation**: TBD (dbt Fusion in development)

```python
class DBTFusionPlugin(DBTPlugin):
    """Rust-based dbt runtime (future).

    Note: dbt Fusion is in development. This is a placeholder
    for future integration when Python bindings become available.

    References:
    - https://github.com/dbt-labs/dbt-fusion/issues/10
    """

    def compile_project(self, project_dir: Path, profiles_dir: Path, target: str) -> Path:
        raise NotImplementedError("dbt Fusion Python bindings not yet available")

    # ... other methods raise NotImplementedError
```

**Expected Characteristics**:
- ✅ Performance improvements (Rust compilation)
- ✅ Local execution (no cloud dependency)
- ⚠️ Python bindings TBD (design in progress)
- ⚠️ Timeline TBD

---

## Integration with Existing Architecture

### OrchestratorPlugin Integration

**Critical Design Constraint**: OrchestratorPlugin (Dagster, Airflow, Step Functions, etc.) MUST NOT directly invoke dbt. It delegates to DBTPlugin.

**Before (Hardcoded)**:
```python
# ❌ FORBIDDEN - Direct dbtRunner invocation
from dbt.cli.main import dbtRunner

@asset
def customers():
    dbt = dbtRunner()
    dbt.invoke(["run", "--select", "customers"])
```

**After (Plugin-Based)**:
```python
# ✅ CORRECT - Via DBTPlugin
from floe_core.plugin_registry import PluginRegistry

@asset
def customers(context):
    # Resolve runtime plugin from platform manifest
    registry = PluginRegistry()
    dbt_runtime = registry.get_plugin("dbt", "local")  # or "cloud"

    # Execute via plugin interface
    result = dbt_runtime.run_models(
        project_dir=Path("/opt/dbt/project"),
        profiles_dir=Path("/opt/dbt/profiles"),
        target="dev",
        select="customers",
    )

    # Standard artifact handling (runtime-agnostic)
    manifest = dbt_runtime.get_manifest(project_dir=Path("/opt/dbt/project"))
    context.log_metadata({"models_run": result.models_run})
```

**Key Insight**: Dagster assets consume `DBTCompilationResult` (standardized), NOT dbtRunner result objects (unstable).

---

### Configuration Schema

**manifest.yaml** extension:

```yaml
# Platform Team selects dbt runtime
plugins:
  dbt_runtime: local  # or cloud, fusion

  dbt_runtime_config:
    # Local runtime (dbt-core)
    local:
      dbt_version: "1.8.0"
      python_version: "3.11"

    # Cloud runtime (dbt Cloud API)
    cloud:
      account_id: "12345"
      api_token_ref: "dbt-cloud-api-token"  # SecretReference
      job_ids:
        compile: 67890
        run: 67891
        test: 67892
```

**floe.yaml** (unchanged):
```yaml
# Data Team defines transforms (runtime-agnostic)
transforms:
  - type: dbt
    path: models/
    select: "tag:daily"
    tests: true
```

**Separation of Concerns**:
- **Platform Team**: Chooses HOW dbt runs (local vs cloud)
- **Data Team**: Defines WHAT dbt runs (models, tests)

---

## Consequences

### Positive

1. **OSS + Commercial Support**: Single interface supports both dbt-core and dbt Cloud
2. **Future-Proof**: dbt Fusion integration path established
3. **Composability**: Follows ADR-0037 (plugin > config switch)
4. **API Stability**: DBTPlugin provides stable contract despite dbtRunner's "liable to change" warning
5. **Parallel Execution**: dbt Cloud plugin supports concurrency (dbt-core does not)
6. **Metadata Access**: Unified interface for manifest.json (filesystem or API)
7. **Production-Ready**: Supports remote execution, job scheduling, artifact storage

### Negative

1. **Plugin Type Count**: 12 plugins (was 11) - increased complexity
2. **dbt Cloud Dependency**: Commercial features require dbt Cloud license
3. **API Versioning**: Must track dbt Cloud API v2/v3 changes
4. **Testing Complexity**: Must test both local and remote runtimes

### Neutral

1. **Cube Integration**: Unaffected (Cube reads manifest.json via `cube_dbt`, runtime-agnostic)
2. **dbt Semantic Layer**: Intentionally NOT supported (Cube handles consumption APIs)
3. **Migration Path**: LocalDBTPlugin is drop-in replacement for existing hardcoded dbtRunner usage

---

## Migration Strategy

### Phase 1: Extract Interface (Epic 3)
1. Define `DBTPlugin` ABC in `floe-core/src/floe_core/plugin_interfaces.py`
2. Implement `LocalDBTPlugin` in `plugins/floe-dbt-local/`
3. Update `floe-dagster` to use `DBTPlugin` instead of direct dbtRunner
4. Add plugin registration: `[project.entry-points."floe.dbt"]`
5. Contract tests: `tests/contract/test_dbt_compilation_plugin.py`

### Phase 2: Add Cloud Support (Epic 8)
1. Implement `DBTCloudPlugin` in `plugins/floe-dbt-cloud/`
2. Add dbt Cloud API client (`httpx`, GraphQL queries)
3. Implement artifact caching (`.floe/dbt-cloud-cache/`)
4. Integration tests with dbt Cloud sandbox account
5. Documentation: "Using dbt Cloud with floe"

### Phase 3: Fusion Preparation (Future)
1. Monitor dbt Fusion Python bindings development
2. Create `DBTFusionPlugin` stub with NotImplementedError
3. Add to plugin type table (entry point ready)

---

## Testing Strategy

### Contract Tests (Must Pass)

```python
# tests/contract/test_dbt_compilation_plugin.py

import pytest
from floe_core.plugin_interfaces import DBTPlugin

@pytest.mark.parametrize("plugin_name", ["local", "cloud"])
def test_dbt_compilation_plugin_interface(plugin_name: str):
    """Verify all DBTPlugin implementations satisfy ABC."""
    from floe_core.plugin_registry import PluginRegistry

    registry = PluginRegistry()
    plugin = registry.get_plugin("dbt", plugin_name)

    # Verify ABC compliance
    assert isinstance(plugin, DBTPlugin)

    # Verify all abstract methods implemented
    assert callable(plugin.compile_project)
    assert callable(plugin.run_models)
    assert callable(plugin.run_tests)
    assert callable(plugin.get_manifest)
    assert callable(plugin.get_run_results)
    assert callable(plugin.supports_parallel_execution)
    assert callable(plugin.get_runtime_metadata)
```

### Integration Tests

```python
# plugins/floe-dbt-local/tests/integration/test_local_runtime.py

def test_local_dbt_compile_and_run(tmp_path: Path):
    """Test LocalDBTPlugin compiles and runs dbt project."""
    from floe_dbt_local import LocalDBTPlugin

    # Setup test dbt project
    project_dir = setup_test_dbt_project(tmp_path)
    profiles_dir = setup_test_profiles(tmp_path)

    plugin = LocalDBTPlugin()

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
```

---

## References

### Research Sources

- [dbt Core vs dbt Cloud – Key Differences as of 2025 | Datacoves](https://datacoves.com/post/dbt-core-key-differences)
- [dbt Cloud vs dbt Core: Major Differences | Estuary](https://estuary.dev/blog/dbt-cloud-vs-core/)
- [dbt Administrative API | dbt Developer Hub](https://docs.getdbt.com/docs/dbt-cloud-apis/admin-cloud-api)
- [dbt Discovery API (Metadata) | dbt Developer Hub](https://docs.getdbt.com/docs/dbt-cloud-apis/metadata-querying)
- [Programmatic invocations (dbtRunner) | dbt Developer Hub](https://docs.getdbt.com/reference/programmatic-invocations)
- [Running dbt Cloud or core from python - use cases and simple solutions | dltHub](https://dlthub.com/blog/dbt-runners-usage)
- [dbt Semantic Layer FAQs | dbt Developer Hub](https://docs.getdbt.com/docs/use-dbt-semantic-layer/sl-faqs)
- [dbt Fusion Python bindings issue | GitHub](https://github.com/dbt-labs/dbt-fusion/issues/10)

### Related ADRs

- **ADR-0009**: dbt Owns SQL - Establishes dbt ownership of SQL transformation
- **ADR-0037**: Composability Principle - Plugin architecture > configuration switches
- **ADR-0001**: Cube Semantic Layer - Cube handles consumption APIs (not dbt Semantic Layer)
- **ADR-0032**: Cube Compute Integration - Cube delegates to ComputePlugin for database connections

### Traceability

- **Domain 01**: Plugin Architecture (NEW: DBTPlugin as 12th plugin type)
- **Domain 02**: Configuration Management (manifest.yaml extension)
- **Domain 03**: Data Governance (no impact - PolicyEnforcer validates manifest.json regardless of runtime)

---

## Decision Record

**Date**: 2025-01-06
**Participants**: Architecture Team, CTO
**Decision**: Add DBTPlugin as 12th plugin type to support OSS + commercial dbt runtimes
**Rationale**: Production deployments require dbt Cloud support without compromising composability
**Next Steps**: Create requirements (Domain 01 update), implement LocalDBTPlugin (Epic 3), DBTCloudPlugin (Epic 8)
