"""Unit tests for secret reference validation in RBAC generation.

Tests the validate_secret_references function that ensures all secret
references are covered by RBAC permissions before generation.

Task: T049
User Story: US4 - RBAC Manifest Generation
Requirements: FR-073
"""

from __future__ import annotations

import pytest


class TestSecretReferenceValidationBasics:
    """Unit tests for basic secret reference validation behavior."""

    @pytest.mark.requirement("FR-073")
    def test_valid_secret_references_pass_validation(self) -> None:
        """Test validation passes when all references have permissions."""
        from floe_core.rbac.generator import validate_secret_references

        # Secret references that need access
        secret_refs = ["snowflake-creds", "catalog-creds"]

        # Permissions covering those secrets
        permitted_secrets = {"snowflake-creds", "catalog-creds", "api-key"}

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        assert is_valid is True
        assert errors == []

    @pytest.mark.requirement("FR-073")
    def test_missing_permission_fails_validation(self) -> None:
        """Test validation fails when a secret reference lacks permission."""
        from floe_core.rbac.generator import validate_secret_references

        # Secret references including one without permission
        secret_refs = ["snowflake-creds", "missing-secret"]

        # Permissions NOT covering missing-secret
        permitted_secrets = {"snowflake-creds", "catalog-creds"}

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        assert is_valid is False
        assert len(errors) == 1
        assert "missing-secret" in errors[0]

    @pytest.mark.requirement("FR-073")
    def test_multiple_missing_permissions_reports_all(self) -> None:
        """Test validation reports all missing permissions, not just first."""
        from floe_core.rbac.generator import validate_secret_references

        secret_refs = ["secret-a", "secret-b", "secret-c"]
        permitted_secrets = {"secret-a"}  # Only one permitted

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        assert is_valid is False
        assert len(errors) == 2
        error_text = " ".join(errors)
        assert "secret-b" in error_text
        assert "secret-c" in error_text

    @pytest.mark.requirement("FR-073")
    def test_empty_secret_references_passes(self) -> None:
        """Test empty secret references list passes validation."""
        from floe_core.rbac.generator import validate_secret_references

        secret_refs: list[str] = []
        permitted_secrets = {"some-secret"}

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        assert is_valid is True
        assert errors == []

    @pytest.mark.requirement("FR-073")
    def test_empty_permitted_secrets_fails_if_refs_exist(self) -> None:
        """Test validation fails when permissions are empty but refs exist."""
        from floe_core.rbac.generator import validate_secret_references

        secret_refs = ["needed-secret"]
        permitted_secrets: set[str] = set()

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        assert is_valid is False
        assert len(errors) == 1
        assert "needed-secret" in errors[0]


class TestSecretReferenceValidationEdgeCases:
    """Unit tests for edge cases in secret reference validation."""

    @pytest.mark.requirement("FR-073")
    def test_duplicate_secret_refs_validated_once(self) -> None:
        """Test duplicate references don't produce duplicate errors."""
        from floe_core.rbac.generator import validate_secret_references

        # Same secret referenced multiple times, but missing from permissions
        secret_refs = ["missing-secret", "missing-secret", "missing-secret"]
        permitted_secrets = {"other-secret"}

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        assert is_valid is False
        # Should only report missing-secret once
        assert len(errors) == 1
        assert "missing-secret" in errors[0]

    @pytest.mark.requirement("FR-073")
    def test_whitespace_in_secret_refs_handled(self) -> None:
        """Test secret references with whitespace are handled correctly."""
        from floe_core.rbac.generator import validate_secret_references

        # Whitespace-padded reference
        secret_refs = ["  my-secret  "]
        permitted_secrets = {"my-secret"}

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        # Should pass after stripping whitespace
        assert is_valid is True
        assert errors == []

    @pytest.mark.requirement("FR-073")
    def test_case_sensitive_matching(self) -> None:
        """Test secret name matching is case-sensitive."""
        from floe_core.rbac.generator import validate_secret_references

        secret_refs = ["My-Secret"]
        permitted_secrets = {"my-secret"}  # Lowercase

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        # Should fail - K8s names are case-sensitive
        assert is_valid is False
        assert "My-Secret" in errors[0]

    @pytest.mark.requirement("FR-073")
    def test_validation_error_message_format(self) -> None:
        """Test error messages have helpful format."""
        from floe_core.rbac.generator import validate_secret_references

        secret_refs = ["unauthorized-secret"]
        permitted_secrets = {"some-other-secret"}

        is_valid, errors = validate_secret_references(secret_refs, permitted_secrets)

        assert is_valid is False
        assert len(errors) == 1
        # Error should mention the secret and indicate it's not permitted
        error = errors[0]
        assert "unauthorized-secret" in error
        assert "permission" in error.lower() or "rbac" in error.lower()


class TestSecretReferenceValidationIntegration:
    """Tests for validation integration with RBACManifestGenerator."""

    @pytest.mark.requirement("FR-073")
    def test_generator_validate_method_exists(self) -> None:
        """Test RBACManifestGenerator has validate_secret_references method."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        from floe_core.rbac.generator import RBACManifestGenerator

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        assert hasattr(generator, "validate_secret_references")
        assert callable(generator.validate_secret_references)

    @pytest.mark.requirement("FR-073")
    def test_generator_validate_returns_tuple(self) -> None:
        """Test generator validate method returns (bool, list) tuple."""
        from floe_rbac_k8s.plugin import K8sRBACPlugin

        from floe_core.rbac.generator import RBACManifestGenerator

        generator = RBACManifestGenerator(plugin=K8sRBACPlugin())

        result = generator.validate_secret_references(
            secret_references=["secret-a"],
            permitted_secrets={"secret-a"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)
