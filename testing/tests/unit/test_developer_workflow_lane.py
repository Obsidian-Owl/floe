"""Structural tests for the developer workflow E2E lane."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_E2E_ROOT = _REPO_ROOT / "tests" / "e2e"


def _is_developer_workflow_decorator(decorator: ast.expr) -> bool:
    """Return True when an expression is ``pytest.mark.developer_workflow``."""
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    return (
        isinstance(decorator, ast.Attribute)
        and decorator.attr == "developer_workflow"
        and isinstance(decorator.value, ast.Attribute)
        and decorator.value.attr == "mark"
        and isinstance(decorator.value.value, ast.Name)
        and decorator.value.value.id == "pytest"
    )


def _contains_developer_workflow_mark(expression: ast.expr) -> bool:
    """Return True when an expression contains a developer workflow pytest mark."""
    if _is_developer_workflow_decorator(expression):
        return True
    if isinstance(expression, (ast.List, ast.Tuple, ast.Set)):
        return any(_contains_developer_workflow_mark(element) for element in expression.elts)
    return False


def _has_developer_workflow_mark(expressions: list[ast.expr]) -> bool:
    """Return True when any expression contains a developer workflow pytest mark."""
    return any(_contains_developer_workflow_mark(expression) for expression in expressions)


def _module_has_developer_workflow_pytestmark(tree: ast.Module) -> bool:
    """Return True when module-level ``pytestmark`` selects developer workflow tests."""
    has_developer_workflow_mark = False
    for statement in tree.body:
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(statement, ast.Assign):
            targets = list(statement.targets)
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value = statement.value

        if value is None:
            continue
        if any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets):
            has_developer_workflow_mark = _contains_developer_workflow_mark(value)

    return has_developer_workflow_mark


def _class_index(tree: ast.Module) -> dict[str, ast.ClassDef]:
    """Index classes in a module by class name."""
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def _global_class_index(trees: list[ast.Module]) -> dict[str, ast.ClassDef]:
    """Index unambiguous classes across all scanned modules by class name."""
    candidates: dict[str, ast.ClassDef | None] = {}
    for tree in trees:
        for name, node in _class_index(tree).items():
            if name in candidates:
                candidates[name] = None
            else:
                candidates[name] = node

    resolved: dict[str, ast.ClassDef] = {}
    for name, candidate in candidates.items():
        if candidate is not None:
            resolved[name] = candidate
    return resolved


def _base_class_name(base: ast.expr) -> str | None:
    """Return the simple class name from a base-class expression."""
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    if isinstance(base, ast.Subscript):
        return _base_class_name(base.value)
    return None


def _class_direct_required_services(node: ast.ClassDef) -> list[str] | None:
    """Return literal ``required_services`` entries declared directly on a class."""
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


def _class_required_services(
    node: ast.ClassDef,
    local_class_index: dict[str, ast.ClassDef],
    global_class_index: dict[str, ast.ClassDef],
    seen: set[int] | None = None,
) -> list[str] | None:
    """Return literal ``required_services`` entries declared on or inherited by a class."""
    if seen is None:
        seen = set()
    node_identity = id(node)
    if node_identity in seen:
        return None
    seen.add(node_identity)

    direct_required_services = _class_direct_required_services(node)
    if direct_required_services is not None:
        return direct_required_services

    for base in node.bases:
        base_name = _base_class_name(base)
        if base_name is None:
            continue
        base_node = local_class_index.get(base_name) or global_class_index.get(base_name)
        if base_node is None:
            continue
        inherited_required_services = _class_required_services(
            base_node,
            local_class_index,
            global_class_index,
            seen,
        )
        if inherited_required_services is not None:
            return inherited_required_services

    return None


@pytest.mark.requirement("285")
def test_developer_workflow_guard_catches_async_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lane guard must catch async developer workflow methods."""
    test_file = tmp_path / "test_async_lane.py"
    test_file.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "class TestAsync:",
                "    required_services = ['dagster-webserver']",
                "",
                "    @pytest.mark.developer_workflow",
                "    async def test_async_flow(self):",
                "        pass",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys.modules[__name__], "_E2E_ROOT", tmp_path)

    with pytest.raises(AssertionError, match="TestAsync.test_async_flow"):
        test_developer_workflow_tests_do_not_inherit_service_health_gates()


@pytest.mark.requirement("285")
def test_developer_workflow_guard_catches_called_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lane guard must catch ``@pytest.mark.developer_workflow()``."""
    test_file = tmp_path / "test_called_marker.py"
    test_file.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "class TestCalledMarker:",
                "    required_services = ['dagster-webserver']",
                "",
                "    @pytest.mark.developer_workflow()",
                "    def test_called_marker_flow(self):",
                "        pass",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys.modules[__name__], "_E2E_ROOT", tmp_path)

    with pytest.raises(AssertionError, match="TestCalledMarker.test_called_marker_flow"):
        test_developer_workflow_tests_do_not_inherit_service_health_gates()


@pytest.mark.requirement("285")
def test_developer_workflow_guard_catches_class_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lane guard must catch class-level developer workflow marks."""
    test_file = tmp_path / "test_class_marker.py"
    test_file.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "@pytest.mark.developer_workflow",
                "class TestClassMarker:",
                "    required_services = ['dagster-webserver']",
                "",
                "    def test_class_marker_flow(self):",
                "        pass",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys.modules[__name__], "_E2E_ROOT", tmp_path)

    with pytest.raises(AssertionError, match="TestClassMarker.test_class_marker_flow"):
        test_developer_workflow_tests_do_not_inherit_service_health_gates()


@pytest.mark.requirement("285")
def test_developer_workflow_guard_catches_module_pytestmark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lane guard must catch module-level developer workflow marks."""
    test_file = tmp_path / "test_module_marker.py"
    test_file.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "pytestmark = [pytest.mark.developer_workflow]",
                "",
                "class TestModuleMarker:",
                "    required_services = ['dagster-webserver']",
                "",
                "    def test_module_marker_flow(self):",
                "        pass",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys.modules[__name__], "_E2E_ROOT", tmp_path)

    with pytest.raises(AssertionError, match="TestModuleMarker.test_module_marker_flow"):
        test_developer_workflow_tests_do_not_inherit_service_health_gates()


@pytest.mark.requirement("285")
def test_developer_workflow_guard_honors_final_module_pytestmark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lane guard must use the effective final module-level pytestmark value."""
    test_file = tmp_path / "test_reassigned_module_marker.py"
    test_file.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "pytestmark = [pytest.mark.e2e]",
                "pytestmark = [pytest.mark.developer_workflow]",
                "",
                "class TestReassignedModuleMarker:",
                "    required_services = ['dagster-webserver']",
                "",
                "    def test_reassigned_module_marker_flow(self):",
                "        pass",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys.modules[__name__], "_E2E_ROOT", tmp_path)

    with pytest.raises(
        AssertionError,
        match="TestReassignedModuleMarker.test_reassigned_module_marker_flow",
    ):
        test_developer_workflow_tests_do_not_inherit_service_health_gates()


@pytest.mark.requirement("285")
def test_developer_workflow_guard_catches_inherited_required_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lane guard must catch service gates inherited from base classes."""
    test_file = tmp_path / "test_inherited_gate.py"
    test_file.write_text(
        "\n".join(
            [
                "import pytest",
                "",
                "class ServiceGatedBase:",
                "    required_services = ['dagster-webserver']",
                "",
                "@pytest.mark.developer_workflow",
                "class TestInheritedGate(ServiceGatedBase):",
                "    def test_inherited_gate_flow(self):",
                "        pass",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sys.modules[__name__], "_E2E_ROOT", tmp_path)

    with pytest.raises(AssertionError, match="TestInheritedGate.test_inherited_gate_flow"):
        test_developer_workflow_tests_do_not_inherit_service_health_gates()


@pytest.mark.requirement("285")
def test_developer_workflow_tests_do_not_inherit_service_health_gates() -> None:
    """Developer workflow tests must not require host port-forwards implicitly."""
    offenders: list[str] = []
    parsed_modules = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(_E2E_ROOT.rglob("*.py"))
    }
    global_class_index = _global_class_index(list(parsed_modules.values()))

    for path, tree in parsed_modules.items():
        module_has_developer_workflow_mark = _module_has_developer_workflow_pytestmark(tree)
        local_class_index = _class_index(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            required_services = _class_required_services(
                node,
                local_class_index,
                global_class_index,
            )
            if not required_services:
                continue

            class_has_developer_workflow_mark = _has_developer_workflow_mark(node.decorator_list)
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not child.name.startswith("test_"):
                    continue

                if (
                    module_has_developer_workflow_mark
                    or class_has_developer_workflow_mark
                    or _has_developer_workflow_mark(child.decorator_list)
                ):
                    try:
                        rel_path = path.relative_to(_REPO_ROOT)
                    except ValueError:
                        rel_path = path
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
