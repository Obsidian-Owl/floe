"""TDD unit tests for Epic 4G US3: Destinations field on FloeSpec.

These tests are written BEFORE implementation as part of Test-Driven Development.
They will fail until DestinationConfig and FloeSpec.destinations are implemented.

Epic: 4G - Reverse ETL Plugin
User Story: US3 - Destinations field on FloeSpec
Tasks: T023 (DestinationConfig model), T024 (FloeSpec.destinations field)
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from floe_core.schemas.floe_spec import (
    DestinationConfig,
    FloeMetadata,
    FloeSpec,
    TransformSpec,
)


@pytest.fixture
def minimal_floe_spec_data() -> dict[str, Any]:
    """Minimal valid FloeSpec data for testing."""
    return {
        "apiVersion": "floe.dev/v1",
        "kind": "FloeSpec",
        "metadata": {"name": "test-product", "version": "1.0.0"},
        "transforms": [{"name": "stg_test"}],
    }


@pytest.fixture
def valid_destination_data() -> dict[str, Any]:
    """Valid DestinationConfig data."""
    return {
        "name": "crm-sync",
        "sink_type": "rest_api",
        "connection_secret_ref": "crm-api-key",
    }


class TestDestinationConfig:
    """Unit tests for DestinationConfig Pydantic model (T023)."""

    @pytest.mark.requirement("4G-FR-011")
    def test_destination_config_with_required_fields(
        self, valid_destination_data: dict[str, Any]
    ) -> None:
        """Test DestinationConfig creation with only required fields.

        Validates that DestinationConfig accepts minimal valid input
        with name, sink_type, and connection_secret_ref.
        """
        destination = DestinationConfig(**valid_destination_data)

        assert destination.name == "crm-sync"
        assert destination.sink_type == "rest_api"
        assert destination.connection_secret_ref == "crm-api-key"
        assert destination.source_table is None
        assert destination.config is None
        assert destination.field_mapping is None
        assert destination.batch_size is None

    @pytest.mark.requirement("4G-FR-011")
    def test_destination_config_with_all_fields(self) -> None:
        """Test DestinationConfig creation with all optional fields.

        Validates that DestinationConfig accepts all fields including
        source_table, config, field_mapping, and batch_size.
        """
        destination = DestinationConfig(
            name="salesforce-sync",
            sink_type="salesforce",
            connection_secret_ref="sf-credentials",
            source_table="gold.customers",
            config={"object_type": "Contact", "operation": "upsert"},
            field_mapping={"email": "Email", "name": "Name"},
            batch_size=100,
        )

        assert destination.name == "salesforce-sync"
        assert destination.sink_type == "salesforce"
        assert destination.connection_secret_ref == "sf-credentials"
        assert destination.source_table == "gold.customers"
        assert destination.config == {
            "object_type": "Contact",
            "operation": "upsert",
        }
        assert destination.field_mapping == {"email": "Email", "name": "Name"}
        assert destination.batch_size == 100

    @pytest.mark.requirement("4G-FR-011")
    def test_destination_config_rejects_extra_fields(
        self, valid_destination_data: dict[str, Any]
    ) -> None:
        """Test DestinationConfig rejects extra fields.

        Validates that extra='forbid' is enforced on DestinationConfig.
        """
        invalid_data = {**valid_destination_data, "unknown_field": "value"}

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DestinationConfig(**invalid_data)

    @pytest.mark.requirement("4G-FR-011")
    def test_destination_config_rejects_empty_name(
        self, valid_destination_data: dict[str, Any]
    ) -> None:
        """Test DestinationConfig rejects empty name.

        Validates that name field has min_length=1 constraint.
        """
        invalid_data = {**valid_destination_data, "name": ""}

        with pytest.raises(
            ValidationError, match="String should have at least 1 character"
        ):
            DestinationConfig(**invalid_data)

    @pytest.mark.requirement("4G-FR-018")
    def test_destination_config_validates_secret_ref_pattern(
        self, valid_destination_data: dict[str, Any]
    ) -> None:
        """Test DestinationConfig validates connection_secret_ref pattern.

        Validates that connection_secret_ref must match SECRET_NAME_PATTERN
        (K8s secret naming convention).
        """
        invalid_data = {
            **valid_destination_data,
            "connection_secret_ref": "INVALID!!ref",
        }

        with pytest.raises(ValidationError, match="String should match pattern"):
            DestinationConfig(**invalid_data)

    @pytest.mark.requirement("4G-FR-018")
    def test_destination_config_rejects_hardcoded_credentials(
        self, minimal_floe_spec_data: dict[str, Any]
    ) -> None:
        """Test FloeSpec rejects hardcoded credentials in destination config.

        Validates that FloeSpec's validate_no_environment_fields catches
        forbidden keys like 'password' in destination config dicts.
        """
        spec_data = {
            **minimal_floe_spec_data,
            "destinations": [
                {
                    "name": "crm-sync",
                    "sink_type": "rest_api",
                    "connection_secret_ref": "crm-api-key",
                    "config": {
                        "password": "secret123",
                    },
                }
            ],
        }

        with pytest.raises(ValidationError, match="password"):
            FloeSpec(**spec_data)

    @pytest.mark.requirement("4G-FR-011")
    def test_destination_config_batch_size_ge_1(
        self, valid_destination_data: dict[str, Any]
    ) -> None:
        """Test DestinationConfig rejects batch_size less than 1.

        Validates that batch_size field has ge=1 constraint.
        """
        invalid_data = {**valid_destination_data, "batch_size": 0}

        with pytest.raises(
            ValidationError, match="Input should be greater than or equal to 1"
        ):
            DestinationConfig(**invalid_data)


class TestFloeSpecDestinations:
    """Unit tests for FloeSpec.destinations field (T024)."""

    @pytest.mark.requirement("4G-FR-012")
    def test_floe_spec_with_destinations_validates(
        self,
        minimal_floe_spec_data: dict[str, Any],
        valid_destination_data: dict[str, Any],
    ) -> None:
        """Test FloeSpec accepts valid destinations list.

        Validates that FloeSpec can be created with a destinations field
        containing a list of valid DestinationConfig objects.
        """
        spec_data = {**minimal_floe_spec_data, "destinations": [valid_destination_data]}

        spec = FloeSpec(**spec_data)

        assert spec.destinations is not None
        assert len(spec.destinations) == 1
        assert spec.destinations[0].name == "crm-sync"

    @pytest.mark.requirement("4G-FR-012")
    def test_floe_spec_without_destinations_validates(
        self, minimal_floe_spec_data: dict[str, Any]
    ) -> None:
        """Test FloeSpec validates without destinations field.

        Validates backwards compatibility - destinations is optional.
        """
        spec = FloeSpec(**minimal_floe_spec_data)

        assert spec.destinations is None

    @pytest.mark.requirement("4G-FR-012")
    def test_floe_spec_with_multiple_destinations(
        self,
        minimal_floe_spec_data: dict[str, Any],
        valid_destination_data: dict[str, Any],
    ) -> None:
        """Test FloeSpec accepts multiple destinations.

        Validates that FloeSpec can contain a list of multiple destinations.
        """
        spec_data = {
            **minimal_floe_spec_data,
            "destinations": [
                valid_destination_data,
                {
                    "name": "hubspot-sync",
                    "sink_type": "hubspot",
                    "connection_secret_ref": "hubspot-api-key",
                },
            ],
        }

        spec = FloeSpec(**spec_data)

        assert spec.destinations is not None
        assert len(spec.destinations) == 2
        assert spec.destinations[0].name == "crm-sync"
        assert spec.destinations[1].name == "hubspot-sync"

    @pytest.mark.requirement("4G-FR-012")
    def test_floe_spec_rejects_duplicate_destination_names(
        self,
        minimal_floe_spec_data: dict[str, Any],
        valid_destination_data: dict[str, Any],
    ) -> None:
        """Test FloeSpec rejects duplicate destination names.

        Validates that FloeSpec enforces unique destination names
        within the destinations list.
        """
        spec_data = {
            **minimal_floe_spec_data,
            "destinations": [
                valid_destination_data,
                {
                    "name": "crm-sync",  # Duplicate name
                    "sink_type": "different_sink",
                    "connection_secret_ref": "other-secret",
                },
            ],
        }

        with pytest.raises(ValidationError, match="[Dd]uplicate.*destination.*name"):
            FloeSpec(**spec_data)
