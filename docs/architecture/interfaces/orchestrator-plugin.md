# OrchestratorPlugin

**Purpose**: Job scheduling and execution orchestration
**Location**: `floe_core/interfaces/orchestrator.py`
**Entry Point**: `floe.orchestrators`
**ADR**: [ADR-0033: Orchestrator Plugin](../adr/0033-orchestrator-plugin.md)

OrchestratorPlugin abstracts workflow orchestration, enabling platform teams to choose between Dagster, Airflow, or other orchestration platforms while maintaining consistent pipeline definitions.

## Interface Definition

```python
# floe_core/interfaces/orchestrator.py
from abc import ABC, abstractmethod
from typing import Any

class OrchestratorPlugin(ABC):
    """Interface for orchestration platforms (Dagster, Airflow, etc.)."""

    name: str
    version: str

    @abstractmethod
    def create_definitions(self, artifacts: "CompiledArtifacts") -> Any:
        """Generate orchestrator-specific definitions from compiled artifacts.

        For Dagster: Returns Dagster Definitions object
        For Airflow: Returns DAG object
        """
        pass

    @abstractmethod
    def create_assets_from_transforms(self, transforms: list["TransformConfig"]) -> list:
        """Create orchestrator assets from dbt transforms.

        For Dagster: Returns list of @asset decorated functions
        For Airflow: Returns list of tasks
        """
        pass

    @abstractmethod
    def emit_lineage_event(
        self,
        event_type: str,
        job: str,
        inputs: list["Dataset"],
        outputs: list["Dataset"]
    ) -> None:
        """Emit OpenLineage event for data lineage tracking.

        Args:
            event_type: "START" | "COMPLETE" | "FAIL"
            job: Job name (e.g., "dbt_run")
            inputs: Input datasets
            outputs: Output datasets
        """
        pass

    @abstractmethod
    def schedule_job(self, job_name: str, cron: str, timezone: str) -> None:
        """Schedule a job for recurring execution."""
        pass
```

## Reference Implementations

| Plugin | Description |
|--------|-------------|
| `DagsterOrchestratorPlugin` | Software-defined assets, native dbt integration |
| `AirflowOrchestratorPlugin` | Airflow 3.x DAGs with dbt operators |

## Related Documents

- [ADR-0033: Orchestrator Plugin](../adr/0033-orchestrator-plugin.md)
- [Plugin Architecture](../plugin-system/index.md)
- [LineageBackendPlugin](lineage-backend-plugin.md) - For lineage event destinations
