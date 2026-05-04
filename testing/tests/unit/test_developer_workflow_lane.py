"""Structural tests for the developer workflow E2E lane."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_E2E_ROOT = _REPO_ROOT / "tests" / "e2e"


def _is_developer_workflow_decorator(decorator: ast.expr) -> bool:
    """Return True when a decorator is ``pytest.mark.developer_workflow``."""
    return (
        isinstance(decorator, ast.Attribute)
        and decorator.attr == "developer_workflow"
        and isinstance(decorator.value, ast.Attribute)
        and decorator.value.attr == "mark"
        and isinstance(decorator.value.value, ast.Name)
        and decorator.value.value.id == "pytest"
    )


def _class_required_services(node: ast.ClassDef) -> list[str] | None:
    """Return literal ``required_services`` entries declared on a class."""
    for statement in node.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign):
            if len(statement.targets) == 1:
                target = statement.targets[0]
                value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            target = statement.target
            value = statement.value

        if not isinstance(target, ast.Name) or target.id != "required_services":
            continue
        if value is None:
            return []
        literal = ast.literal_eval(value)
        if not isinstance(literal, list):
            raise AssertionError(
                f"{node.name}.required_services must be a literal list for lane validation"
            )
        return literal
    return None


@pytest.mark.requirement("285")
def test_developer_workflow_tests_do_not_inherit_service_health_gates() -> None:
    """Developer workflow tests must not require host port-forwards implicitly."""
    offenders: list[str] = []

    for path in sorted(_E2E_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            required_services = _class_required_services(node)
            if not required_services:
                continue

            for child in node.body:
                if not isinstance(child, ast.FunctionDef):
                    continue
                if any(
                    _is_developer_workflow_decorator(decorator)
                    for decorator in child.decorator_list
                ):
                    rel_path = path.relative_to(_REPO_ROOT)
                    offenders.append(
                        f"{rel_path}:{child.lineno} {node.name}.{child.name} "
                        f"inherits required_services={required_services!r}"
                    )

    assert offenders == [], (
        "developer_workflow tests run from the repo workspace and do not set up "
        "host service port-forwards; move the test out of a service-gated class "
        "or remove the unconditional required_services gate:\n"
        + "\n".join(f"  {offender}" for offender in offenders)
    )
