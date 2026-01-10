"""K8s-Native Testing Infrastructure for floe platform.

This module provides the foundational testing infrastructure for the floe platform,
enabling integration tests to run inside Kind clusters matching production deployment
patterns.

Components:
    base_classes: Test base classes (IntegrationTestBase, PluginTestBase, AdapterTestBase)
    fixtures: Pytest fixtures for test services (PostgreSQL, MinIO, Polaris, DuckDB, Dagster)
    traceability: Requirement traceability checker and reporting
    k8s: Kind cluster configuration and K8s manifests

Usage:
    from testing.base_classes import IntegrationTestBase
    from testing.fixtures import wait_for_condition, wait_for_service

    class TestMyCatalog(IntegrationTestBase):
        required_services = [("polaris", 8181), ("minio", 9000)]

        @pytest.mark.requirement("9c-FR-012")
        def test_create_catalog(self) -> None:
            namespace = self.generate_unique_namespace("test_catalog")
            # Test implementation...

See Also:
    - specs/9c-testing-infra/quickstart.md for usage examples
    - TESTING.md for complete testing guide
"""

from __future__ import annotations

__version__ = "0.1.0"
