"""dlt source construction adapters for Dagster ingestion assets."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from floe_orchestrator_dagster.ingestion.filesystem_sources import build_filesystem_source


def build_dlt_source(source_config: Mapping[str, Any], *, project_dir: Path) -> Any:
    """Build an executable dlt source/resource from compiled ingestion config."""
    if source_config.get("source_type") == "filesystem":
        return build_filesystem_source(source_config, project_dir=project_dir)
    source_name = source_config.get("name", "unnamed")
    source_type = source_config.get("source_type", "missing")
    raise ValueError(f"Unsupported ingestion source_type {source_type!r} for {source_name!r}")


__all__ = [
    "build_dlt_source",
    "build_filesystem_source",
]
