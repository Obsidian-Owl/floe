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
from uuid import UUID

from floe_core.lineage import LineageDataset, LineageEmitter, RunState
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
        compute: Optional compute target override. When None, inherits from
            platform default. When specified, must be in the approved compute
            list. Validated at compile time via ComputeRegistry.validate_selection().

    Example:
        >>> transform = TransformConfig(
        ...     name="stg_customers",
        ...     path="models/staging/stg_customers.sql",
        ...     schema_name="staging",
        ...     materialization="view",
        ...     depends_on=["raw_customers"]
        ... )
        >>> # With explicit compute override
        >>> heavy_transform = TransformConfig(
        ...     name="heavy_aggregation",
        ...     compute="spark"  # Override platform default
        ... )

    See Also:
        - FR-012: Per-transform compute selection in floe.yaml
        - FR-014: Environment parity enforcement
        - ComputeRegistry.validate_selection(): Compile-time validation
    """

    name: str
    path: str = ""
    schema_name: str = ""
    materialization: str = "table"
    tags: list[str] = field(default_factory=lambda: [])
    depends_on: list[str] = field(default_factory=lambda: [])
    meta: dict[str, Any] = field(default_factory=lambda: {})
    compute: str | None = None


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
    def create_assets_from_transforms(self, transforms: list[TransformConfig]) -> list[Any]:
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
        event_type: RunState,
        job_name: str,
        job_namespace: str | None = None,
        run_id: UUID | None = None,
        inputs: list[LineageDataset] | None = None,
        outputs: list[LineageDataset] | None = None,
        run_facets: dict[str, Any] | None = None,
        job_facets: dict[str, Any] | None = None,
        producer: str | None = None,
    ) -> UUID:
        """Emit an OpenLineage event for data lineage tracking.

        Sends a lineage event to the configured lineage backend
        (Marquez, Atlan, etc.) for tracking data flow.

        Args:
            event_type: Run state (START, COMPLETE, FAIL, etc.).
            job_name: Job name (e.g., "dbt_run_customers").
            job_namespace: Job namespace. Defaults to plugin-specific namespace.
            run_id: Unique run identifier. Auto-generated if None.
            inputs: Input datasets consumed by the job.
            outputs: Output datasets produced by the job.
            run_facets: Additional OpenLineage run facets.
            job_facets: Additional OpenLineage job facets.
            producer: Producer identifier. Defaults to "floe".

        Returns:
            The run UUID for this event (generated or provided).

        Example:
            >>> from floe_core.lineage import RunState, LineageDataset
            >>> inputs = [LineageDataset(namespace="floe", name="raw.customers")]
            >>> outputs = [LineageDataset(namespace="floe", name="staging.stg_customers")]
            >>> run_id = plugin.emit_lineage_event(
            ...     event_type=RunState.COMPLETE,
            ...     job_name="dbt_run_stg_customers",
            ...     inputs=inputs,
            ...     outputs=outputs,
            ... )
        """
        ...

    def get_lineage_emitter(self) -> LineageEmitter | None:
        """Get the unified lineage emitter for this plugin.

        Returns:
            LineageEmitter instance, or None if not configured.
            Implementations should override to provide a real emitter.
        """
        return None

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

    def sensor_definition(self) -> Any | None:
        """Return optional sensor definition for event-driven orchestration.

        Sensors enable event-driven pipeline triggering beyond cron-based
        scheduling. Examples include health checks, file arrival sensors,
        or external system event listeners.

        Returns:
            Platform-specific sensor definition (e.g., Dagster SensorDefinition),
            or None if the plugin does not provide sensors.

        Example:
            >>> sensor = plugin.sensor_definition()
            >>> if sensor:
            ...     definitions = Definitions(assets=[...], sensors=[sensor])

        Requirements:
            FR-029: Auto-trigger demo pipeline on platform health
            FR-033: Health check integration for platform services
        """
        return None

    @abstractmethod
    def generate_entry_point_code(
        self,
        product_name: str,
        output_dir: str,
    ) -> str:
        """Generate orchestrator-specific entry point code file.

        Creates the entry point file that enables workspace discovery.
        Each orchestrator has its own format:
        - Dagster: definitions.py with Definitions object
        - Airflow: dag.py with DAG object
        - Prefect: flow.py with Flow object

        This method respects component ownership: floe-core provides data
        (CompiledArtifacts), orchestrator plugins own code generation.

        Args:
            product_name: Name from FloeSpec metadata (e.g., "customer-360").
            output_dir: Directory path where the entry point will be written.

        Returns:
            Path to the generated entry point file as string.

        Example:
            >>> path = plugin.generate_entry_point_code(
            ...     product_name="customer-360",
            ...     output_dir="/path/to/product",
            ... )
            >>> # For Dagster: returns "/path/to/product/definitions.py"
            >>> # For Airflow: returns "/path/to/product/dag.py"

        Requirements:
            - Component ownership: Orchestrator plugin owns its code generation
            - Spec 2b-compilation-pipeline: floe-core provides DATA, plugins own code

        See Also:
            - create_definitions(): Runtime definitions from artifacts
            - specs/2b-compilation-pipeline/spec.md: Technology ownership boundaries
        """
        ...
