"""Unit tests for PlatformManifest model.

Tests validation of manifest loading including valid configurations,
required fields, field validation, and forward compatibility.

Task: T011, T012, T013, T014, T058, T059
Requirements: FR-001, FR-002, FR-011, FR-013, FR-015, FR-016
"""

from __future__ import annotations

import warnings
from typing import Any

import pytest
from pydantic import ValidationError


class TestPlatformManifestValidLoading:
    """Tests for valid manifest loading (T011)."""

    @pytest.mark.requirement("001-FR-001")
    def test_valid_manifest_minimal(self) -> None:
        """Test that minimal valid manifest is accepted.

        A manifest with only required fields should load successfully.
        """
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "test-platform",
                "version": "1.0.0",
                "owner": "test@example.com",
            },
            plugins={},
        )
        assert manifest.api_version == "floe.dev/v1"
        assert manifest.kind == "Manifest"
        assert manifest.metadata.name == "test-platform"
        assert manifest.scope is None  # 2-tier mode default

    @pytest.mark.requirement("001-FR-001")
    def test_valid_manifest_full(self) -> None:
        """Test that full valid manifest with all fields is accepted."""
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "acme-platform",
                "version": "2.1.0",
                "owner": "platform-team@acme.com",
                "description": "ACME Corporation data platform",
            },
            plugins={
                "compute": {"type": "duckdb"},
                "orchestrator": {"type": "dagster"},
                "catalog": {"type": "polaris"},
            },
            governance={
                "pii_encryption": "required",
                "audit_logging": "enabled",
                "policy_enforcement_level": "strict",
                "data_retention_days": 90,
            },
        )
        assert manifest.metadata.name == "acme-platform"
        assert manifest.plugins.compute is not None
        assert manifest.plugins.compute.type == "duckdb"
        assert manifest.governance is not None
        assert manifest.governance.pii_encryption == "required"

    @pytest.mark.requirement("001-FR-001")
    def test_valid_manifest_enterprise_scope(self) -> None:
        """Test that enterprise-scoped manifest is accepted."""
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "enterprise-platform",
                "version": "1.0.0",
                "owner": "enterprise@corp.com",
            },
            scope="enterprise",
            plugins={},
            approved_plugins={
                "compute": ["duckdb", "snowflake"],
                "orchestrator": ["dagster"],
            },
        )
        assert manifest.scope == "enterprise"
        assert manifest.parent_manifest is None
        assert manifest.approved_plugins is not None
        assert "duckdb" in manifest.approved_plugins["compute"]

    @pytest.mark.requirement("001-FR-001")
    def test_valid_manifest_domain_scope(self) -> None:
        """Test that domain-scoped manifest with parent is accepted."""
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "sales-domain",
                "version": "1.0.0",
                "owner": "sales@corp.com",
            },
            scope="domain",
            parent_manifest="oci://registry.corp.com/manifests/enterprise:v1",
            plugins={},
            approved_products=["product-a", "product-b"],
        )
        assert manifest.scope == "domain"
        assert manifest.parent_manifest is not None
        assert manifest.approved_products is not None

    @pytest.mark.requirement("001-FR-001")
    def test_valid_manifest_from_dict(self) -> None:
        """Test that manifest can be created from a dictionary (YAML-like)."""
        from floe_core.schemas.manifest import PlatformManifest

        data: dict[str, Any] = {
            "api_version": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "test",
                "version": "1.0.0",
                "owner": "test",
            },
            "plugins": {},
        }
        manifest = PlatformManifest.model_validate(data)
        assert manifest.metadata.name == "test"

    @pytest.mark.requirement("001-FR-016")
    def test_manifest_immutable(self) -> None:
        """Test that PlatformManifest is immutable (frozen)."""
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "test",
                "version": "1.0.0",
                "owner": "test",
            },
            plugins={},
        )
        with pytest.raises(ValidationError):
            manifest.scope = "enterprise"  # type: ignore[misc]


class TestPlatformManifestMissingFields:
    """Tests for missing required field errors (T012)."""

    @pytest.mark.requirement("001-FR-002")
    @pytest.mark.requirement("001-FR-013")
    def test_missing_api_version(self) -> None:
        """Test that missing api_version raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                plugins={},
            )
        assert "api_version" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    @pytest.mark.requirement("001-FR-013")
    def test_missing_kind(self) -> None:
        """Test that missing kind raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                plugins={},
            )
        assert "kind" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    @pytest.mark.requirement("001-FR-013")
    def test_missing_metadata(self) -> None:
        """Test that missing metadata raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                plugins={},
            )
        assert "metadata" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    @pytest.mark.requirement("001-FR-013")
    def test_missing_plugins(self) -> None:
        """Test that missing plugins raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
            )
        assert "plugins" in str(exc_info.value)


class TestPlatformManifestInvalidValues:
    """Tests for invalid field value errors (T013)."""

    @pytest.mark.requirement("001-FR-002")
    def test_invalid_api_version(self) -> None:
        """Test that invalid api_version raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="v1",  # Should be "floe.dev/v1"
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                plugins={},
            )
        assert "api_version" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_invalid_kind(self) -> None:
        """Test that invalid kind raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Config",  # Should be "Manifest"
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                plugins={},
            )
        assert "kind" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_invalid_scope(self) -> None:
        """Test that invalid scope raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                scope="invalid",  # type: ignore[arg-type]
                plugins={},
            )
        assert "scope" in str(exc_info.value)

    @pytest.mark.requirement("001-FR-002")
    def test_domain_scope_without_parent(self) -> None:
        """Test that domain scope without parent_manifest raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                scope="domain",
                plugins={},
            )
        assert "parent_manifest" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-002")
    def test_enterprise_scope_with_parent(self) -> None:
        """Test that enterprise scope with parent_manifest raises ValidationError."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                scope="enterprise",
                parent_manifest="oci://some/manifest:v1",
                plugins={},
            )
        assert "parent_manifest" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-002")
    def test_approved_plugins_without_enterprise_scope(self) -> None:
        """Test that approved_plugins without enterprise scope raises error."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                plugins={},
                approved_plugins={"compute": ["duckdb"]},
            )
        assert "approved_plugins" in str(exc_info.value).lower()

    @pytest.mark.requirement("001-FR-002")
    def test_approved_products_without_domain_scope(self) -> None:
        """Test that approved_products without domain scope raises error."""
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                plugins={},
                approved_products=["product-a"],
            )
        assert "approved_products" in str(exc_info.value).lower()


class TestPlatformManifestForwardCompatibility:
    """Tests for unknown field warning (T014)."""

    @pytest.mark.requirement("001-FR-001")
    def test_unknown_field_allowed(self) -> None:
        """Test that unknown fields are allowed (forward compatibility)."""
        from floe_core.schemas.manifest import PlatformManifest

        # Should not raise an error
        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "test",
                "version": "1.0.0",
                "owner": "test",
            },
            plugins={},
            future_field="some_value",  # type: ignore[call-arg]
        )
        # Unknown fields should be accessible via model_extra
        assert hasattr(manifest, "model_extra")

    @pytest.mark.requirement("001-FR-001")
    def test_unknown_field_warning(self) -> None:
        """Test that unknown fields emit a warning."""
        from floe_core.schemas.manifest import PlatformManifest

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                },
                plugins={},
                unknown_experimental_field="value",  # type: ignore[call-arg]
            )
            # Check that a warning was issued
            unknown_warnings = [
                warning for warning in w if "unknown" in str(warning.message).lower()
            ]
            assert len(unknown_warnings) >= 1


class TestPlatformManifestExtraFieldsForbidden:
    """Tests to ensure strict validation when extra fields are not allowed."""

    @pytest.mark.requirement("001-FR-016")
    def test_nested_models_forbid_extra(self) -> None:
        """Test that nested models (metadata, plugins, governance) forbid extra fields."""
        from floe_core.schemas.manifest import PlatformManifest

        # Extra field in metadata should be rejected
        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test",
                    "extra_field": "not allowed",
                },
                plugins={},
            )
        assert "extra" in str(exc_info.value).lower()


class TestEnvironmentAgnosticConfiguration:
    """Tests for environment-agnostic manifest configuration (T058, T059).

    US6: Compiled artifacts are environment-agnostic; FLOE_ENV determines runtime behavior.
    """

    @pytest.mark.requirement("001-FR-011")
    @pytest.mark.requirement("001-FR-015")
    def test_manifest_contains_no_environment_field(self) -> None:
        """Test that manifest schema has no 'environment' field.

        Given a PlatformManifest model,
        When inspecting its fields,
        Then there is no 'environment', 'env', or 'FLOE_ENV' field.
        """
        from floe_core.schemas.manifest import PlatformManifest

        field_names = set(PlatformManifest.model_fields.keys())
        environment_fields = {"environment", "env", "floe_env", "target_env"}

        # No environment-specific fields should exist in the manifest schema
        assert not field_names.intersection(environment_fields), (
            f"Manifest should not have environment fields. Found: "
            f"{field_names.intersection(environment_fields)}"
        )

    @pytest.mark.requirement("001-FR-011")
    @pytest.mark.requirement("001-FR-015")
    def test_manifest_rejects_env_overrides_field(self) -> None:
        """Test that manifest rejects 'env_overrides' field.

        Given a manifest with an 'env_overrides' field,
        When validating the manifest,
        Then the manifest is rejected with a clear error.
        """
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test@example.com",
                },
                plugins={},
                env_overrides={  # type: ignore[call-arg]
                    "dev": {"plugins": {"compute": {"type": "duckdb"}}},
                    "prod": {"plugins": {"compute": {"type": "snowflake"}}},
                },
            )

        error_str = str(exc_info.value).lower()
        assert "env_overrides" in error_str or "environment" in error_str

    @pytest.mark.requirement("001-FR-011")
    @pytest.mark.requirement("001-FR-015")
    def test_manifest_rejects_environments_field(self) -> None:
        """Test that manifest rejects 'environments' field.

        Given a manifest with an 'environments' field,
        When validating the manifest,
        Then the manifest is rejected with a clear error.
        """
        from floe_core.schemas.manifest import PlatformManifest

        with pytest.raises(ValidationError) as exc_info:
            PlatformManifest(
                api_version="floe.dev/v1",
                kind="Manifest",
                metadata={
                    "name": "test",
                    "version": "1.0.0",
                    "owner": "test@example.com",
                },
                plugins={},
                environments=["dev", "staging", "prod"],  # type: ignore[call-arg]
            )

        error_str = str(exc_info.value).lower()
        assert "environments" in error_str or "environment" in error_str

    @pytest.mark.requirement("001-FR-011")
    @pytest.mark.requirement("001-FR-015")
    def test_same_manifest_works_across_environments(self) -> None:
        """Test that same manifest works across dev/staging/prod.

        Given a valid manifest,
        When loading it (simulating different FLOE_ENV values),
        Then the manifest validates identically regardless of environment.
        """
        from floe_core.schemas.manifest import PlatformManifest

        manifest_data: dict[str, Any] = {
            "api_version": "floe.dev/v1",
            "kind": "Manifest",
            "metadata": {
                "name": "acme-platform",
                "version": "1.0.0",
                "owner": "platform@acme.com",
            },
            "plugins": {
                "compute": {"type": "duckdb"},
                "orchestrator": {"type": "dagster"},
            },
        }

        # Manifest validation is independent of any environment context
        # FLOE_ENV is a runtime concept, not a validation concept
        manifest = PlatformManifest.model_validate(manifest_data)

        # Manifest should be identical regardless of which "environment" it's loaded in
        assert manifest.metadata.name == "acme-platform"
        assert manifest.plugins.compute is not None
        assert manifest.plugins.compute.type == "duckdb"

        # Re-validate the same data multiple times (simulating different envs)
        # All validations should produce identical results
        for _ in ["dev", "staging", "prod"]:
            re_manifest = PlatformManifest.model_validate(manifest_data)
            assert re_manifest.metadata.name == manifest.metadata.name
            assert re_manifest.plugins.compute == manifest.plugins.compute

    @pytest.mark.requirement("001-FR-011")
    @pytest.mark.requirement("001-FR-015")
    def test_manifest_no_runtime_resolution_at_validation(self) -> None:
        """Test that manifest validation doesn't resolve any runtime values.

        Given a manifest with secret references,
        When validating the manifest,
        Then secrets remain as placeholders (not resolved).
        """
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "test",
                "version": "1.0.0",
                "owner": "test@example.com",
            },
            plugins={
                "compute": {
                    "type": "snowflake",
                    "connection_secret_ref": "snowflake-credentials",
                },
            },
        )

        # Secret reference should remain as a placeholder, not resolved
        assert manifest.plugins.compute is not None
        assert manifest.plugins.compute.connection_secret_ref == "snowflake-credentials"
        # Should NOT have any resolved value - it's a reference only

    @pytest.mark.requirement("001-FR-011")
    def test_manifest_environment_agnostic_serialization(self) -> None:
        """Test that serialized manifest contains no environment info.

        Given a valid manifest,
        When serializing to dict/JSON,
        Then output contains no environment-specific fields.
        """
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest(
            api_version="floe.dev/v1",
            kind="Manifest",
            metadata={
                "name": "test",
                "version": "1.0.0",
                "owner": "test@example.com",
            },
            plugins={
                "compute": {"type": "duckdb"},
            },
        )

        data = manifest.model_dump(exclude_none=True)

        # No environment keys should exist in serialized output
        forbidden_keys = {"environment", "env", "environments", "env_overrides", "floe_env"}
        all_keys = set(data.keys())
        assert not all_keys.intersection(forbidden_keys), (
            f"Serialized manifest should not contain environment keys. "
            f"Found: {all_keys.intersection(forbidden_keys)}"
        )
