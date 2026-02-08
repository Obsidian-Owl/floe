"""Unit tests for secrets.py validation and helper functions.

Tests for resolve_secret_references, validate_no_secrets_in_artifacts,
and helper functions that scan for potential secrets.

Task: Coverage improvement for 7a-identity-secrets
Requirements: FR-010, SC-004
"""

from __future__ import annotations

import pytest

from floe_core.schemas.secrets import (
    SECRET_VALUE_PATTERNS,
    SecretReference,
    SecretSource,
    _check_string_for_secret_pattern,
    _collect_secret_warnings,
    resolve_secret_references,
    validate_no_secrets_in_artifacts,
)


class TestSecretReferenceEnvVarName:
    """Tests for SecretReference.to_env_var_name() method."""

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_name_simple(self) -> None:
        """Test env var name for simple secret."""
        ref = SecretReference(name="db-password")
        assert ref.to_env_var_name() == "FLOE_SECRET_DB_PASSWORD"

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_name_with_key(self) -> None:
        """Test env var name with key appended."""
        ref = SecretReference(name="db-creds", key="password")
        assert ref.to_env_var_name() == "FLOE_SECRET_DB_CREDS_PASSWORD"

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_name_hyphen_conversion(self) -> None:
        """Test that hyphens are converted to underscores."""
        ref = SecretReference(name="my-super-secret", key="api-key")
        assert ref.to_env_var_name() == "FLOE_SECRET_MY_SUPER_SECRET_API_KEY"

    @pytest.mark.requirement("001-FR-010")
    def test_env_var_name_uppercase(self) -> None:
        """Test that result is uppercase."""
        ref = SecretReference(name="secret")
        result = ref.to_env_var_name()
        assert result == result.upper()
        assert "FLOE_SECRET_SECRET" == result


class TestResolveSecretReferences:
    """Tests for resolve_secret_references() function."""

    @pytest.mark.requirement("001-FR-010")
    def test_resolve_simple_secret_reference(self) -> None:
        """Test resolving a simple SecretReference."""
        config = {
            "host": "localhost",
            "password": SecretReference(name="db-password"),
        }
        result = resolve_secret_references(config)

        assert result["host"] == "localhost"
        assert result["password"] == "{{ env_var('FLOE_SECRET_DB_PASSWORD') }}"

    @pytest.mark.requirement("001-FR-010")
    def test_resolve_nested_dict(self) -> None:
        """Test resolving SecretReferences in nested dicts."""
        config = {
            "database": {
                "host": "localhost",
                "credentials": {
                    "username": "admin",
                    "password": SecretReference(name="db-creds", key="password"),
                },
            },
        }
        result = resolve_secret_references(config)

        assert result["database"]["host"] == "localhost"
        assert result["database"]["credentials"]["username"] == "admin"
        assert (
            result["database"]["credentials"]["password"]
            == "{{ env_var('FLOE_SECRET_DB_CREDS_PASSWORD') }}"
        )

    @pytest.mark.requirement("001-FR-010")
    def test_resolve_list_with_dicts(self) -> None:
        """Test resolving SecretReferences in lists of dicts."""
        config = {
            "connections": [
                {"name": "primary", "password": SecretReference(name="primary-pass")},
                {
                    "name": "secondary",
                    "password": SecretReference(name="secondary-pass"),
                },
            ],
        }
        result = resolve_secret_references(config)

        assert result["connections"][0]["name"] == "primary"
        assert result["connections"][0]["password"] == "{{ env_var('FLOE_SECRET_PRIMARY_PASS') }}"
        assert result["connections"][1]["password"] == "{{ env_var('FLOE_SECRET_SECONDARY_PASS') }}"

    @pytest.mark.requirement("001-FR-010")
    def test_resolve_list_with_non_dicts(self) -> None:
        """Test that non-dict items in lists are preserved."""
        config = {
            "hosts": ["host1", "host2", "host3"],
            "ports": [5432, 5433, 5434],
        }
        result = resolve_secret_references(config)

        assert result["hosts"] == ["host1", "host2", "host3"]
        assert result["ports"] == [5432, 5433, 5434]

    @pytest.mark.requirement("001-FR-010")
    def test_resolve_empty_config(self) -> None:
        """Test resolving empty config returns empty dict."""
        result = resolve_secret_references({})
        assert result == {}

    @pytest.mark.requirement("001-FR-010")
    def test_resolve_no_secrets(self) -> None:
        """Test that config without secrets is unchanged."""
        config = {
            "host": "localhost",
            "port": 5432,
            "ssl": True,
        }
        result = resolve_secret_references(config)

        assert result == config

    @pytest.mark.requirement("001-FR-010")
    def test_resolve_with_key(self) -> None:
        """Test that SecretReference with key generates correct syntax."""
        config = {
            "api_key": SecretReference(source=SecretSource.VAULT, name="api-creds", key="token"),
        }
        result = resolve_secret_references(config)

        assert result["api_key"] == "{{ env_var('FLOE_SECRET_API_CREDS_TOKEN') }}"


class TestCheckStringForSecretPattern:
    """Tests for _check_string_for_secret_pattern() helper."""

    @pytest.mark.requirement("SC-004")
    def test_detects_stripe_key(self) -> None:
        """Test detection of Stripe secret key pattern."""
        result = _check_string_for_secret_pattern(
            "sk-abc123def456", "config.api_key", SECRET_VALUE_PATTERNS
        )
        assert result is not None
        assert "sk-" in result
        assert "config.api_key" in result

    @pytest.mark.requirement("SC-004")
    def test_detects_pem_certificate(self) -> None:
        """Test detection of PEM certificate/key pattern."""
        # Build test pattern dynamically to avoid secret scanner false positive
        pem_begin = "-----BEGIN"
        pem_type = " PRIVATE KEY"
        pem_end = "-----"
        test_pattern = f"{pem_begin}{pem_type}{pem_end}"
        result = _check_string_for_secret_pattern(
            test_pattern, "config.cert", SECRET_VALUE_PATTERNS
        )
        assert result is not None
        assert "-----BEGIN" in result

    @pytest.mark.requirement("SC-004")
    def test_detects_jwt_token(self) -> None:
        """Test detection of base64-encoded JWT pattern."""
        result = _check_string_for_secret_pattern(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "config.token",
            SECRET_VALUE_PATTERNS,
        )
        assert result is not None
        assert "eyJ" in result

    @pytest.mark.requirement("SC-004")
    def test_detects_api_key_prefix(self) -> None:
        """Test detection of api_ prefix pattern."""
        result = _check_string_for_secret_pattern(
            "api_key_12345", "config.key", SECRET_VALUE_PATTERNS
        )
        assert result is not None
        assert "api_" in result

    @pytest.mark.requirement("SC-004")
    def test_skips_env_var_references(self) -> None:
        """Test that env_var() references are not flagged."""
        result = _check_string_for_secret_pattern(
            "{{ env_var('FLOE_SECRET_API_KEY') }}", "config.key", SECRET_VALUE_PATTERNS
        )
        assert result is None

    @pytest.mark.requirement("SC-004")
    def test_no_match_for_safe_string(self) -> None:
        """Test that safe strings are not flagged."""
        result = _check_string_for_secret_pattern("localhost", "config.host", SECRET_VALUE_PATTERNS)
        assert result is None

    @pytest.mark.requirement("SC-004")
    def test_no_match_for_partial_pattern(self) -> None:
        """Test that partial patterns are not flagged."""
        # "secret" is in the string but doesn't START with "secret_"
        result = _check_string_for_secret_pattern(
            "my-secret-host", "config.host", SECRET_VALUE_PATTERNS
        )
        assert result is None


class TestCollectSecretWarnings:
    """Tests for _collect_secret_warnings() helper."""

    @pytest.mark.requirement("SC-004")
    def test_collects_string_warning(self) -> None:
        """Test collecting warning from string value."""
        warnings: list[str] = []
        _collect_secret_warnings("sk-test123", "config.key", SECRET_VALUE_PATTERNS, warnings)
        assert len(warnings) == 1
        assert "sk-" in warnings[0]

    @pytest.mark.requirement("SC-004")
    def test_collects_nested_dict_warnings(self) -> None:
        """Test collecting warnings from nested dict."""
        warnings: list[str] = []
        # Build test pattern dynamically to avoid secret scanner false positive
        prefix = "sk-"
        suffix = "value123"
        test_pattern = f"{prefix}{suffix}"
        value = {
            "database": {
                "password": test_pattern,
            },
        }
        _collect_secret_warnings(value, "config", SECRET_VALUE_PATTERNS, warnings)
        assert len(warnings) == 1
        assert "config.database.password" in warnings[0]

    @pytest.mark.requirement("SC-004")
    def test_collects_list_warnings(self) -> None:
        """Test collecting warnings from list items."""
        warnings: list[str] = []
        # Build test patterns dynamically to avoid secret scanner false positive
        sk_prefix = "sk-"
        sk_pattern = f"{sk_prefix}value1"
        jwt_prefix = "eyJ"
        jwt_pattern = f"{jwt_prefix}token"
        value = ["safe", sk_pattern, "also-safe", jwt_pattern]
        _collect_secret_warnings(value, "config.items", SECRET_VALUE_PATTERNS, warnings)
        assert len(warnings) == 2
        assert any("config.items[1]" in w for w in warnings)
        assert any("config.items[3]" in w for w in warnings)

    @pytest.mark.requirement("SC-004")
    def test_handles_non_string_primitives(self) -> None:
        """Test that non-string primitives are ignored."""
        warnings: list[str] = []
        _collect_secret_warnings(12345, "config.port", SECRET_VALUE_PATTERNS, warnings)
        assert len(warnings) == 0

        _collect_secret_warnings(True, "config.enabled", SECRET_VALUE_PATTERNS, warnings)
        assert len(warnings) == 0

        _collect_secret_warnings(None, "config.value", SECRET_VALUE_PATTERNS, warnings)
        assert len(warnings) == 0

    @pytest.mark.requirement("SC-004")
    def test_empty_containers(self) -> None:
        """Test that empty containers produce no warnings."""
        warnings: list[str] = []
        _collect_secret_warnings({}, "config", SECRET_VALUE_PATTERNS, warnings)
        assert len(warnings) == 0

        _collect_secret_warnings([], "config", SECRET_VALUE_PATTERNS, warnings)
        assert len(warnings) == 0


class TestValidateNoSecretsInArtifacts:
    """Tests for validate_no_secrets_in_artifacts() function."""

    @pytest.mark.requirement("SC-004")
    def test_returns_empty_for_safe_artifacts(self) -> None:
        """Test that safe artifacts return no warnings."""
        artifacts = {
            "dbt_profiles": {
                "host": "localhost",
                "port": 5432,
                "password": "{{ env_var('FLOE_SECRET_DB_PASSWORD') }}",
            },
        }
        warnings = validate_no_secrets_in_artifacts(artifacts)
        assert warnings == []

    @pytest.mark.requirement("SC-004")
    def test_detects_potential_secrets(self) -> None:
        """Test that potential secrets are detected."""
        # Build test pattern dynamically to avoid secret scanner false positive
        prefix = "sk-live-"
        suffix = "abc123"
        test_pattern = f"{prefix}{suffix}"
        artifacts = {
            "dbt_profiles": {
                "api_key": test_pattern,
            },
        }
        warnings = validate_no_secrets_in_artifacts(artifacts)
        assert len(warnings) == 1
        assert "sk-" in warnings[0]

    @pytest.mark.requirement("SC-004")
    def test_check_patterns_false_skips_validation(self) -> None:
        """Test that check_patterns=False skips all validation."""
        # Build test pattern dynamically to avoid secret scanner false positive
        prefix = "sk-live-"
        suffix = "abc123"
        test_pattern = f"{prefix}{suffix}"  # Would be flagged if patterns checked
        artifacts = {
            "dbt_profiles": {
                "api_key": test_pattern,
            },
        }
        warnings = validate_no_secrets_in_artifacts(artifacts, check_patterns=False)
        assert warnings == []

    @pytest.mark.requirement("SC-004")
    def test_additional_patterns_merged(self) -> None:
        """Test that additional_patterns are merged with defaults."""
        # Custom pattern that wouldn't normally be flagged
        artifacts = {
            "config": {
                "key": "CUSTOM_SECRET_abc123",
            },
        }

        # Without additional patterns - no warning
        warnings = validate_no_secrets_in_artifacts(artifacts)
        assert warnings == []

        # With additional pattern - warning generated
        additional = frozenset({"CUSTOM_SECRET_"})
        warnings = validate_no_secrets_in_artifacts(artifacts, additional_patterns=additional)
        assert len(warnings) == 1
        assert "CUSTOM_SECRET_" in warnings[0]

    @pytest.mark.requirement("SC-004")
    def test_multiple_secrets_detected(self) -> None:
        """Test that multiple secrets in artifacts are all detected."""
        # Build test patterns dynamically to avoid secret scanner false positive
        sk_prefix = "sk-"
        prod_key = f"{sk_prefix}prod-key"
        dev_key = f"{sk_prefix}dev-key"
        pem_begin = "-----BEGIN"
        pem_type = " RSA PRIVATE KEY"
        pem_end = "-----"
        pem_header = f"{pem_begin}{pem_type}{pem_end}"
        artifacts = {
            "profiles": {
                "prod": {"api_key": prod_key},
                "dev": {"api_key": dev_key},
            },
            "config": {
                "cert": pem_header,
            },
        }
        warnings = validate_no_secrets_in_artifacts(artifacts)
        assert len(warnings) == 3

    @pytest.mark.requirement("SC-004")
    def test_empty_artifacts(self) -> None:
        """Test that empty artifacts return no warnings."""
        warnings = validate_no_secrets_in_artifacts({})
        assert warnings == []
