"""Data contract validation using datacontract-cli.

This module provides the ContractParser and ContractValidator classes for
validating ODCS v3 data contracts at compile time.

Task: T018, T019, T020, T021, T022, T023, T024
Requirements: FR-001 (ODCS Parsing), FR-002 (Schema Requirements),
              FR-005-FR-010 (Type/Format/Classification Validation)

The ContractParser delegates all ODCS parsing and linting to datacontract-cli,
which is a hard dependency for Epic 3C. This ensures full ODCS ecosystem
compatibility and consistency with Epic 3D runtime features.

Example:
    >>> from floe_core.enforcement.validators.data_contracts import ContractParser
    >>> parser = ContractParser()
    >>> contract = parser.parse_contract(Path("datacontract.yaml"))
    >>> print(f"Contract: {contract.name} v{contract.version}")
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.enforcement.result import Violation
from floe_core.schemas.data_contract import (
    DataContract,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class ContractValidationError(Exception):
    """Raised when contract validation fails.

    Attributes:
        message: Human-readable error message.
        violations: List of violations if applicable.
    """

    def __init__(
        self,
        message: str,
        violations: list[Violation] | None = None,
    ) -> None:
        """Initialize ContractValidationError.

        Args:
            message: Human-readable error message.
            violations: Optional list of violations that caused the error.
        """
        super().__init__(message)
        self.message = message
        self.violations = violations or []


class ContractLintError(ContractValidationError):
    """Raised when datacontract-cli linting fails.

    This error wraps linting failures from datacontract-cli, converting
    them to FLOE-E5xx violations for consistent error reporting.
    """

    pass


class ContractParser:
    """Parser for ODCS v3 data contracts using datacontract-cli.

    ContractParser wraps datacontract-cli to provide ODCS v3 parsing
    with lint validation and conversion to floe's DataContract model.

    The parser delegates all ODCS-specific validation to datacontract-cli,
    ensuring full compatibility with the ODCS ecosystem.

    Attributes:
        _log: Structured logger for this parser instance.

    Example:
        >>> from floe_core.enforcement.validators.data_contracts import ContractParser
        >>> parser = ContractParser()
        >>>
        >>> # Parse and validate a contract
        >>> contract = parser.parse_contract(Path("datacontract.yaml"))
        >>> print(f"Contract: {contract.name} v{contract.version}")
        >>>
        >>> # Handle validation errors
        >>> try:
        ...     contract = parser.parse_contract(Path("invalid.yaml"))
        ... except ContractLintError as e:
        ...     for v in e.violations:
        ...         print(f"{v.error_code}: {v.message}")
    """

    def __init__(self) -> None:
        """Initialize ContractParser.

        Verifies that datacontract-cli is installed and available.

        Raises:
            ContractValidationError: If datacontract-cli is not installed.
        """
        self._log = logger.bind(component="ContractParser")
        _check_datacontract_cli()
        self._log.debug("contract_parser_initialized")

    def parse_contract(self, path: Path) -> DataContract:
        """Parse a datacontract.yaml file into a DataContract model.

        Loads the YAML file, runs datacontract-cli lint validation,
        and converts the result to floe's DataContract Pydantic model.

        Args:
            path: Path to the datacontract.yaml file.

        Returns:
            Validated DataContract model.

        Raises:
            ContractValidationError: If the file cannot be read.
            ContractLintError: If linting fails with violations.
            FileNotFoundError: If the file does not exist.
        """
        # Implementation in T020
        raise NotImplementedError("T020: Implement parse_contract")


def _check_datacontract_cli() -> None:
    """Verify datacontract-cli is installed.

    This is called during ContractParser initialization to fail fast
    if the required dependency is missing.

    Raises:
        ContractValidationError: If datacontract-cli is not installed.
    """
    # Implementation in T019
    raise NotImplementedError("T019: Implement _check_datacontract_cli")


def _lint_error_to_violation(
    error: Any,
    contract_name: str,
) -> Violation:
    """Convert a datacontract-cli lint error to a Violation.

    Maps datacontract-cli error types to FLOE-E5xx error codes:
    - FLOE-E500: Invalid apiVersion
    - FLOE-E501: Missing required field
    - FLOE-E502: Invalid element type
    - FLOE-E503: ODCS version mismatch
    - FLOE-E504: Invalid format constraint
    - FLOE-E505: Invalid classification value

    Args:
        error: Lint error from datacontract-cli.
        contract_name: Name of the contract being validated.

    Returns:
        Violation with appropriate FLOE-E5xx error code.
    """
    # Implementation in T021
    raise NotImplementedError("T021: Implement _lint_error_to_violation")


def _convert_to_floe_model(
    dc_data: dict[str, Any],
) -> DataContract:
    """Convert datacontract-cli dict to floe DataContract model.

    Transforms the datacontract-cli internal representation to
    floe's Pydantic DataContract model, mapping all ODCS v3 fields.

    Args:
        dc_data: Dictionary representation from datacontract-cli.

    Returns:
        DataContract Pydantic model.

    Raises:
        ContractValidationError: If conversion fails.
    """
    # Implementation in T022
    raise NotImplementedError("T022: Implement _convert_to_floe_model")


__all__ = [
    "ContractParser",
    "ContractValidationError",
    "ContractLintError",
]
