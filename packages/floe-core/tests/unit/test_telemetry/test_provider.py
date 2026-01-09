"""Unit tests for TelemetryProvider.

Tests cover:
- T013: TelemetryProvider initialization and shutdown lifecycle
- T014: No-op mode detection via OTEL_SDK_DISABLED
- T023: Propagator integration during initialization

Requirements Covered:
- FR-001: Initialize OpenTelemetry SDK with TelemetryConfig
- FR-002: W3C Trace Context propagation
- FR-003: W3C Baggage propagation
- FR-023: Telemetry provider lifecycle management
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from floe_core.telemetry import (
    ProviderState,
    ResourceAttributes,
    TelemetryConfig,
    TelemetryProvider,
)

if TYPE_CHECKING:
    from collections.abc import Generator


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
    return TelemetryConfig(resource_attributes=attrs)


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
    return TelemetryConfig(resource_attributes=attrs, enabled=False)


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

    @pytest.mark.requirement("FR-001")
    def test_provider_initial_state_is_uninitialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test provider starts in UNINITIALIZED state."""
        provider = TelemetryProvider(telemetry_config)
        assert provider.state == ProviderState.UNINITIALIZED

    @pytest.mark.requirement("FR-001")
    def test_provider_stores_config(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test provider stores the configuration."""
        provider = TelemetryProvider(telemetry_config)
        assert provider.config == telemetry_config

    @pytest.mark.requirement("FR-001")
    def test_initialize_changes_state_to_initialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test initialize() transitions to INITIALIZED state."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED

    @pytest.mark.requirement("FR-001")
    def test_initialize_cannot_be_called_twice(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test initialize() raises error if called twice."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()

        with pytest.raises(RuntimeError, match="Cannot initialize provider"):
            provider.initialize()

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-023")
    def test_shutdown_changes_state_to_shutdown(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test shutdown() transitions to SHUTDOWN state."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        provider.shutdown()
        assert provider.state == ProviderState.SHUTDOWN

    @pytest.mark.requirement("FR-023")
    def test_shutdown_cannot_be_called_when_uninitialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test shutdown() raises error if called when uninitialized."""
        provider = TelemetryProvider(telemetry_config)

        with pytest.raises(RuntimeError, match="Cannot shutdown provider"):
            provider.shutdown()

    @pytest.mark.requirement("FR-023")
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

    @pytest.mark.requirement("FR-023")
    def test_force_flush_returns_true_when_successful(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test force_flush() returns True on success."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        result = provider.force_flush()
        assert result is True
        provider.shutdown()

    @pytest.mark.requirement("FR-023")
    def test_force_flush_cannot_be_called_when_uninitialized(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test force_flush() raises error if called when uninitialized."""
        provider = TelemetryProvider(telemetry_config)

        with pytest.raises(RuntimeError, match="Cannot flush provider"):
            provider.force_flush()

    @pytest.mark.requirement("FR-023")
    def test_force_flush_cannot_be_called_after_shutdown(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test force_flush() raises error if called after shutdown."""
        provider = TelemetryProvider(telemetry_config)
        provider.initialize()
        provider.shutdown()

        with pytest.raises(RuntimeError, match="Cannot flush provider"):
            provider.force_flush()

    @pytest.mark.requirement("FR-023")
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

    @pytest.mark.requirement("FR-001")
    def test_context_manager_initializes_on_enter(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test context manager initializes provider on enter."""
        provider = TelemetryProvider(telemetry_config)
        with provider:
            assert provider.state == ProviderState.INITIALIZED

    @pytest.mark.requirement("FR-023")
    def test_context_manager_shuts_down_on_exit(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test context manager shuts down provider on exit."""
        provider = TelemetryProvider(telemetry_config)
        with provider:
            pass
        assert provider.state == ProviderState.SHUTDOWN

    @pytest.mark.requirement("FR-023")
    def test_context_manager_returns_provider(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test context manager returns the provider instance."""
        provider = TelemetryProvider(telemetry_config)
        with provider as p:
            assert p is provider

    @pytest.mark.requirement("FR-023")
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

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-001")
    def test_config_enabled_false_enables_noop(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test TelemetryConfig.enabled=False enables no-op mode."""
        provider = TelemetryProvider(disabled_telemetry_config)
        assert provider.is_noop is True

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-023")
    def test_noop_mode_allows_initialization(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test no-op mode allows initialization."""
        provider = TelemetryProvider(disabled_telemetry_config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED

    @pytest.mark.requirement("FR-023")
    def test_noop_mode_allows_shutdown(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test no-op mode allows shutdown."""
        provider = TelemetryProvider(disabled_telemetry_config)
        provider.initialize()
        provider.shutdown()
        assert provider.state == ProviderState.SHUTDOWN

    @pytest.mark.requirement("FR-023")
    def test_noop_mode_force_flush_returns_true(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test no-op mode force_flush returns True immediately."""
        provider = TelemetryProvider(disabled_telemetry_config)
        provider.initialize()
        result = provider.force_flush()
        assert result is True
        provider.shutdown()

    @pytest.mark.requirement("FR-023")
    def test_noop_mode_context_manager_works(
        self, disabled_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test no-op mode context manager works correctly."""
        provider = TelemetryProvider(disabled_telemetry_config)
        with provider as p:
            assert p.state == ProviderState.INITIALIZED
            assert p.is_noop is True
        assert provider.state == ProviderState.SHUTDOWN

    @pytest.mark.requirement("FR-001")
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

    @pytest.mark.requirement("FR-002")
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

    @pytest.mark.requirement("FR-002")
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

    @pytest.mark.requirement("FR-003")
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

    @pytest.mark.requirement("FR-002")
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

    @pytest.mark.requirement("FR-008")
    def test_grpc_protocol_in_config(
        self, grpc_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryConfig accepts grpc protocol."""
        assert grpc_telemetry_config.otlp_protocol == "grpc"

    @pytest.mark.requirement("FR-008")
    def test_grpc_endpoint_in_config(
        self, grpc_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryConfig stores gRPC endpoint."""
        assert grpc_telemetry_config.otlp_endpoint == "http://localhost:4317"

    @pytest.mark.requirement("FR-008")
    def test_provider_accepts_grpc_config(
        self, grpc_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryProvider accepts gRPC configuration."""
        provider = TelemetryProvider(grpc_telemetry_config)
        assert provider.config.otlp_protocol == "grpc"

    @pytest.mark.requirement("FR-008")
    def test_provider_initializes_with_grpc_config(
        self, grpc_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryProvider initializes with gRPC configuration."""
        provider = TelemetryProvider(grpc_telemetry_config)
        provider.initialize()
        assert provider.state == ProviderState.INITIALIZED
        provider.shutdown()

    @pytest.mark.requirement("FR-008")
    def test_grpc_default_port_4317(
        self, clean_env: None
    ) -> None:
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

    @pytest.mark.requirement("FR-008")
    def test_grpc_custom_endpoint(
        self, clean_env: None
    ) -> None:
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

    @pytest.mark.requirement("FR-010")
    def test_grpc_protocol_is_default(
        self, telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that gRPC is the default OTLP protocol."""
        # TelemetryConfig default should be grpc
        assert telemetry_config.otlp_protocol == "grpc"

    @pytest.mark.requirement("FR-024")
    def test_grpc_config_with_batch_processor_settings(
        self, clean_env: None
    ) -> None:
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
        # BatchSpanProcessorConfig can be created alongside TelemetryConfig
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_protocol="grpc",
        )
        # Both configs are valid and can be used together
        assert config.otlp_protocol == "grpc"
        assert batch_config.max_queue_size == 4096


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

    @pytest.mark.requirement("FR-009")
    def test_http_protocol_in_config(
        self, http_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryConfig accepts http protocol."""
        assert http_telemetry_config.otlp_protocol == "http"

    @pytest.mark.requirement("FR-009")
    def test_http_endpoint_in_config(
        self, http_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryConfig stores HTTP endpoint."""
        assert http_telemetry_config.otlp_endpoint == "http://localhost:4318"

    @pytest.mark.requirement("FR-009")
    def test_provider_accepts_http_config(
        self, http_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryProvider accepts HTTP configuration."""
        provider = TelemetryProvider(http_telemetry_config)
        assert provider.config.otlp_protocol == "http"

    @pytest.mark.requirement("FR-009")
    def test_provider_initializes_with_http_config(
        self, http_telemetry_config: TelemetryConfig, clean_env: None
    ) -> None:
        """Test that TelemetryProvider initializes with HTTP configuration.

        NOTE: HTTP protocol implementation is T041. Until then, this raises
        NotImplementedError. Update this test when T041 is complete.
        """
        provider = TelemetryProvider(http_telemetry_config)
        # HTTP protocol not yet implemented (T041)
        with pytest.raises(NotImplementedError, match="Protocol 'http' not yet implemented"):
            provider.initialize()

    @pytest.mark.requirement("FR-009")
    def test_http_custom_endpoint_port_4318(
        self, clean_env: None
    ) -> None:
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

    @pytest.mark.requirement("FR-009")
    def test_http_custom_endpoint(
        self, clean_env: None
    ) -> None:
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

    @pytest.mark.requirement("FR-009")
    def test_http_endpoint_with_path(
        self, clean_env: None
    ) -> None:
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

    @pytest.mark.requirement("FR-009")
    def test_http_protocol_is_valid_literal(
        self, clean_env: None
    ) -> None:
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

    @pytest.mark.requirement("FR-009")
    def test_invalid_protocol_rejected(
        self, clean_env: None
    ) -> None:
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

    @pytest.mark.requirement("FR-024")
    def test_http_config_with_batch_processor_settings(
        self, clean_env: None
    ) -> None:
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
        # BatchSpanProcessorConfig can be created alongside HTTP TelemetryConfig
        config = TelemetryConfig(
            resource_attributes=attrs,
            otlp_protocol="http",
        )
        # Both configs are valid and can be used together
        assert config.otlp_protocol == "http"
        assert batch_config.max_queue_size == 4096
