"""Quality configuration validation functions.

This module provides compile-time validation for quality configuration,
including provider validation and column reference checking.

Implements:
    - FR-041: FLOE-DQ001 for missing or invalid quality provider
    - FR-045: FLOE-DQ105 for invalid column references
"""

from __future__ import annotations

from floe_core.quality_errors import QualityProviderNotFoundError
from floe_core.schemas.plugins import PLUGIN_REGISTRY


def get_available_quality_providers() -> list[str]:
    """Get the list of available quality providers.

    Returns:
        List of available provider names from the plugin registry.
    """
    return list(PLUGIN_REGISTRY.get("quality", []))


def validate_quality_provider(provider: str) -> None:
    """Validate that a quality provider is valid and available.

    Args:
        provider: The provider name to validate.

    Raises:
        QualityProviderNotFoundError: If provider is not in the registry (FLOE-DQ001).
    """
    available = get_available_quality_providers()
    if provider not in available:
        raise QualityProviderNotFoundError(provider, available)


__all__ = [
    "get_available_quality_providers",
    "validate_quality_provider",
]
