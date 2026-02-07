"""Ingestion asset definitions for Dagster orchestrator (T034).

This module will contain FloeIngestionTranslator and create_ingestion_assets()
once dagster-dlt dependency is available.

Requirements:
    T034: Create ingestion asset factory
    FR-061: Asset naming convention ingestion__{source}__{resource}
    FR-064: Asset metadata includes source_type and destination_table

Note:
    FloeIngestionTranslator and create_ingestion_assets() will be implemented
    when dagster-dlt is added as a dependency. The resource factory pattern
    (resources/ingestion.py) works independently of the asset factory.
"""

from __future__ import annotations

# FloeIngestionTranslator and create_ingestion_assets() will be implemented
# when dagster-dlt is added as a dependency. The resource factory pattern
# (resources/ingestion.py) works independently of the asset factory.
