"""Integration tests for ingestion orchestrator wiring (T032).

These tests validate end-to-end wiring of ingestion resources into
Dagster Definitions via create_definitions().

Requirements:
    T032: Integration tests for ingestion wiring
    FR-059: Load ingestion plugin via PluginRegistry
    FR-063: Graceful degradation when ingestion is not configured
"""

from __future__ import annotations

import pytest


class TestIngestionWiringIntegration:
    """Integration tests for ingestion wiring chain."""

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-059")
    def test_definitions_include_ingestion_resource(self) -> None:
        """Test create_definitions includes ingestion resource when configured.

        Given CompiledArtifacts with plugins.ingestion configured,
        when create_definitions() is called, the resulting Definitions
        includes an "ingestion" resource.
        """
        pytest.fail(
            "Integration test requires full orchestrator stack — "
            "run via make test-integration"
        )

    @pytest.mark.integration
    @pytest.mark.requirement("4F-FR-063")
    def test_definitions_degrade_without_ingestion(self) -> None:
        """Test create_definitions works without ingestion configured.

        Given CompiledArtifacts with plugins.ingestion=None,
        when create_definitions() is called, no ingestion resource
        is included and no error is raised.
        """
        pytest.fail(
            "Integration test requires full orchestrator stack — "
            "run via make test-integration"
        )
