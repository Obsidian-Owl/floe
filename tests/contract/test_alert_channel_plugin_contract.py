"""Contract test for AlertChannelPlugin ABC compliance.

This module tests the AlertChannelPlugin abstract base class contract:
- AlertChannelPlugin is a subclass of PluginMetadata
- AlertChannelPlugin cannot be instantiated directly (abstract)
- Required abstract methods: send_alert, validate_config
- Inherited abstract properties: name, version, floe_api_version
- Concrete implementations must implement all abstract members
- PluginType.ALERT_CHANNEL exists with correct entry point group

Tasks: T018 (Epic 3D)
Requirements: FR-021, FR-022, Constitution II
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from floe_core.contracts.monitoring.violations import (
    ContractViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata
from floe_core.plugin_types import PluginType
from floe_core.plugins.alert_channel import AlertChannelPlugin


class StubAlertChannel(AlertChannelPlugin):
    """Concrete AlertChannelPlugin implementation for testing.

    This stub implements all abstract methods with minimal functionality
    to verify that a complete implementation can be instantiated.
    """

    @property
    def name(self) -> str:
        """Return plugin name."""
        return "stub-channel"

    @property
    def version(self) -> str:
        """Return plugin version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Return required floe API version."""
        return "1.0"

    async def send_alert(
        self,
        event: ContractViolationEvent,
    ) -> bool:
        """Send alert via stub channel (always succeeds)."""
        return True

    def validate_config(self) -> list[str]:
        """Validate configuration (always valid)."""
        return []


class IncompleteAlertChannel_NoSendAlert(AlertChannelPlugin):
    """Incomplete implementation missing send_alert method."""

    @property
    def name(self) -> str:
        return "incomplete-no-send"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def validate_config(self) -> list[str]:
        """Validate configuration."""
        return []


class IncompleteAlertChannel_NoValidateConfig(AlertChannelPlugin):
    """Incomplete implementation missing validate_config method."""

    @property
    def name(self) -> str:
        return "incomplete-no-validate"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    async def send_alert(
        self,
        event: ContractViolationEvent,
    ) -> bool:
        """Send alert."""
        return True


@pytest.mark.requirement("3D-FR-021")
def test_alert_channel_plugin_is_subclass_of_plugin_metadata() -> None:
    """Test that AlertChannelPlugin inherits from PluginMetadata.

    Validates that AlertChannelPlugin is a proper subclass of PluginMetadata,
    ensuring inheritance of lifecycle methods and metadata properties.
    """
    assert issubclass(AlertChannelPlugin, PluginMetadata)


@pytest.mark.requirement("3D-FR-021")
def test_alert_channel_plugin_cannot_be_instantiated_directly() -> None:
    """Test that AlertChannelPlugin is abstract and cannot be instantiated.

    Attempting to instantiate AlertChannelPlugin directly should raise TypeError
    because it has abstract methods (send_alert, validate_config).
    """
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        AlertChannelPlugin()  # type: ignore[abstract]


@pytest.mark.requirement("3D-FR-021")
def test_concrete_implementation_can_be_instantiated() -> None:
    """Test that a complete concrete implementation can be instantiated.

    StubAlertChannel implements all abstract methods, so it should instantiate
    successfully and provide all required properties.
    """
    channel = StubAlertChannel()

    assert channel.name == "stub-channel"
    assert channel.version == "1.0.0"
    assert channel.floe_api_version == "1.0"


@pytest.mark.requirement("3D-FR-022")
def test_send_alert_method_contract() -> None:
    """Test send_alert method signature and behavior.

    Validates that send_alert:
    - Is async (returns coroutine)
    - Accepts ContractViolationEvent
    - Returns bool (True for success, False for failure)

    Note: Uses asyncio.run to execute the async method in a synchronous test.
    """
    import asyncio

    channel = StubAlertChannel()
    event = ContractViolationEvent(
        contract_name="test_contract",
        contract_version="1.0.0",
        violation_type=ViolationType.FRESHNESS,
        severity=ViolationSeverity.ERROR,
        message="Test violation",
        timestamp=datetime.now(tz=timezone.utc),
        check_duration_seconds=0.5,
    )

    result = asyncio.run(channel.send_alert(event))

    assert isinstance(result, bool)
    assert result is True


@pytest.mark.requirement("3D-FR-021")
def test_validate_config_method_contract() -> None:
    """Test validate_config method signature and behavior.

    Validates that validate_config:
    - Returns list of strings (validation errors)
    - Empty list means valid configuration
    """
    channel = StubAlertChannel()

    errors = channel.validate_config()

    assert isinstance(errors, list)
    assert all(isinstance(error, str) for error in errors)
    assert len(errors) == 0


@pytest.mark.requirement("3D-FR-021")
def test_inherited_health_check_method_works() -> None:
    """Test that inherited health_check method works.

    AlertChannelPlugin inherits health_check from PluginMetadata.
    The default implementation returns HEALTHY.
    """
    channel = StubAlertChannel()

    health = channel.health_check()

    assert isinstance(health, HealthStatus)
    assert health.state == HealthState.HEALTHY


@pytest.mark.requirement("3D-FR-021")
def test_inherited_startup_shutdown_methods_work() -> None:
    """Test that inherited lifecycle methods work.

    AlertChannelPlugin inherits startup() and shutdown() from PluginMetadata.
    The default implementations are no-ops that should not raise.
    """
    channel = StubAlertChannel()

    channel.startup()
    channel.shutdown()


@pytest.mark.requirement("3D-FR-021")
def test_incomplete_implementation_no_send_alert_cannot_instantiate() -> None:
    """Test that missing send_alert prevents instantiation.

    A class extending AlertChannelPlugin that doesn't implement send_alert
    should raise TypeError on instantiation.
    """
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteAlertChannel_NoSendAlert()  # type: ignore[abstract]


@pytest.mark.requirement("3D-FR-021")
def test_incomplete_implementation_no_validate_config_cannot_instantiate() -> None:
    """Test that missing validate_config prevents instantiation.

    A class extending AlertChannelPlugin that doesn't implement validate_config
    should raise TypeError on instantiation.
    """
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteAlertChannel_NoValidateConfig()  # type: ignore[abstract]


@pytest.mark.requirement("3D-FR-022")
def test_plugin_type_alert_channel_exists() -> None:
    """Test that PluginType.ALERT_CHANNEL enum member exists.

    Validates that the ALERT_CHANNEL plugin type is defined in PluginType enum.
    """
    assert hasattr(PluginType, "ALERT_CHANNEL")


@pytest.mark.requirement("3D-FR-022")
def test_plugin_type_alert_channel_entry_point_group() -> None:
    """Test that PluginType.ALERT_CHANNEL has correct entry point group.

    The entry point group for alert channels must be 'floe.alert_channels'.
    """
    assert PluginType.ALERT_CHANNEL.entry_point_group == "floe.alert_channels"


@pytest.mark.requirement("3D-FR-022")
def test_plugin_type_alert_channel_value() -> None:
    """Test that PluginType.ALERT_CHANNEL has correct value.

    The enum value must match the entry point group name.
    """
    assert PluginType.ALERT_CHANNEL.value == "floe.alert_channels"
