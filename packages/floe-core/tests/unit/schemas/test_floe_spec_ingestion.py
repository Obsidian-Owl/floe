"""Unit tests for product-level ingestion schema in FloeSpec."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from floe_core.schemas.floe_spec import FloeSpec


def test_ingestion_specs_are_exported_from_public_schema_api() -> None:
    """Product ingestion models are available from floe_core.schemas."""
    from floe_core.schemas import IngestionSourceSpec, ProductIngestionSpec

    assert IngestionSourceSpec.__name__ == "IngestionSourceSpec"
    assert ProductIngestionSpec.__name__ == "ProductIngestionSpec"


def _base_floe_spec(**overrides: Any) -> dict[str, Any]:
    """Build a minimal FloeSpec payload with optional overrides."""
    data: dict[str, Any] = {
        "apiVersion": "floe.dev/v1",
        "kind": "FloeSpec",
        "metadata": {"name": "customer-ingestion", "version": "1.0.0"},
        "transforms": [{"name": "stg_customers"}],
    }
    data.update(overrides)
    return data


def test_floe_spec_accepts_filesystem_ingestion_sources() -> None:
    """FloeSpec accepts data-engineer-owned filesystem ingestion sources."""
    spec = FloeSpec.model_validate(
        _base_floe_spec(
            ingestion={
                "sources": [
                    {
                        "name": "raw-customers",
                        "sourceType": "filesystem",
                        "format": "csv",
                        "path": "./data/customers.csv",
                        "destinationTable": "bronze.raw_customers",
                        "writeMode": "replace",
                        "schemaContract": "evolve",
                    }
                ]
            }
        )
    )

    assert spec.ingestion is not None
    source = spec.ingestion.sources[0]
    assert source.name == "raw-customers"
    assert source.source_type == "filesystem"
    assert source.format == "csv"
    assert source.path == "./data/customers.csv"
    assert source.destination_table == "bronze.raw_customers"
    assert source.write_mode == "replace"
    assert source.schema_contract == "evolve"


@pytest.mark.parametrize(
    "path",
    [
        "./data/customers.csv",
        "s3://bucket/key.csv",
        "s3://bucket/key.csv?versionId=123",
    ],
)
def test_floe_spec_accepts_valid_ingestion_paths(path: str) -> None:
    """Ingestion paths support relative files and object-store URIs."""
    spec = FloeSpec.model_validate(
        _base_floe_spec(
            ingestion={
                "sources": [
                    {
                        "name": "raw-customers",
                        "sourceType": "filesystem",
                        "format": "csv",
                        "path": path,
                        "destinationTable": "bronze.raw_customers",
                    }
                ]
            }
        )
    )

    assert spec.ingestion is not None
    assert spec.ingestion.sources[0].path == path


@pytest.mark.parametrize(
    "path",
    [
        "https://bucket/key.csv",
        "/data/customers.csv",
        "s3:///key.csv",
    ],
)
def test_floe_spec_rejects_invalid_ingestion_paths(path: str) -> None:
    """Ingestion paths reject unsupported schemes, absolute paths, and missing buckets."""
    with pytest.raises(ValidationError):
        FloeSpec.model_validate(
            _base_floe_spec(
                ingestion={
                    "sources": [
                        {
                            "name": "raw-customers",
                            "sourceType": "filesystem",
                            "format": "csv",
                            "path": path,
                            "destinationTable": "bronze.raw_customers",
                        }
                    ]
                }
            )
        )


def test_floe_spec_rejects_duplicate_ingestion_source_names() -> None:
    """Ingestion source names must be unique within a product."""
    with pytest.raises(ValidationError) as exc_info:
        FloeSpec.model_validate(
            _base_floe_spec(
                ingestion={
                    "sources": [
                        {
                            "name": "raw-customers",
                            "sourceType": "filesystem",
                            "format": "csv",
                            "path": "./data/customers.csv",
                            "destinationTable": "bronze.raw_customers",
                        },
                        {
                            "name": "raw-customers",
                            "sourceType": "filesystem",
                            "format": "jsonl",
                            "path": "./data/customers.jsonl",
                            "destinationTable": "bronze.raw_customers_json",
                        },
                    ]
                }
            )
        )

    assert "duplicate" in str(exc_info.value).lower()
    assert "raw-customers" in str(exc_info.value)


def test_floe_spec_rejects_environment_specific_ingestion_fields() -> None:
    """Ingestion sources must not contain environment-specific fields."""
    with pytest.raises(ValidationError) as exc_info:
        FloeSpec.model_validate(
            _base_floe_spec(
                ingestion={
                    "sources": [
                        {
                            "name": "raw-customers",
                            "sourceType": "filesystem",
                            "format": "csv",
                            "path": "./data/customers.csv",
                            "destinationTable": "bronze.raw_customers",
                            "endpoint": "https://storage.example.com",
                        }
                    ]
                }
            )
        )

    assert "endpoint" in str(exc_info.value)
    assert "Environment-specific fields" in str(exc_info.value)


def test_floe_spec_rejects_merge_without_primary_key() -> None:
    """Merge write mode requires a primary key."""
    with pytest.raises(ValidationError) as exc_info:
        FloeSpec.model_validate(
            _base_floe_spec(
                ingestion={
                    "sources": [
                        {
                            "name": "raw-customers",
                            "sourceType": "filesystem",
                            "format": "csv",
                            "path": "./data/customers.csv",
                            "destinationTable": "bronze.raw_customers",
                            "writeMode": "merge",
                        }
                    ]
                }
            )
        )

    assert "primary" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "path",
    [
        "s3://bucket/key?AWSAccessKeyId=abc&Signature=def",
        "s3://bucket/key#token=abc",
    ],
)
def test_floe_spec_rejects_credential_bearing_ingestion_path_parts(path: str) -> None:
    """Object-store paths must not embed credentials in query or fragment parts."""
    with pytest.raises(ValidationError) as exc_info:
        FloeSpec.model_validate(
            _base_floe_spec(
                ingestion={
                    "sources": [
                        {
                            "name": "raw-customers",
                            "sourceType": "filesystem",
                            "format": "csv",
                            "path": path,
                            "destinationTable": "bronze.raw_customers",
                        }
                    ]
                }
            )
        )

    assert "credential" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "path",
    [
        "./data/customers.csv?AWSAccessKeyId=abc&Signature=def",
        "./data/customers.csv#token=abc",
    ],
)
def test_floe_spec_rejects_relative_paths_with_credential_bearing_parts(path: str) -> None:
    """Relative ingestion paths must not embed credentials in query or fragment parts."""
    with pytest.raises(ValidationError) as exc_info:
        FloeSpec.model_validate(
            _base_floe_spec(
                ingestion={
                    "sources": [
                        {
                            "name": "raw-customers",
                            "sourceType": "filesystem",
                            "format": "csv",
                            "path": path,
                            "destinationTable": "bronze.raw_customers",
                        }
                    ]
                }
            )
        )

    assert "credential" in str(exc_info.value).lower()


@pytest.mark.parametrize(
    "primary_key",
    [
        "",
        "   ",
        [],
        [""],
        ["id", ""],
        ["id", "   "],
    ],
)
def test_floe_spec_rejects_merge_with_empty_primary_key_values(
    primary_key: str | list[str],
) -> None:
    """Merge primary keys must contain one or more non-empty field names."""
    with pytest.raises(ValidationError) as exc_info:
        FloeSpec.model_validate(
            _base_floe_spec(
                ingestion={
                    "sources": [
                        {
                            "name": "raw-customers",
                            "sourceType": "filesystem",
                            "format": "csv",
                            "path": "./data/customers.csv",
                            "destinationTable": "bronze.raw_customers",
                            "writeMode": "merge",
                            "primaryKey": primary_key,
                        }
                    ]
                }
            )
        )

    assert "primary" in str(exc_info.value).lower()
