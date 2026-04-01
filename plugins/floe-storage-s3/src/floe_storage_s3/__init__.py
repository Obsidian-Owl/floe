"""S3 Storage Plugin for floe.

This package provides the S3StoragePlugin implementation for
S3-compatible object storage (AWS S3, MinIO, etc.).

Example:
    >>> from floe_core.plugins import get_plugin
    >>> storage = get_plugin("storage", "s3")
    >>> uri = storage.get_warehouse_uri("bronze")

Public API:
    - S3StoragePlugin: Main plugin class (implements StoragePlugin ABC)
    - S3StorageConfig: Configuration model for S3 connection
"""

from __future__ import annotations

__version__ = "0.1.0"

from floe_storage_s3.config import S3StorageConfig
from floe_storage_s3.plugin import S3StoragePlugin

__all__ = [
    "__version__",
    "S3StorageConfig",
    "S3StoragePlugin",
]
