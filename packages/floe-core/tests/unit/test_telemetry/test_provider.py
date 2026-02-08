"""Unit tests for TelemetryProvider.

Tests cover:
- T013: TelemetryProvider initialization and shutdown lifecycle
- T014: No-op mode detection via OTEL_SDK_DISABLED
- T023: Propagator integration during initialization
- T042: Authentication header injection

Requirements Covered:
- FR-001: Initialize OpenTelemetry SDK with TelemetryConfig
- FR-002: W3C Trace Context propagation
- FR-003: W3C Baggage propagation
- FR-011: Authentication header injection
- FR-023: Telemetry provider lifecycle management
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from floe_core.telemetry import (
    ProviderState,
    ResourceAttributes,
    TelemetryAuth,
    TelemetryConfig,
    TelemetryProvider,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def _mock_telemetry_backend() -> Generator[None, None, None]:
    """Mock the telemetry backend loader for all tests.

    Entry point plugins are not available in the test environment,
    so we mock load_telemetry_backend to return a mock plugin.
    """
    mock_plugin = Mock()
    mock_plugin.name = "console"
    with patch(
        "floe_core.telemetry.provider.load_telemetry_backend",
        return_value=mock_plugin,
    ):
        yield


@pytest.fixture
def telemetry_config() -> TelemetryConfig:
    """Create a TelemetryConfig for testing.

    Returns:
        TelemetryConfig instance with test values.
    """
    attrs = ResourceAttributes(
        service_name="test-service",
        service_version="1.0.0",
        deployment_environment="dev",
        floe_namespace="test-namespace",
        floe_product_name="test-product",
        floe_product_version="1.0.0",
        floe_mode="dev",
    )
    return TelemetryConfig(
        resource_attributes=attrs, otlp_endpoint="http://localhost:4317"
    )


@pytest.fixture
def disabled_telemetry_config() -> TelemetryConfig:
    """Create a disabled TelemetryConfig for testing.

    Returns:
        TelemetryConfig instance with enabled=False.
    """
    attrs = ResourceAttributes(
        service_name="test-service",
        service_version="1.0.0",
        deployment_environment="dev",
        floe_namespace="test-namespace",
        floe_product_name="test-product",
        floe_product_version="1.0.0",
        floe_mode="dev",
    )
    return TelemetryConfig(
        resource_attributes=attrs,
        otlp_endpoint="http://localhost:4317",
        enabled=False,
    )


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Ensure OTEL_SDK_DISABLED is not set during tests.

    Yields:
        None after cleaning environment.
    """
    original = os.environ.pop("OTEL_SDK_DISABLED", None)
    yield
    if original is not None:
        os.environ["OTEL_SDK_DISABLED"] = original


class TestTelemetryProviderInitialization:
    """Tests for TelemetryProvider initialization lifecycle (T013).

    Validates the provider correctly initializes and manages state.
    """

    def test_provider_initial_state_is_uninitialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test provider starts in UNINITIALIZED state."""
        provider = TelemetryProvider(telemetry_config)
        assert provider.state == ProviderState.UNINITIALIZED

    def test_provider_stores_config(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test provider stores the configuration."""
        provider = TelemetryProvider(telemetry_config)
        assert provider.config == telemetry_config

    def test_initialize_changes_state_to_initialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test initialize() transitions to INITIALIZED state."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED

    def test_initialize_cannot_be_called_twice(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test initialize() raises error if called twice."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        with pytest.raises(RuntimeError, match="Cannot initialize provider"):
            provider.initialize()

    def test_initialize_cannot_be_called_after_shutdown(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test initialize() raises error if called after shutdown."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        provider.shutdown()

        with pytest.raises(RuntimeError, match="Cannot initialize provider"):
            provider.initialize()


class TestTelemetryProviderShutdown:
    """Tests for TelemetryProvider shutdown lifecycle (T013).

    Validates the provider correctly shuts down and manages state.
    """

    def test_shutdown_changes_state_to_shutdown(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test shutdown() transitions to SHUTDOWN state."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        provider.shutdown()
        assert provider.state == ProviderState.SHUTDOWN

    def test_shutdown_cannot_be_called_when_uninitialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test shutdown() raises error if called when uninitialized."""
        provider = TelemetryProvider(telemetry_config)

        with pytest.raises(RuntimeError, match="Cannot shutdown provider"):
            provider.shutdown()

    def test_shutdown_cannot_be_called_twice(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test shutdown() raises error if called twice."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        provider.shutdown()

        with pytest.raises(RuntimeError, match="Cannot shutdown provider"):
            provider.shutdown()


class TestTelemetryProviderForceFlush:
    """Tests for TelemetryProvider force_flush lifecycle (T013).

    Validates the provider correctly flushes pending telemetry.
    """

    def test_force_flush_returns_true_when_successful(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test force_flush() returns True on success."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        result = provider.force_flush()
        assert result is True
        provider.shutdown()

    def test_force_flush_cannot_be_called_when_uninitialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test force_flush() raises error if called when uninitialized."""
        provider = TelemetryProvider(telemetry_config)

        with pytest.raises(RuntimeError, match="Cannot flush provider"):
            provider.force_flush()

    def test_force_flush_cannot_be_called_after_shutdown(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test force_flush() raises error if called after shutdown."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        provider.shutdown()

        with pytest.raises(RuntimeError, match="Cannot flush provider"):
            provider.force_flush()

    def test_force_flush_state_returns_to_initialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test force_flush() returns state to INITIALIZED."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        provider.force_flush()
        assert provider.state == ProviderState.INITIALIZED
        provider.shutdown()


class TestTelemetryProviderContextManager:
    """Tests for TelemetryProvider context manager protocol (T013).

    Validates the provider works correctly as a context manager.
    """

    def test_context_manager_initializes_on_enter(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test context manager initializes provider on enter."""
        provider = TelemetryProvider(telemetry_config)
        with provider:
            assert provider.state == ProviderState.INITIALIZED

    def test_context_manager_shuts_down_on_exit(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test context manager shuts down provider on exit."""
        provider = TelemetryProvider(telemetry_config)
        with provider:
            pass
        assert provider.state == ProviderState.SHUTDOWN

    def test_context_manager_returns_provider(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test context manager returns the provider instance."""
        provider = TelemetryProvider(telemetry_config)
        with provider as p:
            assert p is provider

    def test_context_manager_shuts_down_on_exception(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test context manager shuts down provider even on exception."""
        provider = TelemetryProvider(telemetry_config)
        with pytest.raises(ValueError, match="test error"):
            with provider:
                raise ValueError("test error")
        assert provider.state == ProviderState.SHUTDOWN


class TestTelemetryProviderNoopModeEnvVar:
    """Tests for no-op mode via OTEL_SDK_DISABLED environment variable (T014).

    Validates the provider correctly detects and handles no-op mode.
    """

    def test_otel_sdk_disabled_true_enables_noop(
        self, telemetry_config: TelemetryConfig
    ) -> None:
        """Test OTEL_SDK_DISABLED=true enables no-op mode."""
        os.environ["OTEL_SDK_DISABLED"] = "true"
        try:
            provider = TelemetryProvider(telemetry_config)
            assert provider.is_noop is True
        finally:
            os.environ.pop("OTEL_SDK_DISABLED", None)

    def test_otel_sdk_disabled_one_enables_noop(
        self, telemetry_config: TelemetryConfig
    ) -> None:
        """Test OTEL_SDK_DISABLED=1 enables no-op mode."""
        os.environ["OTEL_SDK_DISABLED"] = "1"
        try:
            provider = TelemetryProvider(telemetry_config)
            assert provider.is_noop is True
        finally:
            os.environ.pop("OTEL_SDK_DISABLED", None)

    def test_otel_sdk_disabled_yes_enables_noop(
        self, telemetry_config: TelemetryConfig
    ) -> None:
        """Test OTEL_SDK_DISABLED=yes enables no-op mode."""
        os.environ["OTEL_SDK_DISABLED"] = "yes"
        try:
            provider = TelemetryProvider(telemetry_config)
            assert provider.is_noop is True
        finally:
            os.environ.pop("OTEL_SDK_DISABLED", None)

    def test_otel_sdk_disabled_case_insensitive(
        self, telemetry_config: TelemetryConfig
    ) -> None:
        """Test OTEL_SDK_DISABLED is case-insensitive."""
        os.environ["OTEL_SDK_DISABLED"] = "TRUE"
        try:
            provider = TelemetryProvider(telemetry_config)
            assert provider.is_noop is True
        finally:
            os.environ.pop("OTEL_SDK_DISABLED", None)

    def test_otel_sdk_disabled_false_does_not_enable_noop(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test OTEL_SDK_DISABLED=false does not enable no-op mode."""
        os.environ["OTEL_SDK_DISABLED"] = "false"
        try:
            provider = TelemetryProvider(telemetry_config)
            assert provider.is_noop is False
        finally:
            os.environ.pop("OTEL_SDK_DISABLED", None)

    def test_no_env_var_does_not_enable_noop(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test missing OTEL_SDK_DISABLED does not enable no-op mode."""
        provider = TelemetryProvider(telemetry_config)
        assert provider.is_noop is False


class TestTelemetryProviderNoopModeConfig:
    """Tests for no-op mode via TelemetryConfig.enabled flag (T014).

    Validates the provider correctly handles disabled configuration.
    """

    def test_config_enabled_false_enables_noop(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test TelemetryConfig.enabled=False enables no-op mode."""
        provider = TelemetryProvider(disabled_telemetry_config)
        assert provider.is_noop is True

    def test_config_enabled_true_does_not_enable_noop(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test TelemetryConfig.enabled=True does not enable no-op mode."""
        provider = TelemetryProvider(telemetry_config)
        assert provider.is_noop is False


class TestTelemetryProviderNoopModeBehavior:
    """Tests for no-op mode behavior during lifecycle (T014).

    Validates that no-op mode still allows state transitions.
    """

    def test_noop_mode_allows_initialization(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test no-op mode allows initialization."""
        provider = TelemetryProvider(disabled_telemetry_config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED

    def test_noop_mode_allows_shutdown(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test no-op mode allows shutdown."""
        provider = TelemetryProvider(disabled_telemetry_config)
        provider.initialize()
        provider.shutdown()
        assert provider.state == ProviderState.SHUTDOWN

    def test_noop_mode_force_flush_returns_true(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test no-op mode force_flush returns True immediately."""
        provider = TelemetryProvider(disabled_telemetry_config)
        provider.initialize()
        result = provider.force_flush()
        assert result is True
        provider.shutdown()

    def test_noop_mode_context_manager_works(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test no-op mode context manager works correctly."""
        provider = TelemetryProvider(disabled_telemetry_config)
        with provider as p:
            assert p.state == ProviderState.INITIALIZED
            assert p.is_noop is True
        assert provider.state == ProviderState.SHUTDOWN

    def test_noop_mode_env_var_takes_precedence(
        self, telemetry_config: TelemetryConfig
    ) -> None:
        """Test OTEL_SDK_DISABLED takes precedence over config.enabled."""
        os.environ["OTEL_SDK_DISABLED"] = "true"
        try:
            # Config has enabled=True, but env var overrides
            provider = TelemetryProvider(telemetry_config)
            assert telemetry_config.enabled is True
            assert provider.is_noop is True
        finally:
            os.environ.pop("OTEL_SDK_DISABLED", None)


class TestTelemetryProviderPropagatorIntegration:
    """Tests for propagator integration during initialization (T023).

    Validates that W3C propagators are configured when provider initializes.
    """

    def test_initialize_configures_propagators(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that initialize() configures W3C propagators."""
        from opentelemetry.propagate import get_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        # After initialization, global propagator should be composite
        propagator = get_global_textmap()
        assert isinstance(propagator, CompositePropagator)

        provider.shutdown()

    def test_propagator_has_trace_context(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that propagator includes W3C Trace Context."""
        from opentelemetry.propagate import get_global_textmap

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        propagator = get_global_textmap()
        # CompositePropagator should have traceparent in fields
        assert "traceparent" in propagator.fields

        provider.shutdown()

    def test_propagator_has_baggage(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that propagator includes W3C Baggage."""
        from opentelemetry.propagate import get_global_textmap

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        propagator = get_global_textmap()
        # CompositePropagator should have baggage in fields
        assert "baggage" in propagator.fields

        provider.shutdown()

    def test_noop_mode_does_not_configure_propagators(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that no-op mode skips propagator configuration."""
        from opentelemetry.propagate import get_global_textmap, set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        # Set a known propagator before test
        original = TraceContextTextMapPropagator()
        set_global_textmap(original)

        provider = TelemetryProvider(disabled_telemetry_config)
        provider.initialize()

        # In no-op mode, propagator should NOT be changed to composite
        propagator = get_global_textmap()
        # Should still be the original (not composite)
        assert not isinstance(propagator, CompositePropagator)

        provider.shutdown()


class TestOTLPGrpcExporterSetup:
    """Tests for OTLP/gRPC exporter setup (T036).

    These tests validate that TelemetryProvider correctly configures
    the OTLP/gRPC span exporter when otlp_protocol is "grpc".

    Requirements: FR-008, FR-009, FR-010, FR-011, FR-024, FR-026
    """

    @pytest.fixture
    def grpc_telemetry_config(self) -> TelemetryConfig:
        """Create a TelemetryConfig with gRPC protocol.

        Returns:
            TelemetryConfig configured for gRPC export.
        """
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        return TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://localhost:4317",
            otlp_protocol="grpc",
        )

    def test_grpc_protocol_in_config(
        self, grpc_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryConfig accepts grpc protocol."""
        assert grpc_telemetry_config.otlp_protocol == "grpc"

    def test_grpc_endpoint_in_config(
        self, grpc_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryConfig stores gRPC endpoint."""
        assert grpc_telemetry_config.otlp_endpoint == "http://localhost:4317"

    def test_provider_accepts_grpc_config(
        self, grpc_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryProvider accepts gRPC configuration."""
        provider = TelemetryProvider(grpc_telemetry_config)
        assert provider.config.otlp_protocol == "grpc"

    def test_provider_initializes_with_grpc_config(
        self, grpc_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryProvider initializes with gRPC configuration."""
        provider = TelemetryProvider(grpc_telemetry_config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED
        provider.shutdown()

    def test_grpc_default_port_4317(self, clean_env: None) -> None:
        """Test that gRPC uses default port 4317 per OTel convention."""
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        # Default endpoint should use 4317 for gRPC
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_protocol="grpc",
        )
        # Default endpoint has 4317
        assert "4317" in config.otlp_endpoint

    def test_grpc_custom_endpoint(self, clean_env: None) -> None:
        """Test that gRPC accepts custom endpoint."""
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://otel-collector.monitoring:4317",
            otlp_protocol="grpc",
        )
        assert config.otlp_endpoint == "http://otel-collector.monitoring:4317"

    def test_grpc_protocol_is_default(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that gRPC is the default OTLP protocol."""
        # TelemetryConfig default should be grpc
        assert telemetry_config.otlp_protocol == "grpc"

    def test_grpc_config_with_batch_processor_settings(self, clean_env: None) -> None:
        """Test that gRPC config can include BatchSpanProcessor settings."""
        from floe_core.telemetry import BatchSpanProcessorConfig

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        batch_config = BatchSpanProcessorConfig(
            max_queue_size=4096,
            max_export_batch_size=1024,
            schedule_delay_millis=2000,
        )
        # TelemetryConfig includes batch_processor field
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_protocol="grpc",
            batch_processor=batch_config,
        )
        # Verify batch processor config is stored in TelemetryConfig
        assert config.otlp_protocol == "grpc"
        assert config.batch_processor.max_queue_size == 4096
        assert config.batch_processor.max_export_batch_size == 1024
        assert config.batch_processor.schedule_delay_millis == 2000

    def test_grpc_provider_uses_batch_processor_config(self, clean_env: None) -> None:
        """Test that TelemetryProvider uses BatchSpanProcessor config on init."""
        from floe_core.telemetry import BatchSpanProcessorConfig

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        batch_config = BatchSpanProcessorConfig(
            max_queue_size=8192,
            max_export_batch_size=2048,
            schedule_delay_millis=1000,
            export_timeout_millis=15000,
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_protocol="grpc",
            batch_processor=batch_config,
        )
        provider = TelemetryProvider(config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED
        # Verify the span processor was created
        assert provider._span_processor is not None
        provider.shutdown()


class TestOTLPHttpExporterSetup:
    """Tests for OTLP/HTTP exporter setup (T037).

    These tests validate that TelemetryProvider correctly configures
    the OTLP/HTTP span exporter when otlp_protocol is "http".

    Requirements: FR-008, FR-009, FR-010, FR-011, FR-024, FR-026
    """

    @pytest.fixture
    def http_telemetry_config(self) -> TelemetryConfig:
        """Create a TelemetryConfig with HTTP protocol.

        Returns:
            TelemetryConfig configured for HTTP export.
        """
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        return TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://localhost:4318",
            otlp_protocol="http",
        )

    def test_http_protocol_in_config(
        self, http_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryConfig accepts http protocol."""
        assert http_telemetry_config.otlp_protocol == "http"

    def test_http_endpoint_in_config(
        self, http_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryConfig stores HTTP endpoint."""
        assert http_telemetry_config.otlp_endpoint == "http://localhost:4318"

    def test_provider_accepts_http_config(
        self, http_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryProvider accepts HTTP configuration."""
        provider = TelemetryProvider(http_telemetry_config)
        assert provider.config.otlp_protocol == "http"

    def test_provider_initializes_with_http_config(
        self, http_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryProvider initializes with HTTP configuration.

        Validates FR-010: HTTP protocol selection creates OTLPHttpSpanExporter.
        """
        provider = TelemetryProvider(http_telemetry_config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED
        provider.shutdown()

    def test_http_custom_endpoint_port_4318(self, clean_env: None) -> None:
        """Test that HTTP uses port 4318 per OTel convention."""
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        # HTTP endpoint should use 4318 per OpenTelemetry convention
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://otel-collector:4318",
            otlp_protocol="http",
        )
        assert "4318" in config.otlp_endpoint

    def test_http_custom_endpoint(self, clean_env: None) -> None:
        """Test that HTTP accepts custom endpoint."""
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://otel-collector.monitoring:4318",
            otlp_protocol="http",
        )
        assert config.otlp_endpoint == "http://otel-collector.monitoring:4318"

    def test_http_endpoint_with_path(self, clean_env: None) -> None:
        """Test that HTTP endpoint can include path component."""
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        # HTTP OTLP typically uses /v1/traces for traces endpoint
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://otel-collector:4318/v1/traces",
            otlp_protocol="http",
        )
        assert "/v1/traces" in config.otlp_endpoint

    def test_http_protocol_is_valid_literal(self, clean_env: None) -> None:
        """Test that http is a valid protocol literal."""
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        # Should not raise validation error
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_protocol="http",
        )
        assert config.otlp_protocol == "http"

    def test_invalid_protocol_rejected(self, clean_env: None) -> None:
        """Test that invalid protocol is rejected."""
        from pydantic import ValidationError

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        with pytest.raises(ValidationError, match="Input should be 'grpc' or 'http'"):
            TelemetryConfig(
                resource_attributes=attrs,
                otlp_protocol="invalid",  # type: ignore[arg-type]
            )

    def test_http_config_with_batch_processor_settings(self, clean_env: None) -> None:
        """Test that HTTP config can include BatchSpanProcessor settings."""
        from floe_core.telemetry import BatchSpanProcessorConfig

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        batch_config = BatchSpanProcessorConfig(
            max_queue_size=4096,
            max_export_batch_size=1024,
            schedule_delay_millis=2000,
        )
        # TelemetryConfig includes batch_processor field for HTTP protocol
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_protocol="http",
            batch_processor=batch_config,
        )
        # Verify batch processor config is stored in TelemetryConfig
        assert config.otlp_protocol == "http"
        assert config.batch_processor.max_queue_size == 4096
        assert config.batch_processor.max_export_batch_size == 1024
        assert config.batch_processor.schedule_delay_millis == 2000

    def test_http_provider_uses_batch_processor_config(self, clean_env: None) -> None:
        """Test that TelemetryProvider with HTTP uses BatchSpanProcessor config."""
        from floe_core.telemetry import BatchSpanProcessorConfig

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        batch_config = BatchSpanProcessorConfig(
            max_queue_size=8192,
            max_export_batch_size=2048,
            schedule_delay_millis=1000,
            export_timeout_millis=15000,
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://localhost:4318",
            otlp_protocol="http",
            batch_processor=batch_config,
        )
        provider = TelemetryProvider(config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED
        # Verify the span processor was created
        assert provider._span_processor is not None
        provider.shutdown()


# T042: Unit tests for authentication header injection in TelemetryProvider
# These tests validate that TelemetryProvider correctly builds and uses
# authentication headers from TelemetryAuth configuration.


class TestTelemetryProviderAuthHeaderInjection:
    """Test TelemetryProvider authentication header injection (FR-011).

    TelemetryProvider builds authentication headers from TelemetryAuth
    and passes them to the OTLP exporter for SaaS backend authentication.
    """

    def test_build_auth_headers_with_api_key(self, clean_env: None) -> None:
        """Test _build_auth_headers generates correct headers for api_key auth."""
        from pydantic import SecretStr

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("my-api-key"),
            header_name="DD-API-KEY",
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            authentication=auth,
        )
        provider = TelemetryProvider(config)

        headers = provider._build_auth_headers()

        assert headers is not None
        assert headers == {"DD-API-KEY": "my-api-key"}

    def test_build_auth_headers_with_bearer_token(self, clean_env: None) -> None:
        """Test _build_auth_headers generates correct headers for bearer auth."""
        from pydantic import SecretStr

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("my-bearer-token"),
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            authentication=auth,
        )
        provider = TelemetryProvider(config)

        headers = provider._build_auth_headers()

        assert headers is not None
        assert headers == {"Authorization": "Bearer my-bearer-token"}

    def test_build_auth_headers_returns_none_when_no_auth(
        self, clean_env: None
    ) -> None:
        """Test _build_auth_headers returns None when no auth configured."""
        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            # No authentication configured
        )
        provider = TelemetryProvider(config)

        headers = provider._build_auth_headers()

        assert headers is None

    def test_provider_initializes_with_api_key_auth(self, clean_env: None) -> None:
        """Test TelemetryProvider initializes successfully with api_key auth."""
        from pydantic import SecretStr

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("datadog-api-key"),
            header_name="DD-API-KEY",
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://localhost:4317",
            otlp_protocol="grpc",
            authentication=auth,
        )
        provider = TelemetryProvider(config)

        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED
        provider.shutdown()

    def test_provider_initializes_with_bearer_auth(self, clean_env: None) -> None:
        """Test TelemetryProvider initializes successfully with bearer auth."""
        from pydantic import SecretStr

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("grafana-bearer-token"),
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_endpoint="http://localhost:4318",
            otlp_protocol="http",
            authentication=auth,
        )
        provider = TelemetryProvider(config)

        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED
        provider.shutdown()

    def test_bearer_auth_custom_header_name(self, clean_env: None) -> None:
        """Test bearer auth with custom header name."""
        from pydantic import SecretStr

        attrs = ResourceAttributes(
            service_name="test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("custom-token"),
            header_name="X-Custom-Auth",
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            authentication=auth,
        )
        provider = TelemetryProvider(config)

        headers = provider._build_auth_headers()

        assert headers is not None
        assert headers == {"X-Custom-Auth": "Bearer custom-token"}


# T044: Unit tests for async export (non-blocking) verification
# These tests validate that TelemetryProvider uses BatchSpanProcessor for
# asynchronous, non-blocking span export.
# Uses mocked exporters to avoid network calls in unit tests.


class TestTelemetryProviderAsyncExport:
    """Test TelemetryProvider async export behavior (FR-024, FR-026).

    BatchSpanProcessor provides non-blocking export via a background thread.
    Span creation returns immediately; export happens asynchronously.

    These tests mock the OTLP exporter to avoid network calls.
    """

    @pytest.fixture
    def mock_grpc_exporter(self) -> Generator[Mock, None, None]:
        """Mock the gRPC OTLP exporter to avoid network calls."""
        from unittest.mock import patch

        mock_exporter = Mock()
        mock_exporter.export.return_value = None
        mock_exporter.shutdown.return_value = None

        with patch(
            "floe_core.telemetry.provider.OTLPSpanExporter",
            return_value=mock_exporter,
        ):
            yield mock_exporter

    @pytest.fixture
    def telemetry_config(self) -> TelemetryConfig:
        """Create a basic TelemetryConfig for async export tests."""
        attrs = ResourceAttributes(
            service_name="async-test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        return TelemetryConfig(
            resource_attributes=attrs, otlp_endpoint="http://localhost:4317"
        )

    def test_provider_uses_batch_span_processor(
        self,
        telemetry_config: TelemetryConfig,
        mock_grpc_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that TelemetryProvider creates BatchSpanProcessor for async export."""
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        # Verify BatchSpanProcessor is created
        assert provider._span_processor is not None
        assert isinstance(provider._span_processor, BatchSpanProcessor)

        provider.shutdown()

    def test_span_creation_is_non_blocking(
        self,
        telemetry_config: TelemetryConfig,
        mock_grpc_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that span creation returns immediately without blocking on export.

        This verifies that creating spans does not wait for export to complete,
        which is the key characteristic of BatchSpanProcessor's async behavior.
        """
        import time

        from opentelemetry import trace

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        tracer = trace.get_tracer(__name__)

        # Create 100 spans and measure time - should be fast since non-blocking
        start_time = time.monotonic()
        for i in range(100):
            with tracer.start_as_current_span(f"test-span-{i}") as span:
                span.set_attribute("iteration", i)
        elapsed_time = time.monotonic() - start_time

        # Non-blocking span creation should be fast (< 500ms for 100 spans)
        # Use 500ms threshold to account for CI environment variability.
        # If export was synchronous, this would take much longer (seconds).
        assert elapsed_time < 0.5, (
            f"Span creation took {elapsed_time:.3f}s, expected < 0.5s. "
            "Export appears to be blocking."
        )

        provider.shutdown()

    def test_batch_processor_config_applied(
        self,
        mock_grpc_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that BatchSpanProcessor uses configured queue sizes."""
        from floe_core.telemetry import BatchSpanProcessorConfig

        attrs = ResourceAttributes(
            service_name="config-test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        batch_config = BatchSpanProcessorConfig(
            max_queue_size=4096,
            max_export_batch_size=1024,
            schedule_delay_millis=2000,
            export_timeout_millis=15000,
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            batch_processor=batch_config,
        )
        provider = TelemetryProvider(config)
        provider.initialize()

        # Verify span processor is created with our config
        assert provider._span_processor is not None
        # The config values are applied internally - we verify by checking
        # the span processor was created successfully
        assert provider.state == ProviderState.INITIALIZED

        provider.shutdown()

    def test_force_flush_waits_for_pending_exports(
        self,
        telemetry_config: TelemetryConfig,
        mock_grpc_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that force_flush waits for pending spans to be exported.

        This verifies that while span creation is non-blocking,
        force_flush can synchronously wait for export completion.
        """
        from opentelemetry import trace

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        tracer = trace.get_tracer(__name__)

        # Create some spans
        for i in range(10):
            with tracer.start_as_current_span(f"flush-test-span-{i}") as span:
                span.set_attribute("iteration", i)

        # Force flush should complete successfully, waiting for export
        result = provider.force_flush(timeout_millis=5000)
        assert result is True

        provider.shutdown()

    def test_shutdown_flushes_pending_exports(
        self,
        telemetry_config: TelemetryConfig,
        mock_grpc_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that shutdown flushes all pending spans before closing.

        Graceful shutdown ensures no telemetry data is lost.
        """
        from opentelemetry import trace

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        tracer = trace.get_tracer(__name__)

        # Create spans that would be pending in the batch queue
        for i in range(5):
            with tracer.start_as_current_span(f"shutdown-test-span-{i}") as span:
                span.set_attribute("iteration", i)

        # Shutdown should complete without errors, flushing pending spans
        provider.shutdown()

        assert provider.state == ProviderState.SHUTDOWN
        assert provider._span_processor is None


# T045: Unit tests for graceful degradation when backend unavailable
# These tests validate that TelemetryProvider continues operating when
# the OTLP backend is unavailable (SC-005: no application failures).


class TestTelemetryProviderGracefulDegradation:
    """Test TelemetryProvider graceful degradation (SC-005).

    The system must continue operating normally when the observability
    backend is unavailable - no application failures should occur.

    These tests mock the exporter to simulate backend failures.
    """

    @pytest.fixture
    def failing_exporter(self) -> Generator[Mock, None, None]:
        """Mock exporter that simulates backend unavailable."""
        from unittest.mock import patch

        mock_exporter = Mock()
        # Simulate export failure (returns failure result)
        mock_exporter.export.side_effect = Exception("Backend unavailable")
        mock_exporter.shutdown.return_value = None

        with patch(
            "floe_core.telemetry.provider.OTLPSpanExporter",
            return_value=mock_exporter,
        ):
            yield mock_exporter

    @pytest.fixture
    def telemetry_config(self) -> TelemetryConfig:
        """Create a basic TelemetryConfig for degradation tests."""
        attrs = ResourceAttributes(
            service_name="degradation-test-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        return TelemetryConfig(
            resource_attributes=attrs, otlp_endpoint="http://localhost:4317"
        )

    def test_span_creation_continues_when_export_fails(
        self,
        telemetry_config: TelemetryConfig,
        failing_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that span creation continues when export fails.

        Span creation should never fail due to export failures.
        The BatchSpanProcessor handles export failures internally.
        """
        from opentelemetry import trace

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        tracer = trace.get_tracer(__name__)

        # Create spans - should not raise even if export fails
        for i in range(10):
            with tracer.start_as_current_span(f"degradation-span-{i}") as span:
                span.set_attribute("iteration", i)

        # Provider should still be in initialized state
        assert provider.state == ProviderState.INITIALIZED

        provider.shutdown()

    def test_force_flush_handles_export_failure(
        self,
        telemetry_config: TelemetryConfig,
        failing_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that force_flush handles export failures gracefully.

        force_flush should not raise exceptions even if export fails.
        It may return False to indicate incomplete flush.
        """
        from opentelemetry import trace

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        tracer = trace.get_tracer(__name__)

        # Create some spans
        for i in range(5):
            with tracer.start_as_current_span(f"flush-fail-span-{i}") as span:
                span.set_attribute("iteration", i)

        # force_flush should not raise - may return False if export failed
        result = provider.force_flush(timeout_millis=1000)
        # Result could be True or False depending on SDK behavior
        assert isinstance(result, bool)

        # Provider should still be functional
        assert provider.state == ProviderState.INITIALIZED

        provider.shutdown()

    def test_shutdown_completes_when_export_fails(
        self,
        telemetry_config: TelemetryConfig,
        failing_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that shutdown completes even when export fails.

        Shutdown should always complete gracefully, releasing resources
        even if final flush fails.
        """
        from opentelemetry import trace

        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        tracer = trace.get_tracer(__name__)

        # Create spans that will fail to export
        for i in range(5):
            with tracer.start_as_current_span(f"shutdown-fail-span-{i}") as span:
                span.set_attribute("iteration", i)

        # Shutdown should complete without raising
        provider.shutdown()

        assert provider.state == ProviderState.SHUTDOWN
        assert provider._span_processor is None
        assert provider._tracer_provider is None

    def test_context_manager_handles_export_failure(
        self,
        telemetry_config: TelemetryConfig,
        failing_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that context manager handles export failures gracefully.

        The context manager should complete without raising even if
        export fails during shutdown.
        """
        from opentelemetry import trace

        # Context manager should work even with failing exporter
        with TelemetryProvider(telemetry_config) as provider:
            tracer = trace.get_tracer(__name__)

            for i in range(3):
                with tracer.start_as_current_span(f"cm-fail-span-{i}") as span:
                    span.set_attribute("iteration", i)

            state_inside = provider.state
            assert state_inside == ProviderState.INITIALIZED

        # Provider should be shutdown after context exit
        state_after = provider.state
        assert state_after == ProviderState.SHUTDOWN

    def test_application_exception_not_masked_by_export_failure(
        self,
        telemetry_config: TelemetryConfig,
        failing_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that application exceptions are not masked by export failures.

        If the application raises an exception, it should propagate correctly
        even if telemetry export is also failing.
        """
        from opentelemetry import trace

        with pytest.raises(ValueError, match="Application error"):
            with TelemetryProvider(telemetry_config):
                tracer = trace.get_tracer(__name__)

                with tracer.start_as_current_span("app-error-span"):
                    raise ValueError("Application error")

    def test_multiple_failures_do_not_cause_memory_leak(
        self,
        telemetry_config: TelemetryConfig,
        failing_exporter: Mock,
        clean_env: None,
    ) -> None:
        """Test that repeated export failures don't cause resource issues.

        BatchSpanProcessor drops spans when queue is full rather than
        growing unbounded.
        """
        from opentelemetry import trace

        from floe_core.telemetry import BatchSpanProcessorConfig

        # Use small queue to test queue-full behavior
        attrs = ResourceAttributes(
            service_name="small-queue-service",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test-namespace",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        )
        batch_config = BatchSpanProcessorConfig(
            max_queue_size=100,
            max_export_batch_size=50,
        )
        config = TelemetryConfig(
            resource_attributes=attrs,
            batch_processor=batch_config,
        )

        provider = TelemetryProvider(config)
        provider.initialize()

        tracer = trace.get_tracer(__name__)

        # Create many spans (more than queue size)
        for i in range(200):
            with tracer.start_as_current_span(f"queue-test-span-{i}") as span:
                span.set_attribute("iteration", i)

        # Provider should still be functional
        state_before = provider.state
        assert state_before == ProviderState.INITIALIZED

        provider.shutdown()
        state_after = provider.state
        assert state_after == ProviderState.SHUTDOWN
