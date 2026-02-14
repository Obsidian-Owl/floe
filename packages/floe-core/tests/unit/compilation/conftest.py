"""Unit test fixtures for the compilation module.

This module provides fixtures specific to compilation unit tests, which:
- Run without external services (no K8s, no databases)
- Use mocks/fakes for all plugin dependencies
- Execute quickly (< 1s per test)

For shared fixtures across all test tiers, see ../conftest.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

MINIMAL_SPEC_YAML = """\
apiVersion: floe.dev/v1
kind: FloeSpec
metadata:
  name: test-product
  version: 1.0.0
transforms:
  - name: customers
    tags: []
"""

MINIMAL_MANIFEST_YAML = """\
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: test-platform
  version: 1.0.0
  owner: test@example.com
plugins:
  compute:
    type: duckdb
  orchestrator:
    type: dagster
"""


@pytest.fixture
def spec_path(tmp_path: Path) -> Path:
    """Write minimal spec YAML and return its path."""
    path = tmp_path / "floe.yaml"
    path.write_text(MINIMAL_SPEC_YAML)
    return path


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    """Write minimal manifest YAML and return its path."""
    path = tmp_path / "manifest.yaml"
    path.write_text(MINIMAL_MANIFEST_YAML)
    return path


@pytest.fixture
def patch_version_compat() -> Any:
    """Patch version compatibility to allow DuckDB plugin (1.0) with platform (0.1)."""
    with patch("floe_core.plugins.loader.is_compatible", return_value=True):
        yield


@pytest.fixture
def mock_compute_plugin() -> Any:
    """Mock get_compute_plugin to return a plugin with no config schema (like DuckDB).

    This allows unit tests to run without the actual DuckDB plugin installed.
    The mock plugin returns None for get_config_schema(), simulating DuckDB's
    behavior of requiring no credentials.
    """
    mock_plugin = MagicMock()
    mock_plugin.get_config_schema.return_value = None  # DuckDB has no required config
    mock_plugin.generate_dbt_profile.return_value = {
        "type": "duckdb",
        "path": ":memory:",
    }

    with patch(
        "floe_core.compilation.dbt_profiles.get_compute_plugin",
        return_value=mock_plugin,
    ):
        yield
