"""Unit tests for Floe span attributes (semantic conventions).

Tests cover:
- T026: FloeSpanAttributes.to_otel_dict() functionality

Requirements Covered:
- FR-007: floe.namespace attribute on ALL spans
- FR-007b: floe.product.name attribute
- FR-007c: floe.product.version attribute
- FR-007d: floe.mode attribute
- FR-019: OpenTelemetry semantic conventions
- FR-020: Resource attributes
"""

from __future__ import annotations

import pytest

from floe_core.telemetry.conventions import (
    FLOE_DAGSTER_ASSET,
    FLOE_DBT_MODEL,
    FLOE_JOB_TYPE,
    FLOE_MODE,
    FLOE_NAMESPACE,
    FLOE_PIPELINE_ID,
    FLOE_PRODUCT_NAME,
    FLOE_PRODUCT_VERSION,
    FloeSpanAttributes,
)


class TestFloeSpanAttributesToOtelDict:
    """Tests for FloeSpanAttributes.to_otel_dict() (T026).

    The to_otel_dict() method should:
    - Include all mandatory attributes
    - Include optional attributes when set
    - Exclude optional attributes when None
    - Use correct 'floe.*' prefixed keys
    """

    @pytest.mark.requirement("FR-007")
    def test_to_otel_dict_includes_mandatory_attributes(self) -> None:
        """Test that to_otel_dict includes all mandatory attributes."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
        )

        result = attrs.to_otel_dict()

        assert result["floe.namespace"] == "analytics"
        assert result["floe.product.name"] == "customer-360"
        assert result["floe.product.version"] == "1.0.0"
        assert result["floe.mode"] == "prod"

    @pytest.mark.requirement("FR-007")
    def test_to_otel_dict_uses_semantic_convention_keys(self) -> None:
        """Test that to_otel_dict uses the correct semantic convention keys."""
        attrs = FloeSpanAttributes(
            namespace="test",
            product_name="test-product",
            product_version="0.1.0",
            mode="dev",
        )

        result = attrs.to_otel_dict()

        # Verify keys match the defined constants
        assert FLOE_NAMESPACE in result
        assert FLOE_PRODUCT_NAME in result
        assert FLOE_PRODUCT_VERSION in result
        assert FLOE_MODE in result

    @pytest.mark.requirement("FR-019")
    def test_to_otel_dict_excludes_none_optionals(self) -> None:
        """Test that to_otel_dict excludes None optional attributes."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
            # All optionals default to None
        )

        result = attrs.to_otel_dict()

        # Should only have 4 mandatory keys
        assert len(result) == 4
        assert "floe.pipeline.id" not in result
        assert "floe.job.type" not in result
        assert "floe.dbt.model" not in result
        assert "floe.dagster.asset" not in result

    @pytest.mark.requirement("FR-019")
    def test_to_otel_dict_includes_pipeline_id(self) -> None:
        """Test that to_otel_dict includes pipeline_id when set."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
            pipeline_id="run-12345",
        )

        result = attrs.to_otel_dict()

        assert result[FLOE_PIPELINE_ID] == "run-12345"
        assert len(result) == 5

    @pytest.mark.requirement("FR-019")
    def test_to_otel_dict_includes_job_type(self) -> None:
        """Test that to_otel_dict includes job_type when set."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
            job_type="dbt_run",
        )

        result = attrs.to_otel_dict()

        assert result[FLOE_JOB_TYPE] == "dbt_run"
        assert len(result) == 5

    @pytest.mark.requirement("FR-019")
    def test_to_otel_dict_includes_model_name(self) -> None:
        """Test that to_otel_dict includes model_name when set."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
            model_name="stg_customers",
        )

        result = attrs.to_otel_dict()

        assert result[FLOE_DBT_MODEL] == "stg_customers"
        assert len(result) == 5

    @pytest.mark.requirement("FR-019")
    def test_to_otel_dict_includes_asset_key(self) -> None:
        """Test that to_otel_dict includes asset_key when set."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
            asset_key="customers/raw_orders",
        )

        result = attrs.to_otel_dict()

        assert result[FLOE_DAGSTER_ASSET] == "customers/raw_orders"
        assert len(result) == 5

    @pytest.mark.requirement("FR-019")
    def test_to_otel_dict_includes_all_optionals(self) -> None:
        """Test that to_otel_dict includes all optional attributes when set."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="2.1.0",
            mode="prod",
            pipeline_id="run-12345",
            job_type="dbt_run",
            model_name="stg_customers",
            asset_key="customers/stg_customers",
        )

        result = attrs.to_otel_dict()

        # All 8 attributes should be present
        assert len(result) == 8
        assert result["floe.namespace"] == "analytics"
        assert result["floe.product.name"] == "customer-360"
        assert result["floe.product.version"] == "2.1.0"
        assert result["floe.mode"] == "prod"
        assert result["floe.pipeline.id"] == "run-12345"
        assert result["floe.job.type"] == "dbt_run"
        assert result["floe.dbt.model"] == "stg_customers"
        assert result["floe.dagster.asset"] == "customers/stg_customers"

    @pytest.mark.requirement("FR-007")
    def test_to_otel_dict_returns_dict_of_strings(self) -> None:
        """Test that to_otel_dict returns dict[str, str]."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="dev",
        )

        result = attrs.to_otel_dict()

        # All keys should be strings
        assert all(isinstance(k, str) for k in result.keys())
        # All values should be strings
        assert all(isinstance(v, str) for v in result.values())


class TestFloeSpanAttributesValidation:
    """Tests for FloeSpanAttributes validation."""

    @pytest.mark.requirement("FR-007")
    def test_namespace_is_required(self) -> None:
        """Test that namespace is a required field."""
        with pytest.raises(ValueError):
            FloeSpanAttributes(
                product_name="customer-360",
                product_version="1.0.0",
                mode="prod",
            )  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-007")
    def test_namespace_cannot_be_empty(self) -> None:
        """Test that namespace cannot be an empty string."""
        with pytest.raises(ValueError, match="String should have at least 1 character"):
            FloeSpanAttributes(
                namespace="",
                product_name="customer-360",
                product_version="1.0.0",
                mode="prod",
            )

    @pytest.mark.requirement("FR-007")
    def test_namespace_max_length(self) -> None:
        """Test that namespace has a maximum length of 128 characters."""
        long_namespace = "a" * 129
        with pytest.raises(ValueError, match="String should have at most 128 characters"):
            FloeSpanAttributes(
                namespace=long_namespace,
                product_name="customer-360",
                product_version="1.0.0",
                mode="prod",
            )

    @pytest.mark.requirement("FR-007b")
    def test_product_name_is_required(self) -> None:
        """Test that product_name is a required field."""
        with pytest.raises(ValueError):
            FloeSpanAttributes(
                namespace="analytics",
                product_version="1.0.0",
                mode="prod",
            )  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-007c")
    def test_product_version_is_required(self) -> None:
        """Test that product_version is a required field."""
        with pytest.raises(ValueError):
            FloeSpanAttributes(
                namespace="analytics",
                product_name="customer-360",
                mode="prod",
            )  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-007d")
    def test_mode_is_required(self) -> None:
        """Test that mode is a required field."""
        with pytest.raises(ValueError):
            FloeSpanAttributes(
                namespace="analytics",
                product_name="customer-360",
                product_version="1.0.0",
            )  # type: ignore[call-arg]

    @pytest.mark.requirement("FR-007d")
    def test_mode_must_be_valid_literal(self) -> None:
        """Test that mode must be dev, staging, or prod."""
        with pytest.raises(ValueError, match="Input should be 'dev', 'staging' or 'prod'"):
            FloeSpanAttributes(
                namespace="analytics",
                product_name="customer-360",
                product_version="1.0.0",
                mode="invalid",  # type: ignore[arg-type]
            )

    @pytest.mark.requirement("FR-007d")
    def test_mode_accepts_dev(self) -> None:
        """Test that mode accepts 'dev'."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="dev",
        )
        assert attrs.mode == "dev"

    @pytest.mark.requirement("FR-007d")
    def test_mode_accepts_staging(self) -> None:
        """Test that mode accepts 'staging'."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="staging",
        )
        assert attrs.mode == "staging"

    @pytest.mark.requirement("FR-007d")
    def test_mode_accepts_prod(self) -> None:
        """Test that mode accepts 'prod'."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
        )
        assert attrs.mode == "prod"


class TestFloeSpanAttributesImmutability:
    """Tests for FloeSpanAttributes immutability (frozen model)."""

    @pytest.mark.requirement("FR-019")
    def test_attributes_are_frozen(self) -> None:
        """Test that FloeSpanAttributes is immutable (frozen)."""
        attrs = FloeSpanAttributes(
            namespace="analytics",
            product_name="customer-360",
            product_version="1.0.0",
            mode="prod",
        )

        with pytest.raises(ValueError, match="Instance is frozen"):
            attrs.namespace = "new-namespace"  # type: ignore[misc]

    @pytest.mark.requirement("FR-019")
    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are not allowed."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            FloeSpanAttributes(
                namespace="analytics",
                product_name="customer-360",
                product_version="1.0.0",
                mode="prod",
                extra_field="not_allowed",  # type: ignore[call-arg]
            )


class TestSemanticConventionConstants:
    """Tests for semantic convention constants."""

    @pytest.mark.requirement("FR-019")
    def test_constant_values(self) -> None:
        """Test that constants have correct values."""
        assert FLOE_NAMESPACE == "floe.namespace"
        assert FLOE_PRODUCT_NAME == "floe.product.name"
        assert FLOE_PRODUCT_VERSION == "floe.product.version"
        assert FLOE_MODE == "floe.mode"
        assert FLOE_PIPELINE_ID == "floe.pipeline.id"
        assert FLOE_JOB_TYPE == "floe.job.type"
        assert FLOE_DBT_MODEL == "floe.dbt.model"
        assert FLOE_DAGSTER_ASSET == "floe.dagster.asset"

    @pytest.mark.requirement("FR-019")
    def test_constants_match_to_otel_dict_keys(self) -> None:
        """Test that constants match the keys returned by to_otel_dict."""
        attrs = FloeSpanAttributes(
            namespace="test",
            product_name="test",
            product_version="1.0.0",
            mode="dev",
            pipeline_id="run-1",
            job_type="dbt_run",
            model_name="model_a",
            asset_key="asset/a",
        )

        result = attrs.to_otel_dict()

        # All constants should be keys in the result
        assert FLOE_NAMESPACE in result
        assert FLOE_PRODUCT_NAME in result
        assert FLOE_PRODUCT_VERSION in result
        assert FLOE_MODE in result
        assert FLOE_PIPELINE_ID in result
        assert FLOE_JOB_TYPE in result
        assert FLOE_DBT_MODEL in result
        assert FLOE_DAGSTER_ASSET in result
