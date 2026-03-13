"""Unit tests for custom dbt table materialization macro and get_dbt_macro_paths().

These tests validate:
- AC-1.1: Custom table materialization macro content and structure
- AC-1.2: ComputePlugin ABC has get_dbt_macro_paths() with default []
- AC-1.3: DuckDBComputePlugin overrides get_dbt_macro_paths() correctly

The macro must:
- Use DROP + CTAS instead of rename-swap (DuckDB Iceberg limitation)
- Preserve all standard dbt features (hooks, grants, docs)
- Declare itself for the duckdb adapter with sql+python support
"""

from __future__ import annotations

from pathlib import Path

import pytest
from floe_core.plugins.compute import ComputePlugin

from floe_compute_duckdb.plugin import DuckDBComputePlugin

# Resolve the macro file path relative to the floe_compute_duckdb package.
# This ensures tests work regardless of working directory.
_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "floe_compute_duckdb"
_MACRO_DIR = _PACKAGE_ROOT / "dbt_macros" / "materializations"
_TABLE_MACRO_PATH = _MACRO_DIR / "table.sql"


def _read_macro() -> str:
    """Read the table materialization macro file content.

    Returns:
        The full text content of the macro file.

    Raises:
        FileNotFoundError: If the macro file does not exist.
    """
    return _TABLE_MACRO_PATH.read_text()


class TestMacroFileExists:
    """Test that the macro file exists at the expected path."""

    @pytest.mark.requirement("AC-1.1")
    def test_macro_file_exists(self) -> None:
        """Test macro file exists at dbt_macros/materializations/table.sql.

        AC-1.1: File exists at the expected path within the package.
        """
        assert _TABLE_MACRO_PATH.exists(), (
            f"Macro file not found at {_TABLE_MACRO_PATH}. "
            "Expected: plugins/floe-compute-duckdb/src/floe_compute_duckdb/"
            "dbt_macros/materializations/table.sql"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_macro_file_is_not_empty(self) -> None:
        """Test macro file is not an empty placeholder.

        A zero-byte file would pass the existence check but is not a
        valid materialization macro.
        """
        content = _read_macro()
        assert len(content.strip()) > 0, "Macro file exists but is empty"


class TestMaterializationDeclaration:
    """Test the materialization declaration header and footer."""

    @pytest.mark.requirement("AC-1.1")
    def test_materialization_declaration_present(self) -> None:
        """Test macro declares materialization for duckdb adapter.

        The declaration must specify adapter='duckdb' and support
        both sql and python languages.
        """
        content = _read_macro()
        assert "{% materialization table" in content, "Missing {% materialization table declaration"

    @pytest.mark.requirement("AC-1.1")
    def test_materialization_targets_duckdb_adapter(self) -> None:
        """Test materialization is scoped to the duckdb adapter.

        Without adapter='duckdb', the macro would override the default
        table materialization for ALL adapters.
        """
        content = _read_macro()
        assert "adapter='duckdb'" in content, "Materialization must target adapter='duckdb'"

    @pytest.mark.requirement("AC-1.1")
    def test_materialization_supports_sql_language(self) -> None:
        """Test materialization declares SQL language support."""
        content = _read_macro()
        assert "supported_languages=" in content, "Missing supported_languages parameter"
        assert "'sql'" in content, "Materialization must support 'sql' language"

    @pytest.mark.requirement("AC-1.1")
    def test_materialization_supports_python_language(self) -> None:
        """Test materialization declares Python language support."""
        content = _read_macro()
        assert "'python'" in content, "Materialization must support 'python' language"

    @pytest.mark.requirement("AC-1.1")
    def test_materialization_declaration_complete(self) -> None:
        """Test the full materialization declaration line matches spec exactly.

        Validates the entire declaration signature to prevent partial matches
        from a sloppy implementation that includes the keywords but not in
        the correct Jinja2 declaration syntax.
        """
        content = _read_macro()
        # Must have the full declaration on a single logical line
        assert (
            "{% materialization table, adapter='duckdb', supported_languages=['sql', 'python'] %}"
            in content
        ), (
            "Full materialization declaration does not match expected format: "
            "{% materialization table, adapter='duckdb', "
            "supported_languages=['sql', 'python'] %}"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_endmaterialization_present(self) -> None:
        """Test macro contains endmaterialization closing tag.

        Without this, the Jinja2 block is unclosed and dbt will fail
        at compile time.
        """
        content = _read_macro()
        assert "{% endmaterialization %}" in content, "Missing {% endmaterialization %} closing tag"

    @pytest.mark.requirement("AC-1.1")
    def test_endmaterialization_after_declaration(self) -> None:
        """Test endmaterialization appears AFTER the opening declaration.

        Catches reversed or duplicated blocks.
        """
        content = _read_macro()
        decl_pos = content.find("{% materialization table")
        end_pos = content.find("{% endmaterialization %}")
        assert decl_pos >= 0, "Missing materialization declaration"
        assert end_pos >= 0, "Missing endmaterialization"
        assert end_pos > decl_pos, (
            "{% endmaterialization %} must appear after {% materialization table ... %}"
        )


class TestForbiddenPatterns:
    """Test that the macro does NOT contain unsupported operations.

    DuckDB's Iceberg extension does not support rename_relation.
    The macro must use DROP + CTAS instead of the standard
    rename-swap pattern used by most dbt adapters.
    """

    @pytest.mark.requirement("AC-1.1")
    def test_no_rename_relation(self) -> None:
        """Test macro does NOT contain adapter.rename_relation.

        adapter.rename_relation is not supported by DuckDB's Iceberg
        extension and will cause runtime errors.
        """
        content = _read_macro()
        assert "adapter.rename_relation" not in content, (
            "Macro must NOT contain adapter.rename_relation (unsupported by DuckDB Iceberg)"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_no_rename_relation_jinja_call(self) -> None:
        """Test macro does NOT call rename_relation via Jinja2 syntax.

        Catches alternate Jinja2 invocations like
        {{ adapter.rename_relation(...) }}.
        """
        content = _read_macro()
        assert "rename_relation" not in content, (
            "Macro must not reference rename_relation in any form"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_no_intermediate_relation(self) -> None:
        """Test macro does NOT reference intermediate_relation.

        intermediate_relation is part of the rename-swap pattern
        that this macro replaces.
        """
        content = _read_macro()
        assert "intermediate_relation" not in content, (
            "Macro must NOT reference intermediate_relation (part of the rename-swap pattern)"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_no_backup_relation(self) -> None:
        """Test macro does NOT reference backup_relation.

        backup_relation is part of the rename-swap pattern
        that this macro replaces.
        """
        content = _read_macro()
        assert "backup_relation" not in content, (
            "Macro must NOT reference backup_relation (part of the rename-swap pattern)"
        )


class TestRequiredPatterns:
    """Test that the macro contains all required dbt operations.

    The DROP + CTAS pattern requires drop_relation and create_table_as.
    Standard dbt features (hooks, grants, docs) must be preserved.
    """

    @pytest.mark.requirement("AC-1.1")
    def test_contains_drop_relation(self) -> None:
        """Test macro contains adapter.drop_relation for DROP existing.

        The macro must DROP the existing table before CREATE to avoid
        the unsupported rename-swap.
        """
        content = _read_macro()
        assert "adapter.drop_relation" in content, (
            "Macro must contain adapter.drop_relation (DROP existing before CREATE)"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_contains_create_table_as(self) -> None:
        """Test macro contains create_table_as for CTAS operation.

        create_table_as is the standard dbt macro for CREATE TABLE AS SELECT.
        """
        content = _read_macro()
        assert "create_table_as" in content, (
            "Macro must contain create_table_as (CTAS for new table)"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_contains_pre_hooks(self) -> None:
        """Test macro runs pre-hooks before materialization.

        Pre-hooks are a core dbt feature that must be preserved.
        """
        content = _read_macro()
        assert "run_hooks(pre_hooks" in content, (
            "Macro must contain run_hooks(pre_hooks for hook support"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_contains_post_hooks(self) -> None:
        """Test macro runs post-hooks after materialization.

        Post-hooks are a core dbt feature that must be preserved.
        """
        content = _read_macro()
        assert "run_hooks(post_hooks" in content, (
            "Macro must contain run_hooks(post_hooks for hook support"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_contains_apply_grants(self) -> None:
        """Test macro applies grants after materialization.

        Grant support is a core dbt feature that must be preserved.
        """
        content = _read_macro()
        assert "apply_grants" in content, "Macro must contain apply_grants for grant support"

    @pytest.mark.requirement("AC-1.1")
    def test_contains_persist_docs(self) -> None:
        """Test macro persists documentation after materialization.

        Doc persistence is a core dbt feature that must be preserved.
        """
        content = _read_macro()
        assert "persist_docs" in content, "Macro must contain persist_docs for doc persistence"


class TestMacroStructure:
    """Test the structural integrity of the macro.

    These tests verify ordering and completeness constraints that
    prevent a sloppy implementation from stuffing all keywords into
    a comment block or wrong location.
    """

    @pytest.mark.requirement("AC-1.1")
    def test_drop_before_create(self) -> None:
        """Test DROP happens before CREATE in the macro.

        The DROP + CTAS pattern requires dropping the existing table
        BEFORE creating the new one. Reversed order would lose data
        without replacing it.
        """
        content = _read_macro()
        drop_pos = content.find("adapter.drop_relation")
        create_pos = content.find("create_table_as")
        assert drop_pos >= 0, "Missing adapter.drop_relation"
        assert create_pos >= 0, "Missing create_table_as"
        assert drop_pos < create_pos, (
            "adapter.drop_relation must appear before create_table_as "
            "(DROP existing, then CREATE new)"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_pre_hooks_before_create(self) -> None:
        """Test pre_hooks run before create_table_as.

        Pre-hooks must execute before the table is materialized.
        """
        content = _read_macro()
        pre_hooks_pos = content.find("run_hooks(pre_hooks")
        create_pos = content.find("create_table_as")
        assert pre_hooks_pos >= 0, "Missing run_hooks(pre_hooks"
        assert create_pos >= 0, "Missing create_table_as"
        assert pre_hooks_pos < create_pos, "run_hooks(pre_hooks must appear before create_table_as"

    @pytest.mark.requirement("AC-1.1")
    def test_post_hooks_after_create(self) -> None:
        """Test post_hooks run after create_table_as.

        Post-hooks must execute after the table is materialized.
        """
        content = _read_macro()
        post_hooks_pos = content.find("run_hooks(post_hooks")
        create_pos = content.find("create_table_as")
        assert post_hooks_pos >= 0, "Missing run_hooks(post_hooks"
        assert create_pos >= 0, "Missing create_table_as"
        assert post_hooks_pos > create_pos, "run_hooks(post_hooks must appear after create_table_as"

    @pytest.mark.requirement("AC-1.1")
    def test_keywords_not_in_comments_only(self) -> None:
        """Test that required operations appear in executable Jinja2, not just comments.

        A sloppy implementation could pass keyword checks by putting them
        in SQL comments or Jinja2 comments. This test strips comments and
        verifies the keywords still exist.
        """
        content = _read_macro()

        # Strip Jinja2 comments: {# ... #}
        import re

        no_jinja_comments = re.sub(r"\{#.*?#\}", "", content, flags=re.DOTALL)
        # Strip SQL line comments: -- ...
        no_comments = re.sub(r"--[^\n]*", "", no_jinja_comments)

        required_keywords = [
            "adapter.drop_relation",
            "create_table_as",
            "run_hooks(pre_hooks",
            "run_hooks(post_hooks",
            "apply_grants",
            "persist_docs",
        ]

        for keyword in required_keywords:
            assert keyword in no_comments, (
                f"'{keyword}' only found in comments, not in executable code"
            )

    @pytest.mark.requirement("AC-1.1")
    def test_grants_after_create(self) -> None:
        """Test apply_grants appears after create_table_as.

        Grants must be applied after the table exists.
        """
        content = _read_macro()
        grants_pos = content.find("apply_grants")
        create_pos = content.find("create_table_as")
        assert grants_pos >= 0, "Missing apply_grants"
        assert create_pos >= 0, "Missing create_table_as"
        assert grants_pos > create_pos, "apply_grants must appear after create_table_as"

    @pytest.mark.requirement("AC-1.1")
    def test_persist_docs_after_create(self) -> None:
        """Test persist_docs appears after create_table_as.

        Documentation can only be persisted after the table exists.
        """
        content = _read_macro()
        docs_pos = content.find("persist_docs")
        create_pos = content.find("create_table_as")
        assert docs_pos >= 0, "Missing persist_docs"
        assert create_pos >= 0, "Missing create_table_as"
        assert docs_pos > create_pos, "persist_docs must appear after create_table_as"

    @pytest.mark.requirement("AC-1.1")
    def test_return_statement_present(self) -> None:
        """Test macro contains a return statement.

        dbt materializations must return a result dict via
        {{ return(...) }} for proper dbt operation.
        """
        content = _read_macro()
        assert "return(" in content or "return (" in content, (
            "Macro must contain a return statement for dbt materialization protocol"
        )


class TestComputePluginABCDefault:
    """Test that ComputePlugin ABC provides get_dbt_macro_paths() with safe default."""

    @pytest.mark.requirement("AC-1.2")
    def test_abc_has_get_dbt_macro_paths_method(self) -> None:
        """Test ComputePlugin ABC defines get_dbt_macro_paths method.

        AC-1.2: Method exists on ComputePlugin class.
        """
        assert hasattr(ComputePlugin, "get_dbt_macro_paths"), (
            "ComputePlugin ABC must have get_dbt_macro_paths method"
        )

    @pytest.mark.requirement("AC-1.2")
    def test_abc_default_returns_empty_list(self) -> None:
        """Test ComputePlugin.get_dbt_macro_paths() default returns [].

        AC-1.2: Default implementation returns [] so plugins without
        custom macros work without overriding.
        """
        plugin = DuckDBComputePlugin()
        # Call the ABC default via super() indirectly by checking its definition
        result = ComputePlugin.get_dbt_macro_paths(plugin)
        assert result == [], (
            f"ComputePlugin.get_dbt_macro_paths() default must return [], got {result}"
        )

    @pytest.mark.requirement("AC-1.2")
    def test_abc_method_is_not_abstract(self) -> None:
        """Test get_dbt_macro_paths is not abstract (has default impl).

        AC-1.2: Method is NOT abstract — it provides a safe default.
        """
        # Abstract methods are tracked in __abstractmethods__
        abstract_methods = getattr(ComputePlugin, "__abstractmethods__", frozenset())
        assert "get_dbt_macro_paths" not in abstract_methods, (
            "get_dbt_macro_paths must NOT be abstract — it should have a default return []"
        )

    @pytest.mark.requirement("AC-1.2")
    def test_abc_method_return_type_annotation(self) -> None:
        """Test get_dbt_macro_paths has list[Path] return type annotation.

        AC-1.2: Return type annotation is list[Path].
        """
        import inspect

        sig = inspect.signature(ComputePlugin.get_dbt_macro_paths)
        assert sig.return_annotation is not inspect.Parameter.empty, (
            "get_dbt_macro_paths must have a return type annotation"
        )


class TestDuckDBPluginMacroPaths:
    """Test that DuckDBComputePlugin overrides get_dbt_macro_paths() correctly."""

    @pytest.mark.requirement("AC-1.3")
    def test_plugin_returns_non_empty_list(self) -> None:
        """Test DuckDBComputePlugin.get_dbt_macro_paths() returns non-empty list.

        AC-1.3: Returns a non-empty list[Path].
        """
        plugin = DuckDBComputePlugin()
        result = plugin.get_dbt_macro_paths()
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) > 0, "DuckDB plugin must return at least one macro path"

    @pytest.mark.requirement("AC-1.3")
    def test_returned_paths_exist(self) -> None:
        """Test each returned path exists on the filesystem.

        AC-1.3: Each returned path exists (in the installed package).
        """
        plugin = DuckDBComputePlugin()
        for path in plugin.get_dbt_macro_paths():
            assert isinstance(path, Path), f"Expected Path, got {type(path)}"
            assert path.exists(), f"Returned macro path does not exist: {path}"

    @pytest.mark.requirement("AC-1.3")
    def test_first_path_contains_materialization(self) -> None:
        """Test the first returned path contains materializations/table.sql.

        AC-1.3: The macro directory should contain our custom materialization.
        """
        plugin = DuckDBComputePlugin()
        paths = plugin.get_dbt_macro_paths()
        assert len(paths) > 0, "No macro paths returned"
        macro_file = paths[0] / "materializations" / "table.sql"
        assert macro_file.exists(), (
            f"Expected materializations/table.sql inside {paths[0]}, but file not found"
        )

    @pytest.mark.requirement("AC-1.3")
    def test_uses_path_relative_to_module(self) -> None:
        """Test path resolution uses Path(__file__).parent / 'dbt_macros'.

        AC-1.3: Uses Path(__file__).parent / 'dbt_macros' for resolution,
        which works in both editable and installed mode.
        """
        plugin = DuckDBComputePlugin()
        paths = plugin.get_dbt_macro_paths()
        assert len(paths) > 0
        # The path should be within the floe_compute_duckdb package directory
        path_str = str(paths[0])
        assert "floe_compute_duckdb" in path_str, (
            f"Macro path should be within floe_compute_duckdb package, got: {path_str}"
        )
        assert path_str.endswith("dbt_macros"), (
            f"Macro path should end with 'dbt_macros', got: {path_str}"
        )

    @pytest.mark.requirement("AC-1.3")
    def test_returns_list_of_path_objects(self) -> None:
        """Test all returned items are pathlib.Path instances.

        AC-1.3: Return type is list[Path].
        """
        plugin = DuckDBComputePlugin()
        for item in plugin.get_dbt_macro_paths():
            assert isinstance(item, Path), (
                f"get_dbt_macro_paths() must return list[Path], got {type(item)} in list"
            )


class TestVersionPins:
    """Test that DuckDB version pins are updated to >=1.4.0."""

    @pytest.mark.requirement("AC-1.4")
    def test_pyproject_duckdb_version_pin(self) -> None:
        """Test pyproject.toml requires duckdb>=1.4.0.

        AC-1.4: DuckDB >=1.4.0 is required for Iceberg REST write support.
        """
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        content = pyproject_path.read_text()
        assert "duckdb>=1.4.0" in content, "pyproject.toml must contain duckdb>=1.4.0 (not >=0.9.0)"
        assert "duckdb>=0.9.0" not in content, (
            "pyproject.toml still contains outdated duckdb>=0.9.0 pin"
        )

    @pytest.mark.requirement("AC-1.4")
    def test_plugin_get_required_dbt_packages_version(self) -> None:
        """Test get_required_dbt_packages() returns duckdb>=1.4.0.

        AC-1.4: The plugin must advertise the correct minimum DuckDB version.
        """
        plugin = DuckDBComputePlugin()
        packages = plugin.get_required_dbt_packages()
        duckdb_pins = [p for p in packages if p.startswith("duckdb")]
        assert len(duckdb_pins) == 1, f"Expected exactly one duckdb pin, got {duckdb_pins}"
        assert duckdb_pins[0] == "duckdb>=1.4.0", (
            f"Expected 'duckdb>=1.4.0', got '{duckdb_pins[0]}'"
        )


class TestBoundaryConditions:
    """Test boundary conditions from the spec.

    These cover edge cases that a sloppy implementation might miss:
    - get_dbt_macro_paths() returns [] when dbt_macros/ doesn't exist
    - Macro conditionally drops only when existing relation is present
    - ABC return type annotation is exactly list[Path]
    - DuckDBComputePlugin returns exactly 1 macro path directory
    """

    @pytest.mark.requirement("AC-1.3")
    def test_get_dbt_macro_paths_returns_empty_when_dir_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_dbt_macro_paths() returns [] when dbt_macros/ dir is absent.

        Spec boundary condition: guard check returns empty list when the
        macro directory does not exist on disk. Without this guard, a plugin
        installed without macro files would return a nonexistent path.
        """
        import floe_compute_duckdb.plugin as plugin_mod

        # Point the module's __file__ to a temp dir with no dbt_macros/ subdir
        fake_plugin_file = str(tmp_path / "plugin.py")
        monkeypatch.setattr(plugin_mod, "__file__", fake_plugin_file)

        # Precondition: dbt_macros/ does NOT exist under tmp_path
        assert not (tmp_path / "dbt_macros").exists()

        plugin = DuckDBComputePlugin()
        result = plugin.get_dbt_macro_paths()
        assert result == [], f"Expected empty list when dbt_macros/ does not exist, got {result}"

    @pytest.mark.requirement("AC-1.1")
    def test_macro_conditional_drop_guard(self) -> None:
        """Test macro conditionally drops only when existing relation is present.

        Spec boundary condition: macro must skip drop on first run when no
        existing table exists. An unconditional drop would fail at runtime.
        The macro must contain a guard like 'existing_relation is not none'.
        """
        content = _read_macro()
        import re

        # Strip comments to ensure the guard is in executable code
        no_jinja_comments = re.sub(r"\{#.*?#\}", "", content, flags=re.DOTALL)
        no_comments = re.sub(r"--[^\n]*", "", no_jinja_comments)

        # Must have a conditional check before drop_relation
        # The standard dbt pattern is: {% if existing_relation is not none %}
        assert (
            "existing_relation is not none" in no_comments.lower()
            or "existing_relation is not none" in no_comments
        ), (
            "Macro must check 'existing_relation is not none' before dropping. "
            "An unconditional drop fails on first run when no table exists."
        )

        # Verify the conditional appears BEFORE drop_relation
        guard_pos = no_comments.lower().find("existing_relation is not none")
        drop_pos = no_comments.find("adapter.drop_relation")
        assert guard_pos < drop_pos, (
            "Conditional guard 'existing_relation is not none' must appear "
            "BEFORE adapter.drop_relation"
        )

    @pytest.mark.requirement("AC-1.1")
    def test_macro_loads_cached_relation(self) -> None:
        """Test macro uses load_cached_relation to check for existing table.

        The macro must call load_cached_relation(this) to determine whether
        a relation already exists before attempting to drop it.
        """
        content = _read_macro()
        assert "load_cached_relation" in content, (
            "Macro must call load_cached_relation(this) to check for existing relations"
        )

    @pytest.mark.requirement("AC-1.2")
    def test_abc_method_return_type_is_list_path(self) -> None:
        """Test get_dbt_macro_paths return type annotation is list[Path].

        AC-1.2 requires the return type to be specifically list[Path],
        not just any non-empty annotation.
        """
        import inspect

        sig = inspect.signature(ComputePlugin.get_dbt_macro_paths)
        annotation = sig.return_annotation
        annotation_str = str(annotation)
        assert "list" in annotation_str.lower(), (
            f"Return annotation must be list[Path], got: {annotation}"
        )
        assert "Path" in annotation_str, f"Return annotation must be list[Path], got: {annotation}"

    @pytest.mark.requirement("AC-1.3")
    def test_plugin_returns_exactly_one_macro_directory(self) -> None:
        """Test DuckDBComputePlugin returns exactly one macro path directory.

        The plugin ships one set of macros in dbt_macros/. Returning more
        or fewer directories indicates a bug.
        """
        plugin = DuckDBComputePlugin()
        result = plugin.get_dbt_macro_paths()
        assert len(result) == 1, (
            f"Expected exactly 1 macro path directory, got {len(result)}: {result}"
        )

    @pytest.mark.requirement("AC-1.3")
    def test_plugin_returns_directory_not_file(self) -> None:
        """Test returned path is a directory, not a file.

        dbt macro-paths expects directories, not individual files.
        """
        plugin = DuckDBComputePlugin()
        paths = plugin.get_dbt_macro_paths()
        for path in paths:
            assert path.is_dir(), f"Macro path must be a directory, got file: {path}"

    @pytest.mark.requirement("AC-1.1")
    def test_macro_contains_commit(self) -> None:
        """Test macro calls adapter.commit() after operations.

        dbt materializations must commit the transaction.
        """
        content = _read_macro()
        assert "adapter.commit()" in content, (
            "Macro must call adapter.commit() to finalize the transaction"
        )


class TestWheelPackaging:
    """Test that dbt_macros/ is included in the wheel distribution."""

    @pytest.mark.requirement("AC-1.5")
    def test_dbt_macros_inside_package(self) -> None:
        """Test dbt_macros/ directory is inside src/floe_compute_duckdb/.

        AC-1.5: Macros inside the package directory are auto-included
        by hatch via the packages = ['src/floe_compute_duckdb'] config.
        """
        package_root = Path(__file__).resolve().parents[2] / "src" / "floe_compute_duckdb"
        macros_dir = package_root / "dbt_macros"
        assert macros_dir.exists(), f"dbt_macros/ not found inside package at {macros_dir}"
        assert macros_dir.is_dir(), "dbt_macros must be a directory"

    @pytest.mark.requirement("AC-1.5")
    def test_macro_file_inside_package_for_wheel(self) -> None:
        """Test materializations/table.sql exists inside the package tree.

        AC-1.5: The actual macro file must be inside the package for
        hatch to include it in the wheel.
        """
        package_root = Path(__file__).resolve().parents[2] / "src" / "floe_compute_duckdb"
        macro_file = package_root / "dbt_macros" / "materializations" / "table.sql"
        assert macro_file.exists(), f"table.sql not found at {macro_file} — won't be in wheel"
