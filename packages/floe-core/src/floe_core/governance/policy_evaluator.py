"""Policy evaluation engine for custom governance policies.

This module implements the PolicyEvaluator that evaluates custom governance
policies defined in manifest.yaml against dbt manifest data. It supports
built-in policy types (required_tags, naming_convention, max_transforms) and
custom condition-based policies using safe AST evaluation.

Task: T032 (Epic 3E: Governance Integration)
Requirements:
- FR-015: Custom policy definitions with name, condition, action, message
- FR-016: Built-in policies (required_tags, naming_convention, max_transforms)
- FR-017: Policy evaluation against dbt manifest with violation reporting
- FR-018: Safe, sandboxed condition evaluation (no eval/exec)
"""

from __future__ import annotations

import ast
import re
from typing import Any, Literal, cast

import structlog

logger = structlog.get_logger(__name__)

from pydantic import BaseModel, ConfigDict, Field

from floe_core.enforcement.result import Violation


class PolicyDefinition(BaseModel):
    """Definition of a custom governance policy.

    PolicyDefinition specifies the policy rules to be evaluated against
    the dbt manifest. Each policy has a type (built-in or custom), an
    action (warn/error/block), and configuration specific to its type.

    Attributes:
        name: Human-readable policy name for identification.
        type: Policy type (required_tags, naming_convention, max_transforms, custom).
        action: Enforcement action (warn, error, block).
        message: Description of the policy violation.
        config: Type-specific configuration (e.g., required_tags, pattern, threshold).

    Example:
        >>> policy = PolicyDefinition(
        ...     name="require_quality_tags",
        ...     type="required_tags",
        ...     action="error",
        ...     message="Models must have tested and documented tags",
        ...     config={"required_tags": ["tested", "documented"]},
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description="Human-readable policy name",
    )
    type: Literal["required_tags", "naming_convention", "max_transforms", "custom"] = Field(
        ...,
        description="Policy type",
    )
    action: Literal["warn", "error", "block"] = Field(
        ...,
        description="Enforcement action (warn, error, block)",
    )
    message: str = Field(
        ...,
        description="Description of the policy violation",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific configuration",
    )


class PolicyEvaluator:
    """Evaluator for custom governance policies.

    PolicyEvaluator takes a list of PolicyDefinition objects and evaluates
    them against a dbt manifest, producing Violation objects for any policy
    failures. It supports built-in policy types and custom condition-based
    policies with safe AST evaluation (no eval/exec).

    Attributes:
        policies: List of policy definitions to evaluate.

    Example:
        >>> policies = [
        ...     PolicyDefinition(
        ...         name="require_quality_tags",
        ...         type="required_tags",
        ...         action="error",
        ...         message="Models must have tested and documented tags",
        ...         config={"required_tags": ["tested", "documented"]},
        ...     ),
        ... ]
        >>> evaluator = PolicyEvaluator(policies=policies)
        >>> violations = evaluator.evaluate(manifest=manifest)
        >>> len(violations)
        3
    """

    def __init__(self, policies: list[PolicyDefinition]) -> None:
        """Initialize PolicyEvaluator with policy definitions.

        Args:
            policies: List of policy definitions to evaluate.
        """
        self.policies = policies

    def evaluate(self, manifest: dict[str, Any]) -> list[Violation]:
        """Evaluate all policies against the dbt manifest.

        Iterates through all models in the manifest and applies each policy,
        collecting violations for any policy failures.

        Args:
            manifest: dbt manifest dictionary with 'nodes' key containing models.

        Returns:
            List of Violation objects for all policy failures.

        Example:
            >>> violations = evaluator.evaluate(manifest)
            >>> for v in violations:
            ...     print(f"{v.model_name}: {v.message}")
            bronze_events: Missing required tags: tested, documented
        """
        violations: list[Violation] = []

        for policy in self.policies:
            violations.extend(self._evaluate_policy(policy, manifest))

        return violations

    def _evaluate_policy(
        self,
        policy: PolicyDefinition,
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Evaluate a single policy against the manifest.

        Args:
            policy: Policy definition to evaluate.
            manifest: dbt manifest dictionary.

        Returns:
            List of violations for this policy.
        """
        if policy.type == "required_tags":
            return self._evaluate_required_tags(policy, manifest)
        elif policy.type == "naming_convention":
            return self._evaluate_naming_convention(policy, manifest)
        elif policy.type == "max_transforms":
            return self._evaluate_max_transforms(policy, manifest)
        elif policy.type == "custom":
            return self._evaluate_custom_condition(policy, manifest)
        return []

    def _evaluate_required_tags(
        self,
        policy: PolicyDefinition,
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Evaluate required_tags policy.

        Checks that each model has all required tags specified in the policy
        configuration.

        Args:
            policy: Policy definition with required_tags in config.
            manifest: dbt manifest dictionary.

        Returns:
            List of violations for models missing required tags.
        """
        violations: list[Violation] = []
        required_tags: list[str] = policy.config.get("required_tags", [])
        severity = self._map_action_to_severity(policy.action)

        for node_id, node in manifest.get("nodes", {}).items():
            if not node_id.startswith("model."):
                continue

            model_name = node.get("name", "")
            model_tags = set(node.get("tags", []))
            missing_tags = [tag for tag in required_tags if tag not in model_tags]

            if missing_tags:
                missing_tags_str = ", ".join(missing_tags)
                violations.append(
                    Violation(
                        error_code="FLOE-E600",
                        severity=severity,
                        policy_type="custom",
                        model_name=model_name,
                        message=f"{policy.message} (Missing tags: {missing_tags_str})",
                        expected=f"Tags: {', '.join(required_tags)}",
                        actual=f"Tags: {', '.join(sorted(model_tags))}",
                        suggestion=f"Add missing tags to {model_name}: {missing_tags_str}",
                        documentation_url="https://floe.dev/docs/governance/required-tags",
                    )
                )

        return violations

    def _evaluate_naming_convention(
        self,
        policy: PolicyDefinition,
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Evaluate naming_convention policy.

        Checks that each model name matches the specified regex pattern.

        Args:
            policy: Policy definition with pattern in config.
            manifest: dbt manifest dictionary.

        Returns:
            List of violations for models not matching the pattern.
        """
        violations: list[Violation] = []
        pattern: str = policy.config.get("pattern", "")
        severity = self._map_action_to_severity(policy.action)

        compiled_pattern = re.compile(pattern)

        for node_id, node in manifest.get("nodes", {}).items():
            if not node_id.startswith("model."):
                continue

            model_name = node.get("name", "")

            if not compiled_pattern.match(model_name):
                violations.append(
                    Violation(
                        error_code="FLOE-E600",
                        severity=severity,
                        policy_type="custom",
                        model_name=model_name,
                        message=f"{policy.message} (Pattern: {pattern})",
                        expected=f"Pattern: {pattern}",
                        actual=f"Name: {model_name}",
                        suggestion=f"Rename {model_name} to match pattern {pattern}",
                        documentation_url="https://floe.dev/docs/governance/naming-convention",
                    )
                )

        return violations

    def _evaluate_max_transforms(
        self,
        policy: PolicyDefinition,
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Evaluate max_transforms policy.

        Checks that the total number of models does not exceed the threshold.

        Args:
            policy: Policy definition with threshold in config.
            manifest: dbt manifest dictionary.

        Returns:
            List with a single violation if threshold is exceeded, empty otherwise.
        """
        violations: list[Violation] = []
        threshold: int = policy.config.get("threshold", 0)
        severity = self._map_action_to_severity(policy.action)

        # Count models in manifest
        model_count = sum(
            1 for node_id in manifest.get("nodes", {}) if node_id.startswith("model.")
        )

        if model_count > threshold:
            violations.append(
                Violation(
                    error_code="FLOE-E600",
                    severity=severity,
                    policy_type="custom",
                    model_name="project",
                    message=f"{policy.message} (Actual: {model_count}, Threshold: {threshold})",
                    expected=f"<= {threshold} models",
                    actual=f"{model_count} models",
                    suggestion=f"Reduce model count to {threshold} or below",
                    documentation_url="https://floe.dev/docs/governance/max-transforms",
                )
            )

        return violations

    def _evaluate_custom_condition(
        self,
        policy: PolicyDefinition,
        manifest: dict[str, Any],
    ) -> list[Violation]:
        """Evaluate custom condition policy.

        Evaluates a custom condition expression against each model using safe
        AST evaluation (no eval/exec). The condition is evaluated with 'model'
        variable bound to the model dictionary.

        Args:
            policy: Policy definition with condition in config.
            manifest: dbt manifest dictionary.

        Returns:
            List of violations for models where condition evaluates to False.
        """
        violations: list[Violation] = []
        condition: str = policy.config.get("condition", "")
        severity = self._map_action_to_severity(policy.action)

        evaluator = SafeConditionEvaluator(condition)

        for node_id, node in manifest.get("nodes", {}).items():
            if not node_id.startswith("model."):
                continue

            model_name = node.get("name", "")

            # Evaluate condition with model bound to the node dictionary
            try:
                if not evaluator.evaluate({"model": node}):
                    violations.append(
                        Violation(
                            error_code="FLOE-E600",
                            severity=severity,
                            policy_type="custom",
                            model_name=model_name,
                            message=f"{policy.message} (Condition: {condition})",
                            expected=f"Condition true: {condition}",
                            actual=f"Condition false for {model_name}",
                            suggestion=f"Ensure {model_name} satisfies: {condition}",
                            documentation_url="https://floe.dev/docs/governance/custom-policies",
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "condition_evaluation_failed",
                    policy_name=policy.name,
                    condition=condition,
                    model_name=model_name,
                    error=str(exc),
                )
                continue

        return violations

    def _map_action_to_severity(self, action: str) -> Literal["error", "warning"]:
        """Map policy action to violation severity.

        Args:
            action: Policy action (warn, error, block).

        Returns:
            Violation severity (warning or error).
        """
        if action == "warn":
            return "warning"
        # Both "error" and "block" map to "error" severity
        return "error"


class SafeConditionEvaluator:
    """Safe evaluator for custom condition expressions.

    SafeConditionEvaluator parses and evaluates Python expressions using AST
    to avoid the security risks of eval/exec. Only safe node types are allowed
    (comparisons, attribute access, method calls, literals, boolean operators).

    Attributes:
        condition: Python expression string to evaluate.

    Example:
        >>> evaluator = SafeConditionEvaluator("model.meta.get('owner') is not None")
        >>> evaluator.evaluate({"model": {"meta": {"owner": "team-a"}}})
        True
        >>> evaluator.evaluate({"model": {"meta": {}}})
        False
    """

    def __init__(self, condition: str) -> None:
        """Initialize SafeConditionEvaluator with a condition expression.

        Args:
            condition: Python expression string to evaluate.
        """
        self.condition = condition
        self._ast_tree = ast.parse(condition, mode="eval")

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate the condition expression in the given context.

        Args:
            context: Dictionary of variables available to the expression
                (e.g., {"model": model_dict}).

        Returns:
            Boolean result of evaluating the condition.

        Raises:
            ValueError: If the condition contains unsafe AST nodes.
        """
        result = self._eval_node(self._ast_tree.body, context)
        return bool(result)

    def _eval_node(self, node: ast.AST, context: dict[str, Any]) -> Any:
        """Recursively evaluate an AST node.

        Args:
            node: AST node to evaluate.
            context: Variable context.

        Returns:
            Result of evaluating the node.

        Raises:
            ValueError: If node type is not allowed.
        """
        if isinstance(node, ast.Constant):
            return node.value

        elif isinstance(node, ast.Name):
            # Only allow specific variable names
            if node.id in context:
                return context[node.id]
            elif node.id in ("None", "True", "False"):
                return {"None": None, "True": True, "False": False}[node.id]
            else:
                raise ValueError(f"Undefined variable: {node.id}")

        elif isinstance(node, ast.Attribute):
            # Evaluate the value (e.g., model.meta)
            obj: Any = self._eval_node(node.value, context)
            attr_name = node.attr
            if isinstance(obj, dict):
                return cast(dict[str, Any], obj).get(attr_name)
            return getattr(obj, attr_name, None)

        elif isinstance(node, ast.Call):
            # Evaluate function calls (e.g., .get('owner'))
            args = [self._eval_node(arg, context) for arg in node.args]

            # Handle method calls like obj.get('key')
            if isinstance(node.func, ast.Attribute):
                call_obj: Any = self._eval_node(node.func.value, context)
                method_name = node.func.attr

                if isinstance(call_obj, dict) and method_name == "get":
                    # Special handling for dict.get(key, default=None)
                    typed_dict: dict[str, Any] = cast(dict[str, Any], call_obj)
                    key: Any = args[0] if args else None
                    default: Any = args[1] if len(args) > 1 else None
                    return typed_dict.get(key, default)

                # Try to call as a regular method
                target: Any = cast(Any, call_obj)
                if hasattr(target, method_name):
                    method: Any = getattr(target, method_name)
                    if callable(method):
                        return method(*args)

            # General callable (not a method)
            func = self._eval_node(node.func, context)
            if callable(func):
                return func(*args)

            raise ValueError("Calling non-callable")

        elif isinstance(node, ast.Compare):
            # Evaluate comparisons (e.g., x is not None, x > 5)
            left = self._eval_node(node.left, context)
            for op, comparator in zip(node.ops, node.comparators, strict=True):
                right = self._eval_node(comparator, context)
                if isinstance(op, ast.Eq):
                    result = left == right
                elif isinstance(op, ast.NotEq):
                    result = left != right
                elif isinstance(op, ast.Lt):
                    result = left < right
                elif isinstance(op, ast.LtE):
                    result = left <= right
                elif isinstance(op, ast.Gt):
                    result = left > right
                elif isinstance(op, ast.GtE):
                    result = left >= right
                elif isinstance(op, ast.Is):
                    result = left is right
                elif isinstance(op, ast.IsNot):
                    result = left is not right
                elif isinstance(op, ast.In):
                    result = left in right
                elif isinstance(op, ast.NotIn):
                    result = left not in right
                else:
                    raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
                if not result:
                    return False
                left = right
            return True

        elif isinstance(node, ast.BoolOp):
            # Evaluate boolean operators (and, or)
            if isinstance(node.op, ast.And):
                return all(self._eval_node(value, context) for value in node.values)
            elif isinstance(node.op, ast.Or):
                return any(self._eval_node(value, context) for value in node.values)
            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

        elif isinstance(node, ast.UnaryOp):
            # Evaluate unary operators (not)
            if isinstance(node.op, ast.Not):
                return not self._eval_node(node.operand, context)
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        else:
            raise ValueError(f"Unsafe AST node type: {type(node).__name__}")
