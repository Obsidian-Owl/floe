"""Unit tests for quality gate compiler integration.

Tests the quality_compiler module that wires quality gate validation
into the compilation pipeline with FLOE-DQ103 and FLOE-DQ104 errors.

T076: Wire quality gate validation into compiler
"""

from __future__ import annotations

import pytest

from floe_core.compilation.errors import CompilationException
from floe_core.compilation.quality_compiler import (
    raise_if_quality_violations,
    validate_quality_gates_for_models,
)
from floe_core.compilation.stages import CompilationStage
from floe_core.schemas.quality_config import GateTier, QualityConfig, QualityGates


class TestValidateQualityGatesForModels:
    """Test validate_quality_gates_for_models function."""

    @pytest.mark.requirement("005B-FR-021", "005B-FR-043")
    def test_no_errors_when_gates_pass(self) -> None:
        """Test no errors when all models meet gate requirements."""
        models = [
            {
                "name": "gold_customers",
                "tier": "gold",
                "columns": [
                    {"name": "id", "tests": ["not_null", "unique"]},
                    {"name": "email", "tests": ["not_null"]},
                ],
            },
        ]
        config = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                gold=GateTier(
                    min_test_coverage=100, required_tests=["not_null", "unique"]
                ),
            ),
        )
        errors = validate_quality_gates_for_models(models, config)
        assert len(errors) == 0

    @pytest.mark.requirement("005B-FR-021", "005B-FR-043")
    def test_dq103_error_on_coverage_violation(self) -> None:
        """Test FLOE-DQ103 error when coverage is below minimum."""
        models = [
            {
                "name": "gold_customers",
                "tier": "gold",
                "columns": [
                    {"name": "id", "tests": ["not_null"]},
                    {"name": "email", "tests": []},
                ],
            },
        ]
        config = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                gold=GateTier(min_test_coverage=100),
            ),
        )
        errors = validate_quality_gates_for_models(models, config)
        assert len(errors) == 1
        assert errors[0].code == "FLOE-DQ103"
        assert errors[0].stage == CompilationStage.VALIDATE
        assert "gold_customers" in errors[0].message

    @pytest.mark.requirement("005B-FR-022", "005B-FR-044")
    def test_dq104_error_on_missing_tests(self) -> None:
        """Test FLOE-DQ104 error when required tests are missing."""
        models = [
            {
                "name": "silver_orders",
                "tier": "silver",
                "columns": [
                    {"name": "id", "tests": ["not_null"]},
                ],
            },
        ]
        config = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                silver=GateTier(
                    min_test_coverage=100, required_tests=["not_null", "unique"]
                ),
            ),
        )
        errors = validate_quality_gates_for_models(models, config)
        assert len(errors) == 1
        assert errors[0].code == "FLOE-DQ104"
        assert "unique" in errors[0].context["missing_tests"]

    @pytest.mark.requirement("005B-FR-021", "005B-FR-022")
    def test_multiple_errors_from_one_model(self) -> None:
        """Test multiple errors from a single model."""
        models = [
            {
                "name": "gold_customers",
                "tier": "gold",
                "columns": [
                    {"name": "id", "tests": []},
                    {"name": "email", "tests": []},
                ],
            },
        ]
        config = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                gold=GateTier(
                    min_test_coverage=100, required_tests=["not_null", "unique"]
                ),
            ),
        )
        errors = validate_quality_gates_for_models(models, config)
        assert len(errors) == 2
        codes = {e.code for e in errors}
        assert "FLOE-DQ103" in codes
        assert "FLOE-DQ104" in codes

    @pytest.mark.requirement("005B-FR-021")
    def test_multiple_models_with_violations(self) -> None:
        """Test errors from multiple models."""
        models = [
            {
                "name": "gold_customers",
                "tier": "gold",
                "columns": [{"name": "id", "tests": []}],
            },
            {
                "name": "gold_orders",
                "tier": "gold",
                "columns": [{"name": "id", "tests": []}],
            },
        ]
        config = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(
                gold=GateTier(min_test_coverage=100),
            ),
        )
        errors = validate_quality_gates_for_models(models, config)
        assert len(errors) == 2

    @pytest.mark.requirement("005B-FR-021")
    def test_none_config_returns_no_errors(self) -> None:
        """Test None config returns empty error list."""
        models = [{"name": "model", "tier": "gold", "columns": []}]
        errors = validate_quality_gates_for_models(models, None)
        assert errors == []

    @pytest.mark.requirement("005B-FR-021")
    def test_disabled_config_returns_no_errors(self) -> None:
        """Test disabled config returns empty error list."""
        models = [
            {
                "name": "gold_customers",
                "tier": "gold",
                "columns": [{"name": "id", "tests": []}],
            },
        ]
        config = QualityConfig(
            provider="great_expectations",
            enabled=False,
            quality_gates=QualityGates(gold=GateTier(min_test_coverage=100)),
        )
        errors = validate_quality_gates_for_models(models, config)
        assert errors == []

    @pytest.mark.requirement("005B-FR-021")
    def test_bronze_tier_default_passes(self) -> None:
        """Test bronze tier with default (0%) coverage passes."""
        models = [
            {
                "name": "bronze_raw",
                "tier": "bronze",
                "columns": [{"name": "data", "tests": []}],
            },
        ]
        config = QualityConfig(
            provider="great_expectations",
            quality_gates=QualityGates(),
        )
        errors = validate_quality_gates_for_models(models, config)
        assert len(errors) == 0


class TestRaiseIfQualityViolations:
    """Test raise_if_quality_violations function."""

    @pytest.mark.requirement("005B-FR-021")
    def test_no_exception_when_no_errors(self) -> None:
        """Test no exception when error list is empty."""
        raise_if_quality_violations([])

    @pytest.mark.requirement("005B-FR-021", "005B-FR-043", "005B-FR-044")
    def test_raises_compilation_exception_with_errors(self) -> None:
        """Test raises CompilationException when errors exist."""
        from floe_core.compilation.errors import CompilationError

        errors = [
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="FLOE-DQ103",
                message="Coverage violation",
                suggestion="Add more tests",
                context={},
            ),
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="FLOE-DQ104",
                message="Missing tests",
                suggestion="Add required tests",
                context={},
            ),
        ]
        with pytest.raises(CompilationException) as exc_info:
            raise_if_quality_violations(errors)
        assert exc_info.value.error.code == "FLOE-DQ100"
        assert "1 coverage violations" in exc_info.value.error.message
        assert "1 missing test violations" in exc_info.value.error.message

    @pytest.mark.requirement("005B-FR-021")
    def test_exception_context_has_counts(self) -> None:
        """Test exception context includes violation counts."""
        from floe_core.compilation.errors import CompilationError

        errors = [
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="FLOE-DQ103",
                message="Coverage 1",
                suggestion="",
                context={},
            ),
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="FLOE-DQ103",
                message="Coverage 2",
                suggestion="",
                context={},
            ),
            CompilationError(
                stage=CompilationStage.VALIDATE,
                code="FLOE-DQ104",
                message="Missing",
                suggestion="",
                context={},
            ),
        ]
        with pytest.raises(CompilationException) as exc_info:
            raise_if_quality_violations(errors)
        ctx = exc_info.value.error.context
        assert ctx["coverage_violations"] == 2
        assert ctx["missing_test_violations"] == 1
        assert ctx["total_violations"] == 3
