"""Tests for AC-3: Wire conftest.py to read credentials from manifest.yaml.

Verifies that tests/e2e/conftest.py derives default credentials from
demo/manifest.yaml via a ``_read_manifest_config()`` helper, rather than
hardcoding ``demo-admin:demo-secret`` and ``PRINCIPAL_ROLE:ALL``.

These tests are designed to FAIL before implementation:
- ``_read_manifest_config`` does not exist yet in conftest.py.
- Hardcoded credential strings are still present.

Test types:
- Unit tests: pure function behavior of ``_read_manifest_config``.
- Static analysis tests: verify conftest.py source no longer contains
  hardcoded credential defaults.
- Cross-check tests: verify returned values match actual manifest content.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import re
import textwrap
import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.developer_workflow

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFTEST_PATH = _REPO_ROOT / "tests" / "e2e" / "conftest.py"
_MANIFEST_PATH = _REPO_ROOT / "demo" / "manifest.yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_read_manifest_config() -> Any:
    """Import ``_read_manifest_config`` from the E2E conftest module.

    Uses importlib to avoid triggering session-scoped fixtures that
    require a running K8s cluster.

    Returns:
        The ``_read_manifest_config`` callable.

    Raises:
        pytest.fail: If the function does not exist in conftest.py.
    """
    spec = importlib.util.spec_from_file_location("e2e_conftest", _CONFTEST_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(
            f"Cannot create module spec from {_CONFTEST_PATH}. "
            "Ensure the file exists and is valid Python."
        )
    module: Any = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        # conftest may fail to import due to missing K8s services.
        # We only need the function object, so fall back to AST check.
        pytest.fail(
            f"Could not import conftest module: {exc}. "
            "If this is a K8s dependency issue, _read_manifest_config "
            "should be importable without K8s infrastructure."
        )

    fn: Any = getattr(module, "_read_manifest_config", None)
    if fn is None:
        pytest.fail(
            "_read_manifest_config is not defined in tests/e2e/conftest.py. "
            "This function must exist per AC-3."
        )
    return fn


def _load_manifest_values() -> dict[str, Any]:
    """Load raw values from demo/manifest.yaml for cross-checks."""
    with open(_MANIFEST_PATH) as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    catalog = raw["plugins"]["catalog"]["config"]
    return {
        "client_id": catalog["oauth2"]["client_id"],
        "client_secret": catalog["oauth2"]["client_secret"],
        "warehouse": catalog["warehouse"],
    }


# =========================================================================
# 1. _read_manifest_config() function tests
# =========================================================================


class TestReadManifestConfigExists:
    """Verify _read_manifest_config exists and is callable."""

    @pytest.mark.requirement("AC-3")
    def test_function_exists_in_conftest(self) -> None:
        """_read_manifest_config must be defined in tests/e2e/conftest.py."""
        source = _CONFTEST_PATH.read_text()
        tree = ast.parse(source)
        function_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert "_read_manifest_config" in function_names, (
            "_read_manifest_config function not found in conftest.py. "
            "AC-3 requires this helper to read credential defaults from manifest."
        )


class TestReadManifestConfigWithRealManifest:
    """Test _read_manifest_config against the real demo/manifest.yaml."""

    @pytest.mark.requirement("AC-3")
    def test_returns_dict(self) -> None:
        """_read_manifest_config must return a dict."""
        fn = _import_read_manifest_config()
        result = fn()
        assert isinstance(result, dict), f"Expected dict, got {type(result).__name__}"

    @pytest.mark.requirement("AC-3")
    def test_contains_client_id(self) -> None:
        """Result must contain 'client_id' key."""
        fn = _import_read_manifest_config()
        result = fn()
        assert "client_id" in result, (
            "Result missing 'client_id' key. "
            "Must be extracted from plugins.catalog.config.oauth2.client_id"
        )

    @pytest.mark.requirement("AC-3")
    def test_contains_client_secret(self) -> None:
        """Result must contain 'client_secret' key."""
        fn = _import_read_manifest_config()
        result = fn()
        assert "client_secret" in result, (
            "Result missing 'client_secret' key. "
            "Must be extracted from plugins.catalog.config.oauth2.client_secret"
        )

    @pytest.mark.requirement("AC-3")
    def test_contains_scope(self) -> None:
        """Result must contain 'scope' key."""
        fn = _import_read_manifest_config()
        result = fn()
        assert "scope" in result, (
            "Result missing 'scope' key. Must default to 'PRINCIPAL_ROLE:ALL' when not in manifest."
        )

    @pytest.mark.requirement("AC-3")
    def test_contains_warehouse(self) -> None:
        """Result must contain 'warehouse' key."""
        fn = _import_read_manifest_config()
        result = fn()
        assert "warehouse" in result, (
            "Result missing 'warehouse' key. "
            "Must be extracted from plugins.catalog.config.warehouse"
        )

    @pytest.mark.requirement("AC-3")
    def test_client_id_matches_manifest(self) -> None:
        """client_id must match demo/manifest.yaml value."""
        fn = _import_read_manifest_config()
        result = fn()
        expected = _load_manifest_values()
        assert result["client_id"] == expected["client_id"], (
            f"client_id mismatch: got {result['client_id']!r}, "
            f"expected {expected['client_id']!r} from manifest"
        )

    @pytest.mark.requirement("AC-3")
    def test_client_secret_matches_manifest(self) -> None:
        """client_secret must match demo/manifest.yaml value."""
        fn = _import_read_manifest_config()
        result = fn()
        expected = _load_manifest_values()
        assert result["client_secret"] == expected["client_secret"], (
            f"client_secret mismatch: got {result['client_secret']!r}, "
            f"expected {expected['client_secret']!r} from manifest"
        )

    @pytest.mark.requirement("AC-3")
    def test_warehouse_matches_manifest(self) -> None:
        """warehouse must match demo/manifest.yaml value (floe-demo, not floe-e2e)."""
        fn = _import_read_manifest_config()
        result = fn()
        expected = _load_manifest_values()
        assert result["warehouse"] == expected["warehouse"], (
            f"warehouse mismatch: got {result['warehouse']!r}, "
            f"expected {expected['warehouse']!r} from manifest"
        )

    @pytest.mark.requirement("AC-3")
    def test_scope_defaults_to_principal_role_all(self) -> None:
        """scope must default to PRINCIPAL_ROLE:ALL (not in manifest)."""
        fn = _import_read_manifest_config()
        result = fn()
        assert result["scope"] == "PRINCIPAL_ROLE:ALL", (
            f"scope should be 'PRINCIPAL_ROLE:ALL', got {result['scope']!r}"
        )

    @pytest.mark.requirement("AC-3")
    def test_all_values_are_strings(self) -> None:
        """All values in the returned dict must be strings."""
        fn = _import_read_manifest_config()
        result = fn()
        for key, value in result.items():
            assert isinstance(value, str), (
                f"Value for key {key!r} is {type(value).__name__}, expected str"
            )


class TestReadManifestConfigWithCustomPath:
    """Test _read_manifest_config with explicit manifest_path argument."""

    @pytest.mark.requirement("AC-3")
    def test_reads_from_custom_path(self, tmp_path: Path) -> None:
        """Must accept a manifest_path argument to read from a custom location."""
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(
            textwrap.dedent("""\
                plugins:
                  catalog:
                    config:
                      warehouse: custom-warehouse
                      oauth2:
                        client_id: custom-id
                        client_secret: custom-secret
                  storage:
                    config:
                      endpoint: http://localhost:9000
                      bucket: test-bucket
                      region: us-west-2
                      path_style_access: true
            """)
        )
        fn = _import_read_manifest_config()
        result = fn(manifest_path=manifest)
        assert result["client_id"] == "custom-id", (
            f"Expected 'custom-id' from custom manifest, got {result['client_id']!r}"
        )
        assert result["client_secret"] == "custom-secret", (  # pragma: allowlist secret
            f"Expected 'custom-secret', got {result['client_secret']!r}"
        )
        assert result["warehouse"] == "custom-warehouse", (
            f"Expected 'custom-warehouse', got {result['warehouse']!r}"
        )

    @pytest.mark.requirement("AC-3")
    def test_scope_from_manifest_when_present(self, tmp_path: Path) -> None:
        """When manifest contains oauth2.scope, use it instead of default."""
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(
            textwrap.dedent("""\
                plugins:
                  catalog:
                    config:
                      warehouse: test-wh
                      oauth2:
                        client_id: id1
                        client_secret: sec1
                        scope: CUSTOM_SCOPE:READ
                  storage:
                    config:
                      endpoint: http://localhost:9000
                      bucket: b
                      region: us-east-1
                      path_style_access: true
            """)
        )
        fn = _import_read_manifest_config()
        result = fn(manifest_path=manifest)
        assert result["scope"] == "CUSTOM_SCOPE:READ", (
            f"Expected scope from manifest, got {result['scope']!r}"
        )


class TestReadManifestConfigFallback:
    """Test fallback behavior when manifest is not found."""

    @pytest.mark.requirement("AC-3")
    def test_missing_manifest_returns_defaults_with_warning(self, tmp_path: Path) -> None:
        """When manifest is not found, return hardcoded defaults and emit warning."""
        fn = _import_read_manifest_config()
        nonexistent = tmp_path / "does-not-exist.yaml"

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = fn(manifest_path=nonexistent)

        # Must return fallback defaults (not raise / return empty)
        assert isinstance(result, dict), "Must return dict even when manifest missing"
        assert "client_id" in result, "Fallback must include client_id"
        assert "client_secret" in result, "Fallback must include client_secret"
        assert "scope" in result, "Fallback must include scope"
        assert "warehouse" in result, "Fallback must include warehouse"

        # Must have emitted a warning
        warning_messages = [str(w.message) for w in caught]
        assert any("manifest" in msg.lower() for msg in warning_messages), (
            f"Expected a warning mentioning 'manifest' for missing file. "
            f"Got warnings: {warning_messages}"
        )

    @pytest.mark.requirement("AC-3")
    def test_fallback_values_are_sensible(self, tmp_path: Path) -> None:
        """Fallback values must match the previously hardcoded defaults."""
        fn = _import_read_manifest_config()
        nonexistent = tmp_path / "does-not-exist.yaml"

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = fn(manifest_path=nonexistent)

        # The fallback should provide the same defaults that were
        # previously hardcoded, so existing behavior is preserved.
        assert result["client_id"] == "demo-admin", (
            f"Fallback client_id should be 'demo-admin', got {result['client_id']!r}"
        )
        assert result["client_secret"] == "demo-secret", (  # pragma: allowlist secret
            f"Fallback client_secret should be 'demo-secret', got {result['client_secret']!r}"
        )
        assert result["scope"] == "PRINCIPAL_ROLE:ALL", (
            f"Fallback scope should be 'PRINCIPAL_ROLE:ALL', got {result['scope']!r}"
        )


# =========================================================================
# 2. Static analysis tests: conftest.py source code checks
# =========================================================================


class TestConftestNoHardcodedCredentials:
    """Verify conftest.py no longer contains hardcoded credential defaults.

    These tests read conftest.py as source text and check that the
    previously hardcoded values have been replaced by _read_manifest_config
    calls. This catches a sloppy implementation that adds the function
    but never wires it in.
    """

    @pytest.mark.requirement("AC-3")
    def test_no_hardcoded_demo_admin_demo_secret_default(self) -> None:
        """conftest.py must not use 'demo-admin:demo-secret' as a literal default.

        The string may appear in comments or pragma lines, but must not
        be used as an assignment target for default_cred.
        """
        source = _CONFTEST_PATH.read_text()
        # Match assignment patterns like:
        #   default_cred = "demo-admin:demo-secret"
        #   default_cred = 'demo-admin:demo-secret'
        # But NOT comments or docstrings.
        pattern = r"""(?m)^\s*default_cred\s*=\s*["']demo-admin:demo-secret["']"""
        matches = re.findall(pattern, source)
        assert len(matches) == 0, (
            f"Found {len(matches)} hardcoded 'demo-admin:demo-secret' assignment(s) "
            f"in conftest.py. AC-3 requires these to come from _read_manifest_config()."
        )

    @pytest.mark.requirement("AC-3")
    def test_no_hardcoded_floe_e2e_warehouse_default(self) -> None:
        """conftest.py must not use 'floe-e2e' as the default warehouse.

        The manifest specifies 'floe-demo' as the warehouse. Any
        os.environ.get("POLARIS_WAREHOUSE", "floe-e2e") must be replaced
        with the manifest-derived value.
        """
        source = _CONFTEST_PATH.read_text()
        # Match: os.environ.get("POLARIS_WAREHOUSE", "floe-e2e")
        # Exclude comments and the namespace generation function.
        lines = source.splitlines()
        violations: list[tuple[int, str]] = []
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Check for "floe-e2e" as a default value in environ.get calls
            if re.search(
                r"""os\.environ\.get\(\s*["']POLARIS_WAREHOUSE["']\s*,\s*["']floe-e2e["']""",
                line,
            ):
                violations.append((i, line.strip()))
        assert len(violations) == 0, (
            f"Found {len(violations)} hardcoded 'floe-e2e' warehouse default(s) "
            f"in conftest.py at lines {[v[0] for v in violations]}. "
            "AC-3 requires warehouse to come from _read_manifest_config()."
        )

    @pytest.mark.requirement("AC-3")
    def test_read_manifest_config_is_called(self) -> None:
        """conftest.py must actually call _read_manifest_config().

        Having the function defined but never called is useless.
        """
        source = _CONFTEST_PATH.read_text()
        # Look for actual calls (not just the def)
        # Match: _read_manifest_config(  -- with optional arguments
        call_pattern = r"(?<!def\s)_read_manifest_config\s*\("
        calls = re.findall(call_pattern, source)
        assert len(calls) >= 1, (
            "_read_manifest_config is defined but never called in conftest.py. "
            "AC-3 requires the fixtures to use this function for credential defaults."
        )


class TestConftestScopeDerivation:
    """Verify PRINCIPAL_ROLE:ALL scope values derive from the helper."""

    @pytest.mark.requirement("AC-3")
    def test_no_bare_scope_literal_in_polaris_client(self) -> None:
        """The pyiceberg catalog config scope must not be a bare string literal.

        Lines like ``"scope": "PRINCIPAL_ROLE:ALL"`` in the polaris_client
        fixture must be replaced with the manifest-derived value.
        The dbt profile template line (OAUTH2_SCOPE:) is excluded since
        it is a Jinja template and may remain as-is per design.
        """
        source = _CONFTEST_PATH.read_text()
        lines = source.splitlines()
        violations: list[tuple[int, str]] = []
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Match dict literal: "scope": "PRINCIPAL_ROLE:ALL"
            if re.search(
                r"""["']scope["']\s*:\s*["']PRINCIPAL_ROLE:ALL["']""",
                line,
            ):
                violations.append((i, line.strip()))
        assert len(violations) == 0, (
            f"Found {len(violations)} hardcoded 'PRINCIPAL_ROLE:ALL' scope literal(s) "
            f"at lines {[v[0] for v in violations]}. "
            "AC-3 requires scope to come from _read_manifest_config()."
        )


# =========================================================================
# 3. Cross-check: _read_manifest_config values match actual manifest
# =========================================================================


class TestManifestCrossCheck:
    """Verify _read_manifest_config output matches demo/manifest.yaml content.

    These tests load the manifest independently (via PyYAML) and compare
    against _read_manifest_config output. This catches implementations
    that hardcode values inside the function instead of actually reading
    the file.
    """

    @pytest.mark.requirement("AC-3")
    def test_client_id_matches_raw_yaml(self) -> None:
        """client_id from _read_manifest_config must match raw YAML parse."""
        fn = _import_read_manifest_config()
        result = fn()

        with open(_MANIFEST_PATH) as f:
            raw = yaml.safe_load(f)
        expected = raw["plugins"]["catalog"]["config"]["oauth2"]["client_id"]
        assert result["client_id"] == expected

    @pytest.mark.requirement("AC-3")
    def test_warehouse_matches_raw_yaml(self) -> None:
        """warehouse from _read_manifest_config must match raw YAML parse."""
        fn = _import_read_manifest_config()
        result = fn()

        with open(_MANIFEST_PATH) as f:
            raw = yaml.safe_load(f)
        expected = raw["plugins"]["catalog"]["config"]["warehouse"]
        assert result["warehouse"] == expected

    @pytest.mark.requirement("AC-3")
    def test_reads_file_not_hardcoded(self, tmp_path: Path) -> None:
        """Prove values come from the file, not hardcoded in the function.

        Create a manifest with DIFFERENT values and verify they are returned.
        This is the definitive test against a hardcoded implementation.
        """
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(
            textwrap.dedent("""\
                plugins:
                  catalog:
                    config:
                      warehouse: totally-different-warehouse
                      oauth2:
                        client_id: unique-test-id-xyz
                        client_secret: unique-test-secret-abc
                  storage:
                    config:
                      endpoint: http://localhost:9000
                      bucket: b
                      region: us-east-1
                      path_style_access: true
            """)
        )
        fn = _import_read_manifest_config()
        result = fn(manifest_path=manifest)
        assert result["client_id"] == "unique-test-id-xyz", (
            f"Expected 'unique-test-id-xyz' from custom manifest, "
            f"got {result['client_id']!r}. "
            "Is _read_manifest_config actually reading the file?"
        )
        assert result["client_secret"] == "unique-test-secret-abc", (  # pragma: allowlist secret
            f"Expected 'unique-test-secret-abc' from custom manifest, "
            f"got {result['client_secret']!r}. "
            "Is _read_manifest_config actually reading the file?"
        )
        assert result["warehouse"] == "totally-different-warehouse", (
            f"Expected 'totally-different-warehouse' from custom manifest, "
            f"got {result['warehouse']!r}. "
            "Is _read_manifest_config actually reading the file?"
        )


# =========================================================================
# 4. Environment variable override precedence
# =========================================================================


class TestEnvVarOverridePrecedence:
    """Verify that environment variables still take precedence.

    AC-3 condition 4: env var overrides must still work. The conftest
    fixtures use os.environ.get() with defaults from the manifest.
    We verify the pattern is preserved by checking the source structure.
    """

    @pytest.mark.requirement("AC-3")
    def test_polaris_credential_env_override_preserved(self) -> None:
        """POLARIS_CREDENTIAL env var must still override manifest defaults.

        conftest.py must still call os.environ.get("POLARIS_CREDENTIAL", ...)
        so operators can override via environment.
        """
        source = _CONFTEST_PATH.read_text()
        assert (
            'os.environ.get("POLARIS_CREDENTIAL"' in source
            or "os.environ.get('POLARIS_CREDENTIAL'" in source
        ), (
            "conftest.py must still check POLARIS_CREDENTIAL env var "
            "for override precedence (AC-3 condition 4)."
        )

    @pytest.mark.requirement("AC-3")
    def test_polaris_warehouse_env_override_preserved(self) -> None:
        """POLARIS_WAREHOUSE env var must still override manifest defaults.

        conftest.py must still call os.environ.get("POLARIS_WAREHOUSE", ...)
        so operators can override via environment.
        """
        source = _CONFTEST_PATH.read_text()
        assert (
            'os.environ.get("POLARIS_WAREHOUSE"' in source
            or "os.environ.get('POLARIS_WAREHOUSE'" in source
        ), (
            "conftest.py must still check POLARIS_WAREHOUSE env var "
            "for override precedence (AC-3 condition 4)."
        )

    @pytest.mark.requirement("AC-3")
    def test_custom_manifest_keeps_env_credential_precedence(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit manifest paths must still let POLARIS_* credentials win."""
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(
            textwrap.dedent("""\
                plugins:
                  catalog:
                    config:
                      warehouse: manifest-warehouse
                      oauth2:
                        client_id: manifest-id
                        client_secret: manifest-secret
                        scope: MANIFEST_SCOPE:READ
            """)
        )
        monkeypatch.setenv("POLARIS_CLIENT_ID", "env-id")
        monkeypatch.setenv("POLARIS_CLIENT_SECRET", "env-secret")  # pragma: allowlist secret
        monkeypatch.setenv("POLARIS_SCOPE", "ENV_SCOPE:ALL")
        monkeypatch.setenv("POLARIS_WAREHOUSE", "env-warehouse")

        fn = _import_read_manifest_config()
        result = fn(manifest_path=manifest)

        assert result == {
            "client_id": "env-id",
            "client_secret": "env-secret",  # pragma: allowlist secret
            "scope": "ENV_SCOPE:ALL",
            "warehouse": "env-warehouse",
        }
