"""Pytest fixtures for Helm unit tests."""

from __future__ import annotations

import pytest
from floe_core.helm.schemas import (
    ClusterConfig,
    ClusterMapping,
    HelmValuesConfig,
    ResourcePreset,
)


@pytest.fixture
def sample_cluster_mapping() -> ClusterMapping:
    """Create a sample cluster mapping for tests."""
    return ClusterMapping(
        clusters={
            "non-prod": ClusterConfig(
                cluster="aks-nonprod",
                environments=["dev", "qa", "staging"],
                namespace_template="floe-{{ environment }}",
                resource_preset="small",
            ),
            "prod": ClusterConfig(
                cluster="aks-prod",
                environments=["prod"],
                namespace_template="floe-prod",
                resource_preset="large",
            ),
        }
    )


@pytest.fixture
def sample_resource_presets() -> dict[str, ResourcePreset]:
    """Create sample resource presets for tests."""
    return {
        "small": ResourcePreset.small(),
        "medium": ResourcePreset.medium(),
        "large": ResourcePreset.large(),
    }


@pytest.fixture
def sample_helm_config(
    sample_cluster_mapping: ClusterMapping,
    sample_resource_presets: dict[str, ResourcePreset],
) -> HelmValuesConfig:
    """Create a sample Helm values config for tests."""
    return HelmValuesConfig(
        environment="staging",
        cluster_mapping=sample_cluster_mapping,
        resource_presets=sample_resource_presets,
        enable_autoscaling=False,
        enable_network_policies=True,
        enable_pod_disruption_budget=False,
    )
