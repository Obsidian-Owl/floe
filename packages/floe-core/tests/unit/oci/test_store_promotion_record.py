"""Unit tests for promotion record storage (T023).

Tests PromotionController._store_promotion_record() behavior.

Requirements tested:
    FR-008: Store promotion record in OCI annotations
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


class TestStorePromotionRecord:
    """Tests for promotion record storage."""

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

    @pytest.fixture
    def sample_record(self) -> MagicMock:
        """Create a sample PromotionRecord for testing."""
        from floe_core.schemas.promotion import (
            GateResult,
            GateStatus,
            PromotionGate,
            PromotionRecord,
        )

        return PromotionRecord(
            promotion_id=uuid4(),
            artifact_digest="sha256:" + "a" * 64,  # Valid 64-char hex
            artifact_tag="v1.2.3",
            source_environment="dev",
            target_environment="staging",
            gate_results=[
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                ),
            ],
            signature_verified=True,
            operator="ci@github.com",
            promoted_at=datetime.now(timezone.utc),
            dry_run=False,
            trace_id="trace123",
            authorization_passed=True,
        )

    @pytest.mark.requirement("8C-FR-008")
    def test_store_promotion_record_stores_to_oci(
        self, controller: MagicMock, sample_record: MagicMock
    ) -> None:
        """Test _store_promotion_record stores record to OCI annotations."""
        with patch.object(
            controller.client, "_update_artifact_annotations"
        ) as mock_update:
            controller._store_promotion_record(
                tag="v1.2.3-staging",
                record=sample_record,
            )

            mock_update.assert_called_once()
            call_args = mock_update.call_args
            # First positional arg is tag
            assert call_args[0][0] == "v1.2.3-staging"
            # Second positional arg is annotations dict
            annotations = call_args[0][1]
            assert "dev.floe.promotion" in annotations

    @pytest.mark.requirement("8C-FR-008")
    def test_store_promotion_record_uses_annotation_key(
        self, controller: MagicMock, sample_record: MagicMock
    ) -> None:
        """Test _store_promotion_record uses correct annotation key."""
        with patch.object(
            controller.client, "_update_artifact_annotations"
        ) as mock_update:
            controller._store_promotion_record(
                tag="v1.2.3-staging",
                record=sample_record,
            )

            annotations = mock_update.call_args[0][1]
            # Should use dev.floe.promotion as the annotation key
            assert "dev.floe.promotion" in annotations

    @pytest.mark.requirement("8C-FR-008")
    def test_store_promotion_record_serializes_record_as_json(
        self, controller: MagicMock, sample_record: MagicMock
    ) -> None:
        """Test _store_promotion_record serializes record as JSON."""
        import json

        with patch.object(
            controller.client, "_update_artifact_annotations"
        ) as mock_update:
            controller._store_promotion_record(
                tag="v1.2.3-staging",
                record=sample_record,
            )

            annotations = mock_update.call_args[0][1]
            json_value = annotations["dev.floe.promotion"]

            # Should be valid JSON
            parsed = json.loads(json_value)
            assert "promotion_id" in parsed
            assert "artifact_digest" in parsed
            assert parsed["source_environment"] == "dev"
            assert parsed["target_environment"] == "staging"

    @pytest.mark.requirement("8C-FR-008")
    def test_store_promotion_record_includes_all_fields(
        self, controller: MagicMock, sample_record: MagicMock
    ) -> None:
        """Test _store_promotion_record includes all record fields."""
        import json

        with patch.object(
            controller.client, "_update_artifact_annotations"
        ) as mock_update:
            controller._store_promotion_record(
                tag="v1.2.3-staging",
                record=sample_record,
            )

            annotations = mock_update.call_args[0][1]
            parsed = json.loads(annotations["dev.floe.promotion"])

            # Verify required fields
            assert "promotion_id" in parsed
            assert "artifact_digest" in parsed
            assert "artifact_tag" in parsed
            assert "source_environment" in parsed
            assert "target_environment" in parsed
            assert "gate_results" in parsed
            assert "signature_verified" in parsed
            assert "operator" in parsed
            assert "promoted_at" in parsed
            assert "dry_run" in parsed
            assert "trace_id" in parsed
            assert "authorization_passed" in parsed

    @pytest.mark.requirement("8C-FR-008")
    def test_store_promotion_record_returns_none(
        self, controller: MagicMock, sample_record: MagicMock
    ) -> None:
        """Test _store_promotion_record returns None on success."""
        with patch.object(controller.client, "_update_artifact_annotations"):
            result = controller._store_promotion_record(
                tag="v1.2.3-staging",
                record=sample_record,
            )

            assert result is None

    @pytest.mark.requirement("8C-FR-008")
    def test_store_promotion_record_logs_operation(
        self, controller: MagicMock, sample_record: MagicMock
    ) -> None:
        """Test _store_promotion_record logs the storage operation."""
        with (
            patch.object(controller.client, "_update_artifact_annotations"),
            patch.object(controller, "_log") as mock_log,
        ):
            controller._store_promotion_record(
                tag="v1.2.3-staging",
                record=sample_record,
            )

            # Should log start and completion
            assert mock_log.info.call_count >= 1
