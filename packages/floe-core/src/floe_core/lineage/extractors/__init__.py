"""Lineage extractors for various data processing frameworks.

This module provides extractors that convert framework-specific metadata
(dbt manifests, Dagster contexts, etc.) into floe's portable LineageDataset
format for OpenLineage integration.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
"""

from __future__ import annotations

from floe_core.lineage.extractors.dbt import DbtLineageExtractor

__all__ = [
    "DbtLineageExtractor",
]
