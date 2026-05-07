"""Typed models for plugin composition validation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilitySet(BaseModel):
    """Structured capabilities emitted by a plugin for composition checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[str] = Field(default_factory=list)
    catalog_providers: list[str] = Field(default_factory=list)
    table_formats: list[str] = Field(default_factory=list)
    path_style_access: bool | None = None
    sts: bool | None = None


class RequirementSet(BaseModel):
    """Structured peer requirements consumed by the composition resolver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[str] = Field(default_factory=list)
    catalog_providers: list[str] = Field(default_factory=list)
    table_formats: list[str] = Field(default_factory=list)
    requires_server_side_storage_access: bool | None = None
    supports_no_sts: bool | None = None
    supports_path_style_access: bool | None = None


class PluginCapabilities(BaseModel):
    """Capabilities a plugin provides to the composition resolver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_type: str = Field(..., min_length=1)
    plugin_name: str = Field(..., min_length=1)
    capabilities: CapabilitySet = Field(default_factory=CapabilitySet)

    @property
    def ref(self) -> str:
        """Return a stable plugin reference for diagnostics."""
        return f"{self.plugin_type}:{self.plugin_name}"


class PluginRequirements(BaseModel):
    """Requirements a plugin needs from peer plugins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_type: str = Field(..., min_length=1)
    plugin_name: str = Field(..., min_length=1)
    requirements: RequirementSet = Field(default_factory=RequirementSet)

    @property
    def ref(self) -> str:
        """Return a stable plugin reference for diagnostics."""
        return f"{self.plugin_type}:{self.plugin_name}"


class CompositionIssue(BaseModel):
    """Compatibility issue found while composing selected plugins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: Literal["error", "warning"]
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    plugins: list[str] = Field(default_factory=list)


class CompositionValidationResult(BaseModel):
    """Resolver validation result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    issues: list[CompositionIssue] = Field(default_factory=list)
