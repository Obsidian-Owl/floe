"""Unit tests for ArtifactsConfig and PlatformManifest.artifacts field.

Tests Epic 8C artifacts configuration integration with PlatformManifest.

Requirements tested:
    FR-009a: ArtifactsConfig schema integration with manifest
"""

from __future__ import annotations

import pytest


class TestArtifactsConfig:
    """Tests for ArtifactsConfig Pydantic model."""

    @pytest.mark.requirement("8C-FR-009a")
    def test_artifacts_config_with_registry_only(self) -> None:
        """Test ArtifactsConfig with just registry configuration."""
        from floe_core.schemas.manifest import ArtifactsConfig
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        config = ArtifactsConfig(registry=registry)
        assert config.registry.uri == "oci://harbor.example.com/floe"
        assert config.promotion is None

    @pytest.mark.requirement("8C-FR-009a")
    def test_artifacts_config_with_promotion(self) -> None:
        """Test ArtifactsConfig with both registry and promotion config."""
        from floe_core.schemas.manifest import ArtifactsConfig
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        promotion = PromotionConfig()  # Uses defaults [dev, staging, prod]
        config = ArtifactsConfig(registry=registry, promotion=promotion)

        assert config.registry.uri == "oci://harbor.example.com/floe"
        assert config.promotion is not None
        assert len(config.promotion.environments) == 3
        assert config.promotion.environments[0].name == "dev"

    @pytest.mark.requirement("8C-FR-009a")
    def test_artifacts_config_frozen(self) -> None:
        """Test ArtifactsConfig is immutable (frozen)."""
        from floe_core.schemas.manifest import ArtifactsConfig
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        config = ArtifactsConfig(registry=registry)

        with pytest.raises(Exception):  # ValidationError for frozen model
            config.promotion = None  # type: ignore[misc]

    @pytest.mark.requirement("8C-FR-009a")
    def test_artifacts_config_extra_forbid(self) -> None:
        """Test ArtifactsConfig rejects unknown fields."""
        from pydantic import ValidationError

        from floe_core.schemas.manifest import ArtifactsConfig
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)

        with pytest.raises(ValidationError, match="extra"):
            ArtifactsConfig(
                registry=registry,
                unknown_field="value",  # type: ignore[call-arg]
            )


class TestPlatformManifestArtifacts:
    """Tests for PlatformManifest.artifacts field."""

    @pytest.mark.requirement("8C-FR-009a")
    def test_manifest_without_artifacts(self) -> None:
        """Test PlatformManifest works without artifacts field."""
        from floe_core.schemas.manifest import PlatformManifest
        from floe_core.schemas.metadata import ManifestMetadata
        from floe_core.schemas.plugins import PluginsConfig

        manifest = PlatformManifest(
            apiVersion="floe.dev/v1",
            kind="Manifest",
            metadata=ManifestMetadata(
                name="test-platform",
                version="1.0.0",
                owner="test@example.com",
            ),
            plugins=PluginsConfig(),
        )
        assert manifest.artifacts is None

    @pytest.mark.requirement("8C-FR-009a")
    def test_manifest_with_artifacts(self) -> None:
        """Test PlatformManifest with artifacts configuration."""
        from floe_core.schemas.manifest import ArtifactsConfig, PlatformManifest
        from floe_core.schemas.metadata import ManifestMetadata
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.plugins import PluginsConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        promotion = PromotionConfig()  # Default [dev, staging, prod]

        manifest = PlatformManifest(
            apiVersion="floe.dev/v1",
            kind="Manifest",
            metadata=ManifestMetadata(
                name="test-platform",
                version="1.0.0",
                owner="test@example.com",
            ),
            plugins=PluginsConfig(),
            artifacts=ArtifactsConfig(registry=registry, promotion=promotion),
        )
        assert manifest.artifacts is not None
        assert manifest.artifacts.registry.uri == "oci://harbor.example.com/floe"
        assert manifest.artifacts.promotion is not None
        assert len(manifest.artifacts.promotion.environments) == 3

    @pytest.mark.requirement("8C-FR-009a")
    def test_manifest_artifacts_default_environments(self) -> None:
        """Test manifest artifacts uses default [dev, staging, prod] environments."""
        from floe_core.schemas.manifest import ArtifactsConfig, PlatformManifest
        from floe_core.schemas.metadata import ManifestMetadata
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.plugins import PluginsConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)

        manifest = PlatformManifest(
            apiVersion="floe.dev/v1",
            kind="Manifest",
            metadata=ManifestMetadata(
                name="test-platform",
                version="1.0.0",
                owner="test@example.com",
            ),
            plugins=PluginsConfig(),
            artifacts=ArtifactsConfig(
                registry=registry,
                promotion=PromotionConfig(),
            ),
        )

        assert manifest.artifacts is not None
        assert manifest.artifacts.promotion is not None
        envs = [e.name for e in manifest.artifacts.promotion.environments]
        assert envs == ["dev", "staging", "prod"]

    @pytest.mark.requirement("8C-FR-009a")
    def test_manifest_artifacts_custom_environments(self) -> None:
        """Test manifest artifacts with custom environment configuration."""
        from floe_core.schemas.manifest import ArtifactsConfig, PlatformManifest
        from floe_core.schemas.metadata import ManifestMetadata
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.plugins import PluginsConfig
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)

        custom_envs = [
            EnvironmentConfig(
                name="test",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
            EnvironmentConfig(
                name="production",
                gates={
                    PromotionGate.POLICY_COMPLIANCE: True,
                    PromotionGate.TESTS: True,
                    PromotionGate.SECURITY_SCAN: True,
                },
            ),
        ]

        manifest = PlatformManifest(
            apiVersion="floe.dev/v1",
            kind="Manifest",
            metadata=ManifestMetadata(
                name="test-platform",
                version="1.0.0",
                owner="test@example.com",
            ),
            plugins=PluginsConfig(),
            artifacts=ArtifactsConfig(
                registry=registry,
                promotion=PromotionConfig(environments=custom_envs),
            ),
        )

        assert manifest.artifacts is not None
        assert manifest.artifacts.promotion is not None
        envs = [e.name for e in manifest.artifacts.promotion.environments]
        assert envs == ["test", "production"]

    @pytest.mark.requirement("8C-FR-009a")
    def test_manifest_json_schema_includes_artifacts(self) -> None:
        """Test PlatformManifest JSON Schema includes artifacts field."""
        from floe_core.schemas.manifest import PlatformManifest

        schema = PlatformManifest.model_json_schema()
        properties = schema.get("properties", {})

        assert "artifacts" in properties
        artifacts_prop = properties["artifacts"]
        # Should be anyOf (ArtifactsConfig | null) or nullable
        assert "anyOf" in artifacts_prop or artifacts_prop.get("type") == "null"
