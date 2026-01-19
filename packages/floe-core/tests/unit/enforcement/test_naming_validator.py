"""Unit tests for NamingValidator - TDD tests written first.

These tests define the expected behavior for NamingValidator before implementation.
They verify naming convention validation for medallion, kimball, and custom patterns.

Task: T034, T035, T036, T037, T038, T039
Requirements: FR-003 (Naming Convention Enforcement), US3 (Naming Validation)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestMedallionPattern:
    """Tests for medallion naming pattern validation (T034).

    Medallion pattern: ^(bronze|silver|gold)_[a-z][a-z0-9_]*$
    Valid: bronze_orders, silver_customers, gold_revenue
    Invalid: stg_payments, dim_product, raw_data
    """

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_matches_bronze_prefix(self) -> None:
        """Medallion pattern MUST match bronze_ prefix."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        assert re.match(MEDALLION_PATTERN, "bronze_orders")
        assert re.match(MEDALLION_PATTERN, "bronze_customers")
        assert re.match(MEDALLION_PATTERN, "bronze_raw_data")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_matches_silver_prefix(self) -> None:
        """Medallion pattern MUST match silver_ prefix."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        assert re.match(MEDALLION_PATTERN, "silver_orders")
        assert re.match(MEDALLION_PATTERN, "silver_customers")
        assert re.match(MEDALLION_PATTERN, "silver_enriched_orders")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_matches_gold_prefix(self) -> None:
        """Medallion pattern MUST match gold_ prefix."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        assert re.match(MEDALLION_PATTERN, "gold_revenue")
        assert re.match(MEDALLION_PATTERN, "gold_kpi_dashboard")
        assert re.match(MEDALLION_PATTERN, "gold_aggregated_metrics")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_rejects_staging_prefix(self) -> None:
        """Medallion pattern MUST reject stg_ prefix."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        assert not re.match(MEDALLION_PATTERN, "stg_payments")
        assert not re.match(MEDALLION_PATTERN, "stg_customers")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_rejects_dim_prefix(self) -> None:
        """Medallion pattern MUST reject dim_ prefix (kimball pattern)."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        assert not re.match(MEDALLION_PATTERN, "dim_product")
        assert not re.match(MEDALLION_PATTERN, "dim_customer")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_rejects_fact_prefix(self) -> None:
        """Medallion pattern MUST reject fact_ prefix (kimball pattern)."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        assert not re.match(MEDALLION_PATTERN, "fact_orders")
        assert not re.match(MEDALLION_PATTERN, "fact_sales")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_rejects_raw_prefix(self) -> None:
        """Medallion pattern MUST reject raw_ prefix."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        assert not re.match(MEDALLION_PATTERN, "raw_data")
        assert not re.match(MEDALLION_PATTERN, "raw_events")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_requires_lowercase_after_prefix(self) -> None:
        """Medallion pattern MUST require lowercase letter after prefix."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        # Valid: lowercase start
        assert re.match(MEDALLION_PATTERN, "bronze_a")
        assert re.match(MEDALLION_PATTERN, "silver_orders")

        # Invalid: uppercase or number after prefix
        assert not re.match(MEDALLION_PATTERN, "bronze_A")
        assert not re.match(MEDALLION_PATTERN, "silver_1orders")
        assert not re.match(MEDALLION_PATTERN, "gold_")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_pattern_allows_underscores_and_numbers(self) -> None:
        """Medallion pattern MUST allow underscores and numbers after first char."""
        from floe_core.enforcement.patterns import MEDALLION_PATTERN

        assert re.match(MEDALLION_PATTERN, "bronze_orders_2024")
        assert re.match(MEDALLION_PATTERN, "silver_customer_v2")
        assert re.match(MEDALLION_PATTERN, "gold_revenue_q1_2024")


class TestKimballPattern:
    """Tests for kimball naming pattern validation (T035).

    Kimball pattern: ^(dim|fact|bridge|hub|link|sat)_[a-z][a-z0-9_]*$
    Valid: dim_customer, fact_orders, bridge_order_product
    Invalid: bronze_orders, stg_data
    """

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_matches_dim_prefix(self) -> None:
        """Kimball pattern MUST match dim_ prefix."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        assert re.match(KIMBALL_PATTERN, "dim_customer")
        assert re.match(KIMBALL_PATTERN, "dim_product")
        assert re.match(KIMBALL_PATTERN, "dim_date")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_matches_fact_prefix(self) -> None:
        """Kimball pattern MUST match fact_ prefix."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        assert re.match(KIMBALL_PATTERN, "fact_orders")
        assert re.match(KIMBALL_PATTERN, "fact_sales")
        assert re.match(KIMBALL_PATTERN, "fact_inventory_snapshot")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_matches_bridge_prefix(self) -> None:
        """Kimball pattern MUST match bridge_ prefix."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        assert re.match(KIMBALL_PATTERN, "bridge_order_product")
        assert re.match(KIMBALL_PATTERN, "bridge_customer_address")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_matches_hub_prefix(self) -> None:
        """Kimball pattern MUST match hub_ prefix (Data Vault extension)."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        assert re.match(KIMBALL_PATTERN, "hub_customer")
        assert re.match(KIMBALL_PATTERN, "hub_product")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_matches_link_prefix(self) -> None:
        """Kimball pattern MUST match link_ prefix (Data Vault extension)."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        assert re.match(KIMBALL_PATTERN, "link_order_customer")
        assert re.match(KIMBALL_PATTERN, "link_product_supplier")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_matches_sat_prefix(self) -> None:
        """Kimball pattern MUST match sat_ prefix (Data Vault extension)."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        assert re.match(KIMBALL_PATTERN, "sat_customer")
        assert re.match(KIMBALL_PATTERN, "sat_product_details")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_rejects_medallion_prefixes(self) -> None:
        """Kimball pattern MUST reject medallion prefixes."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        assert not re.match(KIMBALL_PATTERN, "bronze_orders")
        assert not re.match(KIMBALL_PATTERN, "silver_customers")
        assert not re.match(KIMBALL_PATTERN, "gold_revenue")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_rejects_staging_prefix(self) -> None:
        """Kimball pattern MUST reject stg_ prefix."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        assert not re.match(KIMBALL_PATTERN, "stg_orders")
        assert not re.match(KIMBALL_PATTERN, "stg_customers")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_pattern_requires_lowercase_after_prefix(self) -> None:
        """Kimball pattern MUST require lowercase letter after prefix."""
        from floe_core.enforcement.patterns import KIMBALL_PATTERN

        # Valid: lowercase start
        assert re.match(KIMBALL_PATTERN, "dim_a")
        assert re.match(KIMBALL_PATTERN, "fact_orders")

        # Invalid: uppercase or number after prefix
        assert not re.match(KIMBALL_PATTERN, "dim_A")
        assert not re.match(KIMBALL_PATTERN, "fact_1orders")
        assert not re.match(KIMBALL_PATTERN, "bridge_")


class TestCustomPatternValidation:
    """Tests for custom pattern validation (T036).

    Custom patterns require:
    1. custom_patterns list when pattern="custom"
    2. Valid regex syntax for all patterns
    """

    @pytest.mark.requirement("3A-US3-FR003")
    def test_custom_pattern_validation_accepts_valid_regex(self) -> None:
        """Custom pattern validation MUST accept valid regex patterns."""
        from floe_core.enforcement.patterns import validate_custom_patterns

        # Should not raise
        validate_custom_patterns(["^raw_.*$", "^clean_.*$", "^agg_.*$"])

    @pytest.mark.requirement("3A-US3-FR003")
    def test_custom_pattern_validation_rejects_invalid_regex(self) -> None:
        """Custom pattern validation MUST reject invalid regex."""
        from floe_core.enforcement.patterns import (
            InvalidPatternError,
            validate_custom_patterns,
        )

        with pytest.raises(InvalidPatternError, match="Invalid regex"):
            validate_custom_patterns(["^valid$", "[invalid("])

    @pytest.mark.requirement("3A-US3-FR003")
    def test_custom_pattern_validation_rejects_empty_list(self) -> None:
        """Custom pattern validation MUST reject empty list."""
        from floe_core.enforcement.patterns import (
            InvalidPatternError,
            validate_custom_patterns,
        )

        with pytest.raises(InvalidPatternError, match="at least one pattern"):
            validate_custom_patterns([])

    @pytest.mark.requirement("3A-US3-FR003")
    def test_custom_pattern_matches_any_pattern(self) -> None:
        """Custom pattern MUST match if ANY pattern matches (OR logic)."""
        from floe_core.enforcement.patterns import matches_custom_patterns

        patterns = ["^raw_.*$", "^clean_.*$", "^agg_.*$"]

        # Each pattern can match
        assert matches_custom_patterns("raw_orders", patterns)
        assert matches_custom_patterns("clean_customers", patterns)
        assert matches_custom_patterns("agg_revenue", patterns)

        # None match
        assert not matches_custom_patterns("stg_data", patterns)
        assert not matches_custom_patterns("bronze_orders", patterns)


class TestReDoSProtection:
    """Tests for ReDoS (Regular Expression Denial of Service) protection (T037).

    Custom patterns MUST be validated for ReDoS vulnerabilities to prevent
    CPU exhaustion attacks via malicious input.
    """

    @pytest.mark.requirement("3A-US3-FR003")
    def test_redos_protection_rejects_catastrophic_backtracking(self) -> None:
        """ReDoS protection MUST reject patterns with catastrophic backtracking.

        Example evil patterns:
        - (a+)+$ - Exponential backtracking
        - (a|a)+$ - Exponential backtracking
        - (.*a){x} where x>10 - Polynomial backtracking
        """
        from floe_core.enforcement.patterns import (
            InvalidPatternError,
            validate_custom_patterns,
        )

        # Known ReDoS patterns
        evil_patterns = [
            "(a+)+$",  # Exponential backtracking
            "(a|a)+$",  # Exponential backtracking
            "^(a+)+b$",  # Classic ReDoS
        ]

        for pattern in evil_patterns:
            with pytest.raises(InvalidPatternError, match="ReDoS|unsafe"):
                validate_custom_patterns([pattern])

    @pytest.mark.requirement("3A-US3-FR003")
    def test_redos_protection_accepts_safe_patterns(self) -> None:
        """ReDoS protection MUST accept safe, bounded patterns."""
        from floe_core.enforcement.patterns import validate_custom_patterns

        safe_patterns = [
            "^[a-z]+$",  # No nesting
            "^raw_[a-z0-9_]*$",  # Bounded repetition
            "^(bronze|silver|gold)_.*$",  # Alternation without nesting
        ]

        # Should not raise
        validate_custom_patterns(safe_patterns)

    @pytest.mark.requirement("3A-US3-FR003")
    def test_redos_protection_limits_pattern_complexity(self) -> None:
        """ReDoS protection MUST limit pattern complexity/length."""
        from floe_core.enforcement.patterns import (
            InvalidPatternError,
            validate_custom_patterns,
        )

        # Excessively long pattern
        long_pattern = "^" + "a" * 10000 + "$"

        with pytest.raises(InvalidPatternError, match="too long|complexity"):
            validate_custom_patterns([long_pattern])


class TestNamingValidatorValidate:
    """Tests for NamingValidator.validate() method (T038)."""

    @pytest.mark.requirement("3A-US3-FR003")
    def test_validate_returns_empty_list_when_enforcement_off(self) -> None:
        """NamingValidator.validate() MUST return empty list when enforcement='off'."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="off", pattern="medallion")
        validator = NamingValidator(config)

        # Even invalid names should pass when enforcement is off
        models = [{"name": "invalid_name", "resource_type": "model"}]
        violations = validator.validate(models)

        assert violations == []

    @pytest.mark.requirement("3A-US3-FR003")
    def test_validate_returns_violations_for_invalid_medallion_names(self) -> None:
        """NamingValidator.validate() MUST return violations for invalid medallion names."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="medallion")
        validator = NamingValidator(config)

        models = [
            {"name": "bronze_orders", "resource_type": "model"},  # Valid
            {"name": "stg_payments", "resource_type": "model"},  # Invalid
            {"name": "dim_customer", "resource_type": "model"},  # Invalid
        ]
        violations = validator.validate(models)

        assert len(violations) == 2
        violation_names = [v.model_name for v in violations]
        assert "stg_payments" in violation_names
        assert "dim_customer" in violation_names
        assert "bronze_orders" not in violation_names

    @pytest.mark.requirement("3A-US3-FR003")
    def test_validate_returns_violations_for_invalid_kimball_names(self) -> None:
        """NamingValidator.validate() MUST return violations for invalid kimball names."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="kimball")
        validator = NamingValidator(config)

        models = [
            {"name": "dim_customer", "resource_type": "model"},  # Valid
            {"name": "fact_orders", "resource_type": "model"},  # Valid
            {"name": "bronze_orders", "resource_type": "model"},  # Invalid
            {"name": "stg_data", "resource_type": "model"},  # Invalid
        ]
        violations = validator.validate(models)

        assert len(violations) == 2
        violation_names = [v.model_name for v in violations]
        assert "bronze_orders" in violation_names
        assert "stg_data" in violation_names

    @pytest.mark.requirement("3A-US3-FR003")
    def test_validate_returns_violations_for_invalid_custom_names(self) -> None:
        """NamingValidator.validate() MUST return violations for invalid custom names."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(
            enforcement="strict",
            pattern="custom",
            custom_patterns=["^raw_.*$", "^clean_.*$"],
        )
        validator = NamingValidator(config)

        models = [
            {"name": "raw_orders", "resource_type": "model"},  # Valid
            {"name": "clean_data", "resource_type": "model"},  # Valid
            {"name": "stg_payments", "resource_type": "model"},  # Invalid
        ]
        violations = validator.validate(models)

        assert len(violations) == 1
        assert violations[0].model_name == "stg_payments"

    @pytest.mark.requirement("3A-US3-FR003")
    def test_validate_uses_warning_severity_for_warn_enforcement(self) -> None:
        """NamingValidator.validate() MUST use 'warning' severity for warn enforcement."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="warn", pattern="medallion")
        validator = NamingValidator(config)

        models = [{"name": "invalid_name", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        assert violations[0].severity == "warning"

    @pytest.mark.requirement("3A-US3-FR003")
    def test_validate_uses_error_severity_for_strict_enforcement(self) -> None:
        """NamingValidator.validate() MUST use 'error' severity for strict enforcement."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="medallion")
        validator = NamingValidator(config)

        models = [{"name": "invalid_name", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        assert violations[0].severity == "error"

    @pytest.mark.requirement("3A-US3-FR003")
    def test_validate_returns_error_code_floe_e201(self) -> None:
        """NamingValidator.validate() MUST return error code FLOE-E201."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="medallion")
        validator = NamingValidator(config)

        models = [{"name": "invalid_name", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E201"
        assert violations[0].policy_type == "naming"

    @pytest.mark.requirement("3A-US3-FR003")
    def test_validate_includes_expected_pattern_in_violation(self) -> None:
        """NamingValidator.validate() MUST include expected pattern in violation."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="medallion")
        validator = NamingValidator(config)

        models = [{"name": "stg_payments", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        # Expected should include the pattern regex or description
        assert "bronze" in violations[0].expected or "medallion" in violations[0].expected.lower()


class TestRemediationSuggestions:
    """Tests for remediation suggestion generation (T039)."""

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_suggestion_for_stg_prefix(self) -> None:
        """Remediation MUST suggest bronze_ prefix for stg_ models."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="medallion")
        validator = NamingValidator(config)

        models = [{"name": "stg_payments", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        # Suggestion should recommend renaming to bronze_
        assert "bronze_" in violations[0].suggestion or "Rename" in violations[0].suggestion

    @pytest.mark.requirement("3A-US3-FR003")
    def test_medallion_suggestion_for_dim_prefix(self) -> None:
        """Remediation MUST suggest appropriate medallion prefix for dim_ models."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="medallion")
        validator = NamingValidator(config)

        models = [{"name": "dim_customer", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        # dim_ suggests a silver/gold layer transformation
        assert "gold_" in violations[0].suggestion or "silver_" in violations[0].suggestion

    @pytest.mark.requirement("3A-US3-FR003")
    def test_kimball_suggestion_for_bronze_prefix(self) -> None:
        """Remediation MUST suggest appropriate kimball prefix for bronze_ models."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="kimball")
        validator = NamingValidator(config)

        models = [{"name": "bronze_orders", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        # bronze_ raw data suggests a fact_ or staging model
        suggestion = violations[0].suggestion.lower()
        assert "fact_" in suggestion or "dim_" in suggestion or "rename" in suggestion

    @pytest.mark.requirement("3A-US3-FR003")
    def test_documentation_url_included(self) -> None:
        """Violations MUST include documentation URL."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="medallion")
        validator = NamingValidator(config)

        models = [{"name": "stg_payments", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        assert violations[0].documentation_url.startswith("https://")
        assert "naming" in violations[0].documentation_url.lower()

    @pytest.mark.requirement("3A-US3-FR003")
    def test_actual_value_is_model_name(self) -> None:
        """Violations MUST include actual model name."""
        from floe_core.enforcement.validators.naming import NamingValidator
        from floe_core.schemas.governance import NamingConfig

        config = NamingConfig(enforcement="strict", pattern="medallion")
        validator = NamingValidator(config)

        models = [{"name": "stg_payments", "resource_type": "model"}]
        violations = validator.validate(models)

        assert len(violations) == 1
        assert violations[0].actual == "stg_payments"


class TestDocumentationURLs:
    """Tests for documentation URL constants (T040)."""

    @pytest.mark.requirement("3A-US3-FR003")
    def test_documentation_urls_base_defined(self) -> None:
        """DOCUMENTATION_URLS base MUST be defined."""
        from floe_core.enforcement.patterns import DOCUMENTATION_URLS

        assert "base" in DOCUMENTATION_URLS
        assert DOCUMENTATION_URLS["base"].startswith("https://")

    @pytest.mark.requirement("3A-US3-FR003")
    def test_documentation_urls_naming_defined(self) -> None:
        """DOCUMENTATION_URLS naming section MUST be defined."""
        from floe_core.enforcement.patterns import DOCUMENTATION_URLS

        assert "naming" in DOCUMENTATION_URLS
        # Should contain pattern-specific paths
        assert "medallion" in DOCUMENTATION_URLS["naming"]
        assert "kimball" in DOCUMENTATION_URLS["naming"]


class TestNamingValidatorIntegration:
    """Integration tests for NamingValidator with PolicyEnforcer."""

    @pytest.mark.requirement("3A-US3-FR003")
    def test_naming_validator_integrated_with_policy_enforcer(self) -> None:
        """NamingValidator MUST be wired into PolicyEnforcer.enforce().

        This test verifies that PolicyEnforcer uses NamingValidator
        when GovernanceConfig has naming configuration.
        """
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.schemas.governance import NamingConfig, QualityGatesConfig
        from floe_core.schemas.manifest import GovernanceConfig

        # Create governance config with naming enforcement
        governance = GovernanceConfig(
            policy_enforcement_level="strict",
            naming=NamingConfig(enforcement="strict", pattern="medallion"),
            quality_gates=QualityGatesConfig(minimum_test_coverage=80),
        )

        enforcer = PolicyEnforcer(governance_config=governance)

        # Create a minimal manifest with invalid model names
        manifest = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {
                "model.test.stg_payments": {
                    "name": "stg_payments",
                    "resource_type": "model",
                },
                "model.test.bronze_orders": {
                    "name": "bronze_orders",
                    "resource_type": "model",
                },
            },
        }

        result = enforcer.enforce(manifest)

        # Should have violation for stg_payments
        assert not result.passed
        naming_violations = [v for v in result.violations if v.policy_type == "naming"]
        assert len(naming_violations) >= 1
        assert any(v.model_name == "stg_payments" for v in naming_violations)
