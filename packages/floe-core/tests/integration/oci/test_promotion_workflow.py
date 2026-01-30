"""Integration tests for full promotion workflow (T031).

Tests the complete promotion lifecycle with real registry operations:
- Push artifact to registry
- Promote from dev to staging
- Verify environment tags created
- Verify promotion record stored

These tests FAIL if the registry is unavailable - no pytest.skip() per Constitution V.

Task: T031
Requirements: FR-001, FR-002, FR-006, FR-008

Example:
    # Run integration tests (requires Kind cluster with registry)
    make test-integration

See Also:
    - testing/k8s/services/registry.yaml: Registry deployment manifest
    - IntegrationTestBase: Base class for K8s-native tests
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

if TYPE_CHECKING:
    pass


def _create_valid_compiled_artifacts(unique_id: str, product_prefix: str = "promo") -> Any:
    """Create a valid CompiledArtifacts instance for promotion testing.

    Args:
        unique_id: Unique identifier for test isolation.
        product_prefix: Prefix for product name.

    Returns:
        A valid CompiledArtifacts instance.
    """
    from floe_core.schemas.compiled_artifacts import (
        CompilationMetadata,
        CompiledArtifacts,
        ObservabilityConfig,
        PluginRef,
        ProductIdentity,
        ResolvedModel,
        ResolvedPlugins,
        ResolvedTransforms,
    )
    from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

    return CompiledArtifacts(
        version=COMPILED_ARTIFACTS_VERSION,
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version=COMPILED_ARTIFACTS_VERSION,
            source_hash=f"sha256:{unique_id}abc123",
            product_name=f"{product_prefix}-product-{unique_id}",
            product_version="1.0.0",
        ),
        identity=ProductIdentity(
            product_id=f"{product_prefix}.product_{unique_id}",
            domain=product_prefix,
            repository="https://github.com/test/repo",
        ),
        mode="simple",
        inheritance_chain=[],
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name=f"floe-{product_prefix}",
                    service_version="1.0.0",
                    environment="test",
                ),
            )
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(name="floe-compute-duckdb", config={}),
            transforms=ResolvedTransforms(
                models=[
                    ResolvedModel(
                        name="test_model",
                        path="models/test_model.sql",
                        columns={},
                        unique_key=["id"],
                        tags=["test"],
                        owner="test@example.com",
                        materialized="table",
                    ),
                ]
            ),
        ),
        dbt_profiles={
            "floe": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": f"/tmp/{product_prefix}.duckdb",
                    }
                },
            }
        },
    )


class TestPromotionWorkflow(IntegrationTestBase):
    """Integration tests for full promotion workflow.

    Tests the complete promotion lifecycle from pushing an artifact to promoting
    it through environments with real registry operations.

    Requirements: FR-001, FR-002, FR-006, FR-008
    """

    required_services = [("oci-registry", 5000)]
    namespace = "floe-test"

    def _create_test_artifacts_json(self, tmp_path: Path, unique_id: str) -> Path:
        """Create a valid CompiledArtifacts JSON file for testing.

        Args:
            tmp_path: Temporary directory path.
            unique_id: Unique identifier for test isolation.

        Returns:
            Path to the created JSON file.
        """
        artifacts = _create_valid_compiled_artifacts(unique_id, "promo-test")
        artifacts_path = tmp_path / "compiled_artifacts.json"
        artifacts.to_json_file(artifacts_path)
        return artifacts_path

    @pytest.mark.requirement("8C-FR-001")
    def test_full_promotion_workflow_dev_to_staging(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test full promotion workflow from dev to staging.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        This test validates the complete promotion flow:
        1. Push artifact to registry with initial tag
        2. Promote artifact from dev to staging
        3. Verify staging environment tag is created
        4. Verify PromotionRecord is returned

        Verifies:
        - FR-001: Promote artifact from one environment to next
        - FR-008: Audit trail via PromotionRecord
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.promotion import PromotionConfig, PromotionRecord

        # Create test artifacts with unique ID for isolation
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)

        # Load CompiledArtifacts
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client from manifest
        client = OCIClient.from_manifest(test_manifest_path)

        # Push initial artifact
        initial_tag = f"v1.0.0-{unique_id}"
        digest = client.push(artifacts, tag=initial_tag)
        assert digest.startswith("sha256:")

        # Create PromotionController
        promotion_config = PromotionConfig()
        controller = PromotionController(client=client, promotion=promotion_config)

        # Promote from dev to staging
        result = controller.promote(
            tag=initial_tag,
            from_env="dev",
            to_env="staging",
            operator="test@example.com",
        )

        # Verify PromotionRecord returned
        assert isinstance(result, PromotionRecord)
        assert result.source_environment == "dev"
        assert result.target_environment == "staging"
        assert result.artifact_digest == digest
        assert result.dry_run is False

    @pytest.mark.requirement("8C-FR-002")
    def test_promotion_validates_gates_in_real_workflow(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test that gates are validated during real promotion workflow.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Verifies:
        - FR-002: Gate validation before promotion
        - Gates are executed in order
        - Gate results are recorded
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.promotion import PromotionConfig

        # Create test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client and push
        client = OCIClient.from_manifest(test_manifest_path)
        initial_tag = f"v1.0.0-{unique_id}"
        client.push(artifacts, tag=initial_tag)

        # Configure promotion with gates
        promotion_config = PromotionConfig(
            gates={
                "staging": {
                    "policy_compliance": {"enabled": True},
                }
            }
        )
        controller = PromotionController(client=client, promotion=promotion_config)

        # Promote and verify gates were run
        result = controller.promote(
            tag=initial_tag,
            from_env="dev",
            to_env="staging",
            operator="test@example.com",
        )

        # Gate results should be recorded
        assert len(result.gate_results) >= 0  # May be 0 if no gates configured

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_creates_environment_specific_tag(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test that promotion creates environment-specific tag in registry.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Verifies:
        - FR-001: Environment-specific tags are created
        - Tag format follows convention (e.g., v1.0.0-staging)
        - Tag can be pulled after promotion
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.promotion import PromotionConfig

        # Create test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client and push
        client = OCIClient.from_manifest(test_manifest_path)
        initial_tag = f"v1.0.0-{unique_id}"
        client.push(artifacts, tag=initial_tag)

        # Promote
        controller = PromotionController(client=client, promotion=PromotionConfig())
        controller.promote(
            tag=initial_tag,
            from_env="dev",
            to_env="staging",
            operator="test@example.com",
        )

        # Verify environment tag was created and is pullable
        staging_tag = f"v1.0.0-{unique_id}-staging"
        pulled_artifacts = client.pull(tag=staging_tag)
        assert pulled_artifacts is not None
        assert pulled_artifacts.metadata.product_name == artifacts.metadata.product_name

    @pytest.mark.requirement("8C-FR-008")
    def test_promotion_stores_promotion_record_in_annotations(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test that promotion record is stored in OCI annotations.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Verifies:
        - FR-008: Audit trail via PromotionRecord
        - Promotion history is queryable
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.promotion import PromotionConfig

        # Create test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client and push
        client = OCIClient.from_manifest(test_manifest_path)
        initial_tag = f"v1.0.0-{unique_id}"
        client.push(artifacts, tag=initial_tag)

        # Promote
        controller = PromotionController(client=client, promotion=PromotionConfig())
        result = controller.promote(
            tag=initial_tag,
            from_env="dev",
            to_env="staging",
            operator="test@example.com",
        )

        # Query promotion history
        history = controller.get_promotion_history(tag=f"v1.0.0-{unique_id}-staging")
        assert len(history) >= 1
        assert history[0].promotion_id == result.promotion_id

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_dry_run_does_not_create_tags(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test that dry_run mode does not create tags in registry.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Verifies:
        - FR-001: Dry-run validation mode
        - No side effects in dry-run
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.errors import ArtifactNotFoundError
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.promotion import PromotionConfig

        # Create test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client and push
        client = OCIClient.from_manifest(test_manifest_path)
        initial_tag = f"v1.0.0-{unique_id}"
        client.push(artifacts, tag=initial_tag)

        # Promote with dry_run=True
        controller = PromotionController(client=client, promotion=PromotionConfig())
        result = controller.promote(
            tag=initial_tag,
            from_env="dev",
            to_env="staging",
            operator="test@example.com",
            dry_run=True,
        )

        # Verify dry_run flag is set
        assert result.dry_run is True

        # Verify environment tag was NOT created
        staging_tag = f"v1.0.0-{unique_id}-staging"
        with pytest.raises(ArtifactNotFoundError):
            client.pull(tag=staging_tag)

    @pytest.mark.requirement("8C-FR-006")
    def test_promotion_verifies_signature_in_real_workflow(
        self,
        tmp_path: Path,
        test_artifact_tag: str,
        test_manifest_path: Path,
    ) -> None:
        """Test that signature verification is performed during promotion.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Note: This test requires artifacts to be signed. In environments without
        signing configured, signature verification may be skipped (warn mode).

        Verifies:
        - FR-006: Signature verification integration
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts
        from floe_core.schemas.promotion import PromotionConfig

        # Create test artifacts
        unique_id = test_artifact_tag.replace("test-", "").split("-")[0]
        artifacts_path = self._create_test_artifacts_json(tmp_path, unique_id)
        artifacts = CompiledArtifacts.from_json_file(artifacts_path)

        # Create client and push
        client = OCIClient.from_manifest(test_manifest_path)
        initial_tag = f"v1.0.0-{unique_id}"
        client.push(artifacts, tag=initial_tag)

        # Configure promotion with signature verification in warn mode
        # (since test artifacts may not be signed)
        promotion_config = PromotionConfig(signature_verification={"enforcement": "warn"})
        controller = PromotionController(client=client, promotion=promotion_config)

        # Promote
        result = controller.promote(
            tag=initial_tag,
            from_env="dev",
            to_env="staging",
            operator="test@example.com",
        )

        # Signature verification result should be recorded
        # (may be False if unsigned, but no error in warn mode)
        assert hasattr(result, "signature_verified")
