# Data Model: Epic 5A - dbt Plugin Abstraction

**Date**: 2026-01-24
**Epic**: 5A
**Branch**: `5a-dbt-plugin`

## Entity Relationship Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Plugin Registry                            │
│                    (floe_core.plugin_registry)                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ discovers via entry points
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          DBTPlugin (ABC)                             │
│                    (floe_core.plugins.dbt)                          │
│                                                                      │
│  Properties:                                                         │
│  ├── name: str                                                       │
│  ├── version: str                                                    │
│  └── floe_api_version: str                                          │
│                                                                      │
│  Methods:                                                            │
│  ├── compile_project() -> Path                                       │
│  ├── run_models() -> DBTRunResult                                    │
│  ├── test_models() -> DBTRunResult                                   │
│  ├── lint_project() -> LintResult                                    │
│  ├── get_manifest() -> dict[str, Any]                               │
│  ├── get_run_results() -> dict[str, Any]                            │
│  ├── supports_parallel_execution() -> bool                          │
│  ├── supports_sql_linting() -> bool                                 │
│  └── get_runtime_metadata() -> dict[str, Any]                       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ implements
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│      DBTCorePlugin        │   │     DBTFusionPlugin       │
│   (floe_dbt_core)         │   │   (floe_dbt_fusion)       │
│                           │   │                           │
│  Uses:                    │   │  Uses:                    │
│  ├── dbtRunner (Python)   │   │  ├── dbt-sa-cli (Rust)    │
│  └── SQLFluff (linting)   │   │  └── Built-in linting     │
│                           │   │                           │
│  Thread-safe: NO          │   │  Thread-safe: YES         │
└───────────────────────────┘   └───────────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                │ returns
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Result Dataclasses                           │
├─────────────────────────────────┬───────────────────────────────────┤
│         DBTRunResult            │           LintResult              │
│  ├── success: bool              │  ├── success: bool                │
│  ├── manifest_path: Path        │  ├── issues: list[dict]           │
│  ├── run_results_path: Path     │  ├── files_checked: int           │
│  ├── catalog_path: Path | None  │  └── files_fixed: int             │
│  ├── execution_time_seconds     │                                   │
│  ├── models_run: int            │                                   │
│  ├── tests_run: int             │                                   │
│  ├── failures: int              │                                   │
│  └── metadata: dict[str, Any]   │                                   │
└─────────────────────────────────┴───────────────────────────────────┘
```

## Core Entities

### DBTPlugin (Abstract Base Class)

**Location**: `packages/floe-core/src/floe_core/plugins/dbt.py`
**Status**: EXISTS - No changes needed

The abstract base class defining the dbt execution environment interface. Extends `PluginMetadata` to inherit standard plugin properties.

```python
class DBTPlugin(PluginMetadata):
    """Abstract base class for dbt execution environment plugins."""

    @abstractmethod
    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path: ...

    @abstractmethod
    def run_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> DBTRunResult: ...

    # ... 8 more abstract methods
```

### DBTRunResult (Dataclass)

**Location**: `packages/floe-core/src/floe_core/plugins/dbt.py`
**Status**: EXISTS - No changes needed

Result of dbt command execution (run, test, compile).

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether command succeeded |
| `manifest_path` | `Path` | Path to compiled manifest.json |
| `run_results_path` | `Path` | Path to run_results.json |
| `catalog_path` | `Path \| None` | Path to catalog.json (if generated) |
| `execution_time_seconds` | `float` | Total execution time |
| `models_run` | `int` | Number of models executed |
| `tests_run` | `int` | Number of tests executed |
| `failures` | `int` | Number of failures |
| `metadata` | `dict[str, Any]` | Additional execution metadata |

### LintResult (Dataclass)

**Location**: `packages/floe-core/src/floe_core/plugins/dbt.py`
**Status**: EXISTS - No changes needed

Result of SQL linting operation.

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether all files passed linting |
| `issues` | `list[dict[str, Any]]` | List of linting issues found |
| `files_checked` | `int` | Number of files checked |
| `files_fixed` | `int` | Number of files auto-fixed |

### LintViolation (New Schema)

**Location**: `plugins/floe-dbt-core/src/floe_dbt_core/linting.py`
**Status**: NEW

Structured representation of a single lint violation (FR-025).

```python
from pydantic import BaseModel, ConfigDict

class LintViolation(BaseModel):
    """Single lint violation with location and rule info."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str
    line: int
    column: int
    code: str  # e.g., "L001", "ST01"
    message: str
    severity: str  # "error", "warning", "info"
```

## Plugin Implementations

### DBTCorePlugin

**Location**: `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py`
**Status**: NEW

Implementation using dbt-core Python API.

```python
class DBTCorePlugin(DBTPlugin):
    """dbt-core implementation using dbtRunner."""

    @property
    def name(self) -> str:
        return "core"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def supports_parallel_execution(self) -> bool:
        return False  # dbtRunner is NOT thread-safe

    def supports_sql_linting(self) -> bool:
        return True  # SQLFluff integration

    # ... implementation of abstract methods
```

### DBTFusionPlugin

**Location**: `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py`
**Status**: NEW

Implementation using dbt Fusion CLI.

```python
class DBTFusionPlugin(DBTPlugin):
    """dbt Fusion implementation using CLI subprocess."""

    @property
    def name(self) -> str:
        return "fusion"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def supports_parallel_execution(self) -> bool:
        return True  # Rust-based, thread-safe

    def supports_sql_linting(self) -> bool:
        return True  # Built-in static analysis

    # ... implementation of abstract methods
```

## Dagster Integration

### DBTResource (ConfigurableResource)

**Location**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/dbt_resource.py`
**Status**: NEW

Dagster resource wrapping DBTPlugin for asset injection (FR-037, FR-038).

```python
from dagster import ConfigurableResource
from floe_core.plugins.dbt import DBTPlugin, DBTRunResult
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType
from pathlib import Path

class DBTResource(ConfigurableResource):
    """DBTPlugin wrapped as Dagster ConfigurableResource."""

    plugin_type: str = "core"  # "core" or "fusion"
    project_dir: str
    profiles_dir: str
    target: str = "dev"

    def get_plugin(self) -> DBTPlugin:
        """Load DBTPlugin from registry."""
        registry = get_registry()
        return registry.get(PluginType.DBT, self.plugin_type)

    def compile(self) -> Path:
        """Compile dbt project."""
        plugin = self.get_plugin()
        return plugin.compile_project(
            project_dir=Path(self.project_dir),
            profiles_dir=Path(self.profiles_dir),
            target=self.target,
        )

    def run_models(
        self,
        select: str | None = None,
        exclude: str | None = None,
        full_refresh: bool = False,
    ) -> DBTRunResult:
        """Execute dbt models."""
        plugin = self.get_plugin()
        return plugin.run_models(
            project_dir=Path(self.project_dir),
            profiles_dir=Path(self.profiles_dir),
            target=self.target,
            select=select,
            exclude=exclude,
            full_refresh=full_refresh,
        )

    def test_models(self, select: str | None = None) -> DBTRunResult:
        """Execute dbt tests."""
        plugin = self.get_plugin()
        return plugin.test_models(
            project_dir=Path(self.project_dir),
            profiles_dir=Path(self.profiles_dir),
            target=self.target,
            select=select,
        )
```

## Exception Hierarchy

**Location**: `packages/floe-core/src/floe_core/errors.py` (base), plugin packages (specific)

```
FloeError (base)
└── DBTError
    ├── DBTCompilationError   # FLOE-DBT-E001
    │   ├── file_path: str | None
    │   ├── line_number: int | None
    │   └── original_message: str
    │
    ├── DBTExecutionError     # FLOE-DBT-E002
    │   ├── model_name: str | None
    │   └── adapter: str | None
    │
    ├── DBTConfigurationError # FLOE-DBT-E003
    │   └── config_file: str | None
    │
    ├── DBTLintError          # FLOE-DBT-E004
    │
    ├── DBTFusionNotFoundError    # FLOE-DBT-E005
    │
    └── DBTAdapterUnavailableError # FLOE-DBT-E006
        └── adapter: str
```

## Configuration Schema

### manifest.yaml (Platform Team)

```yaml
# Platform Team configures dbt runtime
plugins:
  dbt_runtime: core  # or "fusion"
```

### Plugin Selection Logic

```python
def get_dbt_plugin(manifest: PlatformManifest) -> DBTPlugin:
    """Get DBTPlugin based on manifest configuration."""
    runtime = manifest.plugins.get("dbt_runtime", "core")

    registry = get_registry()
    return registry.get(PluginType.DBT, runtime)
```

## Data Flow

```
CompiledArtifacts (from floe-core)
├── dbt_profiles: dict[str, Any]  # Generated profiles.yml content
└── transforms: ResolvedTransforms
    └── models: list[ResolvedModel]
        ├── name: str
        ├── compute: str
        ├── depends_on: list[str]
        └── tags: list[str]

            │
            │ Dagster loads artifacts
            ▼

DagsterOrchestratorPlugin
├── create_assets_from_artifacts(artifacts)
│   └── For each model in artifacts.transforms.models:
│       └── Create @asset with DBTResource dependency
│
└── DBTResource.run_models(select=model.name)
            │
            │ Invokes plugin
            ▼

DBTPlugin.run_models()
├── project_dir: Path (from resource config)
├── profiles_dir: Path (from resource config)
├── target: str (from resource config)
└── select: str (from asset)
            │
            │ Returns result
            ▼

DBTRunResult
├── success: bool
├── manifest_path: Path
├── run_results_path: Path
├── models_run: int
└── metadata: dict (OTel trace context)
```

## Entry Points

```toml
# plugins/floe-dbt-core/pyproject.toml
[project.entry-points."floe.dbt"]
core = "floe_dbt_core:DBTCorePlugin"

# plugins/floe-dbt-fusion/pyproject.toml
[project.entry-points."floe.dbt"]
fusion = "floe_dbt_fusion:DBTFusionPlugin"
```

## Validation Rules

### Project Directory
- Must exist and be readable
- Must contain `dbt_project.yml`

### Profiles Directory
- Must exist and be readable
- Must contain `profiles.yml`

### Target
- Must match a target defined in profiles.yml
- For Fusion: must have Rust adapter available

### Select/Exclude
- Must follow dbt selection syntax
- Validated by dbt, not by plugin
