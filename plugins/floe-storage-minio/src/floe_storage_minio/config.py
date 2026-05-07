"""Configuration model for the MinIO Storage Plugin.

This module provides the Pydantic configuration model for connecting to
MinIO object storage using S3-compatible protocol settings.

Models:
    MinIOStorageConfig: MinIO storage connection and credential settings

Example:
    >>> from floe_storage_minio.config import MinIOStorageConfig
    >>> config = MinIOStorageConfig(
    ...     endpoint="http://minio:9000",
    ...     bucket="floe-data",
    ... )
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class MinIOStorageConfig(BaseModel):
    """MinIO storage configuration.

    Configures connection to MinIO object storage.
    Credentials can be provided directly or sourced from environment
    variables (MINIO_ACCESS_KEY_ID/MINIO_SECRET_ACCESS_KEY, then AWS_* fallback).

    Attributes:
        endpoint: MinIO endpoint URL (e.g., http://minio:9000).
        bucket: Bucket name for data storage.
        region: S3-compatible region (default: us-east-1).
        path_style_access: Use path-style access (required for MinIO).
        access_key_id: Optional access key (falls back to MINIO_ACCESS_KEY_ID,
            then AWS_ACCESS_KEY_ID env).
        secret_access_key: Optional secret key (falls back to MINIO_SECRET_ACCESS_KEY,
            then AWS_SECRET_ACCESS_KEY env).

    Example:
        >>> config = MinIOStorageConfig(
        ...     endpoint="http://floe-platform-minio:9000",
        ...     bucket="floe-data",
        ...     region="us-east-1",
        ...     path_style_access=True,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    endpoint: str = Field(
        ...,
        description="MinIO endpoint URL",
        min_length=1,
        pattern=r"^https?://",
        examples=["http://floe-platform-minio:9000", "https://s3.amazonaws.com"],
    )
    bucket: str = Field(
        ...,
        description="Bucket name for data storage",
        min_length=1,
        examples=["floe-data", "my-warehouse"],
    )
    region: str = Field(
        default="us-east-1",
        description="S3-compatible region",
        min_length=1,
    )
    path_style_access: bool = Field(
        default=True,
        description="Use path-style access (required for MinIO, LocalStack)",
    )
    artifact_bucket: str = Field(
        default="floe-artifacts",
        description="Bucket for platform artifacts and run outputs.",
        min_length=1,
    )
    credential_secret_name: str = Field(
        default="floe-platform-minio-credentials",
        description="Kubernetes Secret name holding MinIO credentials.",
        min_length=1,
    )
    credential_secret_namespace: str = Field(
        default="floe-system",
        description="Kubernetes namespace containing the MinIO credential Secret.",
        min_length=1,
    )
    access_key_secret_key: str = Field(
        default="root-user",
        description="Secret key containing the MinIO access key.",
        min_length=1,
    )
    secret_key_secret_key: str = Field(
        default="root-password",
        description="Secret key containing the MinIO secret key.",
        min_length=1,
    )
    external_endpoint: str | None = Field(
        default=None,
        description="Optional endpoint for local tools or users outside the cluster.",
    )
    access_key_id: SecretStr | None = Field(
        default=None,
        description=("Access key ID (falls back to MINIO_ACCESS_KEY_ID, then AWS_ACCESS_KEY_ID)"),
    )
    secret_access_key: SecretStr | None = Field(
        default=None,
        description=(
            "Secret access key (falls back to MINIO_SECRET_ACCESS_KEY, then AWS_SECRET_ACCESS_KEY)"
        ),
    )
