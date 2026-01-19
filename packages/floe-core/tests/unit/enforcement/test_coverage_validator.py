"""Unit tests for CoverageValidator - TDD tests written first.

These tests define the expected behavior for CoverageValidator before implementation.
They verify test coverage calculation and threshold enforcement per layer.

Coverage Formula: (columns_with_at_least_one_test / total_columns) * 100

Task: T047, T048, T049, T050, T051, T052
Requirements: FR-004 (Coverage Calculation), FR-012 (Layer Thresholds), US4 (Coverage Enforcement)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from floe_core.enforcement.result import Violation


def _create_model_node(
    name: str,
    columns: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Helper to create a model node for testing.

    Args:
        name: Model name (e.g., "bronze_orders").
        columns: Column definitions with optional metadata.

    Returns:
        Model node dictionary matching dbt manifest structure.
    """
    node: dict[str, Any] = {
        "name": name,
        "resource_type": "model",
        "unique_id": f"model.test.{name}",
        "columns": columns or {},
    }
    return node


def _create_test_node(
    model_name: str,
    column_name: str | None = None,
    test_type: str = "not_null",
) -> dict[str, Any]:
    """Helper to create a test node for testing.

    Args:
        model_name: The model this test applies to.
        column_name: The column this test applies to (None for model-level tests).
        test_type: The test type (not_null, unique, etc.).

    Returns:
        Test node dictionary matching dbt manifest structure.
    """
    test_name = f"{test_type}_{model_name}"
    if column_name:
        test_name = f"{test_type}_{model_name}_{column_name}"

    return {
        "name": test_name,
        "resource_type": "test",
        "unique_id": f"test.test.{test_name}",
        "test_metadata": {
            "name": test_type,
        },
        "attached_node": f"model.test.{model_name}",
        "column_name": column_name,
    }


class TestDbtManifestColumnParsing:
    """Tests for dbt manifest column extraction (T047)."""

    @pytest.mark.requirement("3A-US4-FR004")
    def test_extracts_columns_from_model_node(self) -> None:
        """CoverageValidator MUST extract columns from model nodes."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            columns={
                "id": {"name": "id", "description": "Primary key"},
                "customer_id": {"name": "customer_id", "description": "FK"},
                "amount": {"name": "amount", "description": "Order total"},
            },
        )

        columns = validator._extract_columns(model)
        assert len(columns) == 3
        assert "id" in columns
        assert "customer_id" in columns
        assert "amount" in columns

    @pytest.mark.requirement("3A-US4-FR004")
    def test_extracts_empty_columns_when_none_defined(self) -> None:
        """CoverageValidator MUST handle models with no columns."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        model = _create_model_node(name="bronze_orders", columns=None)
        columns = validator._extract_columns(model)
        assert columns == {}

    @pytest.mark.requirement("3A-US4-FR004")
    def test_extracts_columns_with_empty_dict(self) -> None:
        """CoverageValidator MUST handle models with empty columns dict."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        model = _create_model_node(name="bronze_orders", columns={})
        columns = validator._extract_columns(model)
        assert columns == {}


class TestDbtManifestTestParsing:
    """Tests for dbt manifest test extraction (T048)."""

    @pytest.mark.requirement("3A-US4-FR004")
    def test_extracts_tests_for_model(self) -> None:
        """CoverageValidator MUST extract tests attached to a model."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        tests = [
            _create_test_node("bronze_orders", "id", "not_null"),
            _create_test_node("bronze_orders", "id", "unique"),
            _create_test_node("bronze_orders", "customer_id", "not_null"),
            _create_test_node("silver_customers", "email", "unique"),  # Different model
        ]

        model_tests = validator._extract_tests_for_model(
            model_unique_id="model.test.bronze_orders",
            tests=tests,
        )

        # Should only include tests for bronze_orders (3 tests, 2 columns)
        assert len(model_tests) == 3

    @pytest.mark.requirement("3A-US4-FR004")
    def test_maps_tests_to_columns(self) -> None:
        """CoverageValidator MUST map tests to their respective columns."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        tests = [
            _create_test_node("bronze_orders", "id", "not_null"),
            _create_test_node("bronze_orders", "id", "unique"),
            _create_test_node("bronze_orders", "customer_id", "not_null"),
        ]

        column_tests = validator._map_tests_to_columns(tests)

        # id has 2 tests, customer_id has 1 test
        assert column_tests.get("id", 0) >= 1
        assert column_tests.get("customer_id", 0) >= 1

    @pytest.mark.requirement("3A-US4-FR004")
    def test_handles_model_level_tests(self) -> None:
        """CoverageValidator MUST handle model-level tests (no column)."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        # Model-level test (e.g., unique combination test)
        tests = [
            _create_test_node("bronze_orders", None, "relationships"),
        ]

        column_tests = validator._map_tests_to_columns(tests)

        # Model-level tests don't count toward column coverage
        assert column_tests == {}


class TestColumnLevelCoverageCalculation:
    """Tests for column-level coverage calculation (T049).

    Coverage Formula: (columns_with_at_least_one_test / total_columns) * 100
    """

    @pytest.mark.requirement("3A-US4-FR004")
    def test_calculates_100_percent_coverage(self) -> None:
        """100% coverage when all columns have tests."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        # 3 columns, all with tests
        columns = {"id": {}, "customer_id": {}, "amount": {}}
        column_tests = {"id": 2, "customer_id": 1, "amount": 1}

        coverage = validator._calculate_coverage(columns, column_tests)
        assert coverage == pytest.approx(100.0)

    @pytest.mark.requirement("3A-US4-FR004")
    def test_calculates_partial_coverage(self) -> None:
        """Partial coverage when some columns lack tests."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        # 4 columns, 3 with tests = 75% coverage
        columns = {"id": {}, "customer_id": {}, "amount": {}, "status": {}}
        column_tests = {"id": 2, "customer_id": 1, "amount": 1}

        coverage = validator._calculate_coverage(columns, column_tests)
        assert coverage == pytest.approx(75.0)

    @pytest.mark.requirement("3A-US4-FR004")
    def test_calculates_zero_coverage(self) -> None:
        """0% coverage when no columns have tests."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        columns = {"id": {}, "customer_id": {}, "amount": {}}
        column_tests: dict[str, int] = {}

        coverage = validator._calculate_coverage(columns, column_tests)
        assert coverage == pytest.approx(0.0)

    @pytest.mark.requirement("3A-US4-FR004")
    def test_handles_zero_columns_with_report_na(self) -> None:
        """Zero columns with report_na behavior returns None (N/A)."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=80,
            zero_column_coverage_behavior="report_na",
        )
        validator = CoverageValidator(config)

        columns: dict[str, Any] = {}
        column_tests: dict[str, int] = {}

        coverage = validator._calculate_coverage(columns, column_tests)
        assert coverage is None  # N/A

    @pytest.mark.requirement("3A-US4-FR004")
    def test_handles_zero_columns_with_report_100_percent(self) -> None:
        """Zero columns with report_100_percent behavior returns 100."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=80,
            zero_column_coverage_behavior="report_100_percent",
        )
        validator = CoverageValidator(config)

        columns: dict[str, Any] = {}
        column_tests: dict[str, int] = {}

        coverage = validator._calculate_coverage(columns, column_tests)
        assert coverage == pytest.approx(100.0)


class TestLayerDetection:
    """Tests for layer detection from model name (T050)."""

    @pytest.mark.requirement("3A-US4-FR012")
    def test_detects_bronze_layer(self) -> None:
        """CoverageValidator MUST detect bronze layer from model name."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        assert validator._detect_layer("bronze_orders") == "bronze"
        assert validator._detect_layer("bronze_customers") == "bronze"
        assert validator._detect_layer("bronze_raw_events") == "bronze"

    @pytest.mark.requirement("3A-US4-FR012")
    def test_detects_silver_layer(self) -> None:
        """CoverageValidator MUST detect silver layer from model name."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        assert validator._detect_layer("silver_orders") == "silver"
        assert validator._detect_layer("silver_enriched_customers") == "silver"

    @pytest.mark.requirement("3A-US4-FR012")
    def test_detects_gold_layer(self) -> None:
        """CoverageValidator MUST detect gold layer from model name."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        assert validator._detect_layer("gold_revenue") == "gold"
        assert validator._detect_layer("gold_kpi_dashboard") == "gold"

    @pytest.mark.requirement("3A-US4-FR012")
    def test_returns_none_for_unknown_layer(self) -> None:
        """CoverageValidator MUST return None for non-medallion names."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        assert validator._detect_layer("stg_orders") is None
        assert validator._detect_layer("dim_customer") is None
        assert validator._detect_layer("fact_sales") is None


class TestLayerSpecificThresholdChecking:
    """Tests for layer-specific threshold checking (T051)."""

    @pytest.mark.requirement("3A-US4-FR012")
    def test_uses_layer_threshold_when_configured(self) -> None:
        """CoverageValidator MUST use layer threshold when layer_thresholds configured."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import LayerThresholds, QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=80,  # Default
            layer_thresholds=LayerThresholds(bronze=50, silver=80, gold=100),
        )
        validator = CoverageValidator(config)

        # Bronze layer should use 50% threshold
        assert validator._get_threshold_for_layer("bronze") == 50
        # Silver layer should use 80% threshold
        assert validator._get_threshold_for_layer("silver") == 80
        # Gold layer should use 100% threshold
        assert validator._get_threshold_for_layer("gold") == 100

    @pytest.mark.requirement("3A-US4-FR012")
    def test_uses_default_threshold_for_unknown_layer(self) -> None:
        """CoverageValidator MUST use default threshold for non-medallion names."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import LayerThresholds, QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=80,  # Default
            layer_thresholds=LayerThresholds(bronze=50, silver=80, gold=100),
        )
        validator = CoverageValidator(config)

        # Unknown layer uses default
        assert validator._get_threshold_for_layer(None) == 80

    @pytest.mark.requirement("3A-US4-FR012")
    def test_uses_default_threshold_when_layer_thresholds_not_configured(self) -> None:
        """CoverageValidator MUST use default when layer_thresholds is None."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=85,
            layer_thresholds=None,
        )
        validator = CoverageValidator(config)

        # All layers use default
        assert validator._get_threshold_for_layer("bronze") == 85
        assert validator._get_threshold_for_layer("silver") == 85
        assert validator._get_threshold_for_layer("gold") == 85
        assert validator._get_threshold_for_layer(None) == 85

    @pytest.mark.requirement("3A-US4-FR012")
    def test_gold_layer_requires_100_percent(self) -> None:
        """Gold layer models MUST achieve 100% coverage with gold=100 config."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import LayerThresholds, QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=80,
            layer_thresholds=LayerThresholds(bronze=50, silver=80, gold=100),
        )
        validator = CoverageValidator(config)

        model = _create_model_node(
            name="gold_revenue",
            columns={"revenue": {}, "year": {}},
        )

        # 95% coverage should fail for gold layer (requires 100%)
        violations = validator.validate(
            models=[model],
            tests=[
                _create_test_node("gold_revenue", "revenue", "not_null"),
                # year column has no tests
            ],
        )

        assert len(violations) >= 1
        assert any(v.model_name == "gold_revenue" for v in violations)


class TestCoverageGapSuggestions:
    """Tests for coverage gap suggestion generation (T052)."""

    @pytest.mark.requirement("3A-US4-FR004")
    def test_suggests_missing_tests_for_uncovered_columns(self) -> None:
        """CoverageValidator MUST suggest tests for uncovered columns."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            columns={"id": {}, "customer_id": {}, "amount": {}, "status": {}},
        )

        # Only id and customer_id have tests
        violations = validator.validate(
            models=[model],
            tests=[
                _create_test_node("bronze_orders", "id", "not_null"),
                _create_test_node("bronze_orders", "customer_id", "not_null"),
            ],
        )

        # Should have violation with suggestion mentioning uncovered columns
        assert len(violations) == 1
        suggestion = violations[0].suggestion.lower()
        # Should mention uncovered columns (amount, status)
        assert "amount" in suggestion or "status" in suggestion or "uncovered" in suggestion

    @pytest.mark.requirement("3A-US4-FR004")
    def test_violation_includes_coverage_stats(self) -> None:
        """Violation MUST include coverage statistics (current vs required)."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            columns={"id": {}, "customer_id": {}, "amount": {}, "status": {}},
        )

        # 50% coverage (2/4 columns)
        violations = validator.validate(
            models=[model],
            tests=[
                _create_test_node("bronze_orders", "id", "not_null"),
                _create_test_node("bronze_orders", "customer_id", "not_null"),
            ],
        )

        assert len(violations) == 1
        violation = violations[0]

        # Should show current coverage vs required
        assert "50" in violation.actual or "50%" in violation.actual
        assert "80" in violation.expected or "80%" in violation.expected

    @pytest.mark.requirement("3A-US4-FR004")
    def test_violation_error_code_floe_e210(self) -> None:
        """Coverage violation MUST use error code FLOE-E210."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            columns={"id": {}, "customer_id": {}},
        )

        # 0% coverage
        violations = validator.validate(models=[model], tests=[])

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E210"
        assert violations[0].policy_type == "coverage"

    @pytest.mark.requirement("3A-US4-FR012")
    def test_layer_violation_error_code_floe_e211(self) -> None:
        """Layer-specific coverage violation MUST use error code FLOE-E211."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import LayerThresholds, QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=80,
            layer_thresholds=LayerThresholds(bronze=50, silver=80, gold=100),
        )
        validator = CoverageValidator(config)

        # Gold layer model with 50% coverage (should fail gold threshold of 100%)
        model = _create_model_node(
            name="gold_revenue",
            columns={"revenue": {}, "year": {}},
        )

        violations = validator.validate(
            models=[model],
            tests=[
                _create_test_node("gold_revenue", "revenue", "not_null"),
            ],
        )

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E211"
        assert violations[0].policy_type == "coverage"


class TestCoverageValidatorValidate:
    """Integration tests for CoverageValidator.validate() method."""

    @pytest.mark.requirement("3A-US4-FR004")
    def test_validate_returns_empty_when_all_pass(self) -> None:
        """CoverageValidator.validate() MUST return empty list when all models pass."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=50)
        validator = CoverageValidator(config)

        model = _create_model_node(
            name="bronze_orders",
            columns={"id": {}, "customer_id": {}},
        )

        # 100% coverage
        violations = validator.validate(
            models=[model],
            tests=[
                _create_test_node("bronze_orders", "id", "not_null"),
                _create_test_node("bronze_orders", "customer_id", "not_null"),
            ],
        )

        assert violations == []

    @pytest.mark.requirement("3A-US4-FR004")
    def test_validate_multiple_models_with_mixed_results(self) -> None:
        """CoverageValidator.validate() MUST validate multiple models."""
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(minimum_test_coverage=80)
        validator = CoverageValidator(config)

        models = [
            _create_model_node(
                name="bronze_orders",
                columns={"id": {}, "customer_id": {}},
            ),
            _create_model_node(
                name="silver_customers",
                columns={"email": {}, "name": {}, "phone": {}, "address": {}},
            ),
        ]

        # bronze_orders: 100% coverage (2/2)
        # silver_customers: 50% coverage (2/4)
        violations = validator.validate(
            models=models,
            tests=[
                _create_test_node("bronze_orders", "id", "not_null"),
                _create_test_node("bronze_orders", "customer_id", "not_null"),
                _create_test_node("silver_customers", "email", "unique"),
                _create_test_node("silver_customers", "name", "not_null"),
            ],
        )

        # Only silver_customers should have violation
        assert len(violations) == 1
        assert violations[0].model_name == "silver_customers"


class TestZeroColumnEdgeCases:
    """Tests for zero-column edge cases (T095).

    Task: T095
    Requirement: US4 (Coverage Enforcement)

    Models with zero columns are edge cases that need special handling:
    - report_na behavior: Return None (N/A), skip validation
    - report_100_percent behavior: Return 100%, always passes
    """

    @pytest.mark.requirement("3A-US4-007")
    def test_zero_column_model_skipped_with_report_na(self) -> None:
        """Models with zero columns SHOULD be skipped when report_na is configured.

        When zero_column_coverage_behavior="report_na", models with no columns
        should not generate violations (coverage is N/A, not 0%).
        """
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=100,  # Very high threshold
            zero_column_coverage_behavior="report_na",  # Default behavior
        )
        validator = CoverageValidator(config)

        # Model with zero columns
        model = _create_model_node(name="bronze_empty", columns={})

        violations = validator.validate(models=[model], tests=[])

        # Should NOT have violation - zero columns is N/A, not 0%
        assert len(violations) == 0

    @pytest.mark.requirement("3A-US4-007")
    def test_zero_column_model_passes_with_report_100_percent(self) -> None:
        """Models with zero columns SHOULD pass when report_100_percent is configured.

        When zero_column_coverage_behavior="report_100_percent", models with
        no columns are considered to have 100% coverage (vacuous truth).
        """
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=100,  # Requires 100%
            zero_column_coverage_behavior="report_100_percent",
        )
        validator = CoverageValidator(config)

        # Model with zero columns
        model = _create_model_node(name="bronze_empty", columns={})

        violations = validator.validate(models=[model], tests=[])

        # Should NOT have violation - zero columns = 100% coverage
        assert len(violations) == 0

    @pytest.mark.requirement("3A-US4-007")
    def test_zero_column_model_with_null_columns_field(self) -> None:
        """Models with null columns field SHOULD be handled like zero columns.

        Some dbt manifests may have columns=null instead of columns={}.
        Both should be treated as zero columns.
        """
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=100,
            zero_column_coverage_behavior="report_na",
        )
        validator = CoverageValidator(config)

        # Model with null columns (simulated by setting columns to None)
        model = _create_model_node(name="bronze_null_cols", columns=None)

        violations = validator.validate(models=[model], tests=[])

        # Should NOT have violation - null columns treated as zero columns
        assert len(violations) == 0

    @pytest.mark.requirement("3A-US4-007")
    def test_mixed_models_with_zero_column_model(self) -> None:
        """Validation SHOULD correctly handle mix of zero and non-zero column models.

        When validating multiple models, zero-column models should be handled
        according to the configured behavior while non-zero column models
        are validated normally.
        """
        from floe_core.enforcement.validators.coverage import CoverageValidator
        from floe_core.schemas.governance import QualityGatesConfig

        config = QualityGatesConfig(
            minimum_test_coverage=80,
            zero_column_coverage_behavior="report_na",
        )
        validator = CoverageValidator(config)

        models = [
            # Zero columns - should be skipped (N/A)
            _create_model_node(name="bronze_empty", columns={}),
            # Normal model with columns - should be validated
            _create_model_node(
                name="bronze_orders",
                columns={"id": {}, "customer_id": {}},
            ),
        ]

        # Only test the normal model (50% coverage)
        violations = validator.validate(
            models=models,
            tests=[
                _create_test_node("bronze_orders", "id", "not_null"),
            ],
        )

        # Should have exactly 1 violation for bronze_orders (50% < 80%)
        # bronze_empty should be skipped (not counted as 0% violation)
        assert len(violations) == 1
        assert violations[0].model_name == "bronze_orders"

    @pytest.mark.requirement("3A-US4-007")
    def test_default_zero_column_behavior_is_report_na(self) -> None:
        """Default zero_column_coverage_behavior SHOULD be report_na."""
        from floe_core.schemas.governance import QualityGatesConfig

        # Create config without specifying zero_column_coverage_behavior
        config = QualityGatesConfig(minimum_test_coverage=80)

        # Default should be report_na
        assert config.zero_column_coverage_behavior == "report_na"

    @pytest.mark.requirement("3A-US4-007")
    def test_zero_column_in_full_enforcement_flow(self) -> None:
        """Zero-column handling MUST work in full PolicyEnforcer.enforce() flow."""
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance = GovernanceConfig(
            policy_enforcement_level="strict",
            quality_gates=QualityGatesConfig(
                minimum_test_coverage=100,
                zero_column_coverage_behavior="report_na",
            ),
        )

        enforcer = PolicyEnforcer(governance_config=governance)

        # Manifest with zero-column model
        manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.test.empty_model": {
                    "name": "empty_model",
                    "resource_type": "model",
                    "unique_id": "model.test.empty_model",
                    "columns": {},
                },
            },
        }

        result = enforcer.enforce(manifest)

        # Should pass with no coverage violations
        coverage_violations = [v for v in result.violations if v.policy_type == "coverage"]
        assert len(coverage_violations) == 0


class TestCoverageValidatorIntegration:
    """Integration tests with PolicyEnforcer."""

    @pytest.mark.requirement("3A-US4-FR004")
    def test_coverage_validator_integrated_with_policy_enforcer(self) -> None:
        """CoverageValidator MUST be wired into PolicyEnforcer.enforce()."""
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        governance = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(enforcement="off"),  # Disable naming to focus on coverage
            quality_gates=QualityGatesConfig(minimum_test_coverage=80),
        )

        enforcer = PolicyEnforcer(governance_config=governance)

        # Create manifest with model and tests
        manifest = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.test.bronze_orders": {
                    "name": "bronze_orders",
                    "resource_type": "model",
                    "unique_id": "model.test.bronze_orders",
                    "columns": {
                        "id": {"name": "id"},
                        "customer_id": {"name": "customer_id"},
                        "amount": {"name": "amount"},
                        "status": {"name": "status"},
                    },
                },
                "test.test.not_null_bronze_orders_id": {
                    "name": "not_null_bronze_orders_id",
                    "resource_type": "test",
                    "unique_id": "test.test.not_null_bronze_orders_id",
                    "attached_node": "model.test.bronze_orders",
                    "column_name": "id",
                },
                # Only 1 column tested (25% coverage)
            },
        }

        result = enforcer.enforce(manifest)

        # Should have coverage violation (25% < 80%)
        coverage_violations = [v for v in result.violations if v.policy_type == "coverage"]
        assert len(coverage_violations) >= 1
