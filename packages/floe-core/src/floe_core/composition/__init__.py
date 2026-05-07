"""Plugin composition validation primitives."""

from floe_core.composition.models import (
    CompositionIssue,
    CompositionValidationResult,
    CredentialMode,
    IdentityMode,
    PluginCapabilities,
    PluginRequirements,
    SecretProjectionMode,
)
from floe_core.composition.resolver import CompositionResolver

__all__ = [
    "CompositionIssue",
    "CompositionResolver",
    "CompositionValidationResult",
    "CredentialMode",
    "IdentityMode",
    "PluginCapabilities",
    "PluginRequirements",
    "SecretProjectionMode",
]
