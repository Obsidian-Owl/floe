"""Integration tests for environment lock/unlock workflow (T101).

Tests the complete lock/unlock lifecycle with real registry operations:
- Lock environment to prevent promotions
- Verify promotion rejected on locked environment
- Unlock environment
- Verify promotion succeeds after unlock

These tests FAIL if the registry is unavailable - no pytest.skip() per Constitution V.

Task: T101
Requirements: FR-035, FR-036, FR-037

Example:
    # Run integration tests (requires Kind cluster with registry)
    make test-integration

See Also:
    - testing/k8s/services/registry.yaml: Registry deployment manifest
    - IntegrationTestBase: Base class for K8s-native tests
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pytest
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_core.oci.errors import EnvironmentLockedError
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

if TYPE_CHECKING:
    pass


def _create_valid_compiled_artifacts(unique_id: str, product_prefix: str = "lock") -> Any:
    """Create a valid CompiledArtifacts instance for lock testing.

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
                ),
            ),
        ),
        transforms=ResolvedTransforms(
            plugins=ResolvedPlugins(
                transforms=[
                    PluginRef(
                        name="floe-transform-passthrough",
                        version="1.0.0",
                    ),
                ],
            ),
            model=ResolvedModel(
                models=[],
            ),
        ),
    )


class TestLockUnlockWorkflow(IntegrationTestBase):
    """Integration tests for lock/unlock workflow (FR-035, FR-036, FR-037).

    Tests the complete lifecycle:
    1. Lock environment
    2. Verify promotion rejected
    3. Unlock environment
    4. Verify promotion succeeds
    """

    required_services = [("registry", 5000)]

    @pytest.mark.requirement("FR-035")
    @pytest.mark.requirement("FR-036")
    @pytest.mark.requirement("FR-037")
    @pytest.mark.integration
    def test_lock_reject_unlock_promote_workflow(self) -> None:
        """Test full cycle: lock → reject promotion → unlock → promotion succeeds."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        # Check infrastructure
        self.check_infrastructure("registry", 5000)
        unique_id = self.generate_unique_namespace("locktest")

        # Setup registry and client
        registry_url = f"localhost:5000/floe-lock-{unique_id}"
        registry_config = RegistryConfig(
            registry_uri=f"oci://{registry_url}",
            auth=RegistryAuth(auth_type=AuthType.NONE),
        )
        client = OCIClient.from_registry_config(registry_config)

        # Setup promotion controller with test environments
        promotion_config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
                EnvironmentConfig(
                    name="staging",
                    gates={
                        PromotionGate.POLICY_COMPLIANCE: True,
                        PromotionGate.TESTS: True,
                    },
                ),
                EnvironmentConfig(
                    name="prod",
                    gates={
                        PromotionGate.POLICY_COMPLIANCE: True,
                        PromotionGate.TESTS: True,
                    },
                ),
            ],
        )
        controller = PromotionController(
            client=client,
            promotion=promotion_config,
        )

        # Create and push test artifact
        artifacts = _create_valid_compiled_artifacts(unique_id)
        tag = f"v1.0.0-{unique_id}"
        client.push_artifact(
            tag=tag,
            compiled_artifacts=artifacts,
            sign=False,
        )

        # Promote to dev first
        controller.promote(
            tag=tag,
            source_environment=None,  # Initial push
            target_environment="dev",
            operator="test@example.com",
        )

        # --- STEP 1: Lock staging environment ---
        controller.lock_environment(
            environment="staging",
            reason="Integration test - locking staging",
            operator="sre@example.com",
        )

        # Verify lock status
        lock_status = controller.get_lock_status("staging")
        assert lock_status.locked is True
        assert lock_status.reason == "Integration test - locking staging"
        assert lock_status.locked_by == "sre@example.com"

        # --- STEP 2: Verify promotion rejected ---
        with pytest.raises(EnvironmentLockedError) as exc_info:
            controller.promote(
                tag=tag,
                source_environment="dev",
                target_environment="staging",
                operator="release@example.com",
            )

        assert exc_info.value.environment == "staging"
        assert exc_info.value.exit_code == 13

        # --- STEP 3: Unlock environment ---
        controller.unlock_environment(
            environment="staging",
            reason="Integration test - unlocking staging",
            operator="sre@example.com",
        )

        # Verify unlock
        lock_status = controller.get_lock_status("staging")
        assert lock_status.locked is False

        # --- STEP 4: Verify promotion succeeds ---
        promotion_record = controller.promote(
            tag=tag,
            source_environment="dev",
            target_environment="staging",
            operator="release@example.com",
        )

        assert promotion_record is not None
        assert promotion_record.target_environment == "staging"

    @pytest.mark.requirement("FR-035")
    @pytest.mark.integration
    def test_lock_persists_across_controller_instances(self) -> None:
        """Lock persists when new PromotionController instance is created."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        # Check infrastructure
        self.check_infrastructure("registry", 5000)
        unique_id = self.generate_unique_namespace("lockpersist")

        # Setup registry and client
        registry_url = f"localhost:5000/floe-persist-{unique_id}"
        registry_config = RegistryConfig(
            registry_uri=f"oci://{registry_url}",
            auth=RegistryAuth(auth_type=AuthType.NONE),
        )
        client = OCIClient.from_registry_config(registry_config)

        # Setup promotion config
        promotion_config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
                EnvironmentConfig(
                    name="prod",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
            ],
        )

        # Controller 1: Lock environment
        controller1 = PromotionController(
            client=client,
            promotion=promotion_config,
        )
        controller1.lock_environment(
            environment="prod",
            reason="Incident #123",
            operator="oncall@example.com",
        )

        # Controller 2: New instance should see the lock
        controller2 = PromotionController(
            client=client,
            promotion=promotion_config,
        )
        lock_status = controller2.get_lock_status("prod")

        assert lock_status.locked is True
        assert lock_status.reason == "Incident #123"
        assert lock_status.locked_by == "oncall@example.com"

    @pytest.mark.requirement("FR-037")
    @pytest.mark.integration
    def test_unlock_idempotent(self) -> None:
        """Unlocking an already unlocked environment is a no-op."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        # Check infrastructure
        self.check_infrastructure("registry", 5000)
        unique_id = self.generate_unique_namespace("unlockidem")

        # Setup
        registry_url = f"localhost:5000/floe-idem-{unique_id}"
        registry_config = RegistryConfig(
            registry_uri=f"oci://{registry_url}",
            auth=RegistryAuth(auth_type=AuthType.NONE),
        )
        client = OCIClient.from_registry_config(registry_config)

        promotion_config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
            ],
        )
        controller = PromotionController(
            client=client,
            promotion=promotion_config,
        )

        # Environment starts unlocked
        lock_status = controller.get_lock_status("dev")
        assert lock_status.locked is False

        # Unlock should not raise (idempotent)
        controller.unlock_environment(
            environment="dev",
            reason="Test unlock on unlocked env",
            operator="test@example.com",
        )

        # Still unlocked
        lock_status = controller.get_lock_status("dev")
        assert lock_status.locked is False


class TestLockErrorHandling(IntegrationTestBase):
    """Integration tests for lock error handling."""

    required_services = [("registry", 5000)]

    @pytest.mark.requirement("FR-036")
    @pytest.mark.integration
    def test_environment_locked_error_details(self) -> None:
        """EnvironmentLockedError includes all lock details."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        # Check infrastructure
        self.check_infrastructure("registry", 5000)
        unique_id = self.generate_unique_namespace("lockerr")

        # Setup
        registry_url = f"localhost:5000/floe-err-{unique_id}"
        registry_config = RegistryConfig(
            registry_uri=f"oci://{registry_url}",
            auth=RegistryAuth(auth_type=AuthType.NONE),
        )
        client = OCIClient.from_registry_config(registry_config)

        promotion_config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
                EnvironmentConfig(
                    name="staging",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
            ],
        )
        controller = PromotionController(
            client=client,
            promotion=promotion_config,
        )

        # Create and push test artifact
        artifacts = _create_valid_compiled_artifacts(unique_id)
        tag = f"v1.0.0-{unique_id}"
        client.push_artifact(
            tag=tag,
            compiled_artifacts=artifacts,
            sign=False,
        )

        # Promote to dev
        controller.promote(
            tag=tag,
            source_environment=None,
            target_environment="dev",
            operator="ci@example.com",
        )

        # Lock staging with specific details
        lock_reason = "Maintenance window - DB upgrade"
        lock_operator = "dba@example.com"
        controller.lock_environment(
            environment="staging",
            reason=lock_reason,
            operator=lock_operator,
        )

        # Attempt promotion and verify error details
        with pytest.raises(EnvironmentLockedError) as exc_info:
            controller.promote(
                tag=tag,
                source_environment="dev",
                target_environment="staging",
                operator="release@example.com",
            )

        error = exc_info.value
        assert error.environment == "staging"
        assert error.locked_by == lock_operator
        assert lock_reason in error.reason
        assert error.exit_code == 13


__all__: list[str] = [
    "TestLockUnlockWorkflow",
    "TestLockErrorHandling",
]
