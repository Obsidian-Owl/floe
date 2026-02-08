"""Import cycle detection tests for floe-core.

This module validates that floe-core can be imported independently
without requiring external plugin packages like floe_rbac_k8s.

Requirements: FR-001
User Story: US1 - Break Circular Dependency (P0)
Task: T006
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest


@pytest.mark.requirement("FR-001")
def test_floe_core_imports_without_rbac_plugin() -> None:
    """Test that floe_core can be imported without floe_rbac_k8s.

    Given floe-core package,
    When I import it in isolation,
    Then no ImportError occurs and no floe_rbac_k8s dependency is required.
    """
    # Run import in subprocess to ensure clean environment
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import floe_core; print('success')",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert (
        result.returncode == 0
    ), f"floe_core import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert "success" in result.stdout


@pytest.mark.requirement("FR-001")
def test_no_direct_k8s_rbac_plugin_import_in_generator() -> None:
    """Test that rbac/generator.py uses only the RBACPlugin ABC.

    Given the rbac/generator.py file,
    When I inspect its imports,
    Then it uses only the RBACPlugin ABC (no direct K8sRBACPlugin import).
    """
    generator_path = (
        Path(__file__).parents[2] / "src" / "floe_core" / "rbac" / "generator.py"
    )
    assert generator_path.exists(), f"generator.py not found at {generator_path}"

    content = generator_path.read_text()
    tree = ast.parse(content)

    forbidden_imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "floe_rbac_k8s" in alias.name:
                    forbidden_imports.append(f"import {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.module and "floe_rbac_k8s" in node.module:
                names = ", ".join(alias.name for alias in node.names)
                forbidden_imports.append(f"from {node.module} import {names}")

    # Filter out TYPE_CHECKING imports (they're acceptable)
    # Check if imports are inside TYPE_CHECKING block by finding line numbers
    type_checking_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # Check if condition is TYPE_CHECKING
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                for child in ast.walk(node):
                    if hasattr(child, "lineno"):
                        type_checking_lines.add(cast(int, child.lineno))

    # Re-check imports excluding TYPE_CHECKING block
    actual_forbidden: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            if hasattr(node, "lineno") and node.lineno in type_checking_lines:
                continue  # Skip TYPE_CHECKING imports

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "floe_rbac_k8s" in alias.name:
                        actual_forbidden.append(
                            f"Line {node.lineno}: import {alias.name}"
                        )

            elif isinstance(node, ast.ImportFrom) and node.module:
                if "floe_rbac_k8s" in node.module:
                    names = ", ".join(alias.name for alias in node.names)
                    msg = f"Line {node.lineno}: from {node.module} import {names}"
                    actual_forbidden.append(msg)

    assert not actual_forbidden, (
        f"generator.py has direct K8sRBACPlugin imports (should use registry):\n"
        f"{chr(10).join(actual_forbidden)}"
    )


@pytest.mark.requirement("FR-001")
def test_no_direct_k8s_rbac_plugin_import_in_cli_generate() -> None:
    """Test that cli/rbac/generate.py retrieves plugin via registry.

    Given the cli/rbac/generate.py file,
    When it needs an RBAC plugin instance,
    Then it retrieves it via the plugin registry lookup (not direct import).
    """
    generate_path = (
        Path(__file__).parents[2] / "src" / "floe_core" / "cli" / "rbac" / "generate.py"
    )
    assert generate_path.exists(), f"generate.py not found at {generate_path}"

    content = generate_path.read_text()
    tree = ast.parse(content)

    # Find all imports of floe_rbac_k8s
    direct_imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "floe_rbac_k8s" in alias.name:
                    direct_imports.append(f"Line {node.lineno}: import {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.module and "floe_rbac_k8s" in node.module:
                names = ", ".join(alias.name for alias in node.names)
                direct_imports.append(
                    f"Line {node.lineno}: from {node.module} import {names}"
                )

    # This test currently documents the CURRENT state (broken)
    # After T008, this test should PASS with no direct imports
    assert not direct_imports, (
        f"cli/rbac/generate.py has direct K8sRBACPlugin imports "
        f"(should use plugin registry):\n"
        f"{chr(10).join(direct_imports)}"
    )


@pytest.mark.requirement("FR-001")
def test_both_packages_import_in_sequence() -> None:
    """Test that both packages can be imported in sequence without cycle.

    Given both floe_core and floe_rbac_k8s packages,
    When I import them in sequence,
    Then no ImportError or circular import warning occurs.
    """
    # Run in subprocess to isolate import state
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import warnings
import sys

# Capture any circular import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")

    # Import floe_core first (the core package)
    import floe_core

    # Try to import floe_rbac_k8s (may not be installed)
    try:
        import floe_rbac_k8s
        print("both_imported")
    except ImportError:
        print("core_only")

    # Check for circular import warnings
    circular_warnings = [
        str(warning.message) for warning in w
        if "circular" in str(warning.message).lower()
        or "cycle" in str(warning.message).lower()
    ]

    if circular_warnings:
        print(f"CIRCULAR_WARNING: {circular_warnings}")
        sys.exit(1)

print("success")
""",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert (
        result.returncode == 0
    ), f"Import sequence test failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    assert "CIRCULAR_WARNING" not in result.stdout
    assert "success" in result.stdout


@pytest.mark.requirement("FR-001")
def test_generator_docstring_no_direct_import_example() -> None:
    """Test that generator.py docstring examples use registry pattern.

    The module docstring example should show registry-based plugin lookup,
    not direct import from floe_rbac_k8s.
    """
    generator_path = (
        Path(__file__).parents[2] / "src" / "floe_core" / "rbac" / "generator.py"
    )
    content = generator_path.read_text()
    tree = ast.parse(content)

    # Get module docstring
    module_docstring = ast.get_docstring(tree)
    assert module_docstring is not None

    # Check if docstring has direct import examples (should be updated)
    # After fix, docstring should show registry pattern instead
    has_direct_import_example = (
        "from floe_rbac_k8s.plugin import K8sRBACPlugin" in module_docstring
    )

    # This test documents the issue - after T007, this should be False
    assert not has_direct_import_example, (
        "generator.py docstring shows direct K8sRBACPlugin import.\n"
        "Docstring should demonstrate registry-based plugin lookup pattern."
    )
