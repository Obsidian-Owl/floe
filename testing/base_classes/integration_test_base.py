"""Integration test base class for K8s-native testing.

This module provides the IntegrationTestBase class that all integration tests
should inherit from. It provides common functionality for K8s-native tests:

- Service availability checking (polaris, postgres, minio, etc.)
- Unique namespace generation for test isolation
- Setup/teardown with resource cleanup
- Infrastructure verification with actionable error messages

Example:
    from testing.base_classes.integration_test_base import IntegrationTestBase

    class TestPolarisCatalog(IntegrationTestBase):
        required_services = [("polaris", 8181), ("minio", 9000)]

        @pytest.mark.requirement("9c-FR-001")
        def test_create_catalog(self) -> None:
            namespace = self.generate_unique_namespace("test_polaris")
            # Test implementation...
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from testing.fixtures.namespaces import generate_unique_namespace
from testing.fixtures.services import (
    ServiceUnavailableError,
    check_infrastructure,
    check_service_health,
    get_effective_host,
)


class IntegrationTestBase:
    """Base class for K8s-native integration tests.

    Provides common functionality for integration tests that require
    real K8s services (Polaris, PostgreSQL, MinIO, etc.). Tests inheriting
    from this class will fail fast if required infrastructure is unavailable.

    Class Attributes:
        required_services: List of (service_name, port) tuples that must be
            available for tests to run. Override in subclass.
        namespace: Default K8s namespace for test services.
        _created_namespaces: Track namespaces created during test for cleanup.

    Usage:
        class TestMyCatalog(IntegrationTestBase):
            required_services = [("polaris", 8181), ("minio", 9000)]

            @pytest.mark.requirement("9c-FR-001")
            def test_create_catalog(self) -> None:
                self.check_infrastructure("polaris", 8181)
                namespace = self.generate_unique_namespace("test")
                # Test implementation...

    Note:
        Tests MUST inherit from this class for integration tests.
        Unit tests should NOT inherit from this class.
    """

    # Class attributes - override in subclasses
    required_services: ClassVar[list[tuple[str, int]]] = []
    namespace: ClassVar[str] = "floe-test"

    # Instance attributes for tracking resources
    _created_namespaces: list[str]

    def setup_method(self) -> None:
        """Set up test fixtures before each test method.

        Called by pytest before each test method. Performs:
        1. Initialize tracking for created resources
        2. Verify required services are available
        3. Any subclass-specific setup

        Raises:
            ServiceUnavailableError: If any required service is not available.
                Error message includes instructions for starting infrastructure.

        Override:
            Call super().setup_method() first, then add custom setup:

            def setup_method(self) -> None:
                super().setup_method()
                self.client = create_test_client()
        """
        self._created_namespaces = []

        # Verify all required services are available
        if self.required_services:
            try:
                check_infrastructure(
                    self.required_services,
                    namespace=self.namespace,
                    raise_on_failure=True,
                )
            except ServiceUnavailableError as e:
                pytest.fail(
                    f"Required infrastructure not available: {e}\n"
                    f"Start infrastructure with: make kind-up"
                )

    def teardown_method(self) -> None:
        """Clean up test fixtures after each test method.

        Called by pytest after each test method. Performs:
        1. Clean up any created namespaces
        2. Release any acquired resources
        3. Any subclass-specific cleanup

        Override:
            Add custom cleanup, then call super().teardown_method():

            def teardown_method(self) -> None:
                self.client.close()
                super().teardown_method()
        """
        # Clean up created namespaces
        for ns in self._created_namespaces:
            self._cleanup_namespace(ns)
        self._created_namespaces.clear()

    def check_infrastructure(
        self,
        service_name: str,
        port: int,
        namespace: str | None = None,
    ) -> None:
        """Verify a specific service is available.

        Use this method at the start of tests that require specific services
        beyond those listed in required_services.

        Args:
            service_name: Name of the K8s service (e.g., "polaris").
            port: Port number to check.
            namespace: K8s namespace. Defaults to self.namespace.

        Raises:
            pytest.fail: If service is not available, with actionable message.

        Example:
            def test_with_dagster(self) -> None:
                self.check_infrastructure("dagster-webserver", 3000)
                # Test implementation...
        """
        effective_namespace = namespace or self.namespace

        if not check_service_health(service_name, port, effective_namespace):
            pytest.fail(
                f"Service {service_name}:{port} not available in {effective_namespace}\n"
                f"Start infrastructure with: make kind-up"
            )

    def generate_unique_namespace(self, prefix: str = "test") -> str:
        """Generate a unique K8s namespace name for test isolation.

        Creates a unique namespace name and tracks it for cleanup during
        teardown. Each test should use its own namespace to prevent
        interference between parallel test runs.

        Args:
            prefix: Prefix for the namespace name (e.g., "test_polaris").
                Underscores are converted to hyphens for K8s compatibility.

        Returns:
            Unique namespace string (e.g., "test-polaris-a1b2c3d4").

        Example:
            def test_catalog_creation(self) -> None:
                namespace = self.generate_unique_namespace("test_catalog")
                catalog = create_catalog(namespace=namespace)
                # Test with isolated namespace...
        """
        ns = generate_unique_namespace(prefix)
        self._created_namespaces.append(ns)
        return ns

    def get_service_host(
        self,
        service_name: str,
        namespace: str | None = None,
    ) -> str:
        """Get effective hostname for a service.

        Returns the effective hostname for connecting to a service. When running
        on the host (outside K8s), returns localhost. When running inside K8s,
        returns the K8s DNS name.

        Args:
            service_name: Name of the K8s service (e.g., "polaris", "postgres").
            namespace: K8s namespace. Defaults to self.namespace.

        Returns:
            Effective hostname (e.g., "localhost" or K8s DNS name).

        Example:
            def test_with_polaris(self) -> None:
                host = self.get_service_host("polaris")
                # Returns: "localhost" when running on host with Kind
                # Returns: "polaris.floe-test.svc.cluster.local" when in K8s
                catalog_uri = f"http://{host}:8181/api/catalog"
        """
        effective_namespace = namespace or self.namespace
        return get_effective_host(service_name, effective_namespace)

    def _cleanup_namespace(self, namespace: str) -> None:
        """Clean up a K8s namespace created during testing.

        Override this method in subclasses to implement actual K8s cleanup
        when running in a real cluster. Default implementation is a no-op
        for unit tests.

        Args:
            namespace: The namespace to clean up.
        """
        # Default implementation is a no-op
        # Subclasses can override for actual K8s cleanup
        _ = namespace  # Acknowledge parameter for type checker


# Module exports
__all__ = ["IntegrationTestBase"]
