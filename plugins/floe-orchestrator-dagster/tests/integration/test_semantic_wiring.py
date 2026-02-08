"""Integration tests for semantic layer Definitions wiring with real Dagster.

These tests verify semantic resources are wired into Dagster Definitions by
create_definitions when running with a real Dagster deployment.

The complete wiring chain tested:
- Definitions wiring (create_definitions with semantic resources)

Requirements Covered:
- FR-055: Semantic resources wiring into Dagster Definitions

Note:
- Tests require K8s with Dagster deployed. Run with: make test-integration
- For unit-level wiring tests (no services), see test_semantic_wiring_unit.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

import pytest
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION
from testing.base_classes.integration_test_base import IntegrationTestBase


class TestSemanticDefinitionsWiring(IntegrationTestBase):
    """Test semantic resources are wired into Definitions by create_definitions.

    Validates FR-055: create_definitions produces Definitions with semantic resources.
    """

    required_services: ClassVar[list[tuple[str, int]]] = [("dagster-webserver", 3000)]

    @pytest.fixture
    def compiled_artifacts_with_semantic(self) -> dict[str, Any]:
        """Create CompiledArtifacts with semantic plugin configured."""
        return {
            "version": COMPILED_ARTIFACTS_VERSION,
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": COMPILED_ARTIFACTS_VERSION,
                "source_hash": "sha256:semantic123",
                "product_name": "semantic-test-pipeline",
                "product_version": "1.0.0",
            },
            "transforms": {
                "models": [
                    {
                        "name": "test_model",
                        "compute": "duckdb",
                        "tags": ["test"],
                        "depends_on": [],
                    }
                ]
            },
            "plugins": {
                "semantic": {
                    "type": "cube",
                    "version": "0.1.0",
                    "config": {
                        "schema_output_dir": "cube/schema",
                    },
                }
            },
        }

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_create_definitions_includes_semantic_resources(
        self, compiled_artifacts_with_semantic: dict[str, Any]
    ) -> None:
        """Test create_definitions produces Definitions with semantic_layer resource."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()

        definitions = plugin.create_definitions(compiled_artifacts_with_semantic)

        assert definitions is not None, "create_definitions returned None"

        # Check that resources dict contains semantic_layer
        resources = definitions.resources
        assert resources is not None, "Definitions has no resources"
        assert "semantic_layer" in resources, "semantic_layer not found in Definitions resources"

    @pytest.mark.integration
    @pytest.mark.requirement("FR-055")
    def test_create_definitions_without_semantic_config_has_no_semantic_resources(
        self,
    ) -> None:
        """Test create_definitions produces Definitions without semantic_layer.

        Validates that when semantic plugin is not configured, the Definitions
        object does not include semantic_layer in its resources dict.
        """
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        # Minimal artifacts without semantic plugin
        artifacts = {
            "version": COMPILED_ARTIFACTS_VERSION,
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": COMPILED_ARTIFACTS_VERSION,
                "source_hash": "sha256:nosemantic",
                "product_name": "no-semantic-pipeline",
                "product_version": "1.0.0",
            },
            "transforms": {
                "models": [
                    {
                        "name": "test_model",
                        "compute": "duckdb",
                        "tags": ["test"],
                        "depends_on": [],
                    }
                ]
            },
        }

        plugin = DagsterOrchestratorPlugin()
        definitions = plugin.create_definitions(artifacts)

        assert definitions is not None, "create_definitions returned None"

        # Check that resources dict does NOT contain semantic_layer
        resources = definitions.resources
        assert "semantic_layer" not in resources, (
            "semantic_layer should not be present when not configured"
        )


__all__ = [
    "TestSemanticDefinitionsWiring",
]
