"""Unit tests for CustomRuleValidator.

Tests for the custom rule validation system supporting:
- require_tags_for_prefix (FLOE-E400)
- require_meta_field (FLOE-E401)
- require_tests_of_type (FLOE-E402)

Task: T023, T024, T025, T026
Requirements: FR-005 through FR-010 (US2 - Custom Policy Rules)

TDD Pattern: These tests are written FIRST and should FAIL until
T027-T033 implements the CustomRuleValidator class.
"""

from __future__ import annotations

from typing import Any

import pytest

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def valid_manifest() -> dict[str, Any]:
    """Create a valid dbt manifest with models, tags, and meta fields.

    Returns:
        Dictionary representing a valid dbt manifest.json with:
        - gold_customers: Has tags ["tested", "documented"] and meta owner
        - silver_orders: Has tags ["validated"] and meta owner
        - bronze_events: No tags, no meta owner
        - legacy_users: Has tags ["deprecated"]
    """
    return {
        "metadata": {
            "dbt_version": "1.8.0",
            "project_name": "my_project",
            "generated_at": "2026-01-20T10:00:00Z",
        },
        "nodes": {
            "model.my_project.gold_customers": {
                "name": "gold_customers",
                "resource_type": "model",
                "unique_id": "model.my_project.gold_customers",
                "tags": ["tested", "documented"],
                "meta": {"owner": "data-team@example.com"},
                "columns": {
                    "customer_id": {
                        "name": "customer_id",
                        "description": "Primary key",
                    },
                    "email": {"name": "email", "description": "Customer email"},
                },
                "depends_on": {"nodes": []},
            },
            "model.my_project.silver_orders": {
                "name": "silver_orders",
                "resource_type": "model",
                "unique_id": "model.my_project.silver_orders",
                "tags": ["validated"],
                "meta": {"owner": "sales-team@example.com"},
                "columns": {
                    "order_id": {"name": "order_id", "description": "Order ID"},
                },
                "depends_on": {"nodes": []},
            },
            "model.my_project.bronze_events": {
                "name": "bronze_events",
                "resource_type": "model",
                "unique_id": "model.my_project.bronze_events",
                "tags": [],
                "meta": {},
                "columns": {},
                "depends_on": {"nodes": []},
            },
            "model.my_project.legacy_users": {
                "name": "legacy_users",
                "resource_type": "model",
                "unique_id": "model.my_project.legacy_users",
                "tags": ["deprecated"],
                "meta": {"owner": ""},  # Empty value
                "columns": {},
                "depends_on": {"nodes": []},
            },
        },
    }


@pytest.fixture
def manifest_with_tests() -> dict[str, Any]:
    """Create a manifest with models having various test configurations.

    Returns:
        Dictionary representing a dbt manifest with test nodes.
    """
    return {
        "metadata": {
            "dbt_version": "1.8.0",
            "project_name": "my_project",
        },
        "nodes": {
            "model.my_project.customers": {
                "name": "customers",
                "resource_type": "model",
                "unique_id": "model.my_project.customers",
                "tags": [],
                "meta": {},
                "columns": {
                    "customer_id": {"name": "customer_id"},
                    "email": {"name": "email"},
                },
                "depends_on": {"nodes": []},
            },
            "model.my_project.orders": {
                "name": "orders",
                "resource_type": "model",
                "unique_id": "model.my_project.orders",
                "tags": [],
                "meta": {},
                "columns": {
                    "order_id": {"name": "order_id"},
                },
                "depends_on": {"nodes": []},
            },
            # Test nodes for customers model
            "test.my_project.not_null_customers_customer_id": {
                "name": "not_null_customers_customer_id",
                "resource_type": "test",
                "unique_id": "test.my_project.not_null_customers_customer_id",
                "test_metadata": {
                    "name": "not_null",
                },
                "depends_on": {
                    "nodes": ["model.my_project.customers"],
                },
                "attached_node": "model.my_project.customers",
            },
            "test.my_project.unique_customers_customer_id": {
                "name": "unique_customers_customer_id",
                "resource_type": "test",
                "unique_id": "test.my_project.unique_customers_customer_id",
                "test_metadata": {
                    "name": "unique",
                },
                "depends_on": {
                    "nodes": ["model.my_project.customers"],
                },
                "attached_node": "model.my_project.customers",
            },
            # No tests for orders model
        },
    }


# ==============================================================================
# T023: Tests for require_tags_for_prefix Rule (FLOE-E400)
# ==============================================================================


class TestRequireTagsForPrefixRule:
    """Tests for the require_tags_for_prefix custom rule.

    FR-006: System MUST support rule type `require_tags_for_prefix`
    to enforce tags on models matching prefix patterns.
    """

    @pytest.mark.requirement("003b-FR-006")
    def test_model_matching_prefix_without_required_tags_generates_violation(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that model matching prefix but missing tags generates FLOE-E400.

        Given: gold_customers model with tags ["tested", "documented"]
        When: Rule requires ["tested", "production"] tags for gold_ prefix
        Then: FLOE-E400 violation for missing "production" tag
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTagsForPrefix

        rule = RequireTagsForPrefix(
            prefix="gold_",
            required_tags=["tested", "production"],
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E400"
        assert violations[0].policy_type == "custom"
        assert violations[0].model_name == "gold_customers"
        assert "production" in violations[0].message
        assert violations[0].suggestion is not None

    @pytest.mark.requirement("003b-FR-006")
    def test_model_matching_prefix_with_all_required_tags_passes(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that model matching prefix with all required tags passes.

        Given: gold_customers model with tags ["tested", "documented"]
        When: Rule requires ["tested", "documented"] tags for gold_ prefix
        Then: No violations generated
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTagsForPrefix

        rule = RequireTagsForPrefix(
            prefix="gold_",
            required_tags=["tested", "documented"],
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        assert len(violations) == 0

    @pytest.mark.requirement("003b-FR-006")
    def test_model_not_matching_prefix_is_ignored(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that models not matching prefix are not validated.

        Given: silver_orders, bronze_events, legacy_users models
        When: Rule requires tags for gold_ prefix
        Then: No violations for non-gold_ models
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTagsForPrefix

        rule = RequireTagsForPrefix(
            prefix="gold_",
            required_tags=[
                "production",
                "certified",
            ],  # gold_customers doesn't have these
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        # Only gold_customers should be checked (missing production and certified)
        assert len(violations) == 1
        assert violations[0].model_name == "gold_customers"

    @pytest.mark.requirement("003b-FR-006")
    def test_multiple_required_tags_all_checked(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that all required tags are checked and missing ones are reported.

        Given: bronze_events model with no tags
        When: Rule requires ["tag1", "tag2", "tag3"] for bronze_ prefix
        Then: Violation mentions all missing tags
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTagsForPrefix

        rule = RequireTagsForPrefix(
            prefix="bronze_",
            required_tags=["critical", "monitored"],
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        assert len(violations) == 1
        assert violations[0].model_name == "bronze_events"
        # Message should mention the missing tags
        assert "critical" in violations[0].message or "critical" in str(
            violations[0].expected
        )
        assert "monitored" in violations[0].message or "monitored" in str(
            violations[0].expected
        )

    @pytest.mark.requirement("003b-FR-006")
    def test_applies_to_filters_models(self, valid_manifest: dict[str, Any]) -> None:
        """Test that applies_to glob pattern filters which models are checked.

        Given: Multiple gold_ models (hypothetically)
        When: Rule applies_to="gold_cust*" pattern
        Then: Only matching models are validated
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTagsForPrefix

        rule = RequireTagsForPrefix(
            prefix="gold_",
            required_tags=["nonexistent_tag"],
            applies_to="gold_cust*",  # Only gold_customers matches
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        # Should only check gold_customers (matches gold_cust*)
        assert len(violations) == 1
        assert violations[0].model_name == "gold_customers"


# ==============================================================================
# T024: Tests for require_meta_field Rule (FLOE-E401)
# ==============================================================================


class TestRequireMetaFieldRule:
    """Tests for the require_meta_field custom rule.

    FR-007: System MUST support rule type `require_meta_field`
    to enforce specific meta fields on all/filtered models.
    """

    @pytest.mark.requirement("003b-FR-007")
    def test_model_missing_meta_field_generates_violation(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that model missing required meta field generates FLOE-E401.

        Given: bronze_events model with empty meta
        When: Rule requires "owner" meta field
        Then: FLOE-E401 violation generated
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireMetaField

        rule = RequireMetaField(field="owner")

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        # bronze_events has no owner, legacy_users has empty owner
        model_names = {v.model_name for v in violations}
        assert "bronze_events" in model_names
        assert all(v.error_code == "FLOE-E401" for v in violations)
        assert all(v.policy_type == "custom" for v in violations)

    @pytest.mark.requirement("003b-FR-007")
    def test_model_with_empty_meta_field_and_required_true_generates_violation(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that empty meta field value is treated as missing when required=True.

        Given: legacy_users model with meta.owner="" (empty string)
        When: Rule requires "owner" field with required=True
        Then: FLOE-E401 violation for empty value
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireMetaField

        rule = RequireMetaField(field="owner", required=True)

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        model_names = {v.model_name for v in violations}
        assert "legacy_users" in model_names  # Has empty string owner
        assert "bronze_events" in model_names  # Has no owner at all

    @pytest.mark.requirement("003b-FR-007")
    def test_model_with_empty_meta_field_and_required_false_passes(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that empty meta field value passes when required=False.

        Given: legacy_users model with meta.owner="" (empty string)
        When: Rule requires "owner" field with required=False (just exists)
        Then: No violation for legacy_users (key exists)
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireMetaField

        rule = RequireMetaField(field="owner", required=False)

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        # Only bronze_events should fail (no owner key at all)
        model_names = {v.model_name for v in violations}
        assert "bronze_events" in model_names
        assert "legacy_users" not in model_names  # Has empty owner, but key exists

    @pytest.mark.requirement("003b-FR-007")
    def test_model_with_meta_field_passes(self, valid_manifest: dict[str, Any]) -> None:
        """Test that model with required meta field passes validation.

        Given: gold_customers with meta.owner="data-team@example.com"
        When: Rule requires "owner" meta field
        Then: No violation for gold_customers
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireMetaField

        rule = RequireMetaField(field="owner", applies_to="gold_*")

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        # gold_customers has owner, should pass
        assert len(violations) == 0

    @pytest.mark.requirement("003b-FR-007")
    def test_applies_to_filters_models_for_meta_field(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that applies_to glob pattern filters which models are checked.

        Given: Models with varying meta field presence
        When: Rule applies to gold_* pattern only
        Then: Only gold_ models are validated
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireMetaField

        rule = RequireMetaField(field="nonexistent_field", applies_to="silver_*")

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        # Only silver_orders matches silver_* and is missing nonexistent_field
        assert len(violations) == 1
        assert violations[0].model_name == "silver_orders"


# ==============================================================================
# T025: Tests for require_tests_of_type Rule (FLOE-E402)
# ==============================================================================


class TestRequireTestsOfTypeRule:
    """Tests for the require_tests_of_type custom rule.

    FR-008: System MUST support rule type `require_tests_of_type`
    to enforce specific test types (not_null, unique, etc.).
    """

    @pytest.mark.requirement("003b-FR-008")
    def test_model_missing_required_test_type_generates_violation(
        self, manifest_with_tests: dict[str, Any]
    ) -> None:
        """Test that model missing required test type generates FLOE-E402.

        Given: orders model with no tests
        When: Rule requires not_null test
        Then: FLOE-E402 violation generated for orders
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTestsOfType

        rule = RequireTestsOfType(test_types=["not_null"])

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(manifest_with_tests)

        # orders has no tests
        assert len(violations) == 1
        assert violations[0].error_code == "FLOE-E402"
        assert violations[0].model_name == "orders"
        assert violations[0].policy_type == "custom"

    @pytest.mark.requirement("003b-FR-008")
    def test_model_with_required_test_type_passes(
        self, manifest_with_tests: dict[str, Any]
    ) -> None:
        """Test that model with required test type passes validation.

        Given: customers model with not_null and unique tests
        When: Rule requires not_null test
        Then: No violation for customers
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTestsOfType

        rule = RequireTestsOfType(
            test_types=["not_null"],
            applies_to="customers",  # Only check customers
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(manifest_with_tests)

        assert len(violations) == 0

    @pytest.mark.requirement("003b-FR-008")
    def test_multiple_test_types_required(
        self, manifest_with_tests: dict[str, Any]
    ) -> None:
        """Test that multiple test types can be required.

        Given: customers model with not_null and unique tests
        When: Rule requires both not_null and unique
        Then: No violation for customers
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTestsOfType

        rule = RequireTestsOfType(
            test_types=["not_null", "unique"],
            applies_to="customers",
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(manifest_with_tests)

        assert len(violations) == 0

    @pytest.mark.requirement("003b-FR-008")
    def test_min_columns_threshold_enforced(
        self, manifest_with_tests: dict[str, Any]
    ) -> None:
        """Test that min_columns threshold is respected.

        Given: customers model with 1 column having not_null
        When: Rule requires not_null on min_columns=2
        Then: FLOE-E402 violation (only 1 column has not_null)
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTestsOfType

        rule = RequireTestsOfType(
            test_types=["not_null"],
            min_columns=2,  # Require 2 columns with not_null
            applies_to="customers",
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(manifest_with_tests)

        # customers only has not_null on customer_id (1 column), but requires 2
        assert len(violations) == 1
        assert violations[0].model_name == "customers"
        assert "min_columns" in violations[0].message or "2" in violations[0].message

    @pytest.mark.requirement("003b-FR-008")
    def test_model_missing_one_of_multiple_test_types_generates_violation(
        self, manifest_with_tests: dict[str, Any]
    ) -> None:
        """Test that missing any required test type generates violation.

        Given: customers model with not_null and unique tests
        When: Rule requires not_null, unique, AND accepted_values
        Then: FLOE-E402 for missing accepted_values
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTestsOfType

        rule = RequireTestsOfType(
            test_types=["not_null", "unique", "accepted_values"],
            applies_to="customers",
        )

        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(manifest_with_tests)

        # customers has not_null and unique, but not accepted_values
        assert len(violations) == 1
        assert violations[0].model_name == "customers"
        assert "accepted_values" in violations[0].message


# ==============================================================================
# T026: Tests for Invalid Custom Rule Syntax Error Handling
# ==============================================================================


class TestCustomRuleErrorHandling:
    """Tests for custom rule error handling and edge cases.

    FR-009: System MUST validate custom rule syntax at manifest load time
    and provide clear error messages.
    FR-010: System MUST assign error codes FLOE-E4xx for custom rule violations.
    """

    @pytest.mark.requirement("003b-FR-009")
    def test_empty_custom_rules_list_produces_no_violations(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that empty custom rules list works correctly.

        Given: Valid manifest
        When: CustomRuleValidator initialized with empty rules
        Then: No violations generated
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator

        validator = CustomRuleValidator(custom_rules=[])
        violations = validator.validate(valid_manifest)

        assert len(violations) == 0

    @pytest.mark.requirement("003b-FR-009")
    def test_multiple_rules_all_applied(self, valid_manifest: dict[str, Any]) -> None:
        """Test that multiple custom rules are all applied.

        Given: Valid manifest
        When: Multiple rules configured (tags and meta)
        Then: Violations from all rules are collected
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireMetaField, RequireTagsForPrefix

        rules = [
            RequireTagsForPrefix(prefix="bronze_", required_tags=["raw"]),
            RequireMetaField(field="nonexistent", applies_to="silver_*"),
        ]

        validator = CustomRuleValidator(custom_rules=rules)
        violations = validator.validate(valid_manifest)

        # bronze_events missing "raw" tag, silver_orders missing "nonexistent" meta
        assert len(violations) >= 2
        error_codes = {v.error_code for v in violations}
        assert "FLOE-E400" in error_codes  # Tags violation
        assert "FLOE-E401" in error_codes  # Meta violation

    @pytest.mark.requirement("003b-FR-010")
    def test_all_custom_violations_use_e4xx_error_codes(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that all custom rule violations use FLOE-E4xx codes.

        Given: Valid manifest with violations
        When: All rule types generate violations
        Then: All error codes start with FLOE-E4
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import (
            RequireMetaField,
            RequireTagsForPrefix,
            RequireTestsOfType,
        )

        rules = [
            RequireTagsForPrefix(prefix="bronze_", required_tags=["tag1"]),
            RequireMetaField(field="missing_field", applies_to="silver_*"),
            RequireTestsOfType(test_types=["not_null"], applies_to="legacy_*"),
        ]

        validator = CustomRuleValidator(custom_rules=rules)
        violations = validator.validate(valid_manifest)

        # All violations should have FLOE-E4xx codes
        for violation in violations:
            assert violation.error_code.startswith(
                "FLOE-E4"
            ), f"Custom rule violation has non-E4xx code: {violation.error_code}"

    @pytest.mark.requirement("003b-FR-009")
    def test_applies_to_pattern_matching_edge_cases(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test applies_to pattern matching with edge cases.

        Given: Models with various names
        When: Pattern uses different glob syntax
        Then: Correct models are matched
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireMetaField

        # Test that "*" matches all models
        rule_all = RequireMetaField(field="nonexistent_field", applies_to="*")
        validator_all = CustomRuleValidator(custom_rules=[rule_all])
        violations_all = validator_all.validate(valid_manifest)

        # All 4 models should have violations
        assert len(violations_all) == 4

    @pytest.mark.requirement("003b-FR-009")
    def test_manifest_with_no_models_produces_no_violations(self) -> None:
        """Test that manifest with no models produces no violations.

        Given: Empty manifest (no model nodes)
        When: Custom rules are applied
        Then: No violations generated
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTagsForPrefix

        empty_manifest: dict[str, Any] = {
            "metadata": {"dbt_version": "1.8.0"},
            "nodes": {},
        }

        rule = RequireTagsForPrefix(prefix="gold_", required_tags=["tested"])
        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(empty_manifest)

        assert len(violations) == 0

    @pytest.mark.requirement("003b-FR-010")
    def test_violations_include_policy_type_custom(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that all custom rule violations have policy_type='custom'.

        Given: Manifest with violations
        When: Custom rules generate violations
        Then: All violations have policy_type='custom'
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import RequireTagsForPrefix

        rule = RequireTagsForPrefix(prefix="bronze_", required_tags=["tested"])
        validator = CustomRuleValidator(custom_rules=[rule])
        violations = validator.validate(valid_manifest)

        assert len(violations) >= 1
        for violation in violations:
            assert violation.policy_type == "custom"

    @pytest.mark.requirement("003b-FR-009")
    def test_all_violations_have_suggestions(
        self, valid_manifest: dict[str, Any]
    ) -> None:
        """Test that all custom rule violations include actionable suggestions.

        SC-004: 100% of violations include actionable suggestions.

        Given: Manifest with violations
        When: Custom rules generate violations
        Then: All violations have non-empty suggestion field
        """
        from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        from floe_core.schemas.governance import (
            RequireMetaField,
            RequireTagsForPrefix,
            RequireTestsOfType,
        )

        rules = [
            RequireTagsForPrefix(prefix="bronze_", required_tags=["tag1"]),
            RequireMetaField(field="owner", applies_to="bronze_*"),
            RequireTestsOfType(test_types=["not_null"], applies_to="legacy_*"),
        ]

        validator = CustomRuleValidator(custom_rules=rules)
        violations = validator.validate(valid_manifest)

        # All violations should have suggestions
        for violation in violations:
            assert (
                violation.suggestion is not None
            ), f"Violation {violation.error_code} missing suggestion"
            assert (
                len(violation.suggestion) > 0
            ), f"Violation {violation.error_code} has empty suggestion"
