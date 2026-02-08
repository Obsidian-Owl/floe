"""Unit tests for contract catalog registration.

Task: T067, T068
Requirements: FR-026 (Catalog registration), FR-027 (Metadata storage),
              FR-028 (Soft failure handling)

Tests for CatalogRegistrar:
- Contract registration stores metadata in catalog
- Schema hash computed for fingerprinting
- Soft failure when catalog unreachable
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCatalogRegistrar:
    """Tests for CatalogRegistrar class.

    Task: T067
    Requirements: FR-026, FR-027
    """

    @pytest.mark.requirement("3C-FR-026")
    def test_register_contract_stores_metadata(self) -> None:
        """Test that register_contract stores metadata in catalog.

        FR-026: System MUST register contract metadata in Iceberg catalog
        namespace properties.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        # Create a mock catalog plugin
        mock_catalog = MagicMock()
        mock_catalog.set_namespace_properties = MagicMock(return_value=True)

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        # Register a contract
        result = registrar.register_contract(
            contract_id="urn:datacontract:customers",
            contract_version="1.0.0",
            schema_hash="sha256:abc123",
            owner="data-team",
            namespace="production.customers",
        )

        assert result.success is True
        mock_catalog.set_namespace_properties.assert_called_once()

        # Verify the properties passed include required metadata
        call_args = mock_catalog.set_namespace_properties.call_args
        properties = call_args[1].get(
            "properties", call_args[0][1] if len(call_args[0]) > 1 else {}
        )

        assert "floe.contract.id" in properties or any(
            "contract" in str(k).lower() for k in properties.keys()
        )

    @pytest.mark.requirement("3C-FR-027")
    def test_register_contract_includes_all_required_fields(self) -> None:
        """Test that registration includes version, hash, owner, timestamp.

        FR-027: System MUST store contract version, schema hash, owner,
        and registration timestamp.
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog = MagicMock()
        captured_properties: dict[str, str] = {}

        def capture_properties(namespace: str, properties: dict[str, str]) -> bool:
            captured_properties.update(properties)
            return True

        mock_catalog.set_namespace_properties = capture_properties

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)
        registrar.register_contract(
            contract_id="urn:datacontract:orders",
            contract_version="2.1.0",
            schema_hash="sha256:def456",
            owner="analytics-team",
            namespace="production.orders",
        )

        # Verify all required fields are present
        assert "floe.contract.id" in captured_properties
        assert "floe.contract.version" in captured_properties
        assert "floe.contract.schema_hash" in captured_properties
        assert "floe.contract.owner" in captured_properties
        assert "floe.contract.registered_at" in captured_properties

        # Verify values
        assert captured_properties["floe.contract.id"] == "urn:datacontract:orders"
        assert captured_properties["floe.contract.version"] == "2.1.0"
        assert captured_properties["floe.contract.schema_hash"] == "sha256:def456"
        assert captured_properties["floe.contract.owner"] == "analytics-team"

    @pytest.mark.requirement("3C-FR-027")
    def test_registration_timestamp_is_iso_format(self) -> None:
        """Test that registration timestamp is in ISO format."""
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog = MagicMock()
        captured_properties: dict[str, str] = {}

        def capture_properties(namespace: str, properties: dict[str, str]) -> bool:
            captured_properties.update(properties)
            return True

        mock_catalog.set_namespace_properties = capture_properties

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)
        registrar.register_contract(
            contract_id="test",
            contract_version="1.0.0",
            schema_hash="sha256:test",
            owner="test",
            namespace="test.namespace",
        )

        # Verify timestamp is ISO format
        timestamp = captured_properties.get("floe.contract.registered_at", "")
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed is not None

    @pytest.mark.requirement("3C-FR-026")
    def test_register_contract_returns_registration_result(self) -> None:
        """Test that register_contract returns a RegistrationResult."""
        from floe_core.enforcement.validators.data_contracts import (
            CatalogRegistrar,
            RegistrationResult,
        )

        mock_catalog = MagicMock()
        mock_catalog.set_namespace_properties = MagicMock(return_value=True)

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)
        result = registrar.register_contract(
            contract_id="test",
            contract_version="1.0.0",
            schema_hash="sha256:test",
            owner="test",
            namespace="test.namespace",
        )

        assert isinstance(result, RegistrationResult)
        assert result.success is True
        assert result.contract_id == "test"
        assert result.namespace == "test.namespace"


class TestCatalogRegistrarSoftFailure:
    """Tests for soft failure handling (FR-028).

    Task: T068
    Requirements: FR-028
    """

    @pytest.mark.requirement("3C-FR-028")
    def test_catalog_unreachable_returns_soft_failure(self) -> None:
        """Test that catalog unreachability results in soft failure.

        FR-028: System MUST handle catalog unreachability gracefully
        (soft failure with warning).
        """
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog = MagicMock()
        # Simulate catalog being unreachable
        mock_catalog.set_namespace_properties = MagicMock(
            side_effect=ConnectionError("Catalog unreachable")
        )

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)
        result = registrar.register_contract(
            contract_id="test",
            contract_version="1.0.0",
            schema_hash="sha256:test",
            owner="test",
            namespace="test.namespace",
        )

        # Should return failure but not raise exception
        assert result.success is False
        assert result.warning is not None
        assert (
            "unreachable" in result.warning.lower()
            or "failed" in result.warning.lower()
        )

    @pytest.mark.requirement("3C-FR-028")
    def test_catalog_timeout_returns_soft_failure(self) -> None:
        """Test that catalog timeout results in soft failure."""
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog = MagicMock()
        # Simulate timeout
        mock_catalog.set_namespace_properties = MagicMock(
            side_effect=TimeoutError("Connection timed out")
        )

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

    @pytest.mark.requirement("3C-FR-028")
    def test_catalog_permission_error_returns_soft_failure(self) -> None:
        """Test that permission errors result in soft failure."""
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog = MagicMock()
        mock_catalog.set_namespace_properties = MagicMock(
            side_effect=PermissionError("Access denied")
        )

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
        assert (
            "permission" in result.warning.lower() or "denied" in result.warning.lower()
        )

    @pytest.mark.requirement("3C-FR-028")
    def test_soft_failure_does_not_block_validation(self) -> None:
        """Test that soft failure doesn't block overall validation."""
        from floe_core.enforcement.validators.data_contracts import CatalogRegistrar

        mock_catalog = MagicMock()
        mock_catalog.set_namespace_properties = MagicMock(
            side_effect=Exception("Unexpected error")
        )

        registrar = CatalogRegistrar(catalog_plugin=mock_catalog)

        # Should not raise - returns soft failure
        result = registrar.register_contract(
            contract_id="test",
            contract_version="1.0.0",
            schema_hash="sha256:test",
            owner="test",
            namespace="test.namespace",
        )

        # Registration failed but gracefully
        assert result.success is False
        assert result.warning is not None


class TestRegistrationResult:
    """Tests for RegistrationResult model."""

    @pytest.mark.requirement("3C-FR-026")
    def test_registration_result_success(self) -> None:
        """Test RegistrationResult for successful registration."""
        from floe_core.enforcement.validators.data_contracts import RegistrationResult

        result = RegistrationResult(
            success=True,
            contract_id="urn:datacontract:test",
            namespace="production.test",
            registered_at=datetime.now(timezone.utc),
        )

        assert result.success is True
        assert result.warning is None

    @pytest.mark.requirement("3C-FR-028")
    def test_registration_result_failure_with_warning(self) -> None:
        """Test RegistrationResult for failed registration with warning."""
        from floe_core.enforcement.validators.data_contracts import RegistrationResult

        result = RegistrationResult(
            success=False,
            contract_id="urn:datacontract:test",
            namespace="production.test",
            warning="Catalog unreachable: connection timeout",
        )

        assert result.success is False
        assert result.warning is not None
        assert "unreachable" in result.warning.lower()


class TestContractValidatorRegistrationIntegration:
    """Tests for ContractValidator integration with CatalogRegistrar.

    Task: T074 (integration)
    Requirements: FR-026
    """

    @pytest.mark.requirement("3C-FR-026")
    def test_validator_registers_on_successful_validation(self, tmp_path: Path) -> None:
        """Test that ContractValidator registers contract after validation."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        # Create a valid contract
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: urn:datacontract:customers
version: 1.0.0
name: customers-contract
status: active
schema:
  - name: customers
    physicalName: customers
    columns:
      - name: id
        logicalType: string
        required: true
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_yaml)

        # Mock the CatalogRegistrar
        with patch(
            "floe_core.enforcement.validators.data_contracts.CatalogRegistrar"
        ) as MockRegistrar:
            mock_registrar = MagicMock()
            mock_registrar.register_contract = MagicMock(
                return_value=MagicMock(success=True, warning=None)
            )
            MockRegistrar.return_value = mock_registrar

            validator = ContractValidator()

            # Validate with registration
            result = validator.validate_and_register(
                contract_path=contract_path,
                namespace="production.customers",
                catalog_plugin=MagicMock(),
            )

            # Validation should succeed
            assert result.valid is True

            # Registration should have been called
            mock_registrar.register_contract.assert_called_once()

    @pytest.mark.requirement("3C-FR-028")
    def test_validator_returns_warning_on_registration_failure(
        self, tmp_path: Path
    ) -> None:
        """Test that validation succeeds with warning if registration fails."""
        from floe_core.enforcement.validators.data_contracts import ContractValidator

        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: urn:datacontract:orders
version: 1.0.0
name: orders-contract
status: active
schema:
  - name: orders
    physicalName: orders
    columns:
      - name: id
        logicalType: string
        required: true
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_yaml)

        with patch(
            "floe_core.enforcement.validators.data_contracts.CatalogRegistrar"
        ) as MockRegistrar:
            mock_registrar = MagicMock()
            mock_registrar.register_contract = MagicMock(
                return_value=MagicMock(
                    success=False,
                    warning="Catalog unreachable",
                )
            )
            MockRegistrar.return_value = mock_registrar

            validator = ContractValidator()
            result = validator.validate_and_register(
                contract_path=contract_path,
                namespace="production.orders",
                catalog_plugin=MagicMock(),
            )

            # Validation should still succeed (soft failure)
            assert result.valid is True
            # But should have a warning
            assert len(result.warnings) >= 1


__all__ = [
    "TestCatalogRegistrar",
    "TestCatalogRegistrarSoftFailure",
    "TestRegistrationResult",
    "TestContractValidatorRegistrationIntegration",
]
