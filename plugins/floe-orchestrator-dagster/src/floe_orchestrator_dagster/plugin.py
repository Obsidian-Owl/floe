"""Dagster orchestrator plugin for floe.

This module provides the DagsterOrchestratorPlugin implementation that enables
Dagster as the orchestration platform for floe data pipelines. The plugin
implements the OrchestratorPlugin ABC and provides:

- Generation of Dagster Definitions from CompiledArtifacts
- Creation of software-defined assets from dbt transforms
- Helm values for K8s deployment of Dagster services
- OpenLineage event emission for data lineage tracking
- Cron-based job scheduling with timezone support

Example:
    >>> from floe_orchestrator_dagster import DagsterOrchestratorPlugin
    >>> plugin = DagsterOrchestratorPlugin()
    >>> plugin.name
    'dagster'
    >>> definitions = plugin.create_definitions(compiled_artifacts)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError as PydanticValidationError

from floe_core.plugins.orchestrator import (
    Dataset,
    OrchestratorPlugin,
    ResourceSpec,
    TransformConfig,
    ValidationResult,
)
from floe_core.schemas import CompiledArtifacts

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Resource presets for Dagster workloads (following helm-values-schema.md)
_RESOURCE_PRESETS: dict[str, ResourceSpec] = {
    "small": ResourceSpec(
        cpu_request="100m",
        cpu_limit="500m",
        memory_request="256Mi",
        memory_limit="512Mi",
    ),
    "medium": ResourceSpec(
        cpu_request="250m",
        cpu_limit="1000m",
        memory_request="512Mi",
        memory_limit="1Gi",
    ),
    "large": ResourceSpec(
        cpu_request="500m",
        cpu_limit="2000m",
        memory_request="1Gi",
        memory_limit="2Gi",
    ),
}


class DagsterOrchestratorPlugin(OrchestratorPlugin):
    """Dagster orchestrator plugin for floe data platform.

    Implements the OrchestratorPlugin ABC to provide Dagster integration
    for floe data pipelines. Uses dagster-dbt for automatic manifest parsing
    and asset creation.

    Key Features:
        - Generates Dagster Definitions from CompiledArtifacts
        - Creates software-defined assets with dependency preservation
        - Provides Helm values for K8s deployment
        - Emits OpenLineage events for data lineage
        - Supports cron-based scheduling with timezone support

    Example:
        >>> plugin = DagsterOrchestratorPlugin()
        >>> plugin.name
        'dagster'
        >>> definitions = plugin.create_definitions(compiled_artifacts)

    See Also:
        - OrchestratorPlugin: Abstract base class defining the interface
        - specs/4b-orchestrator-plugin/spec.md: Feature specification
        - specs/4b-orchestrator-plugin/contracts/plugin-interface.md: Contract
    """

    @property
    def name(self) -> str:
        """Plugin name identifier.

        Returns:
            The string 'dagster'.
        """
        return "dagster"

    @property
    def version(self) -> str:
        """Plugin version in semver format.

        Returns:
            Current plugin version.
        """
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        """Required floe API version.

        Returns:
            Minimum compatible floe API version.
        """
        return "1.0"

    @property
    def description(self) -> str:
        """Human-readable plugin description.

        Returns:
            Description of the Dagster orchestrator plugin.
        """
        return "Dagster orchestrator for floe data pipelines"

    def _validate_artifacts(self, artifacts: dict[str, Any]) -> CompiledArtifacts:
        """Validate CompiledArtifacts schema before definition generation.

        Uses Pydantic validation to ensure the artifacts dict conforms to
        the CompiledArtifacts schema from floe-core.

        Args:
            artifacts: Dictionary to validate against CompiledArtifacts schema.

        Returns:
            Validated CompiledArtifacts model instance.

        Raises:
            ValueError: If validation fails, with actionable error message.
        """
        try:
            return CompiledArtifacts.model_validate(artifacts)
        except PydanticValidationError as e:
            # Format actionable error message
            error_details = []
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                error_details.append(f"  - {loc}: {msg}")

            error_message = (
                "CompiledArtifacts validation failed. "
                "Ensure you are passing output from 'floe compile'.\n"
                "Validation errors:\n"
                + "\n".join(error_details)
            )
            logger.error(
                "Artifacts validation failed",
                extra={"error_count": len(e.errors())},
            )
            raise ValueError(error_message) from e

    def create_definitions(self, artifacts: dict[str, Any]) -> Any:
        """Generate Dagster Definitions from CompiledArtifacts.

        Creates a Dagster Definitions object containing assets, jobs, resources,
        and schedules based on the compiled data product configuration.

        The method first validates the artifacts against the CompiledArtifacts
        schema, then extracts transforms and creates Dagster assets preserving
        the dependency graph.

        Args:
            artifacts: CompiledArtifacts dictionary containing dbt manifest,
                profiles, transforms, and other configuration.

        Returns:
            Dagster Definitions object ready for deployment.

        Raises:
            ValueError: If artifacts validation fails with actionable message.

        Example:
            >>> definitions = plugin.create_definitions(compiled_artifacts)
            >>> # Returns Dagster Definitions with assets from dbt models
        """
        from dagster import Definitions

        # Validate artifacts against CompiledArtifacts schema (FR-009)
        validated = self._validate_artifacts(artifacts)

        # Extract transforms from validated artifacts
        if validated.transforms is None:
            logger.warning("No transforms found in artifacts, returning empty Definitions")
            return Definitions(assets=[])

        # Get models list from transforms
        models = validated.transforms.models
        if not models:
            logger.warning("No models found in transforms, returning empty Definitions")
            return Definitions(assets=[])

        # Convert ResolvedModel to TransformConfig objects
        transform_configs = self._models_to_transform_configs(
            [model.model_dump() for model in models]
        )

        # Create assets from transforms
        assets = self.create_assets_from_transforms(transform_configs)

        logger.info(
            "Created Dagster Definitions",
            extra={"asset_count": len(assets), "model_count": len(models)},
        )

        return Definitions(assets=assets)

    def _models_to_transform_configs(
        self, models: list[dict[str, Any]]
    ) -> list[TransformConfig]:
        """Convert ResolvedModel dicts to TransformConfig objects.

        Maps the CompiledArtifacts ResolvedModel structure to the
        TransformConfig dataclass used by create_assets_from_transforms().

        Args:
            models: List of ResolvedModel dictionaries from CompiledArtifacts.

        Returns:
            List of TransformConfig objects.
        """
        configs = []
        for model in models:
            config = TransformConfig(
                name=model["name"],
                compute=model.get("compute"),
                tags=model.get("tags") or [],
                depends_on=model.get("depends_on") or [],
            )
            configs.append(config)
        return configs

    def create_assets_from_transforms(
        self, transforms: list[TransformConfig]
    ) -> list[Any]:
        """Create Dagster software-defined assets from dbt transforms.

        Converts TransformConfig objects into Dagster assets, preserving
        the dependency graph specified in the depends_on field.

        Args:
            transforms: List of TransformConfig objects representing dbt models.

        Returns:
            List of Dagster AssetsDefinition objects.

        Example:
            >>> transforms = [
            ...     TransformConfig(name="stg_customers", depends_on=["raw_customers"]),
            ...     TransformConfig(name="dim_customers", depends_on=["stg_customers"])
            ... ]
            >>> assets = plugin.create_assets_from_transforms(transforms)
            >>> len(assets)
            2
        """
        from dagster import AssetKey, AssetsDefinition

        assets: list[AssetsDefinition] = []

        for transform in transforms:
            # Convert depends_on names to AssetKeys
            deps = [AssetKey(dep) for dep in transform.depends_on]

            # Build metadata for the asset
            metadata = self._build_asset_metadata(transform)

            # Create the asset using @asset decorator factory
            asset_def = self._create_asset_for_transform(
                transform=transform,
                deps=deps,
                metadata=metadata,
            )
            assets.append(asset_def)

        logger.info(
            "Created assets from transforms",
            extra={"asset_count": len(assets)},
        )

        return assets

    def _build_asset_metadata(self, transform: TransformConfig) -> dict[str, Any]:
        """Build metadata dict for a transform asset.

        Args:
            transform: The TransformConfig to extract metadata from.

        Returns:
            Dictionary of metadata for the Dagster asset.
        """
        metadata: dict[str, Any] = {}

        if transform.compute:
            metadata["compute"] = transform.compute
        if transform.schema_name:
            metadata["schema"] = transform.schema_name
        if transform.materialization:
            metadata["materialization"] = transform.materialization
        if transform.tags:
            metadata["tags"] = transform.tags
        if transform.path:
            metadata["path"] = transform.path

        return metadata

    def _create_asset_for_transform(
        self,
        transform: TransformConfig,
        deps: list[Any],
        metadata: dict[str, Any],
    ) -> Any:
        """Create a Dagster asset definition for a single transform.

        Uses the @asset decorator to create a software-defined asset that
        represents the dbt model. The asset is a placeholder that can be
        materialized by the dbt resource.

        Args:
            transform: TransformConfig with model details.
            deps: List of AssetKey dependencies.
            metadata: Metadata dictionary for the asset.

        Returns:
            AssetsDefinition for the transform.
        """
        from dagster import asset

        # Create asset with proper dependencies and metadata
        # Note: We avoid type annotations in the inner function due to
        # Dagster's type hint resolution with `from __future__ import annotations`
        @asset(
            name=transform.name,
            deps=deps if deps else None,
            metadata=metadata if metadata else None,
            description=f"dbt model: {transform.name}",
        )
        def _asset_fn():
            """Placeholder asset for dbt model.

            Actual materialization happens via dbt resource integration.
            """
            return None

        return _asset_fn

    def get_helm_values(self) -> dict[str, Any]:
        """Return Helm chart values for deploying Dagster services.

        Provides configuration values for the floe-dagster Helm chart,
        including resource requests/limits and service configuration
        for webserver, daemon, and user-code components.

        The returned structure follows the helm-values-schema.md contract
        and includes default resource allocations for development workloads.

        Returns:
            Dictionary matching the floe-dagster Helm chart schema with
            dagster-webserver, dagster-daemon, dagster-user-code, and
            postgresql configuration.

        Example:
            >>> values = plugin.get_helm_values()
            >>> values["dagster-webserver"]["enabled"]
            True
            >>> values["dagster-daemon"]["replicaCount"]
            1
        """
        # Default resource allocations (small/development preset)
        small_resources = {
            "requests": {"cpu": "100m", "memory": "256Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"},
        }

        user_code_resources = {
            "requests": {"cpu": "250m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "1Gi"},
        }

        return {
            "dagster-webserver": {
                "enabled": True,
                "replicaCount": 1,
                "resources": small_resources.copy(),
            },
            "dagster-daemon": {
                "enabled": True,
                "replicaCount": 1,
                "resources": small_resources.copy(),
            },
            "dagster-user-code": {
                "enabled": True,
                "replicaCount": 1,
                "resources": user_code_resources.copy(),
            },
            "postgresql": {
                "enabled": True,
            },
        }

    def validate_connection(self) -> ValidationResult:
        """Test connectivity to Dagster service.

        Performs an HTTP health check to the Dagster GraphQL API
        to verify the orchestration service is reachable.
        Completes within 10 seconds.

        Returns:
            ValidationResult with success status and actionable error messages.

        Example:
            >>> result = plugin.validate_connection()
            >>> if result.success:
            ...     print("Connected to Dagster")
        """
        # Placeholder - will be implemented in T024
        raise NotImplementedError("validate_connection will be implemented in T024")

    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements for Dagster workloads.

        Provides CPU and memory requests/limits based on workload size
        for Dagster service pods. Uses predefined presets for consistency.

        Args:
            workload_size: One of "small", "medium", "large".
                - small: Development workloads (100m-500m CPU, 256Mi-512Mi memory)
                - medium: Staging workloads (250m-1000m CPU, 512Mi-1Gi memory)
                - large: Production workloads (500m-2000m CPU, 1Gi-2Gi memory)

        Returns:
            ResourceSpec with K8s-compatible resource specifications.

        Raises:
            ValueError: If workload_size is not one of the valid options.

        Example:
            >>> spec = plugin.get_resource_requirements("medium")
            >>> spec.memory_limit
            '1Gi'
        """
        if workload_size not in _RESOURCE_PRESETS:
            valid_sizes = ", ".join(sorted(_RESOURCE_PRESETS.keys()))
            raise ValueError(
                f"Invalid workload_size '{workload_size}'. "
                f"Must be one of: {valid_sizes}"
            )

        return _RESOURCE_PRESETS[workload_size]

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
            >>> plugin.emit_lineage_event("COMPLETE", "dbt_run", inputs, outputs)
        """
        # Placeholder - will be implemented in T021
        raise NotImplementedError("emit_lineage_event will be implemented in T021")

    def _validate_cron(self, cron: str) -> None:
        """Validate cron expression format.

        Uses croniter library to verify the cron expression is syntactically valid.

        Args:
            cron: Cron expression to validate (e.g., "0 8 * * *").

        Raises:
            ValueError: If cron expression is invalid, with format guidance.
        """
        from croniter import croniter

        if not cron or not cron.strip():
            raise ValueError(
                "Invalid cron expression: empty string. "
                "Expected format: 'minute hour day month weekday' (e.g., '0 8 * * *')"
            )

        try:
            # croniter.is_valid returns True/False but doesn't give details
            # Instantiating it will raise if invalid
            croniter(cron)
        except (ValueError, KeyError) as e:
            raise ValueError(
                f"Invalid cron expression: '{cron}'. "
                f"Expected format: 'minute hour day month weekday' (e.g., '0 8 * * *'). "
                f"Error: {e}"
            ) from e

    def _validate_timezone(self, timezone: str) -> None:
        """Validate IANA timezone identifier.

        Uses pytz library to verify the timezone is a valid IANA timezone.

        Args:
            timezone: IANA timezone identifier (e.g., "America/New_York", "UTC").

        Raises:
            ValueError: If timezone is invalid, listing common valid examples.
        """
        import pytz

        if not timezone or not timezone.strip():
            raise ValueError(
                "Invalid timezone: empty string. "
                "Expected IANA timezone (e.g., 'UTC', 'America/New_York', 'Europe/London')"
            )

        try:
            pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError as e:
            raise ValueError(
                f"Invalid timezone: '{timezone}'. "
                "Expected valid IANA timezone. "
                "Examples: 'UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo'"
            ) from e

    def schedule_job(self, job_name: str, cron: str, timezone: str) -> None:
        """Schedule a job for recurring execution.

        Creates a Dagster ScheduleDefinition for the specified job
        using a cron expression in the given timezone. The schedule
        is stored internally and can be included in Definitions.

        Args:
            job_name: Name of the job to schedule.
            cron: Cron expression (e.g., "0 8 * * *" for 8 AM daily).
            timezone: IANA timezone (e.g., "America/New_York", "UTC").

        Raises:
            ValueError: If cron expression is invalid.
            ValueError: If timezone is not a valid IANA timezone.

        Example:
            >>> plugin.schedule_job("daily_refresh", "0 8 * * *", "America/New_York")
        """
        from dagster import ScheduleDefinition

        # Validate inputs (FR-014, FR-015)
        self._validate_cron(cron)
        self._validate_timezone(timezone)

        # Create the ScheduleDefinition (FR-013)
        schedule = ScheduleDefinition(
            name=f"{job_name}_schedule",
            job_name=job_name,
            cron_schedule=cron,
            execution_timezone=timezone,
        )

        # Store schedule for later retrieval
        if not hasattr(self, "_schedules"):
            self._schedules: list[Any] = []
        self._schedules.append(schedule)

        logger.info(
            "Schedule created",
            extra={
                "job_name": job_name,
                "cron": cron,
                "timezone": timezone,
                "schedule_name": schedule.name,
            },
        )
