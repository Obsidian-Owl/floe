"""Contract monitoring check implementations.

This package contains the check types that the ContractMonitor executes:
- FreshnessCheck: Detect stale data based on timestamp analysis
- SchemaDriftCheck: Detect schema changes via CatalogPlugin
- QualityCheck: Validate data quality via QualityPlugin
- AvailabilityCheck: Monitor data source availability via ComputePlugin
"""

from __future__ import annotations
