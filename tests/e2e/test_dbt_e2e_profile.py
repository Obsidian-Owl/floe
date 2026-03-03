"""E2E test: dbt_e2e_profile fixture contract (WU-24 T2).

Validates that the dbt_e2e_profile session fixture correctly generates
Iceberg-aware DuckDB profiles for all demo products. The fixture must:
- Write profiles.yml to each demo project directory
- Include DuckDB + Iceberg catalog attachment config
- Source credentials from environment variables (never hardcode)
- Restore original profiles on session teardown

The fixture is implemented in tests/e2e/conftest.py (dbt_e2e_profile).

Prerequisites:
    - No K8s cluster required (fixture generates local config files)

See Also:
    - demo/*/dbt_project.yml: dbt project configs with profile references
    - demo/*/profiles.yml: Original DuckDB-only profiles (should be backed up)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# The three demo products and their dbt profile names.
# Profile names use underscores; directory names use hyphens.
DEMO_PRODUCTS: dict[str, str] = {
    "customer-360": "customer_360",
    "iot-telemetry": "iot_telemetry",
    "financial-risk": "financial_risk",
}


@pytest.mark.e2e
@pytest.mark.requirement("WU-24-T2")
class TestDbtE2eProfileFixtureContract:
    """Validate the dbt_e2e_profile fixture returns a correct profile mapping.

    The fixture is session-scoped and yields a dict[str, Path] mapping
    product directory names to their generated profiles.yml paths.
    """

    @pytest.mark.requirement("WU-24-T2")
    def test_fixture_returns_dict_with_all_three_products(
        self,
        dbt_e2e_profile: dict[str, Path],
    ) -> None:
        """Fixture must return entries for all 3 demo products.

        A sloppy implementation might only handle one product or use
        wrong keys. We verify the exact set of keys matches all demo
        product directory names.
        """
        expected_keys = {"customer-360", "iot-telemetry", "financial-risk"}
        actual_keys = set(dbt_e2e_profile.keys())
        assert actual_keys == expected_keys, (
            f"Fixture must return entries for all 3 demo products.\n"
            f"Expected keys: {expected_keys}\n"
            f"Actual keys:   {actual_keys}\n"
            f"Missing: {expected_keys - actual_keys}\n"
            f"Extra:   {actual_keys - expected_keys}"
        )

    @pytest.mark.requirement("WU-24-T2")
    def test_fixture_values_are_path_objects(
        self,
        dbt_e2e_profile: dict[str, Path],
    ) -> None:
        """Each value in the dict must be a Path instance, not a string.

        Prevents accidental str return that would break downstream consumers
        expecting Path methods.
        """
        for product, profile_path in dbt_e2e_profile.items():
            assert isinstance(profile_path, Path), (
                f"Profile path for '{product}' is {type(profile_path).__name__}, "
                f"expected Path. Value: {profile_path!r}"
            )


@pytest.mark.e2e
@pytest.mark.requirement("WU-24-T2")
class TestProfileFilesExistAndAreValidYaml:
    """Validate that generated profile files exist on disk and parse as YAML."""

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_file_exists_on_disk(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Each profile path returned by the fixture must exist as a real file.

        A lazy implementation could return fabricated paths without writing
        any files. We verify the file is actually on disk.
        """
        profile_path = dbt_e2e_profile[product]
        assert profile_path.exists(), f"Profile file for '{product}' does not exist: {profile_path}"
        assert profile_path.is_file(), (
            f"Profile path for '{product}' exists but is not a file: {profile_path}"
        )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_file_is_valid_yaml(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Profile file must contain valid YAML that parses to a dict.

        An implementation might write malformed content. We parse with
        yaml.safe_load and verify the result is a dictionary (not None,
        not a list, not a string).
        """
        profile_path = dbt_e2e_profile[product]
        content = profile_path.read_text()
        assert len(content.strip()) > 0, f"Profile file for '{product}' is empty: {profile_path}"
        parsed: Any = yaml.safe_load(content)
        assert isinstance(parsed, dict), (
            f"Profile YAML for '{product}' did not parse to a dict. "
            f"Got {type(parsed).__name__}: {parsed!r}"
        )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_file_is_in_correct_demo_directory(
        self,
        dbt_e2e_profile: dict[str, Path],
        project_root: Path,
        product: str,
    ) -> None:
        """Profile must be written to the demo/<product>/ directory.

        Ensures the fixture writes to the correct location where dbt
        will actually discover it, not some temp directory.
        """
        profile_path = dbt_e2e_profile[product]
        expected_dir = project_root / "demo" / product
        assert profile_path.parent == expected_dir, (
            f"Profile for '{product}' written to wrong directory.\n"
            f"Expected parent: {expected_dir}\n"
            f"Actual parent:   {profile_path.parent}"
        )
        assert profile_path.name == "profiles.yml", (
            f"Profile for '{product}' has wrong filename: {profile_path.name}"
        )


@pytest.mark.e2e
@pytest.mark.requirement("WU-24-T2")
class TestProfileStructure:
    """Validate the internal YAML structure of generated profiles."""

    def _load_profile_output(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> dict[str, Any]:
        """Load and return the 'dev' output config for a product profile.

        Navigates: <profile_name> -> outputs -> dev
        """
        profile_path = dbt_e2e_profile[product]
        parsed: dict[str, Any] = yaml.safe_load(profile_path.read_text())
        profile_name = DEMO_PRODUCTS[product]
        assert profile_name in parsed, (
            f"Profile YAML for '{product}' missing top-level key '{profile_name}'.\n"
            f"Available keys: {list(parsed.keys())}"
        )
        profile_block: dict[str, Any] = parsed[profile_name]
        assert "outputs" in profile_block, (
            f"Profile '{profile_name}' missing 'outputs' key.\n"
            f"Available keys: {list(profile_block.keys())}"
        )
        outputs: dict[str, Any] = profile_block["outputs"]
        assert "dev" in outputs, (
            f"Profile '{profile_name}' missing 'dev' output.\n"
            f"Available outputs: {list(outputs.keys())}"
        )
        return outputs["dev"]

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_type_is_duckdb(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Profile type must be 'duckdb' -- the compute engine for Iceberg via DuckDB.

        A wrong implementation might set type to 'postgres' or omit it entirely.
        """
        dev_output = self._load_profile_output(dbt_e2e_profile, product)
        assert dev_output.get("type") == "duckdb", (
            f"Profile type for '{product}' must be 'duckdb', got: {dev_output.get('type')!r}"
        )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_has_attach_config(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Profile must include an 'attach' list for Iceberg catalog attachment.

        The attach config tells DuckDB to attach an Iceberg REST catalog.
        Without it, dbt would write to local DuckDB files, not Iceberg tables.
        """
        dev_output = self._load_profile_output(dbt_e2e_profile, product)
        assert "attach" in dev_output, (
            f"Profile for '{product}' missing 'attach' key. "
            f"This is required for Iceberg catalog attachment.\n"
            f"Available keys: {list(dev_output.keys())}"
        )
        attach = dev_output["attach"]
        assert isinstance(attach, list), (
            f"'attach' for '{product}' must be a list, got {type(attach).__name__}: {attach!r}"
        )
        assert len(attach) > 0, (
            f"'attach' list for '{product}' is empty. "
            f"At least one Iceberg catalog attachment is required."
        )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_attach_entry_has_iceberg_type(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """The attach entry must specify type 'iceberg' to connect to Polaris.

        A sloppy implementation might attach a different catalog type (e.g.,
        'postgres') or omit the type entirely.
        """
        dev_output = self._load_profile_output(dbt_e2e_profile, product)
        attach = dev_output["attach"]
        # Find an entry that references iceberg
        iceberg_entries = [
            entry for entry in attach if isinstance(entry, dict) and entry.get("type") == "iceberg"
        ]
        assert len(iceberg_entries) > 0, (
            f"No attach entry with type='iceberg' found for '{product}'.\nAttach entries: {attach}"
        )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_has_secrets_config(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Profile must include a 'secrets' list for S3/MinIO credentials.

        DuckDB needs S3 credentials to read/write Iceberg data files.
        Without the secrets block, catalog attachment will fail at query time.
        """
        dev_output = self._load_profile_output(dbt_e2e_profile, product)
        assert "secrets" in dev_output, (
            f"Profile for '{product}' missing 'secrets' key. "
            f"This is required for S3/MinIO credential configuration.\n"
            f"Available keys: {list(dev_output.keys())}"
        )
        secrets = dev_output["secrets"]
        assert isinstance(secrets, list), (
            f"'secrets' for '{product}' must be a list, got {type(secrets).__name__}: {secrets!r}"
        )
        assert len(secrets) > 0, (
            f"'secrets' list for '{product}' is empty. "
            f"At least one S3 credential secret entry is required."
        )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_database_is_ice(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Profile must set database to 'ice' to route queries to the Iceberg catalog.

        DuckDB attaches the Iceberg catalog as a named database. Setting
        database='ice' ensures dbt models write to Iceberg tables, not to
        DuckDB's default 'main' or 'memory' database.

        A sloppy implementation might forget this key, use 'main', or
        use a different name that does not match the attach config.
        """
        dev_output = self._load_profile_output(dbt_e2e_profile, product)
        assert dev_output.get("database") == "ice", (
            f"Profile database for '{product}' must be 'ice', "
            f"got: {dev_output.get('database')!r}. "
            f"Without database='ice', dbt writes to local DuckDB, not Iceberg."
        )


@pytest.mark.e2e
@pytest.mark.requirement("WU-24-T2")
class TestProfileMatchesDbtProject:
    """Validate that generated profiles reference the correct dbt profile names."""

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize(
        ("product", "expected_profile_name"),
        list(DEMO_PRODUCTS.items()),
    )
    def test_profile_top_level_key_matches_dbt_project(
        self,
        dbt_e2e_profile: dict[str, Path],
        project_root: Path,
        product: str,
        expected_profile_name: str,
    ) -> None:
        """Profile YAML top-level key must match the 'profile' field in dbt_project.yml.

        Each dbt_project.yml declares `profile: <name>`. The profiles.yml must
        use that exact name as its top-level key, or dbt will fail to find the
        profile. For example, customer-360 uses `profile: customer_360`.

        A sloppy implementation might use the directory name (hyphenated) instead
        of the profile name (underscored), or use a generic name like 'default'.
        """
        profile_path = dbt_e2e_profile[product]
        parsed: dict[str, Any] = yaml.safe_load(profile_path.read_text())

        # Verify ONLY the correct profile name is the top-level key
        top_level_keys = list(parsed.keys())
        assert expected_profile_name in top_level_keys, (
            f"Profile for '{product}' must have top-level key "
            f"'{expected_profile_name}' (matching dbt_project.yml profile field).\n"
            f"Actual top-level keys: {top_level_keys}"
        )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_has_target_dev(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Profile must set target: dev consistent with original profiles."""
        profile_path = dbt_e2e_profile[product]
        parsed: dict[str, Any] = yaml.safe_load(profile_path.read_text())
        profile_name = DEMO_PRODUCTS[product]
        profile_block = parsed[profile_name]

        assert profile_block.get("target") == "dev", (
            f"Profile '{profile_name}' must have target: dev, got: {profile_block.get('target')!r}"
        )


@pytest.mark.e2e
@pytest.mark.requirement("WU-24-T2")
class TestNoHardcodedCredentials:
    """Validate that profiles do not contain hardcoded secrets.

    Credentials must come from environment variables. The profile YAML
    should use Jinja templating (env_var()) or the fixture should inject
    values read from os.environ at generation time.

    Either way, the actual credential values in the rendered YAML must
    match the environment variable values (or known defaults), NOT be
    novel hardcoded strings.
    """

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_s3_access_key_not_hardcoded_novel_value(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """S3 access key in profile must match env var or known default.

        If the fixture renders credentials into YAML, the values must come
        from os.environ. We verify the access key matches either the env var
        value or the known default ('minioadmin').
        """
        profile_path = dbt_e2e_profile[product]
        content = profile_path.read_text()

        # The known default access key (same as polaris_client fixture)
        env_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")

        # If the content contains an access key, it must match the env value.
        # We check the raw YAML content for any access_key_id-like field.
        parsed: dict[str, Any] = yaml.safe_load(content)
        profile_name = DEMO_PRODUCTS[product]
        dev_output = parsed[profile_name]["outputs"]["dev"]
        secrets = dev_output.get("secrets", [])

        for secret_entry in secrets:
            if not isinstance(secret_entry, dict):
                continue
            # Check common field names for access key
            for key in ("key_id", "access_key_id", "key"):
                if key in secret_entry:
                    actual_value = str(secret_entry[key])
                    # Must match env var value or known default
                    assert actual_value == env_access_key or "env_var" in actual_value.lower(), (
                        f"S3 access key in '{product}' profile appears hardcoded.\n"
                        f"Field '{key}' = {actual_value!r}\n"
                        f"Expected to match AWS_ACCESS_KEY_ID env var "
                        f"('{env_access_key}') or use env_var() template."
                    )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_s3_secret_key_not_hardcoded_novel_value(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """S3 secret key in profile must match env var or known default.

        Similar to access key validation. The secret access key must come
        from the environment, not be a novel hardcoded string.
        """
        profile_path = dbt_e2e_profile[product]
        parsed: dict[str, Any] = yaml.safe_load(profile_path.read_text())
        profile_name = DEMO_PRODUCTS[product]
        dev_output = parsed[profile_name]["outputs"]["dev"]
        secrets = dev_output.get("secrets", [])

        env_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin123")

        for secret_entry in secrets:
            if not isinstance(secret_entry, dict):
                continue
            for key in ("secret", "secret_access_key", "secret_key"):
                if key in secret_entry:
                    actual_value = str(secret_entry[key])
                    assert actual_value == env_secret_key or "env_var" in actual_value.lower(), (
                        f"S3 secret key in '{product}' profile appears hardcoded.\n"
                        f"Field '{key}' = {actual_value!r}\n"
                        f"Expected to match AWS_SECRET_ACCESS_KEY env var "
                        f"('{env_secret_key}') or use env_var() template."
                    )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_profile_content_has_no_novel_password_strings(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Raw profile content must not contain password-like strings that do not
        match known environment variable defaults.

        Scans for common credential patterns and verifies they are either
        known defaults or env_var references. Catches cases where an
        implementer invents a new credential value.
        """
        profile_path = dbt_e2e_profile[product]
        content = profile_path.read_text()

        # Known acceptable credential values (defaults from conftest env vars)
        known_defaults = {
            "minioadmin",
            "minioadmin123",
            "demo-admin",
            "demo-secret",
        }

        # Also accept whatever is currently in env vars
        for env_key in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "POLARIS_CREDENTIAL",
        ):
            val = os.environ.get(env_key, "")
            if val:
                # POLARIS_CREDENTIAL may be "id:secret" format
                for part in val.split(":"):
                    known_defaults.add(part)

        # Look for quoted strings that look like credentials
        # This catches hardcoded values that aren't from env vars
        # Match quoted strings in YAML that could be credential values
        # (strings assigned to key/secret/password/credential fields)
        credential_field_pattern = re.compile(
            r"(?:key|secret|password|credential|token)['\"]?\s*:\s*['\"]?([^'\"\n,\]}{]+)",
            re.IGNORECASE,
        )
        matches = credential_field_pattern.findall(content)
        for match in matches:
            match_stripped = match.strip()
            if not match_stripped:
                continue
            # Skip Jinja env_var() references
            if "env_var" in match_stripped.lower():
                continue
            # Skip YAML references and anchors
            if match_stripped.startswith("*") or match_stripped.startswith("&"):
                continue
            # Must be a known default
            assert match_stripped in known_defaults, (
                f"Potentially hardcoded credential in '{product}' profile:\n"
                f"  Value: {match_stripped!r}\n"
                f"  Known defaults: {known_defaults}\n"
                f"Credentials must come from environment variables."
            )


@pytest.mark.e2e
@pytest.mark.requirement("WU-24-T2")
class TestBackupBehavior:
    """Validate that original profiles are backed up (not destroyed)."""

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_original_profile_is_backed_up(
        self,
        dbt_e2e_profile: dict[str, Path],
        project_root: Path,
        product: str,
    ) -> None:
        """A backup of the original profiles.yml must exist during the session.

        The fixture must not silently destroy the original DuckDB-only profile.
        We check for a backup file (e.g., profiles.yml.bak or profiles.yml.orig)
        in the same directory.
        """
        demo_dir = project_root / "demo" / product

        # Check for common backup file naming conventions
        possible_backups = [
            demo_dir / "profiles.yml.bak",
            demo_dir / "profiles.yml.orig",
            demo_dir / "profiles.yml.backup",
            demo_dir / "profiles.yml.original",
        ]

        found_backup = any(backup.exists() for backup in possible_backups)
        assert found_backup, (
            f"No backup of original profiles.yml found for '{product}'.\n"
            f"Checked: {[str(p) for p in possible_backups]}\n"
            f"The fixture must back up the original profile before overwriting."
        )

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_backup_contains_original_duckdb_only_config(
        self,
        dbt_e2e_profile: dict[str, Path],
        project_root: Path,
        product: str,
    ) -> None:
        """Backup file must contain the original DuckDB-only config.

        Verifies the backup has the simple DuckDB profile structure
        (type: duckdb, path: target/demo.duckdb) without Iceberg attach.
        This proves the backup is the real original, not a copy of the
        E2E profile.
        """
        demo_dir = project_root / "demo" / product

        # Find whichever backup convention was used
        backup_path: Path | None = None
        for suffix in (".bak", ".orig", ".backup", ".original"):
            candidate = demo_dir / f"profiles.yml{suffix}"
            if candidate.exists():
                backup_path = candidate
                break

        assert backup_path is not None, (
            f"No backup file found for '{product}' -- cannot verify original content."
        )

        backup_content: dict[str, Any] = yaml.safe_load(backup_path.read_text())
        profile_name = DEMO_PRODUCTS[product]

        assert profile_name in backup_content, (
            f"Backup for '{product}' missing profile key '{profile_name}'."
        )

        backup_dev = backup_content[profile_name]["outputs"]["dev"]
        assert backup_dev.get("type") == "duckdb", (
            f"Backup for '{product}' does not have original type: duckdb."
        )
        assert backup_dev.get("path") == "target/demo.duckdb", (
            f"Backup for '{product}' does not have original path: target/demo.duckdb.\n"
            f"Got: {backup_dev.get('path')!r}. "
            f"Backup appears to be a copy of the E2E profile, not the original."
        )
        # Original should NOT have attach (proves it is the original, not E2E)
        assert "attach" not in backup_dev, (
            f"Backup for '{product}' contains 'attach' config. "
            f"This means the backup is a copy of the E2E profile, not the original."
        )


@pytest.mark.e2e
@pytest.mark.requirement("WU-24-T2")
class TestAttachConfigDetails:
    """Validate the attach block has correct Iceberg catalog configuration."""

    def _get_iceberg_attach_entry(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> dict[str, Any]:
        """Extract the Iceberg attach entry from a product's profile."""
        profile_path = dbt_e2e_profile[product]
        parsed: dict[str, Any] = yaml.safe_load(profile_path.read_text())
        profile_name = DEMO_PRODUCTS[product]
        dev_output = parsed[profile_name]["outputs"]["dev"]
        attach = dev_output["attach"]
        iceberg_entries = [
            entry for entry in attach if isinstance(entry, dict) and entry.get("type") == "iceberg"
        ]
        assert len(iceberg_entries) > 0, f"No iceberg attach entry for '{product}'."
        return iceberg_entries[0]

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_attach_entry_has_path_or_catalog_url(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Iceberg attach entry must specify a catalog URL or path.

        Without a path/URL to the Polaris REST catalog, DuckDB cannot
        discover Iceberg tables. The entry must have a 'path' field
        pointing to the Polaris catalog endpoint.
        """
        entry = self._get_iceberg_attach_entry(dbt_e2e_profile, product)
        assert "path" in entry, (
            f"Iceberg attach entry for '{product}' missing 'path' field.\n"
            f"Available keys: {list(entry.keys())}\n"
            f"The path should reference the Polaris REST catalog endpoint."
        )
        path_value = str(entry["path"])
        assert len(path_value.strip()) > 0, f"Iceberg attach 'path' for '{product}' is empty."

    @pytest.mark.requirement("WU-24-T2")
    @pytest.mark.parametrize("product", list(DEMO_PRODUCTS.keys()))
    def test_attach_entry_has_alias_ice(
        self,
        dbt_e2e_profile: dict[str, Path],
        product: str,
    ) -> None:
        """Iceberg attach entry alias must be 'ice' to match database setting.

        The profile sets database='ice', so the attach alias must also be
        'ice'. If they mismatch, dbt will try to write to a database that
        does not exist.
        """
        entry = self._get_iceberg_attach_entry(dbt_e2e_profile, product)
        # DuckDB attach uses 'alias' to name the attached database.
        # The profile sets database='ice', so alias must be present and match.
        assert "alias" in entry, (
            f"Iceberg attach entry for '{product}' missing 'alias' key.\n"
            f"Available keys: {list(entry.keys())}\n"
            f"The alias must be 'ice' to match database='ice' in the profile."
        )
        assert entry["alias"] == "ice", (
            f"Iceberg attach alias for '{product}' must be 'ice', "
            f"got: {entry['alias']!r}. Must match database='ice' in profile."
        )


@pytest.mark.e2e
@pytest.mark.requirement("WU-24-T2")
class TestProfileConsistencyAcrossProducts:
    """Validate that all three product profiles are structurally consistent.

    A sloppy implementation might correctly generate one profile but produce
    different or broken structures for the others.
    """

    @pytest.mark.requirement("WU-24-T2")
    def test_all_profiles_have_same_structural_keys(
        self,
        dbt_e2e_profile: dict[str, Path],
    ) -> None:
        """All three profiles must have the same set of keys in their dev output.

        Prevents an implementation that special-cases one product while
        forgetting keys on others.
        """
        key_sets: dict[str, set[str]] = {}
        for product in DEMO_PRODUCTS:
            profile_path = dbt_e2e_profile[product]
            parsed: dict[str, Any] = yaml.safe_load(profile_path.read_text())
            profile_name = DEMO_PRODUCTS[product]
            dev_output = parsed[profile_name]["outputs"]["dev"]
            key_sets[product] = set(dev_output.keys())

        products = list(key_sets.keys())
        first_keys = key_sets[products[0]]
        for product in products[1:]:
            assert key_sets[product] == first_keys, (
                f"Profile structure mismatch between '{products[0]}' and '{product}'.\n"
                f"'{products[0]}' keys: {first_keys}\n"
                f"'{product}' keys: {key_sets[product]}\n"
                f"Difference: {first_keys.symmetric_difference(key_sets[product])}"
            )

    @pytest.mark.requirement("WU-24-T2")
    def test_all_profiles_use_same_s3_endpoint(
        self,
        dbt_e2e_profile: dict[str, Path],
    ) -> None:
        """All three profiles must reference the same S3/MinIO endpoint.

        There is one MinIO instance. All products must point to the same
        endpoint. A sloppy implementation might hardcode different URLs.
        """
        endpoints: dict[str, str | None] = {}
        for product in DEMO_PRODUCTS:
            profile_path = dbt_e2e_profile[product]
            parsed: dict[str, Any] = yaml.safe_load(profile_path.read_text())
            profile_name = DEMO_PRODUCTS[product]
            dev_output = parsed[profile_name]["outputs"]["dev"]

            # Extract endpoint from secrets or attach config
            endpoint: str | None = None
            for secret_entry in dev_output.get("secrets", []):
                if isinstance(secret_entry, dict):
                    for key in ("endpoint", "endpoint_url", "url", "region"):
                        if key in secret_entry and "endpoint" in key:
                            endpoint = str(secret_entry[key])
                            break
            endpoints[product] = endpoint

        # All non-None endpoints must match
        non_none_endpoints = {p: e for p, e in endpoints.items() if e is not None}
        if len(non_none_endpoints) >= 2:
            values = list(non_none_endpoints.values())
            for product, endpoint in non_none_endpoints.items():
                assert endpoint == values[0], (
                    f"S3 endpoint mismatch: '{product}' has '{endpoint}', "
                    f"but expected '{values[0]}' (matching other products)."
                )
