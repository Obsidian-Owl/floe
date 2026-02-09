"""Unit tests for policy framework (Task T030).

These tests validate the policy evaluation engine that enforces custom
governance policies defined in manifest.yaml. Tests are written in TDD
style and will fail until the implementation is complete.

Requirements Covered:
- FR-015: Custom policy definitions with name, condition, action, message
- FR-016: Built-in policies (required_tags, naming_convention, max_transforms)
- FR-017: Policy evaluation against dbt manifest with violation reporting
- FR-018: Safe, sandboxed condition evaluation (no eval/exec)
"""

from __future__ import annotations

from typing import Any

import pytest

from floe_core.governance.policy_evaluator import PolicyDefinition, PolicyEvaluator


@pytest.fixture
def policy_manifest() -> dict[str, Any]:
    """Create test dbt manifest with models for policy validation.

    Returns:
        Dict containing dbt manifest with 4 models:
        - gold_customers: fully tagged and documented
        - silver_orders: partially tagged
        - bronze_events: no tags/meta
        - LEGACY_Users: intentionally non-snake_case name
    """
    return {
        "metadata": {
            "project_name": "test_project",
            "dbt_version": "1.5.0",
        },
        "nodes": {
            "model.test_project.gold_customers": {
                "name": "gold_customers",
                "tags": ["tested", "documented"],
                "meta": {
                    "owner": "team-a",
                    "domain": "sales",
                },
            },
            "model.test_project.silver_orders": {
                "name": "silver_orders",
                "tags": ["validated"],
                "meta": {
                    "owner": "team-b",
                },
            },
            "model.test_project.bronze_events": {
                "name": "bronze_events",
                "tags": [],
                "meta": {},
            },
            "model.test_project.LEGACY_Users": {
                "name": "LEGACY_Users",
                "tags": ["deprecated"],
                "meta": {
                    "owner": "team-c",
                },
            },
        },
    }


@pytest.fixture
def compliant_manifest() -> dict[str, Any]:
    """Create test manifest with all models compliant with policies.

    Returns:
        Dict containing dbt manifest with fully compliant models
    """
    return {
        "metadata": {
            "project_name": "test_project",
            "dbt_version": "1.5.0",
        },
        "nodes": {
            "model.test_project.gold_customers": {
                "name": "gold_customers",
                "tags": ["tested", "documented"],
                "meta": {
                    "owner": "team-a",
                    "domain": "sales",
                },
            },
            "model.test_project.silver_orders": {
                "name": "silver_orders",
                "tags": ["tested", "documented"],
                "meta": {
                    "owner": "team-b",
                },
            },
        },
    }


@pytest.mark.requirement("003e-FR-016")
def test_required_tags_violation_detected(policy_manifest: dict[str, Any]) -> None:
    """Test required_tags policy detects missing tags.

    Validates that models missing required tags generate violations with
    correct severity and policy type.
    """
    policies = [
        PolicyDefinition(
            name="require_quality_tags",
            type="required_tags",
            action="error",
            message="Models must have tested and documented tags",
            config={"required_tags": ["tested", "documented"]},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # Expect violations for silver_orders, bronze_events, LEGACY_Users
    assert len(violations) == 3

    # Verify violation structure
    violation_names = {v.model_name for v in violations}
    assert violation_names == {"silver_orders", "bronze_events", "LEGACY_Users"}

    # Verify all violations have correct attributes
    for violation in violations:
        assert violation.policy_type == "custom"
        assert violation.severity == "error"
        assert "tested" in violation.message or "documented" in violation.message


@pytest.mark.requirement("003e-FR-016")
def test_required_tags_all_present_no_violation(
    compliant_manifest: dict[str, Any],
) -> None:
    """Test required_tags policy passes when all tags present.

    Validates that models with all required tags generate no violations.
    """
    policies = [
        PolicyDefinition(
            name="require_quality_tags",
            type="required_tags",
            action="error",
            message="Models must have tested and documented tags",
            config={"required_tags": ["tested", "documented"]},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=compliant_manifest)

    assert len(violations) == 0


@pytest.mark.requirement("003e-FR-016")
def test_naming_convention_violation_detected(policy_manifest: dict[str, Any]) -> None:
    """Test naming_convention policy detects invalid names.

    Validates that models not matching the naming pattern generate violations
    with correct severity (warning for action=warn).
    """
    policies = [
        PolicyDefinition(
            name="enforce_snake_case",
            type="naming_convention",
            action="warn",
            message="Model names must be snake_case",
            config={"pattern": r"^[a-z][a-z0-9_]*$"},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # Expect violation for LEGACY_Users only
    assert len(violations) == 1
    assert violations[0].model_name == "LEGACY_Users"
    assert violations[0].severity == "warning"
    assert violations[0].policy_type == "custom"


@pytest.mark.requirement("003e-FR-016")
def test_naming_convention_all_valid_no_violation(
    compliant_manifest: dict[str, Any],
) -> None:
    """Test naming_convention policy passes with valid names.

    Validates that models matching the naming pattern generate no violations.
    """
    policies = [
        PolicyDefinition(
            name="enforce_snake_case",
            type="naming_convention",
            action="warn",
            message="Model names must be snake_case",
            config={"pattern": r"^[a-z][a-z0-9_]*$"},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=compliant_manifest)

    assert len(violations) == 0


@pytest.mark.requirement("003e-FR-016")
def test_max_transforms_exceeded(policy_manifest: dict[str, Any]) -> None:
    """Test max_transforms policy detects threshold violations.

    Validates that exceeding the maximum transform count generates a violation
    with block action mapped to error severity.
    """
    policies = [
        PolicyDefinition(
            name="limit_model_count",
            type="max_transforms",
            action="block",
            message="Project has too many models",
            config={"threshold": 3},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # 4 models exceeds threshold of 3
    assert len(violations) == 1
    assert violations[0].severity == "error"  # block maps to error
    assert violations[0].policy_type == "custom"
    assert "4" in violations[0].message  # Should mention actual count


@pytest.mark.requirement("003e-FR-016")
def test_max_transforms_within_limit(policy_manifest: dict[str, Any]) -> None:
    """Test max_transforms policy passes within limit.

    Validates that transform count within threshold generates no violations.
    """
    policies = [
        PolicyDefinition(
            name="limit_model_count",
            type="max_transforms",
            action="block",
            message="Project has too many models",
            config={"threshold": 10},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # 4 models within threshold of 10
    assert len(violations) == 0


@pytest.mark.requirement("003e-FR-015")
@pytest.mark.requirement("003e-FR-017")
def test_warn_action_sets_warning_severity(policy_manifest: dict[str, Any]) -> None:
    """Test warn action produces warning severity violations.

    Validates that policy action=warn maps to violation severity=warning.
    """
    policies = [
        PolicyDefinition(
            name="test_warn_policy",
            type="naming_convention",
            action="warn",
            message="This is a warning",
            config={"pattern": r"^[a-z]+$"},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # At least one violation should exist (LEGACY_Users doesn't match)
    assert len(violations) >= 1
    for violation in violations:
        assert violation.severity == "warning"


@pytest.mark.requirement("003e-FR-015")
@pytest.mark.requirement("003e-FR-017")
def test_error_action_sets_error_severity(policy_manifest: dict[str, Any]) -> None:
    """Test error action produces error severity violations.

    Validates that policy action=error maps to violation severity=error.
    """
    policies = [
        PolicyDefinition(
            name="test_error_policy",
            type="required_tags",
            action="error",
            message="This is an error",
            config={"required_tags": ["nonexistent_tag"]},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # All models missing nonexistent_tag
    assert len(violations) == 4
    for violation in violations:
        assert violation.severity == "error"


@pytest.mark.requirement("003e-FR-015")
@pytest.mark.requirement("003e-FR-017")
def test_block_action_sets_error_severity(policy_manifest: dict[str, Any]) -> None:
    """Test block action produces error severity violations.

    Validates that policy action=block maps to violation severity=error
    (distinction between block/error handled at enforcement level).
    """
    policies = [
        PolicyDefinition(
            name="test_block_policy",
            type="max_transforms",
            action="block",
            message="This blocks compilation",
            config={"threshold": 2},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # 4 models exceeds threshold of 2
    assert len(violations) == 1
    assert violations[0].severity == "error"  # block maps to error


@pytest.mark.requirement("003e-FR-015")
def test_empty_policies_no_violations(policy_manifest: dict[str, Any]) -> None:
    """Test evaluator with no policies returns empty violations.

    Validates that an empty policy list produces no violations regardless
    of manifest content.
    """
    evaluator = PolicyEvaluator(policies=[])
    violations = evaluator.evaluate(manifest=policy_manifest)

    assert len(violations) == 0


@pytest.mark.requirement("003e-FR-017")
def test_multiple_policies_combined(policy_manifest: dict[str, Any]) -> None:
    """Test multiple policies evaluated together.

    Validates that violations from all policies are collected and returned
    in a single list.
    """
    policies = [
        PolicyDefinition(
            name="require_tags",
            type="required_tags",
            action="error",
            message="Missing tags",
            config={"required_tags": ["tested"]},
        ),
        PolicyDefinition(
            name="enforce_naming",
            type="naming_convention",
            action="warn",
            message="Invalid name",
            config={"pattern": r"^[a-z][a-z0-9_]*$"},
        ),
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # Should have violations from both policies
    # required_tags: silver_orders (missing "tested"), bronze_events (missing "tested"),
    #   LEGACY_Users (missing "tested") = 3
    # naming_convention: LEGACY_Users invalid = 1
    # Total = 4
    assert len(violations) == 4

    violation_types = {v.severity for v in violations}
    assert "error" in violation_types  # from required_tags
    assert "warning" in violation_types  # from naming_convention


@pytest.mark.requirement("003e-FR-015")
def test_policy_violation_includes_policy_name_in_message(
    policy_manifest: dict[str, Any],
) -> None:
    """Test violation messages include policy name for traceability.

    Validates that violations reference the originating policy name in
    their message for debugging and audit purposes.
    """
    policies = [
        PolicyDefinition(
            name="unique_policy_name_12345",
            type="required_tags",
            action="error",
            message="Custom message from policy",
            config={"required_tags": ["nonexistent"]},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # At least one violation should exist
    assert len(violations) > 0

    # Check that policy name appears in violation message
    for violation in violations:
        assert violation.model_name
        assert "unique_policy_name_12345" in violation.message, (
            f"Policy name should appear in violation message, got: {violation.message}"
        )


@pytest.mark.requirement("003e-FR-015")
def test_policy_definition_validates_action_values() -> None:
    """Test PolicyDefinition rejects invalid action values.

    Validates that Pydantic validation enforces the action literal type
    and rejects invalid values.
    """
    from pydantic import ValidationError

    # Valid actions should work
    for action in ["warn", "error", "block"]:
        policy = PolicyDefinition(
            name="test",
            type="required_tags",
            action=action,  # type: ignore[arg-type]
            message="test",
            config={},
        )
        assert policy.action == action

    # Invalid action should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        PolicyDefinition(
            name="test",
            type="required_tags",
            action="invalid_action",  # type: ignore[arg-type]
            message="test",
            config={},
        )

    # Verify the error is about the action field
    assert "action" in str(exc_info.value).lower()


@pytest.mark.requirement("003e-FR-018")
def test_custom_condition_policy(policy_manifest: dict[str, Any]) -> None:
    """Test custom condition evaluation with safe sandbox.

    Validates that custom condition policies can be evaluated safely without
    using eval/exec, and properly detect violations based on manifest data.
    """
    policies = [
        PolicyDefinition(
            name="require_owner_metadata",
            type="custom",
            action="error",
            message="Models must have owner metadata",
            config={"condition": "model.meta.get('owner') is not None"},
        )
    ]

    evaluator = PolicyEvaluator(policies=policies)
    violations = evaluator.evaluate(manifest=policy_manifest)

    # bronze_events has no owner metadata
    assert len(violations) == 1
    assert violations[0].model_name == "bronze_events"
    assert violations[0].severity == "error"
    assert violations[0].policy_type == "custom"
    assert "owner" in violations[0].message.lower()


# ==============================================================================
# FR-018: Sandbox Escape Security Tests
# ==============================================================================


@pytest.mark.requirement("003e-FR-018")
def test_sandbox_blocks_import_builtin() -> None:
    """Test sandbox blocks __import__ builtin function.

    Validates that __import__('os') raises ValueError because __import__
    is not in the evaluation context.
    """
    from floe_core.governance.policy_evaluator import SafeConditionEvaluator

    evaluator = SafeConditionEvaluator("__import__('os')")
    with pytest.raises(ValueError, match="Undefined variable"):
        evaluator.evaluate({"model": {}})


@pytest.mark.requirement("003e-FR-018")
def test_sandbox_blocks_dangerous_builtins() -> None:
    """Test sandbox blocks dangerous builtin functions like globals().

    Validates that calling undefined dangerous functions raises ValueError
    because they are not in the evaluation context.
    """
    from floe_core.governance.policy_evaluator import SafeConditionEvaluator

    evaluator = SafeConditionEvaluator("globals()")
    with pytest.raises(ValueError, match="Undefined variable"):
        evaluator.evaluate({"model": {}})


@pytest.mark.requirement("003e-FR-018")
def test_sandbox_blocks_compile_builtin() -> None:
    """Test sandbox blocks compile() builtin function.

    Validates that compile() is not available in the evaluation context.
    """
    from floe_core.governance.policy_evaluator import SafeConditionEvaluator

    evaluator = SafeConditionEvaluator("compile('1', '', 'single')")
    with pytest.raises(ValueError, match="Undefined variable"):
        evaluator.evaluate({"model": {}})


@pytest.mark.requirement("003e-FR-018")
def test_sandbox_blocks_lambda() -> None:
    """Test sandbox blocks lambda expressions.

    Validates that lambda is rejected as an unsafe AST node type
    (Lambda is not in the AST whitelist).
    """
    from floe_core.governance.policy_evaluator import SafeConditionEvaluator

    evaluator = SafeConditionEvaluator("(lambda: 1)()")
    with pytest.raises(ValueError, match="Unsafe AST node"):
        evaluator.evaluate({"model": {}})


@pytest.mark.requirement("003e-FR-018")
def test_sandbox_blocks_list_comprehension() -> None:
    """Test sandbox blocks list comprehensions.

    Validates that list comprehensions are rejected as unsafe AST node types
    (ListComp is not in the AST whitelist).
    """
    from floe_core.governance.policy_evaluator import SafeConditionEvaluator

    evaluator = SafeConditionEvaluator("[x for x in [1]]")
    with pytest.raises(ValueError, match="Unsafe AST node"):
        evaluator.evaluate({"model": {}})


@pytest.mark.requirement("003e-FR-018")
def test_sandbox_blocks_import_statement() -> None:
    """Test sandbox blocks import statements.

    Validates that import statements cause SyntaxError since
    ast.parse(mode='eval') rejects statements (only allows expressions).
    """
    from floe_core.governance.policy_evaluator import SafeConditionEvaluator

    with pytest.raises(SyntaxError):
        SafeConditionEvaluator("import os")
