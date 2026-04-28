"""Shared naming helpers for compiled dbt artifacts."""

from __future__ import annotations

import re


def dbt_project_name(product_name: str) -> str:
    """Return the dbt project/profile identifier derived from a floe product name."""
    return re.sub(r"[^A-Za-z0-9_]", "_", product_name).strip("_") or "floe"
