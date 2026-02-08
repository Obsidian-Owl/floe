"""Unit tests for PromotionController class.

Tests Epic 8C promotion controller skeleton and basic operations.

Requirements tested:
    FR-001: Promote artifact from one environment to next
    FR-002: Gate validation before promotion
    FR-010: Policy compliance gate integration
"""

from __future__ import annotations

import pytest


class TestPromotionControllerInit:
    """Tests for PromotionController initialization."""

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_controller_init_with_oci_client(self) -> None:
        """Test PromotionController can be initialized with OCIClient (T014)."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()  # Default environments [dev, staging, prod]

        controller = PromotionController(client=oci_client, promotion=promotion)

        assert controller.client == oci_client
        assert controller.promotion == promotion

    @pytest.mark.requirement("8C-FR-010")
    def test_promotion_controller_init_with_policy_enforcer(self) -> None:
        """Test PromotionController can be initialized with PolicyEnforcer (T014)."""
        from floe_core.enforcement import PolicyEnforcer
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.manifest import GovernanceConfig
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()
        governance = GovernanceConfig()
        policy_enforcer = PolicyEnforcer(governance_config=governance)

        controller = PromotionController(
            client=oci_client,
            promotion=promotion,
            policy_enforcer=policy_enforcer,
        )

        assert controller.client == oci_client
        assert controller.promotion == promotion
        assert controller.policy_enforcer == policy_enforcer

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_controller_init_without_policy_enforcer(self) -> None:
        """Test PromotionController works without PolicyEnforcer (optional)."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        controller = PromotionController(client=oci_client, promotion=promotion)

        assert controller.client == oci_client
        assert controller.promotion == promotion
        assert controller.policy_enforcer is None

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_controller_init_from_registry_config(self) -> None:
        """Test PromotionController can be initialized from RegistryConfig (deprecated)."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        promotion = PromotionConfig()  # Default environments [dev, staging, prod]

        # Legacy initialization via registry= parameter should still work
        controller = PromotionController(registry=registry, promotion=promotion)

        # Controller should have created an internal OCIClient
        assert controller.client is not None
        assert controller.promotion == promotion

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_controller_default_environments(self) -> None:
        """Test PromotionController has default [dev, staging, prod] environments."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        promotion = PromotionConfig()

        controller = PromotionController(registry=registry, promotion=promotion)

        env_names = [e.name for e in controller.promotion.environments]
        assert env_names == ["dev", "staging", "prod"]

    @pytest.mark.requirement("8C-FR-001")
    def test_promotion_controller_custom_environments(self) -> None:
        """Test PromotionController can use custom environment configurations."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)

        custom_envs = [
            EnvironmentConfig(name="test", gates={PromotionGate.POLICY_COMPLIANCE: True}),
            EnvironmentConfig(name="production", gates={PromotionGate.POLICY_COMPLIANCE: True}),
        ]
        promotion = PromotionConfig(environments=custom_envs)

        controller = PromotionController(registry=registry, promotion=promotion)

        env_names = [e.name for e in controller.promotion.environments]
        assert env_names == ["test", "production"]


class TestPromotionControllerMethods:
    """Tests for PromotionController method signatures."""

    @pytest.mark.requirement("8C-FR-001")
    def test_promote_method_exists(self) -> None:
        """Test PromotionController has promote method."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        assert hasattr(controller, "promote")
        assert callable(controller.promote)

    @pytest.mark.requirement("8C-FR-001")
    def test_rollback_method_exists(self) -> None:
        """Test PromotionController has rollback method."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        assert hasattr(controller, "rollback")
        assert callable(controller.rollback)

    @pytest.mark.requirement("8C-FR-001")
    def test_status_method_exists(self) -> None:
        """Test PromotionController has status method."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        assert hasattr(controller, "status")
        assert callable(controller.status)

    @pytest.mark.requirement("8C-FR-001")
    def test_dry_run_method_exists(self) -> None:
        """Test PromotionController has dry_run method."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        assert hasattr(controller, "dry_run")
        assert callable(controller.dry_run)

    @pytest.mark.requirement("8C-FR-035")
    def test_lock_environment_method_exists(self) -> None:
        """Test PromotionController has lock_environment method."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        assert hasattr(controller, "lock_environment")
        assert callable(controller.lock_environment)

    @pytest.mark.requirement("8C-FR-037")
    def test_unlock_environment_method_exists(self) -> None:
        """Test PromotionController has unlock_environment method."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        assert hasattr(controller, "unlock_environment")
        assert callable(controller.unlock_environment)


class TestPromotionControllerEnvironmentValidation:
    """Tests for PromotionController environment validation."""

    @pytest.mark.requirement("8C-FR-001")
    def test_get_environment_returns_config(self) -> None:
        """Test _get_environment returns EnvironmentConfig for valid name."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        env_config = controller._get_environment("dev")
        assert env_config is not None
        assert env_config.name == "dev"

    @pytest.mark.requirement("8C-FR-001")
    def test_get_environment_returns_none_for_invalid(self) -> None:
        """Test _get_environment returns None for unknown environment."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        env_config = controller._get_environment("nonexistent")
        assert env_config is None

    @pytest.mark.requirement("8C-FR-001")
    def test_validate_transition_succeeds_for_valid_path(self) -> None:
        """Test _validate_transition succeeds for valid environment transition."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        # dev -> staging is valid (adjacent in [dev, staging, prod])
        controller._validate_transition("dev", "staging")  # Should not raise

    @pytest.mark.requirement("8C-FR-001")
    def test_validate_transition_raises_for_invalid_path(self) -> None:
        """Test _validate_transition raises InvalidTransitionError for invalid path."""
        from floe_core.oci.errors import InvalidTransitionError
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        # dev -> prod is invalid (skips staging in [dev, staging, prod])
        with pytest.raises(InvalidTransitionError) as excinfo:
            controller._validate_transition("dev", "prod")

        assert excinfo.value.from_env == "dev"
        assert excinfo.value.to_env == "prod"

    @pytest.mark.requirement("8C-FR-001")
    def test_validate_transition_raises_for_unknown_source(self) -> None:
        """Test _validate_transition raises for unknown source environment."""
        from floe_core.oci.errors import InvalidTransitionError
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        with pytest.raises(InvalidTransitionError) as excinfo:
            controller._validate_transition("unknown", "staging")

        assert "unknown" in excinfo.value.reason.lower()

    @pytest.mark.requirement("8C-FR-001")
    def test_validate_transition_raises_for_backward_promotion(self) -> None:
        """Test _validate_transition raises for backward promotion (prod -> dev)."""
        from floe_core.oci.errors import InvalidTransitionError
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        controller = PromotionController(registry=registry, promotion=PromotionConfig())

        # prod -> dev is backward (invalid direction)
        with pytest.raises(InvalidTransitionError) as excinfo:
            controller._validate_transition("prod", "dev")

        reason_lower = excinfo.value.reason.lower()
        assert "backward" in reason_lower or "direction" in reason_lower
