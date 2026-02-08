"""Tests for OrchestratorPlugin ABC upgrades."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from floe_core.lineage import LineageDataset, RunState
from floe_core.plugins.orchestrator import (
    OrchestratorPlugin,
    ResourceSpec,
    TransformConfig,
    ValidationResult,
)


class ConcreteOrchestratorPlugin(OrchestratorPlugin):
    """Minimal concrete implementation for testing the ABC."""

    @property
    def name(self) -> str:
        return "test-orchestrator"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def create_definitions(self, artifacts: dict[str, Any]) -> Any:
        return {}

    def create_assets_from_transforms(self, transforms: list[TransformConfig]) -> list[Any]:
        return []

    def get_helm_values(self) -> dict[str, Any]:
        return {}

    def validate_connection(self) -> ValidationResult:
        return ValidationResult(success=True)

    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        return ResourceSpec()

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
        return run_id or uuid4()

    def schedule_job(self, job_name: str, cron: str, timezone: str) -> None:
        pass

    def generate_entry_point_code(self, product_name: str, output_dir: str) -> str:
        _ = product_name, output_dir
        return "mock_definitions.py"


class TestEmitLineageEvent:
    """Tests for the upgraded emit_lineage_event signature."""

    @pytest.mark.requirement("REQ-516")
    def test_accepts_run_state_enum(self) -> None:
        """emit_lineage_event accepts RunState enum as event_type."""
        plugin = ConcreteOrchestratorPlugin()
        result = plugin.emit_lineage_event(
            event_type=RunState.START,
            job_name="test_job",
        )
        assert isinstance(result, UUID)

    @pytest.mark.requirement("REQ-516")
    def test_returns_uuid(self) -> None:
        """emit_lineage_event returns a UUID."""
        plugin = ConcreteOrchestratorPlugin()
        run_id = uuid4()
        result = plugin.emit_lineage_event(
            event_type=RunState.COMPLETE,
            job_name="test_job",
            run_id=run_id,
        )
        assert result == run_id

    @pytest.mark.requirement("REQ-516")
    def test_accepts_lineage_datasets(self) -> None:
        """emit_lineage_event accepts LineageDataset inputs/outputs."""
        plugin = ConcreteOrchestratorPlugin()
        inputs = [LineageDataset(namespace="ns", name="input_table")]
        outputs = [LineageDataset(namespace="ns", name="output_table")]
        result = plugin.emit_lineage_event(
            event_type=RunState.COMPLETE,
            job_name="test_job",
            inputs=inputs,
            outputs=outputs,
        )
        assert isinstance(result, UUID)

    @pytest.mark.requirement("REQ-516")
    def test_accepts_all_optional_params(self) -> None:
        """emit_lineage_event accepts all optional parameters."""
        plugin = ConcreteOrchestratorPlugin()
        result = plugin.emit_lineage_event(
            event_type=RunState.FAIL,
            job_name="test_job",
            job_namespace="my-ns",
            run_id=uuid4(),
            inputs=[],
            outputs=[],
            run_facets={"errorMessage": {"message": "boom"}},
            job_facets={"sql": {"query": "SELECT 1"}},
            producer="floe-test",
        )
        assert isinstance(result, UUID)


class TestGetLineageEmitter:
    """Tests for the get_lineage_emitter default implementation."""

    @pytest.mark.requirement("REQ-519")
    def test_returns_none_by_default(self) -> None:
        """get_lineage_emitter returns None when not overridden."""
        plugin = ConcreteOrchestratorPlugin()
        assert plugin.get_lineage_emitter() is None
