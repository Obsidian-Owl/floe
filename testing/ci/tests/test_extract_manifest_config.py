"""Tests for extract-manifest-config.py.

This test suite covers:
- AC-1.1: Script accepts manifest path as argument
- AC-1.2: Output is valid shell (shell-evaluable export lines)
- AC-1.3: All 6 required env vars are present in output
- AC-1.4: Values match demo/manifest.yaml content exactly
- AC-1.5: Error on missing plugins.storage
- AC-1.6: Error on missing plugins.catalog
- AC-1.7: Single-quoted output prevents shell injection

Done when all fail before implementation.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

# Import the module under test (hyphenated filename requires importlib)
_spec = importlib.util.spec_from_file_location(
    "extract_manifest_config",
    Path(__file__).parent.parent / "extract-manifest-config.py",
)
assert _spec is not None and _spec.loader is not None
extract_manifest_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract_manifest_config)

extract_config = extract_manifest_config.extract_config
format_exports = extract_manifest_config.format_exports

# ---------------------------------------------------------------------------
# Exact expected values from demo/manifest.yaml -- the single source of truth
# ---------------------------------------------------------------------------
EXPECTED_VARS: dict[str, str] = {
    "MANIFEST_BUCKET": "floe-data",
    "MANIFEST_REGION": "us-east-1",
    "MANIFEST_PATH_STYLE_ACCESS": "true",
    "MANIFEST_WAREHOUSE": "floe-demo",
    "MANIFEST_OAUTH_CLIENT_ID": "demo-admin",
    "MANIFEST_OAUTH_SCOPE": "PRINCIPAL_ROLE:ALL",
}

REQUIRED_VAR_NAMES: set[str] = set(EXPECTED_VARS.keys())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DEMO_MANIFEST_YAML = textwrap.dedent("""\
    plugins:
      catalog:
        type: polaris
        config:
          uri: http://floe-platform-polaris:8181/api/catalog
          warehouse: floe-demo
          oauth2:
            client_id: demo-admin
            client_secret: demo-secret
            token_url: http://floe-platform-polaris:8181/api/catalog/v1/oauth/tokens
      storage:
        type: s3
        config:
          endpoint: http://floe-platform-minio:9000
          bucket: floe-data
          region: us-east-1
          path_style_access: true
""")


@pytest.fixture()
def manifest_file(tmp_path: Path) -> Path:
    """Write a demo-equivalent manifest to a temp file."""
    p = tmp_path / "manifest.yaml"
    p.write_text(DEMO_MANIFEST_YAML)
    return p


@pytest.fixture()
def manifest_no_storage(tmp_path: Path) -> Path:
    """Manifest missing plugins.storage entirely."""
    content = textwrap.dedent("""\
        plugins:
          catalog:
            type: polaris
            config:
              warehouse: floe-demo
              oauth2:
                client_id: demo-admin
    """)
    p = tmp_path / "manifest.yaml"
    p.write_text(content)
    return p


@pytest.fixture()
def manifest_no_catalog(tmp_path: Path) -> Path:
    """Manifest missing plugins.catalog entirely."""
    content = textwrap.dedent("""\
        plugins:
          storage:
            type: s3
            config:
              bucket: floe-data
              region: us-east-1
              path_style_access: true
    """)
    p = tmp_path / "manifest.yaml"
    p.write_text(content)
    return p


@pytest.fixture()
def manifest_empty_plugins(tmp_path: Path) -> Path:
    """Manifest with plugins key but no children."""
    p = tmp_path / "manifest.yaml"
    p.write_text("plugins:\n")
    return p


@pytest.fixture()
def manifest_no_plugins(tmp_path: Path) -> Path:
    """Manifest with no plugins key at all."""
    p = tmp_path / "manifest.yaml"
    p.write_text("apiVersion: floe.dev/v1\nkind: Manifest\n")
    return p


@pytest.fixture()
def manifest_injection(tmp_path: Path) -> Path:
    """Manifest with shell-injection payloads in values."""
    content = textwrap.dedent("""\
        plugins:
          catalog:
            type: polaris
            config:
              warehouse: "floe'; rm -rf /; echo '"
              oauth2:
                client_id: "$(whoami)"
                token_url: http://example.com/tokens
          storage:
            type: s3
            config:
              bucket: "test`id`bucket"
              region: "us-east-1"
              path_style_access: true
    """)
    p = tmp_path / "manifest.yaml"
    p.write_text(content)
    return p


# ===========================================================================
# AC-1.3 & AC-1.4: All 6 required env vars present with correct values
# ===========================================================================


@pytest.mark.requirement("ARC-002")
class TestExtractConfigReturnsAllVars:
    """Verify extract_config returns all 6 required env vars."""

    def test_returns_all_six_required_keys(self, manifest_file: Path) -> None:
        """extract_config must return exactly the 6 required env var keys."""
        result = extract_config(manifest_file)
        assert isinstance(result, dict), "extract_config must return a dict"
        missing = REQUIRED_VAR_NAMES - set(result.keys())
        assert missing == set(), f"Missing required env vars: {missing}"

    def test_manifest_bucket_value(self, manifest_file: Path) -> None:
        """MANIFEST_BUCKET must equal 'floe-data' from storage.config.bucket."""
        result = extract_config(manifest_file)
        assert result["MANIFEST_BUCKET"] == "floe-data"

    def test_manifest_region_value(self, manifest_file: Path) -> None:
        """MANIFEST_REGION must equal 'us-east-1' from storage.config.region."""
        result = extract_config(manifest_file)
        assert result["MANIFEST_REGION"] == "us-east-1"

    def test_manifest_path_style_access_value(self, manifest_file: Path) -> None:
        """MANIFEST_PATH_STYLE_ACCESS must be string 'true'."""
        result = extract_config(manifest_file)
        # YAML booleans become Python bool -- script must convert to lowercase string
        assert result["MANIFEST_PATH_STYLE_ACCESS"] == "true"
        assert isinstance(result["MANIFEST_PATH_STYLE_ACCESS"], str), (
            "path_style_access must be a string, not a bool"
        )

    def test_manifest_warehouse_value(self, manifest_file: Path) -> None:
        """MANIFEST_WAREHOUSE must equal 'floe-demo' from catalog.config.warehouse."""
        result = extract_config(manifest_file)
        assert result["MANIFEST_WAREHOUSE"] == "floe-demo"

    def test_manifest_oauth_client_id_value(self, manifest_file: Path) -> None:
        """MANIFEST_OAUTH_CLIENT_ID must equal 'demo-admin'."""
        result = extract_config(manifest_file)
        assert result["MANIFEST_OAUTH_CLIENT_ID"] == "demo-admin"

    def test_manifest_oauth_scope_value(self, manifest_file: Path) -> None:
        """MANIFEST_OAUTH_SCOPE must equal 'PRINCIPAL_ROLE:ALL'."""
        result = extract_config(manifest_file)
        assert result["MANIFEST_OAUTH_SCOPE"] == "PRINCIPAL_ROLE:ALL"

    def test_values_are_all_strings(self, manifest_file: Path) -> None:
        """Every value in the dict must be a string (not bool, int, etc)."""
        result = extract_config(manifest_file)
        for key, value in result.items():
            assert isinstance(value, str), (
                f"{key} value must be str, got {type(value).__name__}: {value!r}"
            )


# ===========================================================================
# AC-1.4: Values match demo/manifest.yaml exactly (cross-check real file)
# ===========================================================================


@pytest.mark.requirement("ARC-002")
class TestExtractConfigMatchesRealManifest:
    """Cross-check against the real demo/manifest.yaml to prevent drift."""

    @pytest.fixture()
    def real_manifest(self) -> Path:
        """Path to the real demo/manifest.yaml in the repo."""
        repo_root = Path(__file__).parent.parent.parent.parent
        p = repo_root / "demo" / "manifest.yaml"
        assert p.exists(), f"Real manifest not found at {p}"
        return p

    def test_bucket_matches_real_manifest(self, real_manifest: Path) -> None:
        """MANIFEST_BUCKET matches real demo/manifest.yaml storage.config.bucket."""
        result = extract_config(real_manifest)
        with open(real_manifest) as f:
            raw: dict[str, Any] = yaml.safe_load(f)
        expected_bucket = raw["plugins"]["storage"]["config"]["bucket"]
        assert result["MANIFEST_BUCKET"] == str(expected_bucket)

    def test_region_matches_real_manifest(self, real_manifest: Path) -> None:
        """MANIFEST_REGION matches real demo/manifest.yaml storage.config.region."""
        result = extract_config(real_manifest)
        with open(real_manifest) as f:
            raw: dict[str, Any] = yaml.safe_load(f)
        expected_region = raw["plugins"]["storage"]["config"]["region"]
        assert result["MANIFEST_REGION"] == str(expected_region)

    def test_warehouse_matches_real_manifest(self, real_manifest: Path) -> None:
        """MANIFEST_WAREHOUSE matches real demo/manifest.yaml catalog.config.warehouse."""
        result = extract_config(real_manifest)
        with open(real_manifest) as f:
            raw: dict[str, Any] = yaml.safe_load(f)
        expected_warehouse = raw["plugins"]["catalog"]["config"]["warehouse"]
        assert result["MANIFEST_WAREHOUSE"] == str(expected_warehouse)

    def test_oauth_client_id_matches_real_manifest(self, real_manifest: Path) -> None:
        """MANIFEST_OAUTH_CLIENT_ID matches real manifest oauth2.client_id."""
        result = extract_config(real_manifest)
        with open(real_manifest) as f:
            raw: dict[str, Any] = yaml.safe_load(f)
        expected_cid = raw["plugins"]["catalog"]["config"]["oauth2"]["client_id"]
        assert result["MANIFEST_OAUTH_CLIENT_ID"] == str(expected_cid)


# ===========================================================================
# AC-1.5 & AC-1.6: Error on missing storage/catalog
# ===========================================================================


@pytest.mark.requirement("ARC-002")
class TestExtractConfigMissingSections:
    """Verify clear errors when required plugin sections are missing."""

    def test_error_missing_storage(self, manifest_no_storage: Path) -> None:
        """Script must raise an error mentioning 'storage' when it is absent."""
        with pytest.raises((SystemExit, KeyError, ValueError)) as exc_info:
            extract_config(manifest_no_storage)
        error_text = str(exc_info.value).lower()
        assert "storage" in error_text, (
            f"Error message must mention 'storage', got: {exc_info.value!r}"
        )

    def test_error_missing_catalog(self, manifest_no_catalog: Path) -> None:
        """Script must raise an error mentioning 'catalog' when it is absent."""
        with pytest.raises((SystemExit, KeyError, ValueError)) as exc_info:
            extract_config(manifest_no_catalog)
        error_text = str(exc_info.value).lower()
        assert "catalog" in error_text, (
            f"Error message must mention 'catalog', got: {exc_info.value!r}"
        )

    def test_error_empty_plugins(self, manifest_empty_plugins: Path) -> None:
        """Script must fail when plugins key exists but has no children."""
        with pytest.raises((SystemExit, KeyError, ValueError, TypeError)):
            extract_config(manifest_empty_plugins)

    def test_error_no_plugins_key(self, manifest_no_plugins: Path) -> None:
        """Script must fail when the plugins key is entirely absent."""
        with pytest.raises((SystemExit, KeyError, ValueError)):
            extract_config(manifest_no_plugins)


# ===========================================================================
# AC-1.6: Error on missing manifest file
# ===========================================================================


@pytest.mark.requirement("ARC-002")
class TestExtractConfigMissingFile:
    """Verify clear error when manifest file does not exist."""

    def test_error_file_not_found(self, tmp_path: Path) -> None:
        """Script must raise a clear error for nonexistent file."""
        nonexistent = tmp_path / "does-not-exist.yaml"
        with pytest.raises((SystemExit, FileNotFoundError)) as exc_info:
            extract_config(nonexistent)
        # Error message should be actionable -- mention the file path
        assert "does-not-exist.yaml" in str(exc_info.value) or isinstance(
            exc_info.value, FileNotFoundError
        )

    def test_error_directory_instead_of_file(self, tmp_path: Path) -> None:
        """Script must not silently accept a directory as input."""
        with pytest.raises((SystemExit, FileNotFoundError, IsADirectoryError, ValueError)):
            extract_config(tmp_path)


# ===========================================================================
# AC-1.2 & AC-1.7: Shell output format and injection prevention
# ===========================================================================


@pytest.mark.requirement("ARC-002")
class TestShellOutputFormat:
    """Verify shell output is valid and injection-safe."""

    def test_output_lines_are_export_statements(self, manifest_file: Path) -> None:
        """Every non-empty line must start with 'export '."""
        config = extract_config(manifest_file)
        output = format_exports(config)
        lines = [line for line in output.strip().splitlines() if line.strip()]
        assert len(lines) >= 6, f"Expected at least 6 export lines, got {len(lines)}"
        for line in lines:
            assert line.startswith("export "), f"Line does not start with 'export ': {line!r}"

    def test_output_values_are_single_quoted(self, manifest_file: Path) -> None:
        """Values must be wrapped in single quotes to prevent shell expansion."""
        config = extract_config(manifest_file)
        output = format_exports(config)
        lines = [line for line in output.strip().splitlines() if line.strip()]
        for line in lines:
            # Pattern: export VAR='value'
            assert "='" in line, f"Missing single-quote after '=': {line!r}"
            assert line.endswith("'"), f"Line must end with single quote: {line!r}"

    def test_single_quote_in_value_is_escaped(self, manifest_injection: Path) -> None:
        """Single quotes inside values must be escaped to prevent injection.

        The standard shell-safe approach is to end the quote, add an escaped
        single quote, and restart: 'foo'\\''bar' -- or replace ' with '\"'\"'.
        Either way, a naive wrapping must NOT allow shell code execution.
        """
        config = extract_config(manifest_injection)
        output = format_exports(config)
        warehouse_line = [
            line for line in output.splitlines() if line.startswith("export MANIFEST_WAREHOUSE=")
        ]
        assert len(warehouse_line) == 1, "Must have exactly one MANIFEST_WAREHOUSE line"
        # The raw value contains a single quote -- it must be escaped
        line = warehouse_line[0]
        value_part = line.split("=", 1)[1]
        # Verify the dangerous payload is NOT executable
        assert "'; rm" not in value_part, f"Shell injection not prevented: {value_part!r}"

    def test_dollar_sign_in_value_not_expanded(self, manifest_injection: Path) -> None:
        """Dollar signs in values must not trigger shell expansion."""
        config = extract_config(manifest_injection)
        output = format_exports(config)
        client_id_line = [
            line
            for line in output.splitlines()
            if line.startswith("export MANIFEST_OAUTH_CLIENT_ID=")
        ]
        assert len(client_id_line) == 1
        # The value $(whoami) must appear literally, not be expanded
        assert "whoami" in client_id_line[0], (
            "The literal $(whoami) text must be preserved in output"
        )

    def test_backtick_in_value_not_expanded(self, manifest_injection: Path) -> None:
        """Backtick command substitution in values must be literal."""
        config = extract_config(manifest_injection)
        output = format_exports(config)
        bucket_line = [
            line for line in output.splitlines() if line.startswith("export MANIFEST_BUCKET=")
        ]
        assert len(bucket_line) == 1
        assert "`id`" in bucket_line[0], (
            "Backtick payload must be preserved literally in single-quoted value"
        )

    def test_injection_output_is_safe_under_bash(self, manifest_injection: Path) -> None:
        """Shell-evaluate injection manifest output; verify no command execution.

        This is the definitive injection test: run the output through bash
        and confirm the dangerous payloads are treated as literal strings.
        """
        config = extract_config(manifest_injection)
        output = format_exports(config)
        # Run in bash: source the exports, then echo the warehouse value
        script = output + '\necho "WAREHOUSE=${MANIFEST_WAREHOUSE}"'
        result = subprocess.run(
            ["bash", "-e", "-c", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, f"Bash failed (rc={result.returncode}): {result.stderr}"
        # The warehouse value should contain the literal injection text
        assert "rm -rf" in result.stdout, "Injection payload must be preserved as literal text"


# ===========================================================================
# AC-1.1: Script accepts manifest path as CLI argument
# ===========================================================================


@pytest.mark.requirement("ARC-002")
class TestCLIInterface:
    """Verify the script works as a CLI tool via subprocess."""

    def test_cli_with_valid_manifest(self, manifest_file: Path) -> None:
        """Running the script with a valid manifest path produces export lines."""
        script_path = Path(__file__).parent.parent / "extract-manifest-config.py"
        result = subprocess.run(
            [sys.executable, str(script_path), str(manifest_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Script failed (rc={result.returncode}): {result.stderr}"
        output = result.stdout
        # Must contain all 6 required export lines
        for var_name in REQUIRED_VAR_NAMES:
            assert f"export {var_name}=" in output, f"CLI output missing export for {var_name}"

    def test_cli_with_nonexistent_file(self, tmp_path: Path) -> None:
        """Running the script with a nonexistent path must fail with nonzero exit."""
        script_path = Path(__file__).parent.parent / "extract-manifest-config.py"
        result = subprocess.run(
            [sys.executable, str(script_path), str(tmp_path / "ghost.yaml")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0, "Script must fail for nonexistent file"
        assert result.stderr.strip(), "Script must output error message to stderr"
        # Error must mention the file -- not a generic traceback
        stderr_lower = result.stderr.lower()
        assert "ghost.yaml" in stderr_lower or "not found" in stderr_lower, (
            f"Error should mention the missing file, got: {result.stderr!r}"
        )

    def test_cli_with_no_arguments(self) -> None:
        """Running the script with no arguments must fail with nonzero exit."""
        script_path = Path(__file__).parent.parent / "extract-manifest-config.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0, "Script must fail when no arguments given"
        # Error must be a usage message, not a raw traceback
        stderr_lower = result.stderr.lower()
        assert "usage" in stderr_lower or "argument" in stderr_lower, (
            f"Error should mention usage/argument, got: {result.stderr!r}"
        )

    def test_cli_output_sets_env_vars_via_shell(self, manifest_file: Path) -> None:
        """Full integration: source CLI output in bash, verify env vars are set."""
        script_path = Path(__file__).parent.parent / "extract-manifest-config.py"
        # Build a shell script that sources the output and checks each var
        check_commands = "; ".join(f'[ -n "${{{var}}}" ] || exit 1' for var in REQUIRED_VAR_NAMES)
        # Use command substitution to capture and source the script output
        shell_script = (
            f"OUTPUT=$({sys.executable} {script_path} {manifest_file}) && "
            f'source /dev/stdin <<< "$OUTPUT" && '
            f"{check_commands}"
        )
        result = subprocess.run(
            ["bash", "-e", "-c", shell_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Shell source + env check failed: {result.stderr}"


# ===========================================================================
# Edge cases and anti-bypass tests
# ===========================================================================


@pytest.mark.requirement("ARC-002")
class TestEdgeCases:
    """Edge cases that prevent hardcoded or partial implementations."""

    def test_different_bucket_value(self, tmp_path: Path) -> None:
        """Script must read actual YAML values, not return hardcoded defaults."""
        content = textwrap.dedent("""\
            plugins:
              catalog:
                type: polaris
                config:
                  warehouse: custom-warehouse
                  oauth2:
                    client_id: custom-client
                    token_url: http://example.com/tokens
              storage:
                type: s3
                config:
                  bucket: my-custom-bucket
                  region: eu-west-1
                  path_style_access: false
        """)
        p = tmp_path / "manifest.yaml"
        p.write_text(content)
        result = extract_config(p)
        assert result["MANIFEST_BUCKET"] == "my-custom-bucket", (
            "Script must read from YAML, not hardcode 'floe-data'"
        )
        assert result["MANIFEST_REGION"] == "eu-west-1", (
            "Script must read from YAML, not hardcode 'us-east-1'"
        )
        assert result["MANIFEST_PATH_STYLE_ACCESS"] == "false", (
            "Script must read from YAML, not hardcode 'true'"
        )
        assert result["MANIFEST_WAREHOUSE"] == "custom-warehouse", (
            "Script must read from YAML, not hardcode 'floe-demo'"
        )
        assert result["MANIFEST_OAUTH_CLIENT_ID"] == "custom-client", (
            "Script must read from YAML, not hardcode 'demo-admin'"
        )

    def test_path_style_access_false_is_string(self, tmp_path: Path) -> None:
        """path_style_access: false must become string 'false', not empty or 'False'."""
        content = textwrap.dedent("""\
            plugins:
              catalog:
                type: polaris
                config:
                  warehouse: w
                  oauth2:
                    client_id: c
                    token_url: http://example.com
              storage:
                type: s3
                config:
                  bucket: b
                  region: r
                  path_style_access: false
        """)
        p = tmp_path / "manifest.yaml"
        p.write_text(content)
        result = extract_config(p)
        assert result["MANIFEST_PATH_STYLE_ACCESS"] == "false"
        assert result["MANIFEST_PATH_STYLE_ACCESS"] != "False", (
            "Must be lowercase 'false', not Python's 'False'"
        )

    def test_extra_plugins_do_not_interfere(self, tmp_path: Path) -> None:
        """Additional plugins beyond storage/catalog must not cause errors."""
        content = textwrap.dedent("""\
            plugins:
              compute:
                type: duckdb
                config:
                  threads: 4
              catalog:
                type: polaris
                config:
                  warehouse: w
                  oauth2:
                    client_id: c
                    token_url: http://example.com
              storage:
                type: s3
                config:
                  bucket: b
                  region: r
                  path_style_access: true
              orchestrator:
                type: dagster
                config:
                  default_schedule: "*/10 * * * *"
        """)
        p = tmp_path / "manifest.yaml"
        p.write_text(content)
        result = extract_config(p)
        assert "MANIFEST_BUCKET" in result
        assert result["MANIFEST_BUCKET"] == "b"

    def test_return_type_is_dict_of_strings(self, manifest_file: Path) -> None:
        """Return type must be dict[str, str], not dict[str, Any]."""
        result = extract_config(manifest_file)
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str), f"Key {k!r} is not str"
            assert isinstance(v, str), f"Value for {k!r} is {type(v).__name__}, not str"

    def test_no_secret_in_output(self, manifest_file: Path) -> None:
        """client_secret must NOT be exported -- only client_id and scope."""
        result = extract_config(manifest_file)
        for key in result:
            assert "SECRET" not in key.upper(), f"Secrets must not be exported: found key {key!r}"
        # Also check that the secret value doesn't appear in any value
        for key, value in result.items():
            assert "demo-secret" not in value, f"client_secret value leaked in {key}={value!r}"

    def test_oauth_scope_has_default_when_not_in_manifest(self, manifest_file: Path) -> None:
        """MANIFEST_OAUTH_SCOPE must be set even though it is not in the manifest YAML.

        The demo manifest does not contain an explicit scope field, so the script
        must provide the Polaris default: PRINCIPAL_ROLE:ALL.
        """
        result = extract_config(manifest_file)
        assert result["MANIFEST_OAUTH_SCOPE"] == "PRINCIPAL_ROLE:ALL"


# ===========================================================================
# Anti-hardcoding: parameterised test with varied manifests
# ===========================================================================


@pytest.mark.requirement("ARC-002")
@pytest.mark.parametrize(
    "bucket,region,path_style,warehouse,client_id",
    [
        ("alpha-bucket", "ap-southeast-1", "true", "wh-alpha", "client-a"),
        ("beta-bucket", "eu-central-1", "false", "wh-beta", "client-b"),
        ("gamma-bucket", "us-west-2", "true", "wh-gamma", "client-g"),
    ],
    ids=["alpha", "beta", "gamma"],
)
def test_extract_config_parameterized(
    tmp_path: Path,
    bucket: str,
    region: str,
    path_style: str,
    warehouse: str,
    client_id: str,
) -> None:
    """Parameterized test to prevent hardcoded return values.

    Each combination must produce matching output -- impossible with a lookup table
    unless it covers the exact parametrize matrix (and that IS a correct impl).
    """
    content = textwrap.dedent(f"""\
        plugins:
          catalog:
            type: polaris
            config:
              warehouse: {warehouse}
              oauth2:
                client_id: {client_id}
                token_url: http://example.com/tokens
          storage:
            type: s3
            config:
              bucket: {bucket}
              region: {region}
              path_style_access: {path_style}
    """)
    p = tmp_path / "manifest.yaml"
    p.write_text(content)
    result = extract_config(p)
    assert result["MANIFEST_BUCKET"] == bucket
    assert result["MANIFEST_REGION"] == region
    assert result["MANIFEST_PATH_STYLE_ACCESS"] == path_style
    assert result["MANIFEST_WAREHOUSE"] == warehouse
    assert result["MANIFEST_OAUTH_CLIENT_ID"] == client_id
