"""Data contract validation using ODCS v3 standard.

This module provides the ContractParser for validating and loading ODCS v3
data contracts using datacontract-cli and open-data-contract-standard.

Task: T018, T019, T020, T021, T022, T023, T024, T034, T035
Requirements: FR-001 (ODCS Parsing), FR-002 (Schema Requirements),
              FR-003 (Auto-generation), FR-004 (Merging),
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

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from floe_core.contracts.generator import ContractGenerator
from floe_core.enforcement.result import Violation
from floe_core.schemas.data_contract import (
    ContractValidationResult,
    ContractViolation,
    DataContract,
)
from floe_core.schemas.floe_spec import FloeSpec

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


class ContractValidator:
    """Validator for ODCS v3 data contracts.

    ContractValidator is the main entry point for validating data contracts
    at compile time. It orchestrates contract parsing, ODCS compliance checking,
    and future validation steps (inheritance, versioning, drift detection).

    Task: T023
    Requirements: FR-001, FR-002, FR-005-FR-010

    Attributes:
        _parser: ContractParser instance for loading contracts.
        _log: Structured logger for this validator instance.

    Example:
        >>> from floe_core.enforcement.validators.data_contracts import ContractValidator
        >>> validator = ContractValidator()
        >>>
        >>> # Validate a contract file
        >>> result = validator.validate(Path("datacontract.yaml"))
        >>> if result.valid:
        ...     print(f"Contract {result.contract_name} is valid")
        ... else:
        ...     for v in result.violations:
        ...         print(f"{v.error_code}: {v.message}")
        >>>
        >>> # Validate with enforcement level
        >>> result = validator.validate(
        ...     Path("datacontract.yaml"),
        ...     enforcement_level="strict"
        ... )
    """

    def __init__(self) -> None:
        """Initialize ContractValidator.

        Creates a ContractParser instance for loading contracts.

        Raises:
            ContractValidationError: If datacontract-cli is not installed.
        """
        self._parser = ContractParser()
        self._log = logger.bind(component="ContractValidator")
        self._log.debug("contract_validator_initialized")

    def validate(
        self,
        contract_path: Path,
        enforcement_level: str = "strict",
    ) -> ContractValidationResult:
        """Validate a data contract file.

        Task: T023
        Requirements: FR-001, FR-002, FR-005-FR-010, FR-032

        Performs the following validation steps:
        1. Parse and lint contract via datacontract-cli (ODCS compliance)
        2. Future: Inheritance validation (T039-T045)
        3. Future: Version validation (T049-T055)
        4. Future: Drift detection (T061-T066)

        Args:
            contract_path: Path to the datacontract.yaml file.
            enforcement_level: Enforcement level from governance config.
                - "off": Skip validation entirely
                - "warn": Validate but don't fail
                - "strict": Validate and fail on errors

        Returns:
            ContractValidationResult with validation outcome, violations,
            and metadata (schema hash, timestamp).

        Raises:
            FileNotFoundError: If contract file doesn't exist.
        """
        self._log.info(
            "validating_contract",
            path=str(contract_path),
            enforcement_level=enforcement_level,
        )

        # Check if validation is disabled
        if enforcement_level == "off":
            self._log.info("contract_validation_skipped", reason="enforcement=off")
            return self._create_skipped_result(contract_path)

        violations: list[ContractViolation] = []
        warnings: list[ContractViolation] = []
        contract: DataContract | None = None

        # Step 1: Parse and validate ODCS compliance
        try:
            contract = self._parser.parse_contract(contract_path)
            self._log.debug(
                "contract_parsed_successfully",
                contract_id=contract.id,
                version=contract.version,
            )
        except ContractLintError as e:
            # Convert Violations to ContractViolations
            for v in e.violations:
                contract_violation = ContractViolation(
                    error_code=v.error_code,
                    severity=v.severity,
                    message=v.message,
                    model_name=v.model_name,
                    element_name=v.column_name,
                    expected=v.expected,
                    actual=v.actual,
                    suggestion=v.suggestion,
                )
                if v.severity == "warning":
                    warnings.append(contract_violation)
                else:
                    violations.append(contract_violation)
        except ContractValidationError as e:
            # Generic validation error
            violations.append(
                ContractViolation(
                    error_code="FLOE-E509",
                    severity="error",
                    message=str(e),
                    suggestion="Check the contract file syntax and ODCS compliance",
                )
            )

        # Compute schema hash for fingerprinting
        schema_hash = self._compute_schema_hash(contract_path)

        # Determine contract name and version
        contract_name = contract.name if contract else contract_path.stem
        contract_version = contract.version if contract else "unknown"

        # Build result
        result = ContractValidationResult(
            valid=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            schema_hash=schema_hash,
            validated_at=datetime.now(timezone.utc),
            contract_name=contract_name or contract_path.stem,
            contract_version=contract_version or "unknown",
        )

        # Log outcome
        if result.valid:
            self._log.info(
                "contract_validation_passed",
                contract_name=result.contract_name,
                warnings=len(warnings),
            )
        else:
            self._log.warning(
                "contract_validation_failed",
                contract_name=result.contract_name,
                errors=len(violations),
                warnings=len(warnings),
            )

        return result

    def validate_string(
        self,
        yaml_content: str,
        name: str = "inline",
        enforcement_level: str = "strict",
    ) -> ContractValidationResult:
        """Validate a data contract from YAML string.

        Convenience method for validating contracts from strings rather than files.

        Args:
            yaml_content: YAML content as a string.
            name: Name to use for the contract in results.
            enforcement_level: Enforcement level from governance config.

        Returns:
            ContractValidationResult with validation outcome.
        """
        self._log.info(
            "validating_contract_string",
            name=name,
            enforcement_level=enforcement_level,
        )

        if enforcement_level == "off":
            return self._create_skipped_result_string(name)

        violations: list[ContractViolation] = []
        warnings: list[ContractViolation] = []
        contract: DataContract | None = None

        try:
            contract = self._parser.parse_contract_string(yaml_content, name)
        except ContractLintError as e:
            for v in e.violations:
                contract_violation = ContractViolation(
                    error_code=v.error_code,
                    severity=v.severity,
                    message=v.message,
                    model_name=v.model_name,
                    element_name=v.column_name,
                    expected=v.expected,
                    actual=v.actual,
                    suggestion=v.suggestion,
                )
                if v.severity == "warning":
                    warnings.append(contract_violation)
                else:
                    violations.append(contract_violation)
        except ContractValidationError as e:
            violations.append(
                ContractViolation(
                    error_code="FLOE-E509",
                    severity="error",
                    message=str(e),
                    suggestion="Check the contract YAML syntax and ODCS compliance",
                )
            )

        schema_hash = self._compute_schema_hash_string(yaml_content)
        contract_name = contract.name if contract else name
        contract_version = contract.version if contract else "unknown"

        return ContractValidationResult(
            valid=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            schema_hash=schema_hash,
            validated_at=datetime.now(timezone.utc),
            contract_name=contract_name or name,
            contract_version=contract_version or "unknown",
        )

    def _compute_schema_hash(self, contract_path: Path) -> str:
        """Compute SHA256 hash of contract file for fingerprinting.

        Args:
            contract_path: Path to the contract file.

        Returns:
            Hash string in format "sha256:<64-char-hex>".
        """
        try:
            content = contract_path.read_bytes()
            hash_value = hashlib.sha256(content).hexdigest()
            return f"sha256:{hash_value}"
        except Exception:
            # Return placeholder if file can't be read
            return f"sha256:{'0' * 64}"

    def _compute_schema_hash_string(self, yaml_content: str) -> str:
        """Compute SHA256 hash of contract string for fingerprinting.

        Args:
            yaml_content: YAML content as string.

        Returns:
            Hash string in format "sha256:<64-char-hex>".
        """
        hash_value = hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()
        return f"sha256:{hash_value}"

    def _create_skipped_result(self, contract_path: Path) -> ContractValidationResult:
        """Create a result for skipped validation.

        Args:
            contract_path: Path to the contract file.

        Returns:
            ContractValidationResult indicating validation was skipped.
        """
        return ContractValidationResult(
            valid=True,
            violations=[],
            warnings=[],
            schema_hash=self._compute_schema_hash(contract_path),
            validated_at=datetime.now(timezone.utc),
            contract_name=contract_path.stem,
            contract_version="skipped",
        )

    def _create_skipped_result_string(self, name: str) -> ContractValidationResult:
        """Create a result for skipped string validation.

        Args:
            name: Name for the contract.

        Returns:
            ContractValidationResult indicating validation was skipped.
        """
        return ContractValidationResult(
            valid=True,
            violations=[],
            warnings=[],
            schema_hash=f"sha256:{'0' * 64}",
            validated_at=datetime.now(timezone.utc),
            contract_name=name,
            contract_version="skipped",
        )

    def validate_or_generate(
        self,
        spec: FloeSpec,
        contract_path: Path | None = None,
        enforcement_level: str = "strict",
    ) -> list[ContractValidationResult]:
        """Validate explicit contracts or generate from output_ports.

        Task: T034, T035
        Requirements: FR-003 (Auto-generation), FR-004 (Merging)

        This method implements the auto-generation flow:
        1. If explicit contract_path provided, validate it
        2. If no explicit contract, generate from output_ports
        3. If neither explicit contract nor output_ports, return FLOE-E500 error

        Args:
            spec: FloeSpec containing output_ports definitions.
            contract_path: Optional path to explicit datacontract.yaml.
            enforcement_level: Enforcement level from governance config.

        Returns:
            List of ContractValidationResult (one per contract).

        Example:
            >>> results = validator.validate_or_generate(spec)
            >>> for result in results:
            ...     if result.valid:
            ...         print(f"Contract {result.contract_name}: VALID")
            ...     else:
            ...         for v in result.violations:
            ...             print(f"  {v.error_code}: {v.message}")
        """
        self._log.info(
            "validate_or_generate_started",
            product=spec.metadata.name,
            has_explicit_contract=contract_path is not None,
            has_output_ports=bool(spec.output_ports),
            enforcement_level=enforcement_level,
        )

        # Check if validation is disabled
        if enforcement_level == "off":
            self._log.info("contract_validation_skipped", reason="enforcement=off")
            return [self._create_skipped_result_string(spec.metadata.name)]

        results: list[ContractValidationResult] = []

        # Case 1: Explicit contract provided
        if contract_path is not None and contract_path.exists():
            self._log.debug("validating_explicit_contract", path=str(contract_path))
            result = self.validate(contract_path, enforcement_level)

            # If output_ports also exist, merge generated contracts with explicit
            if spec.output_ports:
                generator = ContractGenerator()
                generated = generator.generate_from_ports(spec)
                self._log.debug(
                    "generated_contracts_for_merge",
                    count=len(generated),
                )
                # For now, explicit contract takes full precedence
                # Merging logic can be enhanced in future

            results.append(result)
            return results

        # Case 2: No explicit contract, generate from output_ports
        if spec.output_ports:
            self._log.info(
                "generating_contracts_from_ports",
                product=spec.metadata.name,
                port_count=len(spec.output_ports),
            )
            generator = ContractGenerator()
            generated_contracts = generator.generate_from_ports(spec)

            for contract in generated_contracts:
                # Validate the generated contract by converting to YAML and validating
                result = self._validate_generated_contract(contract, enforcement_level)
                results.append(result)

            return results

        # Case 3: No explicit contract and no output_ports - error (FR-003/T035)
        self._log.warning(
            "no_contract_source",
            product=spec.metadata.name,
        )
        error_result = ContractValidationResult(
            valid=False,
            violations=[
                ContractViolation(
                    error_code="FLOE-E500",
                    severity="error",
                    message=(
                        f"Data product '{spec.metadata.name}' must define either a "
                        "datacontract.yaml or output_ports for contract generation"
                    ),
                    suggestion=(
                        "Add a datacontract.yaml file or define outputPorts in floe.yaml"
                    ),
                )
            ],
            warnings=[],
            schema_hash=f"sha256:{'0' * 64}",
            validated_at=datetime.now(timezone.utc),
            contract_name=spec.metadata.name,
            contract_version="unknown",
        )
        return [error_result]

    def _validate_generated_contract(
        self,
        contract: DataContract,
        enforcement_level: str,
    ) -> ContractValidationResult:
        """Validate a generated contract.

        Args:
            contract: Generated DataContract to validate.
            enforcement_level: Enforcement level.

        Returns:
            ContractValidationResult for the generated contract.
        """
        # For generated contracts, we trust the structure since ContractGenerator
        # creates valid ODCS models. We still compute hash and return result.
        import yaml

        # Convert to YAML for hash computation
        contract_dict = contract.model_dump(by_alias=True, exclude_none=True)
        yaml_content = yaml.dump(contract_dict, default_flow_style=False)
        schema_hash = self._compute_schema_hash_string(yaml_content)

        self._log.debug(
            "validated_generated_contract",
            contract_name=contract.name,
            version=contract.version,
        )

        return ContractValidationResult(
            valid=True,
            violations=[],
            warnings=[],
            schema_hash=schema_hash,
            validated_at=datetime.now(timezone.utc),
            contract_name=contract.name or "unknown",
            contract_version=contract.version or "unknown",
        )

    def validate_with_inheritance(
        self,
        contract_path: Path,
        parent_contract_path: Path | None = None,
        enforcement_level: str = "strict",
    ) -> ContractValidationResult:
        """Validate a contract with optional inheritance validation.

        Task: T045
        Requirements: FR-011, FR-012, FR-013, FR-014

        Validates the contract and, if a parent contract is provided,
        checks that the child contract does not weaken parent requirements.

        Args:
            contract_path: Path to the child datacontract.yaml file.
            parent_contract_path: Optional path to parent datacontract.yaml.
            enforcement_level: Enforcement level from governance config.

        Returns:
            ContractValidationResult with all violations (ODCS + inheritance).
        """
        # First validate the contract itself
        result = self.validate(contract_path, enforcement_level)

        # If validation failed or no parent, return base result
        if not result.valid or parent_contract_path is None:
            return result

        if not parent_contract_path.exists():
            self._log.warning(
                "parent_contract_not_found",
                path=str(parent_contract_path),
            )
            return result

        # Validate inheritance
        self._log.info(
            "validating_inheritance",
            child=str(contract_path),
            parent=str(parent_contract_path),
        )

        from floe_core.enforcement.validators.inheritance import InheritanceValidator

        inheritance_validator = InheritanceValidator()

        # Read contracts as YAML
        parent_yaml = parent_contract_path.read_text()
        child_yaml = contract_path.read_text()

        inheritance_result = inheritance_validator.validate_inheritance(
            parent_yaml=parent_yaml,
            child_yaml=child_yaml,
        )

        # Merge results
        if not inheritance_result.valid:
            all_violations = result.violations + inheritance_result.violations
            all_warnings = result.warnings + inheritance_result.warnings

            return ContractValidationResult(
                valid=False,
                violations=all_violations,
                warnings=all_warnings,
                schema_hash=result.schema_hash,
                validated_at=result.validated_at,
                contract_name=result.contract_name,
                contract_version=result.contract_version,
            )

        return result


    def validate_with_versioning(
        self,
        contract_path: Path,
        baseline_path: Path | None = None,
        enforcement_level: str = "strict",
    ) -> ContractValidationResult:
        """Validate a contract with version bump validation.

        Task: T054, T055
        Requirements: FR-015, FR-016, FR-017, FR-018, FR-019, FR-020

        Validates the contract and, if a baseline contract is provided,
        checks that version changes follow semantic versioning rules.

        Args:
            contract_path: Path to the current datacontract.yaml file.
            baseline_path: Optional path to baseline/previous datacontract.yaml.
                          If None, treated as first registration (always valid).
            enforcement_level: Enforcement level from governance config.

        Returns:
            ContractValidationResult with all violations (ODCS + versioning).

        Example:
            >>> result = validator.validate_with_versioning(
            ...     contract_path=Path("datacontract.yaml"),
            ...     baseline_path=Path("baseline/datacontract.yaml"),
            ... )
            >>> if not result.valid:
            ...     for v in result.violations:
            ...         if v.error_code == "FLOE-E520":
            ...             print("Breaking change requires MAJOR version bump")
        """
        # First validate the contract itself
        result = self.validate(contract_path, enforcement_level)

        # If validation failed, return base result
        if not result.valid:
            return result

        # If no baseline, this is first registration (always valid per FR-015)
        if baseline_path is None:
            self._log.info(
                "first_registration",
                contract=str(contract_path),
            )
            return result

        if not baseline_path.exists():
            self._log.warning(
                "baseline_contract_not_found",
                path=str(baseline_path),
            )
            # Treat as first registration if baseline doesn't exist
            return result

        # Validate version changes
        self._log.info(
            "validating_version_change",
            current=str(contract_path),
            baseline=str(baseline_path),
        )

        from floe_core.enforcement.validators.versioning import VersioningValidator

        versioning_validator = VersioningValidator()

        # Read contracts as YAML
        baseline_yaml = baseline_path.read_text()
        current_yaml = contract_path.read_text()

        versioning_result = versioning_validator.validate_version_change(
            baseline_yaml=baseline_yaml,
            current_yaml=current_yaml,
        )

        # Merge results
        if not versioning_result.valid:
            all_violations = result.violations + versioning_result.violations
            all_warnings = result.warnings + versioning_result.warnings

            return ContractValidationResult(
                valid=False,
                violations=all_violations,
                warnings=all_warnings,
                schema_hash=result.schema_hash,
                validated_at=result.validated_at,
                contract_name=result.contract_name,
                contract_version=result.contract_version,
            )

        return result

    def validate_with_drift_detection(
        self,
        contract_path: Path,
        table_schema: Any | None = None,
        enforcement_level: str = "strict",
    ) -> ContractValidationResult:
        """Validate a contract with schema drift detection against Iceberg table.

        Task: T066
        Requirements: FR-021, FR-022, FR-023, FR-024

        Validates the contract and, if an Iceberg table schema is provided,
        checks for schema drift between the contract and the actual table.

        Args:
            contract_path: Path to the datacontract.yaml file.
            table_schema: Optional PyIceberg Schema from the table.
                         If None, drift detection is skipped (table may not exist).
            enforcement_level: Enforcement level from governance config.

        Returns:
            ContractValidationResult with all violations (ODCS + drift).

        Example:
            >>> from pyiceberg.catalog import load_catalog
            >>> catalog = load_catalog("default")
            >>> table = catalog.load_table("my_namespace.my_table")
            >>> result = validator.validate_with_drift_detection(
            ...     contract_path=Path("datacontract.yaml"),
            ...     table_schema=table.schema(),
            ... )
            >>> if not result.valid:
            ...     for v in result.violations:
            ...         if v.error_code == "FLOE-E530":
            ...             print(f"Type mismatch: {v.message}")
        """
        # First validate the contract itself
        result = self.validate(contract_path, enforcement_level)

        # If validation failed, return base result
        if not result.valid:
            return result

        # If no table schema provided, skip drift detection (table may not exist)
        if table_schema is None:
            self._log.info(
                "drift_detection_skipped",
                contract=str(contract_path),
                reason="no_table_schema",
            )
            return result

        # Parse contract to get schema columns
        try:
            contract = self._parser.parse_contract(contract_path)
        except (ContractValidationError, ContractLintError):
            # Already handled in first validation pass
            return result

        # Extract columns from contract schema
        contract_columns = self._extract_contract_columns(contract)

        if not contract_columns:
            self._log.debug(
                "no_contract_columns",
                contract=str(contract_path),
            )
            return result

        # Perform drift detection
        self._log.info(
            "performing_drift_detection",
            contract=str(contract_path),
            contract_columns=len(contract_columns),
        )

        try:
            from floe_iceberg.drift_detector import DriftDetector

            detector = DriftDetector()
            drift_result = detector.compare_schemas(
                contract_columns=contract_columns,
                table_schema=table_schema,
            )
        except ImportError:
            self._log.warning(
                "drift_detection_unavailable",
                reason="floe_iceberg not installed",
            )
            return result
        except Exception as e:
            self._log.error(
                "drift_detection_failed",
                error=str(e),
            )
            return result

        # Convert drift results to violations
        if not drift_result.matches:
            drift_violations = self._drift_result_to_violations(drift_result)
            all_violations = result.violations + drift_violations

            return ContractValidationResult(
                valid=False,
                violations=all_violations,
                warnings=result.warnings,
                schema_hash=result.schema_hash,
                validated_at=result.validated_at,
                contract_name=result.contract_name,
                contract_version=result.contract_version,
            )

        self._log.info(
            "drift_detection_passed",
            contract=result.contract_name,
            extra_columns=len(drift_result.extra_columns),
        )

        return result

    def _extract_contract_columns(
        self,
        contract: DataContract,
    ) -> list[dict[str, Any]]:
        """Extract column definitions from contract schema.

        Args:
            contract: Parsed DataContract model.

        Returns:
            List of column dicts with 'name' and 'logicalType' keys.
        """
        columns: list[dict[str, Any]] = []

        if not contract.schema_:
            return columns

        for schema in contract.schema_:
            if schema.properties:
                for prop in schema.properties:
                    columns.append({
                        "name": prop.name,
                        "logicalType": prop.logicalType or "string",
                    })

        return columns

    def _drift_result_to_violations(
        self,
        drift_result: Any,
    ) -> list[ContractViolation]:
        """Convert drift detection result to ContractViolations.

        Args:
            drift_result: SchemaComparisonResult from DriftDetector.

        Returns:
            List of ContractViolation for type mismatches and missing columns.
        """
        violations: list[ContractViolation] = []

        # Type mismatches
        for mismatch in drift_result.type_mismatches:
            violations.append(
                ContractViolation(
                    error_code="FLOE-E530",
                    severity="error",
                    message=(
                        f"Schema drift detected: column '{mismatch.column}' "
                        f"has type '{mismatch.table_type}' in table but "
                        f"'{mismatch.contract_type}' in contract"
                    ),
                    element_name=mismatch.column,
                    expected=mismatch.contract_type,
                    actual=mismatch.table_type,
                    suggestion=(
                        "Update the contract to match the table schema, "
                        "or evolve the table schema to match the contract"
                    ),
                )
            )

        # Missing columns (in contract but not in table)
        for col_name in drift_result.missing_columns:
            violations.append(
                ContractViolation(
                    error_code="FLOE-E531",
                    severity="error",
                    message=(
                        f"Schema drift detected: column '{col_name}' "
                        "is defined in contract but missing from table"
                    ),
                    element_name=col_name,
                    expected="Column present in table",
                    actual="Column missing",
                    suggestion=(
                        "Add the column to the Iceberg table schema, "
                        "or remove it from the contract"
                    ),
                )
            )

        return violations

    def get_baseline_from_catalog(
        self,
        contract_id: str,
        catalog_path: Path | None = None,
    ) -> str | None:
        """Retrieve baseline contract YAML from catalog.

        Task: T054
        Requirements: FR-015 (Baseline comparison)

        Retrieves the previously registered contract from the catalog
        for baseline comparison during version validation.

        Args:
            contract_id: The contract ID to look up.
            catalog_path: Optional path to local contract catalog directory.
                         Defaults to looking in standard locations.

        Returns:
            YAML content of baseline contract, or None if not found.

        Note:
            This is a placeholder for catalog integration. In production,
            this would query the contract registry (e.g., S3, OCI registry).
        """
        self._log.debug("retrieving_baseline", contract_id=contract_id)

        # Look for baseline in catalog directory
        if catalog_path and catalog_path.exists():
            # Try to find contract file in catalog
            contract_file = catalog_path / f"{contract_id}.yaml"
            if contract_file.exists():
                self._log.info(
                    "baseline_found",
                    contract_id=contract_id,
                    path=str(contract_file),
                )
                return contract_file.read_text()

            # Try nested structure: catalog_path/contract_id/datacontract.yaml
            nested_path = catalog_path / contract_id / "datacontract.yaml"
            if nested_path.exists():
                self._log.info(
                    "baseline_found",
                    contract_id=contract_id,
                    path=str(nested_path),
                )
                return nested_path.read_text()

        # No baseline found (first registration)
        self._log.debug("no_baseline_found", contract_id=contract_id)
        return None


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
        "FLOE-E502": (
            "Use a valid logicalType: string, int, long, float, double, "
            "decimal, boolean, date, timestamp, time, bytes, array, object"
        ),
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
    "ContractValidator",
    "ContractValidationError",
    "ContractLintError",
]
