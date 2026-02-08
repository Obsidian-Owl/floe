"""Unit tests for base test classes.

Tests for IntegrationTestBase, PluginTestBase, and AdapterTestBase.
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import patch

import pytest

from testing.base_classes.adapter_test_base import AdapterTestBase
from testing.base_classes.integration_test_base import IntegrationTestBase
from testing.base_classes.plugin_test_base import PluginTestBase


class TestIntegrationTestBase:
    """Tests for IntegrationTestBase class."""

    @pytest.mark.requirement("9c-FR-005")
    def test_setup_method_initializes_namespaces_list(self) -> None:
        """Test setup_method initializes _created_namespaces."""

        class TestClass(IntegrationTestBase):
            required_services: ClassVar[list[tuple[str, int]]] = []

        instance = TestClass()
        instance.setup_method()

        assert hasattr(instance, "_created_namespaces")
        assert instance._created_namespaces == []

    @pytest.mark.requirement("9c-FR-005")
    def test_setup_method_checks_required_services(self) -> None:
        """Test setup_method verifies required services."""

        class TestClass(IntegrationTestBase):
            required_services = [("polaris", 8181)]

        instance = TestClass()

        # Mock service check to fail
        with patch("testing.base_classes.integration_test_base.check_infrastructure") as mock_check:
            from testing.fixtures.services import (
                ServiceEndpoint,
                ServiceUnavailableError,
            )

            mock_check.side_effect = ServiceUnavailableError(
                ServiceEndpoint("polaris", 8181), "connection failed"
            )

            with pytest.raises(pytest.fail.Exception) as exc_info:
                instance.setup_method()

            assert "infrastructure not available" in str(exc_info.value)
            assert "make kind-up" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-008")
    def test_generate_unique_namespace_returns_unique(self) -> None:
        """Test generate_unique_namespace returns unique values."""

        class TestClass(IntegrationTestBase):
            required_services: ClassVar[list[tuple[str, int]]] = []

        instance = TestClass()
        instance.setup_method()

        ns1 = instance.generate_unique_namespace("test")
        ns2 = instance.generate_unique_namespace("test")

        assert ns1 != ns2

    @pytest.mark.requirement("9c-FR-008")
    def test_generate_unique_namespace_tracks_for_cleanup(self) -> None:
        """Test generate_unique_namespace adds to cleanup list."""

        class TestClass(IntegrationTestBase):
            required_services: ClassVar[list[tuple[str, int]]] = []

        instance = TestClass()
        instance.setup_method()

        ns = instance.generate_unique_namespace("test")

        assert ns in instance._created_namespaces

    @pytest.mark.requirement("9c-FR-005")
    def test_check_infrastructure_fails_on_unavailable(self) -> None:
        """Test check_infrastructure fails when service unavailable."""

        class TestClass(IntegrationTestBase):
            required_services: ClassVar[list[tuple[str, int]]] = []

        instance = TestClass()
        instance.setup_method()

        with patch(
            "testing.base_classes.integration_test_base.check_service_health",
            return_value=False,
        ):
            with pytest.raises(pytest.fail.Exception) as exc_info:
                instance.check_infrastructure("polaris", 8181)

            assert "polaris:8181 not available" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-005")
    def test_check_infrastructure_passes_on_available(self) -> None:
        """Test check_infrastructure passes when service available."""

        class TestClass(IntegrationTestBase):
            required_services: ClassVar[list[tuple[str, int]]] = []

        instance = TestClass()
        instance.setup_method()

        with patch(
            "testing.base_classes.integration_test_base.check_service_health",
            return_value=True,
        ):
            # Should not raise
            instance.check_infrastructure("polaris", 8181)

    @pytest.mark.requirement("9c-FR-005")
    def test_teardown_method_clears_namespaces(self) -> None:
        """Test teardown_method clears created namespaces."""

        class TestClass(IntegrationTestBase):
            required_services: ClassVar[list[tuple[str, int]]] = []

        instance = TestClass()
        instance.setup_method()

        instance.generate_unique_namespace("test1")
        instance.generate_unique_namespace("test2")

        assert len(instance._created_namespaces) == 2

        instance.teardown_method()

        assert instance._created_namespaces == []

    @pytest.mark.requirement("9c-FR-005")
    def test_default_namespace_is_floe_test(self) -> None:
        """Test default namespace is 'floe-test'."""
        assert IntegrationTestBase.namespace == "floe-test"


class TestPluginTestBase:
    """Tests for PluginTestBase class."""

    @pytest.mark.requirement("9c-FR-005")
    def test_requires_plugin_type(self) -> None:
        """Test PluginTestBase requires plugin_type."""

        class TestClass(PluginTestBase):
            plugin_type = ""
            plugin_name = "test"

        instance = TestClass()

        with pytest.raises(ValueError, match="must define plugin_type"):
            instance.setup_method()

    @pytest.mark.requirement("9c-FR-005")
    def test_requires_plugin_name(self) -> None:
        """Test PluginTestBase requires plugin_name."""

        class TestClass(PluginTestBase):
            plugin_type = "compute"
            plugin_name = ""

        instance = TestClass()

        with pytest.raises(ValueError, match="must define plugin_name"):
            instance.setup_method()

    @pytest.mark.requirement("9c-FR-005")
    def test_valid_plugin_config_passes_setup(self) -> None:
        """Test valid plugin configuration passes setup."""

        class TestClass(PluginTestBase):
            plugin_type = "compute"
            plugin_name = "duckdb"

        instance = TestClass()
        instance.setup_method()  # Should not raise

    @pytest.mark.requirement("9c-FR-005")
    def test_get_entry_point_group(self) -> None:
        """Test get_entry_point_group returns correct group."""

        class TestClass(PluginTestBase):
            plugin_type = "compute"
            plugin_name = "duckdb"

        instance = TestClass()
        instance.setup_method()

        assert instance.get_entry_point_group() == "floe.computes"

    @pytest.mark.requirement("9c-FR-005")
    def test_plugin_is_registered_returns_bool(self) -> None:
        """Test plugin_is_registered returns boolean."""

        class TestClass(PluginTestBase):
            plugin_type = "compute"
            plugin_name = "duckdb"

        instance = TestClass()
        instance.setup_method()

        result = instance.plugin_is_registered()
        assert isinstance(result, bool)

    @pytest.mark.requirement("9c-FR-005")
    def test_get_plugin_metadata_returns_dict(self) -> None:
        """Test get_plugin_metadata returns metadata dict."""

        class TestClass(PluginTestBase):
            plugin_type = "compute"
            plugin_name = "duckdb"

        instance = TestClass()
        instance.setup_method()

        metadata = instance.get_plugin_metadata()

        assert isinstance(metadata, dict)
        assert metadata["name"] == "duckdb"
        assert metadata["type"] == "compute"


class TestAdapterTestBase:
    """Tests for AdapterTestBase class."""

    @pytest.mark.requirement("9c-FR-005")
    def test_requires_adapter_type(self) -> None:
        """Test AdapterTestBase requires adapter_type."""

        class TestClass(AdapterTestBase):
            adapter_type = ""

        instance = TestClass()

        with pytest.raises(ValueError, match="must define adapter_type"):
            instance.setup_method()

    @pytest.mark.requirement("9c-FR-005")
    def test_valid_adapter_config_passes_setup(self) -> None:
        """Test valid adapter configuration passes setup."""

        class TestClass(AdapterTestBase):
            adapter_type = "catalog"

        instance = TestClass()
        instance.setup_method()  # Should not raise

    @pytest.mark.requirement("9c-FR-005")
    def test_create_adapter_returns_config(self) -> None:
        """Test create_adapter returns adapter with config."""

        class TestClass(AdapterTestBase):
            adapter_type = "catalog"
            adapter_config = {"uri": "http://localhost:8181"}

        instance = TestClass()
        instance.setup_method()

        adapter = instance.create_adapter()

        assert adapter["type"] == "catalog"
        assert adapter["config"]["uri"] == "http://localhost:8181"

    @pytest.mark.requirement("9c-FR-005")
    def test_create_adapter_with_overrides(self) -> None:
        """Test create_adapter allows config overrides."""

        class TestClass(AdapterTestBase):
            adapter_type = "catalog"
            adapter_config = {"uri": "http://localhost:8181", "timeout": 30}

        instance = TestClass()
        instance.setup_method()

        adapter = instance.create_adapter(timeout=60)

        assert adapter["config"]["timeout"] == 60
        assert adapter["config"]["uri"] == "http://localhost:8181"

    @pytest.mark.requirement("9c-FR-005")
    def test_get_test_config_returns_copy(self) -> None:
        """Test get_test_config returns a copy of config."""

        class TestClass(AdapterTestBase):
            adapter_type = "catalog"
            adapter_config = {"uri": "http://localhost:8181"}

        instance = TestClass()
        instance.setup_method()

        config = instance.get_test_config()
        config["modified"] = True

        # Original should not be modified
        assert "modified" not in instance.adapter_config
