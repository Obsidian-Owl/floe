"""Contract generation and management for floe data products.

This module provides contract generation from FloeSpec output_ports
and contract merging utilities for ODCS v3 data contracts.

Tasks: T029, T030, T031, T032, T033
Requirements: FR-003 (Auto-generation), FR-004 (Contract Merging)

Example:
    >>> from floe_core.contracts.generator import ContractGenerator
    >>> from floe_core.schemas.floe_spec import FloeSpec
    >>>
    >>> generator = ContractGenerator()
    >>> contracts = generator.generate_from_ports(spec)
    >>> for contract in contracts:
    ...     print(f"Generated: {contract.name} v{contract.version}")
"""

from __future__ import annotations

from floe_core.contracts.generator import ContractGenerator

__all__ = [
    "ContractGenerator",
]
