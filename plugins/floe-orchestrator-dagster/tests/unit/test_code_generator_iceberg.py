"""Unit tests for Iceberg export code generation in generate_entry_point_code().

These tests verify that the generated _export_dbt_to_iceberg() function uses
the plugin registry system instead of calling load_catalog() directly, and
that no hardcoded credential parameters leak into generated code.

Requirements Covered:
- AC-1: Generated code uses plugin system (registry.get/configure/connect)
- AC-2: Generated code passes S3 config to connect() via config parameter
- AC-3: Generated code imports get_registry and PluginType
- AC-4: Generated code does not contain hardcoded credential parameters

Test Type Rationale:
    All tests are unit tests. generate_entry_point_code() is a pure code
    generation function with no boundary crossing -- it produces a string
    from template interpolation. No mocks needed; we inspect the output string.
"""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


PRODUCT_NAME = "test-product"
"""Shared product name for all tests in this module."""


@pytest.fixture
def generated_code_with_iceberg(
    dagster_plugin: DagsterOrchestratorPlugin,
) -> str:
    """Generate definitions.py code with iceberg_enabled=True.

    Returns the full generated file content as a string.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = dagster_plugin.generate_entry_point_code(
            product_name=PRODUCT_NAME,
            output_dir=tmpdir,
            iceberg_enabled=True,
        )
        from pathlib import Path

        return Path(output_path).read_text()


def _extract_export_function(generated_code: str) -> str:
    """Extract the _export_dbt_to_iceberg function body from generated code.

    Returns the text from 'def _export_dbt_to_iceberg' to the next
    top-level definition or end of file.

    Raises:
        AssertionError: If the function is not found in the generated code.
    """
    marker = "def _export_dbt_to_iceberg("
    start = generated_code.find(marker)
    assert start != -1, (
        f"_export_dbt_to_iceberg function not found in generated code. "
        f"Generated code starts with: {generated_code[:200]}"
    )
    # Find the end: next top-level def/class or end of string
    rest = generated_code[start:]
    lines = rest.split("\n")
    func_lines = [lines[0]]
    for line in lines[1:]:
        # A non-indented, non-empty line that starts a new definition
        if (
            line
            and not line[0].isspace()
            and (line.startswith("def ") or line.startswith("class ") or line.startswith("@"))
        ):
            break
        func_lines.append(line)
    return "\n".join(func_lines)


class TestGeneratedCodeUsesPluginConnect:
    """AC-1: Generated _export_dbt_to_iceberg MUST use plugin system.

    The generated function must use get_registry(), registry.get(),
    registry.configure(), and plugin.connect() instead of load_catalog().
    """

    @pytest.mark.requirement("AC-1")
    def test_generated_code_contains_get_registry_call(
        self, generated_code_with_iceberg: str
    ) -> None:
        """Generated _export_dbt_to_iceberg calls get_registry()."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "get_registry()" in func_body, (
            "Generated _export_dbt_to_iceberg must call get_registry(). "
            f"Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-1")
    def test_generated_code_contains_registry_get(self, generated_code_with_iceberg: str) -> None:
        """Generated _export_dbt_to_iceberg calls registry.get()."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "registry.get(" in func_body, (
            "Generated _export_dbt_to_iceberg must call registry.get(). "
            f"Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-1")
    def test_generated_code_contains_registry_configure(
        self, generated_code_with_iceberg: str
    ) -> None:
        """Generated _export_dbt_to_iceberg calls registry.configure()."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "registry.configure(" in func_body, (
            "Generated _export_dbt_to_iceberg must call registry.configure(). "
            f"Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-1")
    def test_generated_code_contains_plugin_connect(self, generated_code_with_iceberg: str) -> None:
        """Generated _export_dbt_to_iceberg calls plugin.connect().

        Note: must not false-match on duckdb.connect() which is unrelated.
        We look for 'plugin.connect(' or a variable name like
        'catalog_plugin.connect(' that indicates the catalog plugin system.
        """
        func_body = _extract_export_function(generated_code_with_iceberg)
        # Exclude duckdb.connect which is unrelated
        has_plugin_connect = (
            "plugin.connect(" in func_body or "catalog_plugin.connect(" in func_body
        )
        assert has_plugin_connect, (
            "Generated _export_dbt_to_iceberg must call plugin.connect() "
            "or catalog_plugin.connect(). duckdb.connect() does not count. "
            f"Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-1")
    def test_generated_code_does_not_call_load_catalog(
        self, generated_code_with_iceberg: str
    ) -> None:
        """Generated _export_dbt_to_iceberg must NOT call load_catalog() directly."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "load_catalog(" not in func_body, (
            "Generated _export_dbt_to_iceberg must NOT call load_catalog() directly. "
            "It should use the plugin registry system instead. "
            f"Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-1")
    def test_generated_code_does_not_import_load_catalog(
        self, generated_code_with_iceberg: str
    ) -> None:
        """Generated code must NOT import load_catalog when using plugin system."""
        # Check the import section (everything before the first function def)
        first_def = generated_code_with_iceberg.find("\ndef ")
        if first_def == -1:
            first_def = len(generated_code_with_iceberg)
        import_section = generated_code_with_iceberg[:first_def]
        assert "load_catalog" not in import_section, (
            "Generated code must NOT import load_catalog. "
            "The plugin system replaces direct catalog access. "
            f"Import section:\n{import_section}"
        )


class TestGeneratedCodeNoHardcodedCredentials:
    """AC-4: Generated code must NOT contain credential parameters.

    The generated _export_dbt_to_iceberg must not reference credential,
    client_id, client_secret, token_url, or scope parameter construction.
    """

    @pytest.mark.requirement("AC-4")
    def test_no_credential_parameter(self, generated_code_with_iceberg: str) -> None:
        """Generated _export_dbt_to_iceberg must not contain credential= parameter."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "credential=" not in func_body, (
            "Generated code must not contain 'credential=' parameter. "
            "Credentials should be managed by the plugin system. "
            f"Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-4")
    def test_no_client_id_reference(self, generated_code_with_iceberg: str) -> None:
        """Generated _export_dbt_to_iceberg must not reference client_id."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "client_id" not in func_body, (
            f"Generated code must not contain 'client_id'. Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-4")
    def test_no_client_secret_reference(self, generated_code_with_iceberg: str) -> None:
        """Generated _export_dbt_to_iceberg must not reference client_secret."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "client_secret" not in func_body, (
            f"Generated code must not contain 'client_secret'. Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-4")
    def test_no_token_url_reference(self, generated_code_with_iceberg: str) -> None:
        """Generated _export_dbt_to_iceberg must not reference token_url."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "token_url" not in func_body, (
            f"Generated code must not contain 'token_url'. Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-4")
    def test_no_scope_parameter(self, generated_code_with_iceberg: str) -> None:
        """Generated _export_dbt_to_iceberg must not contain scope= parameter."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        # Check for scope= as a parameter, not just substring "scope" in any context
        # The word "scope" might appear in comments, but "scope=" as kwarg is the bug
        assert "scope=" not in func_body, (
            f"Generated code must not contain 'scope=' parameter. Function body:\n{func_body}"
        )


class TestGeneratedCodeImportsPluginRegistry:
    """AC-3: Generated code must import get_registry and PluginType."""

    @pytest.mark.requirement("AC-3")
    def test_imports_get_registry(self, generated_code_with_iceberg: str) -> None:
        """Generated code imports get_registry from floe_core.plugin_registry."""
        assert "get_registry" in generated_code_with_iceberg, (
            "Generated code must import get_registry. "
            f"Code starts with:\n{generated_code_with_iceberg[:500]}"
        )
        # Verify it's an actual import statement, not just a function call
        assert (
            "from floe_core.plugin_registry import get_registry" in generated_code_with_iceberg
        ), (
            "Generated code must have 'from floe_core.plugin_registry "
            "import get_registry'. "
            f"Code starts with:\n{generated_code_with_iceberg[:500]}"
        )

    @pytest.mark.requirement("AC-3")
    def test_imports_plugin_type(self, generated_code_with_iceberg: str) -> None:
        """Generated code imports PluginType from floe_core.plugin_types."""
        assert "PluginType" in generated_code_with_iceberg, (
            "Generated code must import PluginType. "
            f"Code starts with:\n{generated_code_with_iceberg[:500]}"
        )
        assert "from floe_core.plugin_types import PluginType" in generated_code_with_iceberg, (
            "Generated code must have 'from floe_core.plugin_types "
            "import PluginType'. "
            f"Code starts with:\n{generated_code_with_iceberg[:500]}"
        )

    @pytest.mark.requirement("AC-3")
    def test_does_not_import_pyiceberg_catalog(self, generated_code_with_iceberg: str) -> None:
        """Generated code must NOT import from pyiceberg.catalog directly.

        The plugin system abstracts away the catalog implementation.
        """
        # The import 'from pyiceberg.catalog import load_catalog' should
        # no longer be present in the generated code's function body.
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "from pyiceberg.catalog import load_catalog" not in func_body, (
            "Generated _export_dbt_to_iceberg must not import load_catalog "
            "from pyiceberg. Use the plugin registry instead. "
            f"Function body:\n{func_body}"
        )


class TestGeneratedCodePassesS3ConfigToConnect:
    """AC-2: Generated code passes S3 config to plugin connect() via config param."""

    @pytest.mark.requirement("AC-2")
    def test_connect_receives_config_parameter(self, generated_code_with_iceberg: str) -> None:
        """Generated connect() call includes a config= parameter."""
        func_body = _extract_export_function(generated_code_with_iceberg)
        assert "connect(config=" in func_body or ".connect(config=" in func_body, (
            "Generated code must pass config= parameter to plugin.connect(). "
            f"Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-2")
    def test_s3_prefixed_keys_in_connect_config(self, generated_code_with_iceberg: str) -> None:
        """Generated connect() config contains S3-prefixed keys (s3.endpoint etc).

        The storage config must be passed with s3. prefixed keys like
        s3.endpoint, s3.access-key-id, etc. Critically, these keys must
        be part of the config passed to connect(), NOT to load_catalog().
        """
        func_body = _extract_export_function(generated_code_with_iceberg)
        # The S3 prefix keys must exist AND load_catalog must NOT exist.
        # If load_catalog is present, the S3 keys are going to the wrong place.
        has_s3_prefix_construction = (
            '"s3.' in func_body
            or "'s3." in func_body
            or 'f"s3.' in func_body
            or "f's3." in func_body
            or "s3.{" in func_body
        )
        assert has_s3_prefix_construction, (
            "Generated code must construct S3-prefixed keys (e.g. 's3.endpoint') "
            "for the config parameter passed to connect(). "
            f"Function body:\n{func_body}"
        )
        # S3 keys must go to connect(), not load_catalog()
        assert "load_catalog(" not in func_body, (
            "S3-prefixed keys are present but routed to load_catalog() instead "
            "of connect(). The plugin system must handle catalog connection. "
            f"Function body:\n{func_body}"
        )

    @pytest.mark.requirement("AC-2")
    def test_storage_config_used_in_connect_not_load_catalog(
        self, generated_code_with_iceberg: str
    ) -> None:
        """Storage config dict unpacking goes to connect(), not load_catalog().

        This ensures the S3 config is routed through the plugin system.
        """
        func_body = _extract_export_function(generated_code_with_iceberg)
        # Current buggy code has: **{f"s3.{k}": v for k, v in storage_config.items()}
        # as kwargs to load_catalog(). After fix, this pattern should be in
        # the config dict passed to connect().
        # Verify load_catalog is gone (AC-1 overlap, but specifically about S3 routing)
        assert "load_catalog(" not in func_body, (
            "S3 storage config must be passed to connect(), not load_catalog(). "
            f"Function body:\n{func_body}"
        )
        # Verify connect() is present with config
        assert ".connect(" in func_body, (
            f"connect() call must be present to receive S3 config. Function body:\n{func_body}"
        )


class TestGeneratedCodeWithIcebergDisabled:
    """Verify that iceberg-disabled mode does NOT include plugin registry imports.

    This prevents regressions where plugin imports bleed into non-iceberg builds.
    """

    @pytest.mark.requirement("AC-3")
    def test_no_plugin_imports_when_iceberg_disabled(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """When iceberg_enabled=False, no plugin registry imports appear."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = dagster_plugin.generate_entry_point_code(
                product_name=PRODUCT_NAME,
                output_dir=tmpdir,
                iceberg_enabled=False,
            )
            from pathlib import Path

            code = Path(output_path).read_text()

        assert "get_registry" not in code, "get_registry should not appear when iceberg is disabled"
        assert "PluginType" not in code, "PluginType should not appear when iceberg is disabled"
        assert "_export_dbt_to_iceberg" not in code, (
            "_export_dbt_to_iceberg should not appear when iceberg is disabled"
        )
