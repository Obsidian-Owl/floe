"""Integration tests for DltIngestionPlugin discovery.

These tests validate that the DltIngestionPlugin is correctly discoverable
via entry points and meets all discovery requirements.

Requirements Covered:
- 4F-FR-001: DltIngestionPlugin is discoverable via entry points
- 4F-FR-006: Entry point registration and loading
"""

from __future__ import annotations

import pytest
from floe_core.plugins.ingestion import IngestionPlugin
from testing.base_classes.plugin_discovery_tests import BasePluginDiscoveryTests


@pytest.mark.requirement("4F-FR-001")
class TestDltIngestionPluginDiscovery(BasePluginDiscoveryTests):
    """Integration tests for DltIngestionPlugin discovery.

    Inherits standard plugin discovery tests from BasePluginDiscoveryTests.
    These tests validate:
    - Entry point registration
    - Plugin loading
    - Metadata presence
    - ABC compliance
    - Lifecycle methods
    """

    entry_point_group = "floe.ingestion"
    expected_name = "dlt"
    expected_module_prefix = "floe_ingestion_dlt"
    expected_class_name = "DltIngestionPlugin"
    expected_plugin_abc = IngestionPlugin
