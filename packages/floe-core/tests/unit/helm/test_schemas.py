"""Unit tests for Helm schemas.

Tests the Pydantic models for Helm values generation including
ClusterMapping, ResourcePreset, and HelmValuesConfig.

Requirements tested:
- 9b-FR-050: ClusterMapping configuration
- 9b-FR-051: Namespace template rendering
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.helm.schemas import (
    ClusterConfig,
    ClusterMapping,
    HelmValuesConfig,
    ResourcePreset,
    ResourceRequirements,
    ResourceSpec,
)


class TestResourceSpec:
    """Tests for ResourceSpec model."""

    @pytest.mark.requirement("9b-FR-050")
    def test_valid_cpu_formats(self) -> None:
        """Test valid CPU format specifications."""
        # Millicores
        spec = ResourceSpec(cpu="100m", memory="256Mi")
        assert spec.cpu == "100m"

        # Whole cores
        spec = ResourceSpec(cpu="1", memory="256Mi")
        assert spec.cpu == "1"

        # Large millicores
        spec = ResourceSpec(cpu="2000m", memory="256Mi")
        assert spec.cpu == "2000m"

    @pytest.mark.requirement("9b-FR-050")
    def test_valid_memory_formats(self) -> None:
        """Test valid memory format specifications."""
        # Mebibytes
        spec = ResourceSpec(cpu="100m", memory="256Mi")
        assert spec.memory == "256Mi"

        # Gibibytes
        spec = ResourceSpec(cpu="100m", memory="2Gi")
        assert spec.memory == "2Gi"

        # Kibibytes
        spec = ResourceSpec(cpu="100m", memory="1024Ki")
        assert spec.memory == "1024Ki"

    @pytest.mark.requirement("9b-FR-050")
    def test_invalid_cpu_format(self) -> None:
        """Test that invalid CPU format raises validation error."""
        with pytest.raises(ValidationError, match="cpu"):
            ResourceSpec(cpu="100x", memory="256Mi")

    @pytest.mark.requirement("9b-FR-050")
    def test_invalid_memory_format(self) -> None:
        """Test that invalid memory format raises validation error."""
        with pytest.raises(ValidationError, match="memory"):
            ResourceSpec(cpu="100m", memory="256MB")


class TestResourcePreset:
    """Tests for ResourcePreset model."""

    @pytest.mark.requirement("9b-FR-050")
    def test_small_preset(self) -> None:
        """Test small resource preset factory method."""
        preset = ResourcePreset.small()
        assert preset.name == "small"
        assert preset.resources.requests.cpu == "100m"
        assert preset.resources.requests.memory == "256Mi"

    @pytest.mark.requirement("9b-FR-050")
    def test_medium_preset(self) -> None:
        """Test medium resource preset factory method."""
        preset = ResourcePreset.medium()
        assert preset.name == "medium"
        assert preset.resources.requests.cpu == "250m"

    @pytest.mark.requirement("9b-FR-050")
    def test_large_preset(self) -> None:
        """Test large resource preset factory method."""
        preset = ResourcePreset.large()
        assert preset.name == "large"
        assert preset.resources.requests.cpu == "500m"
        assert preset.resources.requests.memory == "1Gi"

    @pytest.mark.requirement("9b-FR-050")
    def test_invalid_preset_name(self) -> None:
        """Test that invalid preset name raises validation error."""
        with pytest.raises(ValidationError, match="name"):
            ResourcePreset(
                name="Invalid Name",  # Spaces not allowed
                resources=ResourceRequirements(
                    requests=ResourceSpec(cpu="100m", memory="256Mi"),
                    limits=ResourceSpec(cpu="200m", memory="512Mi"),
                ),
            )


class TestClusterConfig:
    """Tests for ClusterConfig model."""

    @pytest.mark.requirement("9b-FR-050")
    def test_valid_cluster_config(self) -> None:
        """Test creating valid cluster configuration."""
        config = ClusterConfig(
            cluster="aks-nonprod",
            environments=["dev", "staging"],
            namespace_template="floe-{{ environment }}",
            resource_preset="small",
        )
        assert config.cluster == "aks-nonprod"
        assert config.environments == ["dev", "staging"]

    @pytest.mark.requirement("9b-FR-050")
    def test_default_values(self) -> None:
        """Test default values for cluster config."""
        config = ClusterConfig(environments=["dev"])
        assert config.cluster == ""
        assert config.namespace_template == "floe-{{ environment }}"
        assert config.resource_preset == "small"

    @pytest.mark.requirement("9b-FR-050")
    def test_empty_environments_fails(self) -> None:
        """Test that empty environments list raises validation error."""
        with pytest.raises(ValidationError, match="environments"):
            ClusterConfig(environments=[])

    @pytest.mark.requirement("9b-FR-050")
    def test_invalid_environment_name(self) -> None:
        """Test that invalid environment name raises validation error."""
        with pytest.raises(ValidationError, match="alphanumeric"):
            ClusterConfig(environments=["dev", "invalid@env"])


class TestClusterMapping:
    """Tests for ClusterMapping model."""

    @pytest.mark.requirement("9b-FR-050")
    def test_create_mapping(self) -> None:
        """Test creating cluster mapping with multiple clusters."""
        mapping = ClusterMapping(
            clusters={
                "non-prod": ClusterConfig(
                    cluster="aks-nonprod",
                    environments=["dev", "qa", "staging"],
                ),
                "prod": ClusterConfig(
                    cluster="aks-prod",
                    environments=["prod"],
                ),
            }
        )
        assert len(mapping.clusters) == 2
        assert "non-prod" in mapping.clusters
        assert "prod" in mapping.clusters

    @pytest.mark.requirement("9b-FR-050")
    def test_get_cluster_for_environment(self) -> None:
        """Test finding cluster by environment name."""
        mapping = ClusterMapping(
            clusters={
                "non-prod": ClusterConfig(
                    cluster="aks-nonprod",
                    environments=["dev", "staging"],
                ),
                "prod": ClusterConfig(
                    cluster="aks-prod",
                    environments=["prod"],
                ),
            }
        )

        dev_cluster = mapping.get_cluster_for_environment("dev")
        assert dev_cluster is not None
        assert dev_cluster.cluster == "aks-nonprod"

        prod_cluster = mapping.get_cluster_for_environment("prod")
        assert prod_cluster is not None
        assert prod_cluster.cluster == "aks-prod"

    @pytest.mark.requirement("9b-FR-050")
    def test_get_cluster_not_found(self) -> None:
        """Test that unknown environment returns None."""
        mapping = ClusterMapping(
            clusters={
                "prod": ClusterConfig(environments=["prod"]),
            }
        )
        result = mapping.get_cluster_for_environment("unknown")
        assert result is None

    @pytest.mark.requirement("9b-FR-051")
    def test_get_namespace(self) -> None:
        """Test namespace template rendering."""
        mapping = ClusterMapping(
            clusters={
                "non-prod": ClusterConfig(
                    environments=["dev", "staging"],
                    namespace_template="floe-{{ environment }}",
                ),
            }
        )

        assert mapping.get_namespace("dev") == "floe-dev"
        assert mapping.get_namespace("staging") == "floe-staging"

    @pytest.mark.requirement("9b-FR-051")
    def test_get_namespace_custom_template(self) -> None:
        """Test custom namespace template rendering."""
        mapping = ClusterMapping(
            clusters={
                "custom": ClusterConfig(
                    environments=["test"],
                    namespace_template="data-platform-{{ environment }}-v2",
                ),
            }
        )

        assert mapping.get_namespace("test") == "data-platform-test-v2"

    @pytest.mark.requirement("9b-FR-051")
    def test_get_namespace_not_found(self) -> None:
        """Test that unknown environment raises ValueError."""
        mapping = ClusterMapping(
            clusters={
                "prod": ClusterConfig(environments=["prod"]),
            }
        )

        with pytest.raises(ValueError, match="not found"):
            mapping.get_namespace("unknown")


class TestHelmValuesConfig:
    """Tests for HelmValuesConfig model."""

    @pytest.mark.requirement("9b-FR-050")
    def test_with_defaults_dev(self) -> None:
        """Test default configuration for dev environment."""
        config = HelmValuesConfig.with_defaults(environment="dev")

        assert config.environment == "dev"
        assert not config.enable_autoscaling
        assert not config.enable_network_policies
        assert not config.enable_pod_disruption_budget

    @pytest.mark.requirement("9b-FR-050")
    def test_with_defaults_staging(self) -> None:
        """Test default configuration for staging environment."""
        config = HelmValuesConfig.with_defaults(environment="staging")

        assert config.environment == "staging"
        assert not config.enable_autoscaling
        assert config.enable_network_policies  # Enabled for staging
        assert not config.enable_pod_disruption_budget

    @pytest.mark.requirement("9b-FR-050")
    def test_with_defaults_prod(self) -> None:
        """Test default configuration for prod environment."""
        config = HelmValuesConfig.with_defaults(environment="prod")

        assert config.environment == "prod"
        assert config.enable_autoscaling  # Enabled for prod
        assert config.enable_network_policies  # Enabled for prod
        assert config.enable_pod_disruption_budget  # Enabled for prod

    @pytest.mark.requirement("9b-FR-050")
    def test_get_resource_preset(self) -> None:
        """Test getting resource preset for environment."""
        config = HelmValuesConfig.with_defaults(environment="prod")
        preset = config.get_resource_preset()

        # Prod should use large preset
        assert preset.name == "large"

    @pytest.mark.requirement("9b-FR-050")
    def test_to_values_dict(self) -> None:
        """Test converting config to Helm values dictionary."""
        config = HelmValuesConfig.with_defaults(environment="staging")
        values = config.to_values_dict()

        assert values["global"]["environment"] == "staging"
        assert values["namespace"]["name"] == "floe-staging"
        assert values["autoscaling"]["enabled"] is False
        assert values["networkPolicy"]["enabled"] is True

    @pytest.mark.requirement("9b-FR-051")
    def test_to_values_dict_namespace_from_template(self) -> None:
        """Test that namespace is rendered from template."""
        config = HelmValuesConfig(
            environment="qa",
            cluster_mapping=ClusterMapping(
                clusters={
                    "test": ClusterConfig(
                        environments=["qa"],
                        namespace_template="data-{{ environment }}-ns",
                    ),
                }
            ),
        )
        values = config.to_values_dict()

        assert values["namespace"]["name"] == "data-qa-ns"

    @pytest.mark.requirement("9b-FR-050")
    def test_default_resource_presets(self) -> None:
        """Test that default presets are available."""
        config = HelmValuesConfig.with_defaults()

        assert "small" in config.resource_presets
        assert "medium" in config.resource_presets
        assert "large" in config.resource_presets

    @pytest.mark.requirement("9b-FR-050")
    def test_frozen_model(self) -> None:
        """Test that config is immutable (frozen)."""
        config = HelmValuesConfig.with_defaults()

        # Frozen Pydantic models have model_config["frozen"] = True
        assert config.model_config.get("frozen") is True
