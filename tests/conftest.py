"""Root-level test configuration for floe.

This conftest.py provides shared fixtures and configuration for all
root-level tests (contract tests, e2e tests).

Note:
    Root-level tests are for cross-package contracts and full platform
    workflows. Package-specific tests belong in their respective
    packages/*/tests/ directories.
"""

from __future__ import annotations

import pytest
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION


@pytest.fixture
def compiled_artifacts_version() -> str:
    """Current CompiledArtifacts schema version.

    Tests should use this fixture instead of hardcoding version strings.
    When the schema version changes, all tests automatically adapt.

    Returns:
        Current version string (e.g., "0.3.0").

    Example:
        >>> def test_version_matches_schema(compiled_artifacts_version):
        ...     assert compiled_artifacts_version == "0.3.0"
    """
    return COMPILED_ARTIFACTS_VERSION


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "requirement(id): Mark test as covering a specific requirement",
    )
