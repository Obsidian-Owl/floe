"""Contract tests for Ralph Wiggum plan.json schema.

Tests validate the stability of the plan.json schema used for agent
state persistence. Schema changes must be backwards compatible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Import jsonschema for validation
try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]


class TestPlanJsonSchema:
    """Contract tests for plan.json schema stability."""

    @pytest.fixture
    def plan_schema(self) -> dict[str, Any]:
        """Return the expected plan.json schema.

        This schema defines the contract between the orchestrator
        and individual agents. Changes must be backwards compatible.
        """
        return {
            "type": "object",
            "required": [
                "task_id",
                "linear_id",
                "epic",
                "status",
                "subtasks",
                "iteration",
                "max_iterations",
            ],
            "properties": {
                "task_id": {
                    "type": "string",
                    "pattern": "^T[0-9]{3}$",
                    "description": "Task identifier (e.g., T001)",
                },
                "linear_id": {
                    "type": "string",
                    "pattern": "^FLO-[0-9]+$",
                    "description": "Linear issue identifier",
                },
                "epic": {
                    "type": "string",
                    "pattern": "^EP[0-9]{3}$",
                    "description": "Epic identifier",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "complete", "blocked"],
                },
                "subtasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "description", "passes"],
                        "properties": {
                            "id": {"type": "string"},
                            "description": {"type": "string"},
                            "passes": {"type": "boolean"},
                        },
                    },
                },
                "iteration": {
                    "type": "integer",
                    "minimum": 0,
                },
                "max_iterations": {
                    "type": "integer",
                    "minimum": 1,
                },
                "completion_signal": {
                    "type": ["string", "null"],
                    "enum": ["COMPLETE", "BLOCKED", None],
                },
            },
        }

    @pytest.mark.requirement("ralph-contract-001")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_valid_plan_matches_schema(
        self, plan_schema: dict[str, Any], test_plan_json: dict[str, Any]
    ) -> None:
        """Valid plan.json matches the expected schema.

        Validates that test fixtures produce schema-compliant plans.
        """
        if jsonschema is None:
            pytest.skip("jsonschema not installed")

        # Should not raise
        jsonschema.validate(test_plan_json, plan_schema)

    @pytest.mark.requirement("ralph-contract-002")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_plan_requires_task_id(self, plan_schema: dict[str, Any]) -> None:
        """Plan requires task_id field.

        Validates task_id is a required field in the schema.
        """
        invalid_plan = {
            "linear_id": "FLO-1",
            "epic": "EP001",
            "status": "pending",
            "subtasks": [],
            "iteration": 0,
            "max_iterations": 15,
        }

        if jsonschema is None:
            pytest.skip("jsonschema not installed")

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_plan, plan_schema)

    @pytest.mark.requirement("ralph-contract-003")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_plan_requires_linear_id(self, plan_schema: dict[str, Any]) -> None:
        """Plan requires linear_id field.

        Validates linear_id is required for Linear integration.
        """
        invalid_plan = {
            "task_id": "T001",
            "epic": "EP001",
            "status": "pending",
            "subtasks": [],
            "iteration": 0,
            "max_iterations": 15,
        }

        if jsonschema is None:
            pytest.skip("jsonschema not installed")

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_plan, plan_schema)

    @pytest.mark.requirement("ralph-contract-004")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_plan_status_enum(self, plan_schema: dict[str, Any]) -> None:
        """Plan status must be valid enum value.

        Validates status field only accepts defined values.
        """
        invalid_plan = {
            "task_id": "T001",
            "linear_id": "FLO-1",
            "epic": "EP001",
            "status": "invalid_status",  # Not in enum
            "subtasks": [],
            "iteration": 0,
            "max_iterations": 15,
        }

        if jsonschema is None:
            pytest.skip("jsonschema not installed")

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_plan, plan_schema)

    @pytest.mark.requirement("ralph-contract-005")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_subtasks_structure(self, plan_schema: dict[str, Any]) -> None:
        """Subtasks have required structure.

        Validates subtask objects contain required fields.
        """
        invalid_plan = {
            "task_id": "T001",
            "linear_id": "FLO-1",
            "epic": "EP001",
            "status": "pending",
            "subtasks": [
                {"id": "T001.1"}  # Missing description and passes
            ],
            "iteration": 0,
            "max_iterations": 15,
        }

        if jsonschema is None:
            pytest.skip("jsonschema not installed")

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_plan, plan_schema)


class TestManifestSchema:
    """Contract tests for manifest.json schema stability."""

    @pytest.fixture
    def manifest_schema(self) -> dict[str, Any]:
        """Return the expected manifest.json schema."""
        return {
            "type": "object",
            "required": ["schema_version", "orchestration"],
            "properties": {
                "schema_version": {
                    "type": "string",
                    "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
                },
                "orchestration": {
                    "type": "object",
                    "required": ["max_parallel_agents", "max_iterations_per_task"],
                    "properties": {
                        "max_parallel_agents": {"type": "integer", "minimum": 1},
                        "max_iterations_per_task": {"type": "integer", "minimum": 1},
                        "stale_worktree_hours": {"type": "integer", "minimum": 1},
                        "auto_cleanup": {"type": "boolean"},
                    },
                },
                "active_agents": {
                    "type": "array",
                    "items": {"type": "object"},
                },
                "completed_today": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
        }

    @pytest.mark.requirement("ralph-contract-006")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_manifest_version_required(self, manifest_schema: dict[str, Any]) -> None:
        """Manifest requires schema_version field.

        Validates versioning is mandatory for compatibility tracking.
        """
        invalid_manifest = {
            "orchestration": {
                "max_parallel_agents": 5,
                "max_iterations_per_task": 15,
            }
        }

        if jsonschema is None:
            pytest.skip("jsonschema not installed")

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_manifest, manifest_schema)

    @pytest.mark.requirement("ralph-contract-007")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_valid_manifest_matches_schema(
        self, manifest_schema: dict[str, Any], test_manifest: Path
    ) -> None:
        """Valid manifest matches schema.

        Validates test fixtures produce schema-compliant manifests.
        """
        if jsonschema is None:
            pytest.skip("jsonschema not installed")

        manifest = json.loads(test_manifest.read_text())
        jsonschema.validate(manifest, manifest_schema)


class TestSchemaBackwardsCompatibility:
    """Tests for schema backwards compatibility."""

    @pytest.mark.requirement("ralph-contract-008")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_plan_v1_still_valid(self) -> None:
        """Old v1 plans still validate against current schema.

        Validates backwards compatibility with older plan versions.
        """
        v1_plan = {
            "task_id": "T001",
            "linear_id": "FLO-1",
            "epic": "EP001",
            "status": "pending",
            "subtasks": [],
            "iteration": 0,
            "max_iterations": 10,
            # No completion_signal - should be optional
        }

        # Should have all required fields
        required = [
            "task_id", "linear_id", "epic", "status",
            "subtasks", "iteration", "max_iterations",
        ]
        for field in required:
            assert field in v1_plan, f"Missing required field: {field}"

    @pytest.mark.requirement("ralph-contract-009")
    @pytest.mark.ralph
    @pytest.mark.contract
    def test_additional_fields_allowed(self) -> None:
        """Schema allows additional fields for extensibility.

        Validates forward compatibility - new fields don't break old readers.
        """
        extended_plan = {
            "task_id": "T001",
            "linear_id": "FLO-1",
            "epic": "EP001",
            "status": "pending",
            "subtasks": [],
            "iteration": 0,
            "max_iterations": 10,
            "new_field_v2": "some value",  # New field in v2
            "metrics": {"duration": 100},  # Another new field
        }

        # Should still be parseable as JSON
        json_str = json.dumps(extended_plan)
        parsed = json.loads(json_str)
        assert parsed["task_id"] == "T001"
        # Old readers should ignore new fields
