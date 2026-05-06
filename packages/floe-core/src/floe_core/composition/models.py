"""Typed models for plugin composition validation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PluginCapabilities(BaseModel):
    """Capabilities a plugin provides to the composition resolver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_type: str = Field(..., min_length=1)
    plugin_name: str = Field(..., min_length=1)
    capabilities: dict[str, Any] = Field(default_factory=dict)

    @property
    def ref(self) -> str:
        """Return a stable plugin reference for diagnostics."""
        return f"{self.plugin_type}:{self.plugin_name}"


class PluginRequirements(BaseModel):
    """Requirements a plugin needs from peer plugins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_type: str = Field(..., min_length=1)
    plugin_name: str = Field(..., min_length=1)
    requirements: dict[str, Any] = Field(default_factory=dict)

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
