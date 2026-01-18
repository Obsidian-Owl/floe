"""Contract tests for SecretReference schema stability.

These tests ensure the SecretReference model and its to_env_var_syntax() method
remain stable and backward-compatible. Breaking changes should fail these tests.

SecretReference is the contract for how secrets are referenced in manifests
and resolved at runtime in dbt profiles.yml.

Task: T034
Requirements: 7A-FR-010 (Secret Reference Handling)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from floe_core.schemas.secrets import SecretReference, SecretSource
from pydantic import ValidationError


class TestSecretReferenceSchemaContract:
    """Contract tests for SecretReference schema stability.

    These tests ensure the schema structure remains stable and that
    the contract between manifest configuration and runtime resolution is maintained.
    """

    @pytest.mark.requirement("7A-FR-010")
    def test_default_source_is_kubernetes(self) -> None:
        """Contract: Default source is KUBERNETES.

        This ensures K8s-native deployments work without explicit source config.
        """
        ref = SecretReference(name="test-secret")
        assert ref.source == SecretSource.KUBERNETES

    @pytest.mark.requirement("7A-FR-010")
    def test_required_fields_are_name_only(self) -> None:
        """Contract: Only 'name' is required.

        This ensures minimal configuration for simple use cases.
        """
        # Should succeed with just name
        ref = SecretReference(name="simple")
        assert ref.name == "simple"
        assert ref.source == SecretSource.KUBERNETES
        assert ref.key is None

        # Should fail without name
        with pytest.raises(ValidationError, match="name"):
            SecretReference()  # type: ignore[call-arg]

    @pytest.mark.requirement("7A-FR-010")
    def test_all_secret_sources_are_valid(self) -> None:
        """Contract: All SecretSource enum values are valid sources.

        If new sources are added, this test will still pass.
        If sources are removed, downstream users may break.
        """
        expected_sources = {"env", "kubernetes", "vault", "external-secrets", "infisical"}
        actual_sources = {s.value for s in SecretSource}

        # All expected sources must exist (backward compatibility)
        for expected in expected_sources:
            assert expected in actual_sources, f"Missing source: {expected}"

    @pytest.mark.requirement("7A-FR-010")
    def test_model_is_immutable(self) -> None:
        """Contract: SecretReference is immutable (frozen=True).

        This ensures references can be safely used as dict keys and cached.
        """
        ref = SecretReference(name="immutable-test")

        with pytest.raises(ValidationError):
            ref.name = "new-name"

        with pytest.raises(ValidationError):
            ref.source = SecretSource.VAULT

    @pytest.mark.requirement("7A-FR-010")
    def test_name_validation_pattern(self) -> None:
        """Contract: Secret names follow K8s naming conventions.

        Pattern: lowercase alphanumeric with hyphens, must start/end with alphanumeric.
        """
        # Valid names
        valid_names = [
            "a",
            "ab",
            "abc",
            "a-b",
            "a-b-c",
            "db-password",
            "polaris-credentials",
            "my-secret-123",
            "1-secret",
            "secret-1",
        ]
        for name in valid_names:
            ref = SecretReference(name=name)
            assert ref.name == name

        # Invalid names
        invalid_names = [
            "-starts-with-hyphen",
            "ends-with-hyphen-",
            "UPPERCASE",
            "has_underscore",
            "has.dot",
            "has space",
            "",  # empty
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                SecretReference(name=name)


class TestSecretReferenceEnvVarSyntaxContract:
    """Contract tests for to_env_var_syntax() method stability.

    These tests ensure the dbt environment variable syntax is stable
    and can be reliably used in profiles.yml generation.
    """

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_syntax_format(self) -> None:
        """Contract: to_env_var_syntax() returns dbt env_var() macro format.

        The format must be: {{ env_var('FLOE_SECRET_<NAME>') }}
        """
        ref = SecretReference(name="test")
        result = ref.to_env_var_syntax()

        # Must use dbt env_var() macro syntax
        assert result.startswith("{{ env_var('")
        assert result.endswith("') }}")

        # Must include FLOE_SECRET_ prefix
        assert "FLOE_SECRET_" in result

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_name_is_uppercase_with_underscores(self) -> None:
        """Contract: Secret names are converted to UPPER_CASE with underscores.

        Hyphens become underscores, all letters become uppercase.
        """
        ref = SecretReference(name="db-password")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_DB_PASSWORD') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_includes_key_suffix(self) -> None:
        """Contract: When key is specified, it's appended with underscore.

        Format: FLOE_SECRET_<NAME>_<KEY>
        """
        ref = SecretReference(name="db-creds", key="password")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_DB_CREDS_PASSWORD') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_key_hyphen_conversion(self) -> None:
        """Contract: Key hyphens are also converted to underscores."""
        ref = SecretReference(name="my-secret", key="api-key")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_MY_SECRET_API_KEY') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_without_key(self) -> None:
        """Contract: Without key, only name is used in env var."""
        ref = SecretReference(name="simple-secret")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_SIMPLE_SECRET') }}"

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_numeric_names(self) -> None:
        """Contract: Numeric names work correctly."""
        ref = SecretReference(name="db1-creds", key="value")
        result = ref.to_env_var_syntax()
        assert result == "{{ env_var('FLOE_SECRET_DB1_CREDS_VALUE') }}"


class TestSecretReferenceSourceBehavior:
    """Contract tests for SecretSource enum behavior."""

    @pytest.mark.requirement("7A-FR-010")
    def test_source_enum_values_are_strings(self) -> None:
        """Contract: SecretSource values are lowercase strings.

        This ensures YAML serialization produces human-readable values.
        """
        for source in SecretSource:
            assert isinstance(source.value, str)
            assert source.value == source.value.lower()

    @pytest.mark.requirement("7A-FR-010")
    def test_env_var_syntax_is_source_agnostic(self) -> None:
        """Contract: to_env_var_syntax() works the same for all sources.

        The env var syntax is independent of the secret source - the source
        only affects how the value is resolved at runtime.
        """
        sources_to_test = [
            SecretSource.ENV,
            SecretSource.KUBERNETES,
            SecretSource.VAULT,
            SecretSource.EXTERNAL_SECRETS,
            SecretSource.INFISICAL,
        ]

        expected = "{{ env_var('FLOE_SECRET_TEST_SECRET') }}"

        for source in sources_to_test:
            ref = SecretReference(source=source, name="test-secret")
            assert ref.to_env_var_syntax() == expected


class TestSecretReferenceJsonSerialization:
    """Contract tests for JSON serialization/deserialization stability."""

    @pytest.mark.requirement("7A-FR-010")
    def test_json_roundtrip_is_lossless(self) -> None:
        """Contract: JSON serialization/deserialization is lossless.

        SecretReferences must survive roundtrip through JSON without data loss.
        This is critical for CompiledArtifacts serialization.
        """
        original = SecretReference(
            source=SecretSource.VAULT,
            name="db-creds",
            key="password",
        )

        json_str = original.model_dump_json()
        restored = SecretReference.model_validate_json(json_str)

        assert restored == original
        assert restored.source == original.source
        assert restored.name == original.name
        assert restored.key == original.key

    @pytest.mark.requirement("7A-FR-010")
    def test_json_roundtrip_all_sources(self) -> None:
        """Contract: All source types survive JSON roundtrip."""
        for source in SecretSource:
            original = SecretReference(source=source, name="test-secret")
            json_str = original.model_dump_json()
            restored = SecretReference.model_validate_json(json_str)
            assert restored == original

    @pytest.mark.requirement("7A-FR-010")
    def test_json_roundtrip_minimal(self) -> None:
        """Contract: Minimal SecretReference survives JSON roundtrip."""
        original = SecretReference(name="minimal")
        json_str = original.model_dump_json()
        restored = SecretReference.model_validate_json(json_str)

        assert restored == original
        assert restored.source == SecretSource.KUBERNETES  # Default preserved


class TestSecretReferenceJsonSchema:
    """Contract tests for JSON Schema export stability."""

    @pytest.mark.requirement("7A-FR-010")
    def test_json_schema_includes_examples(self) -> None:
        """Contract: JSON Schema includes usage examples for IDE support."""
        schema = SecretReference.model_json_schema()

        # Must have examples at top level
        assert "examples" in schema
        assert len(schema["examples"]) >= 2

    @pytest.mark.requirement("7A-FR-010")
    def test_json_schema_has_required_properties(self) -> None:
        """Contract: JSON Schema lists 'name' as required."""
        schema = SecretReference.model_json_schema()

        assert "required" in schema
        assert "name" in schema["required"]

    @pytest.mark.requirement("7A-FR-010")
    def test_json_schema_has_name_pattern(self) -> None:
        """Contract: JSON Schema includes name validation pattern."""
        schema = SecretReference.model_json_schema()

        # Check that name property exists and has pattern
        assert "properties" in schema
        assert "name" in schema["properties"]

        name_schema = schema["properties"]["name"]
        # Pattern may be in allOf due to Annotated type
        if "allOf" in name_schema:
            has_pattern = any("pattern" in item for item in name_schema["allOf"])
            assert has_pattern, "Name property missing pattern constraint"
        else:
            assert "pattern" in name_schema, "Name property missing pattern constraint"


class TestSecretReferenceGoldenArtifacts:
    """Contract tests for backwards compatibility with golden artifact fixtures.

    These tests ensure that previously-serialized SecretReference instances
    can still be deserialized correctly, guaranteeing backwards compatibility.
    """

    FIXTURES_DIR = Path(__file__).parent / "fixtures"

    @pytest.mark.requirement("7A-FR-010")
    def test_v1_minimal_fixture_loads(self) -> None:
        """Contract: v1 minimal fixture (name only) still loads correctly."""
        fixture_path = self.FIXTURES_DIR / "v1_secret_reference_minimal.json"
        json_data = fixture_path.read_text()

        ref = SecretReference.model_validate_json(json_data)

        assert ref.name == "simple-secret"
        assert ref.source == SecretSource.KUBERNETES  # Default
        assert ref.key is None

    @pytest.mark.requirement("7A-FR-010")
    def test_v1_kubernetes_fixture_loads(self) -> None:
        """Contract: v1 kubernetes fixture with key still loads correctly."""
        fixture_path = self.FIXTURES_DIR / "v1_secret_reference_kubernetes.json"
        json_data = fixture_path.read_text()

        ref = SecretReference.model_validate_json(json_data)

        assert ref.name == "db-creds"
        assert ref.source == SecretSource.KUBERNETES
        assert ref.key == "password"

    @pytest.mark.requirement("7A-FR-010")
    def test_v1_vault_fixture_loads(self) -> None:
        """Contract: v1 vault fixture (no key) still loads correctly."""
        fixture_path = self.FIXTURES_DIR / "v1_secret_reference_vault.json"
        json_data = fixture_path.read_text()

        ref = SecretReference.model_validate_json(json_data)

        assert ref.name == "api-key"
        assert ref.source == SecretSource.VAULT
        assert ref.key is None

    @pytest.mark.requirement("7A-FR-010")
    def test_all_v1_fixtures_produce_valid_env_var_syntax(self) -> None:
        """Contract: All v1 fixtures produce valid env_var syntax."""
        fixture_files = [
            "v1_secret_reference_minimal.json",
            "v1_secret_reference_kubernetes.json",
            "v1_secret_reference_vault.json",
        ]

        for filename in fixture_files:
            fixture_path = self.FIXTURES_DIR / filename
            json_data = fixture_path.read_text()
            ref = SecretReference.model_validate_json(json_data)

            # Should produce valid dbt env_var syntax
            env_var = ref.to_env_var_syntax()
            assert env_var.startswith("{{ env_var('FLOE_SECRET_")
            assert env_var.endswith("') }}")
