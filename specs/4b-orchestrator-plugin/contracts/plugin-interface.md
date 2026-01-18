# Contract: OrchestratorPlugin Interface

**Version**: 1.0.0
**Status**: Stable (defined in floe-core)

## Overview

This contract defines the interface that all orchestrator plugins must implement.
The `DagsterOrchestratorPlugin` MUST implement this interface exactly.

## Interface Definition

```python
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from floe_core.plugin_metadata import PluginMetadata


@dataclass
class TransformConfig:
    """Configuration for a dbt transform/model."""
    name: str
    path: str = ""
    schema_name: str = ""
    materialization: str = "table"
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    compute: str | None = None


@dataclass
class ValidationResult:
    """Result of connection validation."""
    success: bool
    message: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Dataset:
    """OpenLineage dataset representation."""
    namespace: str
    name: str
    facets: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceSpec:
    """Kubernetes resource requirements."""
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "256Mi"
    memory_limit: str = "512Mi"


class OrchestratorPlugin(PluginMetadata):
    """Abstract base class for orchestrator plugins."""

    @abstractmethod
    def create_definitions(self, artifacts: dict[str, Any]) -> Any:
        """Generate orchestrator-specific definitions from CompiledArtifacts.

        Args:
            artifacts: CompiledArtifacts dictionary

        Returns:
            Platform-specific definitions (Dagster Definitions, Airflow DAG, etc.)
        """
        ...

    @abstractmethod
    def create_assets_from_transforms(
        self, transforms: list[TransformConfig]
    ) -> list[Any]:
        """Create orchestrator assets from dbt transforms.

        Args:
            transforms: List of TransformConfig objects

        Returns:
            List of platform-specific assets
        """
        ...

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Return Helm chart values for orchestration service deployment.

        Returns:
            Dictionary compatible with orchestrator's Helm chart schema
        """
        ...

    @abstractmethod
    def validate_connection(self) -> ValidationResult:
        """Test connectivity to orchestration service.

        Must complete within 10 seconds.

        Returns:
            ValidationResult with success status and messages
        """
        ...

    @abstractmethod
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements for orchestration workloads.

        Args:
            workload_size: One of "small", "medium", "large"

        Returns:
            ResourceSpec with CPU/memory requests and limits

        Raises:
            ValueError: If workload_size is invalid
        """
        ...

    @abstractmethod
    def emit_lineage_event(
        self,
        event_type: str,
        job: str,
        inputs: list[Dataset],
        outputs: list[Dataset],
    ) -> None:
        """Emit OpenLineage event for data lineage tracking.

        Args:
            event_type: "START", "COMPLETE", or "FAIL"
            job: Job name
            inputs: Input datasets
            outputs: Output datasets
        """
        ...

    @abstractmethod
    def schedule_job(
        self, job_name: str, cron: str, timezone: str
    ) -> None:
        """Schedule a job for recurring execution.

        Args:
            job_name: Name of job to schedule
            cron: Cron expression (5-field)
            timezone: IANA timezone name

        Raises:
            ValueError: If cron or timezone is invalid
        """
        ...
```

## Entry Point Registration

```toml
# pyproject.toml
[project.entry-points."floe.orchestrators"]
dagster = "floe_orchestrator_dagster:DagsterOrchestratorPlugin"
```

## Discovery Pattern

```python
from importlib.metadata import entry_points

# Discover orchestrator plugins
eps = entry_points(group="floe.orchestrators")
dagster_ep = next(ep for ep in eps if ep.name == "dagster")
plugin_class = dagster_ep.load()
plugin = plugin_class()

assert isinstance(plugin, OrchestratorPlugin)
assert plugin.name == "dagster"
```

## Contract Stability Rules

| Change Type | Contract Impact | Action Required |
|-------------|-----------------|-----------------|
| Add optional field to dataclass | MINOR | Bump minor version |
| Add new abstract method | MAJOR | Bump major version |
| Remove abstract method | MAJOR | Bump major version |
| Change method signature | MAJOR | Bump major version |
| Add optional parameter | MINOR | Bump minor version |
| Rename field/method | MAJOR | Bump major version |

## Test Requirements

Contract compliance is tested in:
- `tests/contract/test_orchestrator_plugin_contract.py` (root level)
- `plugins/floe-orchestrator-dagster/tests/unit/test_plugin.py` (plugin level)
- `plugins/floe-orchestrator-dagster/tests/integration/test_discovery.py` (plugin level)
