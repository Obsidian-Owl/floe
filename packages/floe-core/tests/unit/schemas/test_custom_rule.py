"""Unit tests for CustomRule schema validation.

Tests for the CustomRule discriminated union types:
- RequireTagsForPrefix: Require tags on models with specific prefix
- RequireMetaField: Require a meta field on models
- RequireTestsOfType: Require specific test types on columns

Task: T011
Requirements: FR-009
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.schemas.governance import (
    CustomRule,
    RequireMetaField,
    RequireTagsForPrefix,
    RequireTestsOfType,
)


class TestRequireTagsForPrefix:
    """Tests for RequireTagsForPrefix custom rule."""

    @pytest.mark.requirement("003b-FR-009")
    def test_valid_require_tags_for_prefix_rule(self) -> None:
        """Test valid require_tags_for_prefix rule creation.

        Given valid prefix and required_tags,
        When creating a RequireTagsForPrefix rule,
        Then the rule is created with correct values.
        """
        rule = RequireTagsForPrefix(
            prefix="gold_",
            required_tags=["tested", "documented"],
        )

        assert rule.type == "require_tags_for_prefix"
        assert rule.prefix == "gold_"
        assert rule.required_tags == ["tested", "documented"]
        assert rule.applies_to == "*"  # Default value

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tags_with_custom_applies_to(self) -> None:
        """Test require_tags_for_prefix with custom applies_to pattern.

        Given a custom applies_to glob pattern,
        When creating a RequireTagsForPrefix rule,
        Then the applies_to value is stored correctly.
        """
        rule = RequireTagsForPrefix(
            prefix="gold_",
            required_tags=["tested"],
            applies_to="models/gold_*.sql",
        )

        assert rule.applies_to == "models/gold_*.sql"

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tags_missing_prefix_raises_error(self) -> None:
        """Test that missing prefix raises ValidationError.

        Given no prefix provided,
        When creating a RequireTagsForPrefix rule,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireTagsForPrefix(required_tags=["tested"])  # type: ignore[call-arg]

        assert "prefix" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tags_empty_prefix_raises_error(self) -> None:
        """Test that empty prefix raises ValidationError.

        Given an empty prefix string,
        When creating a RequireTagsForPrefix rule,
        Then ValidationError is raised for min_length constraint.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireTagsForPrefix(
                prefix="",
                required_tags=["tested"],
            )

        assert "prefix" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tags_empty_tags_list_raises_error(self) -> None:
        """Test that empty required_tags list raises ValidationError.

        Given an empty required_tags list,
        When creating a RequireTagsForPrefix rule,
        Then ValidationError is raised for min_length constraint.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireTagsForPrefix(
                prefix="gold_",
                required_tags=[],
            )

        assert "required_tags" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tags_missing_required_tags_raises_error(self) -> None:
        """Test that missing required_tags raises ValidationError.

        Given no required_tags provided,
        When creating a RequireTagsForPrefix rule,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireTagsForPrefix(prefix="gold_")  # type: ignore[call-arg]

        assert "required_tags" in str(exc_info.value).lower()


class TestRequireMetaField:
    """Tests for RequireMetaField custom rule."""

    @pytest.mark.requirement("003b-FR-009")
    def test_valid_require_meta_field_rule(self) -> None:
        """Test valid require_meta_field rule creation.

        Given a valid field name,
        When creating a RequireMetaField rule,
        Then the rule is created with correct values.
        """
        rule = RequireMetaField(field="owner")

        assert rule.type == "require_meta_field"
        assert rule.field == "owner"
        assert rule.required is True  # Default value
        assert rule.applies_to == "*"  # Default value

    @pytest.mark.requirement("003b-FR-009")
    def test_require_meta_field_optional(self) -> None:
        """Test require_meta_field with required=False.

        Given required=False,
        When creating a RequireMetaField rule,
        Then the rule allows field to be present but empty.
        """
        rule = RequireMetaField(
            field="description",
            required=False,
        )

        assert rule.required is False

    @pytest.mark.requirement("003b-FR-009")
    def test_require_meta_field_with_custom_applies_to(self) -> None:
        """Test require_meta_field with custom applies_to pattern.

        Given a custom applies_to glob pattern,
        When creating a RequireMetaField rule,
        Then the applies_to value is stored correctly.
        """
        rule = RequireMetaField(
            field="owner",
            applies_to="gold_*",
        )

        assert rule.applies_to == "gold_*"

    @pytest.mark.requirement("003b-FR-009")
    def test_require_meta_field_missing_field_raises_error(self) -> None:
        """Test that missing field raises ValidationError.

        Given no field provided,
        When creating a RequireMetaField rule,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireMetaField()  # type: ignore[call-arg]

        assert "field" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-009")
    def test_require_meta_field_empty_field_raises_error(self) -> None:
        """Test that empty field raises ValidationError.

        Given an empty field string,
        When creating a RequireMetaField rule,
        Then ValidationError is raised for min_length constraint.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireMetaField(field="")

        assert "field" in str(exc_info.value).lower()


class TestRequireTestsOfType:
    """Tests for RequireTestsOfType custom rule."""

    @pytest.mark.requirement("003b-FR-009")
    def test_valid_require_tests_of_type_rule(self) -> None:
        """Test valid require_tests_of_type rule creation.

        Given valid test_types list,
        When creating a RequireTestsOfType rule,
        Then the rule is created with correct values.
        """
        rule = RequireTestsOfType(test_types=["not_null", "unique"])

        assert rule.type == "require_tests_of_type"
        assert rule.test_types == ["not_null", "unique"]
        assert rule.min_columns == 1  # Default value
        assert rule.applies_to == "*"  # Default value

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tests_with_min_columns(self) -> None:
        """Test require_tests_of_type with custom min_columns.

        Given a custom min_columns value,
        When creating a RequireTestsOfType rule,
        Then the min_columns value is stored correctly.
        """
        rule = RequireTestsOfType(
            test_types=["not_null"],
            min_columns=3,
        )

        assert rule.min_columns == 3

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tests_with_custom_applies_to(self) -> None:
        """Test require_tests_of_type with custom applies_to pattern.

        Given a custom applies_to glob pattern,
        When creating a RequireTestsOfType rule,
        Then the applies_to value is stored correctly.
        """
        rule = RequireTestsOfType(
            test_types=["not_null"],
            applies_to="silver_*",
        )

        assert rule.applies_to == "silver_*"

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tests_empty_test_types_raises_error(self) -> None:
        """Test that empty test_types list raises ValidationError.

        Given an empty test_types list,
        When creating a RequireTestsOfType rule,
        Then ValidationError is raised for min_length constraint.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireTestsOfType(test_types=[])

        assert "test_types" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tests_missing_test_types_raises_error(self) -> None:
        """Test that missing test_types raises ValidationError.

        Given no test_types provided,
        When creating a RequireTestsOfType rule,
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireTestsOfType()  # type: ignore[call-arg]

        assert "test_types" in str(exc_info.value).lower()

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tests_min_columns_zero_raises_error(self) -> None:
        """Test that min_columns=0 raises ValidationError.

        Given min_columns=0,
        When creating a RequireTestsOfType rule,
        Then ValidationError is raised for ge=1 constraint.
        """
        with pytest.raises(ValidationError) as exc_info:
            RequireTestsOfType(
                test_types=["not_null"],
                min_columns=0,
            )

        assert "min_columns" in str(exc_info.value).lower()


class TestCustomRuleDiscriminatedUnion:
    """Tests for CustomRule discriminated union type."""

    @pytest.mark.requirement("003b-FR-009")
    def test_custom_rule_discriminator_require_tags(self) -> None:
        """Test CustomRule discriminator with require_tags_for_prefix.

        Given a dict with type='require_tags_for_prefix',
        When parsing as CustomRule,
        Then RequireTagsForPrefix is created.
        """
        from pydantic import TypeAdapter

        adapter: TypeAdapter[CustomRule] = TypeAdapter(CustomRule)
        rule: CustomRule = adapter.validate_python({
            "type": "require_tags_for_prefix",
            "prefix": "gold_",
            "required_tags": ["tested"],
        })

        assert isinstance(rule, RequireTagsForPrefix)
        assert rule.prefix == "gold_"

    @pytest.mark.requirement("003b-FR-009")
    def test_custom_rule_discriminator_require_meta(self) -> None:
        """Test CustomRule discriminator with require_meta_field.

        Given a dict with type='require_meta_field',
        When parsing as CustomRule,
        Then RequireMetaField is created.
        """
        from pydantic import TypeAdapter

        adapter: TypeAdapter[CustomRule] = TypeAdapter(CustomRule)
        rule: CustomRule = adapter.validate_python({
            "type": "require_meta_field",
            "field": "owner",
        })

        assert isinstance(rule, RequireMetaField)
        assert rule.field == "owner"

    @pytest.mark.requirement("003b-FR-009")
    def test_custom_rule_discriminator_require_tests(self) -> None:
        """Test CustomRule discriminator with require_tests_of_type.

        Given a dict with type='require_tests_of_type',
        When parsing as CustomRule,
        Then RequireTestsOfType is created.
        """
        from pydantic import TypeAdapter

        adapter: TypeAdapter[CustomRule] = TypeAdapter(CustomRule)
        rule: CustomRule = adapter.validate_python({
            "type": "require_tests_of_type",
            "test_types": ["not_null", "unique"],
        })

        assert isinstance(rule, RequireTestsOfType)
        assert rule.test_types == ["not_null", "unique"]

    @pytest.mark.requirement("003b-FR-009")
    def test_custom_rule_invalid_type_raises_error(self) -> None:
        """Test that invalid rule type raises ValidationError.

        Given a dict with an invalid type value,
        When parsing as CustomRule,
        Then ValidationError is raised.
        """
        from pydantic import TypeAdapter

        adapter: TypeAdapter[CustomRule] = TypeAdapter(CustomRule)
        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_python({
                "type": "invalid_rule_type",
                "field": "owner",
            })

        # Should mention the invalid discriminator value
        error_str = str(exc_info.value).lower()
        assert "invalid_rule_type" in error_str or "discriminator" in error_str

    @pytest.mark.requirement("003b-FR-009")
    def test_custom_rule_missing_type_raises_error(self) -> None:
        """Test that missing type raises ValidationError.

        Given a dict without type field,
        When parsing as CustomRule,
        Then ValidationError is raised.
        """
        from pydantic import TypeAdapter

        adapter: TypeAdapter[CustomRule] = TypeAdapter(CustomRule)
        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_python({
                "field": "owner",
            })

        # Should mention missing discriminator
        error_str = str(exc_info.value).lower()
        assert "type" in error_str or "discriminator" in error_str


class TestCustomRuleFrozenModel:
    """Tests for CustomRule model immutability."""

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tags_is_frozen(self) -> None:
        """Test that RequireTagsForPrefix is immutable.

        Given a RequireTagsForPrefix rule,
        When checking the model config,
        Then frozen=True is confirmed.
        """
        rule = RequireTagsForPrefix(
            prefix="gold_",
            required_tags=["tested"],
        )

        # Verify frozen config is set
        assert rule.model_config.get("frozen") is True

    @pytest.mark.requirement("003b-FR-009")
    def test_require_meta_field_is_frozen(self) -> None:
        """Test that RequireMetaField is immutable.

        Given a RequireMetaField rule,
        When checking the model config,
        Then frozen=True is confirmed.
        """
        rule = RequireMetaField(field="owner")

        # Verify frozen config is set
        assert rule.model_config.get("frozen") is True

    @pytest.mark.requirement("003b-FR-009")
    def test_require_tests_is_frozen(self) -> None:
        """Test that RequireTestsOfType is immutable.

        Given a RequireTestsOfType rule,
        When checking the model config,
        Then frozen=True is confirmed.
        """
        rule = RequireTestsOfType(test_types=["not_null"])

        # Verify frozen config is set
        assert rule.model_config.get("frozen") is True
