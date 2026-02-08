"""Unit tests for mutable latest tag update (T022).

Tests PromotionController._update_latest_tag() behavior.

Requirements tested:
    FR-003: Mutable "latest" tag update
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestUpdateLatestTag:
    """Tests for mutable latest tag update."""

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

    @pytest.mark.requirement("8C-FR-003")
    def test_update_latest_tag_creates_mutable_tag(self, controller: MagicMock) -> None:
        """Test _update_latest_tag creates mutable latest-{env} tag."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(
                controller.client, "_create_oras_client"
            ) as mock_oras_client_factory,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:abc123"
            mock_inspect.return_value = mock_manifest

            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {"config": {}, "layers": []}
            mock_oras_client_factory.return_value = mock_oras

            tag = controller._update_latest_tag(
                source_tag="v1.2.3",
                target_env="staging",
            )

            # Should create tag in format: latest-{env}
            assert tag == "latest-staging"

    @pytest.mark.requirement("8C-FR-003")
    def test_update_latest_tag_format(self, controller: MagicMock) -> None:
        """Test _update_latest_tag returns correct tag format."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(
                controller.client, "_create_oras_client"
            ) as mock_oras_client_factory,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:def456"
            mock_inspect.return_value = mock_manifest

            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {"config": {}, "layers": []}
            mock_oras_client_factory.return_value = mock_oras

            # Test various environment names
            tag_staging = controller._update_latest_tag(
                source_tag="v2.0.0", target_env="staging"
            )
            assert tag_staging == "latest-staging"

            tag_prod = controller._update_latest_tag(
                source_tag="v2.0.0", target_env="prod"
            )
            assert tag_prod == "latest-prod"

            tag_dev = controller._update_latest_tag(
                source_tag="v2.0.0", target_env="dev"
            )
            assert tag_dev == "latest-dev"

    @pytest.mark.requirement("8C-FR-003")
    def test_update_latest_tag_overwrites_existing(self, controller: MagicMock) -> None:
        """Test _update_latest_tag overwrites existing mutable tag."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(controller.client, "tag_exists", return_value=True),
            patch.object(
                controller.client, "_create_oras_client"
            ) as mock_oras_client_factory,
        ):
            # New artifact to promote
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:newdigest"
            mock_inspect.return_value = mock_manifest

            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {"config": {}, "layers": []}
            mock_oras_client_factory.return_value = mock_oras

            # Should succeed even if tag exists (mutable)
            tag = controller._update_latest_tag(
                source_tag="v1.3.0",
                target_env="staging",
            )

            assert tag == "latest-staging"
            # Should have uploaded manifest to overwrite
            mock_oras.upload_manifest.assert_called()

    @pytest.mark.requirement("8C-FR-003")
    def test_update_latest_tag_uses_source_manifest(
        self, controller: MagicMock
    ) -> None:
        """Test _update_latest_tag copies manifest from source tag."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(
                controller.client, "_create_oras_client"
            ) as mock_oras_client_factory,
            patch.object(controller.client, "_build_target_ref") as mock_build_ref,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:abc123"
            mock_inspect.return_value = mock_manifest

            source_manifest_data = {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": "sha256:config123"},
                "layers": [{"digest": "sha256:layer123"}],
            }
            mock_oras = Mock()
            mock_oras.get_manifest.return_value = source_manifest_data
            mock_oras_client_factory.return_value = mock_oras

            mock_build_ref.side_effect = lambda t: f"harbor.example.com/floe:{t}"

            controller._update_latest_tag(
                source_tag="v1.2.3",
                target_env="staging",
            )

            # Should have fetched manifest from source tag
            mock_oras.get_manifest.assert_called()
            # Should have uploaded to latest-staging
            mock_oras.upload_manifest.assert_called_once()
            call_kwargs = mock_oras.upload_manifest.call_args
            assert "latest-staging" in str(call_kwargs)

    @pytest.mark.requirement("8C-FR-003")
    def test_update_latest_tag_returns_tag_name(self, controller: MagicMock) -> None:
        """Test _update_latest_tag returns the updated tag name."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(
                controller.client, "_create_oras_client"
            ) as mock_oras_client_factory,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:abc123"
            mock_inspect.return_value = mock_manifest

            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {"config": {}, "layers": []}
            mock_oras_client_factory.return_value = mock_oras

            tag = controller._update_latest_tag(
                source_tag="v1.0.0",
                target_env="prod",
            )

            assert isinstance(tag, str)
            assert tag == "latest-prod"

    @pytest.mark.requirement("8C-FR-003")
    def test_update_latest_tag_from_env_tag(self, controller: MagicMock) -> None:
        """Test _update_latest_tag can use environment tag as source."""
        with (
            patch.object(controller.client, "inspect") as mock_inspect,
            patch.object(
                controller.client, "_create_oras_client"
            ) as mock_oras_client_factory,
        ):
            mock_manifest = Mock()
            mock_manifest.digest = "sha256:abc123"
            mock_inspect.return_value = mock_manifest

            mock_oras = Mock()
            mock_oras.get_manifest.return_value = {"config": {}, "layers": []}
            mock_oras_client_factory.return_value = mock_oras

            # Use env-specific tag as source (e.g., after creating v1.2.3-staging)
            tag = controller._update_latest_tag(
                source_tag="v1.2.3-staging",
                target_env="staging",
            )

            assert tag == "latest-staging"
