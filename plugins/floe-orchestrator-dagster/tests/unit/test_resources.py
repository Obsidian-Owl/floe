"""Unit tests for resource requirements in DagsterOrchestratorPlugin.

These tests verify the get_resource_requirements() method returns valid
K8s resource specifications for different workload sizes.

Note: @pytest.mark.requirement markers are used for traceability to spec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from floe_core.plugins.orchestrator import ResourceSpec

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestResourceRequirementsSmall:
    """Test small workload resource requirements."""

    def test_small_returns_resource_spec(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_resource_requirements('small') returns ResourceSpec."""
        result = dagster_plugin.get_resource_requirements("small")

        assert isinstance(result, ResourceSpec)

    def test_small_cpu_request(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test small workload has correct CPU request."""
        result = dagster_plugin.get_resource_requirements("small")

        assert result.cpu_request == "100m"

    def test_small_cpu_limit(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test small workload has correct CPU limit."""
        result = dagster_plugin.get_resource_requirements("small")

        assert result.cpu_limit == "500m"

    def test_small_memory_request(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test small workload has correct memory request."""
        result = dagster_plugin.get_resource_requirements("small")

        assert result.memory_request == "256Mi"

    def test_small_memory_limit(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test small workload has correct memory limit."""
        result = dagster_plugin.get_resource_requirements("small")

        assert result.memory_limit == "512Mi"


class TestResourceRequirementsMedium:
    """Test medium workload resource requirements."""

    def test_medium_returns_resource_spec(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_resource_requirements('medium') returns ResourceSpec."""
        result = dagster_plugin.get_resource_requirements("medium")

        assert isinstance(result, ResourceSpec)

    def test_medium_cpu_request(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test medium workload has correct CPU request."""
        result = dagster_plugin.get_resource_requirements("medium")

        assert result.cpu_request == "250m"

    def test_medium_cpu_limit(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test medium workload has correct CPU limit."""
        result = dagster_plugin.get_resource_requirements("medium")

        assert result.cpu_limit == "1000m"

    def test_medium_memory_request(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test medium workload has correct memory request."""
        result = dagster_plugin.get_resource_requirements("medium")

        assert result.memory_request == "512Mi"

    def test_medium_memory_limit(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test medium workload has correct memory limit."""
        result = dagster_plugin.get_resource_requirements("medium")

        assert result.memory_limit == "1Gi"


class TestResourceRequirementsLarge:
    """Test large workload resource requirements."""

    def test_large_returns_resource_spec(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_resource_requirements('large') returns ResourceSpec."""
        result = dagster_plugin.get_resource_requirements("large")

        assert isinstance(result, ResourceSpec)

    def test_large_cpu_request(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test large workload has correct CPU request."""
        result = dagster_plugin.get_resource_requirements("large")

        assert result.cpu_request == "500m"

    def test_large_cpu_limit(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test large workload has correct CPU limit."""
        result = dagster_plugin.get_resource_requirements("large")

        assert result.cpu_limit == "2000m"

    def test_large_memory_request(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test large workload has correct memory request."""
        result = dagster_plugin.get_resource_requirements("large")

        assert result.memory_request == "1Gi"

    def test_large_memory_limit(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test large workload has correct memory limit."""
        result = dagster_plugin.get_resource_requirements("large")

        assert result.memory_limit == "2Gi"


class TestResourceRequirementsInvalidSize:
    """Test get_resource_requirements with invalid workload_size."""

    def test_invalid_size_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test invalid workload_size raises ValueError."""
        with pytest.raises(ValueError):
            dagster_plugin.get_resource_requirements("invalid")

    def test_invalid_size_error_message_is_actionable(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test ValueError message includes valid options."""
        with pytest.raises(ValueError, match="Invalid workload_size"):
            dagster_plugin.get_resource_requirements("xlarge")

    def test_invalid_size_error_lists_valid_sizes(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test ValueError message lists all valid sizes."""
        with pytest.raises(ValueError, match="small") as exc_info:
            dagster_plugin.get_resource_requirements("tiny")

        error_message = str(exc_info.value)
        assert "small" in error_message
        assert "medium" in error_message
        assert "large" in error_message

    def test_empty_string_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test empty string workload_size raises ValueError."""
        with pytest.raises(ValueError, match="Invalid workload_size"):
            dagster_plugin.get_resource_requirements("")

    def test_none_raises_value_error(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test None workload_size raises ValueError."""
        with pytest.raises(ValueError, match="Invalid workload_size"):
            dagster_plugin.get_resource_requirements(None)  # type: ignore[arg-type]

    def test_case_sensitive(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test workload_size is case-sensitive."""
        with pytest.raises(ValueError):
            dagster_plugin.get_resource_requirements("Small")

        with pytest.raises(ValueError):
            dagster_plugin.get_resource_requirements("MEDIUM")


class TestResourceRequirementsConsistency:
    """Test consistency across resource requirement presets."""

    def test_small_has_smallest_limits(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test small preset has smallest resource limits."""
        small = dagster_plugin.get_resource_requirements("small")
        medium = dagster_plugin.get_resource_requirements("medium")

        # Compare CPU (convert to millicore integers)
        small_cpu = int(small.cpu_limit.replace("m", ""))
        medium_cpu = int(medium.cpu_limit.replace("m", ""))
        assert small_cpu < medium_cpu

    def test_medium_between_small_and_large(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test medium preset is between small and large."""
        small = dagster_plugin.get_resource_requirements("small")
        medium = dagster_plugin.get_resource_requirements("medium")
        large = dagster_plugin.get_resource_requirements("large")

        # Compare CPU (convert to millicore integers)
        small_cpu = int(small.cpu_limit.replace("m", ""))
        medium_cpu = int(medium.cpu_limit.replace("m", ""))
        large_cpu = int(large.cpu_limit.replace("m", ""))

        assert small_cpu < medium_cpu < large_cpu

    def test_large_has_largest_limits(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test large preset has largest resource limits."""
        medium = dagster_plugin.get_resource_requirements("medium")
        large = dagster_plugin.get_resource_requirements("large")

        # Compare CPU (convert to millicore integers)
        medium_cpu = int(medium.cpu_limit.replace("m", ""))
        large_cpu = int(large.cpu_limit.replace("m", ""))
        assert medium_cpu < large_cpu

    def test_requests_less_than_limits(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test resource requests are less than or equal to limits."""
        for size in ["small", "medium", "large"]:
            spec = dagster_plugin.get_resource_requirements(size)

            # CPU comparison (convert to millicore integers)
            cpu_request = int(spec.cpu_request.replace("m", ""))
            cpu_limit = int(spec.cpu_limit.replace("m", ""))
            assert cpu_request <= cpu_limit, f"{size}: CPU request > limit"

    def test_get_resource_requirements_is_idempotent(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_resource_requirements returns consistent results."""
        result1 = dagster_plugin.get_resource_requirements("medium")
        result2 = dagster_plugin.get_resource_requirements("medium")

        assert result1.cpu_request == result2.cpu_request
        assert result1.memory_limit == result2.memory_limit
