# OrchestratorPlugin

**Purpose**: Job scheduling and execution orchestration
**Location**: `floe_core/plugin_interfaces.py`
**Entry Point**: `floe.orchestrators`
**ADR**: [ADR-0011: Pluggable Orchestration](../adr/0011-pluggable-orchestration.md)

OrchestratorPlugin abstracts workflow orchestration, enabling platform teams to choose between Dagster, Airflow, or other orchestration platforms while maintaining consistent pipeline definitions.

## Interface Definition

```python
# floe_core/plugin_interfaces.py
from abc import ABC, abstractmethod
from typing import Any

class OrchestratorPlugin(ABC):
    """Interface for orchestration platforms (Dagster, Airflow, etc.).

    Responsibilities:
    - Validate and delegate CompiledArtifacts to the runtime definitions path
    - Create assets/tasks from dbt transforms
    - Emit OpenLineage events for data lineage
    - Schedule jobs for recurring execution
    - Provide Helm values for K8s deployment
    """

    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def create_definitions(self, artifacts: "CompiledArtifacts") -> Any:
        """Validate compiled artifacts and delegate to runtime definition loading.

        For Dagster: Direct calls validate artifacts, then require the
        loader/runtime builder path because usable Definitions need a
        product project_dir containing compiled_artifacts.json,
        target/manifest.json, profiles.yml, and dbt_project.yml.
        Generated definitions.py files should be thin shims that call
        load_product_definitions(product_name, project_dir).
        For Airflow: Returns DAG object

        Args:
            artifacts: CompiledArtifacts from floe-core compilation

        Returns:
            Platform-specific definitions object when runtime context is available
        """
        pass

    @abstractmethod
    def create_assets_from_transforms(self, transforms: list["TransformConfig"]) -> list:
        """Create orchestrator assets from dbt transforms.

        For Dagster: Returns list of @asset decorated functions
        For Airflow: Returns list of tasks

        Args:
            transforms: List of transform configurations from artifacts

        Returns:
            List of platform-specific assets/tasks
        """
        pass

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Return Helm chart values for deploying orchestration services.

        Returns:
            Dictionary matching Helm chart schema with resource
            requests/limits and service configuration (webserver, workers).
        """
        pass

    @abstractmethod
    def validate_connection(self) -> "ValidationResult":
        """Test connectivity to orchestration service.

        Returns:
            ValidationResult with success status and actionable error messages.
            Must complete within 10 seconds or timeout.
        """
        pass

    @abstractmethod
    def get_resource_requirements(self, workload_size: str) -> "ResourceSpec":
        """Return K8s ResourceRequirements for orchestration workloads.

        Args:
            workload_size: "small", "medium", "large"

        Returns:
            ResourceSpec with CPU/memory requests and limits appropriate
            for orchestrator components (webserver, daemon, workers).
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
        """Schedule a job for recurring execution.

        Args:
            job_name: Name of the job to schedule
            cron: Cron expression (e.g., "0 8 * * *")
            timezone: IANA timezone (e.g., "America/New_York")
        """
        pass
```

## Entry Points

```toml
[project.entry-points."floe.orchestrators"]
dagster = "floe_orchestrator_dagster:DagsterPlugin"
airflow = "floe_orchestrator_airflow:AirflowPlugin"
```

## Reference Implementations

| Plugin | Description | Helm Chart |
|--------|-------------|------------|
| `DagsterOrchestratorPlugin` | Software-defined assets, native dbt integration | `charts/floe-dagster` |
| `AirflowOrchestratorPlugin` | Airflow 3.x DAGs with dbt operators | `charts/floe-airflow` |

## Requirements Traceability

- REQ-021 to REQ-030 (OrchestratorPlugin Standards)

## Related Documents

- [ADR-0011: Pluggable Orchestration](../adr/0011-pluggable-orchestration.md)
- [Plugin Architecture](../plugin-system/index.md)
- [LineageBackendPlugin](lineage-backend-plugin.md) - For lineage event destinations
