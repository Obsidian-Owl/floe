"""Tests for AC-3: test_plugin_system.py relocated to unit tests.

Verifies that test_plugin_system.py has been moved from tests/e2e/ to
packages/floe-core/tests/unit/plugins/ since it does not require any
E2E infrastructure (no K8s, Docker, or external services).

These are STATIC ANALYSIS tests (file system checks). They do NOT
require K8s or any infrastructure.

Test types:
- File existence checks: verify correct file locations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OLD_PATH = _REPO_ROOT / "tests" / "e2e" / "test_plugin_system.py"
_NEW_PATH = (
    _REPO_ROOT / "packages" / "floe-core" / "tests" / "unit" / "plugins" / "test_plugin_system.py"
)


# =========================================================================
# Tests
# =========================================================================


class TestPluginSystemRelocation:
    """Verify test_plugin_system.py has been relocated correctly."""

    @pytest.mark.requirement("AC-3")
    def test_old_location_removed(self) -> None:
        """test_plugin_system.py must NOT exist in tests/e2e/.

        The file tests only floe-core plugin functionality with no
        infrastructure dependencies. It belongs in package-level unit
        tests, not E2E.
        """
        assert not _OLD_PATH.exists(), (
            f"test_plugin_system.py still exists at {_OLD_PATH.relative_to(_REPO_ROOT)}. "
            "It must be moved to packages/floe-core/tests/unit/plugins/ "
            "because it has no E2E infrastructure dependencies."
        )

    @pytest.mark.requirement("AC-3")
    def test_new_location_exists(self) -> None:
        """test_plugin_system.py must exist in packages/floe-core/tests/unit/plugins/.

        The plugin system tests import only from floe_core and testing
        utilities. They belong with floe-core's unit tests.
        """
        assert _NEW_PATH.exists(), (
            f"test_plugin_system.py not found at "
            f"{_NEW_PATH.relative_to(_REPO_ROOT)}. "
            "It must be moved from tests/e2e/ to this location."
        )

    @pytest.mark.requirement("AC-3")
    def test_new_file_has_no_e2e_markers(self) -> None:
        """Relocated test must not have @pytest.mark.e2e markers.

        After relocation, the test is a unit test. E2E markers would
        cause test selection confusion.
        """
        if not _NEW_PATH.exists():
            pytest.fail("Cannot check markers: file not yet relocated.")

        source = _NEW_PATH.read_text()
        assert "@pytest.mark.e2e" not in source, (
            "Relocated test_plugin_system.py still has @pytest.mark.e2e markers. "
            "These must be removed since it's now a unit test."
        )

    @pytest.mark.requirement("AC-3")
    def test_new_file_has_no_integration_base(self) -> None:
        """Relocated test must not inherit from IntegrationTestBase.

        IntegrationTestBase is for tests requiring external services.
        The plugin system tests run entirely in-process.
        """
        if not _NEW_PATH.exists():
            pytest.fail("Cannot check base class: file not yet relocated.")

        source = _NEW_PATH.read_text()
        assert "IntegrationTestBase" not in source, (
            "Relocated test_plugin_system.py still uses IntegrationTestBase. "
            "It should use a plain test class since no services are required."
        )

    @pytest.mark.requirement("AC-3")
    def test_new_file_is_parseable(self) -> None:
        """Relocated test must be valid Python (no import errors from path changes)."""
        if not _NEW_PATH.exists():
            pytest.fail("Cannot check syntax: file not yet relocated.")

        import ast

        source = _NEW_PATH.read_text()
        try:
            ast.parse(source, filename=str(_NEW_PATH))
        except SyntaxError as exc:
            pytest.fail(f"Relocated file has syntax error: {exc}")

    @pytest.mark.requirement("AC-3")
    def test_new_file_preserves_test_count(self) -> None:
        """Relocated file must have at least as many test methods as original.

        Ensures no tests were accidentally dropped during relocation.
        """
        if not _NEW_PATH.exists():
            pytest.fail("Cannot check test count: file not yet relocated.")

        import ast

        source = _NEW_PATH.read_text()
        tree = ast.parse(source)
        test_count = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    test_count += 1

        # Original has 10 test methods
        assert test_count >= 10, (
            f"Relocated file has {test_count} test methods, expected >= 10. "
            "Tests must not be dropped during relocation."
        )
