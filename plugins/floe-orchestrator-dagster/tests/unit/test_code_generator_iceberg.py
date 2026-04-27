"""Unit tests for thin loader pattern in generate_entry_point_code().

These tests verify that generate_entry_point_code() emits a thin ~17-line
shim that delegates to load_product_definitions(), rather than the old
187-line inline template with registry imports, Iceberg export, etc.

Requirements Covered:
- AC-7: generate_entry_point_code() emits thin loader pattern
- AC-8: Tests verify the thin pattern, not the old 187-line template

Test Type Rationale:
    All tests are unit tests. generate_entry_point_code() is a pure code
    generation function with no boundary crossing -- it produces a string
    from template interpolation. No mocks needed; we inspect the output string.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


PRODUCT_NAME = "test-product"
"""Shared product name for all tests in this module."""

# Old patterns that MUST NOT appear in generated code.
# Each is a specific symbol from the old 187-line template.
OLD_PATTERNS_FORBIDDEN: list[str] = [
    "_export_dbt_to_iceberg",
    "_load_iceberg_resources",
    "get_registry",
    "CompiledArtifacts",
    "DbtProject",
    "DbtCliResource",
    "dbt_assets",
    "PluginType",
    "load_catalog",
    "pyiceberg",
    "client_id",
    "client_secret",
    "token_url",
    "credential=",
    "scope=",
    "try_create_lineage_resource",
]
"""Symbols from the old 187-line template that must never appear."""


def _generate_code(
    plugin: DagsterOrchestratorPlugin,
    product_name: str = PRODUCT_NAME,
    *,
    iceberg_enabled: bool = False,
    lineage_enabled: bool = False,
) -> str:
    """Generate definitions.py and return its content as a string.

    Args:
        plugin: DagsterOrchestratorPlugin instance.
        product_name: Product name for interpolation.
        iceberg_enabled: Whether Iceberg export is enabled.
        lineage_enabled: Whether lineage is enabled.

    Returns:
        The full generated file content.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = plugin.generate_entry_point_code(
            product_name=product_name,
            output_dir=tmpdir,
            iceberg_enabled=iceberg_enabled,
            lineage_enabled=lineage_enabled,
        )
        return Path(output_path).read_text()


@pytest.mark.requirement("SEC-DAGSTER-CODEGEN")
def test_generated_entry_point_rejects_unsafe_product_name(
    dagster_plugin: DagsterOrchestratorPlugin,
) -> None:
    """Generated Python must reject product names that can break out of strings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="Invalid product_name"):
            dagster_plugin.generate_entry_point_code(
                product_name='bad"; import os; #',
                output_dir=tmpdir,
            )


class TestThinLoaderImport:
    """AC-7: Generated code must import load_product_definitions."""

    @pytest.mark.requirement("AC-7")
    def test_imports_load_product_definitions(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Generated code contains the correct import statement for the loader."""
        code = _generate_code(dagster_plugin)
        assert "from floe_orchestrator_dagster.loader import load_product_definitions" in code, (
            "Generated code must import load_product_definitions from "
            "floe_orchestrator_dagster.loader. "
            f"Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-7")
    def test_import_present_with_iceberg_enabled(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Import is present regardless of iceberg_enabled flag."""
        code = _generate_code(dagster_plugin, iceberg_enabled=True)
        assert "from floe_orchestrator_dagster.loader import load_product_definitions" in code, (
            "Import must be present even when iceberg_enabled=True."
        )

    @pytest.mark.requirement("AC-7")
    def test_import_present_with_lineage_enabled(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Import is present regardless of lineage_enabled flag."""
        code = _generate_code(dagster_plugin, lineage_enabled=True)
        assert "from floe_orchestrator_dagster.loader import load_product_definitions" in code, (
            "Import must be present even when lineage_enabled=True."
        )


class TestThinLoaderDefsCall:
    """AC-7: Generated code must call load_product_definitions with correct args."""

    @pytest.mark.requirement("AC-7")
    def test_defs_assignment_with_product_name(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Generated code assigns defs = load_product_definitions(product_name, ...)."""
        code = _generate_code(dagster_plugin)
        expected = f'defs = load_product_definitions("{PRODUCT_NAME}", PROJECT_DIR)'
        assert expected in code, f"Generated code must contain:\n  {expected}\nActual code:\n{code}"

    @pytest.mark.requirement("AC-7")
    def test_project_dir_defined(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Generated code defines PROJECT_DIR = Path(__file__).parent."""
        code = _generate_code(dagster_plugin)
        assert "PROJECT_DIR = Path(__file__).parent" in code, (
            f"Generated code must define PROJECT_DIR = Path(__file__).parent. Actual code:\n{code}"
        )


class TestProductNameInterpolation:
    """AC-7/AC-8: product_name is correctly interpolated into the generated code."""

    @pytest.mark.requirement("AC-8")
    def test_simple_product_name_interpolated(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """A simple product name appears in the defs= call."""
        name = "my-pipeline"
        code = _generate_code(dagster_plugin, product_name=name)
        expected = f'defs = load_product_definitions("{name}", PROJECT_DIR)'
        assert expected in code, (
            f"Product name '{name}' not interpolated into defs call. Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-8")
    def test_product_name_with_underscores(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Product name with underscores is interpolated correctly."""
        name = "my_data_product"
        code = _generate_code(dagster_plugin, product_name=name)
        expected = f'defs = load_product_definitions("{name}", PROJECT_DIR)'
        assert expected in code, (
            f"Product name '{name}' not interpolated correctly. Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-8")
    def test_product_name_in_docstring(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Product name appears in the module docstring."""
        name = "analytics-pipeline"
        code = _generate_code(dagster_plugin, product_name=name)
        assert name in code.split('"""')[1] if '"""' in code else name in code[:200], (
            f"Product name '{name}' should appear in the module docstring. Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-8")
    def test_product_name_with_dots(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Product name containing dots is rejected before source generation."""
        name = "org.team.pipeline"
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Invalid product_name"):
                dagster_plugin.generate_entry_point_code(product_name=name, output_dir=tmpdir)

    @pytest.mark.requirement("AC-8")
    def test_different_product_names_produce_different_code(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Two different product names produce different generated code.

        Guards against hardcoded product name in the template.
        """
        code_a = _generate_code(dagster_plugin, product_name="alpha-product")
        code_b = _generate_code(dagster_plugin, product_name="beta-product")
        assert code_a != code_b, (
            "Different product names must produce different generated code. "
            "This suggests the product name is hardcoded in the template."
        )
        assert "alpha-product" in code_a
        assert "beta-product" in code_b
        assert "alpha-product" not in code_b
        assert "beta-product" not in code_a


class TestOldPatternsAbsent:
    """AC-7/AC-8: Old 187-line template patterns must NOT appear in generated code."""

    @pytest.mark.requirement("AC-7")
    @pytest.mark.parametrize("old_pattern", OLD_PATTERNS_FORBIDDEN)
    def test_old_pattern_absent_default_flags(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        old_pattern: str,
    ) -> None:
        """Old template symbol must not appear in generated code (default flags)."""
        code = _generate_code(dagster_plugin)
        assert old_pattern not in code, (
            f"Old pattern '{old_pattern}' must NOT appear in generated code. "
            f"The thin loader pattern replaces all inline logic. "
            f"Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-7")
    @pytest.mark.parametrize("old_pattern", OLD_PATTERNS_FORBIDDEN)
    def test_old_pattern_absent_iceberg_enabled(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        old_pattern: str,
    ) -> None:
        """Old template symbol must not appear even when iceberg_enabled=True."""
        code = _generate_code(dagster_plugin, iceberg_enabled=True)
        assert old_pattern not in code, (
            f"Old pattern '{old_pattern}' must NOT appear in generated code "
            f"even when iceberg_enabled=True. The loader handles everything. "
            f"Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-7")
    @pytest.mark.parametrize("old_pattern", OLD_PATTERNS_FORBIDDEN)
    def test_old_pattern_absent_lineage_enabled(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        old_pattern: str,
    ) -> None:
        """Old template symbol must not appear even when lineage_enabled=True."""
        code = _generate_code(dagster_plugin, lineage_enabled=True)
        assert old_pattern not in code, (
            f"Old pattern '{old_pattern}' must NOT appear in generated code "
            f"even when lineage_enabled=True. The loader handles everything. "
            f"Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-7")
    @pytest.mark.parametrize("old_pattern", OLD_PATTERNS_FORBIDDEN)
    def test_old_pattern_absent_both_enabled(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        old_pattern: str,
    ) -> None:
        """Old template symbol must not appear with both flags enabled."""
        code = _generate_code(dagster_plugin, iceberg_enabled=True, lineage_enabled=True)
        assert old_pattern not in code, (
            f"Old pattern '{old_pattern}' must NOT appear in generated code "
            f"with both iceberg and lineage enabled. "
            f"Actual code:\n{code}"
        )


class TestGeneratedCodeBrevity:
    """AC-7: Generated file must be <= 20 lines."""

    @pytest.mark.requirement("AC-7")
    def test_line_count_default_flags(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Generated code must be <= 20 lines with default flags."""
        code = _generate_code(dagster_plugin)
        line_count = len(code.strip().splitlines())
        assert line_count <= 20, (
            f"Generated code must be <= 20 lines, got {line_count}. "
            f"The thin loader pattern should produce ~17 lines. "
            f"Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-7")
    def test_line_count_iceberg_enabled(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Line count unchanged when iceberg_enabled=True (loader handles it)."""
        code_default = _generate_code(dagster_plugin)
        code_iceberg = _generate_code(dagster_plugin, iceberg_enabled=True)
        lines_default = len(code_default.strip().splitlines())
        lines_iceberg = len(code_iceberg.strip().splitlines())
        assert lines_iceberg <= 20, (
            f"Generated code with iceberg_enabled must be <= 20 lines, got {lines_iceberg}."
        )
        assert lines_default == lines_iceberg, (
            f"iceberg_enabled should not change the generated code length. "
            f"Default: {lines_default} lines, Iceberg: {lines_iceberg} lines. "
            f"The loader handles all feature flags at runtime."
        )

    @pytest.mark.requirement("AC-7")
    def test_line_count_lineage_enabled(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Line count unchanged when lineage_enabled=True (loader handles it)."""
        code_default = _generate_code(dagster_plugin)
        code_lineage = _generate_code(dagster_plugin, lineage_enabled=True)
        lines_default = len(code_default.strip().splitlines())
        lines_lineage = len(code_lineage.strip().splitlines())
        assert lines_lineage <= 20, (
            f"Generated code with lineage_enabled must be <= 20 lines, got {lines_lineage}."
        )
        assert lines_default == lines_lineage, (
            f"lineage_enabled should not change the generated code length. "
            f"Default: {lines_default} lines, Lineage: {lines_lineage} lines."
        )


class TestFlagIndependence:
    """AC-7: iceberg_enabled and lineage_enabled have no effect on generated code.

    The thin loader pattern means the generated shim is identical regardless
    of feature flags. The loader reads compiled_artifacts.json at runtime.
    """

    @pytest.mark.requirement("AC-7")
    def test_iceberg_flag_produces_identical_code(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Generated code is identical with iceberg_enabled True vs False."""
        code_off = _generate_code(dagster_plugin, iceberg_enabled=False)
        code_on = _generate_code(dagster_plugin, iceberg_enabled=True)
        assert code_off == code_on, (
            "iceberg_enabled flag must not change generated code. "
            "The loader handles feature flags at runtime.\n"
            f"--- iceberg=False ---\n{code_off}\n"
            f"--- iceberg=True ---\n{code_on}"
        )

    @pytest.mark.requirement("AC-7")
    def test_lineage_flag_produces_identical_code(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Generated code is identical with lineage_enabled True vs False."""
        code_off = _generate_code(dagster_plugin, lineage_enabled=False)
        code_on = _generate_code(dagster_plugin, lineage_enabled=True)
        assert code_off == code_on, (
            "lineage_enabled flag must not change generated code. "
            "The loader handles feature flags at runtime.\n"
            f"--- lineage=False ---\n{code_off}\n"
            f"--- lineage=True ---\n{code_on}"
        )

    @pytest.mark.requirement("AC-7")
    def test_all_flag_combos_produce_identical_code(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """All four combinations of flags produce identical generated code."""
        codes: list[str] = []
        for iceberg in (False, True):
            for lineage in (False, True):
                codes.append(
                    _generate_code(
                        dagster_plugin,
                        iceberg_enabled=iceberg,
                        lineage_enabled=lineage,
                    )
                )
        assert len(set(codes)) == 1, (
            "All four flag combinations must produce identical generated code. "
            f"Got {len(set(codes))} distinct outputs."
        )


class TestGeneratedCodeStructure:
    """AC-7/AC-8: Verify structural properties of the generated thin loader."""

    @pytest.mark.requirement("AC-7")
    def test_contains_future_annotations(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Generated code includes from __future__ import annotations."""
        code = _generate_code(dagster_plugin)
        assert "from __future__ import annotations" in code, (
            "Generated code must include 'from __future__ import annotations'."
        )

    @pytest.mark.requirement("AC-7")
    def test_contains_do_not_edit_warning(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Generated code includes a DO NOT EDIT warning."""
        code = _generate_code(dagster_plugin)
        assert "DO NOT EDIT" in code.upper(), (
            f"Generated code must include a 'DO NOT EDIT' warning. Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-7")
    def test_imports_path(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Generated code imports Path from pathlib."""
        code = _generate_code(dagster_plugin)
        assert "from pathlib import Path" in code, (
            f"Generated code must import Path from pathlib. Actual code:\n{code}"
        )

    @pytest.mark.requirement("AC-8")
    def test_generated_file_is_valid_python(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Generated code compiles as valid Python (syntax check)."""
        code = _generate_code(dagster_plugin)
        try:
            compile(code, "<generated>", "exec")
        except SyntaxError as exc:
            pytest.fail(f"Generated code is not valid Python: {exc}\nCode:\n{code}")

    @pytest.mark.requirement("AC-8")
    def test_defs_is_module_level_variable(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """defs assignment is at module level, not inside a function or class."""
        code = _generate_code(dagster_plugin)
        for line in code.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("defs = load_product_definitions("):
                # The line must be at column 0 (no indentation)
                assert line == stripped, (
                    f"defs assignment must be at module level (no indentation). Found: '{line}'"
                )
                break
        else:
            pytest.fail(
                "No 'defs = load_product_definitions(...)' line found at module level. "
                f"Actual code:\n{code}"
            )

    @pytest.mark.requirement("AC-7")
    def test_output_file_named_definitions_py(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Generated file is named definitions.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = dagster_plugin.generate_entry_point_code(
                product_name=PRODUCT_NAME,
                output_dir=tmpdir,
            )
            assert Path(output_path).name == "definitions.py", (
                f"Generated file must be named definitions.py, got {Path(output_path).name}"
            )

    @pytest.mark.requirement("AC-7")
    def test_contains_regenerate_instructions(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Generated code includes regeneration instructions mentioning floe compile."""
        code = _generate_code(dagster_plugin)
        assert "floe" in code.lower() and "compile" in code.lower(), (
            "Generated code should include regeneration instructions "
            "mentioning 'floe compile'. "
            f"Actual code:\n{code}"
        )


class TestGeneratedCodeExactContent:
    """AC-7/AC-8: Verify the generated code matches the expected thin loader exactly.

    This is the strongest test -- it catches any deviation from the spec template.
    """

    @pytest.mark.requirement("AC-7")
    @pytest.mark.requirement("AC-8")
    def test_exact_functional_lines(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Non-comment, non-blank lines match the expected thin loader exactly.

        We strip the docstring and blank lines to focus on the functional code.
        This catches any extra imports, assignments, or function calls.
        """
        code = _generate_code(dagster_plugin, product_name="my-product")
        # Extract non-blank, non-docstring lines
        lines = code.strip().splitlines()

        # Filter to functional lines (not blank, not inside docstring, not comments)
        functional_lines: list[str] = []
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_docstring:
                    in_docstring = False
                    continue
                # Single-line docstring
                if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                    continue
                in_docstring = True
                continue
            if in_docstring:
                continue
            if not stripped or stripped.startswith("#"):
                continue
            functional_lines.append(stripped)

        expected_functional = [
            "from __future__ import annotations",
            "from pathlib import Path",
            "from floe_orchestrator_dagster.loader import load_product_definitions",
            "PROJECT_DIR = Path(__file__).parent",
            'defs = load_product_definitions("my-product", PROJECT_DIR)',
        ]

        assert functional_lines == expected_functional, (
            "Functional lines do not match expected thin loader.\n"
            "Expected:\n"
            + "\n".join(f"  {line}" for line in expected_functional)
            + "\nActual:\n"
            + "\n".join(f"  {line}" for line in functional_lines)
        )
