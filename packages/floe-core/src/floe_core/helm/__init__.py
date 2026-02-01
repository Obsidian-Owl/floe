"""Helm utilities for floe platform deployment.

This module provides utilities for generating and managing Helm values
from CompiledArtifacts. It bridges the gap between floe configuration
(manifest.yaml, floe.yaml) and Kubernetes deployment (Helm charts).

Modules:
    schemas: Pydantic models for Helm configuration
    merger: Deep merge utilities for values files
    generator: HelmValuesGenerator class (future)

Example:
    >>> from floe_core.helm import ClusterMapping, deep_merge
    >>> from floe_core.helm.schemas import HelmValuesConfig
    >>>
    >>> # Create environment-specific configuration
    >>> config = HelmValuesConfig.with_defaults(environment="staging")
    >>> values = config.to_values_dict()
    >>>
    >>> # Merge with plugin values
    >>> plugin_values = {"dagster": {"enabled": True}}
    >>> final_values = deep_merge(values, plugin_values)
"""

from __future__ import annotations

from floe_core.helm.merger import (
    deep_merge,
    flatten_dict,
    merge_all,
    unflatten_dict,
)
from floe_core.helm.schemas import (
    ClusterConfig,
    ClusterMapping,
    HelmValuesConfig,
    ResourcePreset,
    ResourceRequirements,
    ResourceSpec,
)

__all__: list[str] = [
    # Schemas
    "ClusterConfig",
    "ClusterMapping",
    "HelmValuesConfig",
    "ResourcePreset",
    "ResourceRequirements",
    "ResourceSpec",
    # Merger utilities
    "deep_merge",
    "flatten_dict",
    "merge_all",
    "unflatten_dict",
]
