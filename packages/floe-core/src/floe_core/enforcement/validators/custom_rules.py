"""CustomRuleValidator for user-defined policy rules.

Validates models against custom rules defined in manifest.yaml governance config:
- require_tags_for_prefix (FLOE-E400)
- require_meta_field (FLOE-E401)
- require_tests_of_type (FLOE-E402)

Task: T027, T028, T029, T030, T031
Requirements: FR-005 through FR-010 (US2 - Custom Policy Rules)
"""

from __future__ import annotations

import fnmatch
from typing import Any

import structlog

from floe_core.enforcement.result import Violation
from floe_core.schemas.governance import (
    CustomRule,
    RequireMetaField,
    RequireTagsForPrefix,
    RequireTestsOfType,
)

logger = structlog.get_logger(__name__)

# Documentation URLs for custom rule violations
CUSTOM_RULES_DOCS_BASE = "https://floe.dev/docs/enforcement/custom-rules"


class CustomRuleValidator:
    """Validates models against user-defined custom rules.

    CustomRuleValidator applies custom rules from the governance configuration
    to dbt models. It supports three rule types:
    - require_tags_for_prefix: Require specific tags on models matching a prefix
    - require_meta_field: Require a meta field on matching models
    - require_tests_of_type: Require specific test types on model columns

    Example:
        >>> from floe_core.enforcement.validators.custom_rules import CustomRuleValidator
        >>> from floe_core.schemas.governance import RequireTagsForPrefix
        >>>
        >>> rule = RequireTagsForPrefix(prefix="gold_", required_tags=["tested"])
        >>> validator = CustomRuleValidator(custom_rules=[rule])
        >>> violations = validator.validate(manifest)
        >>> for v in violations:
        ...     print(f"{v.error_code}: {v.message}")
    """

    def __init__(self, custom_rules: list[CustomRule]) -> None:
        """Initialize CustomRuleValidator with custom rules.

        Args:
            custom_rules: List of custom rules to apply. Can be empty list.
        """
        self.custom_rules = custom_rules
        self._log = logger.bind(
            component="CustomRuleValidator",
            rule_count=len(custom_rules),
        )

    def validate(self, manifest: dict[str, Any]) -> list[Violation]:
        """Validate all models against custom rules.

        Iterates through all custom rules and applies them to matching models
        in the manifest.

        Args:
            manifest: dbt manifest dictionary with nodes.

        Returns:
            List of Violation objects for all rule violations found.
        """
        violations: list[Violation] = []
        nodes = manifest.get("nodes", {})

        # Extract models only
        models = [
            node for node in nodes.values() if node.get("resource_type") == "model"
        ]

        if not self.custom_rules:
            self._log.debug("no_custom_rules_configured")
            return violations

        for rule in self.custom_rules:
            rule_violations = self._validate_rule(rule, models, manifest)
            violations.extend(rule_violations)

        if violations:
            self._log.info(
                "custom_rule_violations_found",
                count=len(violations),
                by_type={
                    "E400": sum(1 for v in violations if v.error_code == "FLOE-E400"),
                    "E401": sum(1 for v in violations if v.error_code == "FLOE-E401"),
                    "E402": sum(1 for v in violations if v.error_code == "FLOE-E402"),
                },
            )
        else:
            self._log.debug("custom_rule_validation_passed")

        return violations

    def _validate_rule(
        self,
        rule: CustomRule,
        models: list[dict[str, Any]],
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Validate models against a single custom rule.

        Args:
            rule: The custom rule to apply.
            models: List of model nodes from manifest.
            manifest: Full manifest (needed for test type validation).

        Returns:
            List of violations from this rule.
        """
        # Filter models by applies_to pattern
        matching_models = self._filter_models_by_pattern(models, rule.applies_to)

        if isinstance(rule, RequireTagsForPrefix):
            return self._validate_tags_for_prefix(rule, matching_models)
        if isinstance(rule, RequireMetaField):
            return self._validate_meta_field(rule, matching_models)
        # Must be RequireTestsOfType (exhaustive via discriminated union)
        return self._validate_tests_of_type(rule, matching_models, manifest)

    def _filter_models_by_pattern(
        self,
        models: list[dict[str, Any]],
        pattern: str,
    ) -> list[dict[str, Any]]:
        """Filter models by glob pattern.

        Args:
            models: List of model nodes.
            pattern: Glob pattern to match model names.

        Returns:
            List of models matching the pattern.
        """
        return [
            model for model in models if fnmatch.fnmatch(model.get("name", ""), pattern)
        ]

    def _validate_tags_for_prefix(
        self,
        rule: RequireTagsForPrefix,
        models: list[dict[str, Any]],
    ) -> list[Violation]:
        """Validate require_tags_for_prefix rule.

        FR-006: System MUST support rule type `require_tags_for_prefix`
        to enforce tags on models matching prefix patterns.

        Args:
            rule: The RequireTagsForPrefix rule.
            models: Models filtered by applies_to pattern.

        Returns:
            List of FLOE-E400 violations.
        """
        violations: list[Violation] = []

        for model in models:
            model_name = model.get("name", "unknown")

            # Check if model name starts with the prefix
            if not model_name.startswith(rule.prefix):
                continue

            # Check for missing tags
            model_tags = set(model.get("tags", []))
            required_tags = set(rule.required_tags)
            missing_tags = required_tags - model_tags

            if missing_tags:
                violation = self._create_tags_violation(
                    model_name=model_name,
                    prefix=rule.prefix,
                    missing_tags=sorted(missing_tags),
                    required_tags=sorted(required_tags),
                )
                violations.append(violation)

        return violations

    def _validate_meta_field(
        self,
        rule: RequireMetaField,
        models: list[dict[str, Any]],
    ) -> list[Violation]:
        """Validate require_meta_field rule.

        FR-007: System MUST support rule type `require_meta_field`
        to enforce specific meta fields on all/filtered models.

        Args:
            rule: The RequireMetaField rule.
            models: Models filtered by applies_to pattern.

        Returns:
            List of FLOE-E401 violations.
        """
        violations: list[Violation] = []

        for model in models:
            model_name = model.get("name", "unknown")
            meta = model.get("meta", {})

            # Check if field exists
            if rule.field not in meta:
                violation = self._create_meta_field_violation(
                    model_name=model_name,
                    field=rule.field,
                    reason="missing",
                )
                violations.append(violation)
            elif rule.required:
                # Check if field has non-empty value
                value = meta.get(rule.field)
                if not value:  # Empty string, None, etc.
                    violation = self._create_meta_field_violation(
                        model_name=model_name,
                        field=rule.field,
                        reason="empty",
                    )
                    violations.append(violation)

        return violations

    def _validate_tests_of_type(
        self,
        rule: RequireTestsOfType,
        models: list[dict[str, Any]],
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Validate require_tests_of_type rule.

        FR-008: System MUST support rule type `require_tests_of_type`
        to enforce specific test types (not_null, unique, etc.).

        Args:
            rule: The RequireTestsOfType rule.
            models: Models filtered by applies_to pattern.
            manifest: Full manifest to access test nodes.

        Returns:
            List of FLOE-E402 violations.
        """
        violations: list[Violation] = []
        nodes = manifest.get("nodes", {})

        # Build map of model -> test types
        model_tests: dict[str, set[str]] = {}
        for node in nodes.values():
            if node.get("resource_type") != "test":
                continue

            # Get attached model
            attached_node = node.get("attached_node")
            if not attached_node:
                # Fallback: check depends_on
                depends_on = node.get("depends_on", {}).get("nodes", [])
                for dep in depends_on:
                    if dep.startswith("model."):
                        attached_node = dep
                        break

            if attached_node:
                # Extract test type from test_metadata
                test_metadata = node.get("test_metadata", {})
                test_name = test_metadata.get("name", "")
                if test_name:
                    if attached_node not in model_tests:
                        model_tests[attached_node] = set()
                    model_tests[attached_node].add(test_name)

        for model in models:
            model_name = model.get("name", "unknown")
            unique_id = model.get("unique_id", f"model.unknown.{model_name}")

            # Get tests for this model
            model_test_types = model_tests.get(unique_id, set())

            # Check if all required test types are present
            required_tests = set(rule.test_types)
            missing_tests = required_tests - model_test_types

            if missing_tests:
                violation = self._create_tests_violation(
                    model_name=model_name,
                    missing_tests=sorted(missing_tests),
                    required_tests=sorted(required_tests),
                    min_columns=rule.min_columns,
                )
                violations.append(violation)
            elif rule.min_columns > 1:
                # Check min_columns threshold
                # Count how many columns have any of the required test types
                columns_with_tests = self._count_columns_with_tests(
                    unique_id, nodes, required_tests
                )
                if columns_with_tests < rule.min_columns:
                    violation = self._create_min_columns_violation(
                        model_name=model_name,
                        required_tests=sorted(required_tests),
                        min_columns=rule.min_columns,
                        actual_columns=columns_with_tests,
                    )
                    violations.append(violation)

        return violations

    def _count_columns_with_tests(
        self,
        model_unique_id: str,
        nodes: dict[str, Any],
        test_types: set[str],
    ) -> int:
        """Count columns with any of the specified test types.

        Args:
            model_unique_id: The model's unique_id.
            nodes: All nodes from manifest.
            test_types: Set of test types to look for.

        Returns:
            Count of columns with matching tests.
        """
        columns_with_tests: set[str] = set()

        for node in nodes.values():
            if node.get("resource_type") != "test":
                continue

            # Check if test is attached to this model
            attached_node = node.get("attached_node")
            if attached_node != model_unique_id:
                continue

            test_metadata = node.get("test_metadata", {})
            test_name = test_metadata.get("name", "")

            if test_name in test_types:
                # Extract column from test name or kwargs
                column_name = test_metadata.get("kwargs", {}).get("column_name")
                if column_name:
                    columns_with_tests.add(column_name)

        return len(columns_with_tests)

    def _create_tags_violation(
        self,
        model_name: str,
        prefix: str,
        missing_tags: list[str],
        required_tags: list[str],
    ) -> Violation:
        """Create FLOE-E400 violation for missing tags.

        Args:
            model_name: Model that violated the rule.
            prefix: The prefix that triggered the rule.
            missing_tags: Tags that are missing.
            required_tags: All tags that were required.

        Returns:
            Violation with actionable details.
        """
        missing_str = ", ".join(missing_tags)
        required_str = ", ".join(required_tags)

        return Violation(
            error_code="FLOE-E400",
            severity="error",
            policy_type="custom",
            model_name=model_name,
            message=(
                f"Model '{model_name}' with prefix '{prefix}' is missing "
                f"required tags: {missing_str}"
            ),
            expected=f"Tags {required_str} should be present on models with prefix '{prefix}'",
            actual=f"Missing tags: {missing_str}",
            suggestion=(
                f"Add the missing tags to the model in your dbt YAML:\n"
                f"  models:\n"
                f"    - name: {model_name}\n"
                f"      tags: [{', '.join(required_tags)}]"
            ),
            documentation_url=f"{CUSTOM_RULES_DOCS_BASE}#require-tags-for-prefix",
        )

    def _create_meta_field_violation(
        self,
        model_name: str,
        field: str,
        reason: str,
    ) -> Violation:
        """Create FLOE-E401 violation for missing/empty meta field.

        Args:
            model_name: Model that violated the rule.
            field: The meta field that is missing or empty.
            reason: "missing" or "empty".

        Returns:
            Violation with actionable details.
        """
        if reason == "missing":
            message = f"Model '{model_name}' is missing required meta field '{field}'"
            actual = f"Meta field '{field}' is not defined"
        else:
            message = f"Model '{model_name}' has empty value for required meta field '{field}'"
            actual = f"Meta field '{field}' is defined but empty"

        return Violation(
            error_code="FLOE-E401",
            severity="error",
            policy_type="custom",
            model_name=model_name,
            message=message,
            expected=f"Meta field '{field}' should be defined with a non-empty value",
            actual=actual,
            suggestion=(
                f"Add the meta field to the model in your dbt YAML:\n"
                f"  models:\n"
                f"    - name: {model_name}\n"
                f"      meta:\n"
                f"        {field}: <your-value>"
            ),
            documentation_url=f"{CUSTOM_RULES_DOCS_BASE}#require-meta-field",
        )

    def _create_tests_violation(
        self,
        model_name: str,
        missing_tests: list[str],
        required_tests: list[str],
        min_columns: int,
    ) -> Violation:
        """Create FLOE-E402 violation for missing test types.

        Args:
            model_name: Model that violated the rule.
            missing_tests: Test types that are missing.
            required_tests: All test types that were required.
            min_columns: Minimum columns requirement.

        Returns:
            Violation with actionable details.
        """
        missing_str = ", ".join(missing_tests)
        required_str = ", ".join(required_tests)

        return Violation(
            error_code="FLOE-E402",
            severity="error",
            policy_type="custom",
            model_name=model_name,
            message=(
                f"Model '{model_name}' is missing required test types: {missing_str}"
            ),
            expected=(
                f"Tests of type [{required_str}] should exist for at least {min_columns} column(s)"
            ),
            actual=f"Missing test types: {missing_str}",
            suggestion=(
                f"Add the required tests to your model columns:\n"
                f"  models:\n"
                f"    - name: {model_name}\n"
                f"      columns:\n"
                f"        - name: <column_name>\n"
                f"          data_tests:\n"
                + "\n".join(f"            - {t}" for t in required_tests)
            ),
            documentation_url=f"{CUSTOM_RULES_DOCS_BASE}#require-tests-of-type",
        )

    def _create_min_columns_violation(
        self,
        model_name: str,
        required_tests: list[str],
        min_columns: int,
        actual_columns: int,
    ) -> Violation:
        """Create FLOE-E402 violation for insufficient columns with tests.

        Args:
            model_name: Model that violated the rule.
            required_tests: Test types that were required.
            min_columns: Minimum columns requirement.
            actual_columns: Actual columns with required tests.

        Returns:
            Violation with actionable details.
        """
        required_str = ", ".join(required_tests)

        return Violation(
            error_code="FLOE-E402",
            severity="error",
            policy_type="custom",
            model_name=model_name,
            message=(
                f"Model '{model_name}' has {actual_columns} column(s) with required tests, "
                f"but min_columns={min_columns} required"
            ),
            expected=f"At least {min_columns} column(s) should have tests of type [{required_str}]",
            actual=f"Only {actual_columns} column(s) have the required test types",
            suggestion=(
                f"Add tests to more columns. Currently {actual_columns} of {min_columns} "
                f"required columns have [{required_str}] tests."
            ),
            documentation_url=f"{CUSTOM_RULES_DOCS_BASE}#require-tests-of-type",
        )


__all__ = ["CustomRuleValidator"]
