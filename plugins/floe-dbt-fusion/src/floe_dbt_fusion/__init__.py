"""floe-dbt-fusion: DBT plugin using dbt Fusion CLI.

This package provides DBTFusionPlugin, which wraps dbt Fusion's Rust-based
CLI for high-performance parallel execution.

Features:
- ~30x faster parsing than dbt-core for large projects
- Thread-safe (Rust memory safety)
- Automatic fallback to dbt-core when Rust adapters unavailable
"""

from __future__ import annotations

__all__: list[str] = []
