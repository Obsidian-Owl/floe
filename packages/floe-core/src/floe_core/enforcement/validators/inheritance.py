"""Contract inheritance validation for ODCS v3 data contracts.

This module provides the InheritanceValidator class that validates child
contracts do not weaken parent contract requirements.

Task: T039, T040, T041, T042, T043, T044
Requirements: FR-011 (Three-tier inheritance), FR-012 (SLA weakening),
              FR-013 (Classification weakening), FR-014 (FLOE-E510 error)

Three-tier inheritance hierarchy:
- Enterprise contracts (organization-wide requirements)
- Domain contracts (business domain requirements)
- Product contracts (data product requirements)

Key rule: Child contracts can STRENGTHEN but NOT WEAKEN parent requirements.

Example:
    >>> from floe_core.enforcement.validators.inheritance import InheritanceValidator
    >>> validator = InheritanceValidator()
    >>> result = validator.validate_inheritance(
    ...     parent_yaml=enterprise_contract,
    ...     child_yaml=product_contract,
    ... )
    >>> if not result.valid:
    ...     for v in result.violations:
    ...         print(f"{v.error_code}: {v.message}")
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

import structlog

from floe_core.enforcement.validators.data_contracts import ContractParser
from floe_core.schemas.data_contract import (
    ContractValidationResult,
    ContractViolation,
    DataContract,
)


class CycleDetectionResult:
    """Result of circular dependency detection.

    Task: T044b
    Requirements: FR-011

    Attributes:
        has_cycle: True if a circular dependency was detected.
        cycle_path: List of contract IDs forming the cycle, or None if no cycle.
    """

    def __init__(
        self,
        has_cycle: bool,
        cycle_path: list[str] | None = None,
    ) -> None:
        """Initialize CycleDetectionResult.

        Args:
            has_cycle: Whether a cycle was detected.
            cycle_path: Path of contract IDs forming the cycle.
        """
        self.has_cycle = has_cycle
        self.cycle_path = cycle_path


logger = structlog.get_logger(__name__)

# Classification hierarchy (higher index = more restrictive)
# More restrictive classifications cannot be weakened to less restrictive
CLASSIFICATION_HIERARCHY = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
    "pii": 4,  # PII is most restrictive
}


def parse_iso8601_duration(duration: str) -> timedelta | None:
    """Parse ISO 8601 duration string to timedelta.

    Supports common formats: PT1H, PT6H, PT12H, PT24H, P1D, etc.

    Args:
        duration: ISO 8601 duration string (e.g., "PT6H", "P1D").

    Returns:
        timedelta object, or None if parsing fails.
    """
    if not duration:
        return None

    # Simple regex for ISO 8601 durations
    # P[n]Y[n]M[n]DT[n]H[n]M[n]S
    pattern = r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$"
    match = re.match(pattern, duration.upper())

    if not match:
        return None

    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def parse_percentage(value: str | float | int) -> float | None:
    """Parse percentage value to float.

    Args:
        value: Percentage as string ("99.9%") or number (99.9).

    Returns:
        Float percentage value, or None if parsing fails.
    """
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        # Remove % sign and parse
        cleaned = value.strip().rstrip("%")
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


class InheritanceValidator:
    """Validator for contract inheritance rules.

    Validates that child contracts do not weaken parent contract requirements:
    - SLA properties (freshness, availability, quality)
    - Field classifications (e.g., PII cannot be downgraded to public)

    Task: T039
    Requirements: FR-011, FR-012, FR-013, FR-014

    Attributes:
        _parser: ContractParser for loading contracts from YAML.
        _log: Structured logger for this validator instance.

    Example:
        >>> validator = InheritanceValidator()
        >>> result = validator.validate_inheritance(
        ...     parent_yaml=enterprise_contract,
        ...     child_yaml=product_contract,
        ... )
    """

    def __init__(self) -> None:
        """Initialize InheritanceValidator."""
        self._parser = ContractParser()
        self._log = logger.bind(component="InheritanceValidator")
        self._log.debug("inheritance_validator_initialized")

    def validate_inheritance(
        self,
        parent_yaml: str,
        child_yaml: str,
    ) -> ContractValidationResult:
        """Validate child contract against parent contract.

        Checks that child contract does not weaken parent requirements:
        - SLA properties must be equal or stronger (FR-012)
        - Classifications must be equal or stronger (FR-013)

        Args:
            parent_yaml: YAML content of parent contract.
            child_yaml: YAML content of child contract.

        Returns:
            ContractValidationResult with any violations found.
        """
        self._log.info("validating_inheritance")

        violations: list[ContractViolation] = []
        warnings: list[ContractViolation] = []

        # Parse contracts
        try:
            parent = self._parser.parse_contract_string(parent_yaml, "parent")
            child = self._parser.parse_contract_string(child_yaml, "child")
        except Exception as e:
            self._log.error("contract_parse_error", error=str(e))
            from datetime import datetime, timezone

            return ContractValidationResult(
                valid=False,
                violations=[
                    ContractViolation(
                        error_code="FLOE-E509",
                        severity="error",
                        message=f"Failed to parse contract: {e}",
                        suggestion="Check contract YAML syntax",
                    )
                ],
                warnings=[],
                schema_hash="sha256:" + "0" * 64,
                validated_at=datetime.now(timezone.utc),
                contract_name="unknown",
                contract_version="unknown",
            )

        # Validate SLA properties (FR-012)
        sla_violations = self._validate_sla_inheritance(parent, child)
        violations.extend(sla_violations)

        # Validate classifications (FR-013)
        classification_violations = self._validate_classification_inheritance(parent, child)
        violations.extend(classification_violations)

        # Build result
        from datetime import datetime, timezone

        result = ContractValidationResult(
            valid=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            schema_hash="sha256:" + "0" * 64,
            validated_at=datetime.now(timezone.utc),
            contract_name=child.name or "unknown",
            contract_version=child.version or "unknown",
        )

        if result.valid:
            self._log.info(
                "inheritance_validation_passed",
                parent=parent.name,
                child=child.name,
            )
        else:
            self._log.warning(
                "inheritance_validation_failed",
                parent=parent.name,
                child=child.name,
                violations=len(violations),
            )

        return result

    def _validate_sla_inheritance(
        self,
        parent: DataContract,
        child: DataContract,
    ) -> list[ContractViolation]:
        """Validate SLA properties are not weakened.

        Task: T040
        Requirements: FR-012, FR-014

        SLA rules:
        - Freshness: child duration <= parent duration (fresher data is stronger)
        - Availability: child percentage >= parent percentage (more available is stronger)
        - Completeness: child percentage >= parent percentage (more complete is stronger)
        - Quality: child percentage >= parent percentage

        Args:
            parent: Parent contract.
            child: Child contract.

        Returns:
            List of violations for SLA weakening.
        """
        violations: list[ContractViolation] = []

        # Get parent SLA properties
        parent_slas = self._get_sla_dict(parent)
        child_slas = self._get_sla_dict(child)

        self._log.debug(
            "comparing_slas",
            parent_slas=list(parent_slas.keys()),
            child_slas=list(child_slas.keys()),
        )

        # Check each parent SLA
        for sla_name, parent_value in parent_slas.items():
            if sla_name not in child_slas:
                # Missing required SLA
                violations.append(
                    ContractViolation(
                        error_code="FLOE-E510",
                        severity="error",
                        message=(
                            f"Child contract missing required SLA property '{sla_name}'. "
                            f"Parent requires: {parent_value}"
                        ),
                        element_name=sla_name,
                        expected=str(parent_value),
                        actual="missing",
                        suggestion=f"Add '{sla_name}' SLA property to child contract",
                    )
                )
                continue

            child_value = child_slas[sla_name]

            # Compare based on SLA type
            if sla_name == "freshness":
                # Freshness: smaller duration = stronger (fresher data)
                weakened = self._is_freshness_weakened(parent_value, child_value)
            else:
                # Availability, completeness, quality: higher = stronger
                weakened = self._is_percentage_weakened(parent_value, child_value)

            if weakened:
                violations.append(
                    ContractViolation(
                        error_code="FLOE-E510",
                        severity="error",
                        message=(
                            f"Child contract weakens '{sla_name}' SLA. "
                            f"Parent requires {parent_value}, child specifies {child_value}"
                        ),
                        element_name=sla_name,
                        expected=str(parent_value),
                        actual=str(child_value),
                        suggestion=(
                            f"Strengthen '{sla_name}' to at least match parent: {parent_value}"
                        ),
                    )
                )

        return violations

    def _get_sla_dict(self, contract: DataContract) -> dict[str, Any]:
        """Extract SLA properties as a dictionary.

        Args:
            contract: DataContract to extract SLAs from.

        Returns:
            Dictionary mapping SLA property names to values.
        """
        if not contract.slaProperties:
            return {}

        return {
            sla.property: sla.value
            for sla in contract.slaProperties
            if sla.property and sla.value is not None
        }

    def _is_freshness_weakened(
        self,
        parent_value: Any,
        child_value: Any,
    ) -> bool:
        """Check if freshness SLA is weakened.

        Freshness uses ISO 8601 durations. Smaller = stronger (fresher data).
        PT1H (1 hour) is stronger than PT6H (6 hours).

        Args:
            parent_value: Parent freshness value (e.g., "PT6H").
            child_value: Child freshness value (e.g., "PT12H").

        Returns:
            True if child is weaker than parent.
        """
        parent_duration = parse_iso8601_duration(str(parent_value))
        child_duration = parse_iso8601_duration(str(child_value))

        if parent_duration is None or child_duration is None:
            # Can't compare, assume not weakened
            self._log.warning(
                "freshness_parse_failed",
                parent=parent_value,
                child=child_value,
            )
            return False

        # Larger duration = weaker (data can be older)
        return child_duration > parent_duration

    def _is_percentage_weakened(
        self,
        parent_value: Any,
        child_value: Any,
    ) -> bool:
        """Check if percentage-based SLA is weakened.

        Higher percentage = stronger for availability, completeness, quality.

        Args:
            parent_value: Parent percentage (e.g., "99.9%" or 99.9).
            child_value: Child percentage (e.g., "99%" or 99).

        Returns:
            True if child is weaker than parent.
        """
        parent_pct = parse_percentage(parent_value)
        child_pct = parse_percentage(child_value)

        if parent_pct is None or child_pct is None:
            self._log.warning(
                "percentage_parse_failed",
                parent=parent_value,
                child=child_value,
            )
            return False

        # Lower percentage = weaker
        return child_pct < parent_pct

    def _validate_classification_inheritance(
        self,
        parent: DataContract,
        child: DataContract,
    ) -> list[ContractViolation]:
        """Validate field classifications are not weakened.

        Task: T041
        Requirements: FR-013

        Classification rules:
        - PII cannot be downgraded (e.g., pii -> public is forbidden)
        - More restrictive classifications can be added
        - Equal classifications are allowed

        Args:
            parent: Parent contract.
            child: Child contract.

        Returns:
            List of violations for classification weakening.
        """
        violations: list[ContractViolation] = []

        # Get parent field classifications
        parent_classifications = self._get_field_classifications(parent)
        child_classifications = self._get_field_classifications(child)

        self._log.debug(
            "comparing_classifications",
            parent_fields=list(parent_classifications.keys()),
            child_fields=list(child_classifications.keys()),
        )

        # Check each parent-classified field
        for field_key, parent_class in parent_classifications.items():
            parent_level = CLASSIFICATION_HIERARCHY.get(parent_class.lower(), -1)

            if parent_level < 0:
                # Unknown classification, skip
                continue

            child_class = child_classifications.get(field_key)

            if child_class is None:
                # Field exists in parent with classification but not in child
                # This is weakening - classification removed
                violations.append(
                    ContractViolation(
                        error_code="FLOE-E511",
                        severity="error",
                        message=(
                            f"Child contract removes classification from field '{field_key}'. "
                            f"Parent requires classification: {parent_class}"
                        ),
                        element_name=field_key,
                        expected=parent_class,
                        actual="none",
                        suggestion=(f"Add classification '{parent_class}' to field '{field_key}'"),
                    )
                )
                continue

            child_level = CLASSIFICATION_HIERARCHY.get(child_class.lower(), -1)

            if child_level < 0:
                # Unknown child classification, skip
                continue

            if child_level < parent_level:
                # Child classification is weaker
                violations.append(
                    ContractViolation(
                        error_code="FLOE-E511",
                        severity="error",
                        message=(
                            f"Child contract weakens classification for field '{field_key}'. "
                            f"Parent requires '{parent_class}', child specifies '{child_class}'"
                        ),
                        element_name=field_key,
                        expected=parent_class,
                        actual=child_class,
                        suggestion=(
                            f"Use classification '{parent_class}' or stronger for '{field_key}'"
                        ),
                    )
                )

        return violations

    def _get_field_classifications(
        self,
        contract: DataContract,
    ) -> dict[str, str]:
        """Extract field classifications from contract schema.

        Args:
            contract: DataContract to extract classifications from.

        Returns:
            Dictionary mapping "schema_name.field_name" to classification.
        """
        classifications: dict[str, str] = {}

        if not contract.schema_:
            return classifications

        for schema_obj in contract.schema_:
            schema_name = schema_obj.name or "unknown"

            if not schema_obj.properties:
                continue

            for prop in schema_obj.properties:
                if prop.classification:
                    field_key = f"{schema_name}.{prop.name}"
                    classifications[field_key] = prop.classification

        return classifications

    def detect_circular_dependencies(
        self,
        contract_id: str,
        contracts: dict[str, dict[str, Any]],
    ) -> CycleDetectionResult:
        """Detect circular dependencies in contract inheritance chain.

        Task: T044b
        Requirements: FR-011

        Uses depth-first search to detect cycles in the inheritance graph.

        Args:
            contract_id: ID of the contract to check for cycles.
            contracts: Dictionary mapping contract IDs to contract info.
                Each entry should have:
                - "id": Contract ID
                - "inherits_from": Parent contract ID or None
                - "yaml": Contract YAML content (optional)

        Returns:
            CycleDetectionResult indicating if a cycle was found and the path.

        Example:
            >>> contracts = {
            ...     "a": {"id": "a", "inherits_from": "b"},
            ...     "b": {"id": "b", "inherits_from": "a"},
            ... }
            >>> result = validator.detect_circular_dependencies("a", contracts)
            >>> result.has_cycle
            True
            >>> result.cycle_path
            ['a', 'b', 'a']
        """
        self._log.debug(
            "detecting_circular_dependencies",
            contract_id=contract_id,
            total_contracts=len(contracts),
        )

        # Track visited nodes and current recursion stack
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(current_id: str) -> CycleDetectionResult:
            """Depth-first search for cycle detection."""
            # Mark current node as visited and add to recursion stack
            visited.add(current_id)
            rec_stack.add(current_id)
            path.append(current_id)

            # Get parent contract
            contract_info = contracts.get(current_id)
            if not contract_info:
                # Contract not found, no cycle from here
                path.pop()
                rec_stack.remove(current_id)
                return CycleDetectionResult(has_cycle=False)

            parent_id = contract_info.get("inherits_from")

            if parent_id:
                # Check for self-reference
                if parent_id == current_id:
                    cycle_path = [current_id, current_id]
                    self._log.warning(
                        "self_reference_detected",
                        contract_id=current_id,
                    )
                    return CycleDetectionResult(has_cycle=True, cycle_path=cycle_path)

                # Check if parent is in current recursion stack (cycle detected)
                if parent_id in rec_stack:
                    # Find the cycle path
                    cycle_start_idx = path.index(parent_id)
                    cycle_path = path[cycle_start_idx:] + [parent_id]
                    self._log.warning(
                        "circular_dependency_detected",
                        cycle_path=cycle_path,
                    )
                    return CycleDetectionResult(has_cycle=True, cycle_path=cycle_path)

                # If parent not visited, recurse
                if parent_id not in visited:
                    result = dfs(parent_id)
                    if result.has_cycle:
                        return result

            # Pop from path and recursion stack
            path.pop()
            rec_stack.remove(current_id)

            return CycleDetectionResult(has_cycle=False)

        # Start DFS from the given contract
        result = dfs(contract_id)

        if not result.has_cycle:
            self._log.debug(
                "no_circular_dependency",
                contract_id=contract_id,
            )

        return result

    def cycle_to_violation(
        self,
        cycle_result: CycleDetectionResult,
    ) -> ContractViolation:
        """Convert a cycle detection result to a ContractViolation.

        Task: T044b
        Requirements: FR-011

        Args:
            cycle_result: Result from detect_circular_dependencies.

        Returns:
            ContractViolation with error code FLOE-E512.
        """
        if not cycle_result.has_cycle or not cycle_result.cycle_path:
            raise ValueError("Cannot create violation for non-cycle result")

        cycle_str = " -> ".join(cycle_result.cycle_path)

        return ContractViolation(
            error_code="FLOE-E512",
            severity="error",
            message=f"Circular contract dependency detected: {cycle_str}",
            element_name=cycle_result.cycle_path[0],
            expected="acyclic inheritance chain",
            actual=cycle_str,
            suggestion="Remove circular dependency in contract inheritance chain",
        )


__all__ = [
    "InheritanceValidator",
    "CycleDetectionResult",
    "parse_iso8601_duration",
    "parse_percentage",
    "CLASSIFICATION_HIERARCHY",
]
