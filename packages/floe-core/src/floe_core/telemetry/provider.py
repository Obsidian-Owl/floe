"""TelemetryProvider: OpenTelemetry SDK lifecycle management.

This module provides the TelemetryProvider class for managing OpenTelemetry SDK
initialization, shutdown, and telemetry emission.

Contract Version: 1.0.0

Requirements Covered:
- FR-001: Initialize OpenTelemetry SDK with TelemetryConfig
- FR-002: W3C Trace Context propagation (via configure_propagators)
- FR-003: W3C Baggage propagation (via configure_propagators)

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

import logging
import os
from enum import Enum, auto
from typing import TYPE_CHECKING

from floe_core.telemetry.propagation import configure_propagators

if TYPE_CHECKING:
    from types import TracebackType

    from floe_core.telemetry.config import TelemetryConfig

logger = logging.getLogger(__name__)


class ProviderState(Enum):
    """TelemetryProvider lifecycle states.

    States:
        UNINITIALIZED: SDK not initialized, API returns no-op
        INITIALIZED: Active telemetry emission
        FLUSHING: Force-flush in progress (graceful shutdown)
        SHUTDOWN: Provider closed, no more telemetry
    """

    UNINITIALIZED = auto()
    INITIALIZED = auto()
    FLUSHING = auto()
    SHUTDOWN = auto()


class TelemetryProvider:
    """OpenTelemetry SDK provider with lifecycle management.

    Manages the OpenTelemetry SDK initialization, configuration, and shutdown.
    Supports context manager protocol for automatic cleanup.

    The provider respects the OTEL_SDK_DISABLED environment variable for no-op mode.

    Attributes:
        config: TelemetryConfig with SDK configuration
        state: Current lifecycle state

    Examples:
        >>> from floe_core.telemetry import TelemetryConfig, ResourceAttributes
        >>> attrs = ResourceAttributes(
        ...     service_name="my-service",
        ...     service_version="1.0.0",
        ...     deployment_environment="dev",
        ...     floe_namespace="analytics",
        ...     floe_product_name="customer-360",
        ...     floe_product_version="1.0.0",
        ...     floe_mode="dev",
        ... )
        >>> config = TelemetryConfig(resource_attributes=attrs)
        >>> with TelemetryProvider(config) as provider:
        ...     # Telemetry is active
        ...     pass

    See Also:
        - TelemetryConfig: Configuration model
        - ADR-0006: Telemetry architecture
    """

    def __init__(self, config: TelemetryConfig) -> None:
        """Initialize TelemetryProvider with configuration.

        Args:
            config: TelemetryConfig containing SDK configuration.
        """
        self._config = config
        self._state = ProviderState.UNINITIALIZED
        self._noop_mode = self._check_noop_mode()

    @property
    def config(self) -> TelemetryConfig:
        """Get the telemetry configuration."""
        return self._config

    @property
    def state(self) -> ProviderState:
        """Get the current provider state."""
        return self._state

    @property
    def is_noop(self) -> bool:
        """Check if provider is in no-op mode.

        Returns:
            True if telemetry is disabled or in no-op mode.
        """
        return self._noop_mode or not self._config.enabled

    def _check_noop_mode(self) -> bool:
        """Check if OTEL_SDK_DISABLED environment variable is set.

        Per OpenTelemetry specification, OTEL_SDK_DISABLED=true disables the SDK.

        Returns:
            True if SDK should be disabled.
        """
        disabled = os.environ.get("OTEL_SDK_DISABLED", "").lower()
        return disabled in ("true", "1", "yes")

    def initialize(self) -> None:
        """Initialize the OpenTelemetry SDK.

        Configures the SDK with the provided TelemetryConfig.
        In no-op mode, this is a no-op.

        Raises:
            RuntimeError: If provider is not in UNINITIALIZED state.
        """
        if self._state != ProviderState.UNINITIALIZED:
            raise RuntimeError(
                f"Cannot initialize provider in state {self._state.name}. "
                "Provider must be in UNINITIALIZED state."
            )

        if self.is_noop:
            logger.info(
                "TelemetryProvider initialized in no-op mode",
                extra={"noop_reason": self._get_noop_reason()},
            )
            self._state = ProviderState.INITIALIZED
            return

        # Configure W3C Trace Context and Baggage propagators (FR-002, FR-003)
        configure_propagators()

        # TODO: Initialize actual OpenTelemetry SDK (T040+)
        # - Configure TracerProvider with resource attributes
        # - Configure sampler based on environment
        # - Set up OTLP exporter (gRPC or HTTP)
        # - Register as global provider
        logger.info(
            "TelemetryProvider initialized",
            extra={
                "endpoint": self._config.otlp_endpoint,
                "protocol": self._config.otlp_protocol,
                "service_name": self._config.resource_attributes.service_name,
            },
        )
        self._state = ProviderState.INITIALIZED

    def _get_noop_reason(self) -> str:
        """Get the reason for no-op mode.

        Returns:
            Human-readable reason for no-op mode.
        """
        if os.environ.get("OTEL_SDK_DISABLED", "").lower() in ("true", "1", "yes"):
            return "OTEL_SDK_DISABLED environment variable set"
        if not self._config.enabled:
            return "TelemetryConfig.enabled is False"
        return "unknown"

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush all pending telemetry data.

        Args:
            timeout_millis: Maximum time to wait for flush (default 30s).

        Returns:
            True if flush completed successfully, False on timeout.

        Raises:
            RuntimeError: If provider is not in INITIALIZED state.
        """
        if self._state != ProviderState.INITIALIZED:
            raise RuntimeError(
                f"Cannot flush provider in state {self._state.name}. "
                "Provider must be in INITIALIZED state."
            )

        if self.is_noop:
            return True

        self._state = ProviderState.FLUSHING
        try:
            # TODO: Call actual SDK force_flush (T015)
            logger.debug(
                "TelemetryProvider force_flush completed",
                extra={"timeout_millis": timeout_millis},
            )
            return True
        finally:
            self._state = ProviderState.INITIALIZED

    def shutdown(self, timeout_millis: int = 30000) -> None:
        """Shutdown the TelemetryProvider.

        Flushes pending data and releases resources.
        After shutdown, the provider cannot be reused.

        Args:
            timeout_millis: Maximum time to wait for shutdown (default 30s).

        Raises:
            RuntimeError: If provider is not in INITIALIZED state.
        """
        if self._state not in (ProviderState.INITIALIZED, ProviderState.FLUSHING):
            raise RuntimeError(
                f"Cannot shutdown provider in state {self._state.name}. "
                "Provider must be in INITIALIZED or FLUSHING state."
            )

        if not self.is_noop:
            # Force flush before shutdown
            self._state = ProviderState.FLUSHING
            # TODO: Call actual SDK shutdown (T015)
            logger.info(
                "TelemetryProvider shutdown",
                extra={"timeout_millis": timeout_millis},
            )

        self._state = ProviderState.SHUTDOWN

    def __enter__(self) -> TelemetryProvider:
        """Enter context manager, initializing the provider.

        Returns:
            Self for use in with statement.
        """
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, shutting down the provider.

        Args:
            exc_type: Exception type if raised in context.
            exc_val: Exception value if raised in context.
            exc_tb: Exception traceback if raised in context.
        """
        if self._state == ProviderState.INITIALIZED:
            self.shutdown()
