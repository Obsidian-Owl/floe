"""Unit tests for quality validation and gate result models.

Tests the Pydantic models in quality_validation.py for validation,
serialization, and edge cases. Covers compile-time validation results
and quality gate validation results.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.schemas.quality_validation import GateResult, ValidationResult


class TestValidationResult:
    """Test ValidationResult Pydantic model."""

    @pytest.mark.requirement("005B-FR-015")
    def test_validation_result_success_minimal(self) -> None:
        """Test ValidationResult with successful validation."""
        result = ValidationResult(success=True)
        assert result.success is True
        assert result.errors == []
        assert result.warnings == []

    @pytest.mark.requirement("005B-FR-015")
    def test_validation_result_success_with_warnings(self) -> None:
        """Test ValidationResult with success but warnings."""
        result = ValidationResult(
            success=True,
            warnings=["No quality checks defined for model 'stg_customers'"],
        )
        assert result.success is True
        assert result.errors == []
        assert len(result.warnings) == 1
        assert "No quality checks" in result.warnings[0]

    @pytest.mark.requirement("005B-FR-015")
    def test_validation_result_failure_minimal(self) -> None:
        """Test ValidationResult with validation failure."""
        result = ValidationResult(
            success=False,
            errors=["Invalid quality provider: 'unknown'"],
        )
        assert result.success is False
        assert len(result.errors) == 1
        assert "Invalid quality provider" in result.errors[0]
        assert result.warnings == []

    @pytest.mark.requirement("005B-FR-015")
    def test_validation_result_failure_full(self) -> None:
        """Test ValidationResult with errors and warnings."""
        result = ValidationResult(
            success=False,
            errors=[
                "Invalid quality provider: 'unknown'",
                "Missing required field: 'dimension_weights'",
            ],
            warnings=[
                "No quality checks defined for model 'stg_customers'",
                "Timeout value is unusually high: 3600 seconds",
            ],
        )
        assert result.success is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 2

    @pytest.mark.requirement("005B-FR-015")
    def test_validation_result_multiple_errors(self) -> None:
        """Test ValidationResult with multiple errors."""
        errors = [
            "Error 1",
            "Error 2",
            "Error 3",
        ]
        result = ValidationResult(success=False, errors=errors)
        assert result.success is False
        assert result.errors == errors

    @pytest.mark.requirement("005B-FR-015")
    def test_validation_result_multiple_warnings(self) -> None:
        """Test ValidationResult with multiple warnings."""
        warnings = [
            "Warning 1",
            "Warning 2",
            "Warning 3",
        ]
        result = ValidationResult(success=True, warnings=warnings)
        assert result.success is True
        assert result.warnings == warnings

    @pytest.mark.requirement("005B-FR-015")
    def test_validation_result_frozen(self) -> None:
        """Test ValidationResult is immutable."""
        result = ValidationResult(success=True)
        with pytest.raises(ValidationError):
            result.success = False  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-015")
    def test_validation_result_extra_fields_forbidden(self) -> None:
        """Test ValidationResult rejects extra fields."""
        with pytest.raises(ValidationError, match="extra_field"):
            ValidationResult(  # type: ignore[call-arg, arg-type]
                success=True,
                extra_field="not_allowed",  # type: ignore[arg-type]
            )


class TestGateResult:
    """Test GateResult Pydantic model."""

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_passed_minimal(self) -> None:
        """Test GateResult with passed gate."""
        result = GateResult(
            passed=True,
            tier="gold",
            coverage_actual=100.0,
            coverage_required=100.0,
        )
        assert result.passed is True
        assert result.tier == "gold"
        assert result.coverage_actual == 100.0
        assert result.coverage_required == 100.0
        assert result.missing_tests == []
        assert result.violations == []

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_failed_minimal(self) -> None:
        """Test GateResult with failed gate."""
        result = GateResult(
            passed=False,
            tier="gold",
            coverage_actual=85.0,
            coverage_required=100.0,
        )
        assert result.passed is False
        assert result.tier == "gold"
        assert result.coverage_actual == 85.0
        assert result.coverage_required == 100.0

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_failed_full(self) -> None:
        """Test GateResult with all failure details."""
        result = GateResult(
            passed=False,
            tier="gold",
            coverage_actual=85.0,
            coverage_required=100.0,
            missing_tests=["relationships"],
            violations=[
                "Coverage 85.0% is below gold tier minimum of 100%",
                "Missing required test type: relationships",
            ],
        )
        assert result.passed is False
        assert result.tier == "gold"
        assert result.coverage_actual == 85.0
        assert result.coverage_required == 100.0
        assert result.missing_tests == ["relationships"]
        assert len(result.violations) == 2

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_tier_bronze(self) -> None:
        """Test GateResult with bronze tier."""
        result = GateResult(
            passed=True,
            tier="bronze",
            coverage_actual=50.0,
            coverage_required=50.0,
        )
        assert result.tier == "bronze"

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_tier_silver(self) -> None:
        """Test GateResult with silver tier."""
        result = GateResult(
            passed=True,
            tier="silver",
            coverage_actual=80.0,
            coverage_required=80.0,
        )
        assert result.tier == "silver"

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_tier_gold(self) -> None:
        """Test GateResult with gold tier."""
        result = GateResult(
            passed=True,
            tier="gold",
            coverage_actual=100.0,
            coverage_required=100.0,
        )
        assert result.tier == "gold"

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_tier_invalid(self) -> None:
        """Test GateResult rejects invalid tier."""
        with pytest.raises(ValidationError, match="tier"):
            GateResult(  # type: ignore[call-arg, arg-type]
                passed=True,
                tier="platinum",  # type: ignore[arg-type]  # Invalid tier
                coverage_actual=100.0,
                coverage_required=100.0,
            )

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_coverage_boundary(self) -> None:
        """Test GateResult coverage percentage boundaries."""
        result_min = GateResult(
            passed=True,
            tier="bronze",
            coverage_actual=0.0,
            coverage_required=0.0,
        )
        assert result_min.coverage_actual == 0.0

        result_max = GateResult(
            passed=True,
            tier="gold",
            coverage_actual=100.0,
            coverage_required=100.0,
        )
        assert result_max.coverage_actual == 100.0

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_coverage_invalid(self) -> None:
        """Test GateResult rejects invalid coverage percentage."""
        with pytest.raises(ValidationError, match="coverage_actual"):
            GateResult(
                passed=True,
                tier="gold",
                coverage_actual=-1.0,
                coverage_required=100.0,
            )

        with pytest.raises(ValidationError, match="coverage_actual"):
            GateResult(
                passed=True,
                tier="gold",
                coverage_actual=101.0,
                coverage_required=100.0,
            )

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_multiple_missing_tests(self) -> None:
        """Test GateResult with multiple missing tests."""
        missing = ["relationships", "accepted_values", "unique"]
        result = GateResult(
            passed=False,
            tier="gold",
            coverage_actual=85.0,
            coverage_required=100.0,
            missing_tests=missing,
        )
        assert result.missing_tests == missing

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_multiple_violations(self) -> None:
        """Test GateResult with multiple violations."""
        violations = [
            "Coverage 85.0% is below gold tier minimum of 100%",
            "Missing required test type: relationships",
            "Missing required test type: accepted_values",
        ]
        result = GateResult(
            passed=False,
            tier="gold",
            coverage_actual=85.0,
            coverage_required=100.0,
            violations=violations,
        )
        assert result.violations == violations

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_frozen(self) -> None:
        """Test GateResult is immutable."""
        result = GateResult(
            passed=True,
            tier="gold",
            coverage_actual=100.0,
            coverage_required=100.0,
        )
        with pytest.raises(ValidationError):
            result.passed = False  # type: ignore[misc]

    @pytest.mark.requirement("005B-FR-016")
    def test_gate_result_extra_fields_forbidden(self) -> None:
        """Test GateResult rejects extra fields."""
        with pytest.raises(ValidationError, match="extra_field"):
            GateResult(  # type: ignore[call-arg, arg-type]
                passed=True,
                tier="gold",
                coverage_actual=100.0,
                coverage_required=100.0,
                extra_field="not_allowed",  # type: ignore[arg-type]
            )
