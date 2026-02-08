"""Unit tests for DltIngestionConfig validation (T020).

Tests for DltIngestionConfig, IngestionSourceConfig, and RetryConfig
Pydantic model validation rules. These tests validate the config models
that are already implemented.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from floe_ingestion_dlt.config import (
    VALID_SCHEMA_CONTRACTS,
    VALID_SOURCE_TYPES,
    DltIngestionConfig,
    IngestionSourceConfig,
    RetryConfig,
)


class TestDltIngestionConfig:
    """Unit tests for DltIngestionConfig validation."""

    @pytest.mark.requirement("4F-FR-067")
    def test_config_frozen(self) -> None:
        """Test DltIngestionConfig is frozen (immutable).

        Creating a config then trying to set config.sources = []
        raises ValidationError or AttributeError.
        """
        config = DltIngestionConfig(
            sources=[
                IngestionSourceConfig(
                    name="test_source",
                    source_type="rest_api",
                    source_config={"url": "https://api.example.com"},
                    destination_table="bronze.raw_data",
                )
            ]
        )

        with pytest.raises((ValidationError, AttributeError)):
            config.sources = []

    @pytest.mark.requirement("4F-FR-067")
    def test_config_extra_forbid(self) -> None:
        """Test DltIngestionConfig rejects extra fields.

        DltIngestionConfig with extra field like unknown_field="x"
        raises ValidationError.
        """
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DltIngestionConfig(
                sources=[
                    IngestionSourceConfig(
                        name="test_source",
                        source_type="rest_api",
                        source_config={"url": "https://api.example.com"},
                        destination_table="bronze.raw_data",
                    )
                ],
                unknown_field="x",  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("4F-FR-068")
    def test_empty_sources_rejected(self) -> None:
        """Test DltIngestionConfig rejects empty sources list.

        DltIngestionConfig with sources=[] raises ValidationError
        (min_length=1 constraint).
        """
        with pytest.raises(ValidationError, match="List should have at least 1 item"):
            DltIngestionConfig(sources=[])

    @pytest.mark.requirement("4F-FR-068")
    def test_valid_config_accepts_single_source(self) -> None:
        """Test DltIngestionConfig accepts single valid source.

        A config with one valid source succeeds without errors.
        """
        config = DltIngestionConfig(
            sources=[
                IngestionSourceConfig(
                    name="single_source",
                    source_type="rest_api",
                    source_config={"url": "https://api.example.com"},
                    destination_table="bronze.raw_data",
                )
            ]
        )
        assert len(config.sources) == 1
        assert config.sources[0].name == "single_source"

    @pytest.mark.requirement("4F-FR-068")
    def test_valid_config_accepts_multiple_sources(self) -> None:
        """Test DltIngestionConfig accepts multiple valid sources.

        A config with multiple valid sources succeeds without errors.
        """
        config = DltIngestionConfig(
            sources=[
                IngestionSourceConfig(
                    name="source_one",
                    source_type="rest_api",
                    source_config={"url": "https://api1.example.com"},
                    destination_table="bronze.data_one",
                ),
                IngestionSourceConfig(
                    name="source_two",
                    source_type="sql_database",
                    source_config={"connection_string": "postgresql://localhost/db"},
                    destination_table="bronze.data_two",
                ),
            ]
        )
        assert len(config.sources) == 2
        assert config.sources[0].name == "source_one"
        assert config.sources[1].name == "source_two"

    @pytest.mark.requirement("4F-FR-068")
    def test_duplicate_source_names_rejected(self) -> None:
        """Test DltIngestionConfig rejects duplicate source names.

        Two sources with same name raises ValidationError due to
        unique name constraint.
        """
        with pytest.raises(ValidationError, match="Duplicate source names found"):
            DltIngestionConfig(
                sources=[
                    IngestionSourceConfig(
                        name="duplicate",
                        source_type="rest_api",
                        source_config={"url": "https://api1.example.com"},
                        destination_table="bronze.data_one",
                    ),
                    IngestionSourceConfig(
                        name="duplicate",  # Duplicate name
                        source_type="sql_database",
                        source_config={
                            "connection_string": "postgresql://localhost/db"
                        },
                        destination_table="bronze.data_two",
                    ),
                ]
            )


class TestIngestionSourceConfig:
    """Unit tests for IngestionSourceConfig validation."""

    @pytest.mark.requirement("4F-FR-069")
    def test_source_type_validation(self) -> None:
        """Test IngestionSourceConfig validates source_type.

        Valid: rest_api, sql_database, filesystem.
        Invalid: "invalid" raises ValidationError.
        """
        # Valid source types
        for source_type in VALID_SOURCE_TYPES:
            config = IngestionSourceConfig(
                name=f"test_{source_type}",
                source_type=source_type,
                source_config={"dummy": "config"},
                destination_table="bronze.test",
            )
            assert config.source_type == source_type

        # Invalid source type
        with pytest.raises(ValidationError, match="source_type must be one of"):
            IngestionSourceConfig(
                name="test_invalid",
                source_type="invalid",
                source_config={"dummy": "config"},
                destination_table="bronze.test",
            )

    @pytest.mark.requirement("4F-FR-069")
    def test_write_mode_validation(self) -> None:
        """Test IngestionSourceConfig validates write_mode.

        Valid: append, replace, merge (but merge requires primary_key).
        Invalid: "upsert" raises ValidationError.
        """
        # Valid write modes (append and replace)
        for write_mode in ["append", "replace"]:
            config = IngestionSourceConfig(
                name=f"test_{write_mode}",
                source_type="rest_api",
                source_config={"dummy": "config"},
                destination_table="bronze.test",
                write_mode=write_mode,
            )
            assert config.write_mode == write_mode

        # Valid write mode (merge with primary_key)
        config = IngestionSourceConfig(
            name="test_merge",
            source_type="rest_api",
            source_config={"dummy": "config"},
            destination_table="bronze.test",
            write_mode="merge",
            primary_key="id",
        )
        assert config.write_mode == "merge"

        # Invalid write mode
        with pytest.raises(ValidationError, match="write_mode must be one of"):
            IngestionSourceConfig(
                name="test_invalid",
                source_type="rest_api",
                source_config={"dummy": "config"},
                destination_table="bronze.test",
                write_mode="upsert",
            )

    @pytest.mark.requirement("4F-FR-069")
    def test_schema_contract_validation(self) -> None:
        """Test IngestionSourceConfig validates schema_contract.

        Valid: evolve, freeze, discard_value.
        Invalid: "strict" raises ValidationError.
        """
        # Valid schema contracts
        for schema_contract in VALID_SCHEMA_CONTRACTS:
            config = IngestionSourceConfig(
                name=f"test_{schema_contract}",
                source_type="rest_api",
                source_config={"dummy": "config"},
                destination_table="bronze.test",
                schema_contract=schema_contract,
            )
            assert config.schema_contract == schema_contract

        # Invalid schema contract
        with pytest.raises(ValidationError, match="schema_contract must be one of"):
            IngestionSourceConfig(
                name="test_invalid",
                source_type="rest_api",
                source_config={"dummy": "config"},
                destination_table="bronze.test",
                schema_contract="strict",
            )

    @pytest.mark.requirement("4F-FR-069")
    def test_merge_requires_primary_key(self) -> None:
        """Test write_mode=merge requires primary_key.

        write_mode="merge" without primary_key raises ValidationError.
        """
        with pytest.raises(
            ValidationError,
            match="primary_key is required when write_mode is 'merge'",
        ):
            IngestionSourceConfig(
                name="test_merge",
                source_type="rest_api",
                source_config={"dummy": "config"},
                destination_table="bronze.test",
                write_mode="merge",
                # Missing primary_key
            )

    @pytest.mark.requirement("4F-FR-069")
    def test_merge_with_primary_key_succeeds(self) -> None:
        """Test write_mode=merge with primary_key succeeds.

        write_mode="merge" with primary_key="id" succeeds without error.
        """
        config = IngestionSourceConfig(
            name="test_merge",
            source_type="rest_api",
            source_config={"dummy": "config"},
            destination_table="bronze.test",
            write_mode="merge",
            primary_key="id",
        )
        assert config.write_mode == "merge"
        assert config.primary_key == "id"

    @pytest.mark.requirement("4F-FR-069")
    def test_name_validation_alphanumeric(self) -> None:
        """Test IngestionSourceConfig validates name format.

        name="valid_name" passes, name="invalid@name" raises ValidationError.
        Name must be alphanumeric with underscores and hyphens.
        The validator checks that after removing underscores and hyphens,
        the remaining characters are alphanumeric.
        """
        # Valid names (alphanumeric with underscores/hyphens allowed)
        valid_names = [
            "valid_name",
            "ValidName123",
            "source_1",
            "mySource",
            "name-with-dash",
            "123invalid",
        ]
        for name in valid_names:
            config = IngestionSourceConfig(
                name=name,
                source_type="rest_api",
                source_config={"dummy": "config"},
                destination_table="bronze.test",
            )
            assert config.name == name

        # Invalid names (contain characters other than alphanumeric, underscore, hyphen)
        invalid_names = [
            "invalid@name",
            "name with space",
            "name.with.dots",
            "name$special",
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError, match="contains invalid characters"):
                IngestionSourceConfig(
                    name=name,
                    source_type="rest_api",
                    source_config={"dummy": "config"},
                    destination_table="bronze.test",
                )

    @pytest.mark.requirement("4F-FR-069")
    def test_source_frozen(self) -> None:
        """Test IngestionSourceConfig is frozen (immutable).

        IngestionSourceConfig is frozen — setting attributes after
        creation raises ValidationError or AttributeError.
        """
        config = IngestionSourceConfig(
            name="test_source",
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="bronze.raw_data",
        )

        with pytest.raises((ValidationError, AttributeError)):
            config.name = "new_name"

    @pytest.mark.requirement("4F-FR-073")
    def test_credentials_secret_str(self) -> None:
        """Test credentials field accepts SecretStr and masks in repr.

        credentials field accepts SecretStr and masks value in repr/str.
        """
        secret_creds = SecretStr("super_secret_password")
        config = IngestionSourceConfig(
            name="test_source",
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="bronze.raw_data",
            credentials=secret_creds,
        )

        assert config.credentials is not None
        # Verify it's masked in repr
        repr_str = repr(config)
        assert "super_secret_password" not in repr_str
        assert "**********" in repr_str or "SecretStr" in repr_str


class TestRetryConfig:
    """Unit tests for RetryConfig validation."""

    @pytest.mark.requirement("4F-FR-071")
    def test_retry_config_defaults(self) -> None:
        """Test RetryConfig default values.

        Default max_retries=3, initial_delay_seconds=1.0.
        """
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay_seconds == pytest.approx(1.0)

    @pytest.mark.requirement("4F-FR-071")
    def test_retry_config_frozen(self) -> None:
        """Test RetryConfig is frozen (immutable).

        RetryConfig is frozen — setting attributes after creation
        raises ValidationError or AttributeError.
        """
        config = RetryConfig()

        with pytest.raises((ValidationError, AttributeError)):
            config.max_retries = 5

    @pytest.mark.requirement("4F-FR-071")
    def test_retry_config_bounds(self) -> None:
        """Test RetryConfig validates bounds.

        max_retries must be 0-10, initial_delay_seconds must be >0 and <=60.
        """
        # Valid bounds
        config = RetryConfig(max_retries=0, initial_delay_seconds=0.1)
        assert config.max_retries == 0
        assert config.initial_delay_seconds == pytest.approx(0.1)

        config = RetryConfig(max_retries=10, initial_delay_seconds=60.0)
        assert config.max_retries == 10
        assert config.initial_delay_seconds == pytest.approx(60.0)

        # Invalid max_retries (too high)
        with pytest.raises(
            ValidationError, match="Input should be less than or equal to 10"
        ):
            RetryConfig(max_retries=11)

        # Invalid max_retries (negative)
        with pytest.raises(
            ValidationError, match="Input should be greater than or equal to 0"
        ):
            RetryConfig(max_retries=-1)

        # Invalid initial_delay_seconds (too high)
        with pytest.raises(
            ValidationError, match="Input should be less than or equal to 60"
        ):
            RetryConfig(initial_delay_seconds=61.0)

        # Invalid initial_delay_seconds (zero)
        with pytest.raises(ValidationError, match="Input should be greater than 0"):
            RetryConfig(initial_delay_seconds=0.0)

        # Invalid initial_delay_seconds (negative)
        with pytest.raises(ValidationError, match="Input should be greater than 0"):
            RetryConfig(initial_delay_seconds=-1.0)
