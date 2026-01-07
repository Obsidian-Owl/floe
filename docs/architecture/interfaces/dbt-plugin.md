# DBTPlugin

**Purpose**: dbt compilation environment (local, fusion, cloud)
**Location**: `floe_core/interfaces/dbt.py`
**Entry Point**: `floe.dbt`
**ADR**: [ADR-0043: DBT Plugin](../adr/0043-dbt-plugin.md)

DBTPlugin abstracts dbt compilation and execution environments, enabling platform teams to choose between local dbt-core, dbt Cloud, or dbt Fusion based on scale and operational requirements.

> **Note**: dbt is an **enforced** component in floe - all SQL transformations go through dbt. This plugin controls *how* dbt runs, not *whether* it runs.

## Interface Definition

```python
# floe_core/interfaces/dbt.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class DBTConfig:
    """Configuration for dbt execution environment."""
    project_dir: Path
    profiles_dir: Path
    target: str
    vars: dict[str, Any] | None = None

@dataclass
class DBTRunResult:
    """Result of a dbt command execution."""
    success: bool
    command: str
    elapsed_time: float
    results: list[dict[str, Any]]
    logs: list[str]
    error: str | None = None

class DBTPlugin(ABC):
    """Interface for dbt execution environments."""

    name: str
    version: str
    is_cloud: bool  # True for dbt Cloud, False for local/fusion

    @abstractmethod
    def compile(self, config: DBTConfig, select: str | None = None) -> DBTRunResult:
        """Compile dbt models without executing.

        Args:
            config: dbt configuration
            select: Optional model selection (dbt --select syntax)

        Returns:
            DBTRunResult with compiled SQL in manifest
        """
        pass

    @abstractmethod
    def run(self, config: DBTConfig, select: str | None = None) -> DBTRunResult:
        """Execute dbt run command.

        Args:
            config: dbt configuration
            select: Optional model selection

        Returns:
            DBTRunResult with execution results
        """
        pass

    @abstractmethod
    def test(self, config: DBTConfig, select: str | None = None) -> DBTRunResult:
        """Execute dbt test command.

        Args:
            config: dbt configuration
            select: Optional model/test selection

        Returns:
            DBTRunResult with test results
        """
        pass

    @abstractmethod
    def get_manifest(self, config: DBTConfig) -> dict[str, Any]:
        """Get the dbt manifest.json.

        Args:
            config: dbt configuration

        Returns:
            Parsed manifest.json content
        """
        pass

    @abstractmethod
    def get_required_packages(self) -> list[str]:
        """Return list of Python packages required for this dbt environment.

        Example: ["dbt-core>=1.7.0", "dbt-duckdb>=1.7.0"]
        """
        pass
```

## Reference Implementations

| Plugin | Description | Cloud |
|--------|-------------|-------|
| `LocalDBTPlugin` | Local dbt-core execution | No |
| `FusionDBTPlugin` | dbt Fusion (experimental) | No |
| `CloudDBTPlugin` | dbt Cloud API integration | Yes |

## Related Documents

- [ADR-0043: DBT Plugin](../adr/0043-dbt-plugin.md)
- [Plugin Architecture](../plugin-system/index.md)
- [ComputePlugin](compute-plugin.md) - For dbt profile generation
