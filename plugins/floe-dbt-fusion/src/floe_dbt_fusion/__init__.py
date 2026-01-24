"""floe-dbt-fusion: DBT plugin using dbt Fusion CLI.

This package provides DBTFusionPlugin, which wraps dbt Fusion's Rust-based
CLI for high-performance parallel execution.

Features:
- ~30x faster parsing than dbt-core for large projects
- Thread-safe (Rust memory safety)
- Automatic fallback to dbt-core when Rust adapters unavailable

Example:
    >>> from floe_dbt_fusion import detect_fusion
    >>> info = detect_fusion()
    >>> if info.available:
    ...     print(f"Fusion {info.version} at {info.binary_path}")
"""

from __future__ import annotations

from .detection import (
    DEFAULT_BINARY_NAME,
    STANDARD_FUSION_PATHS,
    SUPPORTED_RUST_ADAPTERS,
    FusionDetectionInfo,
    check_adapter_available,
    detect_fusion,
    detect_fusion_binary,
    get_available_adapters,
    get_fusion_version,
)
from .errors import (
    DBTAdapterUnavailableError,
    DBTFusionError,
    DBTFusionNotFoundError,
    check_fallback_available,
)

__all__ = [
    # Detection utilities
    "detect_fusion_binary",
    "get_fusion_version",
    "check_adapter_available",
    "get_available_adapters",
    "detect_fusion",
    "FusionDetectionInfo",
    "DEFAULT_BINARY_NAME",
    "STANDARD_FUSION_PATHS",
    "SUPPORTED_RUST_ADAPTERS",
    # Error classes
    "DBTFusionError",
    "DBTFusionNotFoundError",
    "DBTAdapterUnavailableError",
    "check_fallback_available",
]
