"""Version compatibility utilities for floe plugin system.

This module provides version constants and compatibility checking
for plugins to ensure API compatibility between plugins and the
floe platform.

Version Format:
    Versions follow semver MAJOR.MINOR format (e.g., "1.0", "2.1").
    PATCH versions are not used for API compatibility.

Compatibility Rules:
    - Major versions must match exactly
    - Plugin minor version must be <= platform minor version

Example:
    >>> from floe_core.version_compat import is_compatible, FLOE_PLUGIN_API_VERSION
    >>> is_compatible("1.0", FLOE_PLUGIN_API_VERSION)
    True
    >>> is_compatible("2.0", "1.0")  # Major version mismatch
    False
"""

from __future__ import annotations

# Current floe plugin API version
# This is the version of the plugin API that this platform provides.
# Plugins declare which API version they require.
# Note: 0.x versions indicate unstable API (pre-1.0 release)
FLOE_PLUGIN_API_VERSION: str = "0.1"

# Minimum supported plugin API version for backward compatibility
# Plugins requiring versions below this are not supported.
FLOE_PLUGIN_API_MIN_VERSION: str = "0.1"


def is_compatible(plugin_api_version: str, platform_api_version: str) -> bool:
    """Check if a plugin API version is compatible with the platform.

    Determines whether a plugin requiring `plugin_api_version` can run
    on a platform providing `platform_api_version`.

    Args:
        plugin_api_version: The API version required by the plugin (X.Y format).
        platform_api_version: The API version provided by the platform (X.Y format).

    Returns:
        True if the plugin is compatible with the platform, False otherwise.

    Compatibility Rules:
        - Major version must match exactly (breaking changes)
        - Plugin minor version must be <= platform minor version
          (platform can provide newer features, plugin can use older features)

    Examples:
        >>> is_compatible("1.0", "1.0")  # Exact match
        True
        >>> is_compatible("1.0", "1.2")  # Platform has newer minor
        True
        >>> is_compatible("1.2", "1.0")  # Plugin needs newer minor
        False
        >>> is_compatible("2.0", "1.0")  # Major version mismatch
        False

    Raises:
        ValueError: If version strings are not in valid X.Y format.
    """
    plugin_major, plugin_minor = _parse_version(plugin_api_version)
    platform_major, platform_minor = _parse_version(platform_api_version)

    # Major versions must match exactly
    if plugin_major != platform_major:
        return False

    # Plugin minor version must be <= platform minor version
    return plugin_minor <= platform_minor


def _parse_version(version: str) -> tuple[int, int]:
    """Parse a version string into major and minor components.

    Args:
        version: Version string in X.Y format (e.g., "1.0", "2.1").

    Returns:
        Tuple of (major, minor) version numbers as integers.

    Raises:
        ValueError: If version string is not in valid X.Y format.

    Examples:
        >>> _parse_version("1.0")
        (1, 0)
        >>> _parse_version("2.10")
        (2, 10)
    """
    try:
        parts = version.split(".")
        if len(parts) != 2:
            raise ValueError(f"Invalid version format: {version!r}. Expected X.Y format.")
        major = int(parts[0])
        minor = int(parts[1])
        return major, minor
    except (ValueError, IndexError) as e:
        raise ValueError(
            f"Invalid version format: {version!r}. Expected X.Y format (e.g., '1.0')."
        ) from e
