"""Quality configuration validation functions.

This module provides compile-time validation for quality configuration,
including provider validation and column reference checking.

Implements:
    - FR-041: FLOE-DQ001 for missing or invalid quality provider
    - FR-045: FLOE-DQ105 for invalid column references
"""

from __future__ import annotations

from floe_core.quality_errors import (
    QualityColumnReferenceError,
    QualityProviderNotFoundError,
)
from floe_core.schemas.plugins import PLUGIN_REGISTRY
from floe_core.schemas.quality_score import QualityCheck


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


def validate_check_column_references(
    model_name: str,
    checks: list[QualityCheck],
    available_columns: list[str] | None = None,
) -> None:
    """Validate that quality checks reference existing columns.

    Args:
        model_name: The model being validated.
        checks: List of quality checks to validate.
        available_columns: List of columns in the model (if known).

    Raises:
        QualityColumnReferenceError: If a check references a non-existent column (FLOE-DQ105).
    """
    if not available_columns:
        return

    column_set = set(available_columns)
    for check in checks:
        if check.column and check.column not in column_set:
            raise QualityColumnReferenceError(
                model_name=model_name,
                check_name=check.name,
                column_name=check.column,
                available_columns=available_columns,
            )


__all__ = [
    "get_available_quality_providers",
    "validate_check_column_references",
    "validate_quality_provider",
]
