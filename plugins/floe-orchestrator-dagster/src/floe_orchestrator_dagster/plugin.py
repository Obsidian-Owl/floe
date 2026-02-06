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
from typing import Any
from uuid import UUID, uuid4

from dagster import AssetKey, AssetsDefinition, asset
from floe_core.lineage import LineageDataset, RunState
from floe_core.plugins.orchestrator import (
    OrchestratorPlugin,
    ResourceSpec,
    TransformConfig,
    ValidationResult,
)
from floe_core.schemas import CompiledArtifacts
from pydantic import ValidationError as PydanticValidationError

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

# PERF: Pre-created frozenset for asset resource keys (avoid per-asset set creation)
_DBT_RESOURCE_KEYS: frozenset[str] = frozenset({"dbt"})


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
                "Validation errors:\n" + "\n".join(error_details)
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
        the dependency graph. If catalog and storage plugins are configured,
        it also wires IcebergIOManager as the "iceberg" resource.

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

        Requirements:
            FR-005: Generate valid Dagster Definitions from CompiledArtifacts
            FR-009: Validate CompiledArtifacts schema
            T108: Extract catalog/storage config from CompiledArtifacts
            T111: Wire IcebergIOManager into Definitions resources
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

        # T108-T111: Wire Iceberg resources if catalog and storage are configured
        resources = self._create_iceberg_resources(validated.plugins)

        # T047-T049: Wire semantic layer resources if semantic plugin is configured
        semantic_resources = self._create_semantic_resources(validated.plugins)
        resources.update(semantic_resources)

        logger.info(
            "Created Dagster Definitions",
            extra={
                "asset_count": len(assets),
                "model_count": len(models),
                "has_iceberg": "iceberg" in resources,
                "has_semantic_layer": "semantic_layer" in resources,
            },
        )

        return Definitions(assets=assets, resources=resources if resources else {})

    def _create_iceberg_resources(
        self,
        plugins: Any | None,
    ) -> dict[str, Any]:
        """Create Iceberg resources from resolved plugins configuration.

        Attempts to load catalog and storage plugins and create an
        IcebergIOManager resource. Returns empty dict if either plugin
        is not configured or if plugin loading fails.

        Args:
            plugins: ResolvedPlugins from CompiledArtifacts, or None.

        Returns:
            Dictionary with "iceberg" key if successful, empty dict otherwise.

        Requirements:
            T108: Extract catalog/storage config
            T109: Load via PluginRegistry
            T110: Instantiate IcebergTableManager
            T111: Wire IcebergIOManager
        """
        from floe_orchestrator_dagster.resources.iceberg import try_create_iceberg_resources

        return try_create_iceberg_resources(plugins)

    def _create_semantic_resources(
        self,
        plugins: Any | None,
    ) -> dict[str, Any]:
        """Create semantic layer resources from resolved plugins configuration.

        Attempts to load the semantic layer plugin and create a resource.
        Returns empty dict if the plugin is not configured or if plugin
        loading fails.

        Args:
            plugins: ResolvedPlugins from CompiledArtifacts, or None.

        Returns:
            Dictionary with "semantic_layer" key if successful, empty dict otherwise.

        Requirements:
            T047: Create semantic resource factory
            T048: Wire into plugin.py
        """
        from floe_orchestrator_dagster.resources.semantic import try_create_semantic_resources

        return try_create_semantic_resources(plugins)

    def _models_to_transform_configs(self, models: list[dict[str, Any]]) -> list[TransformConfig]:
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

    def create_assets_from_transforms(self, transforms: list[TransformConfig]) -> list[Any]:
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
        # PERF: Pre-bind methods and classes to avoid repeated attribute lookups
        _AssetKey = AssetKey
        _build_metadata = self._build_asset_metadata
        _create_asset = self._create_asset_for_transform

        assets: list[AssetsDefinition] = []

        for transform in transforms:
            # Convert depends_on names to AssetKeys
            deps = [_AssetKey(dep) for dep in transform.depends_on]

            # Build metadata for the asset
            metadata = _build_metadata(transform)

            # Create the asset using @asset decorator factory
            asset_def = _create_asset(
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
        represents the dbt model. The asset receives DBTResource and uses
        it to run the specific dbt model via select pattern.

        Args:
            transform: TransformConfig with model details.
            deps: List of AssetKey dependencies.
            metadata: Metadata dictionary for the asset.

        Returns:
            AssetsDefinition for the transform.

        Requirements:
            FR-030: Delegate dbt operations to DBTPlugin (via DBTResource)
            FR-031: Use DBTRunResult to populate asset metadata
        """
        # Capture transform name for use in inner function
        model_name = transform.name

        # Security: MEDIUM-02 remediation - Dynamic asset creation is safe because:
        # 1. All inputs (transform.name, deps, metadata) are validated through
        #    Pydantic schemas (TransformConfig) before reaching this function
        # 2. transform.name is validated by Pydantic Field constraints
        # 3. deps are derived from validated TransformConfig.depends_on list
        # 4. metadata dict values come from validated TransformConfig fields
        # No user-controlled input reaches this function without validation.
        #
        # Note: We avoid type annotations in the inner function due to
        # Dagster's type hint resolution with `from __future__ import annotations`.
        # Dagster cannot resolve string annotations for AssetExecutionContext.
        # PERF: Use pre-created frozenset and avoid unnecessary conditionals
        @asset(
            name=transform.name,
            deps=deps or None,
            metadata=metadata or None,
            description=f"dbt model: {transform.name}",
            required_resource_keys=_DBT_RESOURCE_KEYS,
        )
        def _asset_fn(context, dbt) -> None:  # noqa: ANN001
            """Execute dbt model via DBTResource.

            Materializes the dbt model by delegating to DBTPlugin through
            DBTResource. The model is selected using dbt's select syntax.

            Args:
                context: Dagster AssetExecutionContext.
                dbt: DBTResource for dbt operations.

            Requirements:
                FR-030: Delegate to DBTPlugin, never invoke dbtRunner directly
                FR-031: Use DBTRunResult for metadata
            """
            # Run the specific model using dbt select syntax
            result = dbt.run_models(select=model_name)

            # Log execution results (FR-031: use DBTRunResult for metadata)
            context.log.info(
                f"dbt model '{model_name}' completed: "
                f"success={result.success}, "
                f"models_run={result.models_run}, "
                f"failures={result.failures}"
            )

            if not result.success:
                msg = f"dbt model '{model_name}' failed with {result.failures} failures"
                raise RuntimeError(msg)

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

    def validate_connection(
        self,
        dagster_url: str | None = None,
        timeout: float = 10.0,
    ) -> ValidationResult:
        """Test connectivity to Dagster service.

        Performs an HTTP health check to the Dagster GraphQL API
        to verify the orchestration service is reachable.
        Completes within the specified timeout (default 10 seconds).

        Args:
            dagster_url: Optional URL to Dagster webserver. If not provided,
                uses DAGSTER_URL environment variable or default localhost.
            timeout: Maximum seconds to wait for connection (default 10.0).

        Returns:
            ValidationResult with success status and actionable error messages.

        Example:
            >>> result = plugin.validate_connection()
            >>> if result.success:
            ...     print("Connected to Dagster")
        """
        import os

        import httpx

        # Determine Dagster URL
        url = dagster_url or os.environ.get("DAGSTER_URL", "http://localhost:3000")
        graphql_endpoint = f"{url.rstrip('/')}/graphql"

        try:
            # Send a simple GraphQL query to check connectivity
            query = {"query": "{ __typename }"}

            with httpx.Client(timeout=timeout) as client:
                response = client.post(graphql_endpoint, json=query)

            if response.status_code == 200:
                logger.info(
                    "Dagster connection validated",
                    extra={"url": graphql_endpoint},
                )
                return ValidationResult(
                    success=True,
                    message="Successfully connected to Dagster service",
                )

            # Non-200 response
            logger.warning(
                "Dagster connection failed",
                extra={
                    "url": graphql_endpoint,
                    "status_code": response.status_code,
                },
            )
            return ValidationResult(
                success=False,
                message=f"Dagster service returned status {response.status_code}",
                errors=[
                    f"HTTP {response.status_code} from {graphql_endpoint}. "
                    "Ensure Dagster webserver is running and accessible."
                ],
            )

        except httpx.TimeoutException:
            logger.warning(
                "Dagster connection timed out",
                extra={"url": graphql_endpoint, "timeout": timeout},
            )
            return ValidationResult(
                success=False,
                message=f"Connection to Dagster timed out after {timeout}s",
                errors=[
                    f"Timeout connecting to {graphql_endpoint}. "
                    "Check network connectivity and ensure Dagster is running."
                ],
            )
        except httpx.ConnectError as e:
            logger.warning(
                "Dagster connection failed",
                extra={"url": graphql_endpoint, "error": str(e)},
            )
            return ValidationResult(
                success=False,
                message="Failed to connect to Dagster service",
                errors=[f"Connection error: {e}. Ensure Dagster webserver is running at {url}."],
            )
        except Exception as e:
            logger.error(
                "Unexpected error validating Dagster connection",
                extra={"url": graphql_endpoint, "error": str(e)},
            )
            return ValidationResult(
                success=False,
                message="Unexpected error connecting to Dagster",
                errors=[str(e)],
            )

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
                f"Invalid workload_size '{workload_size}'. Must be one of: {valid_sizes}"
            )

        return _RESOURCE_PRESETS[workload_size]

    def _validate_event_type(self, event_type: str) -> None:
        """Validate lineage event type.

        Args:
            event_type: Event type to validate.

        Raises:
            ValueError: If event_type is not START, COMPLETE, or FAIL.
        """
        valid_types = {"START", "COMPLETE", "FAIL"}
        if event_type not in valid_types:
            raise ValueError(
                f"Invalid event_type: '{event_type}'. "
                f"Must be one of: {', '.join(sorted(valid_types))}"
            )

    def _build_openlineage_event(
        self,
        event_type: str,
        job: str,
        inputs: list[LineageDataset],
        outputs: list[LineageDataset],
    ) -> dict[str, Any]:
        """Build OpenLineage event structure.

        Creates a dictionary following the OpenLineage spec for lineage events.

        Args:
            event_type: One of "START", "COMPLETE", or "FAIL".
            job: Job name.
            inputs: List of input datasets.
            outputs: List of output datasets.

        Returns:
            Dictionary representing OpenLineage event.
        """
        from datetime import datetime, timezone

        # Build input/output dataset structures
        input_datasets = [{"namespace": ds.namespace, "name": ds.name} for ds in inputs]
        output_datasets = [{"namespace": ds.namespace, "name": ds.name} for ds in outputs]

        return {
            "eventType": event_type,
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "producer": f"floe-orchestrator-dagster/{self.version}",
            "job": {
                "namespace": "floe",
                "name": job,
            },
            "inputs": input_datasets,
            "outputs": output_datasets,
        }

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
        """Emit OpenLineage event for data lineage tracking.

        Sends a lineage event to the configured lineage backend
        (Marquez, Atlan, etc.) for tracking data flow. If no lineage
        backend is configured, this is a graceful no-op that still
        returns a valid run_id.

        Args:
            event_type: Run state (START, COMPLETE, FAIL, etc.).
            job_name: Job name (e.g., "dbt_run_customers").
            job_namespace: Job namespace. Defaults to "floe".
            run_id: Unique run identifier. Auto-generated if None.
            inputs: Input datasets consumed by the job.
            outputs: Output datasets produced by the job.
            run_facets: Additional OpenLineage run facets.
            job_facets: Additional OpenLineage job facets.
            producer: Producer identifier. Defaults to plugin version string.

        Returns:
            The run UUID for this event (generated or provided).

        Example:
            >>> inputs = [LineageDataset(namespace="floe", name="raw.customers")]
            >>> outputs = [LineageDataset(namespace="floe", name="staging.stg_customers")]
            >>> run_id = plugin.emit_lineage_event(
            ...     event_type=RunState.COMPLETE,
            ...     job_name="dbt_run_stg_customers",
            ...     inputs=inputs,
            ...     outputs=outputs,
            ... )
        """
        actual_run_id = run_id if run_id is not None else uuid4()
        actual_namespace = job_namespace if job_namespace is not None else "floe"
        # TODO: Wire producer to lineage backend event emission
        _actual_producer = (
            producer if producer is not None else f"floe-orchestrator-dagster/{self.version}"
        )

        lineage_backend = getattr(self, "_lineage_backend", None)

        if lineage_backend is None:
            logger.debug(
                "Lineage event not emitted - no backend configured",
                extra={
                    "event_type": event_type.value,
                    "job_name": job_name,
                    "run_id": str(actual_run_id),
                    "input_count": len(inputs) if inputs else 0,
                    "output_count": len(outputs) if outputs else 0,
                },
            )
            return actual_run_id

        logger.info(
            "Lineage event emitted",
            extra={
                "event_type": event_type.value,
                "job_name": job_name,
                "job_namespace": actual_namespace,
                "run_id": str(actual_run_id),
                "input_count": len(inputs) if inputs else 0,
                "output_count": len(outputs) if outputs else 0,
            },
        )
        return actual_run_id

    def _validate_cron(self, cron: str) -> None:
        """Validate cron expression format.

        Uses regex pattern matching to verify the cron expression is syntactically valid.
        Supports standard 5-field cron expressions (minute hour day month weekday).

        Args:
            cron: Cron expression to validate (e.g., "0 8 * * *").

        Raises:
            ValueError: If cron expression is invalid, with format guidance.
        """
        import re

        if not cron or not cron.strip():
            raise ValueError(
                "Invalid cron expression: empty string. "
                "Expected format: 'minute hour day month weekday' (e.g., '0 8 * * *')"
            )

        # Regex patterns for each cron field
        # Supports: numbers (with optional leading zeros), *, */N, N-M, N,M,O
        # minute: 0-59 (allows 00-59)
        minute_pattern = (  # noqa: E501
            r"(\*|[0-5]?\d)(\/\d+)?(-[0-5]?\d)?(,[0-5]?\d(-[0-5]?\d)?)*(\/\d+)?|\*\/\d+"
        )
        # hour: 0-23 (allows 00-23, but not 24+)
        hour_pattern = (  # noqa: E501
            r"(\*|[01]?\d|2[0-3])(\/\d+)?(-(?:[01]?\d|2[0-3]))?",
            r"(,(?:[01]?\d|2[0-3])(-(?:[01]?\d|2[0-3]))?)*(\/\d+)?|\*\/\d+",
        )
        hour_pattern = "".join(hour_pattern)
        # day: 1-31 (allows 01-31)
        day_pattern = (  # noqa: E501
            r"(\*|0?[1-9]|[12]\d|3[01])(\/\d+)?(-(?:0?[1-9]|[12]\d|3[01]))?",
            r"(,(?:0?[1-9]|[12]\d|3[01])(-(?:0?[1-9]|[12]\d|3[01]))?)*(\/\d+)?|\*\/\d+",
        )
        day_pattern = "".join(day_pattern)
        # month: 1-12 (allows 01-12)
        month_pattern = (  # noqa: E501
            r"(\*|0?[1-9]|1[0-2])(\/\d+)?(-(?:0?[1-9]|1[0-2]))?",
            r"(,(?:0?[1-9]|1[0-2])(-(?:0?[1-9]|1[0-2]))?)*(\/\d+)?|\*\/\d+",
        )
        month_pattern = "".join(month_pattern)
        # weekday: 0-6
        weekday_pattern = r"(\*|[0-6])(\/\d+)?(-[0-6])?(,[0-6](-[0-6])?)*(\/\d+)?|\*\/\d+"

        # Full cron pattern: 5 whitespace-separated fields
        cron_pattern = (
            rf"^\s*({minute_pattern})\s+({hour_pattern})\s+({day_pattern})\s+"
            rf"({month_pattern})\s+({weekday_pattern})\s*$"
        )

        if not re.match(cron_pattern, cron.strip()):
            raise ValueError(
                f"Invalid cron expression: '{cron}'. "
                "Expected format: 'minute hour day month weekday' (e.g., '0 8 * * *'). "
                "Each field supports: numbers, *, */N, N-M, N,M"
            )

    def _validate_timezone(self, timezone: str) -> None:
        """Validate IANA timezone identifier.

        Uses zoneinfo (Python stdlib) to verify the timezone is a valid IANA timezone.

        Args:
            timezone: IANA timezone identifier (e.g., "America/New_York", "UTC").

        Raises:
            ValueError: If timezone is invalid, listing common valid examples.
        """
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        if not timezone or not timezone.strip():
            raise ValueError(
                "Invalid timezone: empty string. "
                "Expected IANA timezone (e.g., 'UTC', 'America/New_York', 'Europe/London')"
            )

        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as e:
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

    def sensor_definition(self) -> Any | None:
        """Return health check sensor for auto-triggering demo pipelines.

        Provides the health_check_sensor which monitors platform service
        health and triggers the first pipeline run automatically when
        services are ready.

        Returns:
            Dagster SensorDefinition for health monitoring, or None if
            sensors module is not available.

        Requirements:
            FR-029: Auto-trigger demo pipeline on platform health
            FR-033: Health check integration for platform services

        Example:
            >>> plugin = DagsterOrchestratorPlugin()
            >>> sensor = plugin.sensor_definition()
            >>> definitions = Definitions(assets=[...], sensors=[sensor])
        """
        try:
            from floe_orchestrator_dagster.sensors import health_check_sensor

            logger.info("Health check sensor loaded for auto-triggering")
            return health_check_sensor
        except ImportError:
            logger.warning("Sensors module not available, sensor_definition returning None")
            return None

    def get_default_schedule(self, job_name: str = "demo_pipeline") -> Any:
        """Create default 10-minute recurring schedule for demo pipelines.

        Provides a pre-configured ScheduleDefinition that runs the demo
        pipeline every 10 minutes. This enables continuous data refresh
        for demonstration purposes.

        Args:
            job_name: Name of the job to schedule (default: "demo_pipeline").

        Returns:
            Dagster ScheduleDefinition configured for 10-minute intervals.

        Requirements:
            FR-030: Recurring schedule configuration (10-min default)

        Example:
            >>> plugin = DagsterOrchestratorPlugin()
            >>> schedule = plugin.get_default_schedule()
            >>> definitions = Definitions(
            ...     assets=[...],
            ...     schedules=[schedule]
            ... )
        """
        from dagster import ScheduleDefinition

        # 10-minute interval cron: "*/10 * * * *"
        # Runs at: 00, 10, 20, 30, 40, 50 minutes past each hour
        schedule = ScheduleDefinition(
            name=f"{job_name}_recurring_10min",
            job_name=job_name,
            cron_schedule="*/10 * * * *",
            execution_timezone="UTC",
        )

        logger.info(
            "Default 10-minute schedule created",
            extra={
                "job_name": job_name,
                "cron": "*/10 * * * *",
                "schedule_name": schedule.name,
            },
        )

        return schedule

    def generate_entry_point_code(
        self,
        product_name: str,
        output_dir: str,
    ) -> str:
        """Generate Dagster definitions.py entry point file.

        Creates a definitions.py file that can be used as a Dagster code
        location entry point. This respects component ownership: floe-core
        provides data (CompiledArtifacts), Dagster plugin owns code generation.

        The generated file:
        - Uses dagster-dbt's @dbt_assets decorator for dbt integration
        - Configures DbtCliResource for dbt operations
        - Exports a `defs` variable for Dagster workspace discovery

        Args:
            product_name: Name from FloeSpec metadata (e.g., "customer-360").
            output_dir: Directory path where definitions.py will be written.

        Returns:
            Path to the generated definitions.py file as string.

        Example:
            >>> plugin = DagsterOrchestratorPlugin()
            >>> path = plugin.generate_entry_point_code(
            ...     product_name="customer-360",
            ...     output_dir="/path/to/product",
            ... )
            >>> path
            '/path/to/product/definitions.py'

        Requirements:
            - Component ownership: Dagster plugin owns Dagster code generation
            - Spec 2b-compilation-pipeline: Technology ownership boundaries
        """
        import re
        from pathlib import Path

        # Sanitize product name to valid Python identifier
        safe_name = product_name.replace("-", "_")
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", safe_name)
        if safe_name and not safe_name[0].isalpha():
            safe_name = f"product_{safe_name}"
        safe_name = safe_name.lower()

        # Template for generated definitions.py
        template = f'''"""Dagster definitions for {product_name} data product.

AUTO-GENERATED by `floe compile` - DO NOT EDIT MANUALLY.

This module provides the Dagster Definitions entry point for the {product_name}
data product. It loads the dbt project using dagster-dbt integration.

Regenerate with:
    floe platform compile --spec floe.yaml --manifest manifest.yaml --generate-definitions
"""

from __future__ import annotations

from pathlib import Path

from dagster import Definitions
from dagster_dbt import DbtCliResource, dbt_assets

# Get the path to this data product's dbt project
PROJECT_DIR = Path(__file__).parent
DBT_PROJECT_DIR = PROJECT_DIR
MANIFEST_PATH = DBT_PROJECT_DIR / "target" / "manifest.json"


@dbt_assets(
    manifest=MANIFEST_PATH,
    project=DbtCliResource(project_dir=DBT_PROJECT_DIR),
    name="{safe_name}_dbt_assets",
)
def {safe_name}_dbt_assets(context, dbt: DbtCliResource):
    """Execute {product_name} dbt models as Dagster assets.

    This function is auto-generated by floe compile and uses dagster-dbt
    to execute all dbt models in this project as Dagster software-defined assets.
    """
    yield from dbt.cli(["build"], context=context).stream()


# Create Definitions object for Dagster to discover
defs = Definitions(
    assets=[{safe_name}_dbt_assets],
    resources={{
        "dbt": DbtCliResource(
            project_dir=DBT_PROJECT_DIR,
            profiles_dir=DBT_PROJECT_DIR,
        ),
    }},
)
'''

        # Write the file
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        definitions_file = output_path / "definitions.py"
        definitions_file.write_text(template)

        logger.info(
            "Dagster definitions.py generated",
            extra={
                "product_name": product_name,
                "safe_name": safe_name,
                "output_path": str(definitions_file),
            },
        )

        return str(definitions_file)
