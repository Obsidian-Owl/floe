"""MinIO Storage Plugin for floe.

This package provides the MinIOStoragePlugin implementation for
MinIO object storage.

Example:
    >>> from floe_core.plugins import get_plugin
    >>> storage = get_plugin("storage", "minio")
    >>> uri = storage.get_warehouse_uri("bronze")

Public API:
    - MinIOStoragePlugin: Main plugin class (implements StoragePlugin ABC)
    - MinIOStorageConfig: Configuration model for MinIO connection
"""

from __future__ import annotations

__version__ = "0.1.0"

from floe_storage_minio.config import MinIOStorageConfig
from floe_storage_minio.plugin import MinIOStoragePlugin

__all__ = [
    "MinIOStorageConfig",
    "MinIOStoragePlugin",
]
