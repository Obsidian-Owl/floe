"""Unit tests for PlatformManifest model.

Tests validation of manifest loading including valid configurations,
required fields, field validation, and forward compatibility.

Task: T011, T012, T013, T014, T049, T058, T059
Requirements: FR-001, FR-002, FR-011, FR-013, FR-015, FR-016, AC-9.1
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml
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
        # Error message uses alias (apiVersion) - case-insensitive check
        error_str = str(exc_info.value).lower()
        assert "apiversion" in error_str or "api_version" in error_str

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
        # Error message uses alias (apiVersion) - case-insensitive check
        error_str = str(exc_info.value).lower()
        assert "apiversion" in error_str or "api_version" in error_str

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
    """Tests for unknown field warning (T014).

    Implements FR-012: Forward Compatibility (unknown fields warning).
    """

    @pytest.mark.requirement("001-FR-012")
    def test_unknown_field_allowed(self) -> None:
        """Test that unknown fields are allowed (forward compatibility).

        FR-012: System MUST issue warnings (not errors) for unknown fields.
        """
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

    @pytest.mark.requirement("001-FR-012")
    def test_unknown_field_warning(self) -> None:
        """Test that unknown fields emit a warning (FR-012)."""
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
        forbidden_keys = {
            "environment",
            "env",
            "environments",
            "env_overrides",
            "floe_env",
        }
        all_keys = set(data.keys())
        assert not all_keys.intersection(forbidden_keys), (
            f"Serialized manifest should not contain environment keys. "
            f"Found: {all_keys.intersection(forbidden_keys)}"
        )


# ---------------------------------------------------------------------------
# Helper: minimal manifest dict factory
# ---------------------------------------------------------------------------
_MINIMAL_MANIFEST: dict[str, Any] = {
    "api_version": "floe.dev/v1",
    "kind": "Manifest",
    "metadata": {
        "name": "test",
        "version": "1.0.0",
        "owner": "test@example.com",
    },
    "plugins": {},
}
"""Reusable minimal manifest dict for observability tests."""


def _minimal_manifest(**overrides: Any) -> dict[str, Any]:
    """Build a minimal manifest dict with optional overrides.

    Args:
        **overrides: Keys to merge into the base manifest dict.

    Returns:
        A fresh copy of the minimal manifest with overrides applied.
    """
    data = {**_MINIMAL_MANIFEST}
    data.update(overrides)
    return data


class TestObservabilityManifestConfigImport:
    """Tests that ObservabilityManifestConfig and sub-models are importable (T049).

    These tests will fail with ImportError until the models are defined
    in floe_core.schemas.manifest.
    """

    @pytest.mark.requirement("AC-9.1")
    def test_import_observability_manifest_config(self) -> None:
        """Test ObservabilityManifestConfig is importable from manifest module."""
        from floe_core.schemas.manifest import ObservabilityManifestConfig  # noqa: F401

    @pytest.mark.requirement("AC-9.1")
    def test_import_tracing_manifest_config(self) -> None:
        """Test TracingManifestConfig is importable from manifest module."""
        from floe_core.schemas.manifest import TracingManifestConfig  # noqa: F401

    @pytest.mark.requirement("AC-9.1")
    def test_import_lineage_manifest_config(self) -> None:
        """Test LineageManifestConfig is importable from manifest module."""
        from floe_core.schemas.manifest import LineageManifestConfig  # noqa: F401

    @pytest.mark.requirement("AC-9.1")
    def test_import_logging_manifest_config(self) -> None:
        """Test LoggingManifestConfig is importable from manifest module."""
        from floe_core.schemas.manifest import LoggingManifestConfig  # noqa: F401


class TestObservabilityDemoManifestLoading:
    """Tests that loading demo/manifest.yaml populates observability as a typed field (T049).

    Validates AC-9.1: loading the demo manifest.yaml populates
    manifest.observability as a typed ObservabilityManifestConfig.
    """

    @staticmethod
    def _load_demo_manifest() -> Any:
        """Load the demo manifest.yaml and parse via PlatformManifest.

        Returns:
            A PlatformManifest instance loaded from the demo manifest file.
        """
        from floe_core.schemas.manifest import PlatformManifest

        demo_path = Path(__file__).resolve().parents[5] / "demo" / "manifest.yaml"
        assert demo_path.exists(), f"Demo manifest not found at {demo_path}"

        with open(demo_path) as f:
            data: dict[str, Any] = yaml.safe_load(f)

        return PlatformManifest.model_validate(data)

    @pytest.mark.requirement("AC-9.1")
    def test_demo_manifest_observability_is_typed(self) -> None:
        """Test that demo manifest.observability is an ObservabilityManifestConfig instance.

        Not a plain dict and not stuffed into model_extra.
        """
        from floe_core.schemas.manifest import ObservabilityManifestConfig

        manifest = self._load_demo_manifest()
        assert isinstance(manifest.observability, ObservabilityManifestConfig), (
            f"Expected ObservabilityManifestConfig, got {type(manifest.observability)}"
        )

    @pytest.mark.requirement("AC-9.1")
    def test_demo_manifest_tracing_endpoint(self) -> None:
        """Test manifest.observability.tracing.endpoint matches demo value."""
        manifest = self._load_demo_manifest()
        assert manifest.observability.tracing.endpoint == "http://floe-platform-otel:4317"

    @pytest.mark.requirement("AC-9.1")
    def test_demo_manifest_lineage_endpoint(self) -> None:
        """Test manifest.observability.lineage.endpoint matches demo value."""
        manifest = self._load_demo_manifest()
        assert (
            manifest.observability.lineage.endpoint
            == "http://floe-platform-marquez:5000/api/v1/lineage"
        )

    @pytest.mark.requirement("AC-9.1")
    def test_demo_manifest_logging_level(self) -> None:
        """Test manifest.observability.logging.level matches demo value."""
        manifest = self._load_demo_manifest()
        assert manifest.observability.logging.level == "INFO"

    @pytest.mark.requirement("AC-9.1")
    def test_demo_manifest_tracing_sub_fields(self) -> None:
        """Test tracing sub-model fields are populated from demo manifest.

        Verifies enabled and exporter are set correctly, ensuring
        the model actually parses nested YAML fields rather than
        accepting any dict shape.
        """
        from floe_core.schemas.manifest import TracingManifestConfig

        manifest = self._load_demo_manifest()
        tracing = manifest.observability.tracing
        assert isinstance(tracing, TracingManifestConfig)
        assert tracing.enabled is True
        assert tracing.exporter == "otlp"

    @pytest.mark.requirement("AC-9.1")
    def test_demo_manifest_lineage_sub_fields(self) -> None:
        """Test lineage sub-model fields are populated from demo manifest.

        Verifies enabled and transport are set correctly.
        """
        from floe_core.schemas.manifest import LineageManifestConfig

        manifest = self._load_demo_manifest()
        lineage = manifest.observability.lineage
        assert isinstance(lineage, LineageManifestConfig)
        assert lineage.enabled is True
        assert lineage.transport == "http"

    @pytest.mark.requirement("AC-9.1")
    def test_demo_manifest_logging_sub_fields(self) -> None:
        """Test logging sub-model fields are populated from demo manifest.

        Verifies format is set correctly.
        """
        from floe_core.schemas.manifest import LoggingManifestConfig

        manifest = self._load_demo_manifest()
        logging_cfg = manifest.observability.logging
        assert isinstance(logging_cfg, LoggingManifestConfig)
        assert logging_cfg.format == "json"

    @pytest.mark.requirement("AC-9.1")
    def test_demo_manifest_observability_not_in_model_extra(self) -> None:
        """Test that 'observability' does NOT appear in model_extra keys.

        After adding the typed field, observability should be parsed
        as a proper field, not captured as an unknown extra.
        """
        manifest = self._load_demo_manifest()
        extra_keys = set(manifest.model_extra.keys()) if manifest.model_extra else set()
        assert "observability" not in extra_keys, (
            f"'observability' should NOT be in model_extra, but found: {extra_keys}"
        )


class TestObservabilityOptionalField:
    """Tests that PlatformManifest without observability still loads (T049).

    AC-9.1: PlatformManifest without observability still loads (field is Optional).
    """

    @pytest.mark.requirement("AC-9.1")
    def test_manifest_without_observability_loads(self) -> None:
        """Test that manifest without observability field is valid.

        The observability field must be Optional with a default of None.
        """
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest.model_validate(_minimal_manifest())
        assert manifest.observability is None

    @pytest.mark.requirement("AC-9.1")
    def test_manifest_without_observability_has_no_extra(self) -> None:
        """Test that omitting observability does not pollute model_extra."""
        from floe_core.schemas.manifest import PlatformManifest

        manifest = PlatformManifest.model_validate(_minimal_manifest())
        extra_keys = set(manifest.model_extra.keys()) if manifest.model_extra else set()
        assert "observability" not in extra_keys


class TestObservabilityDefaults:
    """Tests for boundary conditions BC-9.1 and BC-9.2 (T049).

    BC-9.1: Empty observability uses all defaults.
    BC-9.2: Partial observability uses defaults for missing sub-sections.
    """

    @pytest.mark.requirement("AC-9.1")
    def test_empty_observability_uses_defaults(self) -> None:
        """Test that observability: {} populates all sub-models with defaults.

        BC-9.1: Empty observability block should result in
        tracing.enabled=True, lineage defaults, logging defaults.
        """
        from floe_core.schemas.manifest import (
            ObservabilityManifestConfig,
            PlatformManifest,
        )

        data = _minimal_manifest(observability={})
        manifest = PlatformManifest.model_validate(data)

        assert manifest.observability is not None
        assert isinstance(manifest.observability, ObservabilityManifestConfig)

        # Tracing defaults
        assert manifest.observability.tracing is not None
        assert manifest.observability.tracing.enabled is True

        # Lineage defaults
        assert manifest.observability.lineage is not None
        assert manifest.observability.lineage.enabled is True

        # Logging defaults
        assert manifest.observability.logging is not None
        assert manifest.observability.logging.level == "INFO"

    @pytest.mark.requirement("AC-9.1")
    def test_empty_observability_tracing_has_no_endpoint(self) -> None:
        """Test that default tracing does not have a hardcoded endpoint.

        When tracing is defaulted (no explicit config), endpoint should
        be None or a sensible default -- NOT the demo manifest endpoint.
        A sloppy implementation that hardcodes the demo value would fail this.
        """
        from floe_core.schemas.manifest import PlatformManifest

        data = _minimal_manifest(observability={})
        manifest = PlatformManifest.model_validate(data)

        # Default endpoint should be None since no endpoint was provided
        assert manifest.observability.tracing.endpoint is None

    @pytest.mark.requirement("AC-9.1")
    def test_partial_observability_tracing_only(self) -> None:
        """Test that providing only tracing uses defaults for lineage and logging.

        BC-9.2: Manifest with observability.tracing only should
        still have lineage and logging with their default values.
        """
        from floe_core.schemas.manifest import PlatformManifest

        data = _minimal_manifest(
            observability={
                "tracing": {
                    "enabled": True,
                    "exporter": "otlp",
                    "endpoint": "http://custom-otel:4317",
                },
            }
        )
        manifest = PlatformManifest.model_validate(data)

        # Tracing should have the explicit values
        assert manifest.observability.tracing.enabled is True
        assert manifest.observability.tracing.exporter == "otlp"
        assert manifest.observability.tracing.endpoint == "http://custom-otel:4317"

        # Lineage and logging should exist with defaults
        assert manifest.observability.lineage is not None
        assert manifest.observability.logging is not None

    @pytest.mark.requirement("AC-9.1")
    def test_partial_observability_lineage_only(self) -> None:
        """Test that providing only lineage uses defaults for tracing and logging.

        BC-9.2: Ensures that omitting tracing and logging sub-sections
        still produces valid default sub-models.
        """
        from floe_core.schemas.manifest import PlatformManifest

        data = _minimal_manifest(
            observability={
                "lineage": {
                    "enabled": True,
                    "transport": "http",
                    "endpoint": "http://marquez:5000/api/v1/lineage",
                },
            }
        )
        manifest = PlatformManifest.model_validate(data)

        # Lineage should have explicit values
        assert manifest.observability.lineage.enabled is True
        assert manifest.observability.lineage.transport == "http"
        assert manifest.observability.lineage.endpoint == "http://marquez:5000/api/v1/lineage"

        # Tracing and logging should exist with defaults
        assert manifest.observability.tracing is not None
        assert manifest.observability.tracing.enabled is True
        assert manifest.observability.logging is not None

    @pytest.mark.requirement("AC-9.1")
    def test_partial_observability_logging_only(self) -> None:
        """Test that providing only logging uses defaults for tracing and lineage.

        BC-9.2: Symmetric test for the logging-only case.
        """
        from floe_core.schemas.manifest import PlatformManifest

        data = _minimal_manifest(
            observability={
                "logging": {
                    "level": "DEBUG",
                    "format": "text",
                },
            }
        )
        manifest = PlatformManifest.model_validate(data)

        # Logging should have explicit values
        assert manifest.observability.logging.level == "DEBUG"
        assert manifest.observability.logging.format == "text"

        # Tracing and lineage should exist with defaults
        assert manifest.observability.tracing is not None
        assert manifest.observability.lineage is not None


class TestObservabilityForwardCompatibility:
    """Tests that observability no longer triggers unknown-field warnings (T049).

    AC-9.1: observability is now a known field and must NOT appear
    in the warn_on_extra_fields warning list.
    """

    @pytest.mark.requirement("AC-9.1")
    def test_observability_does_not_trigger_unknown_field_warning(self) -> None:
        """Test that providing observability does not emit an unknown-field warning.

        After implementation, observability is a declared field, so the
        warn_on_extra_fields model_validator must not fire for it.
        """
        from floe_core.schemas.manifest import PlatformManifest

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PlatformManifest.model_validate(
                _minimal_manifest(
                    observability={
                        "tracing": {"enabled": True, "endpoint": "http://otel:4317"},
                    }
                )
            )

            observability_warnings = [
                warning for warning in w if "observability" in str(warning.message).lower()
            ]
            assert len(observability_warnings) == 0, (
                f"Observability should not trigger unknown-field warnings, "
                f"but got: {[str(ww.message) for ww in observability_warnings]}"
            )

    @pytest.mark.requirement("AC-9.1")
    def test_other_unknown_fields_still_warn(self) -> None:
        """Test that truly unknown fields still trigger warnings.

        Ensures that adding observability did not break the
        warn_on_extra_fields mechanism for other unknown fields.
        """
        from floe_core.schemas.manifest import PlatformManifest

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PlatformManifest.model_validate(
                _minimal_manifest(
                    observability={},
                    totally_unknown_field="surprise",  # Should still warn
                )
            )

            unknown_warnings = [
                warning for warning in w if "unknown" in str(warning.message).lower()
            ]
            assert len(unknown_warnings) >= 1, (
                "Unknown fields other than observability should still trigger warnings"
            )

    @pytest.mark.requirement("AC-9.1")
    def test_observability_is_in_model_fields(self) -> None:
        """Test that 'observability' is a declared field on PlatformManifest.

        This verifies it is part of the Pydantic schema, not just
        captured in model_extra.
        """
        from floe_core.schemas.manifest import PlatformManifest

        assert "observability" in PlatformManifest.model_fields, (
            "'observability' must be a declared field on PlatformManifest, "
            f"but model_fields keys are: {list(PlatformManifest.model_fields.keys())}"
        )


class TestObservabilityManifestConfigModel:
    """Tests for ObservabilityManifestConfig model structure (T049).

    Validates that the model is a proper Pydantic BaseModel with
    the expected sub-fields and behavior.
    """

    @pytest.mark.requirement("AC-9.1")
    def test_observability_config_default_construction(self) -> None:
        """Test that ObservabilityManifestConfig() works with no args.

        All fields have defaults, so constructing with no args must succeed.
        """
        from floe_core.schemas.manifest import ObservabilityManifestConfig

        config = ObservabilityManifestConfig()
        assert config.tracing is not None
        assert config.tracing.enabled is True
        assert config.lineage is not None
        assert config.lineage.enabled is True
        assert config.logging is not None
        assert config.logging.level == "INFO"

    @pytest.mark.requirement("AC-9.1")
    def test_tracing_config_default_construction(self) -> None:
        """Test that TracingManifestConfig() works with no args and has defaults."""
        from floe_core.schemas.manifest import TracingManifestConfig

        tracing = TracingManifestConfig()
        assert tracing.enabled is True
        assert tracing.endpoint is None

    @pytest.mark.requirement("AC-9.1")
    def test_lineage_config_default_construction(self) -> None:
        """Test that LineageManifestConfig() works with no args and has defaults."""
        from floe_core.schemas.manifest import LineageManifestConfig

        lineage = LineageManifestConfig()
        assert lineage.enabled is True
        assert lineage.transport == "http"
        assert lineage.endpoint is None

    @pytest.mark.requirement("AC-9.1")
    def test_logging_config_default_construction(self) -> None:
        """Test that LoggingManifestConfig() works with no args and has defaults."""
        from floe_core.schemas.manifest import LoggingManifestConfig

        logging_cfg = LoggingManifestConfig()
        assert logging_cfg.level == "INFO"
        assert logging_cfg.format == "json"

    @pytest.mark.requirement("AC-9.1")
    def test_observability_config_is_frozen(self) -> None:
        """Test that ObservabilityManifestConfig is immutable (frozen).

        Consistent with PlatformManifest and GovernanceConfig being frozen.
        """
        from floe_core.schemas.manifest import ObservabilityManifestConfig

        config = ObservabilityManifestConfig()
        with pytest.raises(ValidationError):
            config.tracing = None  # type: ignore[misc]

    @pytest.mark.requirement("AC-9.1")
    def test_observability_roundtrip_serialization(self) -> None:
        """Test that ObservabilityManifestConfig roundtrips through dict.

        Construct, dump to dict, re-validate from dict, verify equality.
        A sloppy implementation that drops fields or changes types would fail.
        """
        from floe_core.schemas.manifest import ObservabilityManifestConfig

        original = ObservabilityManifestConfig()
        dumped = original.model_dump()
        restored = ObservabilityManifestConfig.model_validate(dumped)

        assert restored.tracing.enabled == original.tracing.enabled
        assert restored.lineage.endpoint == original.lineage.endpoint
        assert restored.logging.level == original.logging.level
