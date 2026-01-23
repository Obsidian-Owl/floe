"""Integration tests for contract catalog registration.

Task: T069
Requirements: FR-026 (Catalog registration), FR-027 (Metadata storage),
              FR-028 (Soft failure handling)

These tests validate CatalogRegistrar integration with catalog plugins:
- Contract metadata stored as Iceberg namespace properties
- Schema hash, version, owner, timestamp all persisted
- Soft failure handling when catalog is unavailable
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase


class MockCatalogPlugin:
    """Mock catalog plugin for integration testing.

    Simulates a real catalog plugin (e.g., Polaris) for testing
    CatalogRegistrar without requiring K8s infrastructure.

    Attributes:
        namespaces: Dictionary of namespace -> properties.
        should_fail: If True, set_namespace_properties raises ConnectionError.
        failure_type: Type of failure to simulate (connection, timeout, permission).
    """

    def __init__(self) -> None:
        """Initialize mock catalog plugin."""
        self.namespaces: dict[str, dict[str, str]] = {}
        self.should_fail: bool = False
        self.failure_type: str = "connection"

    def set_namespace_properties(
        self,
        namespace: str,
        properties: dict[str, str],
    ) -> bool:
        """Set properties on a namespace.

        Args:
            namespace: Namespace identifier (e.g., "production.customers").
            properties: Key-value properties to set.

        Returns:
            True if successful.

        Raises:
            ConnectionError: If should_fail is True and failure_type is "connection".
            TimeoutError: If should_fail is True and failure_type is "timeout".
            PermissionError: If should_fail is True and failure_type is "permission".
        """
        if self.should_fail:
            if self.failure_type == "connection":
                raise ConnectionError("Catalog server unreachable")
            if self.failure_type == "timeout":
                raise TimeoutError("Connection timed out after 30s")
            if self.failure_type == "permission":
                raise PermissionError("Access denied for namespace")
            raise Exception(f"Unknown error: {self.failure_type}")

        if namespace not in self.namespaces:
            self.namespaces[namespace] = {}
        self.namespaces[namespace].update(properties)
        return True

    def get_namespace_properties(self, namespace: str) -> dict[str, str]:
        """Get properties from a namespace.

        Args:
            namespace: Namespace identifier.

        Returns:
            Dictionary of namespace properties.
        """
        return self.namespaces.get(namespace, {})


class TestCatalogRegistrarIntegration(IntegrationTestBase):
    """Integration tests for CatalogRegistrar with mock catalog.

    Task: T069
    Requirements: FR-026, FR-027

    These tests verify the full registration flow with a mock catalog
    that simulates real namespace property operations.
    """

    # No real K8s services required for mock-based integration tests
    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.fixture
    def mock_catalog(self) -> MockCatalogPlugin:
        """Create mock catalog plugin for testing."""
        return MockCatalogPlugin()

    @pytest.fixture
    def sample_contract_yaml(self, tmp_path: Path) -> Path:
        """Create a sample contract file for testing."""
        contract_content = """apiVersion: v3.1.0
kind: DataContract
id: urn:datacontract:integration-test
version: 1.0.0
name: integration-test-contract
status: active
schema:
  - name: customers
    physicalName: customers
    columns:
      - name: id
        logicalType: string
        required: true
      - name: email
        logicalType: string
        classification: pii
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_content)
        return contract_path

    @pytest.mark.requirement("3C-FR-026")
    def test_register_contract_stores_all_metadata(
        self,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test that CatalogRegistrar stores all required metadata.

        FR-026: System MUST register contract metadata in Iceberg catalog
        namespace properties.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        result = registrar.register_contract(
            contract_id="urn:datacontract:customers",
            contract_version="2.0.0",
            schema_hash="sha256:abc123def456",
            owner="analytics-team@acme.com",
            namespace="production.customers",
        )

        # Verify registration succeeded
        assert result.success is True
        assert result.contract_id == "urn:datacontract:customers"
        assert result.namespace == "production.customers"
        assert result.registered_at is not None

        # Verify all properties stored in catalog
        stored_props = mock_catalog.get_namespace_properties("production.customers")
        assert stored_props["floe.contract.id"] == "urn:datacontract:customers"
        assert stored_props["floe.contract.version"] == "2.0.0"
        assert stored_props["floe.contract.schema_hash"] == "sha256:abc123def456"
        assert stored_props["floe.contract.owner"] == "analytics-team@acme.com"
        assert "floe.contract.registered_at" in stored_props

    @pytest.mark.requirement("3C-FR-027")
    def test_registration_timestamp_is_valid_iso_format(
        self,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test that registration timestamp is in ISO 8601 format.

        FR-027: System MUST store registration timestamp in ISO format.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        before_registration = datetime.now(timezone.utc)

        registrar.register_contract(
            contract_id="test",
            contract_version="1.0.0",
            schema_hash="sha256:test",
            owner="test",
            namespace="test.namespace",
        )

        after_registration = datetime.now(timezone.utc)

        stored_props = mock_catalog.get_namespace_properties("test.namespace")
        timestamp_str = stored_props["floe.contract.registered_at"]

        # Parse the timestamp (ISO format with Z or +00:00)
        parsed = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Verify timestamp is within expected range
        assert parsed >= before_registration.replace(microsecond=0)
        assert parsed <= after_registration.replace(microsecond=0) or (
            parsed.replace(microsecond=0) <= after_registration.replace(microsecond=0)
        )

    @pytest.mark.requirement("3C-FR-026")
    def test_register_contract_overwrites_existing_properties(
        self,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test that re-registration overwrites existing contract properties.

        FR-026: Re-registering a contract should update existing properties.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        # First registration
        registrar.register_contract(
            contract_id="urn:datacontract:orders",
            contract_version="1.0.0",
            schema_hash="sha256:old_hash",
            owner="team-a",
            namespace="production.orders",
        )

        # Second registration (update)
        registrar.register_contract(
            contract_id="urn:datacontract:orders",
            contract_version="2.0.0",
            schema_hash="sha256:new_hash",
            owner="team-b",
            namespace="production.orders",
        )

        # Verify updated values
        stored_props = mock_catalog.get_namespace_properties("production.orders")
        assert stored_props["floe.contract.version"] == "2.0.0"
        assert stored_props["floe.contract.schema_hash"] == "sha256:new_hash"
        assert stored_props["floe.contract.owner"] == "team-b"

    @pytest.mark.requirement("3C-FR-028")
    def test_connection_error_returns_soft_failure(
        self,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test that connection errors result in soft failure.

        FR-028: System MUST handle catalog unreachability gracefully.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog.should_fail = True
        mock_catalog.failure_type = "connection"

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        result = registrar.register_contract(
            contract_id="test",
            contract_version="1.0.0",
            schema_hash="sha256:test",
            owner="test",
            namespace="test.namespace",
        )

        # Should return soft failure, not raise exception
        assert result.success is False
        assert result.warning is not None
        assert "unreachable" in result.warning.lower()

    @pytest.mark.requirement("3C-FR-028")
    def test_timeout_error_returns_soft_failure(
        self,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test that timeout errors result in soft failure.

        FR-028: System MUST handle catalog timeout gracefully.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog.should_fail = True
        mock_catalog.failure_type = "timeout"

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        result = registrar.register_contract(
            contract_id="test",
            contract_version="1.0.0",
            schema_hash="sha256:test",
            owner="test",
            namespace="test.namespace",
        )

        assert result.success is False
        assert result.warning is not None
        assert "timeout" in result.warning.lower()

    @pytest.mark.requirement("3C-FR-028")
    def test_permission_error_returns_soft_failure(
        self,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test that permission errors result in soft failure.

        FR-028: System MUST handle permission errors gracefully.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog.should_fail = True
        mock_catalog.failure_type = "permission"

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        result = registrar.register_contract(
            contract_id="test",
            contract_version="1.0.0",
            schema_hash="sha256:test",
            owner="test",
            namespace="test.namespace",
        )

        assert result.success is False
        assert result.warning is not None
        assert "denied" in result.warning.lower() or "permission" in result.warning.lower()


class TestContractValidatorRegistrationIntegration(IntegrationTestBase):
    """Integration tests for ContractValidator.validate_and_register().

    Task: T069
    Requirements: FR-026, FR-028

    Tests the full validation + registration workflow.
    """

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.fixture
    def mock_catalog(self) -> MockCatalogPlugin:
        """Create mock catalog plugin for testing."""
        return MockCatalogPlugin()

    @pytest.fixture
    def valid_contract_yaml(self, tmp_path: Path) -> Path:
        """Create a valid contract file for testing."""
        contract_content = """apiVersion: v3.1.0
kind: DataContract
id: urn:datacontract:valid-contract
version: 1.0.0
name: valid-contract
status: active
schema:
  - name: orders
    physicalName: orders
    columns:
      - name: order_id
        logicalType: string
        required: true
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_content)
        return contract_path

    @pytest.mark.requirement("3C-FR-026")
    def test_validate_and_register_success_flow(
        self,
        valid_contract_yaml: Path,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test successful validation followed by registration.

        FR-026: validate_and_register MUST register valid contracts.
        """
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        validator = ContractValidator()

        result = validator.validate_and_register(
            contract_path=valid_contract_yaml,
            namespace="production.orders",
            catalog_plugin=mock_catalog,
            enforcement_level="strict",
            owner="integration-test@example.com",
        )

        # Validation should succeed
        assert result.valid is True
        assert result.contract_name == "valid-contract"

        # Contract should be registered in catalog
        stored_props = mock_catalog.get_namespace_properties("production.orders")
        assert "floe.contract.id" in stored_props
        assert stored_props["floe.contract.version"] == "1.0.0"

    @pytest.mark.requirement("3C-FR-028")
    def test_validate_and_register_adds_warning_on_catalog_failure(
        self,
        valid_contract_yaml: Path,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test that catalog failure adds warning but validation still passes.

        FR-028: Registration failure MUST result in warning, not validation failure.
        """
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        mock_catalog.should_fail = True
        mock_catalog.failure_type = "connection"

        validator = ContractValidator()

        result = validator.validate_and_register(
            contract_path=valid_contract_yaml,
            namespace="production.orders",
            catalog_plugin=mock_catalog,
            enforcement_level="strict",
            owner="test",
        )

        # Validation should still pass (soft failure)
        assert result.valid is True

        # Should have warning about registration failure
        assert len(result.warnings) >= 1
        warning_messages = [w.message for w in result.warnings]
        assert any("registration" in msg.lower() for msg in warning_messages)

    @pytest.mark.requirement("3C-FR-026")
    def test_invalid_contract_is_not_registered(
        self,
        tmp_path: Path,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test that invalid contracts are not registered.

        FR-026: Only valid contracts should be registered.
        """
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Create invalid contract (missing required fields)
        invalid_content = """apiVersion: v3.1.0
kind: DataContract
# Missing id, version, name, etc.
"""
        contract_path = tmp_path / "invalid_datacontract.yaml"
        contract_path.write_text(invalid_content)

        validator = ContractValidator()

        result = validator.validate_and_register(
            contract_path=contract_path,
            namespace="production.invalid",
            catalog_plugin=mock_catalog,
            enforcement_level="strict",
            owner="test",
        )

        # Validation should fail
        assert result.valid is False

        # Contract should NOT be registered
        stored_props = mock_catalog.get_namespace_properties("production.invalid")
        assert "floe.contract.id" not in stored_props


class TestMultipleContractRegistration(IntegrationTestBase):
    """Integration tests for registering multiple contracts.

    Task: T069
    Requirements: FR-026
    """

    required_services: ClassVar[list[tuple[str, int]]] = []

    @pytest.fixture
    def mock_catalog(self) -> MockCatalogPlugin:
        """Create mock catalog plugin for testing."""
        return MockCatalogPlugin()

    @pytest.mark.requirement("3C-FR-026")
    def test_register_multiple_contracts_to_different_namespaces(
        self,
        mock_catalog: MockCatalogPlugin,
    ) -> None:
        """Test registering contracts to multiple namespaces.

        FR-026: Each namespace should have independent contract properties.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        # Register contracts to different namespaces
        registrar.register_contract(
            contract_id="urn:datacontract:customers",
            contract_version="1.0.0",
            schema_hash="sha256:customers_hash",
            owner="team-a",
            namespace="production.customers",
        )

        registrar.register_contract(
            contract_id="urn:datacontract:orders",
            contract_version="2.0.0",
            schema_hash="sha256:orders_hash",
            owner="team-b",
            namespace="production.orders",
        )

        # Verify each namespace has correct properties
        customers_props = mock_catalog.get_namespace_properties("production.customers")
        orders_props = mock_catalog.get_namespace_properties("production.orders")

        assert customers_props["floe.contract.id"] == "urn:datacontract:customers"
        assert customers_props["floe.contract.owner"] == "team-a"

        assert orders_props["floe.contract.id"] == "urn:datacontract:orders"
        assert orders_props["floe.contract.owner"] == "team-b"


__all__ = [
    "TestCatalogRegistrarIntegration",
    "TestContractValidatorRegistrationIntegration",
    "TestMultipleContractRegistration",
]
