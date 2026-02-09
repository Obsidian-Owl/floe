"""Unit tests for FloeSpec schema models.

Tests validation of FloeSpec (floe.yaml) configuration including:
- FloeMetadata with DNS-compatible names (C001)
- Semver version validation (C002)
- Environment-agnostic validation (C004, FR-014)
- TransformSpec and ScheduleSpec validation

Task: T022
Requirements: FR-003, FR-014
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from floe_core.schemas.floe_spec import (
    DBT_MODEL_NAME_PATTERN,
    FLOE_NAME_PATTERN,
    FORBIDDEN_ENVIRONMENT_FIELDS,
    SEMVER_PATTERN,
    FloeMetadata,
    FloeSpec,
    PlatformRef,
    ScheduleSpec,
    TransformSpec,
)


class TestFloeMetadata:
    """Tests for FloeMetadata validation rules."""

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_metadata_minimal(self) -> None:
        """Test that minimal valid metadata is accepted."""
        metadata = FloeMetadata(name="test", version="1.0.0")
        assert metadata.name == "test"
        assert metadata.version == "1.0.0"
        assert metadata.owner is None
        assert metadata.description is None

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_metadata_full(self) -> None:
        """Test that full valid metadata is accepted."""
        metadata = FloeMetadata(
            name="customer-analytics",
            version="2.1.3",
            owner="analytics-team@acme.com",
            description="Customer behavior analytics pipeline",
            labels={"domain": "analytics", "tier": "gold"},
        )
        assert metadata.name == "customer-analytics"
        assert metadata.version == "2.1.3"
        assert metadata.owner == "analytics-team@acme.com"
        assert metadata.description == "Customer behavior analytics pipeline"
        assert metadata.labels == {"domain": "analytics", "tier": "gold"}

    @pytest.mark.requirement("2B-C001")
    def test_name_dns_compatible_valid(self) -> None:
        """Test that DNS-compatible names are accepted (C001)."""
        valid_names = ["a", "test", "my-pipeline", "analytics123", "data-v2"]
        for name in valid_names:
            metadata = FloeMetadata(name=name, version="1.0.0")
            assert metadata.name == name

    @pytest.mark.requirement("2B-C001")
    def test_name_invalid_uppercase(self) -> None:
        """Test that uppercase names are rejected (C001)."""
        with pytest.raises(ValidationError) as exc_info:
            FloeMetadata(name="MyPipeline", version="1.0.0")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("2B-C001")
    def test_name_invalid_underscore(self) -> None:
        """Test that names with underscores are rejected (C001)."""
        with pytest.raises(ValidationError) as exc_info:
            FloeMetadata(name="my_pipeline", version="1.0.0")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("2B-C001")
    def test_name_invalid_starts_with_number(self) -> None:
        """Test that names starting with numbers are rejected (C001)."""
        with pytest.raises(ValidationError) as exc_info:
            FloeMetadata(name="123pipeline", version="1.0.0")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("2B-C001")
    def test_name_invalid_starts_with_hyphen(self) -> None:
        """Test that names starting with hyphen are rejected (C001)."""
        with pytest.raises(ValidationError) as exc_info:
            FloeMetadata(name="-pipeline", version="1.0.0")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("2B-C001")
    def test_name_too_long(self) -> None:
        """Test that names exceeding 63 characters are rejected."""
        long_name = "a" * 64
        with pytest.raises(ValidationError) as exc_info:
            FloeMetadata(name=long_name, version="1.0.0")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("2B-C002")
    def test_version_semver_valid(self) -> None:
        """Test that valid semver versions are accepted (C002)."""
        valid_versions = ["0.0.1", "1.0.0", "2.1.3", "10.20.30"]
        for version in valid_versions:
            metadata = FloeMetadata(name="test", version=version)
            assert metadata.version == version

    @pytest.mark.requirement("2B-C002")
    def test_version_invalid_not_semver(self) -> None:
        """Test that non-semver versions are rejected (C002)."""
        invalid_versions = ["1.0", "v1.0.0", "1.0.0-beta", "1.0.0.0"]
        for version in invalid_versions:
            with pytest.raises(ValidationError) as exc_info:
                FloeMetadata(name="test", version=version)
            assert "version" in str(exc_info.value)


class TestTransformSpec:
    """Tests for TransformSpec validation rules."""

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_transform_minimal(self) -> None:
        """Test that minimal valid transform is accepted."""
        transform = TransformSpec(name="stg_customers")
        assert transform.name == "stg_customers"
        assert transform.compute is None
        assert transform.tags is None
        assert transform.depends_on is None

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_transform_full(self) -> None:
        """Test that full valid transform is accepted."""
        transform = TransformSpec(
            name="fct_orders",
            compute="duckdb",
            tags=["fact", "orders"],
            dependsOn=["stg_orders", "stg_customers"],
        )
        assert transform.name == "fct_orders"
        assert transform.compute == "duckdb"
        assert transform.tags == ["fact", "orders"]
        assert transform.depends_on == ["stg_orders", "stg_customers"]

    @pytest.mark.requirement("2B-C005")
    def test_name_dbt_pattern_valid(self) -> None:
        """Test that dbt-compatible names are accepted (C005)."""
        valid_names = [
            "stg_customers",
            "fct_orders",
            "dim_products",
            "Model1",
            "_internal",
        ]
        for name in valid_names:
            transform = TransformSpec(name=name)
            assert transform.name == name

    @pytest.mark.requirement("2B-C005")
    def test_name_invalid_starts_with_number(self) -> None:
        """Test that names starting with numbers are rejected (C005)."""
        with pytest.raises(ValidationError) as exc_info:
            TransformSpec(name="123_model")
        assert "name" in str(exc_info.value)

    @pytest.mark.requirement("2B-C005")
    def test_name_invalid_hyphen(self) -> None:
        """Test that names with hyphens are rejected (C005)."""
        with pytest.raises(ValidationError) as exc_info:
            TransformSpec(name="my-model")
        assert "name" in str(exc_info.value)


class TestScheduleSpec:
    """Tests for ScheduleSpec validation rules."""

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_schedule_defaults(self) -> None:
        """Test that schedule with defaults is accepted."""
        schedule = ScheduleSpec()
        assert schedule.cron is None
        assert schedule.timezone == "UTC"
        assert schedule.enabled is True

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_schedule_full(self) -> None:
        """Test that full schedule configuration is accepted."""
        schedule = ScheduleSpec(
            cron="0 6 * * *",
            timezone="America/New_York",
            enabled=True,
        )
        assert schedule.cron == "0 6 * * *"
        assert schedule.timezone == "America/New_York"
        assert schedule.enabled is True


class TestPlatformRef:
    """Tests for PlatformRef validation rules."""

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_platform_ref_oci(self) -> None:
        """Test that OCI URI platform ref is accepted."""
        ref = PlatformRef(manifest="oci://registry.acme.com/manifests/platform:1.0")
        assert ref.manifest == "oci://registry.acme.com/manifests/platform:1.0"

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_platform_ref_local(self) -> None:
        """Test that local path platform ref is accepted."""
        ref = PlatformRef(manifest="./manifest.yaml")
        assert ref.manifest == "./manifest.yaml"

    @pytest.mark.requirement("2B-FR-003")
    def test_invalid_platform_ref_empty(self) -> None:
        """Test that empty platform ref is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PlatformRef(manifest="")
        assert "manifest" in str(exc_info.value)


class TestFloeSpec:
    """Tests for FloeSpec root model validation."""

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_floe_spec_minimal(self) -> None:
        """Test that minimal valid FloeSpec is accepted."""
        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(name="test", version="1.0.0"),
            transforms=[TransformSpec(name="stg_customers")],
        )
        assert spec.api_version == "floe.dev/v1"
        assert spec.kind == "FloeSpec"
        assert spec.metadata.name == "test"
        assert len(spec.transforms) == 1

    @pytest.mark.requirement("2B-FR-003")
    def test_valid_floe_spec_full(self) -> None:
        """Test that full valid FloeSpec is accepted."""
        spec = FloeSpec(
            apiVersion="floe.dev/v1",
            kind="FloeSpec",
            metadata=FloeMetadata(
                name="customer-analytics",
                version="1.0.0",
                owner="analytics@acme.com",
            ),
            platform=PlatformRef(manifest="./manifest.yaml"),
            transforms=[
                TransformSpec(name="stg_customers"),
                TransformSpec(name="fct_orders", dependsOn=["stg_customers"]),
            ],
            schedule=ScheduleSpec(cron="0 6 * * *"),
        )
        assert spec.metadata.name == "customer-analytics"
        assert spec.platform is not None
        assert spec.platform.manifest == "./manifest.yaml"
        assert len(spec.transforms) == 2
        assert spec.schedule is not None
        assert spec.schedule.cron == "0 6 * * *"

    @pytest.mark.requirement("2B-C003")
    def test_transforms_required(self) -> None:
        """Test that transforms must have at least one entry (C003)."""
        with pytest.raises(ValidationError) as exc_info:
            FloeSpec(
                apiVersion="floe.dev/v1",
                kind="FloeSpec",
                metadata=FloeMetadata(name="test", version="1.0.0"),
                transforms=[],
            )
        assert "transforms" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-014")
    def test_environment_fields_forbidden_top_level(self) -> None:
        """Test that environment-specific fields at top level are rejected (FR-014)."""
        data: dict[str, Any] = {
            "apiVersion": "floe.dev/v1",
            "kind": "FloeSpec",
            "metadata": {"name": "test", "version": "1.0.0"},
            "transforms": [{"name": "stg_customers"}],
            "database": "my_database",  # FORBIDDEN
        }
        with pytest.raises(ValidationError) as exc_info:
            FloeSpec.model_validate(data)
        assert "database" in str(exc_info.value)
        assert "FR-014" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-014")
    def test_environment_fields_forbidden_nested(self) -> None:
        """Test that environment-specific fields in nested dicts are rejected (FR-014)."""
        data: dict[str, Any] = {
            "apiVersion": "floe.dev/v1",
            "kind": "FloeSpec",
            "metadata": {"name": "test", "version": "1.0.0"},
            "transforms": [{"name": "stg_customers", "config": {"password": "secret"}}],
        }
        with pytest.raises(ValidationError) as exc_info:
            FloeSpec.model_validate(data)
        assert "password" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-014")
    def test_environment_fields_all_forbidden(self) -> None:
        """Test that all forbidden environment fields are rejected (FR-014)."""
        for field in FORBIDDEN_ENVIRONMENT_FIELDS:
            data: dict[str, Any] = {
                "apiVersion": "floe.dev/v1",
                "kind": "FloeSpec",
                "metadata": {"name": "test", "version": "1.0.0"},
                "transforms": [{"name": "stg_customers"}],
                field: "some_value",
            }
            with pytest.raises(ValidationError) as exc_info:
                FloeSpec.model_validate(data)
            assert field in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-003")
    def test_duplicate_transform_names_rejected(self) -> None:
        """Test that duplicate transform names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FloeSpec(
                apiVersion="floe.dev/v1",
                kind="FloeSpec",
                metadata=FloeMetadata(name="test", version="1.0.0"),
                transforms=[
                    TransformSpec(name="stg_customers"),
                    TransformSpec(name="stg_customers"),  # Duplicate
                ],
            )
        assert "duplicate" in str(exc_info.value).lower()

    @pytest.mark.requirement("2B-FR-003")
    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are rejected (extra='forbid')."""
        data: dict[str, Any] = {
            "apiVersion": "floe.dev/v1",
            "kind": "FloeSpec",
            "metadata": {"name": "test", "version": "1.0.0"},
            "transforms": [{"name": "stg_customers"}],
            "unknown_field": "value",  # Extra field
        }
        with pytest.raises(ValidationError) as exc_info:
            FloeSpec.model_validate(data)
        assert "unknown_field" in str(exc_info.value)


class TestPatternConstants:
    """Tests for pattern constant validation."""

    @pytest.mark.requirement("2B-C001")
    def test_floe_name_pattern_exists(self) -> None:
        """Test that FLOE_NAME_PATTERN is defined correctly."""
        import re

        assert FLOE_NAME_PATTERN == r"^[a-z][a-z0-9-]*$"
        # Should match DNS-compatible names
        assert re.match(FLOE_NAME_PATTERN, "test")
        assert re.match(FLOE_NAME_PATTERN, "my-pipeline")
        assert not re.match(FLOE_NAME_PATTERN, "MyPipeline")
        assert not re.match(FLOE_NAME_PATTERN, "123test")

    @pytest.mark.requirement("2B-C002")
    def test_semver_pattern_exists(self) -> None:
        """Test that SEMVER_PATTERN is defined correctly."""
        import re

        assert SEMVER_PATTERN == r"^\d+\.\d+\.\d+$"
        assert re.match(SEMVER_PATTERN, "1.0.0")
        assert re.match(SEMVER_PATTERN, "10.20.30")
        assert not re.match(SEMVER_PATTERN, "1.0")
        assert not re.match(SEMVER_PATTERN, "v1.0.0")

    @pytest.mark.requirement("2B-C005")
    def test_dbt_model_name_pattern_exists(self) -> None:
        """Test that DBT_MODEL_NAME_PATTERN is defined correctly."""
        import re

        assert DBT_MODEL_NAME_PATTERN == r"^[a-zA-Z_][a-zA-Z0-9_]*$"
        assert re.match(DBT_MODEL_NAME_PATTERN, "stg_customers")
        assert re.match(DBT_MODEL_NAME_PATTERN, "_internal")
        assert not re.match(DBT_MODEL_NAME_PATTERN, "123_model")
        assert not re.match(DBT_MODEL_NAME_PATTERN, "my-model")
