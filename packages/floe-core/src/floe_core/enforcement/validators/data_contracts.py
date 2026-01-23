"""Data contract validation using ODCS v3 standard.

This module provides the ContractParser for validating and loading ODCS v3
data contracts using datacontract-cli and open-data-contract-standard.

Task: T018, T019, T020, T021, T022, T023, T024
Requirements: FR-001 (ODCS Parsing), FR-002 (Schema Requirements),
              FR-005-FR-010 (Type/Format/Classification Validation)

The ContractParser uses datacontract-cli to validate ODCS contracts and
returns the official OpenDataContractStandard Pydantic model from the
open-data-contract-standard package.

Example:
    >>> from floe_core.enforcement.validators.data_contracts import ContractParser
    >>> parser = ContractParser()
    >>> contract = parser.parse_contract(Path("datacontract.yaml"))
    >>> print(f"Contract: {contract.id} v{contract.version}")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from floe_core.enforcement.result import Violation
from floe_core.schemas.data_contract import DataContract

logger = structlog.get_logger(__name__)

# FLOE-E5xx error code documentation URL base
_DOCS_BASE_URL = "https://floe.dev/docs/errors"


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
    """Raised when contract linting fails.

    This error wraps linting failures from datacontract-cli,
    converting them to FLOE-E5xx violations for consistent error reporting.
    """

    pass


class ContractParser:
    """Parser for ODCS v3 data contracts using datacontract-cli.

    ContractParser validates ODCS v3 data contracts using datacontract-cli
    and returns the official OpenDataContractStandard Pydantic model from
    the open-data-contract-standard package.

    Attributes:
        _log: Structured logger for this parser instance.

    Example:
        >>> from floe_core.enforcement.validators.data_contracts import ContractParser
        >>> parser = ContractParser()
        >>>
        >>> # Parse and validate a contract
        >>> contract = parser.parse_contract(Path("datacontract.yaml"))
        >>> print(f"Contract: {contract.id} v{contract.version}")
        >>>
        >>> # Access schema (tables/models)
        >>> for schema in contract.schema_ or []:
        ...     print(f"  Table: {schema.name}")
        ...     for prop in schema.properties or []:
        ...         print(f"    Column: {prop.name} ({prop.logicalType})")
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

        Task: T020
        Requirements: FR-001 (ODCS Parsing), FR-002 (Schema Requirements)

        Uses datacontract-cli to load and validate the contract, then
        returns the OpenDataContractStandard Pydantic model.

        Args:
            path: Path to the datacontract.yaml file.

        Returns:
            Validated DataContract model (OpenDataContractStandard).

        Raises:
            ContractValidationError: If the file cannot be read or parsed.
            ContractLintError: If validation fails with violations.
            FileNotFoundError: If the file does not exist.
        """
        self._log.debug("parsing_contract", path=str(path))

        # Check file exists
        if not path.exists():
            raise FileNotFoundError(f"Contract file not found: {path}")

        # Use datacontract-cli to load and validate
        from datacontract.data_contract import DataContract as DCContract

        try:
            dc = DCContract(data_contract_file=str(path))
        except Exception as e:
            raise ContractValidationError(
                f"Failed to load contract file: {e}"
            ) from e

        # Lint the contract (validates against ODCS schema)
        lint_result = dc.lint()

        # Check if linting passed (result is ResultEnum)
        from datacontract.model.run import ResultEnum

        if lint_result.result != ResultEnum.passed:
            violations = _lint_result_to_violations(lint_result, path.stem)
            raise ContractLintError(
                f"Contract linting failed with {len(violations)} error(s)",
                violations=violations,
            )

        # Get the parsed ODCS model
        contract: DataContract = dc.get_data_contract()

        # Count schemas for logging
        schema_count = len(contract.schema_) if contract.schema_ else 0

        self._log.info(
            "contract_parsed",
            id=contract.id,
            name=contract.name,
            version=contract.version,
            schemas=schema_count,
        )
        return contract

    def parse_contract_string(self, yaml_content: str, name: str = "inline") -> DataContract:
        """Parse a YAML string into a DataContract model.

        Convenience method for parsing contracts from strings rather than files.

        Args:
            yaml_content: YAML content as a string.
            name: Name to use for error messages.

        Returns:
            Validated DataContract model (OpenDataContractStandard).

        Raises:
            ContractValidationError: If the YAML is invalid.
            ContractLintError: If validation fails with violations.
        """
        from datacontract.data_contract import DataContract as DCContract

        try:
            dc = DCContract(data_contract_str=yaml_content)
        except Exception as e:
            raise ContractValidationError(
                f"Failed to parse contract YAML: {e}"
            ) from e

        # Lint the contract
        lint_result = dc.lint()

        # Check if linting passed (result is ResultEnum)
        from datacontract.model.run import ResultEnum

        if lint_result.result != ResultEnum.passed:
            violations = _lint_result_to_violations(lint_result, name)
            raise ContractLintError(
                f"Contract linting failed with {len(violations)} error(s)",
                violations=violations,
            )

        # Get the parsed ODCS model
        return dc.get_data_contract()


def _check_datacontract_cli() -> None:
    """Verify datacontract-cli is installed.

    This is called during ContractParser initialization to fail fast
    if the required dependency is missing.

    Task: T019
    Requirements: FR-001 (hard dependency on datacontract-cli)

    Raises:
        ContractValidationError: If datacontract-cli is not installed.

    Example:
        >>> _check_datacontract_cli()  # No error if installed
        >>> # Raises ContractValidationError if not installed
    """
    try:
        from datacontract.data_contract import DataContract as DCContract  # noqa: F401
    except ImportError as e:
        raise ContractValidationError(
            "datacontract-cli is required but not installed. "
            "Install with: pip install datacontract-cli"
        ) from e


def _lint_result_to_violations(
    lint_result: Any,
    contract_name: str,
) -> list[Violation]:
    """Convert datacontract-cli lint result to list of Violations.

    Task: T021
    Requirements: FR-010 (Error Reporting)

    Maps lint errors to FLOE-E5xx error codes:
    - FLOE-E500: Invalid apiVersion
    - FLOE-E501: Missing required field
    - FLOE-E502: Invalid element type (logicalType)
    - FLOE-E503: Invalid enum value
    - FLOE-E504: Invalid format constraint
    - FLOE-E505: Invalid classification value
    - FLOE-E506: Pattern validation failed
    - FLOE-E507: Value constraint failed (min/max)

    Args:
        lint_result: datacontract-cli Run object from lint().
        contract_name: Name of the contract being validated.

    Returns:
        List of Violations with appropriate FLOE-E5xx error codes.
    """
    from datacontract.model.run import ResultEnum

    violations: list[Violation] = []

    # Access lint errors from the checks
    # Each check has a result field that is a ResultEnum
    if hasattr(lint_result, "checks"):
        for check in lint_result.checks:
            # Check if this check failed
            check_result = getattr(check, "result", None)
            if check_result and check_result != ResultEnum.passed:
                violation = _lint_check_to_violation(check, contract_name)
                violations.append(violation)

    # If no specific failed checks, create a generic error
    if not violations and lint_result.result != ResultEnum.passed:
        violations.append(
            Violation(
                error_code="FLOE-E509",
                severity="error",
                policy_type="data_contract",
                model_name=contract_name,
                column_name=None,
                message="Contract validation failed",
                expected="Valid ODCS v3 contract",
                actual="Invalid contract",
                suggestion="Check contract against ODCS v3 schema",
                documentation_url=f"{_DOCS_BASE_URL}/FLOE-E509",
            )
        )

    return violations


def _lint_check_to_violation(
    check: Any,
    contract_name: str,
) -> Violation:
    """Convert a single lint check to a Violation.

    Args:
        check: datacontract-cli Check object with name, reason, result fields.
        contract_name: Name of the contract being validated.

    Returns:
        Violation with appropriate FLOE-E5xx error code.
    """
    # Extract check details
    # Check object has: name, reason, result (ResultEnum)
    check_name = getattr(check, "name", "unknown") or "unknown"
    check_reason = getattr(check, "reason", None) or "Validation failed"
    check_result = getattr(check, "result", None)
    check_result_str = str(check_result.value) if check_result else "failed"

    # Map check name to error code
    error_code, expected = _map_lint_check_to_error_code(check_name, check_reason)

    return Violation(
        error_code=error_code,
        severity="error",
        policy_type="data_contract",
        model_name=contract_name,
        column_name=None,
        message=f"Contract lint check '{check_name}' failed: {check_reason}",
        expected=expected,
        actual=check_result_str,
        suggestion=_get_suggestion(error_code, check_name),
        documentation_url=f"{_DOCS_BASE_URL}/{error_code}",
    )


def _map_lint_check_to_error_code(check_name: str, reason: str) -> tuple[str, str]:
    """Map lint check name to FLOE-E5xx error code.

    Args:
        check_name: Name of the lint check.
        reason: Reason for failure.

    Returns:
        Tuple of (error_code, expected_description).
    """
    check_lower = check_name.lower()
    reason_lower = reason.lower()

    # Check for apiVersion errors
    if "apiversion" in check_lower or "version" in check_lower:
        return "FLOE-E500", "apiVersion matching pattern v3.x.x"

    # Check for missing required field
    if "required" in reason_lower or "missing" in reason_lower:
        return "FLOE-E501", "Required field to be present"

    # Check for type errors
    if "type" in check_lower or "logicaltype" in check_lower:
        return "FLOE-E502", "Valid logicalType (string, int, decimal, etc.)"

    # Check for enum errors
    if "enum" in reason_lower or "invalid value" in reason_lower:
        return "FLOE-E503", "Valid enum value"

    # Check for format errors
    if "format" in check_lower:
        return "FLOE-E504", "Valid format constraint"

    # Check for classification errors
    if "classification" in check_lower:
        return "FLOE-E505", "Valid classification (public, pii, phi, restricted)"

    # Check for pattern errors
    if "pattern" in reason_lower:
        return "FLOE-E506", "Value matching the required pattern"

    # Check for constraint errors
    if "constraint" in reason_lower or "range" in reason_lower:
        return "FLOE-E507", "Value within allowed range"

    # Default: generic validation error
    return "FLOE-E509", "Valid contract field value"


def _get_suggestion(error_code: str, context: str) -> str:
    """Get remediation suggestion for an error code.

    Args:
        error_code: FLOE-E5xx error code.
        context: Context string for the suggestion.

    Returns:
        Actionable remediation suggestion.
    """
    suggestions = {
        "FLOE-E500": "Update apiVersion to v3.0.0 or higher (v3.x.x format)",
        "FLOE-E501": f"Add the missing required field: {context}",
        "FLOE-E502": "Use a valid logicalType: string, int, long, float, double, decimal, boolean, date, timestamp, time, bytes, array, object",
        "FLOE-E503": "Check the allowed enum values for this field",
        "FLOE-E504": "Use a valid format: email, uri, uuid, ipv4, ipv6, hostname, date, datetime",
        "FLOE-E505": "Use a valid classification: public, pii, phi, restricted",
        "FLOE-E506": "Ensure the value matches the required pattern",
        "FLOE-E507": "Ensure the value is within the allowed range",
        "FLOE-E509": "Check the ODCS v3 contract documentation for valid field values",
    }
    return suggestions.get(error_code, "Review the ODCS v3 contract schema documentation")


__all__ = [
    "ContractParser",
    "ContractValidationError",
    "ContractLintError",
]
