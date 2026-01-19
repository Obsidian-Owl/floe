"""Unit tests for Helm values generation in DagsterOrchestratorPlugin.

These tests verify the get_helm_values() method returns valid Helm chart
configuration for deploying Dagster services to Kubernetes.

Note: @pytest.mark.requirement markers are used for traceability to spec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestHelmValuesStructure:
    """Test Helm values return structure.

    Validates FR-010: System MUST provide Helm chart values for K8s deployment
    of Dagster services.
    """

    def test_get_helm_values_returns_dict(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_helm_values returns a dictionary."""
        result = dagster_plugin.get_helm_values()

        assert isinstance(result, dict)

    def test_get_helm_values_contains_webserver(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test Helm values include dagster-webserver configuration."""
        result = dagster_plugin.get_helm_values()

        assert "dagster-webserver" in result

    def test_get_helm_values_contains_daemon(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test Helm values include dagster-daemon configuration."""
        result = dagster_plugin.get_helm_values()

        assert "dagster-daemon" in result

    def test_get_helm_values_contains_user_code(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test Helm values include dagster-user-code configuration."""
        result = dagster_plugin.get_helm_values()

        assert "dagster-user-code" in result

    def test_get_helm_values_contains_postgresql(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test Helm values include postgresql configuration."""
        result = dagster_plugin.get_helm_values()

        assert "postgresql" in result


class TestWebserverConfiguration:
    """Test dagster-webserver Helm configuration."""

    def test_webserver_enabled(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test webserver is enabled by default."""
        result = dagster_plugin.get_helm_values()

        assert result["dagster-webserver"]["enabled"] is True

    def test_webserver_replica_count(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test webserver has correct replica count."""
        result = dagster_plugin.get_helm_values()

        assert result["dagster-webserver"]["replicaCount"] == 1

    def test_webserver_has_resources(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test webserver has resource configuration."""
        result = dagster_plugin.get_helm_values()

        assert "resources" in result["dagster-webserver"]

    def test_webserver_resource_requests(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test webserver has resource requests."""
        result = dagster_plugin.get_helm_values()
        resources = result["dagster-webserver"]["resources"]

        assert "requests" in resources
        assert resources["requests"]["cpu"] == "100m"
        assert resources["requests"]["memory"] == "256Mi"

    def test_webserver_resource_limits(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test webserver has resource limits."""
        result = dagster_plugin.get_helm_values()
        resources = result["dagster-webserver"]["resources"]

        assert "limits" in resources
        assert resources["limits"]["cpu"] == "500m"
        assert resources["limits"]["memory"] == "512Mi"


class TestDaemonConfiguration:
    """Test dagster-daemon Helm configuration."""

    def test_daemon_enabled(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test daemon is enabled by default."""
        result = dagster_plugin.get_helm_values()

        assert result["dagster-daemon"]["enabled"] is True

    def test_daemon_replica_count(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test daemon has correct replica count."""
        result = dagster_plugin.get_helm_values()

        assert result["dagster-daemon"]["replicaCount"] == 1

    def test_daemon_has_resources(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test daemon has resource configuration."""
        result = dagster_plugin.get_helm_values()

        assert "resources" in result["dagster-daemon"]

    def test_daemon_resource_requests(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test daemon has resource requests."""
        result = dagster_plugin.get_helm_values()
        resources = result["dagster-daemon"]["resources"]

        assert resources["requests"]["cpu"] == "100m"
        assert resources["requests"]["memory"] == "256Mi"

    def test_daemon_resource_limits(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test daemon has resource limits."""
        result = dagster_plugin.get_helm_values()
        resources = result["dagster-daemon"]["resources"]

        assert resources["limits"]["cpu"] == "500m"
        assert resources["limits"]["memory"] == "512Mi"


class TestUserCodeConfiguration:
    """Test dagster-user-code Helm configuration."""

    def test_user_code_enabled(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test user-code is enabled by default."""
        result = dagster_plugin.get_helm_values()

        assert result["dagster-user-code"]["enabled"] is True

    def test_user_code_replica_count(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test user-code has correct replica count."""
        result = dagster_plugin.get_helm_values()

        assert result["dagster-user-code"]["replicaCount"] == 1

    def test_user_code_has_resources(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test user-code has resource configuration."""
        result = dagster_plugin.get_helm_values()

        assert "resources" in result["dagster-user-code"]

    def test_user_code_resource_requests(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test user-code has larger resource requests than webserver/daemon."""
        result = dagster_plugin.get_helm_values()
        resources = result["dagster-user-code"]["resources"]

        # User code needs more resources for executing pipelines
        assert resources["requests"]["cpu"] == "250m"
        assert resources["requests"]["memory"] == "512Mi"

    def test_user_code_resource_limits(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test user-code has larger resource limits than webserver/daemon."""
        result = dagster_plugin.get_helm_values()
        resources = result["dagster-user-code"]["resources"]

        # User code needs more resources for executing pipelines
        assert resources["limits"]["cpu"] == "1000m"
        assert resources["limits"]["memory"] == "1Gi"


class TestPostgresqlConfiguration:
    """Test postgresql Helm configuration."""

    def test_postgresql_enabled(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test postgresql is enabled by default."""
        result = dagster_plugin.get_helm_values()

        assert result["postgresql"]["enabled"] is True


class TestHelmValuesConsistency:
    """Test Helm values consistency and structure."""

    def test_all_components_have_enabled_flag(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test all components have an enabled flag."""
        result = dagster_plugin.get_helm_values()

        for component in ["dagster-webserver", "dagster-daemon", "dagster-user-code", "postgresql"]:
            assert "enabled" in result[component], f"{component} missing enabled flag"

    def test_dagster_services_have_replica_count(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test Dagster services have replica count configuration."""
        result = dagster_plugin.get_helm_values()

        for service in ["dagster-webserver", "dagster-daemon", "dagster-user-code"]:
            assert "replicaCount" in result[service], f"{service} missing replicaCount"

    def test_dagster_services_have_resources(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test Dagster services have resource configuration."""
        result = dagster_plugin.get_helm_values()

        for service in ["dagster-webserver", "dagster-daemon", "dagster-user-code"]:
            assert "resources" in result[service], f"{service} missing resources"
            resources = result[service]["resources"]
            assert "requests" in resources, f"{service} missing resource requests"
            assert "limits" in resources, f"{service} missing resource limits"

    def test_get_helm_values_is_idempotent(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_helm_values returns consistent results on multiple calls."""
        result1 = dagster_plugin.get_helm_values()
        result2 = dagster_plugin.get_helm_values()

        assert result1 == result2

    def test_get_helm_values_returns_copy(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_helm_values returns a new dict each time (not mutable reference)."""
        result1 = dagster_plugin.get_helm_values()
        result2 = dagster_plugin.get_helm_values()

        # Modify result1
        result1["dagster-webserver"]["replicaCount"] = 99

        # result2 should be unaffected
        assert result2["dagster-webserver"]["replicaCount"] == 1
