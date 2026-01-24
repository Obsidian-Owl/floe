# DBTPlugin API Contract

**Version**: 1.0.0
**Date**: 2026-01-24
**Epic**: 5A

## Overview

This document defines the API contract for DBTPlugin implementations. All implementations (DBTCorePlugin, DBTFusionPlugin, future DBTCloudPlugin) MUST conform to this contract.

## Interface Definition

### DBTPlugin ABC

```python
from abc import abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


@dataclass
class DBTRunResult:
    """Result of a dbt command execution."""
    success: bool
    manifest_path: Path
    run_results_path: Path
    catalog_path: Path | None = None
    execution_time_seconds: float = 0.0
    models_run: int = 0
    tests_run: int = 0
    failures: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LintResult:
    """Result of SQL linting."""
    success: bool
    issues: list[dict[str, Any]] = field(default_factory=list)
    files_checked: int = 0
    files_fixed: int = 0


class DBTPlugin(PluginMetadata):
    """Abstract base class for dbt execution environment plugins."""

    @abstractmethod
    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path:
        """Compile dbt project and return path to manifest.json."""
        ...

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
        """Execute dbt models."""
        ...

    @abstractmethod
    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTRunResult:
        """Execute dbt tests."""
        ...

    @abstractmethod
    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> LintResult:
        """Lint SQL files with dialect-aware validation."""
        ...

    @abstractmethod
    def get_manifest(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt manifest.json."""
        ...

    @abstractmethod
    def get_run_results(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt run_results.json."""
        ...

    @abstractmethod
    def supports_parallel_execution(self) -> bool:
        """Indicate whether runtime supports parallel model execution."""
        ...

    @abstractmethod
    def supports_sql_linting(self) -> bool:
        """Indicate whether this execution environment provides SQL linting."""
        ...

    @abstractmethod
    def get_runtime_metadata(self) -> dict[str, Any]:
        """Return runtime-specific metadata for observability."""
        ...
```

## Method Contracts

### compile_project()

**Purpose**: Compile dbt project (Jinja to SQL) without executing.

**Preconditions**:
- `project_dir` exists and contains `dbt_project.yml`
- `profiles_dir` exists and contains `profiles.yml`
- `target` is defined in profiles.yml

**Postconditions**:
- Returns `Path` to `target/manifest.json`
- `manifest.json` contains all compiled node information
- No models are executed

**Errors**:
- `DBTCompilationError` if Jinja parsing or SQL generation fails
- `DBTConfigurationError` if project or profiles invalid

### run_models()

**Purpose**: Execute dbt models against target database.

**Preconditions**:
- Same as `compile_project()`
- Database connection is valid

**Postconditions**:
- Returns `DBTRunResult` with execution status
- `run_results.json` is written to target/
- Models are materialized in database

**Errors**:
- `DBTExecutionError` if model execution fails
- Partial failures: `DBTRunResult.failures > 0` but `success = False`

### test_models()

**Purpose**: Execute dbt tests (schema and data tests).

**Preconditions**:
- Same as `run_models()`
- Models referenced by tests exist

**Postconditions**:
- Returns `DBTRunResult` with test results
- `tests_run` contains count of executed tests
- `failures` contains count of failed tests

### lint_project()

**Purpose**: Lint SQL files with dialect-aware validation.

**Preconditions**:
- `project_dir` exists and contains SQL files
- `profiles_dir` provides dialect information

**Postconditions**:
- Returns `LintResult` with all issues found
- If `fix=True`, files are modified in place
- `files_fixed` reflects count of modified files

**Behavior Notes**:
- DBTCorePlugin uses SQLFluff
- DBTFusionPlugin uses built-in static analysis
- Dialect is determined from profiles.yml target type

### get_manifest()

**Purpose**: Retrieve compiled manifest.json.

**Preconditions**:
- `project_dir/target/manifest.json` exists

**Postconditions**:
- Returns parsed JSON as dict
- No side effects

**Errors**:
- `FileNotFoundError` if manifest doesn't exist

### get_run_results()

**Purpose**: Retrieve run_results.json from last execution.

**Preconditions**:
- `project_dir/target/run_results.json` exists

**Postconditions**:
- Returns parsed JSON as dict
- No side effects

**Errors**:
- `FileNotFoundError` if run_results doesn't exist

### supports_parallel_execution()

**Purpose**: Indicate thread safety for concurrent invocations.

**Returns**:
- `True` if multiple instances can run in parallel (DBTFusionPlugin)
- `False` if instances share global state (DBTCorePlugin)

**Note**: This is a capability indicator, not a guarantee. Callers should use this to decide whether to parallelize.

### supports_sql_linting()

**Purpose**: Indicate whether `lint_project()` is implemented.

**Returns**:
- `True` if `lint_project()` performs actual linting
- `False` if `lint_project()` is a no-op

### get_runtime_metadata()

**Purpose**: Return observability metadata about the runtime.

**Returns**:
```python
{
    "runtime": "core" | "fusion" | "cloud",
    "dbt_version": "1.7.0",
    "python_version": "3.11.0",  # if applicable
    "adapter": "duckdb" | "snowflake" | ...,
    "parallel_safe": True | False,
}
```

## Entry Point Contract

All DBTPlugin implementations MUST register via entry points:

```toml
# pyproject.toml
[project.entry-points."floe.dbt"]
<name> = "<module>:<PluginClass>"
```

Where:
- `<name>` is the plugin identifier (e.g., "core", "fusion", "cloud")
- `<module>` is the Python module path
- `<PluginClass>` is the class implementing DBTPlugin

## Implementation Compliance

### Required Properties (from PluginMetadata)

| Property | Type | Example |
|----------|------|---------|
| `name` | `str` | `"core"` |
| `version` | `str` | `"0.1.0"` |
| `floe_api_version` | `str` | `"1.0"` |

### Required Implementations

| Implementation | `supports_parallel_execution()` | `supports_sql_linting()` | Linter |
|---------------|--------------------------------|-------------------------|--------|
| DBTCorePlugin | `False` | `True` | SQLFluff |
| DBTFusionPlugin | `True` | `True` | Built-in |
| DBTCloudPlugin (future) | `True` | `True` | dbt Cloud |

## Contract Tests

All implementations MUST pass the contract test suite at `tests/contract/test_dbt_plugin_contract.py`:

```python
import pytest
from floe_core.plugins.dbt import DBTPlugin

class TestDBTPluginContract:
    """Contract tests for all DBTPlugin implementations."""

    @pytest.fixture(params=["core", "fusion"])
    def plugin(self, request) -> DBTPlugin:
        """Load each registered plugin."""
        from floe_core.plugin_registry import get_registry
        from floe_core.plugin_types import PluginType
        return get_registry().get(PluginType.DBT, request.param)

    def test_has_name(self, plugin: DBTPlugin) -> None:
        """Plugin must have a non-empty name."""
        assert plugin.name
        assert isinstance(plugin.name, str)

    def test_has_version(self, plugin: DBTPlugin) -> None:
        """Plugin must have a valid version string."""
        assert plugin.version
        # Should be semver-like
        parts = plugin.version.split(".")
        assert len(parts) >= 2

    def test_has_floe_api_version(self, plugin: DBTPlugin) -> None:
        """Plugin must declare API version."""
        assert plugin.floe_api_version
        assert plugin.floe_api_version == "1.0"

    def test_supports_parallel_execution_returns_bool(self, plugin: DBTPlugin) -> None:
        """Method must return boolean."""
        result = plugin.supports_parallel_execution()
        assert isinstance(result, bool)

    def test_supports_sql_linting_returns_bool(self, plugin: DBTPlugin) -> None:
        """Method must return boolean."""
        result = plugin.supports_sql_linting()
        assert isinstance(result, bool)

    def test_get_runtime_metadata_returns_dict(self, plugin: DBTPlugin) -> None:
        """Method must return dict with required keys."""
        metadata = plugin.get_runtime_metadata()
        assert isinstance(metadata, dict)
        assert "runtime" in metadata
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-24 | Initial contract definition |
