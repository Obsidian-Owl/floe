"""Pytest configuration for schema unit tests.

This module provides fixtures for testing manifest schema models.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def valid_metadata_dict() -> dict[str, str]:
    """Return a valid ManifestMetadata dictionary."""
    return {
        "name": "test-platform",
        "version": "1.0.0",
        "owner": "test@example.com",
        "description": "Test platform configuration",
    }


@pytest.fixture
def valid_2tier_manifest_dict(valid_metadata_dict: dict[str, str]) -> dict[str, object]:
    """Return a valid 2-tier PlatformManifest dictionary."""
    return {
        "apiVersion": "floe.dev/v1",
        "kind": "Manifest",
        "metadata": valid_metadata_dict,
        "plugins": {
            "compute": {"type": "duckdb"},
        },
    }


@pytest.fixture
def valid_enterprise_manifest_dict(
    valid_metadata_dict: dict[str, str],
) -> dict[str, object]:
    """Return a valid enterprise (3-tier) PlatformManifest dictionary."""
    return {
        "apiVersion": "floe.dev/v1",
        "kind": "Manifest",
        "metadata": {
            **valid_metadata_dict,
            "name": "enterprise-platform",
        },
        "scope": "enterprise",
        "plugins": {
            "orchestrator": {"type": "dagster"},
        },
        "approved_plugins": {
            "compute": ["duckdb", "snowflake"],
            "orchestrator": ["dagster"],
        },
        "governance": {
            "pii_encryption": "required",
            "audit_logging": "enabled",
        },
    }
