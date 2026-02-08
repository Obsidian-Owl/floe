"""Unit tests for coverage calculator.

Tests the coverage calculation and test type detection functions.
T072: Coverage calculation (% columns with tests)
T073: Required test type detection
"""

from __future__ import annotations

import pytest

from floe_core.validation.coverage_calculator import (
    CoverageResult,
    calculate_coverage,
    detect_test_types,
)


class TestCalculateCoverage:
    """Test calculate_coverage function (T072)."""

    @pytest.mark.requirement("005B-FR-021")
    def test_full_coverage(self) -> None:
        """Test 100% coverage when all columns have tests."""
        model = {
            "name": "gold_customers",
            "tier": "gold",
            "columns": [
                {"name": "id", "tests": ["not_null", "unique"]},
                {"name": "name", "tests": ["not_null"]},
                {"name": "email", "tests": ["not_null"]},
            ],
        }
        result = calculate_coverage(model)
        assert result.coverage_percentage == 100.0
        assert result.total_columns == 3
        assert result.columns_with_tests == 3

    @pytest.mark.requirement("005B-FR-021")
    def test_partial_coverage(self) -> None:
        """Test partial coverage when some columns lack tests."""
        model = {
            "name": "silver_orders",
            "tier": "silver",
            "columns": [
                {"name": "id", "tests": ["not_null", "unique"]},
                {"name": "customer_id", "tests": ["not_null"]},
                {"name": "created_at", "tests": []},
                {"name": "updated_at", "tests": []},
            ],
        }
        result = calculate_coverage(model)
        assert result.coverage_percentage == 50.0
        assert result.total_columns == 4
        assert result.columns_with_tests == 2

    @pytest.mark.requirement("005B-FR-021")
    def test_zero_coverage(self) -> None:
        """Test 0% coverage when no columns have tests."""
        model = {
            "name": "bronze_raw",
            "tier": "bronze",
            "columns": [
                {"name": "id", "tests": []},
                {"name": "data", "tests": []},
            ],
        }
        result = calculate_coverage(model)
        assert result.coverage_percentage == 0.0
        assert result.columns_with_tests == 0

    @pytest.mark.requirement("005B-FR-021")
    def test_empty_columns(self) -> None:
        """Test handling of model with no columns."""
        model = {
            "name": "empty_model",
            "tier": "bronze",
            "columns": [],
        }
        result = calculate_coverage(model)
        assert result.coverage_percentage == 0.0
        assert result.total_columns == 0
        assert result.columns_with_tests == 0

    @pytest.mark.requirement("005B-FR-021")
    def test_model_name_extraction(self) -> None:
        """Test model name is correctly extracted."""
        model = {
            "name": "my_model",
            "columns": [{"name": "id", "tests": ["not_null"]}],
        }
        result = calculate_coverage(model)
        assert result.model_name == "my_model"

    @pytest.mark.requirement("005B-FR-021")
    def test_tier_extraction(self) -> None:
        """Test tier is correctly extracted."""
        model = {
            "name": "model",
            "tier": "gold",
            "columns": [{"name": "id", "tests": ["not_null"]}],
        }
        result = calculate_coverage(model)
        assert result.tier == "gold"

    @pytest.mark.requirement("005B-FR-021")
    def test_default_tier_is_bronze(self) -> None:
        """Test default tier is bronze when not specified."""
        model = {
            "name": "model",
            "columns": [{"name": "id", "tests": ["not_null"]}],
        }
        result = calculate_coverage(model)
        assert result.tier == "bronze"

    @pytest.mark.requirement("005B-FR-021")
    def test_result_is_dataclass(self) -> None:
        """Test result is a CoverageResult dataclass."""
        model = {"name": "model", "columns": []}
        result = calculate_coverage(model)
        assert isinstance(result, CoverageResult)


class TestDetectTestTypes:
    """Test detect_test_types function (T073)."""

    @pytest.mark.requirement("005B-FR-022")
    def test_detects_column_level_tests(self) -> None:
        """Test detection of tests defined on columns."""
        model = {
            "name": "model",
            "columns": [
                {"name": "id", "tests": ["not_null", "unique"]},
                {"name": "email", "tests": ["not_null"]},
            ],
        }
        test_types = detect_test_types(model)
        assert test_types == {"not_null", "unique"}

    @pytest.mark.requirement("005B-FR-022")
    def test_detects_model_level_tests(self) -> None:
        """Test detection of tests defined at model level."""
        model = {
            "name": "model",
            "columns": [{"name": "id", "tests": ["not_null"]}],
            "tests": [
                "relationships",
                "dbt_expectations.expect_table_row_count_to_be_between",
            ],
        }
        test_types = detect_test_types(model)
        assert "relationships" in test_types
        assert "dbt_expectations.expect_table_row_count_to_be_between" in test_types

    @pytest.mark.requirement("005B-FR-022")
    def test_combines_column_and_model_tests(self) -> None:
        """Test that column and model level tests are combined."""
        model = {
            "name": "model",
            "columns": [
                {"name": "id", "tests": ["not_null", "unique"]},
            ],
            "tests": ["relationships"],
        }
        test_types = detect_test_types(model)
        assert test_types == {"not_null", "unique", "relationships"}

    @pytest.mark.requirement("005B-FR-022")
    def test_handles_dict_test_format(self) -> None:
        """Test handling of dictionary-style test definitions."""
        model = {
            "name": "model",
            "columns": [
                {
                    "name": "status",
                    "tests": [
                        "not_null",
                        {"accepted_values": {"values": ["active", "inactive"]}},
                    ],
                },
            ],
        }
        test_types = detect_test_types(model)
        assert "not_null" in test_types
        assert "accepted_values" in test_types

    @pytest.mark.requirement("005B-FR-022")
    def test_handles_empty_model(self) -> None:
        """Test handling of model with no tests."""
        model = {
            "name": "model",
            "columns": [{"name": "id", "tests": []}],
        }
        test_types = detect_test_types(model)
        assert test_types == set()

    @pytest.mark.requirement("005B-FR-022")
    def test_deduplicates_test_types(self) -> None:
        """Test that duplicate test types are deduplicated."""
        model = {
            "name": "model",
            "columns": [
                {"name": "id", "tests": ["not_null"]},
                {"name": "email", "tests": ["not_null"]},
                {"name": "phone", "tests": ["not_null"]},
            ],
        }
        test_types = detect_test_types(model)
        assert test_types == {"not_null"}
