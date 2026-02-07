"""Unit tests for FloeIngestionTranslator (T031).

The FloeIngestionTranslator customizes dagster-dlt's DagsterDltTranslator
to use floe naming conventions for ingestion assets.

Requirements:
    T031: Unit tests for FloeIngestionTranslator
    FR-061: Asset naming convention ingestion__{source}__{resource}
    FR-064: Asset metadata includes source_type and destination_table
"""

from __future__ import annotations

import pytest


class TestFloeIngestionTranslator:
    """Tests for FloeIngestionTranslator asset key naming."""

    @pytest.mark.requirement("4F-FR-061")
    def test_translator_naming_convention(self) -> None:
        """Test translator produces ingestion__{source}__{resource} naming.

        Given a dlt resource with source_name and resource_name, the
        translator should produce asset key: ingestion__{source}__{resource}.
        """
        pytest.fail(
            "Requires dagster-dlt dependency — "
            "implement when dagster-dlt is installed"
        )

    @pytest.mark.requirement("4F-FR-064")
    def test_translator_includes_metadata(self) -> None:
        """Test translator includes source_type and destination_table metadata.

        Given a dlt resource, the translator should include metadata
        with source_type and destination_table attributes.
        """
        pytest.fail(
            "Requires dagster-dlt dependency — "
            "implement when dagster-dlt is installed"
        )
