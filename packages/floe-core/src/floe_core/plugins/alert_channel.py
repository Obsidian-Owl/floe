"""AlertChannelPlugin ABC for pluggable alert delivery channels.

This module defines the abstract base class for alert channel plugins.
Alert channels are discovered via the ``floe.alert_channels`` entry point
group and receive ContractViolationEvents from the AlertRouter.

Entry point group: floe.alert_channels

Tasks: T012 (Epic 3D)
Requirements: FR-026, FR-027

Example:
    A concrete implementation (e.g., Slack channel)::

        class SlackAlertChannel(AlertChannelPlugin):
            @property
            def name(self) -> str:
                return "slack"

            @property
            def version(self) -> str:
                return "1.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            async def send_alert(self, event: ContractViolationEvent) -> bool:
                # POST to Slack webhook
                ...

            def validate_config(self) -> list[str]:
                # Check webhook URL is configured
                ...
"""

from __future__ import annotations

from abc import abstractmethod

from floe_core.contracts.monitoring.violations import ContractViolationEvent
from floe_core.plugin_metadata import PluginMetadata


class AlertChannelPlugin(PluginMetadata):
    """Abstract base class for alert delivery channel plugins.

    All alert channel implementations MUST inherit from this class and
    implement the abstract methods. Channels are discovered via the
    ``floe.alert_channels`` entry point group (FR-027).

    Inherits from PluginMetadata:
        - name, version, floe_api_version (abstract properties — MUST implement)
        - health_check(timeout) -> HealthStatus (default: HEALTHY — override for real checks)
        - startup() / shutdown() lifecycle hooks
        - get_config_schema() -> type[BaseModel] | None

    Alert delivery is fire-and-forget: failures are logged but not retried.
    The AlertRouter handles deduplication and rate limiting before dispatching
    to channels.

    Abstract Methods:
        send_alert: Deliver a violation alert via this channel.
        validate_config: Validate channel-specific configuration.
    """

    @abstractmethod
    async def send_alert(
        self,
        event: ContractViolationEvent,
    ) -> bool:
        """Send an alert for a contract violation.

        Implementations should format the violation event appropriately
        for their delivery mechanism (e.g., Slack Block Kit, CloudEvents
        envelope, email HTML) and deliver it.

        Alert delivery is fire-and-forget: if delivery fails, return False
        and log the error. The system will NOT retry delivery.

        FR-025: Implementations MUST NOT include PII or sensitive data
        in alert payloads beyond what is in the ContractViolationEvent.

        Args:
            event: The contract violation event to alert on.

        Returns:
            True if delivery succeeded, False otherwise.
        """
        ...

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Validate the channel's configuration.

        Check that all required configuration (webhook URLs, SMTP settings,
        API endpoints, etc.) is present and valid. Called during plugin
        activation to fail fast on misconfiguration.

        Returns:
            List of validation error messages. Empty list means valid.

        Example:
            >>> errors = channel.validate_config()
            >>> if errors:
            ...     for error in errors:
            ...         logger.error("Config error", error=error)
        """
        ...
