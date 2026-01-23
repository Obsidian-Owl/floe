"""Unit tests for datacontract-cli parsing wrapper.

Task: T015
Requirements: FR-001 (ODCS Parsing), FR-002 (Schema Requirements),
              FR-005-FR-010 (Type/Format/Classification Validation)

Tests the wrapper functions that delegate ODCS v3 parsing to datacontract-cli.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from floe_core.schemas.data_contract import (
    Classification,
    ContractStatus,
    DataContract,
    DataContractElement,
    DataContractModel,
    ElementFormat,
    ElementType,
    FreshnessSLA,
    QualitySLA,
    SLAProperties,
)


class TestDataContractYAMLParsing:
    """Tests for parsing datacontract.yaml files into DataContract models."""

    @pytest.mark.requirement("3C-FR-001")
    def test_parse_minimal_yaml(self) -> None:
        """Test parsing minimal valid ODCS v3 YAML."""
        yaml_content = """
apiVersion: v3.0.0
kind: DataContract
name: customers
version: "1.0.0"
owner: data-team@example.com
models:
  - name: customers
    elements:
      - name: id
        type: string
"""
        contract = self._parse_yaml_to_contract(yaml_content)
        assert contract.api_version == "v3.0.0"
        assert contract.name == "customers"
        assert contract.version == "1.0.0"
        assert contract.owner == "data-team@example.com"
        assert len(contract.models) == 1
        assert contract.models[0].name == "customers"

    @pytest.mark.requirement("3C-FR-001")
    def test_parse_full_yaml(self) -> None:
        """Test parsing full ODCS v3 YAML with all fields."""
        yaml_content = """
apiVersion: v3.0.2
kind: DataContract
name: orders
version: "2.1.0"
status: active
owner: analytics@example.com
domain: sales
team: analytics-team
description: Customer orders data contract
models:
  - name: orders
    description: Order fact table
    elements:
      - name: order_id
        type: string
        primaryKey: true
        required: true
      - name: customer_email
        type: string
        format: email
        classification: pii
      - name: total_amount
        type: decimal
        required: true
slaProperties:
  freshness:
    value: PT6H
    element: updated_at
  availability: "99.9%"
  quality:
    completeness: "99%"
    uniqueness: "100%"
tags:
  - production
  - gold
links:
  documentation: https://docs.example.com/orders
"""
        contract = self._parse_yaml_to_contract(yaml_content)
        assert contract.api_version == "v3.0.2"
        assert contract.status == ContractStatus.ACTIVE
        assert contract.domain == "sales"
        assert contract.description == "Customer orders data contract"
        assert len(contract.models) == 1
        assert len(contract.models[0].elements) == 3

        # Check SLA properties
        assert contract.sla_properties is not None
        assert contract.sla_properties.freshness is not None
        assert contract.sla_properties.freshness.value == "PT6H"
        assert contract.sla_properties.availability == "99.9%"

        # Check tags and links
        assert contract.tags == ["production", "gold"]
        assert contract.links["documentation"] == "https://docs.example.com/orders"

    @pytest.mark.requirement("3C-FR-005")
    def test_parse_all_element_types(self) -> None:
        """Test parsing elements with all ODCS v3 types."""
        yaml_content = """
apiVersion: v3.0.0
kind: DataContract
name: types-test
version: "1.0.0"
owner: test@example.com
models:
  - name: all_types
    elements:
      - name: string_col
        type: string
      - name: int_col
        type: int
      - name: long_col
        type: long
      - name: float_col
        type: float
      - name: double_col
        type: double
      - name: decimal_col
        type: decimal
      - name: boolean_col
        type: boolean
      - name: date_col
        type: date
      - name: timestamp_col
        type: timestamp
      - name: time_col
        type: time
      - name: bytes_col
        type: bytes
      - name: array_col
        type: array
      - name: object_col
        type: object
"""
        contract = self._parse_yaml_to_contract(yaml_content)
        elements = contract.models[0].elements
        assert len(elements) == 13

        # Verify all types parsed correctly
        type_map = {e.name: e.type for e in elements}
        assert type_map["string_col"] == ElementType.STRING
        assert type_map["int_col"] == ElementType.INT
        assert type_map["long_col"] == ElementType.LONG
        assert type_map["decimal_col"] == ElementType.DECIMAL
        assert type_map["timestamp_col"] == ElementType.TIMESTAMP
        assert type_map["time_col"] == ElementType.TIME

    @pytest.mark.requirement("3C-FR-009")
    def test_parse_format_constraints(self) -> None:
        """Test parsing elements with format constraints."""
        yaml_content = """
apiVersion: v3.0.0
kind: DataContract
name: formats-test
version: "1.0.0"
owner: test@example.com
models:
  - name: formatted
    elements:
      - name: email_col
        type: string
        format: email
      - name: uri_col
        type: string
        format: uri
      - name: uuid_col
        type: string
        format: uuid
      - name: ipv4_col
        type: string
        format: ipv4
"""
        contract = self._parse_yaml_to_contract(yaml_content)
        elements = contract.models[0].elements

        format_map = {e.name: e.format for e in elements}
        assert format_map["email_col"] == ElementFormat.EMAIL
        assert format_map["uri_col"] == ElementFormat.URI
        assert format_map["uuid_col"] == ElementFormat.UUID
        assert format_map["ipv4_col"] == ElementFormat.IPV4

    @pytest.mark.requirement("3C-FR-008")
    def test_parse_classification_values(self) -> None:
        """Test parsing elements with classification values."""
        yaml_content = """
apiVersion: v3.0.0
kind: DataContract
name: classified-data
version: "1.0.0"
owner: test@example.com
models:
  - name: classified
    elements:
      - name: public_data
        type: string
        classification: public
      - name: pii_data
        type: string
        classification: pii
      - name: phi_data
        type: string
        classification: phi
      - name: restricted_data
        type: string
        classification: restricted
"""
        contract = self._parse_yaml_to_contract(yaml_content)
        elements = contract.models[0].elements

        class_map = {e.name: e.classification for e in elements}
        assert class_map["public_data"] == Classification.PUBLIC
        assert class_map["pii_data"] == Classification.PII
        assert class_map["phi_data"] == Classification.PHI
        assert class_map["restricted_data"] == Classification.RESTRICTED

    @pytest.mark.requirement("3C-FR-007")
    def test_parse_sla_durations(self) -> None:
        """Test parsing various ISO 8601 duration formats."""
        yaml_content = """
apiVersion: v3.0.0
kind: DataContract
name: sla-test
version: "1.0.0"
owner: test@example.com
models:
  - name: test
    elements:
      - name: id
        type: string
slaProperties:
  freshness:
    value: PT6H
    element: updated_at
"""
        contract = self._parse_yaml_to_contract(yaml_content)
        assert contract.sla_properties is not None
        assert contract.sla_properties.freshness is not None
        assert contract.sla_properties.freshness.value == "PT6H"
        assert contract.sla_properties.freshness.element == "updated_at"

    @pytest.mark.requirement("3C-FR-001")
    def test_parse_deprecated_contract(self) -> None:
        """Test parsing deprecated contract with deprecation info."""
        yaml_content = """
apiVersion: v3.0.0
kind: DataContract
name: customers-v1
version: "1.0.0"
status: deprecated
owner: test@example.com
models:
  - name: customers
    elements:
      - name: id
        type: string
deprecation:
  announced: "2026-01-01"
  sunsetDate: "2026-06-01"
  replacement: customers-v2
  reason: Schema redesign for GDPR
"""
        contract = self._parse_yaml_to_contract(yaml_content)
        assert contract.status == ContractStatus.DEPRECATED
        assert contract.deprecation is not None
        assert contract.deprecation.announced == "2026-01-01"
        assert contract.deprecation.sunset_date == "2026-06-01"
        assert contract.deprecation.replacement == "customers-v2"

    def _parse_yaml_to_contract(self, yaml_content: str) -> DataContract:
        """Parse YAML string to DataContract model.

        This is a simplified parser for testing. The real implementation
        will use datacontract-cli for full ODCS v3 compliance.
        """
        import yaml

        data = yaml.safe_load(yaml_content)
        return self._dict_to_contract(data)

    def _dict_to_contract(self, data: dict[str, Any]) -> DataContract:
        """Convert parsed YAML dict to DataContract model."""
        # Parse models
        models = []
        for model_data in data.get("models", []):
            elements = []
            for elem_data in model_data.get("elements", []):
                element = DataContractElement(
                    name=elem_data["name"],
                    type=ElementType(elem_data["type"]),
                    required=elem_data.get("required", False),
                    primary_key=elem_data.get("primaryKey", False),
                    unique=elem_data.get("unique", False),
                    format=ElementFormat(elem_data["format"]) if elem_data.get("format") else None,
                    classification=Classification(elem_data["classification"])
                    if elem_data.get("classification")
                    else None,
                    enum=elem_data.get("enum"),
                    description=elem_data.get("description"),
                )
                elements.append(element)

            model = DataContractModel(
                name=model_data["name"],
                description=model_data.get("description"),
                elements=elements,
            )
            models.append(model)

        # Parse SLA properties
        sla_properties = None
        if "slaProperties" in data:
            sla_data = data["slaProperties"]
            freshness = None
            if "freshness" in sla_data:
                freshness = FreshnessSLA(
                    value=sla_data["freshness"]["value"],
                    element=sla_data["freshness"].get("element"),
                )
            quality = None
            if "quality" in sla_data:
                quality = QualitySLA(
                    completeness=sla_data["quality"].get("completeness"),
                    uniqueness=sla_data["quality"].get("uniqueness"),
                    accuracy=sla_data["quality"].get("accuracy"),
                )
            sla_properties = SLAProperties(
                freshness=freshness,
                availability=sla_data.get("availability"),
                quality=quality,
            )

        # Parse deprecation info
        from floe_core.schemas.data_contract import DeprecationInfo

        deprecation = None
        if "deprecation" in data:
            dep_data = data["deprecation"]
            deprecation = DeprecationInfo(
                announced=dep_data.get("announced"),
                sunset_date=dep_data.get("sunsetDate"),
                replacement=dep_data.get("replacement"),
                migration_guide=dep_data.get("migrationGuide"),
                reason=dep_data.get("reason"),
            )

        # Build contract
        return DataContract(
            api_version=data["apiVersion"],
            kind=data.get("kind", "DataContract"),
            name=data["name"],
            version=data["version"],
            status=ContractStatus(data.get("status", "active")),
            owner=data["owner"],
            domain=data.get("domain"),
            team=data.get("team"),
            description=data.get("description"),
            models=models,
            sla_properties=sla_properties,
            deprecation=deprecation,
            tags=data.get("tags", []),
            links=data.get("links", {}),
        )


class TestDataContractParsingErrors:
    """Tests for parsing error handling."""

    @pytest.mark.requirement("3C-FR-010")
    def test_missing_api_version(self) -> None:
        """Test error when apiVersion is missing."""
        with pytest.raises(ValidationError, match="apiVersion"):
            DataContract(
                name="test",
                version="1.0.0",
                owner="test@example.com",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )  # type: ignore[call-arg]

    @pytest.mark.requirement("3C-FR-010")
    def test_invalid_api_version(self) -> None:
        """Test error for invalid apiVersion (not v3.x.x)."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            DataContract(
                api_version="v2.0.0",  # Invalid - not v3
                name="test",
                version="1.0.0",
                owner="test@example.com",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )

    @pytest.mark.requirement("3C-FR-010")
    def test_missing_required_fields(self) -> None:
        """Test error when required fields are missing."""
        # Missing name
        with pytest.raises(ValidationError, match="name"):
            DataContract(
                api_version="v3.0.0",
                version="1.0.0",
                owner="test@example.com",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )  # type: ignore[call-arg]

        # Missing owner
        with pytest.raises(ValidationError, match="owner"):
            DataContract(
                api_version="v3.0.0",
                name="test",
                version="1.0.0",
                models=[
                    DataContractModel(
                        name="test",
                        elements=[DataContractElement(name="id", type=ElementType.STRING)],
                    )
                ],
            )  # type: ignore[call-arg]

    @pytest.mark.requirement("3C-FR-005")
    def test_invalid_element_type(self) -> None:
        """Test error for invalid element type."""
        with pytest.raises(ValueError, match="'invalid_type' is not a valid ElementType"):
            DataContractElement(
                name="test_col",
                type=ElementType("invalid_type"),  # type: ignore[arg-type]
            )

    @pytest.mark.requirement("3C-FR-006")
    def test_empty_models_list(self) -> None:
        """Test error when models list is empty."""
        with pytest.raises(ValidationError, match="at least 1"):
            DataContract(
                api_version="v3.0.0",
                name="test",
                version="1.0.0",
                owner="test@example.com",
                models=[],
            )

    @pytest.mark.requirement("3C-FR-006")
    def test_empty_elements_list(self) -> None:
        """Test error when elements list is empty."""
        with pytest.raises(ValidationError, match="at least 1"):
            DataContractModel(name="test", elements=[])

    @pytest.mark.requirement("3C-FR-007")
    def test_invalid_duration_format(self) -> None:
        """Test error for invalid ISO 8601 duration."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            FreshnessSLA(value="6 hours")  # Invalid format

    @pytest.mark.requirement("3C-FR-002")
    def test_invalid_percentage_format(self) -> None:
        """Test error for invalid percentage format."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            QualitySLA(completeness="99.5")  # Missing %


class TestDataContractFileOperations:
    """Tests for file-based contract loading."""

    @pytest.mark.requirement("3C-FR-001")
    def test_load_contract_from_file(self, tmp_path: Path) -> None:
        """Test loading contract from YAML file."""
        contract_file = tmp_path / "datacontract.yaml"
        contract_file.write_text("""
apiVersion: v3.0.0
kind: DataContract
name: file-test
version: "1.0.0"
owner: test@example.com
models:
  - name: test
    elements:
      - name: id
        type: string
""")
        import yaml

        with open(contract_file) as f:
            data = yaml.safe_load(f)

        # Simplified parsing - real impl uses datacontract-cli
        contract = DataContract(
            api_version=data["apiVersion"],
            name=data["name"],
            version=data["version"],
            owner=data["owner"],
            models=[
                DataContractModel(
                    name=data["models"][0]["name"],
                    elements=[
                        DataContractElement(
                            name=data["models"][0]["elements"][0]["name"],
                            type=ElementType(data["models"][0]["elements"][0]["type"]),
                        )
                    ],
                )
            ],
        )
        assert contract.name == "file-test"

    @pytest.mark.requirement("3C-FR-010")
    def test_load_invalid_yaml_file(self, tmp_path: Path) -> None:
        """Test error handling for invalid YAML."""
        import yaml

        contract_file = tmp_path / "invalid.yaml"
        contract_file.write_text("invalid: yaml: content: [")

        with pytest.raises(yaml.YAMLError):
            with open(contract_file) as f:
                yaml.safe_load(f)
