"""Tests for connect() guards against unconfigured state (AC-4).

Verifies that Polaris connect() and MinIO get_pyiceberg_fileio() raise
PluginConfigurationError when self._config is None.
"""

from __future__ import annotations

import pytest

from floe_core.plugin_errors import PluginConfigurationError


@pytest.mark.requirement("ARC-001")
def test_polaris_connect_raises_when_unconfigured() -> None:
    """Polaris connect() must raise PluginConfigurationError when _config is None.

    AC-4 condition 1: connect() raises PluginConfigurationError when not configured.
    """
    from unittest.mock import MagicMock

    from floe_catalog_polaris.config import PolarisCatalogConfig
    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    config = MagicMock(spec=PolarisCatalogConfig)
    plugin = PolarisCatalogPlugin(config=config)
    # Reset config to simulate unconfigured state
    plugin.configure(None)
    assert plugin.is_configured is False

    with pytest.raises(PluginConfigurationError, match="not configured"):
        plugin.connect({})


@pytest.mark.requirement("ARC-001")
def test_polaris_connect_error_includes_plugin_name() -> None:
    """Polaris connect() error message must include plugin name.

    AC-4 condition 3: Error message includes plugin name and 'not configured'.
    """
    from unittest.mock import MagicMock

    from floe_catalog_polaris.config import PolarisCatalogConfig
    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    config = MagicMock(spec=PolarisCatalogConfig)
    plugin = PolarisCatalogPlugin(config=config)
    plugin.configure(None)

    with pytest.raises(PluginConfigurationError) as exc_info:
        plugin.connect({})

    assert "polaris" in str(exc_info.value).lower()


@pytest.mark.requirement("ARC-001")
def test_minio_get_pyiceberg_fileio_raises_when_unconfigured() -> None:
    """MinIO get_pyiceberg_fileio() must raise PluginConfigurationError when unconfigured.

    AC-4 condition 2: get_pyiceberg_fileio() raises PluginConfigurationError.
    """
    from floe_storage_minio.plugin import MinIOStoragePlugin

    plugin = MinIOStoragePlugin(config=None)
    assert plugin.is_configured is False

    with pytest.raises(PluginConfigurationError, match="not configured"):
        plugin.get_pyiceberg_fileio()


@pytest.mark.requirement("ARC-001")
def test_minio_error_includes_plugin_name() -> None:
    """MinIO error message must include plugin name.

    AC-4 condition 3: Error message includes plugin name and 'not configured'.
    """
    from floe_storage_minio.plugin import MinIOStoragePlugin

    plugin = MinIOStoragePlugin(config=None)

    with pytest.raises(PluginConfigurationError) as exc_info:
        plugin.get_pyiceberg_fileio()

    assert "minio" in str(exc_info.value).lower()


@pytest.mark.requirement("ARC-001")
def test_polaris_connect_after_configure_none_raises() -> None:
    """Calling connect() after configure(None) on a previously-configured plugin raises.

    AC-6 condition 6: config reset edge case.
    """
    from unittest.mock import MagicMock

    from floe_catalog_polaris.config import PolarisCatalogConfig
    from floe_catalog_polaris.plugin import PolarisCatalogPlugin

    config = MagicMock(spec=PolarisCatalogConfig)
    plugin = PolarisCatalogPlugin(config=config)
    assert plugin.is_configured is True

    # Reset config
    plugin.configure(None)
    assert plugin.is_configured is False

    with pytest.raises(PluginConfigurationError, match="not configured"):
        plugin.connect({})


@pytest.mark.requirement("ARC-001")
def test_minio_fileio_after_configure_none_raises() -> None:
    """Calling get_pyiceberg_fileio() after configure(None) raises.

    AC-6 condition 6: config reset edge case.
    """
    from unittest.mock import MagicMock

    from floe_storage_minio.config import MinIOStorageConfig
    from floe_storage_minio.plugin import MinIOStoragePlugin

    config = MagicMock(spec=MinIOStorageConfig)
    plugin = MinIOStoragePlugin(config=config)
    assert plugin.is_configured is True

    # Reset config
    plugin.configure(None)
    assert plugin.is_configured is False

    with pytest.raises(PluginConfigurationError, match="not configured"):
        plugin.get_pyiceberg_fileio()
