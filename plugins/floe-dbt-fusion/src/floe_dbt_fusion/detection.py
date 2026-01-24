"""Fusion binary detection and version parsing (FR-020, FR-021).

This module provides functions for detecting the dbt Fusion CLI binary,
parsing its version, and checking Rust adapter availability.

The Fusion CLI (dbt-sa-cli) is the Rust-based high-performance dbt runtime.
It supports a subset of adapters with Rust implementations.

Functions:
    detect_fusion_binary: Find the Fusion CLI binary in PATH or standard paths.
    get_fusion_version: Parse version from Fusion CLI output.
    check_adapter_available: Check if a Rust adapter is available.
    get_available_adapters: List all adapters with Rust implementations.
    detect_fusion: Get complete detection info (convenience function).

Example:
    >>> from floe_dbt_fusion.detection import detect_fusion
    >>> info = detect_fusion()
    >>> if info.available:
    ...     print(f"Fusion {info.version} at {info.binary_path}")
    ... else:
    ...     print("Fusion not installed")

Requirements:
    FR-020: Detect Fusion CLI binary
    FR-021: Check Rust adapter availability
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Standard installation paths to check for Fusion binary
STANDARD_FUSION_PATHS: list[Path] = [
    Path("/usr/local/bin/dbt-sa-cli"),
    Path("/opt/dbt-fusion/bin/dbt-sa-cli"),
    Path.home() / ".local/bin/dbt-sa-cli",
    Path.home() / ".dbt-fusion/bin/dbt-sa-cli",
]

# Default binary name for Fusion CLI
DEFAULT_BINARY_NAME = "dbt-sa-cli"

# Adapters with Rust implementations in dbt Fusion
SUPPORTED_RUST_ADAPTERS: list[str] = ["duckdb", "snowflake"]

# Minimum required Fusion CLI version (NFR-004)
MIN_FUSION_VERSION = "1.0.0"


@dataclass
class FusionDetectionInfo:
    """Information about detected Fusion installation.

    Attributes:
        available: Whether Fusion CLI is available on this system.
        binary_path: Path to the Fusion CLI binary, or None if not found.
        version: Parsed version string, or None if version check failed.
        adapters_available: List of adapters with Rust implementations.
    """

    available: bool
    binary_path: Path | None
    version: str | None
    adapters_available: list[str] = field(default_factory=list)


def detect_fusion_binary(binary_name: str = DEFAULT_BINARY_NAME) -> Path | None:
    """Detect Fusion CLI binary in PATH or standard installation paths.

    Searches for the Fusion CLI binary in the following order:
    1. System PATH (using shutil.which)
    2. Standard installation paths (STANDARD_FUSION_PATHS)

    Args:
        binary_name: Name of the binary to search for. Defaults to "dbt-sa-cli".

    Returns:
        Path to the Fusion CLI binary if found, None otherwise.

    Requirements:
        FR-020: Detect Fusion CLI binary

    Example:
        >>> binary_path = detect_fusion_binary()
        >>> if binary_path:
        ...     print(f"Found Fusion at {binary_path}")
    """
    # First check PATH
    path_result = shutil.which(binary_name)
    if path_result:
        return Path(path_result)

    # Then check standard paths
    for standard_path in STANDARD_FUSION_PATHS:
        if standard_path.exists() and standard_path.is_file():
            return standard_path

    return None


def get_fusion_version(binary_path: Path) -> str | None:
    """Parse version from Fusion CLI output.

    Runs the Fusion CLI with --version flag and parses the version
    string from the output.

    Args:
        binary_path: Path to the Fusion CLI binary.

    Returns:
        Version string (e.g., "0.1.0") if parsing succeeds, None otherwise.

    Requirements:
        FR-020: Parse Fusion version

    Example:
        >>> version = get_fusion_version(Path("/usr/local/bin/dbt-sa-cli"))
        >>> print(version)  # "0.1.0"
    """
    try:
        result = subprocess.run(
            [str(binary_path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            return None

        # Parse version from output like "dbt-sa-cli 0.1.0" or "dbt-sa-cli version 0.1.0"
        output = result.stdout.strip()

        # Security: Limit input length to prevent ReDoS attacks (version output is short)
        if len(output) > 256:
            return None

        # Use explicit quantifier limits to prevent polynomial backtracking
        # Pattern: optional "version ", then semver with optional prerelease suffix
        version_match = re.search(
            r"(?:version\s{1,10})?(\d{1,10}\.\d{1,10}\.\d{1,10}(?:-\w{1,20})?)",
            output,
        )
        if version_match:
            return version_match.group(1)

        return None

    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def check_adapter_available(adapter: str) -> bool:
    """Check if a Rust adapter is available for the specified database.

    Fusion only supports databases with Rust-native adapters. This function
    checks if the specified adapter has a Rust implementation.

    Supported adapters:
        - duckdb: DuckDB (duckdb-rs)
        - snowflake: Snowflake (snowflake-connector-rust)

    Unsupported adapters (require fallback to dbt-core):
        - bigquery
        - databricks
        - redshift
        - postgres

    Args:
        adapter: The adapter/database type (e.g., "duckdb", "snowflake").

    Returns:
        True if the adapter has a Rust implementation, False otherwise.

    Requirements:
        FR-021: Check Rust adapter availability

    Example:
        >>> check_adapter_available("duckdb")
        True
        >>> check_adapter_available("bigquery")
        False
    """
    return adapter.lower() in [a.lower() for a in SUPPORTED_RUST_ADAPTERS]


def get_available_adapters() -> list[str]:
    """Get list of adapters with Rust implementations.

    Returns:
        List of adapter names that Fusion supports.

    Requirements:
        FR-021: List available Rust adapters

    Example:
        >>> adapters = get_available_adapters()
        >>> print(adapters)  # ["duckdb", "snowflake"]
    """
    return list(SUPPORTED_RUST_ADAPTERS)


def detect_fusion() -> FusionDetectionInfo:
    """Detect Fusion installation and return complete info.

    Convenience function that combines binary detection, version parsing,
    and adapter availability into a single FusionDetectionInfo object.

    Returns:
        FusionDetectionInfo with detection results.

    Requirements:
        FR-020: Detect Fusion CLI
        FR-021: Check adapter availability

    Example:
        >>> info = detect_fusion()
        >>> if info.available:
        ...     print(f"Fusion {info.version} supports: {info.adapters_available}")
    """
    binary_path = detect_fusion_binary()

    if binary_path is None:
        return FusionDetectionInfo(
            available=False,
            binary_path=None,
            version=None,
            adapters_available=[],
        )

    version = get_fusion_version(binary_path)

    return FusionDetectionInfo(
        available=True,
        binary_path=binary_path,
        version=version,
        adapters_available=get_available_adapters(),
    )


__all__ = [
    "STANDARD_FUSION_PATHS",
    "DEFAULT_BINARY_NAME",
    "SUPPORTED_RUST_ADAPTERS",
    "MIN_FUSION_VERSION",
    "FusionDetectionInfo",
    "detect_fusion_binary",
    "get_fusion_version",
    "check_adapter_available",
    "get_available_adapters",
    "detect_fusion",
]
