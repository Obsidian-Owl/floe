"""Structural tests: test_helm_upgrade_e2e.py uses flux_suspended fixture (AC-5).

Tests verify that the E2E helm upgrade test file:
1. Imports ``flux_suspended`` from ``testing.fixtures.flux``
2. Wires ``flux_suspended`` as a fixture dependency on ``test_helm_upgrade_succeeds``
3. Does NOT wire ``flux_suspended`` on read-only tests (no helm upgrade calls)

These are structural tests that parse source code to verify wiring that cannot
be tested via import alone.  A sloppy implementation that omits the fixture
import or wires it on the wrong tests would fail these tests.

Acceptance Criteria Covered:
    AC-5: test_helm_upgrade_e2e uses flux_suspended

Test Type Rationale:
    Unit (structural) -- reads source text to verify fixture wiring.
    No external services required.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UPGRADE_TEST_PATH = _REPO_ROOT / "tests" / "e2e" / "test_helm_upgrade_e2e.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upgrade_test_source() -> str:
    """Read test_helm_upgrade_e2e.py source text.

    Returns:
        Full source text of the E2E helm upgrade test file.

    Raises:
        FileNotFoundError: If the file does not exist at expected path.
    """
    return _UPGRADE_TEST_PATH.read_text()


def _parse_ast() -> ast.Module:
    """Parse the test file into an AST.

    Returns:
        Parsed AST module node.
    """
    source = _upgrade_test_source()
    return ast.parse(source)


def _get_function_params(tree: ast.Module, func_name: str) -> list[str]:
    """Extract parameter names for a function or method by name.

    Searches all classes and top-level functions.  Returns parameter names
    excluding ``self``.

    Args:
        tree: Parsed AST module.
        func_name: Name of the function/method to find.

    Returns:
        List of parameter names (excluding self).

    Raises:
        ValueError: If the function is not found.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                return [arg.arg for arg in node.args.args if arg.arg != "self"]
    msg = f"Function '{func_name}' not found in AST"
    raise ValueError(msg)


def _get_usefixtures_markers(tree: ast.Module, func_name: str) -> list[str]:
    """Extract fixture names from @pytest.mark.usefixtures decorators.

    Args:
        tree: Parsed AST module.
        func_name: Name of the function/method to find.

    Returns:
        List of fixture names referenced in usefixtures markers.

    Raises:
        ValueError: If the function is not found.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                fixtures: list[str] = []
                for decorator in node.decorator_list:
                    # Match @pytest.mark.usefixtures("flux_suspended")
                    if isinstance(decorator, ast.Call):
                        func = decorator.func
                        if isinstance(func, ast.Attribute) and func.attr == "usefixtures":
                            for arg in decorator.args:
                                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                    fixtures.append(arg.value)
                return fixtures
    msg = f"Function '{func_name}' not found in AST"
    raise ValueError(msg)


def _function_has_flux_suspended(tree: ast.Module, func_name: str) -> bool:
    """Check if a function has flux_suspended as fixture dependency.

    Checks both parameter injection and @pytest.mark.usefixtures.

    Args:
        tree: Parsed AST module.
        func_name: Function name.

    Returns:
        True if flux_suspended is a dependency.
    """
    params = _get_function_params(tree, func_name)
    if "flux_suspended" in params:
        return True
    markers = _get_usefixtures_markers(tree, func_name)
    return "flux_suspended" in markers


# ===========================================================================
# AC-5 STRUCTURAL: Import wiring
# ===========================================================================


class TestHelmUpgradeFluxImport:
    """Structural tests for flux_suspended import in test_helm_upgrade_e2e.py."""

    @pytest.mark.requirement("AC-5")
    def test_imports_flux_suspended_from_testing_fixtures_flux(self) -> None:
        """test_helm_upgrade_e2e.py imports flux_suspended from testing.fixtures.flux.

        Without this import, the fixture cannot be resolved by pytest.
        The import must reference the canonical location: ``testing.fixtures.flux``.
        """
        source = _upgrade_test_source()

        # Check for import statement -- either 'from testing.fixtures.flux import flux_suspended'
        # or 'from testing.fixtures.flux import ... flux_suspended ...'
        import_pattern = re.compile(
            r"from\s+testing\.fixtures\.flux\s+import\s+.*\bflux_suspended\b",
        )
        assert import_pattern.search(source), (
            "test_helm_upgrade_e2e.py must import 'flux_suspended' from "
            "'testing.fixtures.flux'. No matching import found.\n"
            "Expected pattern: from testing.fixtures.flux import flux_suspended"
        )

    @pytest.mark.requirement("AC-5")
    def test_flux_suspended_not_imported_from_wrong_module(self) -> None:
        """flux_suspended must not be imported from a different module.

        A sloppy implementation might define flux_suspended locally or import
        it from conftest. The canonical source is testing.fixtures.flux.
        """
        source = _upgrade_test_source()
        tree = _parse_ast()

        # Collect all import sources for flux_suspended
        wrong_imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module != "testing.fixtures.flux":
                    if node.names:
                        for alias in node.names:
                            if alias.name == "flux_suspended":
                                wrong_imports.append(node.module)

        # Also check for a local def flux_suspended (shadowing the import)
        local_def = re.search(
            r"^def\s+flux_suspended\s*\(",
            source,
            re.MULTILINE,
        )

        assert not wrong_imports, (
            f"flux_suspended imported from wrong module(s): {wrong_imports}. "
            "Must import from testing.fixtures.flux."
        )
        assert local_def is None, (
            "flux_suspended must NOT be defined locally in the test file. "
            "It must be imported from testing.fixtures.flux."
        )


# ===========================================================================
# AC-5 STRUCTURAL: Fixture wiring on test_helm_upgrade_succeeds
# ===========================================================================


class TestHelmUpgradeSucceedsHasFluxSuspended:
    """Verify test_helm_upgrade_succeeds declares flux_suspended dependency."""

    @pytest.mark.requirement("AC-5")
    def test_helm_upgrade_succeeds_has_flux_suspended(self) -> None:
        """test_helm_upgrade_succeeds must depend on flux_suspended fixture.

        This is the test that calls ``helm upgrade``. Without flux_suspended,
        Flux would reconcile the release mid-upgrade, causing race conditions.

        The dependency can be via parameter injection or @pytest.mark.usefixtures.
        """
        tree = _parse_ast()
        has_fixture = _function_has_flux_suspended(tree, "test_helm_upgrade_succeeds")
        assert has_fixture, (
            "test_helm_upgrade_succeeds must have 'flux_suspended' as a "
            "fixture dependency (either as a parameter or via "
            "@pytest.mark.usefixtures('flux_suspended')). "
            "This ensures Flux reconciliation is suspended during helm upgrade."
        )


# ===========================================================================
# AC-5 STRUCTURAL: Read-only tests must NOT have flux_suspended
# ===========================================================================


class TestFluxSuspendedNotOnClass:
    """Verify flux_suspended is NOT applied at the class level.

    A sloppy implementation might add @pytest.mark.usefixtures("flux_suspended")
    to the TestHelmUpgrade class, which would apply the fixture to ALL methods
    at runtime -- including read-only tests that don't need it.
    """

    @pytest.mark.requirement("AC-5")
    def test_class_does_not_have_flux_suspended_usefixtures(self) -> None:
        """TestHelmUpgrade class must NOT have flux_suspended in usefixtures.

        The fixture should be on the individual method, not the class.
        Class-level application would suspend Flux for read-only tests too.
        """
        tree = _parse_ast()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TestHelmUpgrade":
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        func = decorator.func
                        if isinstance(func, ast.Attribute) and func.attr == "usefixtures":
                            for arg in decorator.args:
                                if isinstance(arg, ast.Constant) and arg.value == "flux_suspended":
                                    pytest.fail(
                                        "TestHelmUpgrade class must NOT have "
                                        "@pytest.mark.usefixtures('flux_suspended'). "
                                        "Apply the fixture only to test_helm_upgrade_succeeds."
                                    )
                return  # Found class, checked decorators
        pytest.fail("TestHelmUpgrade class not found in test_helm_upgrade_e2e.py")


class TestReadOnlyTestsDoNotHaveFluxSuspended:
    """Verify read-only tests do not depend on flux_suspended.

    Only tests that mutate via helm upgrade/install need Flux suspended.
    Read-only tests that just inspect cluster state should NOT have the
    fixture -- adding it would cause unnecessary Flux suspend/resume cycles.
    """

    @pytest.mark.requirement("AC-5")
    def test_no_crashloopbackoff_after_upgrade_no_flux_suspended(self) -> None:
        """test_no_crashloopbackoff_after_upgrade must not depend on flux_suspended.

        This test only reads pod status. Suspending Flux is unnecessary.
        """
        tree = _parse_ast()
        has_fixture = _function_has_flux_suspended(tree, "test_no_crashloopbackoff_after_upgrade")
        assert not has_fixture, (
            "test_no_crashloopbackoff_after_upgrade is a read-only test and "
            "must NOT depend on flux_suspended."
        )

    @pytest.mark.requirement("AC-5")
    def test_services_healthy_after_upgrade_no_flux_suspended(self) -> None:
        """test_services_healthy_after_upgrade must not depend on flux_suspended.

        This test only reads pod readiness. Suspending Flux is unnecessary.
        """
        tree = _parse_ast()
        has_fixture = _function_has_flux_suspended(tree, "test_services_healthy_after_upgrade")
        assert not has_fixture, (
            "test_services_healthy_after_upgrade is a read-only test and "
            "must NOT depend on flux_suspended."
        )

    @pytest.mark.requirement("AC-5")
    def test_helm_history_shows_revisions_no_flux_suspended(self) -> None:
        """test_helm_history_shows_revisions must not depend on flux_suspended.

        This test only reads helm history. Suspending Flux is unnecessary.
        """
        tree = _parse_ast()
        has_fixture = _function_has_flux_suspended(tree, "test_helm_history_shows_revisions")
        assert not has_fixture, (
            "test_helm_history_shows_revisions is a read-only test and "
            "must NOT depend on flux_suspended."
        )

    @pytest.mark.requirement("AC-5")
    def test_only_upgrade_test_has_flux_suspended(self) -> None:
        """Exactly one test method has flux_suspended: test_helm_upgrade_succeeds.

        A sloppy implementation might add flux_suspended to all tests in the
        class. This test ensures surgical application: only the test that
        actually calls helm upgrade gets the fixture.
        """
        tree = _parse_ast()

        tests_with_fixture: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    if _function_has_flux_suspended(tree, node.name):
                        tests_with_fixture.append(node.name)

        assert tests_with_fixture == ["test_helm_upgrade_succeeds"], (
            f"Expected exactly ['test_helm_upgrade_succeeds'] to have "
            f"flux_suspended fixture, but found: {tests_with_fixture}. "
            f"Only the test that calls helm upgrade should have this fixture."
        )
