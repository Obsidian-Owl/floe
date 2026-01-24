"""Unit tests for ContractValidator.validate_or_generate method.

Task: T034, T035
Requirements: FR-003 (Auto-generation from output_ports), FR-004 (Merging)

Tests the auto-generation flow:
1. If explicit contract exists, validate it
2. If no explicit contract, generate from output_ports
3. If neither exists, return FLOE-E500 error
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from floe_core.enforcement.validators.data_contracts import ContractValidator
from floe_core.schemas.floe_spec import (
    FloeMetadata,
    FloeSpec,
    OutputPort,
    OutputPortColumn,
    TransformSpec,
)

if TYPE_CHECKING:
    pass


class TestValidateOrGenerateFloeE500:
    """Tests for FLOE-E500 error when no contract source exists."""

    @pytest.fixture
    def validator(self) -> ContractValidator:
        """Create a ContractValidator instance."""
        return ContractValidator()

    @pytest.fixture
    def spec_no_ports(self) -> FloeSpec:
        """Create a FloeSpec without output_ports."""
        return FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="test-product",
                version="1.0.0",
            ),
            transforms=[TransformSpec(name="stg_test", dependsOn=[])],
            outputPorts=None,
        )

    @pytest.mark.requirement("3C-FR-003")
    def test_no_contract_and_no_ports_returns_floe_e500(
        self,
        validator: ContractValidator,
        spec_no_ports: FloeSpec,
    ) -> None:
        """Test FLOE-E500 when neither contract nor output_ports exist."""
        results = validator.validate_or_generate(
            spec=spec_no_ports,
            contract_path=None,
            enforcement_level="strict",
        )

        assert len(results) == 1
        result = results[0]
        assert result.valid is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.error_code == "FLOE-E500"
        assert "test-product" in violation.message
        assert "datacontract.yaml" in violation.message
        assert "output_ports" in violation.message

    @pytest.mark.requirement("3C-FR-003")
    def test_no_contract_and_no_ports_suggestion(
        self,
        validator: ContractValidator,
        spec_no_ports: FloeSpec,
    ) -> None:
        """Test FLOE-E500 includes helpful suggestion."""
        results = validator.validate_or_generate(
            spec=spec_no_ports,
            contract_path=None,
            enforcement_level="strict",
        )

        violation = results[0].violations[0]
        assert violation.suggestion is not None
        assert "datacontract.yaml" in violation.suggestion
        assert "outputPorts" in violation.suggestion

    @pytest.mark.requirement("3C-FR-003")
    def test_enforcement_off_skips_validation(
        self,
        validator: ContractValidator,
        spec_no_ports: FloeSpec,
    ) -> None:
        """Test that enforcement=off skips validation even without contract source."""
        results = validator.validate_or_generate(
            spec=spec_no_ports,
            contract_path=None,
            enforcement_level="off",
        )

        assert len(results) == 1
        result = results[0]
        assert result.valid is True
        assert len(result.violations) == 0


class TestValidateOrGenerateFromPorts:
    """Tests for auto-generation from output_ports."""

    @pytest.fixture
    def validator(self) -> ContractValidator:
        """Create a ContractValidator instance."""
        return ContractValidator()

    @pytest.fixture
    def spec_with_ports(self) -> FloeSpec:
        """Create a FloeSpec with output_ports."""
        return FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="test-product",
                version="1.0.0",
            ),
            transforms=[TransformSpec(name="stg_test", dependsOn=[])],
            outputPorts=[
                OutputPort(
                    name="customers",
                    description="Customer data",
                    schema=[
                        OutputPortColumn(
                            name="id",
                            type="string",
                            required=True,
                            primaryKey=True,
                        ),
                        OutputPortColumn(
                            name="email",
                            type="string",
                            classification="pii",
                        ),
                    ],
                ),
            ],
        )

    @pytest.mark.requirement("3C-FR-003")
    def test_generates_contract_from_ports(
        self,
        validator: ContractValidator,
        spec_with_ports: FloeSpec,
    ) -> None:
        """Test auto-generation when output_ports exist."""
        results = validator.validate_or_generate(
            spec=spec_with_ports,
            contract_path=None,
            enforcement_level="strict",
        )

        assert len(results) == 1
        result = results[0]
        assert result.valid is True
        assert len(result.violations) == 0
        assert result.contract_name == "test-product-customers"
        assert result.contract_version == "1.0.0"

    @pytest.mark.requirement("3C-FR-003")
    def test_generates_multiple_contracts_for_multiple_ports(
        self,
        validator: ContractValidator,
    ) -> None:
        """Test auto-generation creates one contract per port."""
        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="multi-product",
                version="2.0.0",
            ),
            transforms=[TransformSpec(name="stg_test", dependsOn=[])],
            outputPorts=[
                OutputPort(
                    name="customers",
                    schema=[OutputPortColumn(name="id", type="string")],
                ),
                OutputPort(
                    name="orders",
                    schema=[OutputPortColumn(name="order_id", type="string")],
                ),
            ],
        )

        results = validator.validate_or_generate(
            spec=spec,
            contract_path=None,
            enforcement_level="strict",
        )

        assert len(results) == 2
        names = {r.contract_name for r in results}
        assert names == {"multi-product-customers", "multi-product-orders"}

    @pytest.mark.requirement("3C-FR-003")
    def test_generated_contract_has_schema_hash(
        self,
        validator: ContractValidator,
        spec_with_ports: FloeSpec,
    ) -> None:
        """Test generated contracts have computed schema hash."""
        results = validator.validate_or_generate(
            spec=spec_with_ports,
            contract_path=None,
            enforcement_level="strict",
        )

        assert len(results) == 1
        assert results[0].schema_hash.startswith("sha256:")
        assert len(results[0].schema_hash) == 71  # "sha256:" + 64 hex chars


class TestValidateOrGenerateExplicitContract:
    """Tests for validating explicit contract files."""

    @pytest.fixture
    def validator(self) -> ContractValidator:
        """Create a ContractValidator instance."""
        return ContractValidator()

    @pytest.fixture
    def spec_no_ports(self) -> FloeSpec:
        """Create a FloeSpec without output_ports."""
        return FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="test-product",
                version="1.0.0",
            ),
            transforms=[TransformSpec(name="stg_test", dependsOn=[])],
            outputPorts=None,
        )

    @pytest.fixture
    def valid_contract_file(self, tmp_path: Path) -> Path:
        """Create a valid contract file for testing."""
        contract_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-contract
version: 1.0.0
name: test-contract
status: active
schema:
  - name: test
    properties:
      - name: id
        logicalType: string
"""
        contract_path = tmp_path / "datacontract.yaml"
        contract_path.write_text(contract_yaml)
        return contract_path

    @pytest.mark.requirement("3C-FR-001")
    def test_validates_explicit_contract(
        self,
        validator: ContractValidator,
        spec_no_ports: FloeSpec,
        valid_contract_file: Path,
    ) -> None:
        """Test validation of explicit contract file."""
        results = validator.validate_or_generate(
            spec=spec_no_ports,
            contract_path=valid_contract_file,
            enforcement_level="strict",
        )

        assert len(results) == 1
        result = results[0]
        assert result.valid is True
        assert result.contract_name == "test-contract"

    @pytest.mark.requirement("3C-FR-001")
    def test_explicit_contract_takes_precedence(
        self,
        validator: ContractValidator,
        valid_contract_file: Path,
    ) -> None:
        """Test explicit contract takes precedence over output_ports."""
        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="test-product",
                version="1.0.0",
            ),
            transforms=[TransformSpec(name="stg_test", dependsOn=[])],
            outputPorts=[
                OutputPort(
                    name="customers",
                    schema=[OutputPortColumn(name="id", type="string")],
                ),
            ],
        )

        results = validator.validate_or_generate(
            spec=spec,
            contract_path=valid_contract_file,
            enforcement_level="strict",
        )

        # Should return explicit contract result, not generated
        assert len(results) == 1
        assert results[0].contract_name == "test-contract"


__all__ = [
    "TestValidateOrGenerateFloeE500",
    "TestValidateOrGenerateFromPorts",
    "TestValidateOrGenerateExplicitContract",
]
