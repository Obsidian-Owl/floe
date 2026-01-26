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
# The official Fusion CLI is installed as 'dbt' (with 'dbtf' alias)
STANDARD_FUSION_PATHS: list[Path] = [
    Path.home() / ".local/bin/dbt",  # Official install location
    Path("/usr/local/bin/dbt"),
    Path("/opt/dbt-fusion/bin/dbt"),
    # Legacy dbt-sa-cli paths (development builds)
    Path.home() / ".cargo/bin/dbt-sa-cli",
    Path("/usr/local/bin/dbt-sa-cli"),
]

# Binary names to search for (in priority order)
# Official Fusion uses 'dbt', development builds use 'dbt-sa-cli'
FUSION_BINARY_NAMES: list[str] = ["dbt", "dbtf", "dbt-sa-cli"]

# Default binary name for Fusion CLI (official release)
DEFAULT_BINARY_NAME = "dbt"

# Adapters with Rust implementations in dbt Fusion (official CLI)
# As of dbt-fusion 2.0.0-preview, supported adapters are:
# redshift, snowflake, postgres, bigquery, trino, datafusion, spark, databricks, salesforce
# Note: DuckDB is NOT supported in official Fusion CLI (only in dbt-sa-cli standalone analyzer)
SUPPORTED_RUST_ADAPTERS: list[str] = [
    "snowflake",
    "postgres",
    "bigquery",
    "redshift",
    "trino",
    "datafusion",
    "spark",
    "databricks",
    "salesforce",
]

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


def detect_fusion_binary(binary_name: str | None = None) -> Path | None:
    """Detect Fusion CLI binary in PATH or standard installation paths.

    Searches for the Fusion CLI binary in the following order:
    1. Check standard installation paths FIRST (official CLI locations)
    2. Then check system PATH for known Fusion binary names
    3. Only returns binaries that support the 'compile' command

    The official Fusion CLI (dbt/dbtf) supports: compile, run, test, build.
    The standalone analyzer (dbt-sa-cli) only supports: parse, deps, list.
    We need the official CLI for full dbt functionality.

    Args:
        binary_name: Specific binary name to search for. If None, searches
            for all known Fusion binary names in priority order.

    Returns:
        Path to the Fusion CLI binary if found, None otherwise.

    Requirements:
        FR-020: Detect Fusion CLI binary

    Example:
        >>> binary_path = detect_fusion_binary()
        >>> if binary_path:
        ...     print(f"Found Fusion at {binary_path}")
    """
    # Check standard paths FIRST (prefer official install locations)
    for standard_path in STANDARD_FUSION_PATHS:
        if standard_path.exists() and standard_path.is_file():
            if _is_full_fusion_cli(standard_path):
                return standard_path

    # Determine which binary names to search for
    names_to_check = [binary_name] if binary_name else FUSION_BINARY_NAMES

    # Then check PATH for each binary name
    for name in names_to_check:
        path_result = shutil.which(name)
        if path_result:
            # Verify it's the full Fusion CLI (not dbt-core or standalone analyzer)
            if _is_full_fusion_cli(Path(path_result)):
                return Path(path_result)

    return None


def _is_full_fusion_cli(binary_path: Path) -> bool:
    """Check if a binary is the FULL Fusion CLI with compile/run/test support.

    The official Fusion CLI (dbt/dbtf from dbt Labs CDN) supports:
    - compile, run, test, build (full dbt commands)

    The standalone analyzer (dbt-sa-cli from source) only supports:
    - parse, deps, list (limited commands)

    This function uses a single subprocess call to check both:
    1. Whether it identifies as Fusion (contains "fusion" or "dbt-sa-cli")
    2. Whether 'compile' command is available in help output

    Args:
        binary_path: Path to the binary to check.

    Returns:
        True if the binary is the full Fusion CLI, False otherwise.
    """
    try:
        # Single subprocess call to check both identity and capabilities
        result = subprocess.run(
            [str(binary_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        help_output = result.stdout.lower()

        # Must identify as Fusion (not dbt-core which outputs 'core')
        is_fusion = "fusion" in help_output or "dbt-sa-cli" in help_output

        # Must have compile command (full CLI, not standalone analyzer)
        has_compile = "compile" in help_output

        return is_fusion and has_compile
    except (subprocess.TimeoutExpired, OSError):
        return False


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

        # Parse version from output like:
        # - "dbt-fusion 2.0.0-preview.101"
        # - "dbt-sa-cli 0.1.0"
        # - "dbt-sa-cli version 0.1.0"
        output = result.stdout.strip()

        # Security: Limit input length to prevent ReDoS attacks (version output is short)
        if len(output) > 256:
            return None

        # Use explicit quantifier limits to prevent polynomial backtracking
        # Pattern: semver with optional prerelease suffix (e.g., 2.0.0-preview.101)
        version_match = re.search(
            r"(\d{1,10}\.\d{1,10}\.\d{1,10}(?:-[\w.]{1,30})?)",
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
    "FUSION_BINARY_NAMES",
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
