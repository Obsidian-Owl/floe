"""Schema and artifact version constants.

This module defines the authoritative versions for all floe schemas,
making them single-source-of-truth for both runtime and test code.

Changes here automatically propagate to all schema defaults and fixtures.

Usage:
    # In schema definitions
    from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

    class CompiledArtifacts(BaseModel):
        version: str = Field(default=COMPILED_ARTIFACTS_VERSION, ...)

    # In tests
    from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION

    def test_version(compiled_artifacts_version: str) -> None:
        assert artifacts.version == compiled_artifacts_version
"""

from __future__ import annotations

# floe-core package version (tracks the CLI/library release)
# This appears in compiled artifacts metadata.floe_version
FLOE_VERSION: str = "0.3.0"

# CompiledArtifacts contract version
# Increment MAJOR for breaking changes (remove fields, change types)
# Increment MINOR for backward-compatible additions (new optional fields)
# Increment PATCH for documentation/metadata only changes
COMPILED_ARTIFACTS_VERSION: str = "0.6.0"

# Version history (for documentation and compatibility checks)
COMPILED_ARTIFACTS_VERSION_HISTORY: dict[str, str] = {
    "0.1.0": "Initial version (metadata, identity, mode, observability)",
    "0.2.0": "Add plugins, transforms, dbt_profiles, governance (Epic 2B)",
    "0.3.0": "Add enforcement_result summary (Epic 3B)",
    "0.4.0": "Add quality_config, quality_checks/quality_tier to ResolvedModel",
    "0.5.0": "Add lineage_backend to ResolvedPlugins (Epic 6B)",
    "0.6.0": "Add ingestion to ResolvedPlugins (Epic 4F)",
}


def get_compiled_artifacts_version() -> str:
    """Get the current CompiledArtifacts version.

    Returns:
        Current version string in MAJOR.MINOR.PATCH format.

    Example:
        >>> from floe_core.schemas.versions import get_compiled_artifacts_version
        >>> version = get_compiled_artifacts_version()
        >>> version
        '0.4.0'
    """
    return COMPILED_ARTIFACTS_VERSION


__all__: list[str] = [
    "FLOE_VERSION",
    "COMPILED_ARTIFACTS_VERSION",
    "COMPILED_ARTIFACTS_VERSION_HISTORY",
    "get_compiled_artifacts_version",
]
