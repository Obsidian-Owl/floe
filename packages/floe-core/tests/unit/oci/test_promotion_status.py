"""Unit tests for PromotionController.get_status() method (T059).

Tests for querying promotion status across environments:
- T059: Unit tests for get_status()
- T060: Unit tests for output formatting

Requirements tested:
    FR-023: Store promotion metadata in OCI manifest annotations
    FR-024: Emit OpenTelemetry traces for promotion operations
    FR-027: Audit records include required fields

Task: T059
TDD Note: These tests are written FIRST per TDD methodology.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    pass


class TestGetStatusBasic:
    """Unit tests for PromotionController.get_status() basic functionality."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mocked OCIClient for unit testing."""
        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"

        # Mock inspect to return manifest info with promotion annotations
        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:" + "a" * 64
        mock_manifest.annotations = {
            "dev.floe.promotion": '{"promotion_id": "abc123", "environment": "staging"}',
        }
        client.inspect.return_value = mock_manifest

        # Mock list to return environment-specific tags
        mock_tag_dev = MagicMock()
        mock_tag_dev.name = "v1.0.0-dev"
        mock_tag_staging = MagicMock()
        mock_tag_staging.name = "v1.0.0-staging"
        client.list.return_value = [mock_tag_dev, mock_tag_staging]

        return client

    @pytest.fixture
    def controller(self, mock_client: MagicMock) -> MagicMock:
        """Create a PromotionController with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(client=mock_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_method_exists(self, controller: MagicMock) -> None:
        """Test get_status() method exists on PromotionController."""
        assert hasattr(controller, "get_status")
        assert callable(controller.get_status)

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_returns_status_response(self, controller: MagicMock) -> None:
        """Test get_status() returns a PromotionStatusResponse."""
        from floe_core.schemas.promotion import PromotionStatusResponse

        result = controller.get_status(tag="v1.0.0")

        assert isinstance(result, PromotionStatusResponse)

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_includes_tag(
        self, controller: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test status response includes the artifact tag."""
        result = controller.get_status(tag="v1.0.0")

        assert result.tag == "v1.0.0"

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_includes_digest(
        self, controller: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test status response includes the artifact digest."""
        result = controller.get_status(tag="v1.0.0")

        assert result.digest.startswith("sha256:")

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_includes_environment_states(
        self, controller: MagicMock
    ) -> None:
        """Test status response includes state for each environment."""
        result = controller.get_status(tag="v1.0.0")

        assert hasattr(result, "environments")
        assert isinstance(result.environments, dict)


class TestGetStatusEnvironments:
    """Unit tests for get_status() environment tracking."""

    @pytest.fixture
    def mock_client_with_promotions(self) -> MagicMock:
        """Create a mocked client with promotion data in annotations."""
        import json

        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"

        # Mock promotion record in annotations
        promotion_record = {
            "promotion_id": str(uuid4()),
            "artifact_digest": "sha256:" + "a" * 64,
            "source_environment": "dev",
            "target_environment": "staging",
            "operator": "ci@example.com",
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "gate_results": [],
            "signature_verified": True,
        }

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:" + "a" * 64
        mock_manifest.annotations = {
            "dev.floe.promotion": json.dumps(promotion_record),
        }
        client.inspect.return_value = mock_manifest

        # Mock tags showing presence in environments
        mock_tag_dev = MagicMock()
        mock_tag_dev.name = "v1.0.0-dev"
        mock_tag_staging = MagicMock()
        mock_tag_staging.name = "v1.0.0-staging"
        mock_latest_dev = MagicMock()
        mock_latest_dev.name = "latest-dev"
        mock_latest_staging = MagicMock()
        mock_latest_staging.name = "latest-staging"
        client.list.return_value = [
            mock_tag_dev,
            mock_tag_staging,
            mock_latest_dev,
            mock_latest_staging,
        ]

        return client

    @pytest.fixture
    def controller(self, mock_client_with_promotions: MagicMock) -> MagicMock:
        """Create controller with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(
            client=mock_client_with_promotions, promotion=promotion
        )

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_shows_promoted_environments(
        self, controller: MagicMock
    ) -> None:
        """Test status shows which environments the artifact is promoted to."""
        result = controller.get_status(tag="v1.0.0")

        # Should show dev and staging as promoted (based on tags)
        assert "dev" in result.environments
        assert "staging" in result.environments

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_environment_has_promoted_flag(
        self, controller: MagicMock
    ) -> None:
        """Test each environment state has a promoted flag."""
        result = controller.get_status(tag="v1.0.0")

        for _env_name, env_state in result.environments.items():
            assert hasattr(env_state, "promoted")
            assert isinstance(env_state.promoted, bool)

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_environment_has_promoted_at(
        self, controller: MagicMock
    ) -> None:
        """Test promoted environments include promoted_at timestamp."""
        result = controller.get_status(tag="v1.0.0")

        # Promoted environments should have timestamp
        for _env_name, env_state in result.environments.items():
            if env_state.promoted:
                assert env_state.promoted_at is not None


class TestGetStatusWithEnvFilter:
    """Unit tests for get_status() with environment filter."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mocked OCIClient."""
        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:" + "a" * 64
        mock_manifest.annotations = {}
        client.inspect.return_value = mock_manifest
        client.list.return_value = []

        return client

    @pytest.fixture
    def controller(self, mock_client: MagicMock) -> MagicMock:
        """Create controller with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(client=mock_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_with_env_filter(self, controller: MagicMock) -> None:
        """Test get_status() accepts env parameter to filter results."""
        # Should not raise - accepts env parameter
        result = controller.get_status(tag="v1.0.0", env="prod")

        assert result is not None

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_with_env_filter_returns_single_environment(
        self, controller: MagicMock
    ) -> None:
        """Test env filter returns status for only that environment."""
        result = controller.get_status(tag="v1.0.0", env="prod")

        # Should only have the filtered environment
        assert len(result.environments) == 1
        assert "prod" in result.environments


class TestGetStatusHistory:
    """Unit tests for get_status() with promotion history."""

    @pytest.fixture
    def mock_client_with_history(self) -> MagicMock:
        """Create a mocked client with promotion history in annotations."""
        import json

        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"

        # Multiple promotion records representing history
        promotion_history = [
            {
                "promotion_id": str(uuid4()),
                "artifact_digest": "sha256:" + "a" * 64,
                "source_environment": "dev",
                "target_environment": "staging",
                "operator": "ci@example.com",
                "promoted_at": "2026-01-28T10:00:00Z",
            },
            {
                "promotion_id": str(uuid4()),
                "artifact_digest": "sha256:" + "a" * 64,
                "source_environment": "staging",
                "target_environment": "prod",
                "operator": "release@example.com",
                "promoted_at": "2026-01-29T15:00:00Z",
            },
        ]

        mock_manifest = MagicMock()
        mock_manifest.digest = "sha256:" + "a" * 64
        mock_manifest.annotations = {
            "dev.floe.promotion.history": json.dumps(promotion_history),
        }
        client.inspect.return_value = mock_manifest

        mock_tag_dev = MagicMock()
        mock_tag_dev.name = "v1.0.0-dev"
        mock_tag_staging = MagicMock()
        mock_tag_staging.name = "v1.0.0-staging"
        mock_tag_prod = MagicMock()
        mock_tag_prod.name = "v1.0.0-prod"
        client.list.return_value = [mock_tag_dev, mock_tag_staging, mock_tag_prod]

        return client

    @pytest.fixture
    def controller(self, mock_client_with_history: MagicMock) -> MagicMock:
        """Create controller with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(client=mock_client_with_history, promotion=promotion)

    @pytest.mark.requirement("8C-FR-027")
    def test_get_status_includes_history(self, controller: MagicMock) -> None:
        """Test status response includes promotion history."""
        result = controller.get_status(tag="v1.0.0")

        assert hasattr(result, "history")
        assert isinstance(result.history, list)

    @pytest.mark.requirement("8C-FR-027")
    def test_get_status_history_has_required_fields(
        self, controller: MagicMock
    ) -> None:
        """Test history entries have FR-027 required fields."""
        result = controller.get_status(tag="v1.0.0")

        for entry in result.history:
            # FR-027 required fields
            assert hasattr(entry, "promotion_id")
            assert hasattr(entry, "artifact_digest")
            assert hasattr(entry, "source_environment")
            assert hasattr(entry, "target_environment")
            assert hasattr(entry, "operator")
            assert hasattr(entry, "promoted_at")

    @pytest.mark.requirement("8C-FR-027")
    def test_get_status_with_history_limit(self, controller: MagicMock) -> None:
        """Test get_status() accepts history parameter to limit results."""
        result = controller.get_status(tag="v1.0.0", history=1)

        # Should limit history to 1 entry
        assert len(result.history) <= 1


class TestGetStatusNotFound:
    """Unit tests for get_status() when artifact not found."""

    @pytest.fixture
    def mock_client_not_found(self) -> MagicMock:
        """Create a mocked client that raises ArtifactNotFoundError."""
        from floe_core.oci.errors import ArtifactNotFoundError

        client = MagicMock()
        client._build_target_ref.return_value = "harbor.example.com/floe:v1.0.0"
        client.inspect.side_effect = ArtifactNotFoundError(
            tag="v999.0.0",
            registry="oci://harbor.example.com/floe",
        )
        client.list.return_value = []

        return client

    @pytest.fixture
    def controller(self, mock_client_not_found: MagicMock) -> MagicMock:
        """Create controller with mocked client."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import PromotionConfig

        promotion = PromotionConfig()
        return PromotionController(client=mock_client_not_found, promotion=promotion)

    @pytest.mark.requirement("8C-FR-023")
    def test_get_status_raises_for_missing_artifact(
        self, controller: MagicMock
    ) -> None:
        """Test get_status() raises ArtifactNotFoundError for missing tag."""
        from floe_core.oci.errors import ArtifactNotFoundError

        with pytest.raises(ArtifactNotFoundError):
            controller.get_status(tag="v999.0.0")
