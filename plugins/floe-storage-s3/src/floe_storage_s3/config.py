"""Configuration model for the S3 Storage Plugin.

This module provides the Pydantic configuration model for connecting to
S3-compatible object storage (AWS S3, MinIO, etc.).

Models:
    S3StorageConfig: S3 storage connection and credential settings

Example:
    >>> from floe_storage_s3.config import S3StorageConfig
    >>> config = S3StorageConfig(
    ...     endpoint="http://minio:9000",
    ...     bucket="floe-data",
    ... )
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class S3StorageConfig(BaseModel):
    """S3-compatible storage configuration.

    Configures connection to S3 or S3-compatible storage (MinIO, etc.).
    Credentials can be provided directly or sourced from environment
    variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).

    Attributes:
        endpoint: S3 endpoint URL (e.g., http://minio:9000).
        bucket: S3 bucket name for data storage.
        region: AWS region (default: us-east-1).
        path_style_access: Use path-style access (required for MinIO).
        access_key_id: Optional S3 access key (falls back to AWS_ACCESS_KEY_ID env).
        secret_access_key: Optional S3 secret key (falls back to AWS_SECRET_ACCESS_KEY env).

    Example:
        >>> config = S3StorageConfig(
        ...     endpoint="http://floe-platform-minio:9000",
        ...     bucket="floe-data",
        ...     region="us-east-1",
        ...     path_style_access=True,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    endpoint: str = Field(
        ...,
        description="S3 endpoint URL",
        min_length=1,
        examples=["http://floe-platform-minio:9000", "https://s3.amazonaws.com"],
    )
    bucket: str = Field(
        ...,
        description="S3 bucket name for data storage",
        min_length=1,
        examples=["floe-data", "my-warehouse"],
    )
    region: str = Field(
        default="us-east-1",
        description="AWS region",
        min_length=1,
    )
    path_style_access: bool = Field(
        default=True,
        description="Use path-style access (required for MinIO, LocalStack)",
    )
    access_key_id: SecretStr | None = Field(
        default=None,
        description="S3 access key ID (falls back to AWS_ACCESS_KEY_ID env var)",
    )
    secret_access_key: SecretStr | None = Field(
        default=None,
        description="S3 secret access key (falls back to AWS_SECRET_ACCESS_KEY env var)",
    )
