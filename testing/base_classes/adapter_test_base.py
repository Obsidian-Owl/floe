"""Adapter test base class for floe adapter testing.

This module provides the AdapterTestBase class for testing adapters that
connect floe components to external services (catalogs, compute engines, etc.).

Example:
    from testing.base_classes.adapter_test_base import AdapterTestBase

    class TestPolarisCatalogAdapter(AdapterTestBase):
        adapter_type = "catalog"
        required_services = [("polaris", 8181)]

        def test_catalog_connection(self) -> None:
            adapter = self.create_adapter()
            assert adapter.is_connected()
"""

from __future__ import annotations

from typing import Any, ClassVar

from testing.base_classes.integration_test_base import IntegrationTestBase


class AdapterTestBase(IntegrationTestBase):
    """Base class for adapter integration tests.

    Extends IntegrationTestBase with adapter-specific functionality:
    - Adapter factory methods
    - Connection lifecycle testing
    - Configuration validation

    Class Attributes:
        adapter_type: The type of adapter being tested (e.g., "catalog", "compute").
        adapter_config: Default configuration for the adapter.

    Usage:
        class TestPolarisCatalogAdapter(AdapterTestBase):
            adapter_type = "catalog"
            required_services = [("polaris", 8181)]
            adapter_config = {"uri": "http://polaris:8181/api/catalog"}

            @pytest.mark.requirement("adapter-FR-001")
            def test_adapter_connection(self) -> None:
                adapter = self.create_adapter()
                assert adapter.is_connected()
    """

    adapter_type: ClassVar[str] = ""
    adapter_config: ClassVar[dict[str, Any]] = {}

    def setup_method(self) -> None:
        """Set up adapter test fixtures.

        Extends parent setup to verify adapter configuration is valid.
        """
        super().setup_method()
        # Validate adapter configuration
        if not self.adapter_type:
            raise ValueError(
                f"{self.__class__.__name__} must define adapter_type class attribute"
            )

    def create_adapter(self, **config_overrides: Any) -> Any:
        """Create an adapter instance for testing.

        Creates an adapter with the default configuration, allowing
        specific values to be overridden for individual tests.

        Args:
            **config_overrides: Configuration values to override.

        Returns:
            Configured adapter instance.

        Note:
            This is a placeholder implementation. Override in subclasses
            to create actual adapter instances.

        Example:
            def test_custom_config(self) -> None:
                adapter = self.create_adapter(timeout=60)
                # Test with custom timeout...
        """
        # Placeholder - subclasses should override
        config = {**self.adapter_config, **config_overrides}
        return {"type": self.adapter_type, "config": config}

    def get_test_config(self) -> dict[str, Any]:
        """Get the test configuration for the adapter.

        Returns a copy of the adapter configuration that can be modified
        without affecting the class attribute.

        Returns:
            Dictionary with adapter configuration.
        """
        return dict(self.adapter_config)


# Module exports
__all__ = ["AdapterTestBase"]
