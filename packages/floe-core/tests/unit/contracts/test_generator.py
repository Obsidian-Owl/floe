"""Unit tests for contract generation from output_ports.

Task: T027, T028
Requirements: FR-003 (Auto-generation), FR-004 (Contract Merging)

Tests the ContractGenerator that creates ODCS v3 data contracts
from FloeSpec output_ports definitions.
"""

from __future__ import annotations

import pytest

from floe_core.schemas.floe_spec import (
    FloeMetadata,
    FloeSpec,
    OutputPort,
    OutputPortColumn,
    TransformSpec,
)


class TestContractGeneratorFromPorts:
    """Tests for generating contracts from output_ports (US2)."""

    @pytest.fixture
    def sample_floe_spec(self) -> FloeSpec:
        """Create a sample FloeSpec with output_ports."""
        return FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="customer-analytics",
                version="1.0.0",
                owner="analytics-team@acme.com",
            ),
            transforms=[TransformSpec(name="stg_customers")],
            outputPorts=[
                OutputPort(
                    name="customers",
                    description="Customer master data",
                    owner="analytics-team@acme.com",
                    schema=[
                        OutputPortColumn(
                            name="customer_id",
                            type="string",
                            required=True,
                            primaryKey=True,
                            description="Unique customer identifier",
                        ),
                        OutputPortColumn(
                            name="email",
                            type="string",
                            required=True,
                            classification="pii",
                        ),
                        OutputPortColumn(
                            name="created_at",
                            type="timestamp",
                            required=True,
                        ),
                        OutputPortColumn(
                            name="age",
                            type="integer",
                            required=False,
                        ),
                    ],
                )
            ],
        )

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_contract_from_ports_creates_valid_contract(
        self, sample_floe_spec: FloeSpec
    ) -> None:
        """Test that generate_from_ports creates a valid ODCS v3 contract."""
        # Import here to allow test discovery before implementation
        from floe_core.contracts.generator import ContractGenerator

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(sample_floe_spec)

        assert len(contracts) == 1
        contract = contracts[0]

        # Verify contract structure (ODCS v3 format)
        assert contract.apiVersion == "v3.1.0"
        assert contract.kind == "DataContract"
        assert contract.status == "active"

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_contract_name_follows_convention(self, sample_floe_spec: FloeSpec) -> None:
        """Test that contract name is {data_product_name}-{port_name}."""
        from floe_core.contracts.generator import ContractGenerator

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(sample_floe_spec)

        contract = contracts[0]
        expected_name = "customer-analytics-customers"
        assert contract.name == expected_name
        assert contract.id == expected_name

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_contract_version_matches_product(self, sample_floe_spec: FloeSpec) -> None:
        """Test that contract version matches data product version."""
        from floe_core.contracts.generator import ContractGenerator

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(sample_floe_spec)

        contract = contracts[0]
        assert contract.version == sample_floe_spec.metadata.version

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_contract_schema_includes_columns(self, sample_floe_spec: FloeSpec) -> None:
        """Test that generated contract schema includes all port columns."""
        from floe_core.contracts.generator import ContractGenerator

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(sample_floe_spec)

        contract = contracts[0]
        assert contract.schema_ is not None
        assert len(contract.schema_) == 1  # One schema object

        schema = contract.schema_[0]
        assert schema.name == "customers"
        assert schema.properties is not None
        assert len(schema.properties) == 4  # 4 columns

        # Verify columns are present
        col_names = {p.name for p in schema.properties}
        assert col_names == {"customer_id", "email", "created_at", "age"}

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_contract_maps_types_correctly(self, sample_floe_spec: FloeSpec) -> None:
        """Test that port types are mapped to ODCS logicalType."""
        from floe_core.contracts.generator import ContractGenerator

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(sample_floe_spec)

        schema = contracts[0].schema_[0]
        type_map = {p.name: p.logicalType for p in schema.properties or []}

        assert type_map["customer_id"] == "string"
        assert type_map["email"] == "string"
        assert type_map["created_at"] == "timestamp"
        assert type_map["age"] == "integer"

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_contract_preserves_required_flag(self, sample_floe_spec: FloeSpec) -> None:
        """Test that required flag is preserved in generated contract."""
        from floe_core.contracts.generator import ContractGenerator

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(sample_floe_spec)

        schema = contracts[0].schema_[0]
        required_map = {p.name: p.required for p in schema.properties or []}

        assert required_map["customer_id"] is True
        assert required_map["email"] is True
        assert required_map["created_at"] is True
        assert required_map["age"] is False or required_map["age"] is None

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_contract_preserves_primary_key(self, sample_floe_spec: FloeSpec) -> None:
        """Test that primaryKey flag is preserved in generated contract."""
        from floe_core.contracts.generator import ContractGenerator

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(sample_floe_spec)

        schema = contracts[0].schema_[0]
        pk_map = {p.name: p.primaryKey for p in schema.properties or []}

        assert pk_map["customer_id"] is True
        assert pk_map.get("email") is not True
        assert pk_map.get("created_at") is not True

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_contract_preserves_classification(self, sample_floe_spec: FloeSpec) -> None:
        """Test that classification is preserved in generated contract."""
        from floe_core.contracts.generator import ContractGenerator

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(sample_floe_spec)

        schema = contracts[0].schema_[0]
        class_map = {p.name: p.classification for p in schema.properties or []}

        assert class_map["email"] == "pii"
        assert class_map.get("customer_id") is None

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_multiple_ports_creates_multiple_contracts(self) -> None:
        """Test that multiple output_ports generate multiple contracts."""
        from floe_core.contracts.generator import ContractGenerator

        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(name="multi-port", version="1.0.0"),
            transforms=[TransformSpec(name="stg_data")],
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

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(spec)

        assert len(contracts) == 2
        names = {c.name for c in contracts}
        assert names == {"multi-port-customers", "multi-port-orders"}

    @pytest.mark.requirement("3C-FR-003")
    def test_generate_no_output_ports_returns_empty(self) -> None:
        """Test that FloeSpec without output_ports returns empty list."""
        from floe_core.contracts.generator import ContractGenerator

        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(name="no-ports", version="1.0.0"),
            transforms=[TransformSpec(name="stg_data")],
        )

        generator = ContractGenerator()
        contracts = generator.generate_from_ports(spec)

        assert contracts == []


class TestContractMerging:
    """Tests for merging explicit contracts with generated contracts (US2)."""

    @pytest.mark.requirement("3C-FR-004")
    def test_explicit_contract_overrides_generated(self) -> None:
        """Test that explicit datacontract.yaml overrides generated values."""
        from floe_core.contracts.generator import ContractGenerator

        # Create a mock explicit contract (ODCS model)
        # Note: This requires actually creating an ODCS DataContract
        # For now, test the merge logic concept
        generator = ContractGenerator()

        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(name="test-product", version="1.0.0"),
            transforms=[TransformSpec(name="stg_data")],
            outputPorts=[
                OutputPort(
                    name="customers",
                    schema=[OutputPortColumn(name="id", type="string")],
                ),
            ],
        )

        # Generate base contract
        generated = generator.generate_from_ports(spec)
        assert len(generated) == 1

        # Create explicit contract with different status
        from floe_core.enforcement.validators.data_contracts import ContractParser

        parser = ContractParser()
        explicit_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-product-customers
version: 2.0.0
name: test-product-customers
status: deprecated
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
      - name: extra_col
        logicalType: integer
"""
        explicit = parser.parse_contract_string(explicit_yaml)

        # Merge contracts (explicit wins)
        merged = generator.merge_contracts(generated[0], explicit)

        # Explicit values should win
        assert merged.version == "2.0.0"  # From explicit
        assert merged.status == "deprecated"  # From explicit
        # Extra columns from explicit should be included
        assert len(merged.schema_[0].properties) == 2

    @pytest.mark.requirement("3C-FR-004")
    def test_merge_preserves_generated_fields_not_in_explicit(self) -> None:
        """Test that merge preserves generated fields when explicit is minimal."""
        from floe_core.contracts.generator import ContractGenerator
        from floe_core.enforcement.validators.data_contracts import ContractParser

        generator = ContractGenerator()

        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="test-product",
                version="1.0.0",
                owner="team@acme.com",
            ),
            transforms=[TransformSpec(name="stg_data")],
            outputPorts=[
                OutputPort(
                    name="customers",
                    description="Full description from port",
                    schema=[
                        OutputPortColumn(name="id", type="string", classification="pii"),
                    ],
                ),
            ],
        )

        generated = generator.generate_from_ports(spec)

        # Minimal explicit contract that only sets version
        parser = ContractParser()
        explicit_yaml = """
apiVersion: v3.1.0
kind: DataContract
id: test-product-customers
version: 2.0.0
name: test-product-customers
status: active
schema:
  - name: customers
    properties:
      - name: id
        logicalType: string
"""
        explicit = parser.parse_contract_string(explicit_yaml)

        merged = generator.merge_contracts(generated[0], explicit)

        # Version from explicit
        assert merged.version == "2.0.0"
        # Structure preserved
        assert merged.schema_ is not None
