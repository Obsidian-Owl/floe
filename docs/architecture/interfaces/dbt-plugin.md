# DBTPlugin

**Purpose**: dbt compilation environment (local, fusion, cloud)
**Location**: `floe_core/plugin_interfaces.py`
**Entry Point**: `floe.dbt`
**ADR**: [ADR-0043: dbt Compilation Abstraction Layer](../adr/0043-dbt-plugin.md)

DBTPlugin abstracts dbt compilation and execution environments, enabling platform teams to choose between local dbt-core, dbt Cloud, or dbt Fusion based on scale and operational requirements.

> **Note**: dbt is an **enforced** component in floe - all SQL transformations go through dbt. This plugin controls *how* dbt runs, not *whether* it runs.

## Interface Definition

```python
# floe_core/plugin_interfaces.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from pydantic import BaseModel

class DBTRunResult(BaseModel):
    """Result of a dbt command execution."""
    success: bool
    manifest_path: Path
    run_results_path: Path
    catalog_path: Path | None = None
    execution_time_seconds: float
    models_run: int
    tests_run: int
    failures: int
    metadata: dict[str, Any] = {}

class DBTPlugin(ABC):
    """Interface for dbt execution environments.

    Responsibilities:
    - Compile dbt projects (Jinja -> SQL)
    - Execute dbt commands (run, test, snapshot)
    - Provide SQL linting (optional, dialect-aware)

    Note: This plugins WHERE dbt executes (local/cloud/fusion),
    NOT the SQL transformation framework itself (enforced).
    """

    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path:
        """Compile dbt project and return path to manifest.json.

        Returns:
            Path to compiled manifest.json (typically target/manifest.json)

        Raises:
            CompilationError: If dbt compilation fails
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
    ) -> DBTRunResult:
        """Execute dbt run command.

        Returns:
            DBTRunResult with success status and executed model count
        """
        pass

    @abstractmethod
    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTRunResult:
        """Execute dbt test command.

        Returns:
            DBTRunResult with pass/fail status and test results
        """
        pass

    @abstractmethod
    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> "LintResult":
        """Lint SQL files with dialect-aware validation.

        Args:
            fix: If True, auto-fix issues (if linter supports it)

        Returns:
            LintResult with all detected linting issues

        Raises:
            DBTLintError: If linting process fails (not if SQL has issues)
        """
        pass

    @abstractmethod
    def get_manifest(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt manifest.json (filesystem or API).

        Returns:
            Parsed manifest.json content
        """
        pass

    @abstractmethod
    def get_run_results(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt run_results.json.

        Returns:
            Parsed run_results.json content
        """
        pass

    @abstractmethod
    def supports_parallel_execution(self) -> bool:
        """Indicate whether runtime supports parallel execution.

        Returns:
            True for cloud runtimes (remote isolation), False for local (dbtRunner not thread-safe)
        """
        pass

    @abstractmethod
    def supports_sql_linting(self) -> bool:
        """Indicate whether this compilation environment provides SQL linting.

        Returns:
            True if lint_project() is functional, False otherwise
        """
        pass

    @abstractmethod
    def get_runtime_metadata(self) -> dict[str, Any]:
        """Return runtime-specific metadata for observability.

        Returns:
            Metadata dict with runtime type, version, etc.
        """
        pass
```

## Entry Points

```toml
[project.entry-points."floe.dbt"]
local = "floe_dbt_local:LocalDBTPlugin"
fusion = "floe_dbt_fusion:FusionDBTPlugin"
cloud = "floe_dbt_cloud:CloudDBTPlugin"
```

## Reference Implementations

| Plugin | Description | Parallel | Linting |
|--------|-------------|----------|---------|
| `LocalDBTPlugin` | dbt-core via dbtRunner | No | SQLFluff |
| `FusionDBTPlugin` | dbt Fusion CLI (experimental) | Yes | Built-in |
| `CloudDBTPlugin` | dbt Cloud API (Epic 8+) | Yes | No |

## Requirements Traceability

- REQ-086 to REQ-095 (DBT Runtime Plugin)
- REQ-096 to REQ-100 (SQL Linting)

## Related Documents

- [ADR-0043: dbt Compilation Abstraction Layer](../adr/0043-dbt-plugin.md)
- [Plugin Architecture](../plugin-system/index.md)
- [ComputePlugin](compute-plugin.md) - For dbt profile generation
