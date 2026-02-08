"""Contract generation from FloeSpec output_ports.

This module provides the ContractGenerator class that creates ODCS v3
data contracts from FloeSpec output_ports definitions.

Tasks: T030, T031, T032, T033
Requirements: FR-003 (Auto-generation), FR-004 (Contract Merging)

The generator creates valid ODCS v3 contracts with:
- Contract name: {data_product_name}-{port_name}
- Contract version: data product version from metadata
- Schema: mapped from output_port columns to ODCS schema properties

Example:
    >>> from floe_core.contracts.generator import ContractGenerator
    >>> from floe_core.schemas.floe_spec import FloeSpec, FloeMetadata, OutputPort
    >>>
    >>> spec = FloeSpec(
    ...     apiVersion="floe.dev/v1",
    ...     kind="FloeSpec",
    ...     metadata=FloeMetadata(name="my-product", version="1.0.0"),
    ...     transforms=[TransformSpec(name="stg_data")],
    ...     outputPorts=[OutputPort(name="customers", schema=[...])]
    ... )
    >>> generator = ContractGenerator()
    >>> contracts = generator.generate_from_ports(spec)
    >>> print(f"Generated {len(contracts)} contracts")
"""

from __future__ import annotations

from typing import Any

import structlog

from floe_core.schemas.data_contract import (
    DataContract,
    SchemaObject,
    SchemaProperty,
)
from floe_core.schemas.floe_spec import FloeSpec, OutputPort, OutputPortColumn

logger = structlog.get_logger(__name__)

# Default ODCS apiVersion for generated contracts
DEFAULT_API_VERSION = "v3.1.0"

# Default contract status for generated contracts
DEFAULT_STATUS = "active"


class ContractGenerator:
    """Generator for ODCS v3 data contracts from FloeSpec output_ports.

    ContractGenerator creates valid ODCS v3 data contracts by extracting
    schema information from FloeSpec output_ports definitions.

    Tasks: T030, T031, T032, T033
    Requirements: FR-003, FR-004

    Attributes:
        _log: Structured logger for this generator instance.

    Example:
        >>> from floe_core.contracts.generator import ContractGenerator
        >>> from floe_core.schemas.floe_spec import FloeSpec
        >>>
        >>> generator = ContractGenerator()
        >>> contracts = generator.generate_from_ports(spec)
        >>>
        >>> # Merge with explicit contract (explicit wins)
        >>> merged = generator.merge_contracts(generated, explicit)
    """

    def __init__(self) -> None:
        """Initialize ContractGenerator."""
        self._log = logger.bind(component="ContractGenerator")
        self._log.debug("contract_generator_initialized")

    def generate_from_ports(self, spec: FloeSpec) -> list[DataContract]:
        """Generate ODCS v3 contracts from FloeSpec output_ports.

        Task: T031
        Requirements: FR-003

        Creates one contract per output_port, with:
        - name: {data_product_name}-{port_name}
        - id: {data_product_name}-{port_name}
        - version: data product version from metadata
        - schema: mapped from port columns

        Args:
            spec: FloeSpec containing output_ports definitions.

        Returns:
            List of generated DataContract models. Empty list if no output_ports.

        Example:
            >>> contracts = generator.generate_from_ports(spec)
            >>> for c in contracts:
            ...     print(f"{c.name}: {len(c.schema_[0].properties)} columns")
        """
        if not spec.output_ports:
            self._log.debug("no_output_ports", product=spec.metadata.name)
            return []

        contracts: list[DataContract] = []
        product_name = spec.metadata.name
        product_version = spec.metadata.version
        product_owner = spec.metadata.owner

        for port in spec.output_ports:
            contract = self._generate_contract_for_port(
                port=port,
                product_name=product_name,
                product_version=product_version,
                product_owner=product_owner,
            )
            contracts.append(contract)
            self._log.info(
                "contract_generated",
                contract_name=contract.name,
                version=contract.version,
                columns=len(port.schema_),
            )

        return contracts

    def _generate_contract_for_port(
        self,
        port: OutputPort,
        product_name: str,
        product_version: str,
        product_owner: str | None,
    ) -> DataContract:
        """Generate a single contract for an output port.

        Task: T033
        Requirements: FR-003

        Contract naming convention: {data_product_name}-{port_name}

        Args:
            port: Output port definition.
            product_name: Data product name from metadata.
            product_version: Data product version from metadata.
            product_owner: Data product owner from metadata.

        Returns:
            Generated DataContract model.
        """
        # Generate contract name per FR-003
        contract_name = f"{product_name}-{port.name}"

        # Use port owner if specified, fall back to product owner
        owner = port.owner or product_owner

        # Create schema properties from port columns
        properties = [self._column_to_property(col) for col in port.schema_]

        # Create schema object for the port
        schema_object = SchemaObject(
            name=port.name,
            description=port.description,
            properties=properties,
        )

        # Create the contract using ODCS model
        # Note: ODCS model uses 'schema' as input alias, stores as 'schema_'
        contract = DataContract(
            apiVersion=DEFAULT_API_VERSION,
            kind="DataContract",
            id=contract_name,
            version=product_version,
            name=contract_name,
            status=DEFAULT_STATUS,
            schema=[schema_object],  # Use alias 'schema', not 'schema_'
        )

        # Set owner if available (ODCS uses team for ownership)
        # Note: We store owner in a way compatible with ODCS
        # For generated contracts, we use the team field pattern
        if owner:
            # ODCS doesn't have a simple owner field, but we can store it
            # in the description or as a custom property for now
            pass

        return contract

    def _column_to_property(self, column: OutputPortColumn) -> SchemaProperty:
        """Convert OutputPortColumn to ODCS SchemaProperty.

        Maps FloeSpec column types to ODCS logicalType values.

        Args:
            column: OutputPortColumn from port definition.

        Returns:
            SchemaProperty for ODCS contract.
        """
        return SchemaProperty(
            name=column.name,
            logicalType=column.type,
            description=column.description,
            required=column.required if column.required else None,
            primaryKey=column.primary_key if column.primary_key else None,
            classification=column.classification,
        )

    def merge_contracts(
        self,
        generated: DataContract,
        explicit: DataContract,
    ) -> DataContract:
        """Merge generated contract with explicit contract (explicit wins).

        Task: T032
        Requirements: FR-004

        When both a generated contract (from output_ports) and an explicit
        contract (from datacontract.yaml) exist, merge them with explicit
        values taking precedence.

        Merge strategy:
        - Scalar fields: explicit value wins if set
        - Schema: explicit schema completely replaces generated
        - Collections: explicit collection replaces generated

        Args:
            generated: Contract generated from output_ports.
            explicit: Explicitly defined contract from datacontract.yaml.

        Returns:
            Merged DataContract with explicit values taking precedence.

        Example:
            >>> merged = generator.merge_contracts(generated, explicit)
            >>> # explicit.version will be used if set
            >>> # explicit.schema_ will completely replace generated.schema_
        """
        self._log.debug(
            "merging_contracts",
            generated_name=generated.name,
            explicit_name=explicit.name,
        )

        # Get explicit values, using generated as fallback
        # ODCS model uses model_dump() to convert to dict
        generated_data = generated.model_dump(by_alias=True, exclude_none=True)
        explicit_data = explicit.model_dump(by_alias=True, exclude_none=True)

        # Merge with explicit values taking precedence
        merged_data = self._deep_merge(generated_data, explicit_data)

        # Create merged contract
        merged = DataContract.model_validate(merged_data)

        self._log.info(
            "contracts_merged",
            merged_name=merged.name,
            merged_version=merged.version,
        )

        return merged

    def _deep_merge(
        self,
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """Deep merge two dictionaries with override taking precedence.

        For schema and other complex nested structures, explicit values
        completely replace base values (no deep merging of schema).

        Args:
            base: Base dictionary (generated values).
            override: Override dictionary (explicit values).

        Returns:
            Merged dictionary with override values taking precedence.
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Deep merge for nested dicts, but NOT for schema
                # Schema should be completely replaced
                if key == "schema":
                    result[key] = value
                else:
                    result[key] = self._deep_merge(result[key], value)
            else:
                # Override replaces base
                result[key] = value

        return result


__all__ = [
    "ContractGenerator",
]
