"""Capability policy for Dagster alpha runtime proofs."""

from __future__ import annotations

from dataclasses import dataclass

from floe_core.schemas.compiled_artifacts import ResolvedPlugins


class AlphaCapabilityError(RuntimeError):
    """Raised when a configured alpha proof profile is missing a required capability."""


@dataclass(frozen=True)
class CapabilityPolicy:
    """Runtime capability policy for Dagster definitions."""

    require_catalog: bool = False
    require_storage: bool = False
    require_lineage: bool = False

    @classmethod
    def default(cls) -> CapabilityPolicy:
        return cls()

    @classmethod
    def alpha(cls) -> CapabilityPolicy:
        return cls(require_catalog=True, require_storage=True, require_lineage=True)

    def validate_required_plugins(self, plugins: ResolvedPlugins | None) -> None:
        missing: list[str] = []
        if plugins is None:
            missing.extend(self._all_required_names())
        else:
            if self.require_catalog and plugins.catalog is None:
                missing.append("catalog")
            if self.require_storage and plugins.storage is None:
                missing.append("storage")
            if self.require_lineage and plugins.lineage_backend is None:
                missing.append("lineage_backend")

        if missing:
            joined = ", ".join(sorted(set(missing)))
            raise AlphaCapabilityError(
                f"Alpha runtime profile requires configured capability: {joined}"
            )

    def _all_required_names(self) -> list[str]:
        names: list[str] = []
        if self.require_catalog:
            names.append("catalog")
        if self.require_storage:
            names.append("storage")
        if self.require_lineage:
            names.append("lineage_backend")
        return names
