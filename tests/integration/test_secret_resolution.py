"""Integration tests for SecretReference resolution in compilation.

Tests that SecretReferences are correctly converted to dbt-compatible
env_var() syntax during compilation, ensuring no actual secret values
appear in CompiledArtifacts or profiles.yml.

Task: T036
Requirements: 7A-FR-010 (Secret Reference Handling)

Note: This test validates the SecretReference → env_var() contract.
The actual profiles.yml generation with SecretReference support
will be implemented in T039.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from floe_core.schemas.secrets import SecretReference, SecretSource


class TestSecretReferenceResolutionContract:
    """Integration tests for SecretReference resolution.

    These tests verify that SecretReference objects are correctly
    transformed for use in dbt profiles.yml without exposing secrets.
    """

    @pytest.mark.requirement("7A-FR-010")
    def test_secret_reference_never_contains_actual_value(self) -> None:
        """Test SecretReference never stores or exposes actual secret values.

        The SecretReference model should only contain metadata about where
        to find a secret, never the secret value itself.
        """
        ref = SecretReference(
            source=SecretSource.KUBERNETES,
            name="db-credentials",
            key="password",
        )

        # Check serialization doesn't contain any sensitive patterns
        json_str = ref.model_dump_json()
        parsed = json.loads(json_str)

        # Should contain only reference metadata
        assert set(parsed.keys()) == {"source", "name", "key"}

        # Check none of the VALUES contain actual sensitive data
        # (field names can contain 'key' etc., but values should not be secrets)
        for field_name, value in parsed.items():
            if isinstance(value, str):
                value_lower = value.lower()
                # The 'key' field value (e.g., "password") is a key NAME, not a credential
                # So we skip checking the 'key' field - its value is metadata, not a secret
                if field_name == "key":
                    continue
                # Only check actual values that could leak credentials
                assert "secret123" not in value_lower, "Test credential value found"

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_syntax_is_valid_jinja(self) -> None:
        """Test generated env_var syntax is valid Jinja2 for dbt."""
        refs = [
            SecretReference(name="simple"),
            SecretReference(name="with-key", key="value"),
            SecretReference(source=SecretSource.VAULT, name="vault-secret"),
        ]

        jinja_pattern = re.compile(r"\{\{\s*env_var\('FLOE_SECRET_[A-Z0-9_]+'\)\s*\}\}")

        for ref in refs:
            syntax = ref.to_env_var_syntax()

            # Must match Jinja pattern
            assert jinja_pattern.match(
                syntax
            ), f"Invalid Jinja syntax for {ref.name}: {syntax}"

            # Must not contain any lowercase (env var names are UPPER_CASE)
            env_var_match = re.search(r"FLOE_SECRET_([A-Z0-9_]+)", syntax)
            assert env_var_match is not None
            env_var_name = env_var_match.group(1)
            assert env_var_name == env_var_name.upper()
            assert "-" not in env_var_name  # Hyphens converted to underscores

    @pytest.mark.requirement("7A-FR-010")
    def test_profiles_yml_credential_format(self) -> None:
        """Test SecretReference produces correct format for profiles.yml credentials.

        This simulates how credentials would appear in a dbt profiles.yml
        after compilation with SecretReference resolution.
        """
        # Simulate common database credentials
        credentials = {
            "host": "localhost",  # Non-secret, literal value
            "port": 5432,  # Non-secret, literal value
            "user": SecretReference(name="db-creds", key="username"),
            "password": SecretReference(name="db-creds", key="password"),
        }

        # Convert SecretReferences to env_var syntax
        resolved: dict[str, Any] = {}
        for key, value in credentials.items():
            if isinstance(value, SecretReference):
                resolved[key] = value.to_env_var_syntax()
            else:
                resolved[key] = value

        # Verify non-secrets are preserved
        assert resolved["host"] == "localhost"
        assert resolved["port"] == 5432

        # Verify secrets are converted to env_var references
        assert resolved["user"] == "{{ env_var('FLOE_SECRET_DB_CREDS_USERNAME') }}"
        assert resolved["password"] == "{{ env_var('FLOE_SECRET_DB_CREDS_PASSWORD') }}"

        # Verify no actual secret values in output
        resolved_json = json.dumps(resolved)
        assert "actual_password" not in resolved_json
        assert "secret123" not in resolved_json

    @pytest.mark.requirement("7A-FR-010")
    def test_multi_backend_credential_resolution(self) -> None:
        """Test credentials from different backends produce same env_var format.

        Regardless of where a secret is stored (K8s, Vault, Infisical),
        the profiles.yml always uses env_var() syntax. The actual backend
        is used at runtime to populate the environment variables.
        """
        # Use neutral secret names that don't contain the backend name
        # This ensures the assertion "source.value not in syntax" passes
        backends = [
            (SecretSource.KUBERNETES, "db-credentials"),
            (SecretSource.VAULT, "api-credentials"),
            (SecretSource.INFISICAL, "app-credentials"),
            (SecretSource.ENV, "config-credentials"),
            (SecretSource.EXTERNAL_SECRETS, "service-credentials"),
        ]

        for source, name in backends:
            ref = SecretReference(source=source, name=name, key="value")
            syntax = ref.to_env_var_syntax()

            # All backends produce env_var() syntax
            assert "env_var(" in syntax
            assert "FLOE_SECRET_" in syntax

            # Extract the env var name from the syntax
            # Syntax is like: {{ env_var('FLOE_SECRET_DB_CREDENTIALS_VALUE') }}
            import re

            match = re.search(r"FLOE_SECRET_([A-Z0-9_]+)", syntax)
            assert match is not None, f"Failed to extract env var name from {syntax}"
            env_var_suffix = match.group(1).lower()

            # The source doesn't appear in the env var name
            # (it's used at runtime for resolution, not in the profile)
            # Note: We check the suffix only, not the full syntax (which contains 'env_var')
            assert (
                source.value not in env_var_suffix
            ), f"Source '{source.value}' should not appear in env var name '{env_var_suffix}'"


class TestSecretReferenceCompilationSafety:
    """Tests ensuring secrets don't leak into compilation artifacts."""

    @pytest.mark.requirement("7A-FR-010")
    def test_model_dump_excludes_resolved_values(self) -> None:
        """Test SecretReference serialization never includes resolved values.

        This ensures that even if runtime resolution happens, the model
        itself doesn't store the resolved value.
        """
        ref = SecretReference(name="test-secret", key="password")

        # Get all possible serialization formats
        dump = ref.model_dump()
        json_dump = ref.model_dump_json()

        # Should only have metadata fields
        assert "source" in dump
        assert "name" in dump
        assert "key" in dump

        # Should NOT have any value-related fields
        assert "value" not in dump
        assert "resolved" not in dump
        assert "resolved_value" not in dump

        # Same for JSON
        assert "value" not in json_dump
        assert "resolved" not in json_dump

    @pytest.mark.requirement("7A-FR-010")
    def test_string_representation_is_safe(self) -> None:
        """Test string representations don't expose secrets."""
        ref = SecretReference(
            source=SecretSource.KUBERNETES,
            name="db-creds",
            key="password",
        )

        # Check repr
        repr_str = repr(ref)
        assert "db-creds" in repr_str  # Name is fine
        assert "password" in repr_str or "key=" in repr_str  # Key name is fine

        # Check str
        str_str = str(ref)
        # Should be the same as repr for Pydantic models
        assert "db-creds" in str_str

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_name_deterministic(self) -> None:
        """Test same SecretReference always produces same env var name.

        This is critical for caching and idempotent compilation.
        """
        ref = SecretReference(name="consistent-secret", key="value")

        # Multiple calls should produce identical output
        results = [ref.to_env_var_syntax() for _ in range(100)]

        assert len(set(results)) == 1  # All results identical

    @pytest.mark.requirement("7A-FR-010")
    def test_different_secrets_produce_different_env_vars(self) -> None:
        """Test different secrets produce unique env var names."""
        refs = [
            SecretReference(name="secret-a"),
            SecretReference(name="secret-b"),
            SecretReference(name="secret-a", key="key1"),
            SecretReference(name="secret-a", key="key2"),
        ]

        env_vars = [ref.to_env_var_syntax() for ref in refs]

        # All should be unique
        assert len(set(env_vars)) == len(refs)


class TestSecretReferenceProfilesYmlIntegration:
    """Integration tests simulating profiles.yml generation."""

    @pytest.mark.requirement("7A-FR-010")
    def test_snowflake_profile_with_secrets(self) -> None:
        """Test Snowflake profile generation with SecretReferences."""
        # Simulate Snowflake profile configuration
        profile: dict[str, Any] = {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "snowflake",
                    "account": SecretReference(name="snowflake-creds", key="account"),
                    "user": SecretReference(name="snowflake-creds", key="user"),
                    "password": SecretReference(name="snowflake-creds", key="password"),
                    "role": "TRANSFORM_ROLE",  # Non-secret
                    "database": "ANALYTICS",  # Non-secret
                    "warehouse": "TRANSFORM_WH",  # Non-secret
                    "schema": "staging",  # Non-secret
                },
            },
        }

        # Resolve SecretReferences
        resolved_outputs: dict[str, Any] = {}
        for env_name, config in profile["outputs"].items():
            resolved_config: dict[str, Any] = {}
            for key, value in config.items():
                if isinstance(value, SecretReference):
                    resolved_config[key] = value.to_env_var_syntax()
                else:
                    resolved_config[key] = value
            resolved_outputs[env_name] = resolved_config

        dev = resolved_outputs["dev"]

        # Verify secrets are env_var references
        assert dev["account"] == "{{ env_var('FLOE_SECRET_SNOWFLAKE_CREDS_ACCOUNT') }}"
        assert dev["user"] == "{{ env_var('FLOE_SECRET_SNOWFLAKE_CREDS_USER') }}"
        assert (
            dev["password"] == "{{ env_var('FLOE_SECRET_SNOWFLAKE_CREDS_PASSWORD') }}"
        )

        # Verify non-secrets are preserved
        assert dev["role"] == "TRANSFORM_ROLE"
        assert dev["database"] == "ANALYTICS"
        assert dev["warehouse"] == "TRANSFORM_WH"
        assert dev["schema"] == "staging"

    @pytest.mark.requirement("7A-FR-010")
    def test_duckdb_profile_with_motherduck_token(self) -> None:
        """Test DuckDB/MotherDuck profile with token secret."""
        # Simulate MotherDuck profile
        profile: dict[str, Any] = {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "duckdb",
                    "path": "md:analytics",  # MotherDuck prefix
                    "motherduck_token": SecretReference(
                        name="motherduck-creds", key="token"
                    ),
                },
            },
        }

        # Resolve
        dev = profile["outputs"]["dev"]
        resolved_token = dev["motherduck_token"].to_env_var_syntax()

        assert resolved_token == "{{ env_var('FLOE_SECRET_MOTHERDUCK_CREDS_TOKEN') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_bigquery_profile_with_service_account(self) -> None:
        """Test BigQuery profile with service account JSON secret."""
        # Simulate BigQuery profile with service account
        profile: dict[str, Any] = {
            "target": "dev",
            "outputs": {
                "dev": {
                    "type": "bigquery",
                    "method": "service-account-json",
                    "project": "my-project",  # Non-secret
                    "dataset": "analytics",  # Non-secret
                    "keyfile_json": SecretReference(name="bigquery-sa", key="json"),
                },
            },
        }

        dev = profile["outputs"]["dev"]
        resolved = dev["keyfile_json"].to_env_var_syntax()

        assert resolved == "{{ env_var('FLOE_SECRET_BIGQUERY_SA_JSON') }}"
