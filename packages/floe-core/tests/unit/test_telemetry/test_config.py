"""Unit tests for telemetry configuration models.

Tests TelemetryConfig, ResourceAttributes, SamplingConfig, TelemetryAuth,
and BatchSpanProcessorConfig Pydantic models from floe_core.telemetry.config.

Contract Version: 1.0.0
Per ADR-0006: Telemetry configuration models.

Tests cover:
- T007: TelemetryConfig validation
- T035: BatchSpanProcessorConfig validation
- T038: TelemetryAuth header injection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr, ValidationError

from floe_core.telemetry import (
    BatchSpanProcessorConfig,
    ResourceAttributes,
    SamplingConfig,
    TelemetryAuth,
    TelemetryConfig,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# T007: Unit tests for TelemetryConfig validation
# =============================================================================


class TestTelemetryConfigValidation:
    """Test TelemetryConfig Pydantic model validation.

    Requirement: FR-001, FR-023
    """

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_with_required_fields(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig accepts valid required fields."""
        config = TelemetryConfig(
            resource_attributes=sample_resource_attributes,
            otlp_endpoint="http://localhost:4317",
        )

        assert config.enabled is True
        assert config.otlp_endpoint == "http://localhost:4317"
        assert config.otlp_protocol == "grpc"
        assert config.resource_attributes == sample_resource_attributes

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_with_all_fields(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig accepts all optional fields."""
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("test-api-key"),
            header_name="DD-API-KEY",
        )
        sampling = SamplingConfig(dev=1.0, staging=0.25, prod=0.05)

        config = TelemetryConfig(
            enabled=False,
            otlp_endpoint="http://custom-collector:4318",
            otlp_protocol="http",
            sampling=sampling,
            resource_attributes=sample_resource_attributes,
            authentication=auth,
        )

        assert config.enabled is False
        assert config.otlp_endpoint == "http://custom-collector:4318"
        assert config.otlp_protocol == "http"
        assert config.sampling.staging == pytest.approx(0.25)
        assert config.authentication is not None
        assert config.authentication.auth_type == "api_key"

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_requires_resource_attributes(self) -> None:
        """Test TelemetryConfig requires resource_attributes field."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryConfig()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("resource_attributes",) for e in errors)

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_rejects_invalid_protocol(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig rejects invalid otlp_protocol values."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryConfig(
                resource_attributes=sample_resource_attributes,
                otlp_endpoint="http://localhost:4317",
                otlp_protocol="invalid",  # type: ignore[arg-type]
            )

        errors = exc_info.value.errors()
        assert any("otlp_protocol" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_is_frozen(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig is immutable (frozen=True)."""
        config = TelemetryConfig(
            resource_attributes=sample_resource_attributes,
            otlp_endpoint="http://localhost:4317",
        )

        with pytest.raises(ValidationError):
            config.enabled = False

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_forbids_extra_fields(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig rejects unknown fields (extra='forbid')."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryConfig(
                resource_attributes=sample_resource_attributes,
                otlp_endpoint="http://localhost:4317",
                unknown_field="value",  # type: ignore[call-arg]
            )

        errors = exc_info.value.errors()
        assert any("extra" in str(e["type"]) for e in errors)

    @pytest.mark.requirement("FR-023")
    def test_telemetry_config_get_sampling_ratio(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig.get_sampling_ratio() method."""
        config = TelemetryConfig(
            resource_attributes=sample_resource_attributes,
            otlp_endpoint="http://localhost:4317",
            sampling=SamplingConfig(dev=1.0, staging=0.5, prod=0.1),
        )

        assert config.get_sampling_ratio("dev") == pytest.approx(1.0)
        assert config.get_sampling_ratio("staging") == pytest.approx(0.5)
        assert config.get_sampling_ratio("prod") == pytest.approx(0.1)

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_default_sampling(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig uses default SamplingConfig values."""
        config = TelemetryConfig(
            resource_attributes=sample_resource_attributes,
            otlp_endpoint="http://localhost:4317",
        )

        assert config.sampling.dev == pytest.approx(1.0)
        assert config.sampling.staging == pytest.approx(0.5)
        assert config.sampling.prod == pytest.approx(0.1)


# =============================================================================
# T008: Unit tests for ResourceAttributes.to_otel_dict()
# =============================================================================


class TestResourceAttributesToOtelDict:
    """Test ResourceAttributes.to_otel_dict() method.

    Requirement: FR-001, FR-023
    """

    @pytest.mark.requirement("FR-001")
    def test_to_otel_dict_returns_correct_keys(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test to_otel_dict() returns OTel semantic convention keys."""
        result = sample_resource_attributes.to_otel_dict()

        expected_keys = {
            "service.name",
            "service.version",
            "deployment.environment",
            "floe.namespace",
            "floe.product.name",
            "floe.product.version",
            "floe.mode",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.requirement("FR-001")
    def test_to_otel_dict_returns_correct_values(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test to_otel_dict() returns correct attribute values."""
        result = sample_resource_attributes.to_otel_dict()

        assert result["service.name"] == "test-service"
        assert result["service.version"] == "1.0.0"
        assert result["deployment.environment"] == "dev"
        assert result["floe.namespace"] == "analytics"
        assert result["floe.product.name"] == "customer-360"
        assert result["floe.product.version"] == "2.1.0"
        assert result["floe.mode"] == "dev"

    @pytest.mark.requirement("FR-001")
    def test_to_otel_dict_with_prod_environment(
        self,
        valid_resource_attributes: dict[str, str],
    ) -> None:
        """Test to_otel_dict() with production environment."""
        attrs = ResourceAttributes(
            **{  # type: ignore[arg-type]
                **valid_resource_attributes,
                "deployment_environment": "prod",
                "floe_mode": "prod",
            }
        )
        result = attrs.to_otel_dict()

        assert result["deployment.environment"] == "prod"
        assert result["floe.mode"] == "prod"


class TestResourceAttributesValidation:
    """Test ResourceAttributes Pydantic validation.

    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_requires_all_fields(self) -> None:
        """Test ResourceAttributes requires all mandatory fields."""
        with pytest.raises(ValidationError) as exc_info:
            ResourceAttributes()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        required_fields = {
            "service_name",
            "service_version",
            "deployment_environment",
            "floe_namespace",
            "floe_product_name",
            "floe_product_version",
            "floe_mode",
        }
        error_fields = {e["loc"][0] for e in errors}
        assert required_fields <= error_fields

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_validates_service_version_semver(
        self,
        valid_resource_attributes: dict[str, str],
    ) -> None:
        """Test service_version must follow semver pattern."""
        with pytest.raises(ValidationError) as exc_info:
            ResourceAttributes(  # type: ignore[arg-type]
                **{**valid_resource_attributes, "service_version": "invalid"}
            )

        errors = exc_info.value.errors()
        assert any("service_version" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_accepts_semver_with_prerelease(
        self,
        valid_resource_attributes: dict[str, str],
    ) -> None:
        """Test service_version accepts semver with prerelease suffix."""
        attrs = ResourceAttributes(  # type: ignore[arg-type]
            **{**valid_resource_attributes, "service_version": "1.0.0-beta.1"}
        )
        assert attrs.service_version == "1.0.0-beta.1"

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_validates_environment_literal(
        self,
        valid_resource_attributes: dict[str, str],
    ) -> None:
        """Test deployment_environment must be dev, staging, or prod."""
        with pytest.raises(ValidationError) as exc_info:
            ResourceAttributes(  # type: ignore[arg-type]
                **{**valid_resource_attributes, "deployment_environment": "production"}
            )

        errors = exc_info.value.errors()
        assert any("deployment_environment" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_validates_floe_mode_literal(
        self,
        valid_resource_attributes: dict[str, str],
    ) -> None:
        """Test floe_mode must be dev, staging, or prod."""
        with pytest.raises(ValidationError) as exc_info:
            ResourceAttributes(  # type: ignore[arg-type]
                **{**valid_resource_attributes, "floe_mode": "development"}
            )

        errors = exc_info.value.errors()
        assert any("floe_mode" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_validates_service_name_length(
        self,
        valid_resource_attributes: dict[str, str],
    ) -> None:
        """Test service_name has max length 128."""
        with pytest.raises(ValidationError):
            ResourceAttributes(  # type: ignore[arg-type]
                **{**valid_resource_attributes, "service_name": "x" * 129}
            )

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_validates_service_name_not_empty(
        self,
        valid_resource_attributes: dict[str, str],
    ) -> None:
        """Test service_name cannot be empty."""
        with pytest.raises(ValidationError):
            ResourceAttributes(  # type: ignore[arg-type]
                **{**valid_resource_attributes, "service_name": ""}
            )

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_is_frozen(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test ResourceAttributes is immutable (frozen=True)."""
        with pytest.raises(ValidationError):
            sample_resource_attributes.service_name = "new-name"

    @pytest.mark.requirement("FR-001")
    def test_resource_attributes_forbids_extra_fields(
        self,
        valid_resource_attributes: dict[str, str],
    ) -> None:
        """Test ResourceAttributes rejects unknown fields."""
        with pytest.raises(ValidationError):
            ResourceAttributes(  # type: ignore[arg-type]
                **valid_resource_attributes,
                custom_field="value",  # type: ignore[call-arg]
            )


# =============================================================================
# T009: Unit tests for SamplingConfig.get_ratio()
# =============================================================================


class TestSamplingConfigGetRatio:
    """Test SamplingConfig.get_ratio() method.

    Requirement: FR-023
    """

    @pytest.mark.requirement("FR-023")
    def test_get_ratio_returns_dev_ratio(
        self,
        default_sampling_config: SamplingConfig,
    ) -> None:
        """Test get_ratio('dev') returns dev sampling ratio."""
        assert default_sampling_config.get_ratio("dev") == pytest.approx(1.0)

    @pytest.mark.requirement("FR-023")
    def test_get_ratio_returns_staging_ratio(
        self,
        default_sampling_config: SamplingConfig,
    ) -> None:
        """Test get_ratio('staging') returns staging sampling ratio."""
        assert default_sampling_config.get_ratio("staging") == pytest.approx(0.5)

    @pytest.mark.requirement("FR-023")
    def test_get_ratio_returns_prod_ratio(
        self,
        default_sampling_config: SamplingConfig,
    ) -> None:
        """Test get_ratio('prod') returns prod sampling ratio."""
        assert default_sampling_config.get_ratio("prod") == pytest.approx(0.1)

    @pytest.mark.requirement("FR-023")
    def test_get_ratio_returns_default_for_unknown(
        self,
        default_sampling_config: SamplingConfig,
    ) -> None:
        """Test get_ratio() returns 1.0 for unknown environments."""
        assert default_sampling_config.get_ratio("unknown") == pytest.approx(1.0)
        assert default_sampling_config.get_ratio("test") == pytest.approx(1.0)

    @pytest.mark.requirement("FR-023")
    def test_get_ratio_with_custom_values(self) -> None:
        """Test get_ratio() with custom sampling configuration."""
        config = SamplingConfig(dev=0.8, staging=0.3, prod=0.01)

        assert config.get_ratio("dev") == pytest.approx(0.8)
        assert config.get_ratio("staging") == pytest.approx(0.3)
        assert config.get_ratio("prod") == pytest.approx(0.01)


class TestSamplingConfigValidation:
    """Test SamplingConfig Pydantic validation.

    Requirement: FR-023
    """

    @pytest.mark.requirement("FR-023")
    def test_sampling_config_default_values(self) -> None:
        """Test SamplingConfig uses correct default values."""
        config = SamplingConfig()

        assert config.dev == pytest.approx(1.0)
        assert config.staging == pytest.approx(0.5)
        assert config.prod == pytest.approx(0.1)

    @pytest.mark.requirement("FR-023")
    def test_sampling_config_validates_ratio_bounds_min(self) -> None:
        """Test sampling ratios cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            SamplingConfig(dev=-0.1)

        errors = exc_info.value.errors()
        assert any("dev" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("FR-023")
    def test_sampling_config_validates_ratio_bounds_max(self) -> None:
        """Test sampling ratios cannot exceed 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            SamplingConfig(staging=1.5)

        errors = exc_info.value.errors()
        assert any("staging" in str(e["loc"]) for e in errors)

    @pytest.mark.requirement("FR-023")
    def test_sampling_config_accepts_boundary_values(self) -> None:
        """Test sampling ratios accept 0.0 and 1.0 boundaries."""
        config = SamplingConfig(dev=0.0, staging=1.0, prod=0.0)

        assert config.dev == pytest.approx(0.0)
        assert config.staging == pytest.approx(1.0)
        assert config.prod == pytest.approx(0.0)

    @pytest.mark.requirement("FR-023")
    def test_sampling_config_is_frozen(self) -> None:
        """Test SamplingConfig is immutable (frozen=True)."""
        config = SamplingConfig()

        with pytest.raises(ValidationError):
            config.dev = 0.5

    @pytest.mark.requirement("FR-023")
    def test_sampling_config_forbids_extra_fields(self) -> None:
        """Test SamplingConfig rejects unknown fields."""
        with pytest.raises(ValidationError):
            SamplingConfig(
                custom_env=0.5,  # type: ignore[call-arg]
            )


# =============================================================================
# TelemetryAuth Tests (supporting T007)
# =============================================================================


class TestTelemetryAuthValidation:
    """Test TelemetryAuth Pydantic validation.

    Requirement: FR-001
    """

    @pytest.mark.requirement("FR-001")
    def test_auth_api_key_requires_api_key(self) -> None:
        """Test api_key auth_type requires api_key field."""
        with pytest.raises(ValidationError, match="api_key required"):
            TelemetryAuth(auth_type="api_key")

    @pytest.mark.requirement("FR-001")
    def test_auth_bearer_requires_bearer_token(self) -> None:
        """Test bearer auth_type requires bearer_token field."""
        with pytest.raises(ValidationError, match="bearer_token required"):
            TelemetryAuth(auth_type="bearer")

    @pytest.mark.requirement("FR-001")
    def test_auth_api_key_valid(self) -> None:
        """Test valid api_key authentication."""
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("my-api-key"),
            header_name="X-API-KEY",
        )

        assert auth.auth_type == "api_key"
        assert auth.api_key is not None
        assert auth.api_key.get_secret_value() == "my-api-key"
        assert auth.header_name == "X-API-KEY"

    @pytest.mark.requirement("FR-001")
    def test_auth_bearer_valid(self) -> None:
        """Test valid bearer token authentication."""
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("my-bearer-token"),
        )

        assert auth.auth_type == "bearer"
        assert auth.bearer_token is not None
        assert auth.bearer_token.get_secret_value() == "my-bearer-token"
        assert auth.header_name == "Authorization"  # Default

    @pytest.mark.requirement("FR-001")
    def test_auth_is_frozen(self) -> None:
        """Test TelemetryAuth is immutable."""
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("key"),
        )

        with pytest.raises(ValidationError):
            auth.auth_type = "bearer"

    @pytest.mark.requirement("FR-001")
    def test_auth_rejects_invalid_auth_type(self) -> None:
        """Test TelemetryAuth rejects invalid auth_type."""
        with pytest.raises(ValidationError):
            TelemetryAuth(
                auth_type="oauth",  # type: ignore[arg-type]
                api_key=SecretStr("key"),
            )


# =============================================================================
# T035: Unit tests for BatchSpanProcessorConfig validation
# =============================================================================


class TestBatchSpanProcessorConfigValidation:
    """Test BatchSpanProcessorConfig Pydantic model validation.

    BatchSpanProcessor is used for async, non-blocking span export.
    Configuration includes queue sizes and timing parameters.

    Requirements: FR-008, FR-009, FR-010, FR-011, FR-024, FR-026
    """

    @pytest.mark.requirement("FR-008")
    def test_batch_processor_config_default_values(self) -> None:
        """Test BatchSpanProcessorConfig has sensible defaults."""
        config = BatchSpanProcessorConfig()

        # Default values per research.md for medium throughput
        assert config.max_queue_size == 2048
        assert config.max_export_batch_size == 512
        assert config.schedule_delay_millis == 5000
        assert config.export_timeout_millis == 30000

    @pytest.mark.requirement("FR-008")
    def test_batch_processor_config_custom_values(self) -> None:
        """Test BatchSpanProcessorConfig accepts custom values."""
        config = BatchSpanProcessorConfig(
            max_queue_size=4096,
            max_export_batch_size=1024,
            schedule_delay_millis=10000,
            export_timeout_millis=60000,
        )

        assert config.max_queue_size == 4096
        assert config.max_export_batch_size == 1024
        assert config.schedule_delay_millis == 10000
        assert config.export_timeout_millis == 60000

    @pytest.mark.requirement("FR-008")
    def test_batch_processor_config_low_throughput(self) -> None:
        """Test BatchSpanProcessorConfig for low throughput (<100/s)."""
        config = BatchSpanProcessorConfig(
            max_queue_size=512,
            max_export_batch_size=256,
            schedule_delay_millis=10000,
        )

        assert config.max_queue_size == 512
        assert config.max_export_batch_size == 256
        assert config.schedule_delay_millis == 10000

    @pytest.mark.requirement("FR-008")
    def test_batch_processor_config_high_throughput(self) -> None:
        """Test BatchSpanProcessorConfig for high throughput (>1000/s)."""
        config = BatchSpanProcessorConfig(
            max_queue_size=8192,
            max_export_batch_size=1024,
            schedule_delay_millis=2000,
        )

        assert config.max_queue_size == 8192
        assert config.max_export_batch_size == 1024
        assert config.schedule_delay_millis == 2000

    @pytest.mark.requirement("FR-024")
    def test_batch_processor_config_min_queue_size(self) -> None:
        """Test max_queue_size must be positive."""
        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(max_queue_size=0)

    @pytest.mark.requirement("FR-024")
    def test_batch_processor_config_min_batch_size(self) -> None:
        """Test max_export_batch_size must be positive."""
        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(max_export_batch_size=0)

    @pytest.mark.requirement("FR-024")
    def test_batch_processor_config_min_schedule_delay(self) -> None:
        """Test schedule_delay_millis must be positive."""
        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(schedule_delay_millis=0)

    @pytest.mark.requirement("FR-024")
    def test_batch_processor_config_min_export_timeout(self) -> None:
        """Test export_timeout_millis must be positive."""
        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(export_timeout_millis=0)

    @pytest.mark.requirement("FR-024")
    def test_batch_processor_config_batch_size_le_queue_size(self) -> None:
        """Test max_export_batch_size cannot exceed max_queue_size."""
        with pytest.raises(
            ValidationError, match="max_export_batch_size.*cannot exceed.*max_queue_size"
        ):
            BatchSpanProcessorConfig(
                max_queue_size=256,
                max_export_batch_size=512,  # Batch larger than queue
            )

    @pytest.mark.requirement("FR-008")
    def test_batch_processor_config_is_frozen(self) -> None:
        """Test BatchSpanProcessorConfig is immutable (frozen=True)."""
        config = BatchSpanProcessorConfig()

        with pytest.raises(ValidationError):
            config.max_queue_size = 1024  # type: ignore[misc]

    @pytest.mark.requirement("FR-008")
    def test_batch_processor_config_forbids_extra_fields(self) -> None:
        """Test BatchSpanProcessorConfig rejects unknown fields."""
        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(
                unknown_field=123,  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-008")
    def test_batch_processor_config_negative_values_rejected(self) -> None:
        """Test negative values are rejected for all fields."""
        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(max_queue_size=-100)

        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(max_export_batch_size=-50)

        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(schedule_delay_millis=-1000)

        with pytest.raises(ValidationError):
            BatchSpanProcessorConfig(export_timeout_millis=-5000)


# =============================================================================
# T038: Unit tests for TelemetryAuth header injection
# =============================================================================


class TestTelemetryAuthHeaderInjection:
    """Test TelemetryAuth header generation for OTLP exports.

    TelemetryAuth generates HTTP headers for authenticating with SaaS
    telemetry backends like Datadog, Grafana Cloud, and others.

    Requirements: FR-001, FR-012, FR-013
    """

    @pytest.mark.requirement("FR-012")
    def test_api_key_header_generation(self) -> None:
        """Test api_key auth generates correct header name and value."""
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("dd-api-key-12345"),
            header_name="DD-API-KEY",
        )

        # Header name should be as specified
        assert auth.header_name == "DD-API-KEY"
        # API key should be retrievable for header value
        assert auth.api_key is not None
        assert auth.api_key.get_secret_value() == "dd-api-key-12345"

    @pytest.mark.requirement("FR-012")
    def test_bearer_token_header_generation(self) -> None:
        """Test bearer auth generates Authorization header with Bearer prefix."""
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("grafana-cloud-token-xyz"),
        )

        # Default header name for bearer is "Authorization"
        assert auth.header_name == "Authorization"
        # Bearer token should be retrievable for header value
        assert auth.bearer_token is not None
        assert auth.bearer_token.get_secret_value() == "grafana-cloud-token-xyz"

    @pytest.mark.requirement("FR-012")
    def test_bearer_token_custom_header_name(self) -> None:
        """Test bearer auth can use custom header name."""
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("custom-token"),
            header_name="X-Custom-Auth",
        )

        assert auth.header_name == "X-Custom-Auth"
        assert auth.bearer_token is not None
        assert auth.bearer_token.get_secret_value() == "custom-token"

    @pytest.mark.requirement("FR-012")
    def test_datadog_api_key_header(self) -> None:
        """Test Datadog-style DD-API-KEY header configuration."""
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("datadog-api-key"),
            header_name="DD-API-KEY",
        )

        assert auth.auth_type == "api_key"
        assert auth.header_name == "DD-API-KEY"
        assert auth.api_key is not None

    @pytest.mark.requirement("FR-012")
    def test_grafana_cloud_bearer_header(self) -> None:
        """Test Grafana Cloud-style bearer token configuration."""
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("grafana-cloud-api-token"),
            header_name="Authorization",
        )

        assert auth.auth_type == "bearer"
        assert auth.header_name == "Authorization"
        assert auth.bearer_token is not None

    @pytest.mark.requirement("FR-013")
    def test_api_key_secret_is_hidden_in_repr(self) -> None:
        """Test api_key is hidden when TelemetryAuth is printed/logged."""
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("super-secret-key"),
            header_name="X-API-KEY",
        )

        # SecretStr should mask the value in string representation
        auth_str = str(auth)
        assert "super-secret-key" not in auth_str
        # SecretStr displays as '**********'
        assert "**********" in auth_str

    @pytest.mark.requirement("FR-013")
    def test_bearer_token_secret_is_hidden_in_repr(self) -> None:
        """Test bearer_token is hidden when TelemetryAuth is printed/logged."""
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("super-secret-token"),
        )

        # SecretStr should mask the value in string representation
        auth_str = str(auth)
        assert "super-secret-token" not in auth_str
        assert "**********" in auth_str

    @pytest.mark.requirement("FR-012")
    def test_api_key_can_be_used_in_headers_dict(self) -> None:
        """Test api_key can be extracted for use in HTTP headers dict."""
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("my-api-key"),
            header_name="X-API-KEY",
        )

        # Simulate building headers dict for OTLP exporter
        headers: dict[str, str] = {}
        if auth.api_key is not None:
            headers[auth.header_name] = auth.api_key.get_secret_value()

        assert headers == {"X-API-KEY": "my-api-key"}

    @pytest.mark.requirement("FR-012")
    def test_bearer_token_can_be_used_in_headers_dict(self) -> None:
        """Test bearer_token can be extracted for use in HTTP headers dict."""
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("my-bearer-token"),
        )

        # Simulate building headers dict for OTLP exporter
        # Bearer auth typically requires "Bearer " prefix
        headers: dict[str, str] = {}
        if auth.bearer_token is not None:
            headers[auth.header_name] = f"Bearer {auth.bearer_token.get_secret_value()}"

        assert headers == {"Authorization": "Bearer my-bearer-token"}

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_with_api_key_auth(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig accepts TelemetryAuth with api_key."""
        auth = TelemetryAuth(
            auth_type="api_key",
            api_key=SecretStr("config-api-key"),
            header_name="DD-API-KEY",
        )
        config = TelemetryConfig(
            resource_attributes=sample_resource_attributes,
            otlp_endpoint="http://localhost:4317",
            authentication=auth,
        )

        assert config.authentication is not None
        assert config.authentication.auth_type == "api_key"
        assert config.authentication.header_name == "DD-API-KEY"

    @pytest.mark.requirement("FR-001")
    def test_telemetry_config_with_bearer_auth(
        self,
        sample_resource_attributes: ResourceAttributes,
    ) -> None:
        """Test TelemetryConfig accepts TelemetryAuth with bearer token."""
        auth = TelemetryAuth(
            auth_type="bearer",
            bearer_token=SecretStr("config-bearer-token"),
        )
        config = TelemetryConfig(
            resource_attributes=sample_resource_attributes,
            otlp_endpoint="http://localhost:4317",
            authentication=auth,
        )

        assert config.authentication is not None
        assert config.authentication.auth_type == "bearer"
        assert config.authentication.bearer_token is not None
