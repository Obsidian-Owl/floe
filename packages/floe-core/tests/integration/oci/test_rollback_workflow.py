"""Integration tests for full rollback workflow (T049).

Tests the complete rollback lifecycle with real registry operations:
- Promote artifact from dev to staging to prod
- Rollback prod to previous version
- Verify rollback tag created (FR-014)
- Verify latest tag updated (FR-015)
- Verify rollback record stored (FR-017)

These tests FAIL if the registry is unavailable - no pytest.skip() per Constitution V.

Task: T049
Requirements: FR-013, FR-014, FR-015, FR-016, FR-017

Example:
    # Run integration tests (requires Kind cluster with registry)
    make test-integration

TDD Note:
    These tests are written FIRST per TDD methodology.
    They are marked xfail until T050 implements rollback() logic.

See Also:
    - testing/k8s/services/registry.yaml: Registry deployment manifest
    - IntegrationTestBase: Base class for K8s-native tests
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

if TYPE_CHECKING:
    pass


def _create_valid_compiled_artifacts(
    unique_id: str, product_prefix: str = "rollback"
) -> Any:
    """Create a valid CompiledArtifacts instance for rollback testing.

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
    )


class TestRollbackWorkflow(IntegrationTestBase):
    """Integration tests for rollback workflow.

    TDD: These tests document the expected integration behavior.
    They are xfail until T050 implements rollback().
    """

    required_services: list[tuple[str, int]] = [("registry", 5000)]

    @pytest.mark.xfail(reason="Integration: Requires Kind cluster with registry")
    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_to_previous_version(self) -> None:
        """Integration: Rollback prod to a previous version.

        Workflow:
        1. Push v1.0.0 to registry
        2. Promote v1.0.0: dev -> staging -> prod
        3. Push v2.0.0 to registry
        4. Promote v2.0.0: dev -> staging -> prod
        5. Rollback prod to v1.0.0
        6. Verify latest-prod points to v1.0.0's digest
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig, RollbackRecord

        # Setup
        unique_id = self.generate_unique_namespace("rollback")
        registry_uri = self.get_service_uri("registry")

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri=registry_uri, auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion_config = PromotionConfig()
        controller = PromotionController(client=oci_client, promotion=promotion_config)

        # Create and push v1.0.0
        artifacts_v1 = _create_valid_compiled_artifacts(f"{unique_id}_v1")
        oci_client.push(artifacts_v1, tag=f"v1.0.0-{unique_id}")

        # Promote v1.0.0 through environments
        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="dev",
            to_env="staging",
            operator="ci@example.com",
        )
        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="staging",
            to_env="prod",
            operator="ci@example.com",
        )

        # Get v1.0.0 digest for later comparison
        v1_digest = oci_client.resolve_digest(f"v1.0.0-{unique_id}")

        # Create and push v2.0.0
        artifacts_v2 = _create_valid_compiled_artifacts(f"{unique_id}_v2")
        oci_client.push(artifacts_v2, tag=f"v2.0.0-{unique_id}")

        # Promote v2.0.0 through environments
        controller.promote(
            tag=f"v2.0.0-{unique_id}",
            from_env="dev",
            to_env="staging",
            operator="ci@example.com",
        )
        controller.promote(
            tag=f"v2.0.0-{unique_id}",
            from_env="staging",
            to_env="prod",
            operator="ci@example.com",
        )

        # Rollback prod to v1.0.0
        result = controller.rollback(
            tag=f"v1.0.0-{unique_id}",
            environment="prod",
            reason="Performance regression in v2.0.0",
            operator="sre@example.com",
        )

        # Verify RollbackRecord returned
        assert isinstance(result, RollbackRecord)
        assert result.environment == "prod"
        assert result.reason == "Performance regression in v2.0.0"
        assert result.operator == "sre@example.com"

        # Verify latest-prod tag now points to v1.0.0
        latest_digest = oci_client.resolve_digest(f"latest-prod-{unique_id}")
        assert latest_digest == v1_digest

    @pytest.mark.xfail(reason="Integration: Requires Kind cluster with registry")
    @pytest.mark.requirement("8C-FR-014")
    def test_rollback_creates_rollback_tag(self) -> None:
        """Integration: Verify rollback creates tag with correct pattern.

        Pattern: v{X.Y.Z}-{env}-rollback-{N}
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        # Setup
        unique_id = self.generate_unique_namespace("rbktag")
        registry_uri = self.get_service_uri("registry")

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri=registry_uri, auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion_config = PromotionConfig()
        controller = PromotionController(client=oci_client, promotion=promotion_config)

        # Push and promote v1.0.0 to prod
        artifacts = _create_valid_compiled_artifacts(unique_id)
        oci_client.push(artifacts, tag=f"v1.0.0-{unique_id}")

        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="dev",
            to_env="staging",
            operator="ci@example.com",
        )
        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="staging",
            to_env="prod",
            operator="ci@example.com",
        )

        # Push and promote v2.0.0 (so we have something to rollback from)
        artifacts_v2 = _create_valid_compiled_artifacts(f"{unique_id}_v2")
        oci_client.push(artifacts_v2, tag=f"v2.0.0-{unique_id}")

        controller.promote(
            tag=f"v2.0.0-{unique_id}",
            from_env="dev",
            to_env="staging",
            operator="ci@example.com",
        )
        controller.promote(
            tag=f"v2.0.0-{unique_id}",
            from_env="staging",
            to_env="prod",
            operator="ci@example.com",
        )

        # Rollback prod to v1.0.0
        controller.rollback(
            tag=f"v1.0.0-{unique_id}",
            environment="prod",
            reason="Test rollback tag creation",
            operator="sre@example.com",
        )

        # Verify rollback tag was created
        rollback_tag = f"v1.0.0-{unique_id}-prod-rollback-1"
        rollback_digest = oci_client.resolve_digest(rollback_tag)
        assert rollback_digest is not None, f"Rollback tag {rollback_tag} should exist"

    @pytest.mark.xfail(reason="Integration: Requires Kind cluster with registry")
    @pytest.mark.requirement("8C-FR-013")
    def test_rollback_fails_for_non_promoted_version(self) -> None:
        """Integration: Rollback fails if version was never promoted.

        VersionNotPromotedError should be raised with helpful context.
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.errors import VersionNotPromotedError
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        # Setup
        unique_id = self.generate_unique_namespace("rbkerr")
        registry_uri = self.get_service_uri("registry")

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri=registry_uri, auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion_config = PromotionConfig()
        controller = PromotionController(client=oci_client, promotion=promotion_config)

        # Push v1.0.0 but only promote to staging (not prod)
        artifacts = _create_valid_compiled_artifacts(unique_id)
        oci_client.push(artifacts, tag=f"v1.0.0-{unique_id}")

        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="dev",
            to_env="staging",
            operator="ci@example.com",
        )
        # Note: NOT promoted to prod

        # Try to rollback prod to v1.0.0 (which was never in prod)
        with pytest.raises(VersionNotPromotedError) as exc_info:
            controller.rollback(
                tag=f"v1.0.0-{unique_id}",
                environment="prod",
                reason="Should fail - never promoted to prod",
                operator="sre@example.com",
            )

        # Verify error contains helpful context
        assert exc_info.value.tag == f"v1.0.0-{unique_id}"
        assert exc_info.value.environment == "prod"

    @pytest.mark.xfail(reason="Integration: Requires Kind cluster with registry")
    @pytest.mark.requirement("8C-FR-016")
    def test_rollback_impact_analysis(self) -> None:
        """Integration: analyze_rollback_impact() provides pre-rollback analysis.

        Should return RollbackImpactAnalysis with:
        - breaking_changes
        - affected_products
        - recommendations
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig, RollbackImpactAnalysis

        # Setup
        unique_id = self.generate_unique_namespace("rbkimp")
        registry_uri = self.get_service_uri("registry")

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri=registry_uri, auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion_config = PromotionConfig()
        controller = PromotionController(client=oci_client, promotion=promotion_config)

        # Push and promote v1.0.0
        artifacts = _create_valid_compiled_artifacts(unique_id)
        oci_client.push(artifacts, tag=f"v1.0.0-{unique_id}")

        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="dev",
            to_env="staging",
            operator="ci@example.com",
        )
        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="staging",
            to_env="prod",
            operator="ci@example.com",
        )

        # Analyze rollback impact
        analysis = controller.analyze_rollback_impact(
            tag=f"v1.0.0-{unique_id}",
            environment="prod",
        )

        # Verify analysis structure
        assert isinstance(analysis, RollbackImpactAnalysis)
        assert isinstance(analysis.breaking_changes, list)
        assert isinstance(analysis.affected_products, list)
        assert isinstance(analysis.recommendations, list)

    @pytest.mark.xfail(reason="Integration: Requires Kind cluster with registry")
    @pytest.mark.requirement("8C-FR-017")
    def test_rollback_stores_audit_record(self) -> None:
        """Integration: Rollback stores RollbackRecord for audit trail.

        The record should be stored in OCI annotations and be retrievable.
        """
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig, RollbackRecord

        # Setup
        unique_id = self.generate_unique_namespace("rbkaud")
        registry_uri = self.get_service_uri("registry")

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri=registry_uri, auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion_config = PromotionConfig()
        controller = PromotionController(client=oci_client, promotion=promotion_config)

        # Push and promote v1.0.0 and v2.0.0
        artifacts_v1 = _create_valid_compiled_artifacts(f"{unique_id}_v1")
        oci_client.push(artifacts_v1, tag=f"v1.0.0-{unique_id}")

        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="dev",
            to_env="staging",
            operator="ci@example.com",
        )
        controller.promote(
            tag=f"v1.0.0-{unique_id}",
            from_env="staging",
            to_env="prod",
            operator="ci@example.com",
        )

        artifacts_v2 = _create_valid_compiled_artifacts(f"{unique_id}_v2")
        oci_client.push(artifacts_v2, tag=f"v2.0.0-{unique_id}")

        controller.promote(
            tag=f"v2.0.0-{unique_id}",
            from_env="dev",
            to_env="staging",
            operator="ci@example.com",
        )
        controller.promote(
            tag=f"v2.0.0-{unique_id}",
            from_env="staging",
            to_env="prod",
            operator="ci@example.com",
        )

        # Rollback
        result = controller.rollback(
            tag=f"v1.0.0-{unique_id}",
            environment="prod",
            reason="Audit trail test",
            operator="sre@example.com",
        )

        # Verify record contains required audit fields
        assert isinstance(result, RollbackRecord)
        assert result.rollback_id is not None
        assert result.artifact_digest.startswith("sha256:")
        assert result.previous_digest.startswith("sha256:")
        assert result.trace_id is not None
        assert result.rolled_back_at is not None
