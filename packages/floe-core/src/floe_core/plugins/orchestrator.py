"""OrchestratorPlugin ABC for orchestration platform plugins.

This module defines the abstract base class for orchestrator plugins that
provide job scheduling and execution. Orchestrator plugins are responsible for:
- Creating platform-specific definitions from compiled artifacts
- Generating assets from dbt transforms
- Providing Helm values for deploying orchestration services
- Emitting OpenLineage events for data lineage tracking
- Scheduling jobs for recurring execution

Example:
    >>> from floe_core.plugins.orchestrator import OrchestratorPlugin
    >>> class DagsterPlugin(OrchestratorPlugin):
    ...     @property
    ...     def name(self) -> str:
    ...         return "dagster"
    ...     # ... implement other abstract methods
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from floe_core.plugin_metadata import PluginMetadata

if TYPE_CHECKING:
    pass


@dataclass
class TransformConfig:
    """Configuration for a dbt transform/model.

    Represents a single dbt model that needs to be orchestrated.
    Used by create_assets_from_transforms() to generate orchestrator assets.

    Attributes:
        name: Model name (e.g., "stg_customers").
        path: Path to the model file.
        schema_name: Target schema for the model.
        materialization: dbt materialization (table, view, incremental, etc.).
        tags: List of model tags.
        depends_on: List of upstream model names.
        meta: Additional model metadata.

    Example:
        >>> transform = TransformConfig(
        ...     name="stg_customers",
        ...     path="models/staging/stg_customers.sql",
        ...     schema_name="staging",
        ...     materialization="view",
        ...     depends_on=["raw_customers"]
        ... )
    """

    name: str
    path: str = ""
    schema_name: str = ""
    materialization: str = "table"
    tags: list[str] = field(default_factory=lambda: [])
    depends_on: list[str] = field(default_factory=lambda: [])
    meta: dict[str, Any] = field(default_factory=lambda: {})


@dataclass
class ValidationResult:
    """Result of a connection or configuration validation.

    Attributes:
        success: Whether validation passed.
        message: Human-readable message about the validation status.
        errors: List of specific error messages if validation failed.
        warnings: List of non-fatal warning messages.

    Example:
        >>> result = ValidationResult(
        ...     success=False,
        ...     message="Connection failed",
        ...     errors=["Unable to reach orchestrator API at http://dagster:3000"]
        ... )
    """

    success: bool
    message: str = ""
    errors: list[str] = field(default_factory=lambda: [])
    warnings: list[str] = field(default_factory=lambda: [])


@dataclass
class Dataset:
    """OpenLineage dataset representation.

    Used for lineage event emission to track data flow between
    inputs and outputs of orchestrated jobs.

    Attributes:
        namespace: Dataset namespace (e.g., "floe-prod").
        name: Dataset name (e.g., "bronze.raw_customers").
        facets: Additional OpenLineage facets for the dataset.

    Example:
        >>> dataset = Dataset(
        ...     namespace="floe-prod",
        ...     name="silver.dim_customers",
        ...     facets={"schema": {"fields": [{"name": "id", "type": "INTEGER"}]}}
        ... )
    """

    namespace: str
    name: str
    facets: dict[str, Any] = field(default_factory=lambda: {})


@dataclass
class ResourceSpec:
    """Kubernetes resource requirements specification.

    Follows K8s ResourceRequirements schema for CPU and memory
    requests and limits.

    Attributes:
        cpu_request: CPU request (e.g., "100m", "1").
        cpu_limit: CPU limit (e.g., "500m", "2").
        memory_request: Memory request (e.g., "256Mi", "1Gi").
        memory_limit: Memory limit (e.g., "512Mi", "2Gi").

    Example:
        >>> spec = ResourceSpec(
        ...     cpu_request="100m",
        ...     cpu_limit="1",
        ...     memory_request="256Mi",
        ...     memory_limit="1Gi"
        ... )
    """

    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "256Mi"
    memory_limit: str = "512Mi"


class OrchestratorPlugin(PluginMetadata):
    """Abstract base class for orchestration platform plugins.

    OrchestratorPlugin extends PluginMetadata with orchestration-specific
    methods for job scheduling and execution. Implementations include
    Dagster and Airflow.

    Concrete plugins must implement:
        - All abstract properties from PluginMetadata (name, version, floe_api_version)
        - create_definitions() method
        - create_assets_from_transforms() method
        - get_helm_values() method
        - validate_connection() method
        - get_resource_requirements() method
        - emit_lineage_event() method
        - schedule_job() method

    Example:
        >>> class DagsterPlugin(OrchestratorPlugin):
        ...     @property
        ...     def name(self) -> str:
        ...         return "dagster"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     def create_definitions(self, artifacts: dict) -> Any:
        ...         from dagster import Definitions
        ...         return Definitions(assets=[...])
        ...
        ...     # ... other methods

    See Also:
        - PluginMetadata: Base class with common plugin attributes
        - docs/architecture/plugin-system/interfaces.md: Full interface specification
    """

    @abstractmethod
    def create_definitions(self, artifacts: dict[str, Any]) -> Any:
        """Generate orchestrator-specific definitions from compiled artifacts.

        Creates the main orchestration definition object for the platform.
        For Dagster, this returns a Definitions object. For Airflow, this
        returns a DAG object.

        Args:
            artifacts: CompiledArtifacts dictionary containing dbt manifest,
                profiles, and other configuration.

        Returns:
            Platform-specific definitions object (Definitions for Dagster,
            DAG for Airflow).

        Example:
            >>> artifacts = {"dbt_manifest": {...}, "transforms": [...]}
            >>> definitions = plugin.create_definitions(artifacts)
            >>> # For Dagster: returns Dagster Definitions
            >>> # For Airflow: returns Airflow DAG
        """
        ...

    @abstractmethod
    def create_assets_from_transforms(
        self, transforms: list[TransformConfig]
    ) -> list[Any]:
        """Create orchestrator assets from dbt transforms.

        Converts a list of dbt model configurations into platform-specific
        assets. For Dagster, returns @asset decorated functions. For Airflow,
        returns task instances.

        Args:
            transforms: List of TransformConfig objects representing dbt models.

        Returns:
            List of platform-specific asset objects.

        Example:
            >>> transforms = [
            ...     TransformConfig(name="stg_customers", depends_on=["raw_customers"]),
            ...     TransformConfig(name="dim_customers", depends_on=["stg_customers"])
            ... ]
            >>> assets = plugin.create_assets_from_transforms(transforms)
            >>> len(assets)
            2
        """
        ...

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Return Helm chart values for deploying orchestration services.

        Provides configuration values for the orchestrator's Helm chart,
        including resource requests/limits and service configuration.

        Returns:
            Dictionary matching the orchestrator's Helm chart schema.

        Example:
            >>> values = plugin.get_helm_values()
            >>> values
            {
                'dagster-webserver': {
                    'resources': {'requests': {'cpu': '100m', 'memory': '256Mi'}}
                },
                'dagster-daemon': {...}
            }
        """
        ...

    @abstractmethod
    def validate_connection(self) -> ValidationResult:
        """Test connectivity to orchestration service.

        Performs a lightweight connectivity test to verify the orchestration
        service is reachable. Should complete within 10 seconds.

        Returns:
            ValidationResult with success status and actionable error messages.

        Example:
            >>> result = plugin.validate_connection()
            >>> if result.success:
            ...     print("Connected to orchestrator")
            ... else:
            ...     for error in result.errors:
            ...         print(f"Error: {error}")
        """
        ...

    @abstractmethod
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements for orchestration workloads.

        Provides CPU and memory requests/limits based on workload size
        for the orchestration service pods.

        Args:
            workload_size: One of "small", "medium", "large".

        Returns:
            ResourceSpec with K8s-compatible resource specifications.

        Raises:
            ValueError: If workload_size is not one of the valid options.

        Example:
            >>> spec = plugin.get_resource_requirements("medium")
            >>> spec.cpu_request
            '500m'
            >>> spec.memory_limit
            '2Gi'
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

        Sends a lineage event to the configured lineage backend
        (Marquez, Atlan, etc.) for tracking data flow.

        Args:
            event_type: One of "START", "COMPLETE", or "FAIL".
            job: Job name (e.g., "dbt_run_customers").
            inputs: List of input datasets consumed by the job.
            outputs: List of output datasets produced by the job.

        Example:
            >>> inputs = [Dataset(namespace="floe", name="raw.customers")]
            >>> outputs = [Dataset(namespace="floe", name="staging.stg_customers")]
            >>> plugin.emit_lineage_event(
            ...     event_type="COMPLETE",
            ...     job="dbt_run_stg_customers",
            ...     inputs=inputs,
            ...     outputs=outputs
            ... )
        """
        ...

    @abstractmethod
    def schedule_job(self, job_name: str, cron: str, timezone: str) -> None:
        """Schedule a job for recurring execution.

        Creates or updates a schedule for the specified job using
        a cron expression in the given timezone.

        Args:
            job_name: Name of the job to schedule.
            cron: Cron expression (e.g., "0 8 * * *" for 8 AM daily).
            timezone: IANA timezone (e.g., "America/New_York", "UTC").

        Raises:
            ValueError: If cron expression is invalid.
            ValueError: If timezone is not a valid IANA timezone.

        Example:
            >>> plugin.schedule_job(
            ...     job_name="daily_refresh",
            ...     cron="0 8 * * *",
            ...     timezone="America/New_York"
            ... )
        """
        ...
