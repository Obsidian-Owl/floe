"""Unit tests for ODCS contract parsing using ContractParser.

Task: T015
Requirements: FR-001 (ODCS Parsing), FR-002 (Schema Requirements),
              FR-005-FR-010 (Type/Format/Classification Validation)

Tests the ContractParser that uses datacontract-cli for ODCS v3 compliance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from floe_core.enforcement.validators.data_contracts import (
    ContractLintError,
    ContractParser,
    ContractValidationError,
)
from floe_core.schemas.data_contract import (
    Classification,
    ContractStatus,
    ElementType,
)


class TestContractParserODCSParsing:
    """Tests for parsing ODCS v3 contracts with ContractParser."""

    @pytest.fixture
    def parser(self) -> ContractParser:
        """Create a ContractParser instance."""
        return ContractParser()

    @pytest.mark.requirement("3C-FR-001")
    def test_parse_minimal_yaml(self, parser: ContractParser) -> None:
        """Test parsing minimal valid ODCS v3 YAML."""
        yaml_content = """
apiVersion: v3.1.0
kind: DataContract
id: customers
version: 1.0.0
name: customers
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        contract = parser.parse_contract_string(yaml_content)
        assert contract.apiVersion == "v3.1.0"
        assert contract.id == "customers"
        assert contract.version == "1.0.0"
        assert contract.name == "customers"
        assert contract.schema_ is not None
        assert len(contract.schema_) == 1
        assert contract.schema_[0].name == "customers"

    @pytest.mark.requirement("3C-FR-001")
    def test_parse_full_yaml(self, parser: ContractParser) -> None:
        """Test parsing full ODCS v3 YAML with all fields."""
        yaml_content = """
apiVersion: v3.1.0
kind: DataContract
id: orders
version: 2.1.0
name: orders
status: active
domain: sales
description:
  purpose: Customer orders data contract
  usage: Analytics and reporting
schema:
  - name: orders
    description: Order fact table
    properties:
      - name: order_id
        logicalType: string
        primaryKey: true
        required: true
      - name: customer_email
        logicalType: string
        classification: pii
      - name: total_amount
        logicalType: number
        required: true
slaProperties:
  - property: freshness
    value: PT6H
    element: updated_at
  - property: availability
    value: 99.9%
  - property: completeness
    value: 99%
tags:
  - production
  - gold
"""
        contract = parser.parse_contract_string(yaml_content)
        assert contract.apiVersion == "v3.1.0"
        assert contract.status == "active"
        assert contract.domain == "sales"
        assert contract.description is not None
        assert contract.description.purpose == "Customer orders data contract"
        assert contract.schema_ is not None
        assert len(contract.schema_) == 1
        assert contract.schema_[0].properties is not None
        assert len(contract.schema_[0].properties) == 3

        # Check SLA properties
        assert contract.slaProperties is not None
        assert len(contract.slaProperties) == 3

        # Check tags
        assert contract.tags == ["production", "gold"]

    @pytest.mark.requirement("3C-FR-005")
    def test_parse_all_logical_types(self, parser: ContractParser) -> None:
        """Test parsing elements with various ODCS logicalType values."""
        yaml_content = """
apiVersion: v3.1.0
kind: DataContract
id: types-test
version: 1.0.0
name: types-test
status: active
schema:
  - name: all_types
    properties:
      - name: string_col
        logicalType: string
      - name: int_col
        logicalType: integer
      - name: boolean_col
        logicalType: boolean
      - name: date_col
        logicalType: date
      - name: timestamp_col
        logicalType: timestamp
      - name: number_col
        logicalType: number
"""
        contract = parser.parse_contract_string(yaml_content)
        assert contract.schema_ is not None
        props = contract.schema_[0].properties
        assert props is not None
        assert len(props) == 6

        # Verify logical types parsed correctly
        type_map = {p.name: p.logicalType for p in props}
        assert type_map["string_col"] == "string"
        assert type_map["int_col"] == "integer"
        assert type_map["boolean_col"] == "boolean"
        assert type_map["timestamp_col"] == "timestamp"
        assert type_map["number_col"] == "number"

    @pytest.mark.requirement("3C-FR-008")
    def test_parse_classification_values(self, parser: ContractParser) -> None:
        """Test parsing elements with classification values."""
        yaml_content = """
apiVersion: v3.1.0
kind: DataContract
id: classified-data
version: 1.0.0
name: classified-data
status: active
schema:
  - name: classified
    properties:
      - name: public_data
        logicalType: string
        classification: public
      - name: pii_data
        logicalType: string
        classification: pii
"""
        contract = parser.parse_contract_string(yaml_content)
        assert contract.schema_ is not None
        props = contract.schema_[0].properties
        assert props is not None

        class_map = {p.name: p.classification for p in props}
        assert class_map["public_data"] == "public"
        assert class_map["pii_data"] == "pii"

    @pytest.mark.requirement("3C-FR-007")
    def test_parse_sla_properties(self, parser: ContractParser) -> None:
        """Test parsing various SLA properties."""
        yaml_content = """
apiVersion: v3.1.0
kind: DataContract
id: sla-test
version: 1.0.0
name: sla-test
status: active
schema:
  - name: test
    properties:
      - name: id
        logicalType: string
slaProperties:
  - property: freshness
    value: PT6H
    element: updated_at
  - property: availability
    value: 99.9%
"""
        contract = parser.parse_contract_string(yaml_content)
        assert contract.slaProperties is not None
        assert len(contract.slaProperties) == 2

        # Find freshness SLA
        freshness = next((s for s in contract.slaProperties if s.property == "freshness"), None)
        assert freshness is not None
        assert freshness.value == "PT6H"
        assert freshness.element == "updated_at"

    @pytest.mark.requirement("3C-FR-001")
    def test_parse_deprecated_contract(self, parser: ContractParser) -> None:
        """Test parsing deprecated contract status."""
        yaml_content = """
apiVersion: v3.1.0
kind: DataContract
id: customers-v1
version: 1.0.0
name: customers-v1
status: deprecated
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        contract = parser.parse_contract_string(yaml_content)
        assert contract.status == "deprecated"


class TestContractParserErrors:
    """Tests for parsing error handling."""

    @pytest.fixture
    def parser(self) -> ContractParser:
        """Create a ContractParser instance."""
        return ContractParser()

    @pytest.mark.requirement("3C-FR-010")
    def test_invalid_yaml_syntax(self, parser: ContractParser) -> None:
        """Test error when YAML syntax is invalid."""
        yaml_content = "invalid: yaml: content: ["

        # datacontract-cli wraps YAML errors in lint errors
        with pytest.raises((ContractValidationError, ContractLintError)):
            parser.parse_contract_string(yaml_content)

    @pytest.mark.requirement("3C-FR-010")
    def test_file_not_found(self, parser: ContractParser, tmp_path: Path) -> None:
        """Test error when file does not exist.

        Uses tmp_path to get a path that exists but file doesn't exist,
        avoiding the path traversal security check for absolute paths.
        """
        nonexistent_file = tmp_path / "nonexistent_datacontract.yaml"
        with pytest.raises(FileNotFoundError, match="Contract file not found"):
            parser.parse_contract(nonexistent_file)

    @pytest.mark.requirement("3C-FR-010")
    def test_path_traversal_blocked(self, parser: ContractParser) -> None:
        """Test that path traversal attempts are blocked.

        SECURITY: Absolute paths to non-existent files outside CWD are blocked
        to prevent directory traversal attacks.
        """
        with pytest.raises(ValueError, match="directory traversal"):
            parser.parse_contract(Path("/nonexistent/datacontract.yaml"))


class TestContractParserFileOperations:
    """Tests for file-based contract loading."""

    @pytest.fixture
    def parser(self) -> ContractParser:
        """Create a ContractParser instance."""
        return ContractParser()

    @pytest.mark.requirement("3C-FR-001")
    def test_load_contract_from_file(self, parser: ContractParser, tmp_path: Path) -> None:
        """Test loading contract from YAML file."""
        contract_file = tmp_path / "datacontract.yaml"
        contract_file.write_text("""
apiVersion: v3.1.0
kind: DataContract
id: file-test
version: 1.0.0
name: file-test
status: active
schema:
  - name: test
    properties:
      - name: id
        logicalType: string
""")
        contract = parser.parse_contract(contract_file)
        assert contract.id == "file-test"
        assert contract.schema_ is not None
        assert len(contract.schema_) == 1

    @pytest.mark.requirement("3C-FR-010")
    def test_load_invalid_yaml_file(self, parser: ContractParser, tmp_path: Path) -> None:
        """Test error handling for invalid YAML file."""
        contract_file = tmp_path / "invalid.yaml"
        contract_file.write_text("invalid: yaml: content: [")

        # datacontract-cli wraps YAML errors - could be validation or lint error
        with pytest.raises((ContractValidationError, ContractLintError)):
            parser.parse_contract(contract_file)


class TestElementTypeConstants:
    """Tests for ElementType constants."""

    def test_element_type_constants(self) -> None:
        """Test that ElementType constants match ODCS v3.1 logicalType values."""
        # Core ODCS types
        assert ElementType.STRING == "string"
        assert ElementType.INTEGER == "integer"
        assert ElementType.NUMBER == "number"
        assert ElementType.BOOLEAN == "boolean"
        assert ElementType.TIMESTAMP == "timestamp"
        assert ElementType.DATE == "date"
        assert ElementType.TIME == "time"
        assert ElementType.ARRAY == "array"
        assert ElementType.OBJECT == "object"

        # Aliases map to ODCS types
        assert ElementType.INT == "integer"  # Alias for INTEGER
        assert ElementType.DECIMAL == "number"  # Mapped to NUMBER


class TestClassificationConstants:
    """Tests for Classification constants."""

    def test_classification_constants(self) -> None:
        """Test that Classification constants match ODCS values."""
        assert Classification.PUBLIC == "public"
        assert Classification.PII == "pii"
        assert Classification.PHI == "phi"
        assert Classification.RESTRICTED == "restricted"


class TestContractStatusConstants:
    """Tests for ContractStatus constants."""

    def test_contract_status_constants(self) -> None:
        """Test that ContractStatus constants match ODCS values."""
        assert ContractStatus.ACTIVE == "active"
        assert ContractStatus.DEPRECATED == "deprecated"
        assert ContractStatus.DRAFT == "draft"
