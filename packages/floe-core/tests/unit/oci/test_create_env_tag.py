"""Unit tests for environment tag creation (T021).

Tests PromotionController._create_env_tag() behavior.

Requirements tested:
    FR-002: Immutable environment-specific tag creation
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestCreateEnvTag:
    """Tests for environment tag creation."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked OCI client."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-002")
    def test_create_env_tag_creates_immutable_tag(self, controller: MagicMock) -> None:
        """Test _create_env_tag creates immutable environment-specific tag."""
        # Mock the OCI client methods
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(controller.client, "tag_exists", return_value=False),
            patch.object(controller.client, "_create_oras_client") as mock_oras_client_factory,
        ):
            # Setup mock inspect to return artifact with digest
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:abc123"
            mock_inspect.return_value = mock_manifest

            # Setup mock ORAS client
            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {"config": {}, "layers": []}
            mock_oras_client_factory.return_value = mock_oras

            tag = controller._create_env_tag(
                source_tag="v1.2.3",
                target_env="staging",
            )

            # Should create tag in format: source_tag-target_env
            assert tag == "v1.2.3-staging"

    @pytest.mark.requirement("8C-FR-002")
    def test_create_env_tag_format(self, controller: MagicMock) -> None:
        """Test _create_env_tag returns correct tag format."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(controller.client, "tag_exists", return_value=False),
            patch.object(controller.client, "_create_oras_client") as mock_oras_client_factory,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:def456"
            mock_inspect.return_value = mock_manifest

            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {"config": {}, "layers": []}
            mock_oras_client_factory.return_value = mock_oras

            # Test various environment names
            tag_staging = controller._create_env_tag(source_tag="v2.0.0", target_env="staging")
            assert tag_staging == "v2.0.0-staging"

            tag_prod = controller._create_env_tag(source_tag="v2.0.0", target_env="prod")
            assert tag_prod == "v2.0.0-prod"

            tag_qa = controller._create_env_tag(source_tag="v2.0.0", target_env="qa")
            assert tag_qa == "v2.0.0-qa"

    @pytest.mark.requirement("8C-FR-002")
    def test_create_env_tag_raises_when_tag_exists(self, controller: MagicMock) -> None:
        """Test _create_env_tag raises error if immutable tag already exists."""
        from floe_core.oci.errors import ImmutabilityViolationError

        with (
            patch.object(controller.client, "tag_exists", return_value=True),
            patch.object(controller.client, "inspect") as mock_inspect,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:existing123"
            mock_inspect.return_value = mock_manifest

            with pytest.raises(ImmutabilityViolationError):
                controller._create_env_tag(
                    source_tag="v1.2.3",
                    target_env="staging",
                )

    @pytest.mark.requirement("8C-FR-002")
    def test_create_env_tag_allows_force_when_same_digest(self, controller: MagicMock) -> None:
        """Test _create_env_tag allows force when digests match (idempotent)."""
        with (
            patch.object(controller.client, "tag_exists", return_value=True),
            patch.object(controller.client, "inspect") as mock_inspect,
        ):
            # Both source and target have same digest
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:same123"
            mock_inspect.return_value = mock_manifest

            # Should not raise when force=True and digests match
            tag = controller._create_env_tag(
                source_tag="v1.2.3",
                target_env="staging",
                force=True,
            )

            # Returns the tag without re-creating (idempotent)
            assert tag == "v1.2.3-staging"

    @pytest.mark.requirement("8C-FR-002")
    def test_create_env_tag_uses_oras_upload_manifest(self, controller: MagicMock) -> None:
        """Test _create_env_tag uses ORAS upload_manifest for tag creation."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(controller.client, "tag_exists", return_value=False),
            patch.object(controller.client, "_create_oras_client") as mock_oras_client_factory,
            patch.object(controller.client, "_build_target_ref") as mock_build_ref,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:abc123"
            mock_inspect.return_value = mock_manifest

            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {},
                "layers": [],
            }
            mock_oras_client_factory.return_value = mock_oras

            mock_build_ref.side_effect = lambda t: f"harbor.example.com/floe:{t}"

            controller._create_env_tag(
                source_tag="v1.2.3",
                target_env="staging",
            )

            # Should have called upload_manifest with new tag
            mock_oras.upload_manifest.assert_called_once()
            call_args = mock_oras.upload_manifest.call_args
            # First positional arg should be the manifest
            # Container should be the new tag
            assert "v1.2.3-staging" in str(call_args)

    @pytest.mark.requirement("8C-FR-002")
    def test_create_env_tag_returns_created_tag_name(self, controller: MagicMock) -> None:
        """Test _create_env_tag returns the created tag name."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(controller.client, "tag_exists", return_value=False),
            patch.object(controller.client, "_create_oras_client") as mock_oras_client_factory,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:abc123"
            mock_inspect.return_value = mock_manifest

            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {"config": {}, "layers": []}
            mock_oras_client_factory.return_value = mock_oras

            tag = controller._create_env_tag(
                source_tag="v1.0.0",
                target_env="prod",
            )

            assert isinstance(tag, str)
            assert tag == "v1.0.0-prod"
