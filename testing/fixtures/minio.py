"""MinIO/S3 pytest fixture for integration tests.

Provides MinIO S3-compatible storage fixture for tests running in Kind cluster.

Example:
    from testing.fixtures.minio import minio_client_context

    def test_with_s3(minio_client):
        minio_client.put_object(
            "test-bucket",
            "test-key",
            io.BytesIO(b"test data"),
            length=9,
        )
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Generator

from pydantic import BaseModel, ConfigDict, Field, SecretStr

if TYPE_CHECKING:
    from minio import Minio


class MinIOConfig(BaseModel):
    """Configuration for MinIO/S3 connection.

    Attributes:
        endpoint: MinIO endpoint URL or host:port.
        access_key: AWS access key ID.
        secret_key: AWS secret access key (SecretStr for security).
        secure: Use HTTPS (default False for local testing).
        region: AWS region (default us-east-1).
        namespace: K8s namespace where MinIO runs.
    """

    model_config = ConfigDict(frozen=True)

    endpoint: str = Field(
        default_factory=lambda: os.environ.get("MINIO_ENDPOINT", "minio:9000")
    )
    access_key: str = Field(
        default_factory=lambda: os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
    )
    secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(
            os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin")
        )
    )
    secure: bool = Field(default=False)
    region: str = Field(
        default_factory=lambda: os.environ.get("AWS_REGION", "us-east-1")
    )
    namespace: str = Field(default="floe-test")

    @property
    def k8s_endpoint(self) -> str:
        """Get K8s DNS endpoint for MinIO service."""
        # Extract host from endpoint (remove port if present)
        host = self.endpoint.split(":")[0]
        port = self.endpoint.split(":")[1] if ":" in self.endpoint else "9000"
        return f"{host}.{self.namespace}.svc.cluster.local:{port}"


class MinIOConnectionError(Exception):
    """Raised when MinIO connection fails."""

    pass


def create_minio_client(config: MinIOConfig) -> "Minio":
    """Create MinIO client from config.

    Args:
        config: MinIO configuration.

    Returns:
        MinIO client instance.

    Raises:
        MinIOConnectionError: If client creation fails.
    """
    try:
        from minio import Minio
    except ImportError as e:
        raise MinIOConnectionError(
            "minio not installed. Install with: pip install minio"
        ) from e

    try:
        client = Minio(
            endpoint=config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key.get_secret_value(),
            secure=config.secure,
            region=config.region,
        )
        return client
    except Exception as e:
        raise MinIOConnectionError(
            f"Failed to create MinIO client for {config.endpoint}: {e}"
        ) from e


@contextmanager
def minio_client_context(
    config: MinIOConfig | None = None,
) -> Generator["Minio", None, None]:
    """Context manager for MinIO client.

    Creates client on entry, cleans up on exit (no explicit close needed).

    Args:
        config: Optional MinIOConfig. Uses defaults if not provided.

    Yields:
        MinIO client instance.

    Example:
        with minio_client_context() as client:
            client.list_buckets()
    """
    if config is None:
        config = MinIOConfig()

    client = create_minio_client(config)
    yield client
    # MinIO client doesn't need explicit close


def ensure_bucket(
    client: "Minio",
    bucket_name: str,
    region: str = "us-east-1",
) -> bool:
    """Ensure bucket exists, create if not.

    Args:
        client: MinIO client.
        bucket_name: Name of bucket to ensure.
        region: Region for bucket creation.

    Returns:
        True if bucket was created, False if already existed.
    """
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name, location=region)
        return True
    return False


def delete_bucket_contents(
    client: "Minio",
    bucket_name: str,
) -> int:
    """Delete all objects in a bucket.

    Args:
        client: MinIO client.
        bucket_name: Name of bucket to empty.

    Returns:
        Number of objects deleted.
    """
    from minio.deleteobjects import DeleteObject

    objects = client.list_objects(bucket_name, recursive=True)
    delete_objects = [DeleteObject(obj.object_name) for obj in objects]

    if delete_objects:
        errors = list(client.remove_objects(bucket_name, delete_objects))
        if errors:
            raise MinIOConnectionError(f"Failed to delete objects: {errors}")
        return len(delete_objects)
    return 0


def cleanup_bucket(
    client: "Minio",
    bucket_name: str,
) -> None:
    """Delete bucket and all its contents.

    Args:
        client: MinIO client.
        bucket_name: Name of bucket to delete.
    """
    if client.bucket_exists(bucket_name):
        delete_bucket_contents(client, bucket_name)
        client.remove_bucket(bucket_name)


def get_connection_info(config: MinIOConfig) -> dict[str, Any]:
    """Get connection info dictionary (for logging/debugging).

    Args:
        config: MinIO configuration.

    Returns:
        Dictionary with connection info (secret key masked).
    """
    return {
        "endpoint": config.endpoint,
        "access_key": config.access_key,
        "secure": config.secure,
        "region": config.region,
        "namespace": config.namespace,
        "k8s_endpoint": config.k8s_endpoint,
    }


__all__ = [
    "MinIOConfig",
    "MinIOConnectionError",
    "cleanup_bucket",
    "create_minio_client",
    "delete_bucket_contents",
    "ensure_bucket",
    "get_connection_info",
    "minio_client_context",
]
