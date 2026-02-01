"""Pydantic schemas for Helm values generation.

This module defines the data models used by the HelmValuesGenerator
to produce environment-specific Helm values from CompiledArtifacts.

Models:
    ResourceSpec: CPU/memory resource requests and limits
    ResourcePreset: Named resource configuration (small, medium, large)
    ClusterConfig: Physical cluster configuration
    ClusterMapping: Logical-to-physical environment mapping
    HelmValuesConfig: Complete Helm values generation configuration

Example:
    >>> from floe_core.helm.schemas import ClusterMapping, ResourcePreset
    >>> mapping = ClusterMapping(
    ...     non_prod=ClusterConfig(
    ...         cluster="aks-nonprod",
    ...         environments=["dev", "staging"],
    ...         namespace_template="floe-{{ environment }}"
    ...     )
    ... )
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResourceSpec(BaseModel):
    """Kubernetes resource specification for CPU and memory.

    Attributes:
        cpu: CPU request/limit (e.g., "100m", "1", "2000m")
        memory: Memory request/limit (e.g., "256Mi", "1Gi", "2048Mi")
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cpu: str = Field(
        ...,
        description="CPU allocation (e.g., '100m', '1', '2000m')",
        pattern=r"^[0-9]+m?$",
    )
    memory: str = Field(
        ...,
        description="Memory allocation (e.g., '256Mi', '1Gi')",
        pattern=r"^[0-9]+(Mi|Gi|Ki)$",
    )


class ResourceRequirements(BaseModel):
    """Kubernetes resource requirements with requests and limits.

    Attributes:
        requests: Minimum resources guaranteed to the container
        limits: Maximum resources the container can use
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requests: ResourceSpec = Field(..., description="Resource requests")
    limits: ResourceSpec = Field(..., description="Resource limits")


class ResourcePreset(BaseModel):
    """Named resource configuration preset.

    Presets provide a convenient way to apply consistent resource
    configurations across environments (e.g., small for dev, large for prod).

    Attributes:
        name: Preset name (small, medium, large, custom)
        resources: Resource requirements for this preset
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description="Preset name",
        pattern=r"^[a-z][a-z0-9-]*$",
    )
    resources: ResourceRequirements = Field(..., description="Resource configuration")

    @classmethod
    def small(cls) -> ResourcePreset:
        """Create a small resource preset suitable for development."""
        return cls(
            name="small",
            resources=ResourceRequirements(
                requests=ResourceSpec(cpu="100m", memory="256Mi"),
                limits=ResourceSpec(cpu="500m", memory="512Mi"),
            ),
        )

    @classmethod
    def medium(cls) -> ResourcePreset:
        """Create a medium resource preset suitable for staging."""
        return cls(
            name="medium",
            resources=ResourceRequirements(
                requests=ResourceSpec(cpu="250m", memory="512Mi"),
                limits=ResourceSpec(cpu="1000m", memory="1Gi"),
            ),
        )

    @classmethod
    def large(cls) -> ResourcePreset:
        """Create a large resource preset suitable for production."""
        return cls(
            name="large",
            resources=ResourceRequirements(
                requests=ResourceSpec(cpu="500m", memory="1Gi"),
                limits=ResourceSpec(cpu="2000m", memory="2Gi"),
            ),
        )


class ClusterConfig(BaseModel):
    """Physical cluster configuration for environment deployment.

    Attributes:
        cluster: Kubernetes cluster context name (empty for current context)
        environments: List of logical environments deployed to this cluster
        namespace_template: Template for namespace naming (supports {{ environment }})
        resource_preset: Resource preset name for this cluster's deployments
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cluster: str = Field(
        default="",
        description="Kubernetes cluster context name",
    )
    environments: list[str] = Field(
        ...,
        description="Logical environments on this cluster",
        min_length=1,
    )
    namespace_template: str = Field(
        default="floe-{{ environment }}",
        description="Namespace naming template",
    )
    resource_preset: str = Field(
        default="small",
        description="Resource preset name",
    )

    @field_validator("environments")
    @classmethod
    def validate_environments(cls, v: list[str]) -> list[str]:
        """Validate environment names are lowercase alphanumeric."""
        for env in v:
            if not env.replace("-", "").replace("_", "").isalnum():
                msg = f"Environment name must be alphanumeric: {env}"
                raise ValueError(msg)
        return v


class ClusterMapping(BaseModel):
    """Maps logical environments to physical cluster configurations.

    This model implements the logical-to-physical environment mapping
    described in ADR-0042. Multiple logical environments (dev, qa, staging)
    can be deployed to a single physical cluster with namespace isolation.

    Attributes:
        clusters: Dictionary of cluster configurations by name

    Example:
        >>> mapping = ClusterMapping(clusters={
        ...     "non-prod": ClusterConfig(
        ...         cluster="aks-nonprod",
        ...         environments=["dev", "qa", "staging"]
        ...     ),
        ...     "prod": ClusterConfig(
        ...         cluster="aks-prod",
        ...         environments=["prod"]
        ...     )
        ... })
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    clusters: dict[str, ClusterConfig] = Field(
        default_factory=dict,
        description="Cluster configurations by name",
    )

    def get_cluster_for_environment(self, environment: str) -> ClusterConfig | None:
        """Find the cluster configuration for a given environment.

        Args:
            environment: Logical environment name (e.g., "staging")

        Returns:
            ClusterConfig if found, None otherwise
        """
        for config in self.clusters.values():
            if environment in config.environments:
                return config
        return None

    def get_namespace(self, environment: str) -> str:
        """Get the namespace for a given environment.

        Args:
            environment: Logical environment name

        Returns:
            Namespace name rendered from template, or default format

        Raises:
            ValueError: If environment is not found in any cluster
        """
        config = self.get_cluster_for_environment(environment)
        if config is None:
            msg = f"Environment not found in cluster mapping: {environment}"
            raise ValueError(msg)

        # Simple template replacement ({{ environment }} -> env value)
        return config.namespace_template.replace("{{ environment }}", environment)


class HelmValuesConfig(BaseModel):
    """Configuration for Helm values generation.

    This model captures all settings needed to generate environment-specific
    Helm values from CompiledArtifacts.

    Attributes:
        environment: Target environment (dev, staging, prod)
        cluster_mapping: Logical-to-physical environment mapping
        resource_presets: Available resource presets by name
        enable_autoscaling: Enable HPA for scalable components
        enable_network_policies: Enable NetworkPolicy resources
        enable_pod_disruption_budget: Enable PDB for HA
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    environment: str = Field(
        default="dev",
        description="Target environment",
    )
    cluster_mapping: ClusterMapping = Field(
        default_factory=ClusterMapping,
        description="Environment to cluster mapping",
    )
    resource_presets: dict[str, ResourcePreset] = Field(
        default_factory=dict,
        description="Available resource presets",
    )
    enable_autoscaling: bool = Field(
        default=False,
        description="Enable HorizontalPodAutoscaler",
    )
    enable_network_policies: bool = Field(
        default=False,
        description="Enable NetworkPolicy resources",
    )
    enable_pod_disruption_budget: bool = Field(
        default=False,
        description="Enable PodDisruptionBudget",
    )

    @classmethod
    def with_defaults(cls, environment: str = "dev") -> HelmValuesConfig:
        """Create configuration with sensible defaults.

        Args:
            environment: Target environment

        Returns:
            HelmValuesConfig with default presets and mapping
        """
        return cls(
            environment=environment,
            resource_presets={
                "small": ResourcePreset.small(),
                "medium": ResourcePreset.medium(),
                "large": ResourcePreset.large(),
            },
            cluster_mapping=ClusterMapping(
                clusters={
                    "non-prod": ClusterConfig(
                        environments=["dev", "qa", "staging"],
                        resource_preset="small",
                    ),
                    "prod": ClusterConfig(
                        environments=["prod"],
                        resource_preset="large",
                    ),
                }
            ),
            enable_autoscaling=environment == "prod",
            enable_network_policies=environment in ("staging", "prod"),
            enable_pod_disruption_budget=environment == "prod",
        )

    def get_resource_preset(self) -> ResourcePreset:
        """Get the resource preset for the current environment.

        Returns:
            ResourcePreset for the environment, or small as default
        """
        cluster = self.cluster_mapping.get_cluster_for_environment(self.environment)
        if cluster is None:
            return self.resource_presets.get("small", ResourcePreset.small())

        preset_name = cluster.resource_preset
        return self.resource_presets.get(preset_name, ResourcePreset.small())

    def to_values_dict(self) -> dict[str, Any]:
        """Convert configuration to Helm values dictionary format.

        Returns:
            Dictionary suitable for YAML serialization as values.yaml
        """
        preset = self.get_resource_preset()
        cluster = self.cluster_mapping.get_cluster_for_environment(self.environment)
        namespace = (
            cluster.namespace_template.replace("{{ environment }}", self.environment)
            if cluster
            else f"floe-{self.environment}"
        )

        return {
            "global": {
                "environment": self.environment,
            },
            "namespace": {
                "name": namespace,
            },
            "autoscaling": {
                "enabled": self.enable_autoscaling,
            },
            "networkPolicy": {
                "enabled": self.enable_network_policies,
            },
            "podDisruptionBudget": {
                "enabled": self.enable_pod_disruption_budget,
            },
            "resourcePresets": {
                preset.name: {
                    "requests": {
                        "cpu": preset.resources.requests.cpu,
                        "memory": preset.resources.requests.memory,
                    },
                    "limits": {
                        "cpu": preset.resources.limits.cpu,
                        "memory": preset.resources.limits.memory,
                    },
                }
            },
        }


__all__: list[str] = [
    "ClusterConfig",
    "ClusterMapping",
    "HelmValuesConfig",
    "ResourcePreset",
    "ResourceRequirements",
    "ResourceSpec",
]
